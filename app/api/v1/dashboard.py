"""
Dashboard API — Visao Executivo vs Operacional.

GET /dashboard/summary?view=executivo  → KPIs de alto nivel, financeiro, pipeline
GET /dashboard/summary?view=operacional → Tarefas do dia, docs pendentes, alertas
"""

from __future__ import annotations

import enum
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Literal, Optional, Union

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.audit_log import AuditLog
from app.models.client import Client, ClientStatus
from app.models.contract import Contract, ContractStatus
from app.models.macroetapa import MACROETAPA_LABELS, Macroetapa
from app.models.document import Document
from app.models.process import Process, ProcessPriority, ProcessStatus
from app.models.proposal import Proposal, ProposalStatus
from app.models.property import Property
from app.models.task import TERMINAL_TASK_STATUSES, Task
from app.models.user import User
from app.services.notifications import _get_redis_client

router = APIRouter()
logger = logging.getLogger(__name__)

# Regente Cam3 / QA-008 — Leitura da IA do Quadro de Ações cacheada 1x/dia.
# Decisão da sócia em 2026-04-19: atualizar 1x/dia para controlar custo.
KANBAN_INSIGHTS_CACHE_TTL = 24 * 60 * 60  # 24h em segundos


def _kanban_insights_cache_key(tenant_id: int) -> str:
    return f"tenant:{tenant_id}:kanban_insights:v1"


# ---------------------------------------------------------------------------
# Enums e constantes
# ---------------------------------------------------------------------------

class ViewMode(str, enum.Enum):
    executivo = "executivo"
    operacional = "operacional"


_ACTIVE_PROCESS_STATUSES = [
    s for s in ProcessStatus
    if s not in (ProcessStatus.cancelado, ProcessStatus.arquivado, ProcessStatus.concluido)
]

_OVERDUE_EXCLUDED_STATUSES = list(TERMINAL_TASK_STATUSES)


# ---------------------------------------------------------------------------
# Schemas compartilhados
# ---------------------------------------------------------------------------

