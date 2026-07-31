import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import AccessContext, get_access_context, get_current_internal_user, get_db
from app.models.document import Document
from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
from app.models.macroetapa import (
    MACROETAPA_AGENT_CHAIN,
    MACROETAPA_LABELS,
    MACROETAPA_METADATA,
    MACROETAPA_ORDER,
    Macroetapa,
    MacroetapaChecklist,
    MacroetapaState,
    can_advance_macroetapa,
    compute_macroetapa_state,
    list_macroetapa_blockers,
    resolve_next_macroetapa,
)
from app.models.process import Process as ProcessModel
from app.models.process import ProcessStatus, is_valid_transition
from app.models.user import User
from app.repositories import ExtractedFieldStagingRepository, ProcessRepository
from app.schemas.audit_log import AuditLogRead
from app.schemas.extracted_field_staging import (
    BulkAcceptResult,
    ConsolidationResult,
    ExtractedFieldStagingOut,
    StagingDecisionRequest,
    StagingDecisionResult,
)
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
    RunStageAgentsResponse,
    StageOutputCreate,
    StageOutputResponse,
)
from app.schemas.matricula import (
    ChainApplyRequest,
    ChainApplyResult,
    ChainProposalOut,
    MatriculaVigenteMini,
)
from app.schemas.process import (
    Process,
    ProcessCreate,
    ProcessDetail,
    ProcessExtractJob,
    ProcessExtractRequest,
    ProcessExtractResponse,
    ProcessStatusUpdate,
    ProcessUpdate,
)
from app.schemas.requisito_documental import (
    RequisitoDocumentalOut,
    RequisitosDocumentaisResponse,
)
from app.services.macroetapa_engine import (
    advance_macroetapa,
    ensure_macroetapa_checklists,
    get_macroetapa_status,
    has_consolidated,
    has_contract_signed,
    has_proposal_accepted,
    has_rota_validada,
    initialize_macroetapa_checklists,
    stage_agents_executados,
    toggle_action,
    validate_action,
)
from app.services.requisito_documental import (
    REQUISITOS_BASE,
    avaliar_requisitos,
    contar_pendentes,
    contar_pendentes_checklist,
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

    # fix/diagnostico-propaga-estado: set de process_ids com pelo menos uma
    # RegulatoryDiagnosis com `validated_at` preenchido. O badge da etapa de
    # diagnóstico e o gate de avanço cobram esse fato (Princípio 1 — humano
    # assinou). Uma query agregada evita N+1 no kanban.
    from app.models.regulatory import RegulatoryDiagnosis  # noqa: PLC0415

    validated_diagnosis_ids: set[int] = set()
    if process_ids:
        validated_diagnosis_ids = {
            pid
            for (pid,) in db.query(RegulatoryDiagnosis.process_id)
            .filter(
                RegulatoryDiagnosis.tenant_id == tenant_id,
                RegulatoryDiagnosis.process_id.in_(process_ids),
                RegulatoryDiagnosis.validated_at.isnot(None),
            )
            .distinct()
            .all()
        }

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
            missing_docs = contar_pendentes_checklist(
                db, proc.id, tenant_id, pc.items
            )

        try:
            current_macroetapa_enum = Macroetapa(etapa) if etapa else None
        except ValueError:
            current_macroetapa_enum = None
        # CAM3FT-004 — estado formal da etapa (cálculo dinâmico). Sprint 1: o
        # ramo da E2 faz doc pendente ROTEAR (não travar) em diagnostico_preliminar.
        blockers_list = list_macroetapa_blockers(
            cl,
            documents_pending_required=missing_docs,
            current_macroetapa=current_macroetapa_enum,
        )
        diagnosis_validated = proc.id in validated_diagnosis_ids
        state_enum = (
            compute_macroetapa_state(
                cl,
                is_current=True,
                has_blockers=bool(blockers_list),
                current_macroetapa=current_macroetapa_enum,
                diagnosis_validated=diagnosis_validated,
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


@router.get("/{process_id}/requisitos", response_model=RequisitosDocumentaisResponse)
def get_requisitos_documentais(
    process_id: int,
    db: Session = Depends(get_db),
    access_context: AccessContext = Depends(get_access_context),
) -> Any:
    """Os 6 requisitos documentais da Ficha 08 §2, pela fonte única.

    Endpoint de LEITURA da mesma função que alimenta o dossiê, o checklist e os
    gates — para a tela não reimplementar a pergunta pela nona vez. Ver
    ``docs/auditoria/AUDITORIA_REQUISITOS_DOCUMENTAIS_2026-07-20.md``.
    """
    repo = ProcessRepository(db, access_context.tenant_id)
    process = repo.get_scoped_or_404(process_id, client_id=access_context.client_id)

    resultados = avaliar_requisitos(db, process.id, access_context.tenant_id)
    ordem = [r.key for r in REQUISITOS_BASE]

    return RequisitosDocumentaisResponse(
        process_id=process.id,
        requisitos=[
            RequisitoDocumentalOut(
                requisito=resultados[k].requisito,
                label=resultados[k].label,
                status=resultados[k].status.value,
                detalhe=resultados[k].detalhe,
                document_ids=resultados[k].document_ids,
                gaps=resultados[k].gaps,
                alertas=resultados[k].alertas,
                satisfeito_por=resultados[k].satisfeito_por,
                pendente=resultados[k].pendente,
            )
            for k in ordem
        ],
        pendentes=contar_pendentes(resultados),
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
    from app.models.checklist_template import ProcessChecklist  # noqa: PLC0415
    from app.models.client import Client  # noqa: PLC0415
    from app.models.document import Document  # noqa: PLC0415
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
        missing_docs = contar_pendentes_checklist(
            db, process.id, access_context.tenant_id, pc.items
        )

    # (contagem via fonte única — ver `contar_pendentes_checklist`)

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


@router.post("/{process_id}/extract", response_model=ProcessExtractResponse)
def extract_process_documents(
    process_id: int,
    body: ProcessExtractRequest = ProcessExtractRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Dispara extração de campos em todos os documentos do processo.

    Para cada Document do processo:
      - Se já há `extracted_text` cacheado e `force=False`: enfileira só
        o agente `extrator` (rápido, sem custo de OCR).
      - Caso contrário: enfileira a chain `workers.ocr_then_extract` que
        roda OCR (pypdf/Gemini/OpenAI Vision) e depois despacha o extrator.

    Resolve o sintoma "rodar o extrator com metadata vazia é no-op" da UI
    — agora há um caminho explícito de extração por processo.
    """
    from app.models.document import Document  # noqa: PLC0415

    repo = ProcessRepository(db, current_user.tenant_id)
    process = repo.get_or_404(process_id, detail="Processo não encontrado")

    docs = (
        db.query(Document)
        .filter(
            Document.process_id == process.id,
            Document.tenant_id == current_user.tenant_id,
            Document.deleted_at.is_(None),
        )
        .order_by(Document.created_at.asc())
        .all()
    )

    if not docs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo sem documentos para extrair.",
        )

    jobs: list[ProcessExtractJob] = []
    pending_ocr: list[ProcessExtractJob] = []

    from app.workers.agent_tasks import run_agent  # noqa: PLC0415
    from app.workers.ocr_tasks import ocr_then_extract  # noqa: PLC0415

    for doc in docs:
        has_text = bool((doc.extracted_text or "").strip())
        if has_text and not body.force:
            try:
                t = run_agent.delay(
                    agent_name="extrator",
                    tenant_id=current_user.tenant_id,
                    user_id=current_user.id,
                    process_id=process.id,
                    metadata={
                        "document_id": doc.id,
                        "document_type": doc.document_type,
                    },
                )
                jobs.append(
                    ProcessExtractJob(
                        document_id=doc.id,
                        filename=doc.filename,
                        document_type=doc.document_type,
                        method="extract",
                        task_id=getattr(t, "id", None),
                    )
                )
            except Exception as exc:
                logger.warning(
                    "extract_process_documents: falha ao enfileirar extrator doc=%s: %s",
                    doc.id, exc,
                )
        else:
            try:
                t = ocr_then_extract.delay(
                    doc_id=doc.id,
                    tenant_id=current_user.tenant_id,
                    user_id=current_user.id,
                    draft_id=None,
                    force=body.force,
                )
                pending_ocr.append(
                    ProcessExtractJob(
                        document_id=doc.id,
                        filename=doc.filename,
                        document_type=doc.document_type,
                        method="ocr_then_extract",
                        task_id=getattr(t, "id", None),
                    )
                )
            except Exception as exc:
                logger.warning(
                    "extract_process_documents: falha ao enfileirar ocr_then_extract doc=%s: %s",
                    doc.id, exc,
                )

    repo.add_audit(
        user_id=current_user.id,
        process=process,
        action="extractor_dispatched",
        details=(
            f"{len(jobs)} job(s) de extrator + {len(pending_ocr)} chain(s) OCR+extrator "
            f"enfileiradas (force={body.force})"
        ),
    )
    db.commit()

    return ProcessExtractResponse(
        process_id=process.id,
        total_docs=len(docs),
        jobs=jobs,
        pending_ocr=pending_ocr,
        skipped=[],
    )


def _enrich_timeline_origin(db: Session, tenant_id: int, logs: Any) -> list[AuditLogRead]:
    """Liga cada evento de decisão de staging ao DOCUMENTO de origem do campo.

    `fix/historico-eventos-humanizado` (Item 2): o `fonte` cru do audit
    `staging_decidir` é a fonte opcional do `escolher_fonte` — quase sempre
    `null` e enganosa. A rastreabilidade real é o documento de onde o campo foi
    extraído (`ExtractedFieldStaging.document_id`). Resolvemos no read-time
    (via `field_id`) para que eventos JÁ gravados (ex.: process 13) também
    ganhem a origem, sem reescrever o histórico imutável.
    """
    import json  # noqa: PLC0415

    parsed: dict[int, dict[str, Any]] = {}
    field_ids: set[int] = set()
    for log in logs:
        if log.action == "staging_decidir" and log.details:
            try:
                data = json.loads(log.details)
            except (ValueError, TypeError):
                continue
            if isinstance(data, dict):
                parsed[log.id] = data
                fid = data.get("field_id")
                if isinstance(fid, int):
                    field_ids.add(fid)

    doc_by_field: dict[int, str] = {}
    if field_ids:
        staging_rows = (
            db.query(ExtractedFieldStaging.id, ExtractedFieldStaging.document_id)
            .filter(
                ExtractedFieldStaging.tenant_id == tenant_id,
                ExtractedFieldStaging.id.in_(field_ids),
            )
            .all()
        )
        doc_ids = {did for _fid, did in staging_rows if did is not None}
        name_by_doc: dict[int, str] = {}
        if doc_ids:
            for did, name in (
                db.query(Document.id, Document.original_file_name)
                .filter(Document.tenant_id == tenant_id, Document.id.in_(doc_ids))
                .all()
            ):
                name_by_doc[did] = name
        for fid, did in staging_rows:
            if did is not None and did in name_by_doc:
                doc_by_field[fid] = name_by_doc[did]

    out: list[AuditLogRead] = []
    for log in logs:
        item = AuditLogRead.model_validate(log)
        data = parsed.get(log.id)
        if data is not None:
            fid = data.get("field_id")
            if isinstance(fid, int) and fid in doc_by_field:
                item.origin_document = doc_by_field[fid]
        out.append(item)
    return out


@router.get("/{process_id}/timeline", response_model=list[AuditLogRead])
def get_process_timeline(
    process_id: int,
    db: Session = Depends(get_db),
    access_context: AccessContext = Depends(get_access_context),
) -> Any:
    """Retorna a linha do tempo (timeline) de eventos e logs de auditoria do processo."""
    repo = ProcessRepository(db, access_context.tenant_id)
    repo.get_scoped_or_404(process_id, client_id=access_context.client_id)
    logs = repo.get_timeline(process_id)
    return _enrich_timeline_origin(db, access_context.tenant_id, logs)


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
    # Fase 0.2 — backfill lazy de checklists para casos legados (idempotente).
    if ensure_macroetapa_checklists(db, process, current_user.tenant_id):
        db.commit()
    return get_macroetapa_status(db, process)


def _compute_can_advance(
    db: Session,
    process: ProcessModel,
    *,
    require_complete: bool = True,
) -> CanAdvanceResponse:
    """Helper interno: avalia se um processo pode avançar de etapa."""
    from app.models.checklist_template import ProcessChecklist  # noqa: PLC0415

    # Fase 0.2 — backfill lazy de checklists para casos legados (idempotente).
    if ensure_macroetapa_checklists(db, process, process.tenant_id):
        db.commit()

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
    # Terceira cópia do mesmo laço (a auditoria mapeou duas) — a mais crítica
    # das três: esta alimenta o gate que TRAVA o avanço da macroetapa. Um
    # requisito falso-pendente aqui bloqueava o caso com o documento na base.
    missing_docs = contar_pendentes_checklist(
        db, process.id, process.tenant_id, pc.items if pc else None
    )

    # fix/diagnostico-propaga-estado: gate de saída de etapa de diagnóstico
    # exige assinatura humana do RegulatoryDiagnosis. Consulta única por
    # processo — não é caminho de listagem, só do detalhe.
    from app.models.regulatory import RegulatoryDiagnosis  # noqa: PLC0415

    diagnosis_validated = bool(
        db.query(RegulatoryDiagnosis.id)
        .filter(
            RegulatoryDiagnosis.tenant_id == process.tenant_id,
            RegulatoryDiagnosis.process_id == process.id,
            RegulatoryDiagnosis.validated_at.isnot(None),
        )
        .first()
    )

    # Fase 0 (gap-analysis Ficha 07, item 2) — só é relevante saindo da E2;
    # calcular sempre é barato (1 query indexada) e mantém o sinal correto
    # se `current_etapa` mudar de valor mais adiante.
    consolidacao_executada = has_consolidated(db, process.tenant_id, process.id)
    # Fase 0 (item 9 do adendo) — mesma lógica pra E5/E6/E7; barato calcular
    # sempre (1 query indexada cada), independe da etapa atual.
    rota_validada = has_rota_validada(db, process.tenant_id, process.id)
    proposta_aceita = has_proposal_accepted(db, process.tenant_id, process.id)
    contract_signed = has_contract_signed(db, process.tenant_id, process.id)

    can, blockers = can_advance_macroetapa(
        cl,
        documents_pending_required=missing_docs,
        require_complete=require_complete,
        current_macroetapa=current_etapa,
        diagnosis_validated=diagnosis_validated,
        consolidacao_executada=consolidacao_executada,
        rota_validada=rota_validada,
        proposta_aceita=proposta_aceita,
    )

    state_value = None
    if cl:
        state_value = compute_macroetapa_state(
            cl,
            is_current=True,
            has_blockers=bool(blockers),
            current_macroetapa=current_etapa,
            diagnosis_validated=diagnosis_validated,
            contract_signed=contract_signed,
        ).value

    # Sprint 1 (Ficha 07) — DESTINO recomendado do avanço. Na saída da E2 o ramo
    # depende de haver documento essencial pendente (`missing_docs`): se há, vai
    # para a coleta (E3); senão pula para o diagnóstico técnico (E4). Demais
    # etapas seguem o sucessor linear.
    next_macro = resolve_next_macroetapa(
        current_etapa, has_essential_pending=missing_docs > 0
    )
    next_etapa = next_macro.value if next_macro else None

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
            mats_count = len(prop.matriculas or [])
            if not prop.registry_number and mats_count == 0:
                gaps.append("Matrícula do imóvel não preenchida")
            if not prop.car_code:
                gaps.append("Código CAR do imóvel não preenchido")
            # Sprint 4: soma derivada das matrículas conta como área conhecida
            # (antes: falso positivo pós-consolidação, que nunca grava total_area_ha).
            area_derivada = prop.area_total_matriculas() if mats_count else 0.0
            if not prop.total_area_ha and not area_derivada:
                gaps.append("Área total do imóvel não informada")
            # Sprint 4 (Ficha 07 §9) — informativa, nunca trava.
            if mats_count > 1 and prop.matriculas_contiguas is None:
                gaps.append("Contiguidade das matrículas não declarada (>1 matrícula)")
            if not prop.biome:
                gaps.append("Bioma do imóvel não identificado")
    if not process.initial_summary:
        gaps.append("Resumo inicial da demanda (voz do cliente) não registrado")

    # Guard-rail (item 1 da validação 20/07): liberdade com consciência.
    # Se a etapa TEM chain de agentes e ela não rodou, o avanço não é
    # bloqueado — mas o consultor é avisado em texto claro antes de confirmar.
    agentes_ok = True
    avisos: list[str] = []
    if current_etapa is not None and MACROETAPA_AGENT_CHAIN.get(current_etapa):
        agentes_ok = stage_agents_executados(cl)
        if not agentes_ok:
            avisos.append(
                "Os agentes desta etapa não foram executados — o caso avançará "
                "sem diagnóstico automático."
            )

    return CanAdvanceResponse(
        can_advance=can,
        current_macroetapa=current_etapa.value if current_etapa else None,
        current_state=state_value,
        next_macroetapa=next_etapa,
        blockers=blockers,
        gaps=gaps,
        objective=meta.get("objective"),
        expected_outputs=meta.get("expected_outputs", []),
        agentes_executados=agentes_ok,
        avisos=avisos,
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

    # Guard-rail (item 1 da validação 20/07): a confirmação registra O QUE
    # estava pendente no momento do avanço. Liberdade com consciência assinada —
    # daqui a três meses a auditoria responde "o consultor sabia?" com sim e a
    # lista exata do que ele viu na tela.
    ressalvas: list[str] = []
    if not gate.agentes_executados:
        ressalvas.append("agentes da etapa não executados")
    if gate.gaps:
        ressalvas.append(f"{len(gate.gaps)} lacuna(s): " + "; ".join(gate.gaps))
    detalhe = f"Macroetapa avançada para {body.macroetapa.value}"
    if ressalvas:
        detalhe += " — avanço confirmado com ressalvas: " + " | ".join(ressalvas)

    repo.add_audit(
        user_id=current_user.id,
        process=process,
        action="macroetapa_changed",
        details=detalhe,
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

    # Fase 0.2 — de-inversão (ADR-017): avançar o card NÃO dispara mais a chain.
    # Rodar os agentes é uma ação própria do consultor (POST .../macroetapa/run-agents),
    # anterior e separada do avanço. Avançar só move o card (gate já validado acima).
    return process


@router.post("/{process_id}/macroetapa/run-agents", response_model=RunStageAgentsResponse)
def run_stage_agents(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Fase 0.2 — "Rodar os agentes da etapa" (Ficha 07 §2/§6).

    Dispara, async, a chain de agentes da macroetapa ATUAL do processo
    (`MACROETAPA_AGENT_CHAIN`). Ao concluir com sucesso, o worker marca o
    checklist da etapa (`mark_stage_agents_done`) e o card fica
    `pronta_para_avancar` — o avanço efetivo só ocorre quando o consultor
    confirma em "Avançar etapa". Etapas sem chain (coleta/contrato) são manuais.
    """
    repo = ProcessRepository(db, current_user.tenant_id)
    process = repo.get_or_404(process_id, detail="Processo não encontrado")

    current = Macroetapa(process.macroetapa) if process.macroetapa else None
    if current is None:
        raise HTTPException(status_code=409, detail="Processo sem macroetapa definida.")

    chain_name = MACROETAPA_AGENT_CHAIN.get(current)
    if not chain_name:
        return RunStageAgentsResponse(
            dispatched=False,
            macroetapa=current.value,
            chain_name=None,
            detail="Esta etapa não tem agentes automáticos — é conduzida manualmente.",
        )

    # Contexto real do processo pra chain (forense caso Isis): a chain 'intake'
    # (atendimento) exige uma descrição da demanda; passar só {macroetapa} fazia
    # o agente FALHAR silenciosamente ("Campo 'description' obrigatorio") e o
    # consultor via "não gerou resultado". Deriva a descrição do que houver.
    descricao = (
        (process.description or "").strip()
        or (getattr(process, "initial_summary", "") or "").strip()
        or (getattr(process, "intake_notes", "") or "").strip()
        or (process.title or "").strip()
    )
    # Guard honesto: sem descrição, a classificação não roda — explica na tela em
    # vez de disparar pra falha invisível (nunca silêncio).
    if chain_name == "intake" and not descricao:
        return RunStageAgentsResponse(
            dispatched=False,
            macroetapa=current.value,
            chain_name=chain_name,
            detail=(
                "Esta etapa classifica a demanda a partir da descrição do caso, "
                "que ainda está vazia. Preencha a descrição/resumo do caso e rode "
                "os agentes novamente."
            ),
        )

    metadata: dict[str, Any] = {"macroetapa": current.value}
    if descricao:
        metadata["description"] = descricao
    if process.process_type:
        metadata["process_type"] = process.process_type
    if process.urgency:
        metadata["urgency"] = process.urgency

    try:
        from app.workers.agent_tasks import run_agent_chain  # noqa: PLC0415
        run_agent_chain.delay(
            chain_name=chain_name,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            process_id=process_id,
            metadata=metadata,
            stop_on_review=True,
        )
    except Exception as exc:
        logger.warning("Falha ao enfileirar chain '%s': %s", chain_name, exc)
        raise HTTPException(status_code=503, detail="Não foi possível enfileirar os agentes da etapa.")

    repo.add_audit(
        user_id=current_user.id,
        process=process,
        action="stage_agents_dispatched",
        details=f"Agentes da etapa '{current.value}' disparados (chain '{chain_name}')",
        new_value=chain_name,
    )
    db.commit()
    logger.info("Chain '%s' enfileirada para process_id=%s (run-agents, macroetapa=%s)",
                chain_name, process_id, current.value)
    return RunStageAgentsResponse(
        dispatched=True, macroetapa=current.value, chain_name=chain_name,
        detail="Agentes da etapa disparados. Acompanhe na aba IA; ao concluir, a etapa fica pronta para avançar.",
    )


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

    checklist = toggle_action(
        db, checklist, body.action_id, body.completed, user_id=current_user.id
    )
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
    from datetime import UTC, datetime  # noqa: PLC0415

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


@router.get("/{process_id}/artifacts/{artifact_id}/download")
def download_process_artifact(
    process_id: int,
    artifact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """S5-C — URL de download do PDF de um artefato/Saída.

    Os geradores de proposta/minuta (S5-B) gravam o `pdf_storage_key` em
    `StageOutput.content_data`; este endpoint devolve a URL pré-assinada,
    fazendo a aba Saídas convergir (proposta/contrato baixáveis num só lugar)."""
    from app.models.stage_output import StageOutput  # noqa: PLC0415
    from app.services.storage import get_storage_service  # noqa: PLC0415

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
        raise HTTPException(status_code=404, detail="Artefato não encontrado.")
    key = (artifact.content_data or {}).get("pdf_storage_key")
    if not key:
        raise HTTPException(status_code=404, detail="Este artefato não tem PDF armazenado.")
    try:
        url = get_storage_service().generate_presigned_get_url(key, expires_in=3600)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Erro ao gerar URL: {exc}") from exc
    return {"download_url": url, "expires_in": 3600}


# ---------------------------------------------------------------------------
# Staging de campos extraídos (Ficha 01, FASE 1) — leitura
# ---------------------------------------------------------------------------

@router.get("/{process_id}/staging-fields", response_model=list[ExtractedFieldStagingOut])
def list_process_staging_fields(
    process_id: int,
    status: Optional[ExtractedFieldStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
):
    """Lista os campos extraídos em staging de um processo (tenant-scoped).

    Ficha 01: agentes propõem (staging), consultor decide (Alertas, fase 4). Nesta
    fase nada escreve no staging ainda; o endpoint já existe para a UI consumir.
    Filtro opcional por ``status``.
    """
    from app.services.staging_consolidation import flag_sem_casa  # noqa: PLC0415

    ProcessRepository(db, current_user.tenant_id).get_or_404(
        process_id, detail="Processo não encontrado."
    )
    rows = ExtractedFieldStagingRepository(db, current_user.tenant_id).list_by_process(
        process_id, status=status
    )
    # Item 6 — "aceite sem casa" durável: o mesmo julgamento da consolidação vira
    # um flag por linha, a cada leitura, para a pendência nunca sumir calada.
    _proc, prop = _load_process_property(db, current_user.tenant_id, process_id)
    motivos = flag_sem_casa(db, current_user.tenant_id, process_id, prop)
    # Nome do documento de origem por linha (26/07) — uma query, não N+1. Sem ele
    # a Conferência agrupa linhas de documentos diferentes no mesmo quadro anônimo.
    doc_ids = {r.document_id for r in rows if r.document_id}
    nomes: dict[int, str] = {}
    if doc_ids:
        nomes = {
            doc_id: (original or filename or f"documento #{doc_id}")
            for doc_id, filename, original in db.query(
                Document.id, Document.filename, Document.original_file_name
            ).filter(
                Document.tenant_id == current_user.tenant_id,
                Document.id.in_(doc_ids),
            )
        }
    for r in rows:
        r.sem_casa = r.id in motivos
        r.sem_casa_motivo = motivos.get(r.id)
        r.source_doc_nome = nomes.get(r.document_id) if r.document_id else None
    return rows


# ---------------------------------------------------------------------------
# FASE 4 — decisão do consultor + consolidação na base real
# ---------------------------------------------------------------------------

@router.post(
    "/{process_id}/staging-fields/aceitar-consistentes",
    response_model=BulkAcceptResult,
)
def accept_consistent_staging_fields(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
):
    """Aceita em lote TODOS os campos status=consistente do processo.

    Divergentes NUNCA entram no lote — exigem escolha ativa (gate em /decidir)."""
    from app.services.staging_consolidation import bulk_accept_consistentes  # noqa: PLC0415

    ProcessRepository(db, current_user.tenant_id).get_or_404(
        process_id, detail="Processo não encontrado."
    )
    ids = bulk_accept_consistentes(
        db, tenant_id=current_user.tenant_id, process_id=process_id, user_id=current_user.id
    )
    return BulkAcceptResult(aceitos=len(ids), field_ids=ids)


@router.post(
    "/{process_id}/staging-fields/{field_id}/decidir",
    response_model=StagingDecisionResult,
)
def decide_staging_field(
    process_id: int,
    field_id: int,
    body: StagingDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
):
    """Decisão do consultor sobre um campo (aceitar/escolher_fonte/editar/rejeitar)."""
    from app.services.staging_consolidation import decide_field  # noqa: PLC0415

    ProcessRepository(db, current_user.tenant_id).get_or_404(
        process_id, detail="Processo não encontrado."
    )
    row = decide_field(
        db, tenant_id=current_user.tenant_id, process_id=process_id, field_id=field_id,
        acao=body.acao, valor=body.valor, fonte=body.fonte, user_id=current_user.id,
    )
    decided = row.decided_value.get("value") if isinstance(row.decided_value, dict) else None
    return StagingDecisionResult(field_id=row.id, status=row.status, decided_value=decided)


@router.get("/{process_id}/confronto-identidade")
def get_confronto_identidade(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Números de matrícula concorrentes no caso — a decisão mais cara do domínio.

    No caso 15 o CCIR declarava 2923 e a certidão 4698, e a Conferência nunca
    colocou os dois lado a lado. O consultor escolheu sem saber que estava
    escolhendo a identidade jurídica do imóvel.

    A frase da regra vem do BACKEND (padrão do guard-rail): a tela não
    reimplementa a hierarquia da Ficha 08 §5.1.
    """
    from app.services.confronto_identidade import detectar_confrontos  # noqa: PLC0415

    ProcessRepository(db, current_user.tenant_id).get_or_404(
        process_id, detail="Processo não encontrado"
    )
    confrontos = detectar_confrontos(
        db, tenant_id=current_user.tenant_id, process_id=process_id
    )

    def _serialize(c: Any) -> dict[str, Any]:
        return {
            "regra": c.regra,
            "prevalente": (
                {"numero": c.prevalente.numero, "fonte": c.prevalente.rotulo_fonte}
                if c.prevalente else None
            ),
            "fontes": [
                {
                    "numero": f.numero, "document_id": f.document_id,
                    "fonte": f.rotulo_fonte, "status": f.status,
                    "staging_id": f.staging_id,
                }
                for f in c.fontes
            ],
            "cadeia_proposta": c.cadeia_proposta,
        }

    lista = [_serialize(c) for c in confrontos]
    primeiro = lista[0] if lista else {
        "regra": "", "prevalente": None, "fontes": [], "cadeia_proposta": None,
    }
    # `confrontos` é a forma nova (um por lote); os campos de topo espelham o
    # primeiro para compat com clientes antigos.
    return {
        "ha_confronto": bool(confrontos),
        "confrontos": lista,
        **primeiro,
    }


@router.get("/{process_id}/matriculas-rotulos")
def matriculas_rotulos(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> dict[str, str]:
    """Rótulo de linhagem por número de matrícula histórica (item 4, 21/07).

    Solução barata para a confusão da Isis ("17 itens do CCIR, nenhum na aba da
    4698"): os itens do CCIR ficam sob a matrícula 2923 (o hint do documento),
    não sob a 4698. Em vez de re-homar hints (reescrever a resolução de
    identidade), só ROTULAMOS o grupo quando a cadeia já existe — "Matrícula 2923
    — ficha anterior da 4698". Devolve ``{numero_matricula: rótulo}`` só para as
    históricas encadeadas; sem cadeia → vazio (rótulo some)."""
    from app.services.inconsistency_matrix import _clean_matricula_hint  # noqa: PLC0415

    _proc, prop = _load_process_property(db, current_user.tenant_id, process_id)
    if prop is None:
        return {}
    por_id = {m.id: m for m in prop.matriculas_ativas()}
    out: dict[str, str] = {}
    for m in prop.matriculas_historicas():
        vig = por_id.get(m.superseded_by_id) if m.superseded_by_id else None
        chave = _clean_matricula_hint(m.numero_matricula)
        if vig is not None and vig.numero_matricula and chave:
            out[chave] = f"ficha anterior da {vig.numero_matricula}"
    return out


@router.get("/{process_id}/vinculo-candidatos/{document_id}")
def listar_candidatos_vinculo(
    process_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Degrau 4 da cascata (spec da Isis) — a quem este documento pode pertencer.

    Roda a cascata e devolve o que ela concluiu: vínculo automático (NIRF ou
    INCRA único), ou a lista de candidatos para o consultor escolher. Nunca
    decide sozinho fora dos degraus 1 e 2.
    """
    from app.models.document import Document  # noqa: PLC0415
    from app.services.consolidacao_lineage import vincular_itr  # noqa: PLC0415

    repo = ProcessRepository(db, current_user.tenant_id)
    process = repo.get_or_404(process_id, detail="Processo não encontrado")
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.tenant_id == current_user.tenant_id)
        .first()
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    if not process.property_id:
        return {"autolink": False, "nivel": 0, "candidatas": [],
                "motivo": "o processo ainda não tem imóvel vinculado"}

    linhas = (
        db.query(ExtractedFieldStaging)
        .filter(
            ExtractedFieldStaging.tenant_id == current_user.tenant_id,
            ExtractedFieldStaging.process_id == process_id,
            ExtractedFieldStaging.document_id == document_id,
        )
        .all()
    )
    por_campo = {linha.field_name: linha.field_value for linha in linhas}
    incras = [
        v for k, v in por_campo.items()
        if k in ("codigo_incra", "codigo_sncr_incra")
    ]
    r = vincular_itr(
        db, tenant_id=current_user.tenant_id, property_id=process.property_id,
        nirf=por_campo.get("nirf_cib"), codigos_incra=incras,
    )
    return {
        "autolink": r.autolink,
        "nivel": r.nivel,
        "sinal": r.sinal,
        "motivo": r.motivo,
        "matricula_id": r.matricula.id if r.matricula else None,
        "candidatas": r.candidatas,
    }


@router.post("/{process_id}/vinculo-manual/{document_id}")
def vincular_documento_manual(
    process_id: int,
    document_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Degrau 4 — o consultor escolhe a matrícula; a escolha vira proveniência."""
    from app.services.consolidacao_lineage import (  # noqa: PLC0415
        vincular_manualmente,
    )

    ProcessRepository(db, current_user.tenant_id).get_or_404(
        process_id, detail="Processo não encontrado"
    )
    matricula_id = body.get("matricula_id")
    if not matricula_id:
        raise HTTPException(status_code=422, detail="'matricula_id' é obrigatório")
    try:
        n = vincular_manualmente(
            db, tenant_id=current_user.tenant_id, process_id=process_id,
            document_id=document_id, matricula_id=int(matricula_id),
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return {"linhas_ancoradas": n, "matricula_id": int(matricula_id)}


@router.post("/{process_id}/consolidar", response_model=ConsolidationResult)
def consolidate_process_endpoint(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
):
    """Consolida o staging aceito na base real (Client/Property/Matricula).

    Determinístico, idempotente. NÃO grava nada que não esteja aceito; NÃO
    sobrescreve Property.total_area_ha (área = derivada da soma das matrículas)."""
    from app.services.staging_consolidation import (  # noqa: PLC0415
        consolidate_process,
        registrar_falha_consolidacao,
    )

    ProcessRepository(db, current_user.tenant_id).get_or_404(
        process_id, detail="Processo não encontrado."
    )
    try:
        result = consolidate_process(
            db, tenant_id=current_user.tenant_id, process_id=process_id, user_id=current_user.id
        )
    except HTTPException:
        raise
    except Exception as exc:
        # Nenhum clique morre calado (validação 30/07): o `_audit` de sucesso mora
        # dentro da transação que o erro desfaz, então uma consolidação que quebra
        # não deixava NADA — nem auditoria, nem mensagem com causa. Aqui a falha
        # vira linha permanente (transação própria), log com stack, e uma frase
        # que diz ao consultor o que aconteceu e o que fazer.
        logger.exception("consolidar: falhou para process_id=%s", process_id)
        registrar_falha_consolidacao(
            db, tenant_id=current_user.tenant_id, process_id=process_id,
            user_id=current_user.id, exc=exc,
        )
        raise HTTPException(
            status_code=500,
            detail=(
                "A gravação na base falhou e NADA foi gravado — suas decisões na "
                "Conferência continuam salvas. A falha ficou registrada na "
                f"auditoria deste caso ({type(exc).__name__}). Tente de novo; se "
                "repetir, avise o suporte com o número do caso."
            ),
        ) from exc
    return ConsolidationResult(**result)


# ---------------------------------------------------------------------------
# Dívida #60 — cadeia de fichas / vigência (proposta na Conferência + 1 clique)
# ---------------------------------------------------------------------------

def _load_process_property(db: Session, tenant_id: int, process_id: int):
    """Processo (tenant-scoped) + seu imóvel — base das propostas de cadeia."""
    from app.models.property import Property  # noqa: PLC0415

    process = ProcessRepository(db, tenant_id).get_or_404(
        process_id, detail="Processo não encontrado."
    )
    prop = None
    if process.property_id:
        prop = (
            db.query(Property)
            .filter(Property.id == process.property_id, Property.tenant_id == tenant_id)
            .first()
        )
    return process, prop


@router.get("/{process_id}/chain-proposals", response_model=list[ChainProposalOut])
def list_chain_proposals(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
):
    """Propõe cadeias entre as matrículas VIGENTES do imóvel do processo (#60).

    A Conferência exibe pré-marcadas; nada muda sem o clique do consultor
    (IA propõe, humano decide). Sem imóvel/sem cadeia → lista vazia."""
    from app.services.matricula_chain import detect_chain_proposals  # noqa: PLC0415

    _process, prop = _load_process_property(db, current_user.tenant_id, process_id)
    if prop is None:
        return []
    return [ChainProposalOut(**p.__dict__) for p in detect_chain_proposals(prop)]


@router.get("/{process_id}/matriculas-vigentes", response_model=list[MatriculaVigenteMini])
def list_matriculas_vigentes(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
):
    """Matrículas VIGENTES do imóvel do processo — alimenta o seletor manual de
    cadeia na Conferência (#60).

    Existe porque `detect_chain_proposals` é deterministicamente conservador:
    quando os sinais não disparam (sem `registro_anterior`/`denominacao_anterior`,
    tokens de lote divergentes — caso 15: "Lote 1 B" vs "Gleba 01 B"), não há
    proposta para clicar. Estas alimentam a declaração manual (humano decide,
    Princípio 1). Sem imóvel → lista vazia."""
    _process, prop = _load_process_property(db, current_user.tenant_id, process_id)
    if prop is None:
        return []
    return [MatriculaVigenteMini.model_validate(m) for m in prop.matriculas_vigentes()]


@router.post("/{process_id}/chain-proposals/aplicar", response_model=ChainApplyResult)
def apply_chain_proposals(
    process_id: int,
    body: ChainApplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
):
    """1 clique confirma a cadeia: cada anterior vira histórica, encadeada à
    vigente (#60). Substitui N rejeições campo-a-campo. Auditado, reversível."""
    from app.services.matricula_chain import apply_chain  # noqa: PLC0415

    _process, prop = _load_process_property(db, current_user.tenant_id, process_id)
    if prop is None:
        return ChainApplyResult(aplicadas=[], count=0)
    result = apply_chain(
        db, tenant_id=current_user.tenant_id, property_id=prop.id,
        pairs=[(p.anterior_id, p.vigente_id) for p in body.pairs],
        user_id=current_user.id,
    )
    return ChainApplyResult(**result)
