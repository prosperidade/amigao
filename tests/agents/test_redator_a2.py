"""Testes da migração do RedatorAgent para PecaJuridicaContent — Sprint A2-redator-A.

Cobre os 7 templates servidos pelo agente, o fallback de
``resposta_notificacao`` quando faltam ``prazo_dias``/``ato_regulatorio``,
a derivação de ``Source`` em cascata, e o ``computed_field document_type``
preservado para backward-compat.
"""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from app.agents.base import AgentContext
from app.agents.redator import RedatorAgent, _parse_ato_regulatorio, _parse_prazo_dias
from app.schemas.stage_output import (
    PecaJuridicaContent,
    RespostaNotificacaoContent,
)


def _make_ai_response(content: str):
    from app.core.ai_gateway import AIResponse
    return AIResponse(
        content=content,
        model_used="mock-model",
        tokens_in=10,
        tokens_out=5,
        cost_usd=0.0,
        duration_ms=10,
        provider="mock",
    )


def _ctx(*, chain_data: dict | None = None, metadata: dict | None = None) -> AgentContext:
    return AgentContext(
        tenant_id=1,
        user_id=None,
        process_id=None,
        session=MagicMock(),
        metadata=metadata or {"document_template": "oficio"},
        chain_data=chain_data or {},
    )


def _enter_default_patches(stack: ExitStack):
    stack.enter_context(patch("app.agents.base.check_tenant_cost_limit"))
    stack.enter_context(patch("app.agents.base.check_tenant_monthly_budget"))


@pytest.fixture(autouse=True)
def _isolate_skills(tmp_path, monkeypatch):
    monkeypatch.setattr("app.skills._registry.SKILLS_ROOT", tmp_path)
    from app.skills._registry import invalidate_cache
    invalidate_cache()


# ---------------------------------------------------------------------------
# Bateria paramétrica — 1 caso por template servido (Q1: todos os 7)
# ---------------------------------------------------------------------------

ALL_TEMPLATES = ["prad", "memorial", "oficio", "proposta", "resposta_notificacao", "contrato", "comunicacao"]


@pytest.mark.parametrize("template", ALL_TEMPLATES)
def test_each_template_emits_peca_juridica_content_shape(template: str):
    """Todo template servido produz dict com keys do PecaJuridicaContent + flags fora-do-schema."""
    legal_data = {"legislacao_aplicavel": ["Lei 12.651/2012"]}
    metadata = {"document_template": template}
    if template == "resposta_notificacao":
        metadata["prazo_dias"] = 30
        metadata["ato_regulatorio"] = "Notificação SEMAD nº 123/2026"

    agent = RedatorAgent(_ctx(chain_data={"legislacao": legal_data}, metadata=metadata))

    with ExitStack() as stack:
        _enter_default_patches(stack)
        complete = stack.enter_context(patch("app.agents.base.complete"))
        complete.return_value = _make_ai_response("Texto da peça com Lei 12.651/2012.")
        result = agent.run()

    assert result.success is True
    data = result.data
    # campos do schema
    assert data["template"] == template
    assert data["document_type"] == template  # alias computed_field (Q2)
    assert data["content"] == "Texto da peça com Lei 12.651/2012."
    assert "sources" in data and len(data["sources"]) >= 1
    assert "legal_citations" in data
    # campos fora-do-schema
    assert data["requires_review"] is True
    assert data["confidence"] == "medium"
    # quando há contexto + citação no texto, citation_eval rodou
    assert data["citation_total"] == 1
    assert data["citation_valid"] is True


# ---------------------------------------------------------------------------
# resposta_notificacao — subclass quando enriched, fallback quando não
# ---------------------------------------------------------------------------

class TestRespostaNotificacao:
    def _run(self, metadata: dict, content: str = "Resposta texto.") -> dict:
        agent = RedatorAgent(
            _ctx(
                chain_data={"legislacao": {"legislacao_aplicavel": ["Lei 12.651/2012"]}},
                metadata=metadata,
            )
        )
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response(content)
            return agent.run().data

    def test_metadata_provided_uses_subclass(self):
        data = self._run({
            "document_template": "resposta_notificacao",
            "prazo_dias": 30,
            "ato_regulatorio": "Notificação SEMAD nº 123/2026",
        })
        assert data["template"] == "resposta_notificacao"
        assert data["prazo_dias"] == 30
        assert data["ato_regulatorio"] == "Notificação SEMAD nº 123/2026"

    def test_falls_back_when_metadata_missing_and_text_silent(self):
        """Sem prazo/ato em metadata e sem padrão no texto → fallback PecaJuridicaContent puro."""
        data = self._run(
            {"document_template": "resposta_notificacao"},
            content="Texto livre sem padrões reconhecíveis.",
        )
        # template preservado mas sem campos enriched
        assert data["template"] == "resposta_notificacao"
        assert "prazo_dias" not in data
        assert "ato_regulatorio" not in data

    def test_parses_prazo_from_text_when_metadata_missing(self):
        data = self._run(
            {"document_template": "resposta_notificacao"},
            content="Em atenção à Notificação SEMAD nº 123/2026, no prazo de 30 dias...",
        )
        # parser pegou tudo do texto → subclass enriched
        assert data["prazo_dias"] == 30
        assert "Notificação" in data["ato_regulatorio"]


