from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.process import Process, ProcessStatus
from app.models.property import Property
from app.models.task import TERMINAL_TASK_STATUSES, Task
from app.models.user import User

router = APIRouter()

_ACTIVE_PROCESS_STATUSES = [
    s for s in ProcessStatus
    if s not in (ProcessStatus.cancelado, ProcessStatus.arquivado, ProcessStatus.concluido)
]

_OVERDUE_EXCLUDED_STATUSES = list(TERMINAL_TASK_STATUSES)


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


class DashboardSummary(BaseModel):
    active_processes: int
    overdue_tasks: int
    total_clients: int
    total_properties: int
    recent_activities: list[RecentActivity]
    my_pending_tasks: list[PendingTask]


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> DashboardSummary:
    """Retorna os dados agregados da dashboard para o tenant do usuário autenticado."""
    tenant_id = current_user.tenant_id
    now = datetime.now(UTC)

    active_processes = (
        db.query(Process)
        .filter(
            Process.tenant_id == tenant_id,
            Process.status.in_(_ACTIVE_PROCESS_STATUSES),
            Process.deleted_at.is_(None),
        )
        .count()
    )

    overdue_tasks = (
        db.query(Task)
        .filter(
            Task.tenant_id == tenant_id,
            Task.due_date < now,
            Task.status.notin_(_OVERDUE_EXCLUDED_STATUSES),
        )
        .count()
    )

    total_clients = (
        db.query(Client)
        .filter(Client.tenant_id == tenant_id)
        .count()
    )

    total_properties = (
        db.query(Property)
        .filter(Property.tenant_id == tenant_id)
        .count()
    )

    recent_log_rows = (
        db.query(AuditLog, User)
        .outerjoin(User, AuditLog.user_id == User.id)
        .filter(
            AuditLog.tenant_id == tenant_id,
            AuditLog.entity_type == "process",
        )
        .order_by(AuditLog.created_at.desc())
        .limit(8)
        .all()
    )

    recent_activities = [
        RecentActivity(
            id=log.id,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            action=log.action,
            details=log.details,
            actor_name=user.full_name if user else None,
            created_at=log.created_at,
        )
        for log, user in recent_log_rows
    ]

    my_task_rows = (
        db.query(Task)
        .filter(
            Task.tenant_id == tenant_id,
            Task.assigned_to_user_id == current_user.id,
            Task.status.notin_(list(TERMINAL_TASK_STATUSES)),
        )
        .order_by(Task.due_date.asc().nulls_last())
        .limit(10)
        .all()
    )

    my_pending_tasks = [
        PendingTask(
            id=t.id,
            title=t.title,
            status=t.status.value,
            priority=t.priority.value,
            process_id=t.process_id,
            due_date=t.due_date,
        )
        for t in my_task_rows
    ]

    return DashboardSummary(
        active_processes=active_processes,
        overdue_tasks=overdue_tasks,
        total_clients=total_clients,
        total_properties=total_properties,
        recent_activities=recent_activities,
        my_pending_tasks=my_pending_tasks,
    )
