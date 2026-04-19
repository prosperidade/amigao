"""
Schemas Pydantic para a API de agentes.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AgentRunRequest(BaseModel):
    """Request para executar um agente individual."""

    model_config = ConfigDict(strict=False)

    agent_name: str = Field(..., description="Nome do agente (ex: atendimento, diagnostico)")
    process_id: Optional[int] = Field(None, description="ID do processo (quando aplicavel)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Dados especificos do agente")


class AgentRunResponse(BaseModel):
    """Response de execucao de um agente."""

    model_config = ConfigDict(from_attributes=True)

    success: bool
    data: dict[str, Any]
    confidence: str
    ai_job_id: Optional[int]
    suggestions: list[str]
    requires_review: bool
    agent_name: str
    duration_ms: int
    error: Optional[str] = None


class ChainRunRequest(BaseModel):
    """Request para executar uma chain de agentes."""

    model_config = ConfigDict(strict=False)

    chain_name: str = Field(..., description="Nome da chain (ex: diagnostico_completo, intake)")
    process_id: Optional[int] = Field(None, description="ID do processo")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Dados iniciais da chain")
    stop_on_review: bool = Field(True, description="Parar chain quando agente requer revisao humana")


class ChainRunResponse(BaseModel):
    """Response de execucao de uma chain."""

    model_config = ConfigDict(from_attributes=True)

    chain_name: str
    steps: list[AgentRunResponse]
    completed: bool
    stopped_for_review: bool
    total_duration_ms: int


class AgentInfo(BaseModel):
    """Info basica de um agente registrado."""

    name: str
    description: str


class AsyncTaskResponse(BaseModel):
    """Response para execucao assincrona (Celery)."""

    task_id: str
    status: str = "queued"
    agent_name: Optional[str] = None
    chain_name: Optional[str] = None
    process_id: Optional[int] = None
