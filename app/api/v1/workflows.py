"""
Workflows API — Sprint 3

  GET  /workflows/templates              — lista templates disponíveis
  GET  /workflows/templates/{demand_type} — detalhe do template
  POST /processes/{id}/apply-workflow    — aplica trilha ao processo (cria tarefas)
  GET  /processes/{id}/workflow-status   — status da trilha atual
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.process import Process
from app.models.user import User
from app.services.workflow_engine import (
    WorkflowStatus,
    WorkflowStep,
    apply_workflow_template,
    get_workflow_status,
    list_templates,
)

router = APIRouter()          # montado em /workflows
process_router = APIRouter()  # montado em /processes
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_process_or_404(db: Session, process_id: int, tenant_id: int) -> Process:
    process = db.query(Process).filter(
        Process.id == process_id,
        Process.tenant_id == tenant_id,
    ).first()
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    return process


def _serialize_step(step: WorkflowStep) -> dict:
    return {
        "order": step.order,
        "title": step.title,
        "description": step.description,
        "task_type": step.task_type,
        "estimated_days": step.estimated_days,
        "depends_on": step.depends_on,
        "task_id": step.task_id,
        "task_status": step.task_status,
        "completed_at": step.completed_at,
        "due_date": step.due_date,
    }


def _serialize_workflow_status(ws: WorkflowStatus) -> dict:
    return {
        "process_id": ws.process_id,
        "template_id": ws.template_id,
        "template_name": ws.template_name,
        "demand_type": ws.demand_type,
        "total_steps": ws.total_steps,
        "completed_steps": ws.completed_steps,
        "completion_pct": ws.completion_pct,
        "is_applied": ws.is_applied,
        "current_step": _serialize_step(ws.current_step) if ws.current_step else None,
        "next_steps": [_serialize_step(s) for s in ws.next_steps],
        "all_steps": [_serialize_step(s) for s in ws.all_steps],
    }


# ---------------------------------------------------------------------------
# GET /workflows/templates
# ---------------------------------------------------------------------------

@router.get("/templates")
def list_workflow_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Lista todos os templates de trilha regulatória disponíveis para o tenant."""
    templates = list_templates(db, current_user.tenant_id)
    return [
        {
            "id": t.id,
            "demand_type": t.demand_type,
            "name": t.name,
            "description": t.description,
            "steps_count": len(t.steps or []),
            "is_active": t.is_active,
        }
        for t in templates
    ]


# ---------------------------------------------------------------------------
# GET /workflows/templates/{demand_type}
# ---------------------------------------------------------------------------

@router.get("/templates/{demand_type}")
def get_workflow_template(
    demand_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Retorna o template completo de trilha para um tipo de demanda."""
    from app.models.workflow_template import WorkflowTemplate
    template = (
        db.query(WorkflowTemplate)
        .filter(
            WorkflowTemplate.demand_type == demand_type,
            WorkflowTemplate.is_active == True,
            (WorkflowTemplate.tenant_id == current_user.tenant_id) |
            (WorkflowTemplate.tenant_id == None),
        )
        .order_by(WorkflowTemplate.tenant_id.desc().nullslast())
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail=f"Template para '{demand_type}' não encontrado.")
    return {
        "id": template.id,
        "demand_type": template.demand_type,
        "name": template.name,
        "description": template.description,
        "steps": template.steps,
        "is_active": template.is_active,
    }


# ---------------------------------------------------------------------------
# POST /processes/{process_id}/apply-workflow
# ---------------------------------------------------------------------------

@process_router.post("/{process_id}/apply-workflow", status_code=status.HTTP_201_CREATED)
def apply_workflow(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """
    Aplica a trilha regulatória ao processo baseada no demand_type.
    Cria as tarefas do fluxo na ordem correta em status 'backlog'.
    """
    process = _get_process_or_404(db, process_id, current_user.tenant_id)
    demand_type = process.demand_type.value if process.demand_type else None

    if not demand_type:
        raise HTTPException(
            status_code=422,
            detail="O processo não possui demand_type definido. Use o intake para classificar primeiro.",
        )

    tasks = apply_workflow_template(
        db=db,
        process_id=process_id,
        tenant_id=current_user.tenant_id,
        demand_type=demand_type,
        created_by_user_id=current_user.id,
    )

    if not tasks:
        raise HTTPException(
            status_code=404,
            detail=f"Nenhum template de trilha encontrado para o tipo '{demand_type}'.",
        )

    db.commit()
    logger.info(
        "Trilha aplicada: process_id=%s demand_type=%s tarefas=%s",
        process_id, demand_type, len(tasks),
    )

    return {
        "message": f"Trilha '{demand_type}' aplicada com sucesso.",
        "tasks_created": len(tasks),
        "task_ids": [t.id for t in tasks],
    }


# ---------------------------------------------------------------------------
# GET /processes/{process_id}/workflow-status
# ---------------------------------------------------------------------------

@process_router.get("/{process_id}/workflow-status")
def workflow_status(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Retorna o status atual da trilha regulatória do processo."""
    _get_process_or_404(db, process_id, current_user.tenant_id)
    ws = get_workflow_status(db, process_id, current_user.tenant_id)
    return _serialize_workflow_status(ws)
