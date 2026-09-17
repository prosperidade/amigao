"""Legacy entry adapter for the persisted ADR-069 dependency scheduler."""

from app.agents.base import AgentContext, AgentResult
from app.services.connected_agents import CHAINS

INTENT_TO_CHAIN = {
    "analyze_property": "diagnostico_completo",
    "generate_proposal": "gerar_proposta",
    "generate_document": "gerar_documento",
    "check_regulation": "analise_regulatoria",
    "regulatory_assessment": "enquadramento_regulatorio",
}


def _derivar_macroetapa_chains():
    from app.models.macroetapa import MACROETAPA_AGENT_CHAIN
    return {etapa.value: chain if chain in CHAINS else None for etapa, chain in MACROETAPA_AGENT_CHAIN.items()}


MACROETAPA_CHAINS = _derivar_macroetapa_chains()


class OrchestratorAgent:
    @staticmethod
    def list_chains():
        return CHAINS.copy()

    @staticmethod
    def execute_chain(chain_name: str, ctx: AgentContext, *, stop_on_review: bool = True) -> list[AgentResult]:
        """Compatibility projection; stop_on_review=False cannot bypass the gate."""
        from app.services.connected_agents import legacy_step_result, resume_execution, start_execution
        execution = start_execution(ctx.session, ctx.tenant_id, ctx.user_id, ctx.process_id, chain_name)
        execution = resume_execution(ctx.session, ctx.tenant_id, ctx.user_id, execution.id)
        return [AgentResult(**legacy_step_result(ctx.session, execution, step)) for step in execution.steps]

    @staticmethod
    def route(intent: str, ctx: AgentContext) -> list[AgentResult]:
        if intent not in INTENT_TO_CHAIN:
            raise ValueError(f"Intent desconhecido ou desativado: {intent}")
        return OrchestratorAgent.execute_chain(INTENT_TO_CHAIN[intent], ctx)
