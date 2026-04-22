"""
AtendimentoAgent — Qualificacao de lead e classificacao de demanda.

Wrapper sobre o servico llm_classifier existente, integrando-o
ao framework de agentes com lifecycle padronizado.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentRegistry, BaseAgent
from app.models.ai_job import AIJobType


@AgentRegistry.register
class AtendimentoAgent(BaseAgent):
    name = "atendimento"
    description = "Qualifica leads, classifica a demanda e apoia o atendimento ao cliente"
    job_type = AIJobType.classify_demand
    prompt_slugs = ["classify_demand_system", "classify_demand_user"]
    palace_room = "agent_atendimento"

    def validate_preconditions(self) -> None:
        desc = self.ctx.metadata.get("description", "")
        if not desc.strip():
            raise ValueError("Campo 'description' obrigatorio em metadata para classificacao")

    def execute(self) -> dict[str, Any]:
        from app.services.llm_classifier import classify_demand_with_llm  # noqa: PLC0415

        result, ai_job_id = classify_demand_with_llm(
            description=self.ctx.metadata.get("description", ""),
            process_type=self.ctx.metadata.get("process_type"),
            urgency=self.ctx.metadata.get("urgency"),
            source_channel=self.ctx.metadata.get("source_channel"),
            tenant_id=self.ctx.tenant_id,
            save_job=False,  # BaseAgent.run() cuida do AIJob
            db_session=self.ctx.session,
        )

        return {
            "demand_type": result.demand_type,
            "demand_label": result.demand_label,
            "confidence": result.confidence,
            "initial_diagnosis": result.initial_diagnosis,
            "required_documents": result.required_documents,
            "suggested_next_steps": result.suggested_next_steps,
            "urgency_flag": result.urgency_flag,
            "relevant_agencies": result.relevant_agencies,
            "checklist_template_demand_type": result.checklist_template_demand_type,
        }

    def _fallback_prompts(self) -> dict[str, str]:
        return {
            "classify_demand_system": (
                "Voce e um especialista em regularizacao ambiental rural brasileira. "
                "Classifique a demanda e retorne JSON estruturado."
            ),
            "classify_demand_user": (
                "Classifique esta demanda ambiental:\n"
                "DESCRICAO: {description}\nCANAL: {channel}\nURGENCIA: {urgency}\n"
                "Retorne apenas o JSON."
            ),
        }
