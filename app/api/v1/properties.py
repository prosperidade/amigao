from datetime import datetime, timedelta, UTC
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api import deps
from app.models.audit_log import AuditLog
from app.models.client import Client as ClientModel
from app.models.document import Document
from app.models.macroetapa import (
    MACROETAPA_LABELS,
    Macroetapa,
    MacroetapaChecklist,
    compute_macroetapa_state,
    list_macroetapa_blockers,
)
from app.models.process import Process as ProcessModel, ProcessStatus
from app.models.property import Property as PropertyModel
from app.models.stage_output import StageOutput
from app.models.user import User
from app.repositories import PropertyRepository
from app.schemas.property import Property, PropertyCreate, PropertyUpdate
from app.schemas.property_hub import (
    PropertyAISummary,
    PropertyFieldValidateRequest,
    PropertyHealthScore,
    PropertyHubCase,
    PropertyHubChips,
    PropertyHubEvent,
    PropertyHubHeader,
    PropertyHubSummary,
    PropertyHubTechnicalKpis,
)

router = APIRouter()

# Importante: o ProcessStatus é Enum de strings, essa lista ajuda em queries
_ACTIVE_PROCESS_STATUSES = [
    s for s in ProcessStatus
    if s not in (ProcessStatus.cancelado, ProcessStatus.arquivado, ProcessStatus.concluido)
]


@router.post("/", response_model=Property)
def create_property(
    *,
    db: Session = Depends(deps.get_db),
    property_in: PropertyCreate,
    current_user: User = Depends(deps.get_current_internal_user),
):
    repo = PropertyRepository(db, current_user.tenant_id)
    db_obj = repo.create(property_in.model_dump())
    db.commit()
    db.refresh(db_obj)
    return db_obj


@router.get("/", response_model=list[Property])
def get_properties(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    client_id: Optional[int] = None,
    current_user: User = Depends(deps.get_current_internal_user),
):
    repo = PropertyRepository(db, current_user.tenant_id)
    if client_id:
        return repo.list_by_client(client_id, skip=skip, limit=limit)
    return repo.list(skip=skip, limit=limit)


@router.get("/{id}", response_model=Property)
def get_property(
    id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_internal_user),
):
    repo = PropertyRepository(db, current_user.tenant_id)
    return repo.get_or_404(id, detail="Property not found")


@router.patch("/{id}", response_model=Property)
def update_property(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    property_in: PropertyUpdate,
    current_user: User = Depends(deps.get_current_internal_user),
):
    repo = PropertyRepository(db, current_user.tenant_id)
    property_obj = repo.update(id, property_in.model_dump(exclude_unset=True), detail="Property not found")
    db.commit()
    db.refresh(property_obj)
    return property_obj


# ---------------------------------------------------------------------------
# IMÓVEL HUB (Regente Cam2 — CAM2IH)
# ---------------------------------------------------------------------------

def _get_property_or_404(db: Session, tenant_id: int, prop_id: int) -> PropertyModel:
    p = (
        db.query(PropertyModel)
        .filter(PropertyModel.id == prop_id, PropertyModel.tenant_id == tenant_id)
        .first()
    )
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imóvel não encontrado")
    return p