class RecentActivity(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    action: str
    details: Optional[str]
    actor_name: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PendingTask(BaseModel):
    id: int
    title: str
    status: str
    priority: str
    process_id: Optional[int]
    due_date: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Schemas Executivo
# ---------------------------------------------------------------------------

class StatusDistribution(BaseModel):
    status: str
    count: int


class ProposalPipelineItem(BaseModel):
    status: str
    count: int
    total_value: float


class ExecutivoDashboard(BaseModel):
    view: Literal["executivo"] = "executivo"
    # Contadores base
    active_processes: int
    overdue_tasks: int
    total_clients: int
    total_properties: int
    # KPIs executivos
    conversion_rate: float
    faturamento: float
    risco_medio: Optional[float]
    # Distribuicoes
    processes_by_status: list[StatusDistribution]
    processes_by_demand_type: list[StatusDistribution]
    proposal_pipeline: list[ProposalPipelineItem]
    # Secoes
    recent_activities: list[RecentActivity]
    my_pending_tasks: list[PendingTask]


# ---------------------------------------------------------------------------
# Schemas Operacional
# ---------------------------------------------------------------------------

class DocumentAlert(BaseModel):
    id: int
    filename: str
    document_type: Optional[str]
    process_id: Optional[int]
    expires_at: Optional[datetime]
    review_required: bool

    model_config = ConfigDict(from_attributes=True)


class ProcessAlert(BaseModel):
    id: int
    title: str
    status: str
    priority: Optional[str]
    due_date: Optional[datetime]
    days_in_status: Optional[int]

    model_config = ConfigDict(from_attributes=True)


class OperacionalDashboard(BaseModel):
    view: Literal["operacional"] = "operacional"
    # Contadores base
    active_processes: int
    overdue_tasks: int
    total_clients: int
    total_properties: int
    # KPIs operacionais
    my_pending_tasks_count: int
    my_overdue_tasks_count: int
    documents_needing_review: int
    processes_aguardando_orgao: int
    # Secoes
    my_pending_tasks: list[PendingTask]
    documents_for_review: list[DocumentAlert]
    expiring_documents: list[DocumentAlert]
    process_alerts: list[ProcessAlert]
    recent_activities: list[RecentActivity]


# ---------------------------------------------------------------------------
# Queries compartilhadas
# ---------------------------------------------------------------------------

def _base_counts(db: Session, tenant_id: int, now: datetime) -> dict:
    active_processes = (
        db.query(sa_func.count(Process.id))
        .filter(
            Process.tenant_id == tenant_id,
            Process.status.in_(_ACTIVE_PROCESS_STATUSES),
            Process.deleted_at.is_(None),
        )
        .scalar()
    ) or 0

    overdue_tasks = (
        db.query(sa_func.count(Task.id))
        .filter(
            Task.tenant_id == tenant_id,
            Task.due_date < now,
            Task.status.notin_(_OVERDUE_EXCLUDED_STATUSES),
        )
        .scalar()
    ) or 0

    total_clients = (
        db.query(sa_func.count(Client.id))
        .filter(Client.tenant_id == tenant_id)
        .scalar()
    ) or 0

    total_properties = (
        db.query(sa_func.count(Property.id))
        .filter(Property.tenant_id == tenant_id)
        .scalar()
    ) or 0

    return {
        "active_processes": active_processes,
        "overdue_tasks": overdue_tasks,
        "total_clients": total_clients,
        "total_properties": total_properties,
    }


def _recent_activities(db: Session, tenant_id: int, *, entity_type_filter: str | None = None) -> list[RecentActivity]:
    q = (
        db.query(AuditLog, User)
        .outerjoin(User, AuditLog.user_id == User.id)
        .filter(AuditLog.tenant_id == tenant_id)
    )
    if entity_type_filter:
        q = q.filter(AuditLog.entity_type == entity_type_filter)
    rows = q.order_by(AuditLog.created_at.desc()).limit(8).all()

    return [
        RecentActivity(
            id=log.id,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            action=log.action,
            details=log.details,
            actor_name=user.full_name if user else None,
            created_at=log.created_at,
        )
        for log, user in rows
    ]


def _my_pending_tasks(db: Session, tenant_id: int, user_id: int) -> list[PendingTask]:
    rows = (
        db.query(Task)
        .filter(
            Task.tenant_id == tenant_id,
            Task.assigned_to_user_id == user_id,
            Task.status.notin_(list(TERMINAL_TASK_STATUSES)),
        )
        .order_by(Task.due_date.asc().nulls_last())
        .limit(10)
        .all()
    )
    return [
        PendingTask(
            id=t.id,
            title=t.title,
            status=t.status.value,
            priority=t.priority.value,
            process_id=t.process_id,
            due_date=t.due_date,
        )
        for t in rows
    ]


# ---------------------------------------------------------------------------
# Queries Executivo
# ---------------------------------------------------------------------------

def _executivo_data(db: Session, tenant_id: int) -> dict:
    # Proposta pipeline: count e sum por status
    pipeline_rows = (
        db.query(
            Proposal.status,
            sa_func.count(Proposal.id),
            sa_func.coalesce(sa_func.sum(Proposal.total_value), 0.0),
        )
        .filter(Proposal.tenant_id == tenant_id)
        .group_by(Proposal.status)
        .all()
    )

    pipeline = [
        ProposalPipelineItem(
            status=row[0].value if hasattr(row[0], "value") else str(row[0]),
            count=row[1],
            total_value=float(row[2]),
        )
        for row in pipeline_rows
    ]

    # Conversao e faturamento
    sent_count = sum(p.count for p in pipeline if p.status == "sent")
    accepted_count = sum(p.count for p in pipeline if p.status == "accepted")
    faturamento = sum(p.total_value for p in pipeline if p.status == "accepted")
    conversion_rate = (accepted_count / sent_count) if sent_count > 0 else 0.0

    # Risco medio dos processos ativos
    risco_medio = (
        db.query(sa_func.avg(Process.risk_score))
        .filter(
            Process.tenant_id == tenant_id,
            Process.status.in_(_ACTIVE_PROCESS_STATUSES),
            Process.deleted_at.is_(None),
            Process.risk_score.isnot(None),
        )
        .scalar()
    )

    # Processos por status
    status_rows = (
        db.query(Process.status, sa_func.count(Process.id))
        .filter(Process.tenant_id == tenant_id, Process.deleted_at.is_(None))
        .group_by(Process.status)
        .all()
    )
    processes_by_status = [
        StatusDistribution(status=row[0].value if hasattr(row[0], "value") else str(row[0]), count=row[1])
        for row in status_rows
    ]

    # Processos por tipo de demanda
    demand_rows = (
        db.query(Process.demand_type, sa_func.count(Process.id))
        .filter(
            Process.tenant_id == tenant_id,
            Process.deleted_at.is_(None),
            Process.demand_type.isnot(None),
        )
        .group_by(Process.demand_type)
        .all()
    )
    processes_by_demand_type = [
        StatusDistribution(status=row[0].value if hasattr(row[0], "value") else str(row[0]), count=row[1])
        for row in demand_rows
    ]

    return {
        "conversion_rate": round(conversion_rate, 3),
        "faturamento": round(faturamento, 2),
        "risco_medio": round(float(risco_medio), 2) if risco_medio is not None else None,
        "processes_by_status": processes_by_status,
        "processes_by_demand_type": processes_by_demand_type,
        "proposal_pipeline": pipeline,
    }


# ---------------------------------------------------------------------------
# Queries Operacional
# ---------------------------------------------------------------------------

def _operacional_data(db: Session, tenant_id: int, user_id: int, now: datetime) -> dict:
    # Tarefas do usuario
    my_pending_count = (
        db.query(sa_func.count(Task.id))
        .filter(
            Task.tenant_id == tenant_id,
            Task.assigned_to_user_id == user_id,
            Task.status.notin_(list(TERMINAL_TASK_STATUSES)),
        )
        .scalar()
    ) or 0

    my_overdue_count = (
        db.query(sa_func.count(Task.id))
        .filter(
            Task.tenant_id == tenant_id,
            Task.assigned_to_user_id == user_id,
            Task.due_date < now,
            Task.status.notin_(list(TERMINAL_TASK_STATUSES)),
        )
        .scalar()
    ) or 0

    # Documentos para revisao
    docs_review_count = (
        db.query(sa_func.count(Document.id))
        .filter(
            Document.tenant_id == tenant_id,
            Document.review_required.is_(True),
            Document.deleted_at.is_(None),
        )
        .scalar()
    ) or 0

    docs_for_review = (
        db.query(Document)
        .filter(
            Document.tenant_id == tenant_id,
            Document.review_required.is_(True),
            Document.deleted_at.is_(None),
        )
        .order_by(Document.created_at.desc())
        .limit(15)
        .all()
    )

    # Documentos expirando (proximos 30 dias)
    soon = now + timedelta(days=30)
    expiring_docs = (
        db.query(Document)
        .filter(
            Document.tenant_id == tenant_id,
            Document.expires_at.isnot(None),
            Document.expires_at.between(now, soon),
            Document.deleted_at.is_(None),
        )
        .order_by(Document.expires_at.asc())
        .limit(15)
        .all()
    )

    # Processos aguardando orgao
    aguardando_count = (
        db.query(sa_func.count(Process.id))
        .filter(
            Process.tenant_id == tenant_id,
            Process.status == ProcessStatus.aguardando_orgao,
            Process.deleted_at.is_(None),
        )
        .scalar()
    ) or 0

    # Alertas de processo: parados >14 dias ou due_date proxima (7 dias)
    stale_threshold = now - timedelta(days=14)
    due_soon = now + timedelta(days=7)

    stale_processes = (
        db.query(Process)
        .filter(
            Process.tenant_id == tenant_id,
            Process.status.in_(_ACTIVE_PROCESS_STATUSES),
            Process.deleted_at.is_(None),
            Process.updated_at < stale_threshold,
        )
        .limit(10)
        .all()
    )

    due_processes = (
        db.query(Process)
        .filter(
            Process.tenant_id == tenant_id,
            Process.status.in_(_ACTIVE_PROCESS_STATUSES),
            Process.deleted_at.is_(None),
            Process.due_date.isnot(None),
            Process.due_date.between(now, due_soon),
        )
        .limit(10)
        .all()
    )

    # Combinar e deduplificar alertas
    alert_ids = set()
    process_alerts: list[ProcessAlert] = []
    for p in stale_processes + due_processes:
        if p.id in alert_ids:
            continue
        alert_ids.add(p.id)
        days_in = (now - p.updated_at).days if p.updated_at else None
        process_alerts.append(ProcessAlert(
            id=p.id,
            title=p.title,
            status=p.status.value if p.status else "",
            priority=p.priority.value if p.priority else None,
            due_date=p.due_date,
            days_in_status=days_in,
        ))

    return {
        "my_pending_tasks_count": my_pending_count,
        "my_overdue_tasks_count": my_overdue_count,
        "documents_needing_review": docs_review_count,
        "processes_aguardando_orgao": aguardando_count,
        "documents_for_review": [
            DocumentAlert(
                id=d.id,
                filename=d.original_file_name or d.filename or "",
                document_type=d.document_type,
                process_id=d.process_id,
                expires_at=d.expires_at,
                review_required=d.review_required or False,
            )
            for d in docs_for_review
        ],
        "expiring_documents": [
            DocumentAlert(
                id=d.id,
                filename=d.original_file_name or d.filename or "",
                document_type=d.document_type,
                process_id=d.process_id,
                expires_at=d.expires_at,
                review_required=d.review_required or False,
            )
            for d in expiring_docs
        ],
        "process_alerts": process_alerts,
    }


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=Union[ExecutivoDashboard, OperacionalDashboard])
def get_dashboard_summary(
    view: ViewMode = Query(ViewMode.executivo),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> ExecutivoDashboard | OperacionalDashboard:
    """Retorna os dados agregados da dashboard para o tenant do usuario autenticado."""
    tenant_id = current_user.tenant_id
    now = datetime.now(UTC)

    base = _base_counts(db, tenant_id, now)
    tasks = _my_pending_tasks(db, tenant_id, current_user.id)

    if view == ViewMode.executivo:
        activities = _recent_activities(db, tenant_id)  # Todas entidades
        exec_data = _executivo_data(db, tenant_id)
        return ExecutivoDashboard(
            **base,
            **exec_data,
            recent_activities=activities,
            my_pending_tasks=tasks,
        )

    # Operacional
    activities = _recent_activities(db, tenant_id, entity_type_filter="process")
    ops_data = _operacional_data(db, tenant_id, current_user.id, now)
    return OperacionalDashboard(
        **base,
        **ops_data,
        my_pending_tasks=tasks,
        recent_activities=activities,
    )


# ---------------------------------------------------------------------------
# Kanban Insights (Leitura da IA)
# ---------------------------------------------------------------------------

class KanbanInsight(BaseModel):
    gargalo_macroetapa: Optional[str] = None
    gargalo_label: Optional[str] = None
    gargalo_count: int = 0
    pendencias_criticas: int = 0
    prontos_para_avancar: int = 0
    mensagem: str = ""
    distribuicao: list[dict] = []


@router.get("/kanban-insights", response_model=KanbanInsight)
def get_kanban_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
    refresh: bool = Query(False, description="Força recálculo ignorando cache (24h TTL)."),
) -> KanbanInsight:
    """Analisa o kanban e retorna insights operacionais (Leitura da IA).

    Regente Cam3 / QA-008 — cache server-side de 24h por tenant.
    Usar ?refresh=true para recalcular sob demanda.
    """
    tenant_id = current_user.tenant_id
    cache_key = _kanban_insights_cache_key(tenant_id)

    # Tenta hit de cache primeiro (a menos que o caller peça refresh).
    if not refresh:
        try:
            cached = _get_redis_client().get(cache_key)
            if cached:
                return KanbanInsight(**json.loads(cached))
        except Exception:
            logger.warning("kanban_insights cache read failed", exc_info=True)

    # Contar processos por macroetapa
    rows = (
        db.query(Process.macroetapa, sa_func.count(Process.id))
        .filter(
            Process.tenant_id == tenant_id,
            Process.deleted_at.is_(None),
            Process.macroetapa.isnot(None),
            Process.status.notin_([ProcessStatus.cancelado, ProcessStatus.arquivado]),
        )
        .group_by(Process.macroetapa)
        .all()
    )

    distribuicao = []
    gargalo_etapa = None
    gargalo_count = 0
    total = 0

    for etapa_val, count in rows:
        total += count
        try:
            etapa = Macroetapa(etapa_val)
            label = MACROETAPA_LABELS[etapa]
        except ValueError:
            label = etapa_val
        distribuicao.append({"macroetapa": etapa_val, "label": label, "count": count})
        if count > gargalo_count:
            gargalo_count = count
            gargalo_etapa = etapa_val

    # Contar processos com urgencia alta/critica sem progresso
    pendencias_criticas = (
        db.query(sa_func.count(Process.id))
        .filter(
            Process.tenant_id == tenant_id,
            Process.deleted_at.is_(None),
            Process.macroetapa.isnot(None),
            Process.priority.in_([ProcessPriority.alta, ProcessPriority.critica]),
            Process.status.notin_([ProcessStatus.cancelado, ProcessStatus.arquivado, ProcessStatus.concluido]),
        )
        .scalar()
    ) or 0

    # Montar mensagem
    gargalo_label = None
    if gargalo_etapa:
        try:
            gargalo_label = MACROETAPA_LABELS[Macroetapa(gargalo_etapa)]
        except ValueError:
            gargalo_label = gargalo_etapa

    if gargalo_etapa and gargalo_count > 0:
        partes = [f"Hoje o maior acúmulo está em **{gargalo_label}** ({gargalo_count} casos)."]
        if pendencias_criticas > 0:
            partes.append(f"{pendencias_criticas} caso(s) possuem urgência alta ou crítica.")
        partes.append("Priorize os casos com urgência alta e documentos impeditivos.")
        mensagem = " ".join(partes)
    else:
        mensagem = "Nenhum caso ativo com macroetapa definida no momento."

    response = KanbanInsight(
        gargalo_macroetapa=gargalo_etapa,
        gargalo_label=gargalo_label,
        gargalo_count=gargalo_count,
        pendencias_criticas=pendencias_criticas,
        prontos_para_avancar=0,
        mensagem=mensagem,
        distribuicao=distribuicao,
    )

    # Grava no cache para as próximas 24h.
    try:
        _get_redis_client().setex(
            cache_key,
            KANBAN_INSIGHTS_CACHE_TTL,
            response.model_dump_json(),
        )
    except Exception:
        logger.warning("kanban_insights cache write failed", exc_info=True)

    return response


