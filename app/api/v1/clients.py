from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.audit_log import AuditLog
from app.models.client import Client as ClientModel
from app.models.client import ClientStatus
from app.models.client_representative import ClientRepresentative as RepModel
from app.models.macroetapa import (
    Macroetapa,
    MacroetapaChecklist,
    compute_macroetapa_state,
    list_macroetapa_blockers,
)
from app.models.process import Process as ProcessModel
from app.models.process import ProcessStatus
from app.models.property import Property as PropertyModel
from app.models.user import User
from app.repositories import ClientRepository
from app.schemas.client import (
    Client,
    ClientCreate,
    ClientRepresentative,
    ClientRepresentativeCreate,
    ClientRepresentativeUpdate,
    ClientUpdate,
)
from app.schemas.client_hub import (
    ClientHubAISummary,
    ClientHubChips,
    ClientHubHeader,
    ClientHubKpis,
    ClientHubProperty,
    ClientHubPropertyEvent,
    ClientHubRepresentante,
    ClientHubSummary,
    ClientHubTimelineItem,
)
from app.services.identity import find_client_by_doc, normalize_doc

router = APIRouter()


@router.get("/", response_model=list[Client])
def list_clients(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Lista todos os clientes do tenant autenticado."""
    repo = ClientRepository(db, current_user.tenant_id)
    return repo.list(skip=skip, limit=limit)


@router.post("/", response_model=Client, status_code=status.HTTP_201_CREATED)
def create_client(
    *,
    db: Session = Depends(get_db),
    client_in: ClientCreate,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Cria um novo cliente para o tenant autenticado.

    ENT-002: antes de criar, procura correspondência EXATA por documento
    normalizado. Achou → 409 com o cadastro existente no corpo, para a tela
    oferecer reutilização em vez de fabricar um segundo histórico. A fusão dos
    duplicados HISTÓRICOS não acontece aqui (a spec veta fusão automática);
    isto só impede o próximo.
    """
    repo = ClientRepository(db, current_user.tenant_id)
    _bloqueia_documento_duplicado(db, current_user.tenant_id, client_in.cpf_cnpj)
    client = repo.create(client_in.model_dump())
    db.commit()
    db.refresh(client)
    return client


def _bloqueia_documento_duplicado(db: Session, tenant_id: int, documento: Optional[str],
                                  exclude_id: Optional[int] = None) -> None:
    """409 quando o documento já pertence a outro cadastro do tenant."""
    existente = find_client_by_doc(db, tenant_id, documento, exclude_id=exclude_id)
    if existente is None:
        return
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "documento_ja_cadastrado",
            "message": (
                f"O documento {documento} já pertence ao cadastro "
                f"#{existente.id} — {existente.legal_name or existente.full_name}. "
                "Use o cadastro existente ou atualize os dados dele."
            ),
            "client_id": existente.id,
            "full_name": existente.full_name,
            "legal_name": existente.legal_name,
            "cpf_cnpj": existente.cpf_cnpj,
        },
    )


