"""
OrcamentoAgent — o passo ``orcamento`` da cadeia ``gerar_proposta`` (ADR-074, ADR-081).

O orçamento é um contrato determinístico sobre a Rota assinada, com os métodos e preços do
tenant: quem calcula é ``app/services/comercial/orcamento.py``, chamado pelo agendador do
ADR-069 (``connected_agents`` desvia os agentes comerciais para ``comercial/cadeia.py``). Esta
classe existe só para o registro do agente e o tipo do job.

A estimativa por regras de código (``_estimate_by_rules``, faixas fixas por demanda) e o
enriquecimento por LLM saíram com a dívida #284: preço de código não é preço do escritório.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentRegistry, BaseAgent
from app.models.ai_job import AIJobType


@AgentRegistry.register
class OrcamentoAgent(BaseAgent):
    name = "orcamento"
    description = "Orçamento da Rota assinada com os métodos e preços do tenant (determinístico)"
    job_type = AIJobType.generate_proposal
    prompt_slugs: list[str] = []

    def validate_preconditions(self) -> None:
        if not self.ctx.process_id:
            raise ValueError("process_id é necessário para o orçamento")

    def execute(self) -> dict[str, Any]:
        # Nunca chamado pelo agendador: o passo é resolvido em comercial/cadeia.py. Se alguém
        # chamar direto, recusa em vez de inventar preço.
        raise RuntimeError("O orçamento é calculado por app/services/comercial/orcamento.py "
                           "(métodos e preços do tenant); não há estimativa de código (ADR-081).")

    def _fallback_prompts(self) -> dict[str, str]:
        return {}
