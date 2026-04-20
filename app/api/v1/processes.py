import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import AccessContext, get_access_context, get_current_internal_user, get_db
from app.models.macroetapa import (
    MACROETAPA_LABELS,
    MACROETAPA_METADATA,
    MACROETAPA_ORDER,
    MACROETAPA_TRANSITIONS,
    Macroetapa,
    MacroetapaChecklist,
    MacroetapaState,
    can_advance_macroetapa,
    compute_macroetapa_state,
    list_macroetapa_blockers,
)
from app.models.process import Process as ProcessModel, ProcessStatus, is_valid_transition
from app.models.user import User
from app.repositories import ProcessRepository
from app.schemas.audit_log import AuditLogRead
from app.schemas.macroetapa import (
    ActionToggleRequest,
    ActionValidateRequest,
    CanAdvanceResponse,
    KanbanColumn,
    KanbanProcessCard,
    KanbanResponse,
    MacroetapaAdvanceRequest,
    MacroetapaChecklistResponse,
    MacroetapaStatusResponse,
    StageOutputCreate,
    StageOutputResponse,
)
from app.schemas.process import Process, ProcessCreate, ProcessDetail, ProcessStatusUpdate, ProcessUpdate
from app.services.macroetapa_engine import (
    advance_macroetapa,
    get_macroetapa_status,
    initialize_macroetapa_checklists,
    toggle_action,
    validate_action,
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


@router.get("/kanban", response_model=KanbanResponse)
def get_kanban_view(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Retorna visão kanban organizada por macroetapas com cards enriquecidos."""
    from app.models.checklist_template import ProcessChecklist
    from app.models.client import Client
    from app.models.document import Document
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

    # Regente Cam1: gate de prontidão precisa de process_checklists e documentos
    proc_checklists = (
        db.query(ProcessChecklist)
        .filter(ProcessChecklist.process_id.in_(process_ids))
        .all()
    ) if process_ids else []
    pc_map: dict[int, ProcessChecklist] = {pc.process_id: pc for pc in proc_checklists}

    # Contagem de documentos anexados por processo
    doc_counts: dict[int, int] = {}
    if process_ids:
        for pid, count in (
            db.query(Document.process_id, func.count(Document.id))
            .filter(Document.process_id.in_(process_ids))
            .group_by(Document.process_id)
            .all()
        ):
            doc_counts[pid] = count

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

        # Gate de prontidão (CAM1-011)
        has_min = bool(
            client
            and client.full_name
            and (client.phone or client.email)
            and prop
            and prop.name
        )
        doc_count = doc_counts.get(proc.id, 0)
        has_complementary = doc_count > 0
        missing_docs = 0
        pc = pc_map.get(proc.id)
        if pc and pc.items:
            for item in pc.items:
                if item.get("required") and item.get("status") == "pending":
                    missing_docs += 1

        # CAM3FT-004 — estado formal da etapa (cálculo dinâmico)
        blockers_list = list_macroetapa_blockers(
            cl, documents_pending_required=missing_docs
        )
        state_enum = (
            compute_macroetapa_state(
                cl, is_current=True, has_blockers=bool(blockers_list)
            )
            if cl
            else MacroetapaState.nao_iniciada
        )

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
            has_alerts=missing_docs > 0 or state_enum == MacroetapaState.travada,
            created_at=proc.created_at,
            entry_type=proc.entry_type.value if proc.entry_type else None,
            has_minimal_base=has_min,
            has_complementary_base=has_complementary,
            missing_docs_count=missing_docs,
            macroetapa_state=state_enum.value,
            blockers=blockers_list,
        )
        columns_data[etapa].append(card)

    # CAM3FT-003 — counts agregados por estado em cada coluna
    columns = [
        KanbanColumn(
            macroetapa=m.value,
            label=MACROETAPA_LABELS[m],
            count=len(columns_data[m.value]),
            blocked_count=sum(
                1 for c in columns_data[m.value] if c.macroetapa_state == MacroetapaState.travada.value
            ),
            ready_to_advance_count=sum(
                1 for c in columns_data[m.value] if c.macroetapa_state == MacroetapaState.pronta_para_avancar.value
            ),
            cards=columns_data[m.value],
        )
        for m in MACROETAPA_ORDER
    ]

    return KanbanResponse(
        columns=columns,
        total_active=sum(c.count for c in columns),
    )


@router.get("/{process_id}", response_model=ProcessDetail)
def get_process(
    process_id: int,
    db: Session = Depends(get_db),
    access_context: AccessContext = Depends(get_access_context),
) -> Any:
    """Retorna um processo pelo ID.

    CAM1-011 (Sprint I) — inclui gates de prontidão (`has_minimal_base`,
    `has_complementary_base`, `missing_docs_count`) com a mesma semântica do
    kanban, para o card de detalhe mostrar os mesmos indicadores.
    """
    from app.models.client import Client  # noqa: PLC0415
    from app.models.document import Document  # noqa: PLC0415
    from app.models.checklist_template import ProcessChecklist  # noqa: PLC0415
    from app.models.property import Property  # noqa: PLC0415

    repo = ProcessRepository(db, access_context.tenant_id)
    process = repo.get_scoped_or_404(process_id, client_id=access_context.client_id)

    # Gate: base mínima (cliente com contato + imóvel com nome)
    client = db.query(Client).filter(Client.id == process.client_id).first() if process.client_id else None
    prop = db.query(Property).filter(Property.id == process.property_id).first() if process.property_id else None
    has_min = bool(
        client
        and client.full_name
        and (client.phone or client.email)
        and prop
        and prop.name
    )

    # Gate: base complementada (≥1 documento)
    doc_count = (
        db.query(func.count(Document.id))
        .filter(
            Document.process_id == process.id,
            Document.tenant_id == access_context.tenant_id,
            Document.deleted_at.is_(None),
        )
        .scalar() or 0
    )

    # Gate: docs obrigatórios pendentes
    missing_docs = 0
    pc = (
        db.query(ProcessChecklist)
        .filter(ProcessChecklist.process_id == process.id)
        .first()
    )
    if pc and pc.items:
        for item in pc.items:
            if item.get("required") and item.get("status") == "pending":
                missing_docs += 1

    # Pydantic converte ORM -> dict via from_attributes; adicionamos os gates computados.
    detail = ProcessDetail.model_validate(process)
    detail.has_minimal_base = has_min
    detail.has_complementary_base = doc_count > 0
    detail.missing_docs_count = missing_docs
    return detail


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


def _compute_can_advance(
    db: Session,
    process: ProcessModel,
    *,
    require_complete: bool = True,
) -> CanAdvanceResponse:
    """Helper interno: avalia se um processo pode avançar de etapa."""
    from app.models.checklist_template import ProcessChecklist  # noqa: PLC0415

    current_etapa_str = process.macroetapa
    current_etapa: Optional[Macroetapa] = None
    if current_etapa_str:
        try:
            current_etapa = Macroetapa(current_etapa_str)
        except ValueError:
            current_etapa = None

    cl = None
    if current_etapa:
        cl = (
            db.query(MacroetapaChecklist)
            .filter(
                MacroetapaChecklist.process_id == process.id,
                MacroetapaChecklist.macroetapa == current_etapa.value,
            )
            .first()
        )

    # Documentos obrigatórios pendentes do ProcessChecklist
    pc = (
        db.query(ProcessChecklist)
        .filter(ProcessChecklist.process_id == process.id)
        .first()
    )
    missing_docs = 0
    if pc and pc.items:
        for item in pc.items:
            if item.get("required") and item.get("status") == "pending":
                missing_docs += 1

    can, blockers = can_advance_macroetapa(
        cl,
        documents_pending_required=missing_docs,
        require_complete=require_complete,
    )

    state_value = None
    if cl:
        state_value = compute_macroetapa_state(
            cl, is_current=True, has_blockers=bool(blockers)
        ).value

    next_etapa = None
    if current_etapa:
        nexts = MACROETAPA_TRANSITIONS.get(current_etapa, [])
        next_etapa = nexts[0].value if nexts else None

    meta = MACROETAPA_METADATA.get(current_etapa, {}) if current_etapa else {}

    # CAM3WS-005 (Sprint K) — lacunas informativas (nice-to-have, não travam avanço).
    # Distintas dos blockers: lacunas sinalizam "informação faltando" que o consultor
    # pode preencher em paralelo; blockers impedem transição.
    from app.models.client import Client  # noqa: PLC0415
    from app.models.property import Property  # noqa: PLC0415

    gaps: list[str] = []
    if process.client_id:
        cli = db.query(Client).filter(Client.id == process.client_id).first()
        if cli:
            if not cli.email:
                gaps.append("E-mail do cliente não preenchido")
            if not cli.phone:
                gaps.append("Telefone do cliente não preenchido")
            if cli.client_type and cli.client_type.value == "pj" and not cli.legal_name:
                gaps.append("Razão social do cliente PJ não preenchida")
    if process.property_id:
        prop = db.query(Property).filter(Property.id == process.property_id).first()
        if prop:
            if not prop.registry_number:
                gaps.append("Matrícula do imóvel não preenchida")
            if not prop.car_code:
                gaps.append("Código CAR do imóvel não preenchido")
            if not prop.total_area_ha:
                gaps.append("Área total do imóvel não informada")
            if not prop.biome:
                gaps.append("Bioma do imóvel não identificado")
    if not process.initial_summary:
        gaps.append("Resumo inicial da demanda (voz do cliente) não registrado")

    return CanAdvanceResponse(
        can_advance=can,
        current_macroetapa=current_etapa.value if current_etapa else None,
        current_state=state_value,
        next_macroetapa=next_etapa,
        blockers=blockers,
        gaps=gaps,
        objective=meta.get("objective"),
        expected_outputs=meta.get("expected_outputs", []),
    )


@router.get("/{process_id}/can-advance", response_model=CanAdvanceResponse)
def get_can_advance(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """CAM3FT-005 — Avalia se o processo pode avançar de etapa.

    Retorna `can_advance` + lista de blockers (output mínimo, docs pendentes,
    validação humana pendente). Cliente usa pra desabilitar botão "Avançar".
    """
    repo = ProcessRepository(db, current_user.tenant_id)
    process = repo.get_or_404(process_id, detail="Processo não encontrado")
    return _compute_can_advance(db, process)


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

    # CAM3FT-005 — guard: bloqueia avanço se gate falhar
    # (mantém soft mode: aceita override via header se necessário no futuro)
    gate = _compute_can_advance(db, process)
    if not gate.can_advance:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Avanço bloqueado pelo gate de prontidão.",
                "blockers": gate.blockers,
                "current_state": gate.current_state,
            },
        )

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

    # QA-008 — invalida cache do kanban-insights para o banner do Quadro
    # refletir o avanço imediatamente (evita "mentira" de até 24h).
    try:
        from app.api.v1.dashboard import _kanban_insights_cache_key  # noqa: PLC0415
        from app.services.notifications import _get_redis_client  # noqa: PLC0415
        _get_redis_client().delete(_kanban_insights_cache_key(current_user.tenant_id))
    except Exception as exc:
        logger.warning("Falha ao invalidar kanban-insights cache: %s", exc)

    # Trigger chain de agentes automatica por macroetapa (async, fire-and-forget)
    _MACROETAPA_CHAINS: dict[str, str] = {
        "diagnostico_tecnico": "diagnostico_completo",
        "caminho_regulatorio": "enquadramento_regulatorio",
        "orcamento_negociacao": "gerar_proposta",
    }
    chain_name = _MACROETAPA_CHAINS.get(body.macroetapa.value)
    if chain_name:
        try:
            from app.workers.agent_tasks import run_agent_chain  # noqa: PLC0415
            run_agent_chain.delay(
                chain_name=chain_name,
                tenant_id=current_user.tenant_id,
                user_id=current_user.id,
                process_id=process_id,
                metadata={},
                stop_on_review=True,
            )
            logger.info(
                "Chain '%s' enfileirada para process_id=%s (macroetapa=%s)",
                chain_name, process_id, body.macroetapa.value,
            )
        except Exception as exc:
            logger.warning("Falha ao enfileirar chain '%s': %s", chain_name, exc)

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


@router.post(
    "/{process_id}/macroetapa/{macroetapa}/actions/validate",
    response_model=MacroetapaChecklistResponse,
)
def validate_macroetapa_action(
    process_id: int,
    macroetapa: Macroetapa,
    *,
    db: Session = Depends(get_db),
    body: ActionValidateRequest,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """CAM3WS-005 — Humano valida o resultado de uma ação que precisa de validação.

    Útil quando agentes IA produziram uma saída que requer assinatura humana
    (ex: leitura técnica, caminho regulatório, proposta).
    """
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

    checklist = validate_action(db, checklist, body.action_id, user_id=current_user.id)
    db.commit()
    db.refresh(checklist)
    return checklist


# ---------------------------------------------------------------------------
# CAM3WS-006 — Artefatos / saídas das etapas
# ---------------------------------------------------------------------------

@router.get("/{process_id}/artifacts", response_model=list[StageOutputResponse])
def list_process_artifacts(
    process_id: int,
    macroetapa: Optional[Macroetapa] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Lista artefatos produzidos por etapa para o processo."""
    from app.models.stage_output import StageOutput  # noqa: PLC0415

    repo = ProcessRepository(db, current_user.tenant_id)
    repo.get_or_404(process_id, detail="Processo não encontrado")

    q = db.query(StageOutput).filter(
        StageOutput.process_id == process_id,
        StageOutput.tenant_id == current_user.tenant_id,
    )
    if macroetapa:
        q = q.filter(StageOutput.macroetapa == macroetapa.value)
    return q.order_by(StageOutput.created_at.desc()).all()


@router.post(
    "/{process_id}/artifacts",
    response_model=StageOutputResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_process_artifact(
    process_id: int,
    body: StageOutputCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Registra um artefato/saída para uma etapa do processo.

    Pode ser produzido por humano (produced_by_user_id) ou por agente
    (produced_by_agent). Se vier de agente, normalmente needs_human_validation=True.
    """
    from app.models.stage_output import StageOutput  # noqa: PLC0415

    repo = ProcessRepository(db, current_user.tenant_id)
    repo.get_or_404(process_id, detail="Processo não encontrado")

    artifact = StageOutput(
        tenant_id=current_user.tenant_id,
        process_id=process_id,
        macroetapa=body.macroetapa.value,
        output_type=body.output_type,
        title=body.title,
        content=body.content,
        content_data=body.content_data or {},
        produced_by_agent=body.produced_by_agent,
        produced_by_user_id=current_user.id if not body.produced_by_agent else None,
        needs_human_validation=body.needs_human_validation,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


@router.post("/{process_id}/artifacts/{artifact_id}/validate", response_model=StageOutputResponse)
def validate_process_artifact(
    process_id: int,
    artifact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """CAM3WS-005 + CAM3WS-006 — humano valida um artefato gerado por IA."""
    from datetime import datetime, UTC  # noqa: PLC0415
    from app.models.stage_output import StageOutput  # noqa: PLC0415

    artifact = (
        db.query(StageOutput)
        .filter(
            StageOutput.id == artifact_id,
            StageOutput.process_id == process_id,
            StageOutput.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not artifact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artefato não encontrado.")

    artifact.validated_at = datetime.now(UTC)
    artifact.validated_by_user_id = current_user.id
    db.commit()
    db.refresh(artifact)
    return artifact