def _compute_health_score(
    *,
    prop: PropertyModel,
    docs_count: int,
    analyses_count: int,
    pending_critical: int,
    has_car: bool,
    car_status: Optional[str],
    cases_active: int,
) -> PropertyHealthScore:
    """CAM2IH-006 — Score de maturidade 0-100 + componentes.

    Heurística: combina completude documental, análises, situação regulatória,
    consistência e confiança da base. Pondera por pendências críticas.
    """
    # Completude documental — 100 se >= 5 docs, escala linear
    documental_completeness = min(100, docs_count * 20)
    if pending_critical > 0:
        documental_completeness = max(0, documental_completeness - pending_critical * 15)

    # Atualização regulatória — depende de CAR
    if not has_car:
        regulatory_update = 10
    elif car_status in (None, "pendente", "cancelado"):
        regulatory_update = 40
    elif car_status == "analise":
        regulatory_update = 60
    else:  # ativo/regular
        regulatory_update = 90

    # Profundidade de análises
    analysis_depth = min(100, analyses_count * 25)

    # Consistência cadastral — penaliza campos faltando principais
    consistency = 100
    missing_main = [
        getattr(prop, f, None) is None or getattr(prop, f, None) == ""
        for f in ("registry_number", "total_area_ha", "municipality", "state")
    ]
    consistency -= sum(missing_main) * 15

    # Confiança da base — combinação ponderada
    confidence_base = int(
        0.35 * documental_completeness
        + 0.25 * regulatory_update
        + 0.20 * analysis_depth
        + 0.20 * consistency
    )
    overall = confidence_base  # neste MVP overall = confidence base

    if pending_critical > 0:
        label = "ruim" if pending_critical >= 3 else "media"
    elif overall >= 75:
        label = "consolidada"
    elif overall >= 50:
        label = "boa"
    elif overall >= 25:
        label = "media"
    else:
        label = "ruim"

    return PropertyHealthScore(
        overall=max(0, min(100, overall)),
        documental_completeness=max(0, min(100, documental_completeness)),
        regulatory_update=max(0, min(100, regulatory_update)),
        analysis_depth=max(0, min(100, analysis_depth)),
        consistency=max(0, min(100, consistency)),
        confidence_base=max(0, min(100, confidence_base)),
        pending_critical=pending_critical,
        label=label,
    )


def _compute_property_hub_state(
    *, docs_count: int, analyses_count: int, age_days: int, has_alerts: bool, cases_count: int
) -> str:
    """CAM2IH-008 — 5 estados do hub."""
    if has_alerts:
        return "com_alertas"
    if docs_count >= 5 and analyses_count >= 2:
        return "consolidado"
    if docs_count >= 2 or cases_count >= 1:
        return "memoria_estruturada"
    if age_days < 7 and docs_count <= 1:
        return "recem_criado"
    return "em_construcao"


