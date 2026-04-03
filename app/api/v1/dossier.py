"""
Dossier API — Sprint 3

  GET  /processes/{id}/dossier          — retorna dossiê agregado do processo
  GET  /processes/{id}/inconsistencies  — lista inconsistências técnicas
  POST /processes/{id}/dossier/refresh  — força re-análise (alias GET)
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.checklist_template import ProcessChecklist
from app.models.document import Document
from app.models.process import Process
from app.models.property import Property
from app.models.user import User
from app.services.dossier import ProcessDossier, generate_dossier, validate_technical_consistency

router = APIRouter()
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


def _serialize_dossier(d: ProcessDossier) -> dict:
    return {
        "process_id": d.process_id,
        "process": d.process,
        "client": d.client,
        "property": d.property,
        "documents": d.documents,
        "checklist_summary": d.checklist_summary,
        "tasks_summary": d.tasks_summary,
        "previous_processes": d.previous_processes,
        "inconsistencies": [
            {
                "code": i.code,
                "severity": i.severity,
                "title": i.title,
                "description": i.description,
                "field": i.field,
            }
            for i in d.inconsistencies
        ],
    }


# ---------------------------------------------------------------------------
# GET /processes/{process_id}/dossier
# ---------------------------------------------------------------------------

@router.get("/{process_id}/dossier")
def get_dossier(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Retorna o dossiê técnico completo do processo."""
    _get_process_or_404(db, process_id, current_user.tenant_id)
    dossier = generate_dossier(db, process_id, current_user.tenant_id)
    logger.info("Dossiê gerado: process_id=%s inconsistencias=%s", process_id, len(dossier.inconsistencies))
    return _serialize_dossier(dossier)


# ---------------------------------------------------------------------------
# GET /processes/{process_id}/inconsistencies
# ---------------------------------------------------------------------------

@router.get("/{process_id}/inconsistencies")
def get_inconsistencies(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Retorna apenas as inconsistências técnicas detectadas no processo."""
    process = _get_process_or_404(db, process_id, current_user.tenant_id)

    prop = (
        db.query(Property).filter(Property.id == process.property_id).first()
        if process.property_id else None
    )
    documents = (
        db.query(Document)
        .filter(Document.process_id == process_id, Document.tenant_id == current_user.tenant_id)
        .all()
    )
    checklist = (
        db.query(ProcessChecklist)
        .filter(ProcessChecklist.process_id == process_id)
        .first()
    )

    issues = validate_technical_consistency(process, prop, documents, checklist)
    return {
        "process_id": process_id,
        "total": len(issues),
        "errors": sum(1 for i in issues if i.severity == "error"),
        "warnings": sum(1 for i in issues if i.severity == "warning"),
        "inconsistencies": [
            {
                "code": i.code,
                "severity": i.severity,
                "title": i.title,
                "description": i.description,
                "field": i.field,
            }
            for i in issues
        ],
    }


# ---------------------------------------------------------------------------
# POST /processes/{process_id}/dossier/refresh
# ---------------------------------------------------------------------------

@router.post("/{process_id}/dossier/refresh")
def refresh_dossier(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Força re-análise do dossiê (equivale ao GET, mas semântica de ação)."""
    _get_process_or_404(db, process_id, current_user.tenant_id)
    dossier = generate_dossier(db, process_id, current_user.tenant_id)
    return _serialize_dossier(dossier)
