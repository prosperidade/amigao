"""Schemas Pydantic para o feedback loop do AtendimentoAgent — Sprint A1 Tarefa E."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.process import DemandType


class ClassifyDemandRequest(BaseModel):
    """Body de ``POST /processes/{id}/classify``."""

    demand_type: DemandType = Field(..., description="Classificação canônica decidida pelo consultor")


class ClassifyDemandResponse(BaseModel):
    """Resposta de ``POST /processes/{id}/classify``."""

    process_id: int
    previous_demand_type: str | None
    new_demand_type: str
    feedback_logged: bool
    feedback_id: int | None
    ai_demand_type: str | None
    diverged_from_ai: bool


class IntakeFeedbackOut(BaseModel):
    """Saída de leitura de IntakeClassificationFeedback."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    process_id: int
    intake_draft_id: int | None
    ai_demand_type: str | None
    ai_confidence: float | None
    ai_run_id: int | None
    corrected_demand_type: str
    corrected_by_user_id: int | None
    corrected_at: datetime


class IntakeFeedbackStats(BaseModel):
    """Métricas agregadas para ``GET /admin/intake-feedback/stats``.

    Convenção:
    * ``total_classifications`` = nº de processos onde houve ao menos um log
      (universo restrito a casos onde houve classificação humana explícita).
    * ``total_corrections`` = nº de processos onde a IA divergiu do humano
      (último log por processo, quando ``ai_demand_type`` ≠ ``corrected_demand_type``).
    * ``accuracy_overall`` = ``1 - corrections/classifications``.
    """

    total_classifications: int
    total_corrections: int
    accuracy_overall: float
    accuracy_by_demand_type: dict[str, float]
    top_corrections: list[tuple[str, int]] = Field(
        default_factory=list,
        description="Pares 'X -> Y' mais frequentes, com contagem (até 10).",
    )