@router.get("/{property_id}/summary", response_model=PropertyHubSummary)
def get_property_hub_summary(
    property_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_internal_user),
) -> Any:
    """CAM2IH-002+003+006+008 — Cabeçalho + KPIs + health score + estado."""
    from app.models.checklist_template import ProcessChecklist  # noqa: PLC0415

    prop = _get_property_or_404(db, current_user.tenant_id, property_id)
    tenant_id = current_user.tenant_id

    client = db.query(ClientModel).filter(ClientModel.id == prop.client_id).first()

    # Casos do imóvel
    procs = (
        db.query(ProcessModel)
        .filter(
            ProcessModel.property_id == property_id,
            ProcessModel.tenant_id == tenant_id,
            ProcessModel.deleted_at.is_(None),
        )
        .all()
    )
    proc_ids = [p.id for p in procs]
    cases_active = sum(
        1 for p in procs
        if p.status not in (ProcessStatus.cancelado, ProcessStatus.arquivado, ProcessStatus.concluido)
    )

    # Documentos do imóvel (ligados via property_id OU via processos)
    docs_q = db.query(Document).filter(
        Document.tenant_id == tenant_id,
        Document.deleted_at.is_(None),
    )
    if proc_ids:
        from sqlalchemy import or_  # noqa: PLC0415
        docs_q = docs_q.filter(or_(Document.property_id == property_id, Document.process_id.in_(proc_ids)))
    else:
        docs_q = docs_q.filter(Document.property_id == property_id)
    docs = docs_q.all()
    docs_count = len(docs)
    last_document_at = max((d.created_at for d in docs), default=None)

    # Análises = StageOutputs do tipo análise vinculadas aos casos do imóvel
    analyses_count = 0
    last_analysis_at = None
    if proc_ids:
        analyses = (
            db.query(StageOutput)
            .filter(
                StageOutput.process_id.in_(proc_ids),
                StageOutput.tenant_id == tenant_id,
            )
            .all()
        )
        analyses_count = len(analyses)
        last_analysis_at = max((a.created_at for a in analyses), default=None)

    # Pendências críticas (docs obrigatórios pendentes)
    pending_critical = 0
    if proc_ids:
        for pc in db.query(ProcessChecklist).filter(ProcessChecklist.process_id.in_(proc_ids)).all():
            for item in pc.items or []:
                if item.get("required") and item.get("status") == "pending":
                    pending_critical += 1

    last_activity_at = None
    if procs:
        last_activity_at = max((p.updated_at or p.created_at for p in procs), default=None)

    kpis = PropertyHubTechnicalKpis(
        cases_count=len(procs),
        cases_active=cases_active,
        documents_count=docs_count,
        analyses_count=analyses_count,
        last_document_at=last_document_at,
        last_analysis_at=last_analysis_at,
        last_activity_at=last_activity_at,
        pending_critical=pending_critical,
    )

    chips = PropertyHubChips(
        has_car=bool(prop.car_code),
        car_pending=prop.car_status in (None, "", "pendente") and bool(prop.car_code),
        has_embargo=bool(prop.has_embargo),
        has_active_cases=cases_active > 0,
        has_doc_pending=pending_critical > 0,
    )

    health = _compute_health_score(
        prop=prop,
        docs_count=docs_count,
        analyses_count=analyses_count,
        pending_critical=pending_critical,
        has_car=bool(prop.car_code),
        car_status=prop.car_status,
        cases_active=cases_active,
    )

    age_days = (datetime.now(UTC) - prop.created_at).days if prop.created_at else 0
    state = _compute_property_hub_state(
        docs_count=docs_count,
        analyses_count=analyses_count,
        age_days=age_days,
        has_alerts=pending_critical > 0 or bool(prop.has_embargo),
        cases_count=len(procs),
    )

    header = PropertyHubHeader(
        id=prop.id,
        name=prop.name,
        client_id=prop.client_id,
        client_name=client.full_name if client else None,
        registry_number=prop.registry_number,
        ccir=prop.ccir,
        nirf=prop.nirf,
        car_code=prop.car_code,
        car_status=prop.car_status,
        total_area_ha=prop.total_area_ha,
        municipality=prop.municipality,
        state=prop.state,
        biome=prop.biome,
        has_embargo=bool(prop.has_embargo),
        created_at=prop.created_at,
        field_sources=prop.field_sources or {},
        # CAM2IH-003/004 (Sprint H) — campos técnicos
        rl_status=prop.rl_status,
        app_area_ha=prop.app_area_ha,
        regulatory_issues=prop.regulatory_issues or [],
        area_documental_ha=prop.area_documental_ha,
        area_grafica_ha=prop.area_grafica_ha,
        tipologia=prop.tipologia,
        strategic_notes=prop.strategic_notes,
    )

    return PropertyHubSummary(header=header, chips=chips, kpis=kpis, health=health, state=state)


