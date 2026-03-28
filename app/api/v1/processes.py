from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_active_user
from app.models.process import Process as ProcessModel, is_valid_transition, ProcessStatus
from app.models.task import Task as TaskModel, TaskStatus
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.process import Process, ProcessCreate, ProcessUpdate, ProcessStatusUpdate

router = APIRouter()


@router.get("/", response_model=List[Process])
def list_processes(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Lista todos os processos do tenant autenticado."""
    processes = (
        db.query(ProcessModel)
        .filter(ProcessModel.tenant_id == current_user.tenant_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return processes


@router.post("/", response_model=Process, status_code=status.HTTP_201_CREATED)
def create_process(
    *,
    db: Session = Depends(get_db),
    process_in: ProcessCreate,
    current_user: User = Depends(get_current_active_user),
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
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Retorna um processo pelo ID."""
    process = (
        db.query(ProcessModel)
        .filter(ProcessModel.id == process_id, ProcessModel.tenant_id == current_user.tenant_id)
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
    current_user: User = Depends(get_current_active_user),
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
    current_user: User = Depends(get_current_active_user),
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
            TaskModel.status != TaskStatus.done
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

    # Dispara e-mail de notificação para o cliente
    if process.client and process.client.email:
        from app.workers.tasks import send_email_notification
        from app.services.email import format_notification_template
        
        email_html = format_notification_template(process_name=process.title, new_status=status_update.status.value)
        send_email_notification.delay(
            email_to=process.client.email,
            subject=f"Atualização do Processo: {process.title}",
            html_content=email_html
        )

    # Dispara a geração de PDF se o processo foi concluído
    if status_update.status == ProcessStatus.concluido:
        from app.workers.tasks import generate_pdf_report
        generate_pdf_report.delay(tenant_id=process.tenant_id, process_id=process.id)

    return process


@router.delete("/{process_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_process(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
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
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Retorna a linha do tempo (timeline) de eventos e logs de auditoria do processo."""
    process = (
        db.query(ProcessModel)
        .filter(ProcessModel.id == process_id, ProcessModel.tenant_id == current_user.tenant_id)
        .first()
    )
    if not process:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == "process", AuditLog.entity_id == process_id)
        .order_by(AuditLog.created_at.desc())
        .all()
    )
    return logs
