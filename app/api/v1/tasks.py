from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.core.alerts import emit_operational_alert
from app.core.metrics import record_task_transition
from app.models.task import (
    TERMINAL_TASK_STATUSES,
    VALID_TASK_TRANSITIONS,
    TaskStatus,
    is_valid_task_transition,
)
from app.models.task import (
    Task as TaskModel,
)
from app.models.user import User
from app.repositories import TaskRepository
from app.schemas.task import Task, TaskCreate, TaskStatusUpdate, TaskUpdate
from app.services.notifications import publish_realtime_event

router = APIRouter()


def _serialize_task(task_obj: TaskModel) -> Task:
    task_payload = Task.model_validate(task_obj).model_dump()
    task_payload["allowed_transitions"] = VALID_TASK_TRANSITIONS.get(task_obj.status, [])
    return Task.model_validate(task_payload)


def _emit_task_deadline_alert(task_obj: TaskModel) -> None:
    if not task_obj.due_date or task_obj.status in TERMINAL_TASK_STATUSES:
        return

    due_date = task_obj.due_date
    if due_date.tzinfo is None:
        due_date = due_date.replace(tzinfo=UTC)

    if due_date < datetime.now(UTC):
        emit_operational_alert(
            category="deadline_alert",
            severity="warning",
            message="Tarefa vencida permanece aberta",
            metadata={
                "task_id": task_obj.id,
                "process_id": task_obj.process_id,
                "status": task_obj.status.value,
                "due_date": due_date.isoformat(),
            },
        )


def _validate_task_status_transition(task_obj: TaskModel, new_status: TaskStatus) -> None:
    if not is_valid_task_transition(task_obj.status, new_status):
        record_task_transition(task_obj.status.value, new_status.value, "rejected")
        raise HTTPException(
            status_code=400,
            detail=(
                f"Transição de status inválida: não é permitido ir de "
                f"'{task_obj.status.value}' para '{new_status.value}'"
            ),
        )

    if new_status == TaskStatus.concluida:
        unresolved_dependencies = [
            dependency.id
            for dependency in task_obj.dependencies
            if dependency.status != TaskStatus.concluida
        ]
        if unresolved_dependencies:
            record_task_transition(task_obj.status.value, new_status.value, "blocked_by_dependency")
            raise HTTPException(
                status_code=400,
                detail=(
                    "Não é possível concluir a tarefa enquanto houver dependências pendentes: "
                    + ", ".join(str(task_id) for task_id in unresolved_dependencies)
                ),
            )


def _apply_task_update(
    repo: TaskRepository,
    task_obj: TaskModel,
    task_in: TaskUpdate,
    current_user: User,
) -> Task:
    update_data = task_in.model_dump(exclude_unset=True)
    previous_status = task_obj.status

    if "status" in update_data and update_data["status"] is not None:
        _validate_task_status_transition(task_obj, update_data["status"])

    for field, value in update_data.items():
        setattr(task_obj, field, value)

    if "status" in update_data and update_data["status"] is not None:
        new_status = update_data["status"]
        if new_status == TaskStatus.concluida:
            task_obj.completed_at = datetime.now(UTC)
        elif previous_status == TaskStatus.concluida and new_status != TaskStatus.concluida:
            task_obj.completed_at = None

        repo.add_audit(
            user_id=current_user.id,
            task=task_obj,
            action="status_changed",
            details="Status da tarefa alterado via API",
            old_value=previous_status.value,
            new_value=new_status.value,
        )

    repo.db.commit()
    repo.db.refresh(task_obj)
    _emit_task_deadline_alert(task_obj)

    if "status" in update_data and update_data["status"] is not None:
        new_status = update_data["status"]
        record_task_transition(previous_status.value, new_status.value, "success")
        publish_realtime_event(
            tenant_id=current_user.tenant_id,
            event_type="task.completed" if new_status == TaskStatus.concluida else "task.status.changed",
            payload={
                "task_id": task_obj.id,
                "process_id": task_obj.process_id,
                "from_status": previous_status.value,
                "to_status": new_status.value,
            },
        )

    return _serialize_task(task_obj)


@router.post("/", response_model=Task)
def create_task(
    *,
    db: Session = Depends(deps.get_db),
    task_in: TaskCreate,
    current_user: User = Depends(deps.get_current_internal_user),
):
    repo = TaskRepository(db, current_user.tenant_id)
    db_obj = repo.create({**task_in.model_dump(), "created_by_user_id": current_user.id})
    repo.add_audit(
        user_id=current_user.id,
        task=db_obj,
        action="created",
        details="Tarefa criada via API",
    )
    db.commit()
    db.refresh(db_obj)
    _emit_task_deadline_alert(db_obj)
    publish_realtime_event(
        tenant_id=current_user.tenant_id,
        event_type="task.created",
        payload={"task_id": db_obj.id, "process_id": db_obj.process_id, "status": db_obj.status.value},
    )
    return _serialize_task(db_obj)


@router.get("/", response_model=list[Task])
def get_tasks(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    process_id: Optional[int] = None,
    current_user: User = Depends(deps.get_current_internal_user),
):
    repo = TaskRepository(db, current_user.tenant_id)
    if process_id:
        tasks = repo.list_by_process(process_id, skip=skip, limit=limit)
    else:
        tasks = repo.list(skip=skip, limit=limit)
    return [_serialize_task(t) for t in tasks]


@router.get("/{id}", response_model=Task)
def get_task(
    id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_internal_user),
):
    repo = TaskRepository(db, current_user.tenant_id)
    return _serialize_task(repo.get_or_404(id, detail="Task not found"))


@router.patch("/{id}", response_model=Task)
def update_task(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    task_in: TaskUpdate,
    current_user: User = Depends(deps.get_current_internal_user),
):
    repo = TaskRepository(db, current_user.tenant_id)
    task_obj = repo.get_or_404(id, detail="Task not found")
    return _apply_task_update(repo, task_obj, task_in, current_user)


@router.patch("/{id}/status", response_model=Task)
@router.put("/{id}/status", response_model=Task)
def update_task_status(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    status_in: TaskStatusUpdate,
    current_user: User = Depends(deps.get_current_internal_user),
):
    repo = TaskRepository(db, current_user.tenant_id)
    task_obj = repo.get_or_404(id, detail="Task not found")
    return _apply_task_update(repo, task_obj, TaskUpdate(status=status_in.status), current_user)
