"""Golden tests dos agentes LLM — fix/llm-consistencia (2026-06-07).

Cinto de segurança da esteira: respostas LLM GRAVADAS do caso real (Fazenda São
Jorge, formato pós-#70) alimentam o parser/agente. Toda mudança futura de
prompt/parser/formato de saída passa por aqui ANTES do merge.

Cobre os três cenários exigidos:
  1. Resposta no formato novo (#70) → parser processa e produz o shape esperado.
  2. Resposta TRUNCADA → vira o erro ESPECÍFICO de truncamento (não o genérico
     de parse) e o parser NÃO repara em silêncio.
  3. Resposta com fonte inexistente/vazia → marcada como `sem_fonte=True`
     ("fonte não verificada"), nunca inventada.

Fixtures em tests/agents/golden/ (ver README lá).
"""

from __future__ import annotations

import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.agents.base import AgentContext
from app.agents.diagnostico import DiagnosticoAgent
from app.agents.validators import OutputValidationError, OutputValidationPipeline
from app.core.ai_gateway import AIResponse, AITruncationError

GOLDEN = Path(__file__).parent / "golden"


def _load_text(name: str) -> str:
    return (GOLDEN / name).read_text(encoding="utf-8")


def _load_json(name: str) -> dict:
    return json.loads(_load_text(name))


def _ai_response(content: str) -> AIResponse:
    return AIResponse(
        content=content,
        model_used="golden-model",
        tokens_in=1000,
        tokens_out=2000,
        cost_usd=0.01,
        duration_ms=200,
        provider="golden",
        finish_reason="stop",
    )


def _ctx(*, chain_data: dict | None = None) -> AgentContext:
    return AgentContext(
        tenant_id=1,
        user_id=1,
        process_id=12,  # caso #12
        session=MagicMock(),
        metadata={},
        chain_data=chain_data or {},
    )


def _enter_default_patches(stack: ExitStack):
    stack.enter_context(patch("app.agents.base.check_tenant_cost_limit"))
    stack.enter_context(patch("app.agents.base.check_tenant_monthly_budget"))
    stack.enter_context(patch.object(
        DiagnosticoAgent, "_load_process_data",
        return_value={"process": {"id": 12}, "property": {}, "documents": []},
    ))
    stack.enter_context(patch("app.agents.base.get_active_prompt", return_value=None))


@pytest.fixture(autouse=True)
def _isolate_skills(tmp_path, monkeypatch):
    monkeypatch.setattr("app.skills._registry.SKILLS_ROOT", tmp_path)
    from app.skills._registry import invalidate_cache
    invalidate_cache()


# ---------------------------------------------------------------------------
# 1. Formato novo (#70) — parser + agente produzem o shape esperado
# ---------------------------------------------------------------------------