# ---------------------------------------------------------------------------
# Bloco 1 — Dashboard Operacional Regente (8 KPIs + Funil)
# Matching com o print Lovable da sócia.
# ---------------------------------------------------------------------------

class KpiValue(BaseModel):
    """KPI individual com valor e delta opcional em %."""
    key: str                      # identificador estável (ex: "clientes_ativos")
    label: str                    # rótulo do card
    value: int
    delta_pct: Optional[float] = None  # variação em % vs janela anterior (null se indeterminado)
    hint: Optional[str] = None    # texto curto de dica (ex: macroetapa usada)


class DashboardKpis(BaseModel):
    """Resposta do endpoint /dashboard/kpis — 8 cards operacionais."""
    days: int
    responsible_user_id: Optional[int] = None
    demand_type: Optional[str] = None
    kpis: list[KpiValue]
    funnel: list[StageDistribution]  # distribuição por macroetapa (para funil + barras)


def _safe_delta_pct(current: int, previous: int) -> Optional[float]:
    """Calcula variação percentual. Retorna None quando a base é zero ou baixa demais."""
    if previous <= 0:
        return None
    return round(((current - previous) / previous) * 100.0, 1)


def _count_processes_in_window(
    db: Session,
    *,
    tenant_id: int,
    window_start: datetime,
    window_end: datetime,
    macroetapa: Optional[list[str]] = None,
    responsible_user_id: Optional[int] = None,
    demand_type: Optional[str] = None,
) -> int:
    q = db.query(sa_func.count(Process.id)).filter(
        Process.tenant_id == tenant_id,
        Process.deleted_at.is_(None),
        Process.created_at >= window_start,
        Process.created_at < window_end,
    )
    if macroetapa:
        q = q.filter(Process.macroetapa.in_(macroetapa))
    if responsible_user_id:
        q = q.filter(Process.responsible_user_id == responsible_user_id)
    if demand_type:
        q = q.filter(Process.demand_type == demand_type)
    return q.scalar() or 0