# ---------------------------------------------------------------------------
# Source cascata
# ---------------------------------------------------------------------------

class TestSourceDerivation:
    def _run_with_legal(self, legal_data: dict | None) -> dict:
        agent = RedatorAgent(
            _ctx(
                chain_data={"legislacao": legal_data} if legal_data else {},
                metadata={"document_template": "oficio", "instructions": "Instrução X"},
            )
        )
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response("texto")
            return agent.run().data

    def test_source_from_legislacao_aplicavel(self):
        data = self._run_with_legal({"legislacao_aplicavel": ["Lei 12.651/2012", "Lei 9.605/1998"]})
        types = [s["type"] for s in data["sources"]]
        refs = [s["ref"] for s in data["sources"]]
        assert "legislation" in types
        assert "Lei 12.651/2012" in refs

    def test_fallback_manual_source_when_no_legal_context(self):
        data = self._run_with_legal(None)
        assert len(data["sources"]) == 1
        s = data["sources"][0]
        assert s["type"] == "manual"
        assert s["ref"] == "agent_redator"
        assert "Instrução X" in s["excerpt"] or "Sem contexto" in s["excerpt"]

    def test_fallback_manual_when_legal_keys_empty(self):
        data = self._run_with_legal({"legislacao_aplicavel": [], "normas_estaduais": []})
        assert len(data["sources"]) == 1
        assert data["sources"][0]["type"] == "manual"

    def test_caps_at_5_sources(self):
        data = self._run_with_legal({
            "legislacao_aplicavel": [f"Lei {i}/2020" for i in range(10)],
        })
        assert len(data["sources"]) <= 5


# ---------------------------------------------------------------------------
# Cascade addressee
# ---------------------------------------------------------------------------

class TestAddresseeCascade:
    def _run(self, *, metadata: dict, process_data: dict | None = None) -> dict:
        agent = RedatorAgent(
            _ctx(
                chain_data={
                    "legislacao": {"legislacao_aplicavel": ["Lei 12.651/2012"]},
                    "diagnostico": process_data or {},
                },
                metadata=metadata,
            )
        )
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response("texto")
            return agent.run().data

    def test_metadata_addressee_wins(self):
        data = self._run(
            metadata={"document_template": "oficio", "addressee": "SEMAD-GO"},
            process_data={"destination_agency": "IBAMA"},
        )
        assert data["addressee"] == "SEMAD-GO"

    def test_falls_back_to_process_destination_agency(self):
        data = self._run(
            metadata={"document_template": "oficio"},
            process_data={"destination_agency": "IBAMA"},
        )
        assert data["addressee"] == "IBAMA"

    def test_none_when_neither(self):
        data = self._run(metadata={"document_template": "oficio"})
        assert data["addressee"] is None


# ---------------------------------------------------------------------------
# Citation evaluator extension — all_citations populando legal_citations
# ---------------------------------------------------------------------------

class TestCitationEvaluatorIntegration:
    def test_all_citations_become_legal_citations(self):
        legal_data = {"legislacao_aplicavel": ["Lei 12.651/2012", "Lei 9.605/1998"]}
        agent = RedatorAgent(
            _ctx(chain_data={"legislacao": legal_data}, metadata={"document_template": "oficio"})
        )
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response(
                "Conforme a Lei 12.651/2012 e a Lei 9.605/1998..."
            )
            data = agent.run().data

        # Sprint A2-A: legal_citations = todas as citações detectadas (válidas + inválidas)
        # antes só vinham as inválidas em citation_issues — agora a lista completa
        # vai pra peca.legal_citations.
        assert len(data["legal_citations"]) == 2
        numeros = sorted(c["numero"] for c in data["legal_citations"])
        assert numeros == ["12.651", "9.605"]

    def test_invalid_citation_appears_in_both_lists(self):
        legal_data = {"legislacao_aplicavel": ["Lei 12.651/2012"]}
        agent = RedatorAgent(
            _ctx(chain_data={"legislacao": legal_data}, metadata={"document_template": "oficio"})
        )
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response(
                "Lei 12.651/2012 e a inventada Lei 99.999/2099..."
            )
            data = agent.run().data

        # legal_citations tem ambas (lista completa)
        assert len(data["legal_citations"]) == 2
        # citation_issues tem só a inválida
        assert len(data["citation_issues"]) == 1
        assert data["citation_issues"][0]["numero"] == "99.999"
        assert data["citation_valid"] is False


