import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import AccessContext, get_access_context, get_current_internal_user, get_db
from app.models.macroetapa import (
    MACROETAPA_LABELS,
    MACROETAPA_ORDER,
    Macroetapa,
    MacroetapaChecklist,
)
from app.models.process import Process as ProcessModel, ProcessStatus, is_valid_transition
from app.models.user import User
from app.repositories import ProcessRepository
from app.schemas.audit_log import AuditLogRead
from app.schemas.macroetapa import (
    ActionToggleRequest,
    KanbanColumn,
    KanbanProcessCard,
    KanbanResponse,
    MacroetapaAdvanceRequest,
    MacroetapaChecklistResponse,
    MacroetapaStatusResponse,
)
from app.schemas.process import Process, ProcessCreate, ProcessStatusUpdate, ProcessUpdate
from app.services.macroetapa_engine import (
    advance_macroetapa,
    get_macroetapa_status,
    initialize_macroetapa_checklists,
    toggle_action,
)

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


# ---------------------------------------------------------------------------
# Macroetapa endpoints
# ---------------------------------------------------------------------------


@router.get("/{process_id}/macroetapa/status", response_model=MacroetapaStatusResponse)
def get_process_macroetapa_status(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Retorna status completo da macroetapa do processo (stepper, checklists, next action)."""
    repo = ProcessRepository(db, current_user.tenant_id)
    process = repo.get_or_404(process_id, detail="Processo não encontrado")
    return get_macroetapa_status(db, process)


@router.post("/{process_id}/macroetapa", response_model=Process)
def advance_process_macroetapa(
    process_id: int,
    *,
    db: Session = Depends(get_db),
    body: MacroetapaAdvanceRequest,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Avança o processo para a próxima macroetapa."""
    repo = ProcessRepository(db, current_user.tenant_id)
    process = repo.get_or_404(process_id, detail="Processo não encontrado")

    process = advance_macroetapa(
        db, process, body.macroetapa,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )

    repo.add_audit(
        user_id=current_user.id,
        process=process,
        action="macroetapa_changed",
        details=f"Macroetapa avançada para {body.macroetapa.value}",
        new_value=body.macroetapa.value,
    )

    db.commit()
    db.refresh(process)
    return process


@router.post("/{process_id}/macroetapa/initialize", response_model=MacroetapaStatusResponse)
def initialize_process_macroetapas(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Inicializa checklists de todas as macroetapas para um processo."""
    repo = ProcessRepository(db, current_user.tenant_id)
    process = repo.get_or_404(process_id, detail="Processo não encontrado")

    if not process.macroetapa:
        process.macroetapa = Macroetapa.entrada_demanda.value

    initialize_macroetapa_checklists(db, process, current_user.tenant_id)
    db.commit()
    db.refresh(process)
    return get_macroetapa_status(db, process)


@router.patch(
    "/{process_id}/macroetapa/{macroetapa}/actions",
    response_model=MacroetapaChecklistResponse,
)
def toggle_macroetapa_action(
    process_id: int,
    macroetapa: Macroetapa,
    *,
    db: Session = Depends(get_db),
    body: ActionToggleRequest,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Marca/desmarca uma ação no checklist de uma macroetapa."""
    repo = ProcessRepository(db, current_user.tenant_id)
    repo.get_or_404(process_id, detail="Processo não encontrado")

    checklist = (
        db.query(MacroetapaChecklist)
        .filter(
            MacroetapaChecklist.process_id == process_id,
            MacroetapaChecklist.macroetapa == macroetapa,
            MacroetapaChecklist.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist da macroetapa não encontrado")

    checklist = toggle_action(db, checklist, body.action_id, body.completed)
    db.commit()
    db.refresh(checklist)
    return checklist


# ---------------------------------------------------------------------------
# Kanban endpoint (enriquecido para frontend)
# ---------------------------------------------------------------------------


@router.get("/kanban", response_model=KanbanResponse)
def get_kanban_view(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Retorna visão kanban organizada por macroetapas com cards enriquecidos."""
    from app.models.client import Client
    from app.models.property import Property

    tenant_id = current_user.tenant_id

    # Buscar processos ativos com macroetapa definida
    processes = (
        db.query(ProcessModel, Client, Property, User)
        .outerjoin(Client, ProcessModel.client_id == Client.id)
        .outerjoin(Property, ProcessModel.property_id == Property.id)
        .outerjoin(User, ProcessModel.responsible_user_id == User.id)
        .filter(
            ProcessModel.tenant_id == tenant_id,
            ProcessModel.deleted_at.is_(None),
            ProcessModel.macroetapa.isnot(None),
            ProcessModel.status.notin_([ProcessStatus.cancelado, ProcessStatus.arquivado]),
        )
        .all()
    )

    # Buscar todos os checklists para calcular completion e next_action
    process_ids = [p.id for p, _, _, _ in processes]
    checklists = (
        db.query(MacroetapaChecklist)
        .filter(MacroetapaChecklist.process_id.in_(process_ids))
        .all()
    ) if process_ids else []

    # Index: {(process_id, macroetapa): checklist}
    cl_map: dict[tuple[int, str], MacroetapaChecklist] = {}
    for cl in checklists:
        cl_map[(cl.process_id, cl.macroetapa.value if hasattr(cl.macroetapa, "value") else cl.macroetapa)] = cl

    # Montar cards por macroetapa
    columns_data: dict[str, list[KanbanProcessCard]] = {m.value: [] for m in MACROETAPA_ORDER}

    for proc, client, prop, responsible in processes:
        etapa = proc.macroetapa
        if etapa not in columns_data:
            continue

        cl = cl_map.get((proc.id, etapa))
        next_action = None
        completion = 0.0
        if cl:
            completion = cl.completion_pct
            for action in (cl.actions or []):
                if not action.get("completed"):
                    next_action = action.get("label")
                    break

        card = KanbanProcessCard(
            id=proc.id,
            title=proc.title,
            client_name=client.full_name if client else None,
            property_name=prop.name if prop else None,
            demand_type=proc.demand_type.value if proc.demand_type else None,
            urgency=proc.urgency,
            priority=proc.priority.value if proc.priority else None,
            macroetapa=etapa,
            macroetapa_label=MACROETAPA_LABELS.get(Macroetapa(etapa), etapa),
            macroetapa_completion_pct=completion,
            responsible_user_name=responsible.full_name if responsible else None,
            next_action=next_action,
            has_alerts=False,
            created_at=proc.created_at,
        )
        columns_data[etapa].append(card)

    columns = [
        KanbanColumn(
            macroetapa=m.value,
            label=MACROETAPA_LABELS[m],
            count=len(columns_data[m.value]),
            cards=columns_data[m.value],
        )
        for m in MACROETAPA_ORDER
    ]

    return KanbanResponse(
        columns=columns,
        total_active=sum(c.count for c in columns),
    )
