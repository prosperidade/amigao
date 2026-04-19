"""Schemas Pydantic para macroetapas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.macroetapa import Macroetapa


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class MacroetapaAdvanceRequest(BaseModel):
    macroetapa: Macroetapa


class ActionToggleRequest(BaseModel):
    action_id: str
    completed: bool


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class ActionItem(BaseModel):
    id: str
    label: str
    completed: bool
    completed_at: Optional[str] = None
    agent_suggestion: Optional[str] = None
    # Regente Cam3 CAM3WS-005 — validação humana
    needs_human_validation: bool = False
    validated_at: Optional[str] = None
    validated_by_user_id: Optional[int] = None


class ActionValidateRequest(BaseModel):
    action_id: str


class MacroetapaStep(BaseModel):
    macroetapa: str
    label: str
    order: int
    status: str  # pending | active | completed
    completion_pct: float
    actions: list[ActionItem]
    agent_chain: Optional[str] = None


class MacroetapaStatusResponse(BaseModel):
    current_macroetapa: Optional[str] = None
    current_label: Optional[str] = None
    current_index: int
    total_steps: int
    next_action: Optional[str] = None
    steps: list[MacroetapaStep]


class MacroetapaChecklistResponse(BaseModel):
    id: int
    process_id: int
    macroetapa: str
    actions: list[ActionItem]
    completion_pct: float

    model_config = ConfigDict(from_attributes=True)


# CAM3FT-005 — Resposta do gate de avanço
class CanAdvanceResponse(BaseModel):
    can_advance: bool
    current_macroetapa: Optional[str] = None
    current_state: Optional[str] = None
    next_macroetapa: Optional[str] = None
    blockers: list[str] = []
    objective: Optional[str] = None
    expected_outputs: list[str] = []


# CAM3WS-006 — Saídas/artefatos por etapa
class StageOutputCreate(BaseModel):
    macroetapa: Macroetapa
    output_type: str
    title: str
    content: Optional[str] = None
    content_data: Optional[dict] = None
    produced_by_agent: Optional[str] = None
    needs_human_validation: bool = False


class StageOutputResponse(BaseModel):
    id: int
    process_id: int
    macroetapa: str
    output_type: str
    title: str
    content: Optional[str] = None
    content_data: Optional[dict] = None
    produced_by_agent: Optional[str] = None
    produced_by_user_id: Optional[int] = None
    needs_human_validation: bool = False
    validated_at: Optional[datetime] = None
    validated_by_user_id: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Kanban card (enriquecido para frontend)
# ---------------------------------------------------------------------------

class KanbanProcessCard(BaseModel):
    id: int
    title: str
    client_name: Optional[str] = None
    property_name: Optional[str] = None
    demand_type: Optional[str] = None
    urgency: Optional[str] = None
    priority: Optional[str] = None
    macroetapa: Optional[str] = None
    macroetapa_label: Optional[str] = None
    macroetapa_completion_pct: float = 0.0
    responsible_user_name: Optional[str] = None
    next_action: Optional[str] = None
    has_alerts: bool = False
    created_at: Optional[datetime] = None

    # Regente Cam1 — Gate de prontidão (CAM1-011)
    entry_type: Optional[str] = None
    has_minimal_base: bool = False
    has_complementary_base: bool = False
    missing_docs_count: int = 0

    # Regente Cam3 — Estado formal da etapa (CAM3FT-004)
    macroetapa_state: Optional[str] = None  # MacroetapaState value
    blockers: list[str] = []

    model_config = ConfigDict(from_attributes=True)


class KanbanColumn(BaseModel):
    macroetapa: str
    label: str
    count: int
    # CAM3FT-003 — counts agregados por estado
    blocked_count: int = 0
    ready_to_advance_count: int = 0
    cards: list[KanbanProcessCard]


class KanbanResponse(BaseModel):
    columns: list[KanbanColumn]
    total_active: int
