"""Endpoints REST regulatórios — Sprint A1 Tarefa D2.

Read-only nesta sprint:

* ``GET  /processes/{process_id}/diagnoses``                 (lista versões, mais nova primeiro)
* ``GET  /processes/{process_id}/diagnoses/{version}``       (versão específica)
* ``GET  /properties/{property_id}/issues?status=...``       (lista issues, filtro por status)

Auth: perfil ``internal``. Tenant isolation aplicada em todas as queries.

POST/PUT/PATCH/DELETE ficam para A2/Y (quando o agente ``auditor_imovel``
e o consultor passarem a escrever).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.process import Process
from app.models.property import Property
from app.models.regulatory import RegulatoryDiagnosis, RegulatoryIssue
from app.models.user import User
from app.schemas.regulatory import (
    IssueStatusFilter,
    RegulatoryDiagnosisOut,
    RegulatoryIssueOut,
)

# Routers separados — segue padrão do app/api/v1/workflows.py com 2 prefixes
process_router = APIRouter()
property_router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_process_or_404(db: Session, process_id: int, tenant_id: int) -> Process:
    process = (
        db.query(Process)
        .filter(Process.id == process_id, Process.tenant_id == tenant_id)
        .first()
    )
    if process is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    return process


def _get_property_or_404(db: Session, property_id: int, tenant_id: int) -> Property:
    prop = (
        db.query(Property)
        .filter(Property.id == property_id, Property.tenant_id == tenant_id)
        .first()
    )
    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imóvel não encontrado")
    return prop


# ---------------------------------------------------------------------------
# /processes/{process_id}/diagnoses
# ---------------------------------------------------------------------------

@process_router.get("/{process_id}/diagnoses", response_model=list[RegulatoryDiagnosisOut])
def list_diagnoses(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> list[RegulatoryDiagnosis]:
    """Lista as versões de diagnóstico regulatório de um processo, mais nova primeiro."""
    _get_process_or_404(db, process_id, current_user.tenant_id)
    return (
        db.query(RegulatoryDiagnosis)
        .filter(
            RegulatoryDiagnosis.process_id == process_id,
            RegulatoryDiagnosis.tenant_id == current_user.tenant_id,
        )
        .order_by(RegulatoryDiagnosis.version.desc())
        .all()
    )


@process_router.get(
    "/{process_id}/diagnoses/{version}",
    response_model=RegulatoryDiagnosisOut,
)
def get_diagnosis_version(
    process_id: int,
    version: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> RegulatoryDiagnosis:
    """Retorna a versão específica do diagnóstico de um processo."""
    _get_process_or_404(db, process_id, current_user.tenant_id)
    diag = (
        db.query(RegulatoryDiagnosis)
        .filter(
            RegulatoryDiagnosis.process_id == process_id,
            RegulatoryDiagnosis.version == version,
            RegulatoryDiagnosis.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if diag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Versão {version} de diagnóstico não encontrada para este processo",
        )
    return diag


# ---------------------------------------------------------------------------
# /properties/{property_id}/issues
# ---------------------------------------------------------------------------

@property_router.get("/{property_id}/issues", response_model=list[RegulatoryIssueOut])
def list_property_issues(
    property_id: int,
    status_filter: IssueStatusFilter = Query(
        "open",
        alias="status",
        description="open=resolved_at is null, resolved=resolved_at is not null, all=tudo",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> list[RegulatoryIssue]:
    """Lista issues regulatórios do imóvel, filtrável por status."""
    _get_property_or_404(db, property_id, current_user.tenant_id)
    query = (
        db.query(RegulatoryIssue)
        .filter(
            RegulatoryIssue.property_id == property_id,
            RegulatoryIssue.tenant_id == current_user.tenant_id,
        )
    )
    if status_filter == "open":
        query = query.filter(RegulatoryIssue.resolved_at.is_(None))
    elif status_filter == "resolved":
        query = query.filter(RegulatoryIssue.resolved_at.is_not(None))
    # "all" → sem filtro adicional
    return query.order_by(RegulatoryIssue.detected_at.desc()).all()
