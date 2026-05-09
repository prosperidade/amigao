"""Bateria E2E do RedatorAgent — Sprint A2-redator-C1.

Pipeline completo (`run()` → AgentResult → JSON dump) por template
com LLM stubado por template (textos realistas mas determinísticos).

Vai pra CI. Custo: zero (sem LLM real). Para validação com LLM real,
ver Tarefa C2 (`scripts/smoke_a2_redator.py`).
"""

from __future__ import annotations

import json
from contextlib import ExitStack
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from app.agents.base import AgentContext
from app.agents.redator import RedatorAgent


def _make_ai_response(content: str):
    from app.core.ai_gateway import AIResponse
    return AIResponse(
        content=content,
        model_used="mock-model",
        tokens_in=120,
        tokens_out=80,
        cost_usd=0.0001,
        duration_ms=250,
        provider="mock",
    )


def _ctx(*, metadata: dict, chain_data: dict | None = None) -> AgentContext:
    return AgentContext(
        tenant_id=1,
        user_id=None,
        process_id=None,
        session=MagicMock(),
        metadata=metadata,
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
# Stubs realistas por template
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TemplateScenario:
    template: str
    metadata_extra: dict
    legal_data: dict
    llm_output: str
    expected_min_citations: int
    expected_addressee: str | None
    expected_subclass: bool  # True = RespostaNotificacaoContent


_LEGAL_FEDERAL = {
    "legislacao_aplicavel": ["Lei 12.651/2012", "Decreto 7.830/2012", "Lei 9.605/1998"],
}

_LEGAL_GO = {
    "legislacao_aplicavel": ["Lei 12.651/2012"],
    "normas_estaduais": ["Lei Estadual 18.102/2013"],
}


SCENARIOS: dict[str, TemplateScenario] = {
    "prad": TemplateScenario(
        template="prad",
        metadata_extra={},
        legal_data=_LEGAL_FEDERAL,
        llm_output=(
            "PLANO DE RECUPERAÇÃO DE ÁREA DEGRADADA\n\n"
            "Diagnóstico: área de 12 hectares com supressão irregular de vegetação "
            "nativa, em desacordo com o art. 7º da Lei 12.651/2012. Aplicam-se "
            "também as disposições do Decreto 7.830/2012 quanto ao SICAR. "
            "Cronograma: 36 meses, plantio em 3 etapas."
        ),
        expected_min_citations=2,
        expected_addressee=None,
        expected_subclass=False,
    ),
    "memorial": TemplateScenario(
        template="memorial",
        metadata_extra={},
        legal_data=_LEGAL_GO,
        llm_output=(
            "MEMORIAL DESCRITIVO\n\n"
            "Imóvel rural denominado Fazenda Boa Vista, com 482,3 hectares, "
            "matrícula 12.345, CRI Goiânia. Conforme Lei 12.651/2012, a "
            "Reserva Legal corresponde a 35% do total."
        ),
        expected_min_citations=1,
        expected_addressee=None,
        expected_subclass=False,
    ),
    "oficio": TemplateScenario(
        template="oficio",
        metadata_extra={"addressee": "SEMAD-GO"},
        legal_data=_LEGAL_GO,
        llm_output=(
            "OFÍCIO\n\n"
            "À SEMAD-GO,\n\n"
            "Em atenção à demanda em epígrafe, vem o requerente, nos termos "
            "da Lei 12.651/2012, apresentar a documentação comprobatória "
            "da regularidade do CAR. Termos em que pede deferimento."
        ),
        expected_min_citations=1,
        expected_addressee="SEMAD-GO",
        expected_subclass=False,
    ),
    "proposta": TemplateScenario(
        template="proposta",
        metadata_extra={},
        legal_data={},  # propostas comerciais raramente citam lei
        llm_output=(
            "PROPOSTA COMERCIAL\n\n"
            "Escopo: regularização ambiental completa do imóvel.\n"
            "Investimento: R$ 18.500,00 em 3 parcelas.\n"
            "Prazo: 90 dias após assinatura."
        ),
        expected_min_citations=0,
        expected_addressee=None,
        expected_subclass=False,
    ),
    "resposta_notificacao": TemplateScenario(
        template="resposta_notificacao",
        metadata_extra={
            "prazo_dias": 30,
            "ato_regulatorio": "Notificação SEMAD nº 0123/2026",
            "addressee": "SEMAD-GO",
        },
        legal_data=_LEGAL_FEDERAL,
        llm_output=(
            "Em resposta à Notificação SEMAD nº 0123/2026, no prazo de 30 dias, "
            "manifestamos o seguinte: nos termos da Lei 12.651/2012 e do "
            "Decreto 7.830/2012, o imóvel encontra-se em regularidade junto "
            "ao SICAR. Não houve infração ambiental ao art. 38 da Lei 9.605/1998."
        ),
        expected_min_citations=3,
        expected_addressee="SEMAD-GO",
        expected_subclass=True,
    ),
    "contrato": TemplateScenario(
        template="contrato",
        metadata_extra={},
        legal_data={},
        llm_output=(
            "CONTRATO DE PRESTAÇÃO DE SERVIÇOS\n\n"
            "Objeto: consultoria ambiental para regularização CAR.\n"
            "Prazo: 90 dias.\n"
            "Valor: R$ 18.500,00."
        ),
        expected_min_citations=0,
        expected_addressee=None,
        expected_subclass=False,
    ),
    "comunicacao": TemplateScenario(
        template="comunicacao",
        metadata_extra={"addressee": "Cliente Final"},
        legal_data={},
        llm_output=(
            "Prezado(a),\n\n"
            "Informamos que o protocolo do CAR foi efetuado com sucesso. "
            "Aguardamos análise técnica do órgão competente."
        ),
        expected_min_citations=0,
        expected_addressee="Cliente Final",
        expected_subclass=False,
    ),
}


@pytest.mark.parametrize("template_name", list(SCENARIOS.keys()))
def test_redator_e2e_pipeline_per_template(template_name: str):
    """Pipeline completo: setup → run() → AgentResult → JSON dump."""
    scenario = SCENARIOS[template_name]

    metadata = {"document_template": scenario.template, **scenario.metadata_extra}
    chain_data = {"legislacao": scenario.legal_data} if scenario.legal_data else {}

    agent = RedatorAgent(_ctx(metadata=metadata, chain_data=chain_data))

    with ExitStack() as stack:
        _enter_default_patches(stack)
        complete = stack.enter_context(patch("app.agents.base.complete"))
        complete.return_value = _make_ai_response(scenario.llm_output)
        result = agent.run()

    # 1. AgentResult OK
    assert result.success is True, f"falhou em template={scenario.template}: {result.error}"
    assert result.requires_review is True
    data = result.data

    # 2. Schema PecaJuridicaContent fields presentes
    assert data["template"] == scenario.template
    assert data["document_type"] == scenario.template  # alias backward-compat
    assert data["content"] == scenario.llm_output
    assert isinstance(data["sources"], list) and len(data["sources"]) >= 1
    assert isinstance(data["legal_citations"], list)

    # 3. Subclass enriched para resposta_notificacao quando aplicável
    if scenario.expected_subclass:
        assert "prazo_dias" in data
        assert "ato_regulatorio" in data
        assert data["prazo_dias"] == 30
    else:
        # demais templates não devem ter campos do subclass
        if scenario.template != "resposta_notificacao":
            assert "prazo_dias" not in data

    # 4. Addressee esperado
    assert data["addressee"] == scenario.expected_addressee

    # 5. Citation evaluator: total esperado quando havia legal_data
    if scenario.legal_data:
        assert data["citation_total"] >= scenario.expected_min_citations
        # quando tem legal_data e citações no texto, citation_valid deve ser True
        # (todas as citações no llm_output stub estão no legal_data)
        if scenario.expected_min_citations > 0:
            assert data["citation_valid"] is True

    # 6. Flags fora-do-schema presentes
    assert data["confidence"] == "medium"

    # 7. JSON-serializable round-trip
    json_text = json.dumps(data)
    rebuilt = json.loads(json_text)
    assert rebuilt == data


def test_all_templates_covered():
    """Garante que a bateria não desincroniza com VALID_TEMPLATES do agente."""
    from app.agents.redator import RedatorAgent
    assert set(SCENARIOS.keys()) == RedatorAgent.VALID_TEMPLATES


def test_resposta_notificacao_falls_back_when_metadata_missing_in_pipeline():
    """E2E: caller sem prazo_dias/ato_regulatorio + texto silencioso →
    PecaJuridicaContent puro, mas pipeline conclui com sucesso."""
    legal_data = {"legislacao_aplicavel": ["Lei 12.651/2012"]}
    agent = RedatorAgent(
        _ctx(
            metadata={"document_template": "resposta_notificacao"},  # sem extras
            chain_data={"legislacao": legal_data},
        )
    )
    with ExitStack() as stack:
        _enter_default_patches(stack)
        complete = stack.enter_context(patch("app.agents.base.complete"))
        complete.return_value = _make_ai_response("Texto livre sem padrão de prazo ou ato.")
        result = agent.run()

    assert result.success is True
    data = result.data
    assert data["template"] == "resposta_notificacao"
    # Fallback gracioso: sem prazo_dias / ato_regulatorio
    assert "prazo_dias" not in data
    assert "ato_regulatorio" not in data
