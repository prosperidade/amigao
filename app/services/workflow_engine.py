"""
Workflow Engine — Sprint 3

Motor de trilha regulatória: aplica templates de etapas a processos,
criando tarefas na ordem correta com dependências.
Lógica pura (sem dependência de request/response HTTP).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.workflow_template import WorkflowTemplate
from app.models.task import Task, TaskStatus, TaskPriority
from app.models.process import Process


# ---------------------------------------------------------------------------
# Estruturas de retorno
# ---------------------------------------------------------------------------

@dataclass
class WorkflowStep:
    order: int
    title: str
    description: str
    task_type: str
    estimated_days: int
    depends_on: List[int]
    task_id: Optional[int]
    task_status: Optional[str]
    completed_at: Optional[datetime]
    due_date: Optional[datetime]


@dataclass
class WorkflowStatus:
    process_id: int
    template_id: Optional[int]
    template_name: Optional[str]
    demand_type: Optional[str]
    total_steps: int
    completed_steps: int
    current_step: Optional[WorkflowStep]
    next_steps: List[WorkflowStep]
    all_steps: List[WorkflowStep]
    completion_pct: float
    is_applied: bool  # se já existe ao menos uma tarefa de workflow neste processo


# ---------------------------------------------------------------------------
# Funções públicas
# ---------------------------------------------------------------------------

def apply_workflow_template(
    db: Session,
    process_id: int,
    tenant_id: int,
    demand_type: Optional[str],
    created_by_user_id: int,
) -> List[Task]:
    """
    Aplica o template de trilha regulatória ao processo, criando tarefas
    na ordem correta. As tarefas são criadas em status 'backlog'.
    Retorna a lista de tarefas criadas.
    """
    template = _find_template(db, tenant_id, demand_type)
    if not template:
        return []

    steps = template.steps or []
    created_tasks: List[Task] = []
    order_to_task_id: dict[int, int] = {}

    # Calcular data de início estimada (hoje)
    base_date = datetime.now(timezone.utc)
    accumulated_days = 0

    for step in sorted(steps, key=lambda s: s["order"]):
        accumulated_days += step.get("estimated_days", 1)
        due = base_date + timedelta(days=accumulated_days)

        # Mapear descrição da dependência para título
        depends_on_orders = step.get("depends_on", [])

        task = Task(
            tenant_id=tenant_id,
            process_id=process_id,
            title=step["title"],
            description=_build_task_description(step, depends_on_orders),
            status=TaskStatus.backlog,
            priority=TaskPriority.medium,
            created_by_user_id=created_by_user_id,
            due_date=due,
        )
        db.add(task)
        db.flush()
        order_to_task_id[step["order"]] = task.id
        created_tasks.append(task)

    return created_tasks


def get_workflow_status(
    db: Session,
    process_id: int,
    tenant_id: int,
) -> WorkflowStatus:
    """
    Retorna o status atual da trilha regulatória do processo.
    Cruza as tarefas existentes do processo com o template esperado.
    """
    process = db.query(Process).filter(
        Process.id == process_id,
        Process.tenant_id == tenant_id,
    ).first()

    demand_type = process.demand_type.value if process and process.demand_type else None
    template = _find_template(db, tenant_id, demand_type)

    tasks = (
        db.query(Task)
        .filter(Task.process_id == process_id, Task.tenant_id == tenant_id)
        .order_by(Task.due_date.asc().nullslast(), Task.id.asc())
        .all()
    )

    # Montar mapa título → task para cruzamento
    title_to_task: dict[str, Task] = {t.title: t for t in tasks}

    steps_data: List[WorkflowStep] = []
    template_id = None
    template_name = None

    if template:
        template_id = template.id
        template_name = template.name
        for step in sorted(template.steps or [], key=lambda s: s["order"]):
            matched_task = title_to_task.get(step["title"])
            steps_data.append(WorkflowStep(
                order=step["order"],
                title=step["title"],
                description=step.get("description", ""),
                task_type=step.get("task_type", ""),
                estimated_days=step.get("estimated_days", 1),
                depends_on=step.get("depends_on", []),
                task_id=matched_task.id if matched_task else None,
                task_status=matched_task.status.value if matched_task else None,
                completed_at=matched_task.completed_at if matched_task else None,
                due_date=matched_task.due_date if matched_task else None,
            ))
    else:
        # Sem template: montar steps a partir das tarefas existentes
        for i, task in enumerate(tasks, start=1):
            steps_data.append(WorkflowStep(
                order=i,
                title=task.title,
                description=task.description or "",
                task_type="",
                estimated_days=0,
                depends_on=[],
                task_id=task.id,
                task_status=task.status.value,
                completed_at=task.completed_at,
                due_date=task.due_date,
            ))

    total = len(steps_data)
    completed = sum(1 for s in steps_data if s.task_status == "concluida")
    completion_pct = round(completed / total * 100, 1) if total > 0 else 0.0

    current_step: Optional[WorkflowStep] = None
    next_steps: List[WorkflowStep] = []
    for step in steps_data:
        if step.task_status not in ("concluida", "cancelada", None):
            if current_step is None:
                current_step = step
            else:
                next_steps.append(step)
        elif step.task_status is None:
            next_steps.append(step)

    is_applied = any(s.task_id is not None for s in steps_data)

    return WorkflowStatus(
        process_id=process_id,
        template_id=template_id,
        template_name=template_name,
        demand_type=demand_type,
        total_steps=total,
        completed_steps=completed,
        current_step=current_step,
        next_steps=next_steps[:3],  # só as 3 próximas
        all_steps=steps_data,
        completion_pct=completion_pct,
        is_applied=is_applied,
    )


def list_templates(db: Session, tenant_id: int) -> List[WorkflowTemplate]:
    """Lista todos os templates disponíveis para o tenant (globais + próprios)."""
    return (
        db.query(WorkflowTemplate)
        .filter(
            WorkflowTemplate.is_active == True,
            (WorkflowTemplate.tenant_id == tenant_id) |
            (WorkflowTemplate.tenant_id == None),
        )
        .order_by(WorkflowTemplate.demand_type)
        .all()
    )


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _find_template(
    db: Session,
    tenant_id: int,
    demand_type: Optional[str],
) -> Optional[WorkflowTemplate]:
    if not demand_type:
        return None
    return (
        db.query(WorkflowTemplate)
        .filter(
            WorkflowTemplate.demand_type == demand_type,
            WorkflowTemplate.is_active == True,
            (WorkflowTemplate.tenant_id == tenant_id) |
            (WorkflowTemplate.tenant_id == None),
        )
        .order_by(WorkflowTemplate.tenant_id.desc().nullslast())
        .first()
    )


def _build_task_description(step: dict, depends_on_orders: List[int]) -> str:
    desc = step.get("description", "")
    if depends_on_orders:
        dep_str = ", ".join(f"etapa {o}" for o in depends_on_orders)
        desc = f"{desc}\n\nDependência(s): {dep_str}."
    return desc.strip()
