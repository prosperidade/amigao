"""
Sistema de Agentes IA — Amigao do Meio Ambiente.

Re-exports das classes publicas e registro de todos os agentes.
"""

from app.agents.base import AgentContext, AgentRegistry, AgentResult, BaseAgent
from app.agents.events import emit_agent_event
from app.agents.orchestrator import CHAINS, INTENT_TO_CHAIN, OrchestratorAgent
from app.agents.validators import OutputValidationPipeline

# Importar todos os agentes para que se registrem via @AgentRegistry.register
from app.agents import (  # noqa: F401
    acompanhamento,
    atendimento,
    diagnostico,
    extrator,
    financeiro,
    legislacao,
    marketing,
    orcamento,
    redator,
    vigia,
)

__all__ = [
    "AgentContext",
    "AgentRegistry",
    "AgentResult",
    "BaseAgent",
    "CHAINS",
    "INTENT_TO_CHAIN",
    "OrchestratorAgent",
    "OutputValidationPipeline",
    "emit_agent_event",
]
