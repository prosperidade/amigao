from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.api.deps import AccessContext, get_access_context, get_current_internal_user, get_db
from app.models.process import Process as ProcessModel, is_valid_transition, ProcessStatus
from app.models.task import TERMINAL_TASK_STATUSES, Task as TaskModel
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.process import Process, ProcessCreate, ProcessUpdate, ProcessStatusUpdate

router = APIRouter()
logger = logging.getLogger(__name__)


def _scoped_process_query(db: Session, access_context: AccessContext):
    query = db.query(ProcessModel).filter(ProcessModel.tenant_id == access_context.tenant_id)
    if access_context.client_id is not None:
        query = query.filter(ProcessModel.client_id == access_context.client_id)
    return query


@router.get("/", response_model=List[Process])
def list_processes(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    access_context: AccessContext = Depends(get_access_context),
) -> Any:
    """Lista processos respeitando o escopo do usuário autenticado."""
    processes = _scoped_process_query(db, access_context).offset(skip).limit(limit).all()
    return processes


@router.post("/", response_model=Process, status_code=status.HTTP_201_CREATED)
def create_process(
    *,
    db: Session = Depends(get_db),
    process_in: ProcessCreate,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Cria um novo processo ambiental."""
    process = ProcessModel(
        **process_in.dict(exclude={"tenant_id"}),
        tenant_id=current_user.tenant_id,
    )
    db.add(process)
    db.flush()

    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        entity_type="process",
        entity_id=process.id,
        action="created",
        details="Processo criado via API"
    )
    db.add(audit)
    db.commit()
    db.refresh(process)
    return process


@router.get("/{process_id}", response_model=Process)
def get_process(
    process_id: int,
    db: Session = Depends(get_db),
    access_context: AccessContext = Depends(get_access_context),
) -> Any:
    """Retorna um processo pelo ID."""
    process = (
        _scoped_process_query(db, access_context)
        .filter(ProcessModel.id == process_id)
        .first()
    )
    if not process:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    return process


@router.put("/{process_id}", response_model=Process)
def update_process(
    process_id: int,
    *,
    db: Session = Depends(get_db),
    process_in: ProcessUpdate,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Atualiza um processo ambiental."""
    process = (
        db.query(ProcessModel)
        .filter(ProcessModel.id == process_id, ProcessModel.tenant_id == current_user.tenant_id)
        .first()
    )
    if not process:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    update_data = process_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(process, field, value)
    db.add(process)
    db.commit()
    db.refresh(process)
    return process


@router.post("/{process_id}/status", response_model=Process)
def update_process_status(
    process_id: int,
    *,
    db: Session = Depends(get_db),
    status_update: ProcessStatusUpdate,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Avança o estado do processo usando a máquina de estados (validando regras de negócio)."""
    process = (
        db.query(ProcessModel)
        .filter(ProcessModel.id == process_id, ProcessModel.tenant_id == current_user.tenant_id)
        .first()
    )
    if not process:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
        
    if not is_valid_transition(process.status, status_update.status):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Transição de status inválida: não é permitido ir de '{process.status.value}' para '{status_update.status.value}'"
        )
        
    # Validar se existem tarefas pendentes antes de avançar o processo
    if status_update.status not in [ProcessStatus.cancelado, ProcessStatus.arquivado, ProcessStatus.triagem, ProcessStatus.lead]:
        incomplete_tasks = db.query(TaskModel).filter(
            TaskModel.process_id == process.id,
            TaskModel.status.notin_(list(TERMINAL_TASK_STATUSES))
        ).count()
        if incomplete_tasks > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Não é possível avançar o processo. Existem {incomplete_tasks} tarefa(s) pendente(s)."
            )
        
    old_status = process.status.value
    process.status = status_update.status
    
    # Gerar log de auditoria
    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        entity_type="process",
        entity_id=process.id,
        action="status_changed",
        old_value=old_status,
        new_value=status_update.status.value,
        details="Status alterado via API"
    )
    db.add(audit)
    
    db.add(process)
    db.commit()
    db.refresh(process)

    # Dispara notificações assíncronas do processo sem bloquear a API
    try:
        from app.workers.tasks import notify_process_status_changed

        notify_process_status_changed.delay(
            tenant_id=process.tenant_id,
            process_id=process.id,
            old_status=old_status,
            new_status=status_update.status.value,
            actor_user_id=current_user.id,
        )
    except Exception as exc:
        logger.warning(
            "Falha ao enfileirar notificação de status do processo %s: %s",
            process.id,
            exc,
        )

    # Dispara a geração de PDF se o processo foi concluído
    if status_update.status == ProcessStatus.concluido:
        try:
            from app.workers.tasks import generate_pdf_report

            generate_pdf_report.delay(tenant_id=process.tenant_id, process_id=process.id)
        except Exception as exc:
            logger.warning(
                "Falha ao enfileirar geração de PDF do processo %s: %s",
                process.id,
                exc,
            )

    return process


@router.delete("/{process_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_process(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> None:
    """Remove um processo."""
    process = (
        db.query(ProcessModel)
        .filter(ProcessModel.id == process_id, ProcessModel.tenant_id == current_user.tenant_id)
        .first()
    )
    if not process:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    db.delete(process)
    db.commit()


@router.get("/{process_id}/timeline")
def get_process_timeline(
    process_id: int,
    db: Session = Depends(get_db),
    access_context: AccessContext = Depends(get_access_context),
) -> Any:
    """Retorna a linha do tempo (timeline) de eventos e logs de auditoria do processo."""
    process = (
        _scoped_process_query(db, access_context)
        .filter(ProcessModel.id == process_id)
        .first()
    )
    if not process:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    
    logs = (
        db.query(AuditLog)
        .filter(
            AuditLog.tenant_id == access_context.tenant_id,
            AuditLog.entity_type == "process",
            AuditLog.entity_id == process_id,
        )
        .order_by(AuditLog.created_at.desc())
        .all()
    )
    return logs
