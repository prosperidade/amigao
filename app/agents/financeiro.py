"""
FinanceiroAgent — Analise financeira, projecao de custos, acompanhamento.

Agrega dados de propostas, contratos e custos de IA para produzir
analise financeira do processo/tenant.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func

from app.agents.base import AgentRegistry, BaseAgent
from app.agents.validators import OutputValidationPipeline
from app.models.ai_job import AIJob, AIJobType


@AgentRegistry.register
class FinanceiroAgent(BaseAgent):
    name = "financeiro"
    description = "Analise financeira, projecao de custos, acompanhamento de pagamentos"
    job_type = AIJobType.analise_financeira
    prompt_slugs = ["financeiro_system", "financeiro_user"]
    palace_room = "agent_financeiro"

    def execute(self) -> dict[str, Any]:
        from app.core.config import settings  # noqa: PLC0415

        financial_data = self._aggregate_financial_data()

        if not settings.ai_configured or not self.ctx.metadata.get("generate_insights", False):
            return financial_data

        # Enriquecer com insights LLM
        system_prompt = self.get_prompt("financeiro_system")
        user_prompt = self.get_prompt("financeiro_user", {
            "financial_data": json.dumps(financial_data, ensure_ascii=False, default=str),
        })

        response = self.call_llm(user_prompt, system=system_prompt)
        parsed = OutputValidationPipeline.parse_llm_json(response.content)

        financial_data["insights"] = parsed.get("insights", [])
        financial_data["recommendations"] = parsed.get("recommendations", [])
        financial_data["confidence"] = parsed.get("confidence", "medium")

        return financial_data

    def _aggregate_financial_data(self) -> dict[str, Any]:
        """Agrega dados financeiros de propostas, contratos e custos de IA."""
        from app.models.contract import Contract  # noqa: PLC0415
        from app.models.proposal import Proposal  # noqa: PLC0415

        filters = [AIJob.tenant_id == self.ctx.tenant_id]
        proposal_filters = [Proposal.tenant_id == self.ctx.tenant_id]
        contract_filters = [Contract.tenant_id == self.ctx.tenant_id]

        if self.ctx.process_id:
            filters.append(AIJob.entity_type == "process")
            filters.append(AIJob.entity_id == self.ctx.process_id)
            proposal_filters.append(Proposal.process_id == self.ctx.process_id)
            contract_filters.append(Contract.process_id == self.ctx.process_id)

        # Custos de IA
        ai_cost = (
            self.ctx.session.query(func.coalesce(func.sum(AIJob.cost_usd), 0.0))
            .filter(*filters)
            .scalar()
        ) or 0.0

        ai_job_count = (
            self.ctx.session.query(func.count(AIJob.id))
            .filter(*filters)
            .scalar()
        ) or 0

        # Propostas
        proposals = self.ctx.session.query(Proposal).filter(*proposal_filters).all()
        proposals_data = [
            {
                "id": p.id,
                "title": p.title,
                "total_value": p.total_value,
                "status": p.status.value if p.status else None,
            }
            for p in proposals
        ]

        # Contratos
        contracts = self.ctx.session.query(Contract).filter(*contract_filters).all()
        contracts_data = [
            {
                "id": c.id,
                "title": c.title,
                "status": c.status.value if c.status else None,
            }
            for c in contracts
        ]

        # Totais
        total_proposed = sum(p.total_value or 0 for p in proposals)
        accepted_value = sum(p.total_value or 0 for p in proposals if p.status and p.status.value == "accepted")

        return {
            "ai_cost_usd": float(ai_cost),
            "ai_job_count": ai_job_count,
            "proposals": proposals_data,
            "proposals_count": len(proposals),
            "total_proposed_value": total_proposed,
            "accepted_value": accepted_value,
            "contracts": contracts_data,
            "contracts_count": len(contracts),
            "scope": "process" if self.ctx.process_id else "tenant",
        }

    def _fallback_prompts(self) -> dict[str, str]:
        return {
            "financeiro_system": (
                "Voce e um analista financeiro de consultoria ambiental. "
                "Analise os dados financeiros e forneca insights e recomendacoes. "
                "Retorne APENAS JSON com: insights (list[str]), "
                "recommendations (list[str]), confidence (high|medium|low)."
            ),
            "financeiro_user": (
                "Analise financeira:\n\n"
                "DADOS: {financial_data}\n\n"
                "Forneca insights e recomendacoes financeiras."
            ),
        }
