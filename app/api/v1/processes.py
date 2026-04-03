import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import AccessContext, get_access_context, get_current_internal_user, get_db
from app.models.process import ProcessStatus, is_valid_transition
from app.models.user import User
from app.repositories import ProcessRepository
from app.schemas.audit_log import AuditLogRead
from app.schemas.process import Process, ProcessCreate, ProcessStatusUpdate, ProcessUpdate

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=list[Process])
def list_processes(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    access_context: AccessContext = Depends(get_access_context),
) -> Any:
    """Lista processos respeitando o escopo do usuário autenticado."""
    repo = ProcessRepository(db, access_context.tenant_id)
    return repo.list(skip=skip, limit=limit, client_id=access_context.client_id)


@router.post("/", response_model=Process, status_code=status.HTTP_201_CREATED)
def create_process(
    *,
    db: Session = Depends(get_db),
    process_in: ProcessCreate,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Cria um novo processo ambiental."""
    repo = ProcessRepository(db, current_user.tenant_id)
    process = repo.create(process_in.model_dump(exclude={"tenant_id"}))
    repo.add_audit(
        user_id=current_user.id,
        process=process,
        action="created",
        details="Processo criado via API",
    )
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
    repo = ProcessRepository(db, access_context.tenant_id)
    return repo.get_scoped_or_404(process_id, client_id=access_context.client_id)


@router.put("/{process_id}", response_model=Process)
def update_process(
    process_id: int,
    *,
    db: Session = Depends(get_db),
    process_in: ProcessUpdate,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Atualiza um processo ambiental."""
    repo = ProcessRepository(db, current_user.tenant_id)
    process = repo.update(
        process_id,
        process_in.model_dump(exclude_unset=True),
        detail="Processo não encontrado",
    )
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
    repo = ProcessRepository(db, current_user.tenant_id)
    process = repo.get_or_404(process_id, detail="Processo não encontrado")

    if not is_valid_transition(process.status, status_update.status):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transição de status inválida: não é permitido ir de '{process.status.value}' para '{status_update.status.value}'",
        )

    # Validar se existem tarefas pendentes antes de avançar o processo
    if status_update.status not in [ProcessStatus.cancelado, ProcessStatus.arquivado, ProcessStatus.triagem, ProcessStatus.lead]:
        incomplete_tasks = repo.count_incomplete_tasks(process.id)
        if incomplete_tasks > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Não é possível avançar o processo. Existem {incomplete_tasks} tarefa(s) pendente(s).",
            )

    old_status = process.status.value
    process.status = status_update.status

    repo.add_audit(
        user_id=current_user.id,
        process=process,
        action="status_changed",
        details="Status alterado via API",
        old_value=old_status,
        new_value=status_update.status.value,
    )

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
    repo = ProcessRepository(db, current_user.tenant_id)
    repo.delete(process_id, detail="Processo não encontrado")
    db.commit()


@router.get("/{process_id}/timeline", response_model=list[AuditLogRead])
def get_process_timeline(
    process_id: int,
    db: Session = Depends(get_db),
    access_context: AccessContext = Depends(get_access_context),
) -> Any:
    """Retorna a linha do tempo (timeline) de eventos e logs de auditoria do processo."""
    repo = ProcessRepository(db, access_context.tenant_id)
    repo.get_scoped_or_404(process_id, client_id=access_context.client_id)
    return repo.get_timeline(process_id)
