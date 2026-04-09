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

    model_config = ConfigDict(from_attributes=True)


class KanbanColumn(BaseModel):
    macroetapa: str
    label: str
    count: int
    cards: list[KanbanProcessCard]


class KanbanResponse(BaseModel):
    columns: list[KanbanColumn]
    total_active: int
