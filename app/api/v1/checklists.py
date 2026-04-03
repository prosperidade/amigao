"""
Checklists API — Sprint 2

Endpoints montados sob /processes/{process_id}/checklist:

  GET    /processes/{id}/checklist              — retorna checklist com status por item
  POST   /processes/{id}/checklist/generate     — gera ou regenera checklist do processo
  PATCH  /processes/{id}/checklist/items/{iid}  — atualiza status de um item
  GET    /processes/{id}/checklist/gaps         — retorna apenas itens pendentes (gaps)
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.checklist_template import ProcessChecklist
from app.models.process import Process
from app.models.user import User
from app.services.checklist_engine import (
    get_checklist_status,
    get_or_create_checklist,
    mark_item_pending,
    mark_item_received,
    mark_item_waived,
    regenerate_checklist,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_process_or_404(db: Session, process_id: int, tenant_id: int) -> Process:
    process = (
        db.query(Process)
        .filter(Process.id == process_id, Process.tenant_id == tenant_id)
        .first()
    )
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    return process


def _get_checklist_or_404(db: Session, process_id: int) -> ProcessChecklist:
    checklist = (
        db.query(ProcessChecklist)
        .filter(ProcessChecklist.process_id == process_id)
        .first()
    )
    if not checklist:
        raise HTTPException(
            status_code=404,
            detail="Checklist não encontrado. Use POST /generate para criar.",
        )
    return checklist


def _serialize_checklist(checklist: ProcessChecklist, include_status: bool = True) -> dict:
    data = {
        "id": checklist.id,
        "process_id": checklist.process_id,
        "template_id": checklist.template_id,
        "items": checklist.items or [],
        "completed_at": checklist.completed_at,
        "created_at": checklist.created_at,
        "updated_at": checklist.updated_at,
    }
    if include_status:
        s = get_checklist_status(checklist)
        data["summary"] = {
            "total": s.total_items,
            "received": s.received,
            "pending": s.pending,
            "waived": s.waived,
            "completion_pct": s.completion_pct,
            "has_required_gaps": s.has_required_gaps,
        }
    return data


# ---------------------------------------------------------------------------
# GET /processes/{process_id}/checklist
# ---------------------------------------------------------------------------

@router.get("/{process_id}/checklist")
def get_checklist(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Retorna o checklist do processo com status por item e resumo de progresso."""
    _get_process_or_404(db, process_id, current_user.tenant_id)
    checklist = _get_checklist_or_404(db, process_id)
    return _serialize_checklist(checklist)


# ---------------------------------------------------------------------------
# POST /processes/{process_id}/checklist/generate
# ---------------------------------------------------------------------------

@router.post("/{process_id}/checklist/generate", status_code=status.HTTP_201_CREATED)
def generate_checklist(
    process_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """
    Gera o checklist do processo baseado no demand_type.
    Se já existir e force=False, retorna o existente.
    Se force=True, remove e recria do zero.
    """
    process = _get_process_or_404(db, process_id, current_user.tenant_id)
    demand_type = process.demand_type.value if process.demand_type else None

    if force:
        checklist = regenerate_checklist(db, process_id, current_user.tenant_id, demand_type)
    else:
        checklist = get_or_create_checklist(db, process_id, current_user.tenant_id, demand_type)

    db.commit()
    db.refresh(checklist)
    logger.info("Checklist gerado: process_id=%s demand_type=%s itens=%s", process_id, demand_type, len(checklist.items or []))
    return _serialize_checklist(checklist)


# ---------------------------------------------------------------------------
# PATCH /processes/{process_id}/checklist/items/{item_id}
# ---------------------------------------------------------------------------

@router.patch("/{process_id}/checklist/items/{item_id}")
def update_checklist_item(
    process_id: int,
    item_id: str,
    action: str = Body(..., description="'received' | 'waived' | 'pending'", embed=True),
    document_id: Optional[int] = Body(None, embed=True),
    waiver_reason: Optional[str] = Body(None, embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """
    Atualiza o status de um item do checklist.

    - action=received  → marca como recebido (document_id opcional)
    - action=waived    → dispensa o item (waiver_reason obrigatório)
    - action=pending   → reverte para pendente
    """
    _get_process_or_404(db, process_id, current_user.tenant_id)
    checklist = _get_checklist_or_404(db, process_id)

    if action == "received":
        ok = mark_item_received(checklist, item_id, document_id)
    elif action == "waived":
        if not waiver_reason:
            raise HTTPException(status_code=422, detail="waiver_reason obrigatório ao dispensar item.")
        ok = mark_item_waived(checklist, item_id, waiver_reason)
    elif action == "pending":
        ok = mark_item_pending(checklist, item_id)
    else:
        raise HTTPException(status_code=422, detail="action deve ser 'received', 'waived' ou 'pending'.")

    if not ok:
        raise HTTPException(status_code=404, detail=f"Item '{item_id}' não encontrado no checklist.")

    db.add(checklist)
    db.commit()
    db.refresh(checklist)
    return _serialize_checklist(checklist)


# ---------------------------------------------------------------------------
# GET /processes/{process_id}/checklist/gaps
# ---------------------------------------------------------------------------

@router.get("/{process_id}/checklist/gaps")
def get_checklist_gaps(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """
    Retorna apenas os itens pendentes (gaps) do checklist, com indicação
    de quais são obrigatórios e há quantos dias estão sem documento.
    """
    _get_process_or_404(db, process_id, current_user.tenant_id)
    checklist = _get_checklist_or_404(db, process_id)
    status_obj = get_checklist_status(checklist)

    return {
        "process_id": process_id,
        "has_required_gaps": status_obj.has_required_gaps,
        "gaps": [
            {
                "item_id": g.item_id,
                "label": g.label,
                "doc_type": g.doc_type,
                "category": g.category,
                "required": g.required,
                "days_pending": g.days_pending,
                "alert": g.required and (g.days_pending or 0) >= 5,
            }
            for g in status_obj.gaps
        ],
    }
