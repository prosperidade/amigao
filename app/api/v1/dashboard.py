"""
Dashboard API — Visao Executivo vs Operacional.

GET /dashboard/summary?view=executivo  → KPIs de alto nivel, financeiro, pipeline
GET /dashboard/summary?view=operacional → Tarefas do dia, docs pendentes, alertas
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime, timedelta
from typing import Literal, Optional, Union

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.macroetapa import MACROETAPA_LABELS, Macroetapa
from app.models.document import Document
from app.models.process import Process, ProcessPriority, ProcessStatus
from app.models.proposal import Proposal
from app.models.property import Property
from app.models.task import TERMINAL_TASK_STATUSES, Task
from app.models.user import User

router = APIRouter()


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
) -> KanbanInsight:
    """Analisa o kanban e retorna insights operacionais (Leitura da IA)."""
    tenant_id = current_user.tenant_id

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

    return KanbanInsight(
        gargalo_macroetapa=gargalo_etapa,
        gargalo_label=gargalo_label,
        gargalo_count=gargalo_count,
        pendencias_criticas=pendencias_criticas,
        prontos_para_avancar=0,
        mensagem=mensagem,
        distribuicao=distribuicao,
    )