class TestGoldenFormatoNovo:
    def test_parser_processa_diagnostico_p70_sem_erro(self):
        raw = _load_text("diagnostico_sao_jorge_p70.json")
        parsed = OutputValidationPipeline.parse_llm_json(raw)
        assert parsed["situacao_geral"]
        assert isinstance(parsed["passivos_identificados"], list)
        assert isinstance(parsed["afirmacoes"], list) and parsed["afirmacoes"]
        # formato #70: cada afirmação carrega afirmacao/fonte/confianca
        a0 = parsed["afirmacoes"][0]
        assert "afirmacao" in a0 and "fonte" in a0 and "confianca" in a0

    def test_diagnostico_agente_emite_shape_e_afirmacoes_com_fonte(self):
        payload = _load_json("diagnostico_sao_jorge_p70.json")
        agent = DiagnosticoAgent(_ctx())
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _ai_response(json.dumps(payload, ensure_ascii=False))
            result = agent.run()

        assert result.success is True
        assert result.requires_review is True
        data = result.data
        # shape do schema preservado
        assert data["content"].startswith("Imóvel rural Fazenda São Jorge")
        assert len(data["hipoteses"]) == len(payload["passivos_identificados"])
        assert len(data["checklist_documental"]) == len(payload["acoes_remediacao"])
        # Cobertura 100% (Ficha 04, Isis 16/06): UMA afirmação por passivo e por
        # ação (6+6=12), cada uma com fontes. O LLM citou 4 → essas 4 carregam
        # fonte real; as demais ficam marcadas "sem fonte identificada" (nunca
        # órfãs, nunca inventadas).
        afirmacoes = data["afirmacoes"]
        assert len(afirmacoes) == len(payload["passivos_identificados"]) + len(payload["acoes_remediacao"])
        for af in afirmacoes:
            assert af["texto"]
            assert af["fontes"]  # sempre ≥1 fonte (real ou sem_fonte)
        com_fonte = [af for af in afirmacoes if all(not f.get("sem_fonte") for f in af["fontes"])]
        assert len(com_fonte) == 4  # exatamente as 4 que o LLM atribuiu
        # todo passivo aparece como afirmação
        textos = {af["texto"] for af in afirmacoes}
        for p in payload["passivos_identificados"]:
            assert p in textos

    def test_parser_processa_legislacao_sao_jorge_sem_erro(self):
        parsed = OutputValidationPipeline.parse_llm_json(_load_text("legislacao_sao_jorge.json"))
        for key in (
            "caminho_regulatorio", "orgao_competente", "legislacao_aplicavel",
            "etapas", "riscos", "confianca",
        ):
            assert key in parsed, f"chave ausente no parse: {key}"
        assert isinstance(parsed["legislacao_aplicavel"], list)


# ---------------------------------------------------------------------------
# 2. Truncamento — erro ESPECÍFICO, sem parse parcial silencioso
# ---------------------------------------------------------------------------

class TestGoldenTruncamento:
    def test_parser_truncado_nao_repara_em_silencio(self):
        """JSON cortado no meio → OutputValidationError(json_parse), NUNCA um dict
        parcial fabricado em silêncio."""
        raw = _load_text("diagnostico_truncado.txt")
        with pytest.raises(OutputValidationError) as exc:
            OutputValidationPipeline.parse_llm_json(raw)
        assert exc.value.stage == "json_parse"

    def test_agente_trata_truncamento_como_erro_especifico(self):
        """Quando o gateway sinaliza truncamento (AITruncationError), o agente
        falha com a mensagem ESPECÍFICA — distinta do erro genérico de parse."""
        agent = DiagnosticoAgent(_ctx())
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.side_effect = AITruncationError(
                message=(
                    "resposta truncada (limite de tokens): o modelo atingiu "
                    "max_tokens=2048 sem fechar a resposta."
                ),
                last_error="finish_reason=length model=gpt-4.1",
            )
            result = agent.run()

        assert result.success is False
        assert "truncada" in result.error.lower()
        assert "json" not in result.error.lower()  # não é o erro genérico de parse


# ---------------------------------------------------------------------------
# 3. Fonte inexistente → marcada como não verificada (nunca inventada)
# ---------------------------------------------------------------------------

class TestGoldenFonteInexistente:
    def test_fonte_vazia_ou_sem_fonte_marca_nao_verificada(self):
        payload = _load_json("diagnostico_fonte_inexistente.json")
        agent = DiagnosticoAgent(_ctx())
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _ai_response(json.dumps(payload, ensure_ascii=False))
            result = agent.run()

        assert result.success is True
        afirmacoes = result.data["afirmacoes"]
        # Cobertura 100%: 2 passivos + 1 ação = 3 afirmações (a ação não tinha
        # afirmação no payload → entra com piso sem_fonte).
        assert len(afirmacoes) == 3
        # TODAS as fontes vieram vazias/"sem fonte" → marcadas sem_fonte (não inventadas)
        for af in afirmacoes:
            assert af["fontes"], "afirmação deve ter ao menos a marca de sem_fonte"
            assert all(f.get("sem_fonte") for f in af["fontes"])