# ---------------------------------------------------------------------------
# computed_field document_type (Q2 — defesa em profundidade)
# ---------------------------------------------------------------------------

class TestDocumentTypeAlias:
    def test_alias_present_in_payload(self):
        agent = RedatorAgent(_ctx(metadata={"document_template": "memorial"}))
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response("memorial")
            data = agent.run().data
        assert data["template"] == "memorial"
        assert data["document_type"] == "memorial"

    def test_alias_round_trip_via_model(self):
        peca = PecaJuridicaContent(
            content="x",
            sources=[{"type": "legislation", "ref": "Lei 1/2020"}],  # type: ignore[list-item]
            template="oficio",
        )
        dumped = peca.model_dump(mode="json")
        assert dumped["document_type"] == "oficio"
        # extra=ignore garante que document_type no input é silenciosamente descartado
        rebuilt = PecaJuridicaContent.model_validate(dumped)
        assert rebuilt.template == "oficio"


# ---------------------------------------------------------------------------
# Parsers best-effort
# ---------------------------------------------------------------------------

class TestParsers:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("no prazo de 30 dias", 30),
            ("em até 15 dias", 15),
            ("60 dias para", 60),
            ("não há prazo", None),
            ("", None),
        ],
    )
    def test_parse_prazo_dias(self, text: str, expected: int | None):
        assert _parse_prazo_dias(text) == expected

    def test_parse_ato_regulatorio_basic(self):
        assert _parse_ato_regulatorio("Auto de Infração nº 12345/2026") is not None
        assert _parse_ato_regulatorio("Notificação SEMAD nº 123/2026") is not None
        assert _parse_ato_regulatorio("texto sem ato") is None


# ---------------------------------------------------------------------------
# Log INFO em proposta/contrato (Q1)
# ---------------------------------------------------------------------------

class TestLogInfoForDedicatedFlows:
    @pytest.mark.parametrize("template", ["proposta", "contrato"])
    def test_logs_info_when_template_has_dedicated_flow(self, template: str, caplog):
        caplog.set_level("INFO", logger="app.agents.redator")
        agent = RedatorAgent(_ctx(metadata={"document_template": template}))
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response("texto")
            agent.run()
        msgs = [r.message for r in caplog.records if r.name == "app.agents.redator"]
        assert any("fluxo dedicado" in m for m in msgs)

    def test_no_log_for_oficio(self, caplog):
        caplog.set_level("INFO", logger="app.agents.redator")
        agent = RedatorAgent(_ctx(metadata={"document_template": "oficio"}))
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response("texto")
            agent.run()
        msgs = [r.message for r in caplog.records if r.name == "app.agents.redator"]
        assert not any("fluxo dedicado" in m for m in msgs)


# ---------------------------------------------------------------------------
# JSON-serializability + roundtrip
# ---------------------------------------------------------------------------

def test_payload_is_json_serializable():
    """O dict retornado por execute() deve ser totalmente JSON-serializável
    para persistir limpo em AIJob.result (PortableJSON)."""
    import json
    agent = RedatorAgent(
        _ctx(
            chain_data={"legislacao": {"legislacao_aplicavel": ["Lei 12.651/2012"]}},
            metadata={"document_template": "resposta_notificacao", "prazo_dias": 30, "ato_regulatorio": "Of. 1"},
        )
    )
    with ExitStack() as stack:
        _enter_default_patches(stack)
        complete = stack.enter_context(patch("app.agents.base.complete"))
        complete.return_value = _make_ai_response("Lei 12.651/2012 aplica.")
        data = agent.run().data
    # round-trip JSON
    text = json.dumps(data)
    assert json.loads(text) == data


def test_resposta_notificacao_roundtrip_via_pydantic():
    peca = RespostaNotificacaoContent(
        content="x",
        sources=[{"type": "legislation", "ref": "Lei 1/2020"}],  # type: ignore[list-item]
        legal_citations=[],
        prazo_dias=30,
        ato_regulatorio="Of. 1/2026",
    )
    dumped = peca.model_dump(mode="json")
    assert dumped["template"] == "resposta_notificacao"
    rebuilt = RespostaNotificacaoContent.model_validate(dumped)
    assert rebuilt.prazo_dias == 30
