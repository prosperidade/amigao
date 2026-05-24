"""
OrchestratorAgent — Roteador deterministico com chains pre-definidas.

O orquestrador NAO usa LLM para decidir roteamento. Ele executa chains
de agentes sequencialmente, acumulando contexto entre eles.
Se um agente retorna requires_review=True, a chain para (human-in-the-loop).
"""

from __future__ import annotations

import logging
from typing import Any

from app.agents.base import AgentContext, AgentRegistry, AgentResult
from app.agents.events import emit_agent_event

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Chains pre-definidas
# ---------------------------------------------------------------------------

CHAINS: dict[str, list[str]] = {
    "intake": ["atendimento"],
    # Onda B Fase 2: auditor_imovel entra entre extrator e legislacao.
    # Sequência decidida no PROMPT_3 (validada pelo FLUXOS_E2E.md):
    #   extrator → auditor_imovel → legislacao → diagnostico.
    # O auditor cruza documentos extraídos (matrícula × CAR × CCIR/etc.) e produz
    # findings/divergências em `chain_data["auditor_imovel"]`. legislacao e
    # diagnostico continuam executando — o `requires_review=True` do auditor
    # é não-bloqueante (ver NON_BLOCKING_REVIEW_AGENTS abaixo).
    "diagnostico_completo": ["extrator", "auditor_imovel", "legislacao", "diagnostico"],
    "gerar_proposta": ["diagnostico", "orcamento"],
    "gerar_documento": ["redator"],
    "analise_regulatoria": ["legislacao"],
    "enquadramento_regulatorio": ["extrator", "legislacao"],
    "analise_financeira": ["financeiro"],
    "monitoramento": ["acompanhamento", "vigia"],
    "marketing_content": ["marketing"],
}

# Agentes cujo `requires_review=True` NÃO interrompe a chain.
#
# Princípio 1 do manifesto ("a IA propõe, o humano decide e assina") continua
# valendo: estes agentes ainda marcam `requires_review=True` e a UI exibe o
# badge. O que muda é só o efeito sobre o pipeline em batch: agentes produtores
# de findings/contexto (não peças formais) seguem alimentando os próximos da
# chain. Sem isso, qualquer chain que inclua `auditor_imovel` quebraria antes
# do `diagnostico` rodar, derrotando o propósito de tê-lo na chain.
#
# Critério para entrar nesta lista: agente cujo output é INSUMO para downstream
# (chain_data), não produto final entregue ao consultor.
NON_BLOCKING_REVIEW_AGENTS: frozenset[str] = frozenset({"auditor_imovel"})


# Mapeamento intent -> chain (usado pela API)
INTENT_TO_CHAIN: dict[str, str] = {
    "classify_demand": "intake",
    "analyze_property": "diagnostico_completo",
    "generate_proposal": "gerar_proposta",
    "generate_document": "gerar_documento",
    "check_regulation": "analise_regulatoria",
    "regulatory_assessment": "enquadramento_regulatorio",
    "monitor_process": "monitoramento",
    "financial_analysis": "analise_financeira",
    "create_content": "marketing_content",
}

# Mapeamento macroetapa -> chain sugerida
MACROETAPA_CHAINS: dict[str, str | None] = {
    "entrada_demanda": "intake",
    "diagnostico_preliminar": "diagnostico_completo",
    "coleta_documental": None,
    "diagnostico_tecnico": "diagnostico_completo",
    "caminho_regulatorio": "enquadramento_regulatorio",
    "orcamento_negociacao": "gerar_proposta",
    "contrato_formalizacao": None,
}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class OrchestratorAgent:
    """Coordenador central que roteia requests para chains de agentes."""

    @staticmethod
    def list_chains() -> dict[str, list[str]]:
        return CHAINS.copy()

    @staticmethod
    def execute_chain(
        chain_name: str,
        ctx: AgentContext,
        *,
        stop_on_review: bool = True,
    ) -> list[AgentResult]:
        """
        Executa uma chain de agentes sequencialmente.

        Cada agente recebe chain_data acumulado dos anteriores.
        Se stop_on_review=True, para quando um agente retorna requires_review=True.
        """
        agent_names = CHAINS.get(chain_name)
        if not agent_names:
            raise ValueError(f"Chain desconhecida: '{chain_name}'. Disponiveis: {list(CHAINS.keys())}")

        results: list[AgentResult] = []
        stopped_for_review = False

        for agent_name in agent_names:
            try:
                agent = AgentRegistry.create(agent_name, ctx)
            except ValueError as exc:
                logger.error("orchestrator: agente '%s' nao encontrado na chain '%s': %s", agent_name, chain_name, exc)
                results.append(AgentResult(
                    success=False,
                    data={},
                    confidence="low",
                    ai_job_id=None,
                    suggestions=[],
                    requires_review=False,
                    agent_name=agent_name,
                    duration_ms=0,
                    error=str(exc),
                ))
                break

            result = agent.run()
            results.append(result)

            # Acumular dados para o proximo agente
            ctx.chain_data[agent_name] = result.data

            if not result.success:
                logger.warning(
                    "orchestrator: chain '%s' parou — agente '%s' falhou: %s",
                    chain_name, agent_name, result.error,
                )
                break

            if stop_on_review and result.requires_review:
                if agent_name in NON_BLOCKING_REVIEW_AGENTS:
                    # Sinaliza review (UI exibe badge) mas continua a chain.
                    # Output ja foi acumulado em chain_data acima — proximos agentes
                    # podem consumir os findings/divergencias via chain_data[agent_name].
                    logger.info(
                        "orchestrator: chain '%s' continua apos review do agente '%s' (NON_BLOCKING)",
                        chain_name, agent_name,
                    )
                else:
                    stopped_for_review = True
                    logger.info(
                        "orchestrator: chain '%s' pausada para revisao humana no agente '%s'",
                        chain_name, agent_name,
                    )
                    break

        # Emitir evento de chain completa
        chain_result = AgentResult(
            success=all(r.success for r in results),
            data={
                "chain": chain_name,
                "steps_completed": len(results),
                "steps_total": len(agent_names),
                "stopped_for_review": stopped_for_review,
                "agents_executed": [r.agent_name for r in results],
            },
            confidence="high" if all(r.confidence == "high" for r in results) else "medium",
            ai_job_id=None,
            suggestions=[],
            requires_review=stopped_for_review,
            agent_name="orchestrator",
            duration_ms=sum(r.duration_ms for r in results),
        )
        emit_agent_event("orchestrator", "completed", ctx, result=chain_result)

        logger.info(
            "orchestrator: chain '%s' concluida — %d/%d steps, review=%s",
            chain_name, len(results), len(agent_names), stopped_for_review,
        )
        return results

    @staticmethod
    def route(intent: str, ctx: AgentContext) -> list[AgentResult]:
        """Roteia um intent de alto nivel para a chain apropriada."""
        chain_name = INTENT_TO_CHAIN.get(intent)
        if not chain_name:
            raise ValueError(f"Intent desconhecido: '{intent}'. Disponiveis: {list(INTENT_TO_CHAIN.keys())}")
        return OrchestratorAgent.execute_chain(chain_name, ctx)


