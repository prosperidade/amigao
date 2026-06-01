"""Testes do OrchestratorAgent — Onda B Fase 2.

Cobre:
- Composição correta da chain `diagnostico_completo` pós-Fase 2
  (`extrator → auditor_imovel → legislacao → diagnostico`).
- Mecanismo `NON_BLOCKING_REVIEW_AGENTS`: agentes que sinalizam
  `requires_review=True` mas não interrompem a chain. Sem isso, qualquer chain
  incluindo o `auditor_imovel` quebraria antes do `diagnostico` rodar.
- Preservação do comportamento bloqueante para agentes que NÃO estão na lista
  (regressão: peças formais como `redator` continuam parando a chain).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.agents.base import AgentContext, AgentRegistry, AgentResult, BaseAgent
from app.agents.orchestrator import (
    CHAINS,
    NON_BLOCKING_FAILURE_BY_CHAIN,
    NON_BLOCKING_REVIEW_AGENTS,
    NON_BLOCKING_REVIEW_BY_CHAIN,
    OrchestratorAgent,
)


def _ctx() -> AgentContext:
    return AgentContext(
        tenant_id=1, user_id=1, process_id=42,
        session=MagicMock(), metadata={}, chain_data={},
    )


def _ok(name: str, *, requires_review: bool = False, data: dict | None = None) -> AgentResult:
    return AgentResult(
        success=True,
        data=data or {"agent": name},
        confidence="high",
        ai_job_id=None,
        suggestions=[],
        requires_review=requires_review,
        agent_name=name,
        duration_ms=10,
    )


def _fail(name: str, *, error: str = "boom") -> AgentResult:
    return AgentResult(
        success=False,
        data={},
        confidence="low",
        ai_job_id=None,
        suggestions=[],
        requires_review=False,
        agent_name=name,
        duration_ms=10,
        error=error,
    )


class TestChainDiagnosticoCompletoComposicao:
    """Composição da chain diagnostico_completo pós-Onda B."""

    def test_chain_segue_ordem_extrator_auditor_legislacao_diagnostico(self):
        assert CHAINS["diagnostico_completo"] == [
            "extrator",
            "auditor_imovel",
            "legislacao",
            "diagnostico",
        ]

    def test_auditor_imovel_esta_entre_extrator_e_legislacao(self):
        """Posição garante que auditor recebe documentos extraídos e que
        legislacao/diagnostico podem consumir findings via chain_data."""
        chain = CHAINS["diagnostico_completo"]
        i_extrator = chain.index("extrator")
        i_auditor = chain.index("auditor_imovel")
        i_legislacao = chain.index("legislacao")
        i_diagnostico = chain.index("diagnostico")
        assert i_extrator < i_auditor < i_legislacao < i_diagnostico


class TestNonBlockingReviewAgents:
    """Mecanismo `requires_review=True` não-bloqueante."""

    def test_auditor_imovel_esta_marcado_como_non_blocking(self):
        assert "auditor_imovel" in NON_BLOCKING_REVIEW_AGENTS
        assert "legislacao" in NON_BLOCKING_REVIEW_BY_CHAIN["diagnostico_completo"]
        assert "legislacao" in NON_BLOCKING_FAILURE_BY_CHAIN["diagnostico_completo"]

    def test_chain_continua_quando_agente_non_blocking_pede_review(self):
        """Simula auditor pedindo review; chain segue pra legislacao e diagnostico."""
        ctx = _ctx()
        executed: list[str] = []

        class FakeAgent(BaseAgent):
            name: str = ""

            def __init__(self, ctx, name):
                super().__init__(ctx)
                self.name = name

            def validate_preconditions(self):
                pass

            def execute(self):
                return {"agent": self.name}

            def _fallback_prompts(self):
                return {}

            def run(self) -> AgentResult:
                executed.append(self.name)
                # auditor_imovel pede review; outros não
                review = self.name == "auditor_imovel"
                return _ok(self.name, requires_review=review)

        def fake_create(name, ctx):
            return FakeAgent(ctx, name)

        with patch.object(AgentRegistry, "create", side_effect=fake_create):
            results = OrchestratorAgent.execute_chain("diagnostico_completo", ctx)

        # Todos os 4 agentes da chain rodaram
        assert executed == ["extrator", "auditor_imovel", "legislacao", "diagnostico"]
        assert len(results) == 4
        # Auditor pediu review mas a chain continuou
        assert results[1].requires_review is True
        # Resultados subsequentes não pediram review
        assert results[2].requires_review is False
        assert results[3].requires_review is False

    def test_chain_continua_quando_legislacao_pede_review_no_diagnostico_completo(self):
        """Legislação é insumo intermediário nesta chain; diagnóstico ainda roda."""
        ctx = _ctx()
        executed: list[str] = []

        class FakeAgent(BaseAgent):
            name: str = ""

            def __init__(self, ctx, name):
                super().__init__(ctx)
                self.name = name

            def validate_preconditions(self):
                pass

            def execute(self):
                return {"agent": self.name}

            def _fallback_prompts(self):
                return {}

            def run(self) -> AgentResult:
                executed.append(self.name)
                # legislacao pede review (não está em NON_BLOCKING) → chain deve parar
                review = self.name == "legislacao"
                return _ok(self.name, requires_review=review)

        def fake_create(name, ctx):
            return FakeAgent(ctx, name)

        with patch.object(AgentRegistry, "create", side_effect=fake_create):
            results = OrchestratorAgent.execute_chain("diagnostico_completo", ctx)

        assert executed == ["extrator", "auditor_imovel", "legislacao", "diagnostico"]
        assert len(results) == 4
        assert results[2].requires_review is True

    def test_chain_continua_quando_legislacao_falha_no_diagnostico_completo(self):
        """Timeout/provider da legislação não pode impedir a entrega do diagnóstico."""
        ctx = _ctx()
        executed: list[str] = []

        class FakeAgent(BaseAgent):
            name: str = ""

            def __init__(self, ctx, name):
                super().__init__(ctx)
                self.name = name

            def validate_preconditions(self):
                pass

            def execute(self):
                return {"agent": self.name}

            def _fallback_prompts(self):
                return {}

            def run(self) -> AgentResult:
                executed.append(self.name)
                if self.name == "legislacao":
                    return _fail(self.name, error="Timeout")
                snapshot = dict(self.ctx.chain_data)
                return _ok(self.name, data={"agent": self.name, "saw": list(snapshot.keys())})

        def fake_create(name, ctx):
            return FakeAgent(ctx, name)

        with patch.object(AgentRegistry, "create", side_effect=fake_create):
            results = OrchestratorAgent.execute_chain("diagnostico_completo", ctx)

        assert executed == ["extrator", "auditor_imovel", "legislacao", "diagnostico"]
        assert len(results) == 4
        assert results[2].success is False
        assert ctx.chain_data["legislacao"] == {
            "success": False,
            "error": "Timeout",
            "agent_name": "legislacao",
        }
        assert "legislacao" in results[3].data["saw"]

    def test_chain_para_quando_agente_blocking_pede_review(self):
        """Regressão: agentes fora da exceção continuam parando sua chain."""
        ctx = _ctx()
        executed: list[str] = []

        class FakeAgent(BaseAgent):
            name: str = ""

            def __init__(self, ctx, name):
                super().__init__(ctx)
                self.name = name

            def validate_preconditions(self):
                pass

            def execute(self):
                return {"agent": self.name}

            def _fallback_prompts(self):
                return {}

            def run(self) -> AgentResult:
                executed.append(self.name)
                return _ok(self.name, requires_review=True)

        def fake_create(name, ctx):
            return FakeAgent(ctx, name)

        with patch.object(AgentRegistry, "create", side_effect=fake_create):
            results = OrchestratorAgent.execute_chain("gerar_proposta", ctx)

        assert executed == ["diagnostico"]
        assert len(results) == 1

    def test_chain_data_acumula_output_de_agentes_anteriores(self):
        """Confirma que chain_data["auditor_imovel"] fica disponível para os
        próximos agentes — base do contrato downstream (legislacao/diagnostico
        podem consumir findings via chain_data)."""
        ctx = _ctx()

        class FakeAgent(BaseAgent):
            name: str = ""

            def __init__(self, ctx, name):
                super().__init__(ctx)
                self.name = name

            def validate_preconditions(self):
                pass

            def execute(self):
                return {"agent": self.name}

            def _fallback_prompts(self):
                return {}

            def run(self) -> AgentResult:
                snapshot = dict(self.ctx.chain_data)
                review = self.name == "auditor_imovel"
                data = {"agent": self.name, "saw": list(snapshot.keys())}
                return _ok(self.name, requires_review=review, data=data)

        def fake_create(name, ctx):
            return FakeAgent(ctx, name)

        with patch.object(AgentRegistry, "create", side_effect=fake_create):
            results = OrchestratorAgent.execute_chain("diagnostico_completo", ctx)

        # legislacao deve ter visto chain_data com extrator + auditor_imovel
        assert "extrator" in results[2].data["saw"]
        assert "auditor_imovel" in results[2].data["saw"]
        # diagnostico vê todos os 3 anteriores
        assert set(results[3].data["saw"]) == {"extrator", "auditor_imovel", "legislacao"}