@router.get("/lookup/documento", response_model=Optional[Client])
def lookup_client_por_documento(
    documento: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Cadastro do tenant com este CPF/CNPJ, ou `null` (ENT-002).

    Serve à tela de cadastro: perguntar ANTES de digitar o resto é o que
    transforma "duplicata bloqueada no fim" em "reutilização oferecida no
    começo". Compara por dígitos — pontuação não cria pessoa nova.
    """
    if not normalize_doc(documento):
        return None
    return find_client_by_doc(db, current_user.tenant_id, documento)


@router.get("/{client_id}", response_model=Client)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Retorna um cliente pelo ID."""
    repo = ClientRepository(db, current_user.tenant_id)
    return repo.get_or_404(client_id, detail="Cliente não encontrado")


@router.put("/{client_id}", response_model=Client)
@router.patch("/{client_id}", response_model=Client)
def update_client(
    client_id: int,
    *,
    db: Session = Depends(get_db),
    client_in: ClientUpdate,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Atualiza os dados de um cliente."""
    repo = ClientRepository(db, current_user.tenant_id)
    # Mesma regra na EDIÇÃO: trocar o documento de um cadastro para o de outro
    # é criar o duplicado pela porta dos fundos (lição registrada: cobrir PATCH
    # além de POST).
    dados = client_in.model_dump(exclude_unset=True)
    if "cpf_cnpj" in dados:
        _bloqueia_documento_duplicado(db, current_user.tenant_id, dados["cpf_cnpj"],
                                      exclude_id=client_id)
    client = repo.update(client_id, dados, detail="Cliente não encontrado")
    db.commit()
    db.refresh(client)
    return client


@router.get("/{client_id}/delete-preview")
def get_client_delete_preview(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Preview da cascata antes do DELETE — usado pelo modal de confirmação."""
    from app.services.cascade_delete import preview_client_cascade  # noqa: PLC0415

    _get_client_or_404(db, current_user.tenant_id, client_id)
    return preview_client_cascade(db, current_user.tenant_id, client_id).to_dict()


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> None:
    """Remove cliente em cascata controlada (LGPD: registra AuditLog com hash chain).

    Apaga: contratos, propostas, processos, checklists, documentos e imóveis
    pertencentes ao cliente — sempre nessa ordem para satisfazer FKs RESTRICT.
    Nunca toca documentos de outro cliente.
    """
    from app.services.cascade_delete import cascade_delete_client  # noqa: PLC0415

    cascade_delete_client(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        client_id=client_id,
    )
    db.commit()


# ---------------------------------------------------------------------------
# CLIENTE HUB (Regente Cam2 — CAM2CH)
# ---------------------------------------------------------------------------

def _get_client_or_404(db: Session, tenant_id: int, client_id: int) -> ClientModel:
    c = (
        db.query(ClientModel)
        .filter(ClientModel.id == client_id, ClientModel.tenant_id == tenant_id)
        .first()
    )
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    return c


def _compute_status_label(status: ClientStatus, cases_active: int) -> str:
    """CAM2CH-002 — Status operacional visual decidido pela sócia em 2026-04-19.

    Mapeia o enum persistido (lead/active/inactive/delinquent/blocked) para os
    labels operacionais do Regente (ativo / em andamento / sem casos ativos /
    bloqueado). 'Em andamento' e 'Sem casos ativos' são derivados do volume,
    não persistidos.
    """
    if status == ClientStatus.blocked:
        return "Bloqueado"
    if status == ClientStatus.active:
        return "Em andamento" if cases_active > 0 else "Sem casos ativos"
    if status == ClientStatus.lead:
        return "Lead"
    if status == ClientStatus.inactive:
        return "Inativo"
    if status == ClientStatus.delinquent:
        return "Inadimplente"
    return "Ativo"


def _compute_hub_state(kpis: ClientHubKpis, client_age_days: int, has_alerts: bool) -> str:
    """CAM2CH-009 — deriva estado do hub baseado em volume + idade + alertas."""
    if has_alerts:
        return "com_alertas"
    if kpis.cases_completed >= 5:
        return "consolidado"
    if kpis.properties_count >= 2 or kpis.cases_active >= 1:
        return "ativo"
    if client_age_days < 7 and kpis.properties_count <= 1:
        return "recem_criado"
    return "em_construcao"


@router.get("/{client_id}/summary", response_model=ClientHubSummary)
def get_client_hub_summary(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """CAM2CH-002+003+009 — Cabeçalho + KPIs + chips + estado do hub."""
    from app.models.checklist_template import ProcessChecklist  # noqa: PLC0415
    from app.models.contract import Contract, ContractStatus  # noqa: PLC0415

    c = _get_client_or_404(db, current_user.tenant_id, client_id)
    tenant_id = current_user.tenant_id

    # KPIs agregados
    properties_count = (
        db.query(func.count(PropertyModel.id))
        .filter(PropertyModel.client_id == client_id, PropertyModel.tenant_id == tenant_id)
        .scalar() or 0
    )

    # Casos
    procs = (
        db.query(ProcessModel)
        .filter(
            ProcessModel.client_id == client_id,
            ProcessModel.tenant_id == tenant_id,
            ProcessModel.deleted_at.is_(None),
        )
        .all()
    )
    cases_active = sum(
        1 for p in procs
        if p.status not in (ProcessStatus.cancelado, ProcessStatus.arquivado, ProcessStatus.concluido)
    )
    cases_completed = sum(1 for p in procs if p.status == ProcessStatus.concluido)
    diagnoses_done = sum(1 for p in procs if p.initial_diagnosis)

    # Contratos emitidos (qualquer status)
    contracts_emitted = (
        db.query(func.count(Contract.id))
        .filter(Contract.client_id == client_id, Contract.tenant_id == tenant_id)
        .scalar() or 0
    )

    # Contratos pendentes (draft/sent não assinados)
    contracts_pending = (
        db.query(func.count(Contract.id))
        .filter(
            Contract.client_id == client_id,
            Contract.tenant_id == tenant_id,
            Contract.status.in_([ContractStatus.draft, ContractStatus.sent]),
        )
        .scalar() or 0
    )

    # Pendências críticas: docs obrigatórios pendentes em qualquer caso
    pending_critical = 0
    proc_ids = [p.id for p in procs]
    if proc_ids:
        pcs = (
            db.query(ProcessChecklist)
            .filter(ProcessChecklist.process_id.in_(proc_ids))
            .all()
        )
        for pc in pcs:
            if pc.items:
                for item in pc.items:
                    if item.get("required") and item.get("status") == "pending":
                        pending_critical += 1

    # Última atividade (max updated_at entre process/property)
    last_activity = None
    if procs:
        last_activity = max((p.updated_at or p.created_at for p in procs), default=None)

    kpis = ClientHubKpis(
        properties_count=properties_count,
        cases_active=cases_active,
        cases_completed=cases_completed,
        contracts_emitted=contracts_emitted,
        diagnoses_done=diagnoses_done,
        pending_critical=pending_critical,
        last_activity_at=last_activity,
    )

    chips = ClientHubChips(
        is_active=(c.status == ClientStatus.active),
        has_active_cases=cases_active > 0,
        has_doc_pending=pending_critical > 0,
        has_contract_pending=contracts_pending > 0,
        is_pj=(c.client_type and c.client_type.value == "pj"),
    )

    age_days = (
        (datetime.now(UTC) - c.created_at).days if c.created_at else 0
    )
    state = _compute_hub_state(kpis, age_days, has_alerts=pending_critical > 0)

    header = ClientHubHeader(
        id=c.id,
        full_name=c.full_name,
        legal_name=c.legal_name,
        client_type=c.client_type.value if c.client_type else "pf",
        cpf_cnpj=c.cpf_cnpj,
        email=c.email,
        phone=c.phone,
        status=c.status.value if c.status else "lead",
        status_label=_compute_status_label(c.status or ClientStatus.lead, cases_active),
        source_channel=c.source_channel,
        created_at=c.created_at,
        field_sources=c.field_sources or {},
        representantes=[
            ClientHubRepresentante(id=r.id, full_name=r.full_name, cpf=r.cpf, papel=r.papel)
            for r in (c.representatives or [])
            if r.deleted_at is None
        ],
    )

    return ClientHubSummary(header=header, chips=chips, kpis=kpis, state=state)


@router.get("/{client_id}/properties-with-status", response_model=list[ClientHubProperty])
def get_client_properties_with_status(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """CAM2CH-004 — Lista de imóveis do cliente com status do caso primário."""
    _get_client_or_404(db, current_user.tenant_id, client_id)
    tenant_id = current_user.tenant_id

    props = (
        db.query(PropertyModel)
        .filter(PropertyModel.client_id == client_id, PropertyModel.tenant_id == tenant_id)
        .order_by(PropertyModel.id.desc())
        .all()
    )
    if not props:
        return []

    prop_ids = [p.id for p in props]
    procs = (
        db.query(ProcessModel)
        .filter(
            ProcessModel.property_id.in_(prop_ids),
            ProcessModel.tenant_id == tenant_id,
            ProcessModel.deleted_at.is_(None),
        )
        .order_by(ProcessModel.updated_at.desc().nullslast(), ProcessModel.created_at.desc())
        .all()
    )
    procs_by_prop: dict[int, list[ProcessModel]] = {}
    for p in procs:
        procs_by_prop.setdefault(p.property_id, []).append(p)

    # Carrega checklists das macroetapas correntes pra computar state
    proc_ids = [p.id for p in procs]
    cl_map: dict[tuple[int, str], MacroetapaChecklist] = {}
    if proc_ids:
        cls = (
            db.query(MacroetapaChecklist)
            .filter(MacroetapaChecklist.process_id.in_(proc_ids))
            .all()
        )
        for cl in cls:
            etapa = cl.macroetapa.value if hasattr(cl.macroetapa, "value") else cl.macroetapa
            cl_map[(cl.process_id, etapa)] = cl

    # CAM2CH-005 — coletar audit logs dos imóveis e dos processos pra mini-timeline
    # Filtro composto em uma query única pra evitar N+1
    from sqlalchemy import and_, or_  # noqa: PLC0415
    events_by_prop: dict[int, list[ClientHubPropertyEvent]] = {pid: [] for pid in prop_ids}
    proc_ids_all = [p.id for p in procs]
    proc_to_prop = {p.id: p.property_id for p in procs}

    conds = [and_(AuditLog.entity_type == "property", AuditLog.entity_id.in_(prop_ids))]
    if proc_ids_all:
        conds.append(and_(AuditLog.entity_type == "process", AuditLog.entity_id.in_(proc_ids_all)))

    audit_logs = (
        db.query(AuditLog)
        .filter(AuditLog.tenant_id == tenant_id, or_(*conds))
        .order_by(AuditLog.created_at.desc())
        .limit(200)
        .all()
    )

    _ACTION_LABELS = {
        "created":           ("cadastro_criado", "Cadastro criado"),
        "base_enriched":     ("base_complementada", "Base complementada"),
        "status_changed":    ("status_alterado", "Status alterado"),
        "macroetapa_changed":("etapa_avancada", "Etapa avançada"),
        "uploaded":          ("doc_anexado", "Documento anexado"),
    }
    for log in audit_logs:
        prop_id = (
            log.entity_id if log.entity_type == "property"
            else proc_to_prop.get(log.entity_id) if log.entity_type == "process"
            else None
        )
        if not prop_id or prop_id not in events_by_prop:
            continue
        if len(events_by_prop[prop_id]) >= 8:
            continue  # limita a 8 eventos por imóvel
        kind, label = _ACTION_LABELS.get(log.action, (log.action, log.details or log.action))
        macro = None
        # Tenta extrair macroetapa do details "Macroetapa avançada para X"
        if log.action == "macroetapa_changed" and log.details:
            for etapa in Macroetapa:
                if etapa.value in (log.details or ""):
                    macro = etapa.value
                    label = f"Avançou para {etapa.value.replace('_', ' ')}"
                    break
        events_by_prop[prop_id].append(ClientHubPropertyEvent(
            when=log.created_at,
            kind=kind,
            label=label,
            macroetapa=macro,
        ))

    out: list[ClientHubProperty] = []
    for prop in props:
        prop_procs = procs_by_prop.get(prop.id, [])
        primary = prop_procs[0] if prop_procs else None
        primary_state: Optional[str] = None
        if primary and primary.macroetapa:
            cl = cl_map.get((primary.id, primary.macroetapa))
            if cl:
                blockers = list_macroetapa_blockers(cl, documents_pending_required=0)
                primary_state = compute_macroetapa_state(
                    cl, is_current=True, has_blockers=bool(blockers)
                ).value

        out.append(ClientHubProperty(
            id=prop.id,
            name=prop.name,
            matricula=getattr(prop, "matricula", None) or getattr(prop, "registry_number", None),
            car_code=prop.car_code,
            municipality=prop.municipality,
            state=prop.state,
            total_area_ha=prop.total_area_ha,
            cases_count=len(prop_procs),
            primary_case_id=primary.id if primary else None,
            primary_case_macroetapa=primary.macroetapa if primary else None,
            primary_case_state=primary_state,
            last_activity_at=primary.updated_at if primary else None,
            events=events_by_prop.get(prop.id, []),
        ))
    return out


@router.get("/{client_id}/ai-summary", response_model=ClientHubAISummary)
def get_client_ai_summary(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """CAM2CH-007 — Painel lateral de IA (Bloco 6).

    Versão MVP determinística: consolida dados já agregados (summary + properties)
    em texto executivo com regras simples. Sem chamada a LLM — evita latência
    e custo no MVP. Fácil de trocar depois por agent_atendimento se necessário.
    """
    # Reaproveita a lógica do summary + properties
    summary = get_client_hub_summary(client_id, db=db, current_user=current_user)
    props = get_client_properties_with_status(client_id, db=db, current_user=current_user)

    kpis = summary.kpis
    focus_prop = None
    top_pending = None

    # Foco: imóvel com caso em estado "travada" ou "aguardando_validacao"
    priority_states = {"travada", "aguardando_validacao", "aguardando_input"}
    for p in props:
        if p.primary_case_state in priority_states:
            focus_prop = p
            break
    if not focus_prop and props:
        focus_prop = props[0]

    # Pendência mais crítica
    if kpis.pending_critical > 0:
        top_pending = f"{kpis.pending_critical} documento(s) obrigatório(s) pendente(s) nos casos ativos"
    elif focus_prop and focus_prop.primary_case_state == "aguardando_validacao":
        top_pending = f"Validação humana pendente em {focus_prop.name}"

    # Recomendação
    recommendation: Optional[str] = None
    if summary.state == "com_alertas":
        recommendation = "Priorize resolver a pendência crítica antes de abrir novos casos."
    elif summary.state == "recem_criado":
        recommendation = "Complete o cadastro básico e adicione o primeiro imóvel."
    elif kpis.cases_active == 0 and kpis.properties_count > 0:
        recommendation = "Cliente sem casos ativos. Considere reabrir contato ou avaliar oportunidade."
    elif focus_prop and focus_prop.primary_case_state == "pronta_para_avancar":
        recommendation = f"Caso de {focus_prop.name} está pronto para avançar de etapa."
    else:
        recommendation = "Acompanhar andamento normal dos casos."

    # Texto executivo
    def _plural(n: int, singular: str, plural: str) -> str:
        return f"{n} {singular if n == 1 else plural}"

    parts = [
        f"Cliente com {_plural(kpis.properties_count, 'imóvel vinculado', 'imóveis vinculados')}",
        _plural(kpis.cases_active, "caso ativo", "casos ativos"),
        _plural(kpis.contracts_emitted, "contrato emitido", "contratos emitidos"),
    ]
    text = ". ".join(parts) + "."
    if focus_prop and kpis.pending_critical > 0:
        text += f" O imóvel {focus_prop.name} concentra a principal pendência atual."

    return ClientHubAISummary(
        text=text,
        focus_property_id=focus_prop.id if focus_prop else None,
        focus_property_name=focus_prop.name if focus_prop else None,
        top_pending=top_pending,
        recommendation=recommendation,
        source="deterministic",
    )


@router.get("/{client_id}/timeline", response_model=list[ClientHubTimelineItem])
def get_client_timeline(
    client_id: int,
    limit: int = 50,
    days: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """CAM2CH-006 — Timeline geral da relação com o cliente.

    Reúne eventos do AuditLog filtrados por entidades do cliente
    (cliente, imóveis, processos do cliente).
    """
    _get_client_or_404(db, current_user.tenant_id, client_id)
    tenant_id = current_user.tenant_id

    # IDs relevantes pra filtrar audit logs
    prop_ids = [
        pid for (pid,) in db.query(PropertyModel.id)
        .filter(PropertyModel.client_id == client_id, PropertyModel.tenant_id == tenant_id)
        .all()
    ]
    proc_ids = [
        pid for (pid,) in db.query(ProcessModel.id)
        .filter(ProcessModel.client_id == client_id, ProcessModel.tenant_id == tenant_id)
        .all()
    ]

    q = db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id)

    # Filtro composto: client + (any property) + (any process)
    from sqlalchemy import and_, or_  # noqa: PLC0415
    conds = [and_(AuditLog.entity_type == "client", AuditLog.entity_id == client_id)]
    if prop_ids:
        conds.append(and_(AuditLog.entity_type == "property", AuditLog.entity_id.in_(prop_ids)))
    if proc_ids:
        conds.append(and_(AuditLog.entity_type == "process", AuditLog.entity_id.in_(proc_ids)))
    q = q.filter(or_(*conds))

    if days:
        since = datetime.now(UTC) - timedelta(days=days)
        q = q.filter(AuditLog.created_at >= since)

    logs = q.order_by(AuditLog.created_at.desc()).limit(limit).all()

    return [
        ClientHubTimelineItem(
            when=log.created_at,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            action=log.action,
            description=log.details,
            user_id=log.user_id,
        )
        for log in logs
    ]


# ---------------------------------------------------------------------------
# Representantes da PJ (ENT-001)
# ---------------------------------------------------------------------------
# Sob `/clients/{id}/representatives` e não em rota própria de topo porque é
# exatamente isso que a entidade é: subordinada. Não existe representante sem
# titular, e não há tela que o procure fora do cliente.


def _client_pj_ou_404(db: Session, tenant_id: int, client_id: int) -> ClientModel:
    """Cliente do tenant que PODE ter representante. 404 fora do tenant."""
    client = (
        db.query(ClientModel)
        .filter(ClientModel.id == client_id, ClientModel.tenant_id == tenant_id,
                ClientModel.deleted_at.is_(None))
        .first()
    )
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    tipo = getattr(client.client_type, "value", client.client_type)
    if (tipo or "").lower() != "pj":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Representante só existe em cliente pessoa jurídica. Em pessoa "
                "física o documento pessoal é do próprio titular."
            ),
        )
    return client


def _representante_ou_404(db: Session, tenant_id: int, client_id: int, rep_id: int) -> RepModel:
    rep = (
        db.query(RepModel)
        .filter(RepModel.id == rep_id, RepModel.tenant_id == tenant_id,
                RepModel.client_id == client_id, RepModel.deleted_at.is_(None))
        .first()
    )
    if rep is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Representante não encontrado")
    return rep


@router.get("/{client_id}/representatives", response_model=list[ClientRepresentative])
def list_representatives(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Representantes do cliente PJ."""
    _client_pj_ou_404(db, current_user.tenant_id, client_id)
    return (
        db.query(RepModel)
        .filter(RepModel.tenant_id == current_user.tenant_id,
                RepModel.client_id == client_id, RepModel.deleted_at.is_(None))
        .order_by(RepModel.id.asc())
        .all()
    )


@router.post("/{client_id}/representatives", response_model=ClientRepresentative,
             status_code=status.HTTP_201_CREATED)
def create_representative(
    client_id: int,
    *,
    payload: ClientRepresentativeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Cadastra representante do cliente PJ (papel, nunca titularidade)."""
    _client_pj_ou_404(db, current_user.tenant_id, client_id)
    dados = payload.model_dump(exclude_unset=True)
    rep = RepModel(
        tenant_id=current_user.tenant_id,
        client_id=client_id,
        # Digitado pelo consultor: a proveniência é humana desde o nascimento.
        field_sources={k: "human_validated" for k, v in dados.items() if v is not None},
        **dados,
    )
    db.add(rep)
    db.commit()
    db.refresh(rep)
    return rep


@router.patch("/{client_id}/representatives/{rep_id}", response_model=ClientRepresentative)
def update_representative(
    client_id: int,
    rep_id: int,
    *,
    payload: ClientRepresentativeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Corrige dados do representante."""
    _client_pj_ou_404(db, current_user.tenant_id, client_id)
    rep = _representante_ou_404(db, current_user.tenant_id, client_id, rep_id)
    dados = payload.model_dump(exclude_unset=True)
    fs = dict(rep.field_sources or {})
    for campo, valor in dados.items():
        setattr(rep, campo, valor)
        fs[campo] = "human_validated"
    rep.field_sources = fs
    db.commit()
    db.refresh(rep)
    return rep


@router.delete("/{client_id}/representatives/{rep_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_representative(
    client_id: int,
    rep_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> None:
    """Remove o representante (soft delete — o vínculo já existiu)."""
    _client_pj_ou_404(db, current_user.tenant_id, client_id)
    rep = _representante_ou_404(db, current_user.tenant_id, client_id, rep_id)
    rep.deleted_at = datetime.now(UTC)
    db.commit()