@router.get("/{property_id}/cases", response_model=list[PropertyHubCase])
def get_property_cases(
    property_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_internal_user),
) -> Any:
    """CAM2IH-004 — Aba Casos: lista de processos do imóvel com estado."""
    _get_property_or_404(db, current_user.tenant_id, property_id)
    tenant_id = current_user.tenant_id

    procs = (
        db.query(ProcessModel)
        .filter(
            ProcessModel.property_id == property_id,
            ProcessModel.tenant_id == tenant_id,
            ProcessModel.deleted_at.is_(None),
        )
        .order_by(ProcessModel.updated_at.desc().nullslast(), ProcessModel.created_at.desc())
        .all()
    )
    if not procs:
        return []

    proc_ids = [p.id for p in procs]
    cl_map: dict[tuple[int, str], MacroetapaChecklist] = {}
    for cl in db.query(MacroetapaChecklist).filter(MacroetapaChecklist.process_id.in_(proc_ids)).all():
        etapa = cl.macroetapa.value if hasattr(cl.macroetapa, "value") else cl.macroetapa
        cl_map[(cl.process_id, etapa)] = cl

    users = {
        u.id: u for u in db.query(User).filter(
            User.id.in_([p.responsible_user_id for p in procs if p.responsible_user_id])
        ).all()
    }

    out: list[PropertyHubCase] = []
    for p in procs:
        state_value = None
        next_step = None
        if p.macroetapa:
            cl = cl_map.get((p.id, p.macroetapa))
            if cl:
                blockers = list_macroetapa_blockers(cl, documents_pending_required=0)
                state_value = compute_macroetapa_state(
                    cl, is_current=True, has_blockers=bool(blockers)
                ).value
                for a in cl.actions or []:
                    if not a.get("completed"):
                        next_step = a.get("label")
                        break

        macro_label = None
        if p.macroetapa:
            try:
                macro_label = MACROETAPA_LABELS[Macroetapa(p.macroetapa)]
            except ValueError:
                macro_label = p.macroetapa

        responsible = users.get(p.responsible_user_id) if p.responsible_user_id else None

        out.append(PropertyHubCase(
            id=p.id,
            title=p.title,
            demand_type=p.demand_type.value if p.demand_type else None,
            urgency=p.urgency,
            macroetapa=p.macroetapa,
            macroetapa_label=macro_label,
            state=state_value,
            next_step=next_step,
            responsible_user_name=responsible.full_name if responsible else None,
            last_activity_at=p.updated_at,
        ))
    return out


@router.get("/{property_id}/events", response_model=list[PropertyHubEvent])
def get_property_events(
    property_id: int,
    limit: int = Query(50, le=200),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_internal_user),
) -> Any:
    """CAM2IH-004 — Aba Histórico: eventos cronológicos do imóvel."""
    _get_property_or_404(db, current_user.tenant_id, property_id)
    tenant_id = current_user.tenant_id

    proc_ids = [
        pid for (pid,) in db.query(ProcessModel.id)
        .filter(
            ProcessModel.property_id == property_id,
            ProcessModel.tenant_id == tenant_id,
        )
        .all()
    ]

    from sqlalchemy import and_, or_  # noqa: PLC0415
    conds = [and_(AuditLog.entity_type == "property", AuditLog.entity_id == property_id)]
    if proc_ids:
        conds.append(and_(AuditLog.entity_type == "process", AuditLog.entity_id.in_(proc_ids)))

    logs = (
        db.query(AuditLog)
        .filter(AuditLog.tenant_id == tenant_id, or_(*conds))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )

    _LABELS = {
        "created": "Cadastro criado",
        "base_enriched": "Base complementada",
        "status_changed": "Status alterado",
        "macroetapa_changed": "Etapa avançada",
        "uploaded": "Documento inserido",
    }

    out: list[PropertyHubEvent] = []
    for log in logs:
        macro = None
        label = _LABELS.get(log.action, log.details or log.action)
        if log.action == "macroetapa_changed" and log.details:
            for etapa in Macroetapa:
                if etapa.value in (log.details or ""):
                    macro = etapa.value
                    label = f"Avançou para {MACROETAPA_LABELS[etapa]}"
                    break
        out.append(PropertyHubEvent(
            when=log.created_at,
            kind=log.action,
            label=label,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            macroetapa=macro,
            user_id=log.user_id,
        ))
    return out


