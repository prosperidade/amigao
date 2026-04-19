"""
Schemas Pydantic para ProcessDecision.

Regente Sprint E — Aba Decisões.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.macroetapa import Macroetapa
from app.models.process_decision import DecisionStatus, DecisionType


class DecisionCreate(BaseModel):
    """Payload para criar uma nova decisão."""
    macroetapa: Macroetapa
    decision_type: DecisionType
    decision_text: str = Field(..., min_length=3)
    justification: Optional[str] = None
    basis: Optional[dict[str, Any]] = None
    impact: Optional[str] = None
    next_step: Optional[str] = None
    status: DecisionStatus = DecisionStatus.validada
    decided_at: Optional[datetime] = None
    supersedes_decision_id: Optional[int] = None


class DecisionUpdate(BaseModel):
    """Patch parcial de uma decisão existente."""
    decision_text: Optional[str] = Field(None, min_length=3)
    justification: Optional[str] = None
    basis: Optional[dict[str, Any]] = None
    impact: Optional[str] = None
    next_step: Optional[str] = None
    status: Optional[DecisionStatus] = None
    decided_at: Optional[datetime] = None


class DecisionRead(BaseModel):
    """Resposta da API."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    process_id: int
    macroetapa: str
    decision_type: str
    decision_text: str
    justification: Optional[str] = None
    basis: Optional[dict[str, Any]] = None
    decided_by_user_id: Optional[int] = None
    decided_by_user_name: Optional[str] = None  # populado pelo endpoint
    decided_at: Optional[datetime] = None
    impact: Optional[str] = None
    next_step: Optional[str] = None
    status: str
    supersedes_decision_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class DecisionSummary(BaseModel):
    """Resumo curto (QA-013 — exibido no drawer do Quadro)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    macroetapa: str
    decision_type: str
    decision_type_label: str
    decision_text: str
    status: str
    status_label: str
    decided_by_user_name: Optional[str] = None
    decided_at: Optional[datetime] = None
    created_at: datetime