@router.get("/kpis", response_model=DashboardKpis)
def get_dashboard_kpis(
    days: int = Query(30, ge=1, le=365, description="Janela de comparação em dias."),
    responsible_user_id: Optional[int] = None,
    demand_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> DashboardKpis:
    """Retorna os 8 KPIs operacionais + distribuição por macroetapa (p/ funil)."""
    tenant_id = current_user.tenant_id
    now = datetime.now(UTC)
    window_current = now - timedelta(days=days)
    window_previous = now - timedelta(days=days * 2)

    # ── Filtros comuns pra contagem SNAPSHOT ────────────────────────────────
    def _snapshot(query):
        if responsible_user_id:
            query = query.filter(Process.responsible_user_id == responsible_user_id)
        if demand_type:
            query = query.filter(Process.demand_type == demand_type)
        return query

    active_statuses_exclude = [
        ProcessStatus.concluido, ProcessStatus.arquivado, ProcessStatus.cancelado,
    ]

    # 1. Clientes ativos (snapshot)
    clientes_ativos = (
        db.query(sa_func.count(Client.id))
        .filter(
            Client.tenant_id == tenant_id,
            Client.status == ClientStatus.active,
            Client.deleted_at.is_(None),
        )
        .scalar()
    ) or 0
    # Delta de clientes: compara criados na janela atual vs anterior
    clientes_current = (
        db.query(sa_func.count(Client.id))
        .filter(
            Client.tenant_id == tenant_id,
            Client.created_at >= window_current,
            Client.created_at < now,
        )
        .scalar()
    ) or 0
    clientes_previous = (
        db.query(sa_func.count(Client.id))
        .filter(
            Client.tenant_id == tenant_id,
            Client.created_at >= window_previous,
            Client.created_at < window_current,
        )
        .scalar()
    ) or 0

    # 2. Casos ativos (snapshot)
    casos_ativos_q = _snapshot(
        db.query(sa_func.count(Process.id)).filter(
            Process.tenant_id == tenant_id,
            Process.deleted_at.is_(None),
            Process.status.notin_(active_statuses_exclude),
        )
    )
    casos_ativos = casos_ativos_q.scalar() or 0

    casos_current = _count_processes_in_window(
        db, tenant_id=tenant_id, window_start=window_current, window_end=now,
        responsible_user_id=responsible_user_id, demand_type=demand_type,
    )
    casos_previous = _count_processes_in_window(
        db, tenant_id=tenant_id, window_start=window_previous, window_end=window_current,
        responsible_user_id=responsible_user_id, demand_type=demand_type,
    )

    # 3/4/5. Casos por macroetapa (snapshot)
    def _count_by_macroetapa(etapas: list[str]) -> int:
        q = _snapshot(
            db.query(sa_func.count(Process.id)).filter(
                Process.tenant_id == tenant_id,
                Process.deleted_at.is_(None),
                Process.macroetapa.in_(etapas),
                Process.status.notin_(active_statuses_exclude),
            )
        )
        return q.scalar() or 0

    em_diagnostico = _count_by_macroetapa(["diagnostico_preliminar", "diagnostico_tecnico"])
    em_coleta = _count_by_macroetapa(["coleta_documental"])
    em_caminho_reg = _count_by_macroetapa(["caminho_regulatorio"])

    # 6. Propostas enviadas (snapshot: atualmente em status=sent)
    propostas_enviadas = (
        db.query(sa_func.count(Proposal.id))
        .filter(
            Proposal.tenant_id == tenant_id,
            Proposal.status == ProposalStatus.sent,
            Proposal.deleted_at.is_(None),
        )
        .scalar()
    ) or 0
    propostas_current = (
        db.query(sa_func.count(Proposal.id))
        .filter(
            Proposal.tenant_id == tenant_id,
            Proposal.created_at >= window_current,
            Proposal.created_at < now,
        )
        .scalar()
    ) or 0
    propostas_previous = (
        db.query(sa_func.count(Proposal.id))
        .filter(
            Proposal.tenant_id == tenant_id,
            Proposal.created_at >= window_previous,
            Proposal.created_at < window_current,
        )
        .scalar()
    ) or 0

    # 7. Contratos enviados (snapshot: atualmente em status=sent)
    contratos_enviados = (
        db.query(sa_func.count(Contract.id))
        .filter(
            Contract.tenant_id == tenant_id,
            Contract.status == ContractStatus.sent,
            Contract.deleted_at.is_(None),
        )
        .scalar()
    ) or 0

    # 8. Casos formalizados (snapshot: macroetapa=contrato_formalizacao OR status=concluido)
    casos_formalizados_q = _snapshot(
        db.query(sa_func.count(Process.id)).filter(
            Process.tenant_id == tenant_id,
            Process.deleted_at.is_(None),
        ).filter(
            sa_func.coalesce(Process.macroetapa, "") == "contrato_formalizacao"
        )
    )
    casos_formalizados = casos_formalizados_q.scalar() or 0

    # ── Funil: distribuição por macroetapa (para gráficos) ──────────────────
    rows = (
        _snapshot(
            db.query(Process.macroetapa, sa_func.count(Process.id))
            .filter(
                Process.tenant_id == tenant_id,
                Process.deleted_at.is_(None),
                Process.macroetapa.isnot(None),
                Process.status.notin_(active_statuses_exclude),
            )
        )
        .group_by(Process.macroetapa)
        .all()
    )
    by_etapa: dict[str, int] = {k: v for k, v in rows}
    funnel: list[StageDistribution] = []
    for etapa in list(Macroetapa):
        total = by_etapa.get(etapa.value, 0)
        funnel.append(StageDistribution(
            macroetapa=etapa.value,
            label=MACROETAPA_LABELS[etapa],
            total=total,
        ))

    kpis = [
        KpiValue(
            key="clientes_ativos",
            label="Clientes Ativos",
            value=clientes_ativos,
            delta_pct=_safe_delta_pct(clientes_current, clientes_previous),
        ),
        KpiValue(
            key="casos_ativos",
            label="Casos Ativos",
            value=casos_ativos,
            delta_pct=_safe_delta_pct(casos_current, casos_previous),
        ),
        KpiValue(
            key="em_diagnostico",
            label="Em Diagnóstico",
            value=em_diagnostico,
            hint="Diagnóstico preliminar + técnico",
        ),
        KpiValue(
            key="em_coleta",
            label="Em Coleta Documental",
            value=em_coleta,
        ),
        KpiValue(
            key="em_caminho_regulatorio",
            label="Em Caminho Regulatório",
            value=em_caminho_reg,
        ),
        KpiValue(
            key="propostas_enviadas",
            label="Propostas Enviadas",
            value=propostas_enviadas,
            delta_pct=_safe_delta_pct(propostas_current, propostas_previous),
            hint="Status: enviada",
        ),
        KpiValue(
            key="contratos_enviados",
            label="Contratos Enviados",
            value=contratos_enviados,
            hint="Status: enviado",
        ),
        KpiValue(
            key="casos_formalizados",
            label="Casos Formalizados",
            value=casos_formalizados,
            hint="Macroetapa: contrato e formalização",
        ),
    ]

    return DashboardKpis(
        days=days,
        responsible_user_id=responsible_user_id,
        demand_type=demand_type,
        kpis=kpis,
        funnel=funnel,
    )


# ---------------------------------------------------------------------------
# Regente Cam2 — Dashboard executivo (CAM2D-001 a CAM2D-004)
# ---------------------------------------------------------------------------

class StageDistribution(BaseModel):
    macroetapa: str
    label: str
    total: int
    blocked: int = 0
    ready_to_advance: int = 0
    avg_days_in_stage: Optional[float] = None


class DashboardAlert(BaseModel):
    kind: str       # doc_pendente | etapa_travada | contrato_aguardando | inconsistencia
    severity: str   # low | medium | high | critical
    count: int
    label: str      # texto curto ex "5 casos com matrícula pendente"
    macroetapa: Optional[str] = None


class DashboardPriorityCase(BaseModel):
    process_id: int
    client_name: Optional[str] = None
    property_name: Optional[str] = None
    demand_type: Optional[str] = None
    urgency: Optional[str] = None
    macroetapa: Optional[str] = None
    macroetapa_label: Optional[str] = None
    state: Optional[str] = None
    priority_reason: str
    next_step: Optional[str] = None
    responsible_user_name: Optional[str] = None


class DashboardAISummary(BaseModel):
    text: str
    top_stage_bottleneck: Optional[str] = None
    top_stage_bottleneck_label: Optional[str] = None
    critical_pending_count: int = 0
    ready_to_advance_count: int = 0
    recommendation: Optional[str] = None
    source: str = "deterministic"


def _apply_process_filters(
    query,
    *,
    responsible_user_id: Optional[int] = None,
    urgency: Optional[str] = None,
    demand_type: Optional[str] = None,
    state_uf: Optional[str] = None,
    days: Optional[int] = None,
    now: Optional[datetime] = None,
):
    """CAM2D-005 — aplica filtros executivos comuns em uma query de Process."""
    if responsible_user_id:
        query = query.filter(Process.responsible_user_id == responsible_user_id)
    if urgency:
        query = query.filter(Process.urgency == urgency)
    if demand_type:
        query = query.filter(Process.demand_type == demand_type)
    if state_uf:
        # state_uf aplicado via join com Property
        query = query.join(Property, Process.property_id == Property.id).filter(Property.state == state_uf)
    if days and now:
        since = now - timedelta(days=days)
        query = query.filter(Process.created_at >= since)
    return query


@router.get("/stages", response_model=list[StageDistribution])
def get_dashboard_stages(
    responsible_user_id: Optional[int] = Query(None),
    urgency: Optional[str] = Query(None, description="critica | alta | media | baixa"),
    demand_type: Optional[str] = Query(None),
    state_uf: Optional[str] = Query(None, description="UF do imóvel (2 letras)"),
    days: Optional[int] = Query(None, description="Considerar apenas casos criados nos últimos N dias"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> list[StageDistribution]:
    """CAM2D-001 + CAM2D-005 — Distribuição de casos pelas 7 macroetapas com filtros."""
    from app.models.checklist_template import ProcessChecklist  # noqa: PLC0415
    from app.models.macroetapa import (  # noqa: PLC0415
        MACROETAPA_ORDER,
        MacroetapaChecklist,
        compute_macroetapa_state,
        list_macroetapa_blockers,
    )

    tenant_id = current_user.tenant_id
    now = datetime.now(UTC)

    # Processos ativos por etapa
    q = (
        db.query(Process)
        .filter(
            Process.tenant_id == tenant_id,
            Process.deleted_at.is_(None),
            Process.macroetapa.isnot(None),
            Process.status.in_([s.value for s in _ACTIVE_PROCESS_STATUSES]),
        )
    )
    q = _apply_process_filters(
        q, responsible_user_id=responsible_user_id, urgency=urgency,
        demand_type=demand_type, state_uf=state_uf, days=days, now=now,
    )
    processes = q.all()

    proc_ids = [p.id for p in processes]

    # Checklists pra computar state por processo
    cl_map: dict[tuple[int, str], MacroetapaChecklist] = {}
    if proc_ids:
        for cl in db.query(MacroetapaChecklist).filter(MacroetapaChecklist.process_id.in_(proc_ids)).all():
            etapa = cl.macroetapa.value if hasattr(cl.macroetapa, "value") else cl.macroetapa
            cl_map[(cl.process_id, etapa)] = cl

    # Documentos obrigatórios pendentes por processo
    pending_by_proc: dict[int, int] = {}
    if proc_ids:
        for pc in db.query(ProcessChecklist).filter(ProcessChecklist.process_id.in_(proc_ids)).all():
            n = 0
            for item in pc.items or []:
                if item.get("required") and item.get("status") == "pending":
                    n += 1
            pending_by_proc[pc.process_id] = n

    # Agregação por etapa
    by_stage: dict[str, dict] = {
        m.value: {"total": 0, "blocked": 0, "ready": 0, "days_sum": 0.0, "days_count": 0}
        for m in MACROETAPA_ORDER
    }

    for p in processes:
        etapa = p.macroetapa
        if etapa not in by_stage:
            continue
        b = by_stage[etapa]
        b["total"] += 1

        # Tempo na etapa baseado em updated_at (proxy — pode refinar com audit log de mudança)
        if p.updated_at:
            days = (now - p.updated_at).days
            b["days_sum"] += max(days, 0)
            b["days_count"] += 1

        cl = cl_map.get((p.id, etapa))
        missing_docs = pending_by_proc.get(p.id, 0)
        blockers = list_macroetapa_blockers(cl, documents_pending_required=missing_docs)
        if cl:
            state = compute_macroetapa_state(
                cl, is_current=True, has_blockers=bool(blockers)
            )
            if state.value == "travada":
                b["blocked"] += 1
            elif state.value == "pronta_para_avancar":
                b["ready"] += 1

    return [
        StageDistribution(
            macroetapa=m.value,
            label=MACROETAPA_LABELS[m],
            total=by_stage[m.value]["total"],
            blocked=by_stage[m.value]["blocked"],
            ready_to_advance=by_stage[m.value]["ready"],
            avg_days_in_stage=(
                round(by_stage[m.value]["days_sum"] / by_stage[m.value]["days_count"], 1)
                if by_stage[m.value]["days_count"] > 0
                else None
            ),
        )
        for m in MACROETAPA_ORDER
    ]


@router.get("/alerts", response_model=list[DashboardAlert])
def get_dashboard_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> list[DashboardAlert]:
    """CAM2D-002 — Gargalos e alertas críticos agregados."""
    from app.models.checklist_template import ProcessChecklist  # noqa: PLC0415
    from app.models.macroetapa import (  # noqa: PLC0415
        MacroetapaChecklist,
        compute_macroetapa_state,
        list_macroetapa_blockers,
    )

    tenant_id = current_user.tenant_id
    alerts: list[DashboardAlert] = []

    # Processos ativos
    active_procs = (
        db.query(Process)
        .filter(
            Process.tenant_id == tenant_id,
            Process.deleted_at.is_(None),
            Process.status.in_([s.value for s in _ACTIVE_PROCESS_STATUSES]),
        )
        .all()
    )
    active_ids = [p.id for p in active_procs]

    # Docs obrigatórios pendentes — contagem por tipo
    doc_type_pending: dict[str, int] = {}
    if active_ids:
        for pc in db.query(ProcessChecklist).filter(ProcessChecklist.process_id.in_(active_ids)).all():
            for item in pc.items or []:
                if item.get("required") and item.get("status") == "pending":
                    dt = item.get("doc_type") or item.get("id") or "documento"
                    doc_type_pending[dt] = doc_type_pending.get(dt, 0) + 1
    for dt, count in sorted(doc_type_pending.items(), key=lambda x: -x[1])[:5]:
        if count > 0:
            label_dt = dt.replace("_", " ")
            alerts.append(DashboardAlert(
                kind="doc_pendente",
                severity="high" if count >= 3 else "medium",
                count=count,
                label=f"{count} caso(s) com {label_dt} pendente",
            ))

    # Etapas travadas
    if active_ids:
        cls = db.query(MacroetapaChecklist).filter(MacroetapaChecklist.process_id.in_(active_ids)).all()
        blocked_by_stage: dict[str, int] = {}
        # Mapa proc_id → macroetapa
        proc_macro = {p.id: p.macroetapa for p in active_procs}
        # Mapa proc_id → missing_docs
        missing_by_proc: dict[int, int] = {}
        for pc in db.query(ProcessChecklist).filter(ProcessChecklist.process_id.in_(active_ids)).all():
            n = 0
            for item in pc.items or []:
                if item.get("required") and item.get("status") == "pending":
                    n += 1
            missing_by_proc[pc.process_id] = n

        for cl in cls:
            etapa = cl.macroetapa.value if hasattr(cl.macroetapa, "value") else cl.macroetapa
            if proc_macro.get(cl.process_id) != etapa:
                continue  # só etapa corrente
            blockers = list_macroetapa_blockers(cl, documents_pending_required=missing_by_proc.get(cl.process_id, 0))
            state = compute_macroetapa_state(cl, is_current=True, has_blockers=bool(blockers))
            if state.value == "travada":
                blocked_by_stage[etapa] = blocked_by_stage.get(etapa, 0) + 1

        for etapa, count in sorted(blocked_by_stage.items(), key=lambda x: -x[1])[:3]:
            try:
                m_enum = Macroetapa(etapa)
                label = MACROETAPA_LABELS[m_enum]
            except ValueError:
                label = etapa
            alerts.append(DashboardAlert(
                kind="etapa_travada",
                severity="high",
                count=count,
                label=f"{count} caso(s) travado(s) em {label}",
                macroetapa=etapa,
            ))

    # Propostas sem retorno há >7 dias
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=7)
    stale_proposals = (
        db.query(sa_func.count(Proposal.id))
        .filter(
            Proposal.tenant_id == tenant_id,
            Proposal.sent_at.isnot(None),
            Proposal.sent_at < cutoff,
            Proposal.accepted_at.is_(None),
            Proposal.rejected_at.is_(None),
        )
        .scalar() or 0
    )
    if stale_proposals > 0:
        alerts.append(DashboardAlert(
            kind="proposta_sem_retorno",
            severity="medium",
            count=stale_proposals,
            label=f"{stale_proposals} proposta(s) sem retorno há mais de 7 dias",
        ))

    return alerts


@router.get("/priority-cases", response_model=list[DashboardPriorityCase])
def get_dashboard_priority_cases(
    limit: int = Query(10, le=50),
    responsible_user_id: Optional[int] = Query(None),
    urgency: Optional[str] = Query(None),
    demand_type: Optional[str] = Query(None),
    state_uf: Optional[str] = Query(None),
    days: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> list[DashboardPriorityCase]:
    """CAM2D-003 + CAM2D-005 — Casos prioritários do dia com filtros executivos."""
    from app.models.checklist_template import ProcessChecklist  # noqa: PLC0415
    from app.models.macroetapa import (  # noqa: PLC0415
        MacroetapaChecklist,
        compute_macroetapa_state,
        list_macroetapa_blockers,
    )

    tenant_id = current_user.tenant_id
    now = datetime.now(UTC)

    q = (
        db.query(Process)
        .filter(
            Process.tenant_id == tenant_id,
            Process.deleted_at.is_(None),
            Process.status.in_([s.value for s in _ACTIVE_PROCESS_STATUSES]),
        )
    )
    q = _apply_process_filters(
        q, responsible_user_id=responsible_user_id, urgency=urgency,
        demand_type=demand_type, state_uf=state_uf, days=days, now=now,
    )
    processes = q.all()
    proc_ids = [p.id for p in processes]
    if not proc_ids:
        return []

    # Preload
    clients = {c.id: c for c in db.query(Client).filter(Client.id.in_([p.client_id for p in processes if p.client_id])).all()}
    props = {p.id: p for p in db.query(Property).filter(Property.id.in_([pr.property_id for pr in processes if pr.property_id])).all()}
    users = {u.id: u for u in db.query(User).filter(User.id.in_([pr.responsible_user_id for pr in processes if pr.responsible_user_id])).all()}

    cl_map: dict[tuple[int, str], MacroetapaChecklist] = {}
    for cl in db.query(MacroetapaChecklist).filter(MacroetapaChecklist.process_id.in_(proc_ids)).all():
        etapa = cl.macroetapa.value if hasattr(cl.macroetapa, "value") else cl.macroetapa
        cl_map[(cl.process_id, etapa)] = cl

    missing_by_proc: dict[int, int] = {}
    for pc in db.query(ProcessChecklist).filter(ProcessChecklist.process_id.in_(proc_ids)).all():
        n = sum(1 for item in (pc.items or []) if item.get("required") and item.get("status") == "pending")
        missing_by_proc[pc.process_id] = n

    _URGENCY_WEIGHT = {"critica": 400, "alta": 200, "media": 50, "baixa": 0}

    scored: list[tuple[float, DashboardPriorityCase]] = []
    for p in processes:
        score = 0.0
        reasons: list[str] = []

        urg = (p.urgency or "").lower()
        score += _URGENCY_WEIGHT.get(urg, 0)
        if urg in ("critica", "alta"):
            reasons.append(f"urgência {urg}")

        # Dias parado (updated_at como proxy)
        if p.updated_at:
            days_stale = max((now - p.updated_at).days, 0)
            if days_stale >= 7:
                score += min(days_stale * 5, 150)
                reasons.append(f"{days_stale}d sem movimento")

        # Docs pendentes obrigatórios
        missing = missing_by_proc.get(p.id, 0)
        if missing > 0:
            score += missing * 20
            reasons.append(f"{missing} docs pendentes")

        # Estado da etapa corrente
        state_value: Optional[str] = None
        next_step: Optional[str] = None
        if p.macroetapa:
            cl = cl_map.get((p.id, p.macroetapa))
            if cl:
                blockers = list_macroetapa_blockers(cl, documents_pending_required=missing)
                state = compute_macroetapa_state(cl, is_current=True, has_blockers=bool(blockers))
                state_value = state.value
                if state.value == "travada":
                    score += 120
                    if "travas" not in reasons:
                        reasons.append("etapa travada")
                elif state.value == "pronta_para_avancar":
                    score += 80
                    reasons.append("pronto para avançar")
                elif state.value == "aguardando_validacao":
                    score += 100
                    reasons.append("aguardando validação humana")

                # Next step — primeira action pendente
                for a in cl.actions or []:
                    if not a.get("completed"):
                        next_step = a.get("label")
                        break

        if score <= 0:
            continue

        c = clients.get(p.client_id) if p.client_id else None
        prop = props.get(p.property_id) if p.property_id else None
        user = users.get(p.responsible_user_id) if p.responsible_user_id else None

        stage_label = None
        if p.macroetapa:
            try:
                stage_label = MACROETAPA_LABELS[Macroetapa(p.macroetapa)]
            except ValueError:
                stage_label = p.macroetapa

        scored.append((score, DashboardPriorityCase(
            process_id=p.id,
            client_name=c.full_name if c else None,
            property_name=prop.name if prop else None,
            demand_type=p.demand_type.value if p.demand_type else None,
            urgency=p.urgency,
            macroetapa=p.macroetapa,
            macroetapa_label=stage_label,
            state=state_value,
            priority_reason=", ".join(reasons) or "prioridade geral",
            next_step=next_step,
            responsible_user_name=user.full_name if user else None,
        )))

    scored.sort(key=lambda x: -x[0])
    return [pc for _, pc in scored[:limit]]


@router.get("/ai-summary", response_model=DashboardAISummary)
def get_dashboard_ai_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> DashboardAISummary:
    """CAM2D-004 — Leitura executiva da IA (determinística MVP)."""
    stages = get_dashboard_stages(db=db, current_user=current_user)
    alerts = get_dashboard_alerts(db=db, current_user=current_user)

    # Gargalo: etapa com mais bloqueados; empate, mais total
    bottleneck = max(stages, key=lambda s: (s.blocked, s.total), default=None)
    ready_total = sum(s.ready_to_advance for s in stages)
    critical_pending = sum(a.count for a in alerts if a.severity in ("high", "critical") and a.kind == "doc_pendente")
    blocked_total = sum(s.blocked for s in stages)

    parts: list[str] = []
    if bottleneck and bottleneck.blocked > 0:
        parts.append(
            f"Hoje o maior gargalo está em {bottleneck.label}: {bottleneck.blocked} caso(s) travado(s)"
        )
    elif bottleneck and bottleneck.total > 0:
        parts.append(f"Maior volume está em {bottleneck.label} ({bottleneck.total} casos)")

    if critical_pending > 0:
        parts.append(f"{critical_pending} documento(s) crítico(s) pendente(s)")
    if ready_total > 0:
        parts.append(f"{ready_total} caso(s) prontos para avançar")

    text = ". ".join(parts) + "." if parts else "Operação sem gargalos relevantes no momento."

    recommendation: Optional[str] = None
    if blocked_total > 0 and ready_total > 0:
        recommendation = "Aprove os casos prontos e endereçe simultaneamente as travas mais frequentes."
    elif blocked_total > 0:
        recommendation = f"Priorize destravar {bottleneck.label if bottleneck else 'a etapa com mais travas'}."
    elif ready_total > 0:
        recommendation = "Revise e valide os casos prontos para fazer o fluxo andar."
    else:
        recommendation = "Fluxo saudável. Mantenha o acompanhamento normal."

    return DashboardAISummary(
        text=text,
        top_stage_bottleneck=bottleneck.macroetapa if bottleneck and bottleneck.blocked > 0 else None,
        top_stage_bottleneck_label=bottleneck.label if bottleneck and bottleneck.blocked > 0 else None,
        critical_pending_count=critical_pending,
        ready_to_advance_count=ready_total,
        recommendation=recommendation,
        source="deterministic",
    )