@router.get("/{property_id}/ai-summary", response_model=PropertyAISummary)
def get_property_ai_summary(
    property_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_internal_user),
) -> Any:
    """CAM2IH-005 — Painel lateral de IA (determinístico MVP).

    Reaproveita dados do summary + cases para sintetizar leitura executiva
    técnica do imóvel. Sem chamada a LLM no MVP.
    """
    summary = get_property_hub_summary(property_id, db=db, current_user=current_user)
    cases = get_property_cases(property_id, db=db, current_user=current_user)

    kpis = summary.kpis
    health = summary.health
    header = summary.header

    # Inconsistência principal — simplificação: CAR faltando, embargo, áreas faltantes
    inconsistency: Optional[str] = None
    if header.has_embargo:
        inconsistency = "Imóvel com embargo registrado — revisar urgente."
    elif not header.car_code:
        inconsistency = "CAR não cadastrado — pré-requisito regulatório."
    elif header.car_status in (None, "", "pendente"):
        inconsistency = "CAR em situação pendente — verificar análise."
    elif health.consistency < 70:
        inconsistency = "Campos cadastrais básicos incompletos."

    # Pendência top
    top_pending: Optional[str] = None
    if kpis.pending_critical > 0:
        top_pending = f"{kpis.pending_critical} documento(s) obrigatório(s) pendente(s) nos casos do imóvel"

    # Recomendação
    recommendation: Optional[str] = None
    if header.has_embargo:
        recommendation = "Validar embargo e anexar documentação de defesa."
    elif not header.car_code:
        recommendation = "Cadastrar CAR antes de avançar qualquer caso regulatório."
    elif kpis.pending_critical > 0:
        recommendation = "Priorizar coleta dos documentos obrigatórios faltantes."
    elif health.analysis_depth < 50 and kpis.cases_active > 0:
        recommendation = "Realizar análise técnica inicial antes de avançar."
    elif health.overall >= 75:
        recommendation = "Base consolidada — pronto para abrir novos casos."
    else:
        recommendation = "Acompanhar andamento normal dos casos."

    # Texto executivo
    parts = [
        f"Imóvel com {_plural(kpis.cases_count, 'caso registrado', 'casos registrados')}"
        + (f" ({kpis.cases_active} ativo{'' if kpis.cases_active == 1 else 's'})" if kpis.cases_active else ""),
        _plural(kpis.documents_count, "documento anexado", "documentos anexados"),
        f"score de saúde {health.overall}/100 ({health.label})",
    ]
    text = ". ".join(parts) + "."
    if cases:
        priority = next(
            (c for c in cases if c.state in ("travada", "aguardando_validacao")),
            None,
        )
        if priority:
            text += f" Caso prioritário: {priority.title} ({priority.state})."

    return PropertyAISummary(
        text=text,
        main_inconsistency=inconsistency,
        top_pending=top_pending,
        recommendation=recommendation,
        source="deterministic",
    )


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


_VALID_SOURCES = {"raw", "ai_extracted", "human_validated"}
_TRACKED_FIELDS = {
    "registry_number", "ccir", "nirf", "car_code", "total_area_ha",
    "municipality", "state", "biome",
    # CAM2IH-003/004 (Sprint H) — campos técnicos também validáveis
    "rl_status", "app_area_ha", "area_documental_ha", "area_grafica_ha", "tipologia",
}


@router.post("/{property_id}/validate-fields")
def validate_property_fields(
    property_id: int,
    body: PropertyFieldValidateRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_internal_user),
) -> Any:
    """CAM2IH-007 — Marca campos como validados pelo humano (ou outro source).

    Atualiza `Property.field_sources` com {field: source} para cada campo
    informado. Registra AuditLog.
    """
    prop = _get_property_or_404(db, current_user.tenant_id, property_id)

    source = body.source or "human_validated"
    if source not in _VALID_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"source inválido. Use um de: {sorted(_VALID_SOURCES)}",
        )

    unknown = [f for f in body.fields if f not in _TRACKED_FIELDS]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Campos desconhecidos: {unknown}. Aceitos: {sorted(_TRACKED_FIELDS)}",
        )

    sources = dict(prop.field_sources or {})
    for f in body.fields:
        sources[f] = source
    prop.field_sources = sources

    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        entity_type="property",
        entity_id=prop.id,
        action="fields_validated",
        details=f"Campos marcados como {source}: {', '.join(body.fields)}",
    )
    db.add(audit)
    db.commit()
    db.refresh(prop)
    return {
        "property_id": prop.id,
        "field_sources": prop.field_sources,
        "updated_count": len(body.fields),
    }
