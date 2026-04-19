"""
Decisions API — CRUD de decisões críticas do caso (Regente Sprint E).

Rotas montadas sob o prefixo `/processes`:
  GET    /processes/{process_id}/decisions          → lista
  GET    /processes/{process_id}/decisions/latest   → QA-013, resumo da última
  POST   /processes/{process_id}/decisions          → cria
  PATCH  /processes/{process_id}/decisions/{id}     → atualiza
  DELETE /processes/{process_id}/decisions/{id}     → soft delete
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.process import Process as ProcessModel
from app.models.process_decision import (
    DECISION_STATUS_LABELS,
    DECISION_TYPE_LABELS,
    DecisionStatus,
    DecisionType,
    ProcessDecision,
)
from app.models.user import User
from app.schemas.process_decision import (
    DecisionCreate,
    DecisionRead,
    DecisionSummary,
    DecisionUpdate,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _enrich(decision: ProcessDecision, db: Session) -> DecisionRead:
    """Adiciona decided_by_user_name à resposta."""
    user_name: Optional[str] = None
    if decision.decided_by_user_id:
        row = (
            db.query(User.full_name)
            .filter(User.id == decision.decided_by_user_id)
            .first()
        )
        if row:
            user_name = row[0]
    data = DecisionRead.model_validate(decision).model_dump()
    data["decided_by_user_name"] = user_name
    return DecisionRead(**data)


def _require_process(
    db: Session, process_id: int, tenant_id: int
) -> ProcessModel:
    process = (
        db.query(ProcessModel)
        .filter(
            ProcessModel.id == process_id,
            ProcessModel.tenant_id == tenant_id,
            ProcessModel.deleted_at.is_(None),
        )
        .first()
    )
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado")
    return process


def _require_decision(
    db: Session, decision_id: int, process_id: int, tenant_id: int
) -> ProcessDecision:
    decision = (
        db.query(ProcessDecision)
        .filter(
            ProcessDecision.id == decision_id,
            ProcessDecision.process_id == process_id,
            ProcessDecision.tenant_id == tenant_id,
            ProcessDecision.deleted_at.is_(None),
        )
        .first()
    )
    if not decision:
        raise HTTPException(status_code=404, detail="Decisão não encontrada")
    return decision


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{process_id}/decisions", response_model=list[DecisionRead])
def list_decisions(
    process_id: int,
    macroetapa: Optional[str] = Query(None, description="Filtra por macroetapa"),
    decision_type: Optional[str] = Query(None, description="Filtra por tipo"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filtra por status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> list[DecisionRead]:
    """Lista decisões do processo (mais recentes primeiro)."""
    _require_process(db, process_id, current_user.tenant_id)

    q = db.query(ProcessDecision).filter(
        ProcessDecision.process_id == process_id,
        ProcessDecision.tenant_id == current_user.tenant_id,
        ProcessDecision.deleted_at.is_(None),
    )
    if macroetapa:
        q = q.filter(ProcessDecision.macroetapa == macroetapa)
    if decision_type:
        q = q.filter(ProcessDecision.decision_type == decision_type)
    if status_filter:
        q = q.filter(ProcessDecision.status == status_filter)

    decisions = q.order_by(desc(ProcessDecision.created_at)).all()
    return [_enrich(d, db) for d in decisions]


@router.get("/{process_id}/decisions/latest", response_model=Optional[DecisionSummary])
def get_latest_decision(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Optional[DecisionSummary]:
    """QA-013 — resumo da última decisão registrada no caso (p/ drawer do Quadro)."""
    _require_process(db, process_id, current_user.tenant_id)

    row = (
        db.query(ProcessDecision, User.full_name)
        .outerjoin(User, User.id == ProcessDecision.decided_by_user_id)
        .filter(
            ProcessDecision.process_id == process_id,
            ProcessDecision.tenant_id == current_user.tenant_id,
            ProcessDecision.deleted_at.is_(None),
        )
        .order_by(desc(ProcessDecision.created_at))
        .first()
    )
    if not row:
        return None

    decision, user_name = row
    try:
        type_label = DECISION_TYPE_LABELS[DecisionType(decision.decision_type)]
    except ValueError:
        type_label = decision.decision_type
    try:
        status_label = DECISION_STATUS_LABELS[DecisionStatus(decision.status)]
    except ValueError:
        status_label = decision.status

    return DecisionSummary(
        id=decision.id,
        macroetapa=decision.macroetapa,
        decision_type=decision.decision_type,
        decision_type_label=type_label,
        decision_text=decision.decision_text,
        status=decision.status,
        status_label=status_label,
        decided_by_user_name=user_name,
        decided_at=decision.decided_at,
        created_at=decision.created_at,
    )


@router.post(
    "/{process_id}/decisions",
    response_model=DecisionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_decision(
    process_id: int,
    payload: DecisionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> DecisionRead:
    """Cria nova decisão. Consultor é o decided_by por padrão."""
    _require_process(db, process_id, current_user.tenant_id)

    # Se supersedes_decision_id vier preenchido, marca a anterior como substituída.
    if payload.supersedes_decision_id:
        prev = _require_decision(
            db, payload.supersedes_decision_id, process_id, current_user.tenant_id
        )
        prev.status = DecisionStatus.substituida.value

    decision = ProcessDecision(
        tenant_id=current_user.tenant_id,
        process_id=process_id,
        macroetapa=payload.macroetapa.value,
        decision_type=payload.decision_type.value,
        decision_text=payload.decision_text,
        justification=payload.justification,
        basis=payload.basis or {},
        decided_by_user_id=current_user.id,
        decided_at=payload.decided_at or datetime.utcnow(),
        impact=payload.impact,
        next_step=payload.next_step,
        status=payload.status.value,
        supersedes_decision_id=payload.supersedes_decision_id,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)

    logger.info(
        "decision_created process_id=%s decision_id=%s type=%s status=%s",
        process_id, decision.id, decision.decision_type, decision.status,
    )
    return _enrich(decision, db)


@router.patch("/{process_id}/decisions/{decision_id}", response_model=DecisionRead)
def update_decision(
    process_id: int,
    decision_id: int,
    payload: DecisionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> DecisionRead:
    """Atualiza decisão. Edições viram status=revisada salvo se o payload diga outro."""
    decision = _require_decision(db, decision_id, process_id, current_user.tenant_id)

    update_data = payload.model_dump(exclude_unset=True)
    had_meaningful_edit = any(
        k in update_data for k in ("decision_text", "justification", "impact", "next_step", "basis")
    )

    for field, value in update_data.items():
        if field == "status" and value is not None:
            setattr(decision, field, value.value if hasattr(value, "value") else value)
        else:
            setattr(decision, field, value)

    # Se edição significativa sem troca explícita de status → marca como revisada.
    if had_meaningful_edit and "status" not in update_data:
        decision.status = DecisionStatus.revisada.value

    db.commit()
    db.refresh(decision)
    return _enrich(decision, db)


@router.delete(
    "/{process_id}/decisions/{decision_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_decision(
    process_id: int,
    decision_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> None:
    """Soft delete — preserva rastreabilidade histórica."""
    decision = _require_decision(db, decision_id, process_id, current_user.tenant_id)
    decision.deleted_at = datetime.utcnow()
    db.commit()
