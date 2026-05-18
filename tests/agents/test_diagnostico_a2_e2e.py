"""Bateria E2E paramétrica do DiagnosticoAgent — Sprint A2-diagnostico-C1.

Pipeline completo (`run()` → AgentResult → JSON dump round-trip) por
cenário, cobrindo as duas dimensões críticas:

* **AI on/off:** path IA (`execute()` com LLM JSON) × path rules-based
  (`_rules_based_diagnosis` quando settings.ai_configured=False).
* **Cenário documental:** simples, médio, completo, erro.

Vai pra CI. Custo: zero (LLM stubado). Smoke real com gpt-4o-mini fica
em C2 (`scripts/smoke_a2_diagnostico.py`).
"""

from __future__ import annotations

import json
from contextlib import ExitStack
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.agents.base import AgentContext
from app.agents.diagnostico import DiagnosticoAgent


def _make_ai_response(payload: dict | str):
    from app.core.ai_gateway import AIResponse
    content = json.dumps(payload, ensure_ascii=False) if isinstance(payload, dict) else payload
    return AIResponse(
        content=content, model_used="mock-model", tokens_in=80,
        tokens_out=160, cost_usd=0.0001, duration_ms=200, provider="mock",
    )


def _ctx(*, chain_data: dict | None = None) -> AgentContext:
    return AgentContext(
        tenant_id=1, user_id=1, process_id=42,
        session=MagicMock(), metadata={}, chain_data=chain_data or {},
    )


def _enter_default_patches(stack: ExitStack, *, process_data: dict, ai_on: bool):
    stack.enter_context(patch("app.agents.base.check_tenant_cost_limit"))
    stack.enter_context(patch("app.agents.base.check_tenant_monthly_budget"))
    stack.enter_context(patch.object(
        DiagnosticoAgent, "_load_process_data", return_value=process_data,
    ))
    stack.enter_context(patch("app.agents.base.get_active_prompt", return_value=None))
    if not ai_on:
        mock_settings = MagicMock()
        mock_settings.ai_configured = False
        stack.enter_context(patch("app.core.config.settings", mock_settings))


@pytest.fixture(autouse=True)
def _isolate_skills(tmp_path, monkeypatch):
    monkeypatch.setattr("app.skills._registry.SKILLS_ROOT", tmp_path)
    from app.skills._registry import invalidate_cache
    invalidate_cache()


# ---------------------------------------------------------------------------
# Cenários E2E
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Scenario:
    name: str
    ai_on: bool
    process_data: dict[str, Any]
    chain_data: dict[str, Any] = field(default_factory=dict)
    llm_payload: dict[str, Any] | None = None
    expected_min_sources: int = 1
    expected_severidade: str | None = None
    expected_min_hipoteses: int = 0
    expected_min_checklist: int = 0


SCENARIOS: list[Scenario] = [
    Scenario(
        name="ai_on_simples",
        ai_on=True,
        process_data={
            "process": {"id": 42, "demand_type": "car"},
            "property": {"state": "GO", "biome": "Cerrado", "car_code": "GO-12345"},
            "documents": [{"id": 1, "document_type": "matricula"}],
        },
        chain_data={},
        llm_payload={
            "situacao_geral": "Imóvel regular no SICAR.",
            "passivos_identificados": [],
            "acoes_remediacao": [],
            "prioridade_acoes": [],
            "risco_estimado": "baixo",
            "observacoes": "",
        },
        expected_min_sources=1,  # 1 doc
        expected_severidade="baixo",
    ),
    Scenario(
        name="ai_on_medio",
        ai_on=True,
        process_data={
            "process": {"id": 42, "demand_type": "retificacao_car"},
            "property": {"state": "GO", "biome": "Cerrado", "car_code": "GO-12345"},
            "documents": [
                {"id": 1, "document_type": "matricula"},
                {"id": 2, "document_type": "car"},
            ],
        },
        chain_data={"legislacao": {"legislacao_aplicavel": ["Lei 12.651/2012"]}},
        llm_payload={
            "situacao_geral": "Divergência de área entre matrícula e CAR.",
            "passivos_identificados": ["Área CAR ≠ matrícula"],
            "acoes_remediacao": ["Solicitar retificação no SICAR"],
            "prioridade_acoes": ["retificacao_car"],
            "risco_estimado": "medio",
            "observacoes": "Caso típico de retificação.",
        },
        expected_min_sources=3,  # 2 docs + 1 lei
        expected_severidade="medio",
        expected_min_hipoteses=1,
        expected_min_checklist=1,
    ),
    Scenario(
        name="ai_on_completo",
        ai_on=True,
        process_data={
            "process": {"id": 42, "demand_type": "regularizacao_fundiaria"},
            "property": {
                "state": "GO", "biome": "Cerrado", "car_code": "GO-67890",
                "has_embargo": True, "car_status": "pendente",
            },
            "documents": [
                {"id": 1, "document_type": "matricula"},
                {"id": 2, "document_type": "car"},
                {"id": 3, "document_type": "ccir"},
                {"id": 4, "document_type": "auto_infracao"},
            ],
        },
        chain_data={
            "legislacao": {
                "legislacao_aplicavel": ["Lei 12.651/2012", "Lei 9.605/1998", "Decreto 7.830/2012"],
            },
        },
        llm_payload={
            "situacao_geral": "Imóvel com embargo ativo + pendência CAR + auto de infração.",
            "passivos_identificados": [
                "Embargo ativo IBAMA",
                "CAR pendente SICAR",
                "Auto de infração não defendido",
            ],
            "acoes_remediacao": [
                "Apresentar defesa do auto",
                "Resolver pendência CAR",
                "Solicitar desembargo",
            ],
            "prioridade_acoes": ["defesa_auto_primeiro"],
            "risco_estimado": "alto",
            "observacoes": "Caso urgente — prazo de defesa pode estar correndo.",
        },
        expected_min_sources=7,  # 4 docs + 3 leis
        expected_severidade="alto",
        expected_min_hipoteses=3,
        expected_min_checklist=3,
    ),
    Scenario(
        name="ai_off_rules_based",
        ai_on=False,
        process_data={
            "process": {"id": 42},
            "property": {"has_embargo": True, "car_code": None},
            "documents": [],
        },
        expected_severidade="alto",
        expected_min_hipoteses=2,  # embargo + car_nao_cadastrado
        expected_min_checklist=2,
    ),
]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_diagnostico_e2e_pipeline(scenario: Scenario):
    """Pipeline completo por cenário: AI on/off × densidade documental."""
    agent = DiagnosticoAgent(_ctx(chain_data=scenario.chain_data))

    with ExitStack() as stack:
        _enter_default_patches(stack, process_data=scenario.process_data, ai_on=scenario.ai_on)
        if scenario.ai_on:
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response(scenario.llm_payload or {})
        result = agent.run()

    assert result.success is True, f"falhou em {scenario.name}: {result.error}"
    assert result.requires_review is True
    data = result.data

    # Schema novo presente em ambos os paths
    assert "content" in data
    assert "hipoteses" in data
    assert "lacunas" in data
    assert "checklist_documental" in data
    assert "riscos" in data
    assert "sources" in data
    assert "metadata" in data

    # Sources expected count
    assert len(data["sources"]) >= scenario.expected_min_sources, (
        f"{scenario.name}: esperava ≥{scenario.expected_min_sources} sources, "
        f"achei {len(data['sources'])}: {data['sources']}"
    )

    # Severidade
    if scenario.expected_severidade:
        assert data["risco_estimado"] == scenario.expected_severidade
        assert data["riscos"][0]["severidade"] == scenario.expected_severidade

    # Hipóteses + checklist
    assert len(data["hipoteses"]) >= scenario.expected_min_hipoteses
    assert len(data["checklist_documental"]) >= scenario.expected_min_checklist

    # lacunas = [] em V1 (todos os cenários)
    assert data["lacunas"] == []

    # Dual-emit: chaves antigas presentes
    assert "situacao_geral" in data
    assert "passivos_identificados" in data
    assert "acoes_remediacao" in data
    assert "prioridade_acoes" in data
    assert "risco_estimado" in data
    assert "observacoes" in data

    # Coerência dual-emit ↔ schema
    assert data["situacao_geral"] == "" or data["situacao_geral"] == data["content"] or data["content"].startswith(data["situacao_geral"][:50])
    assert data["passivos_identificados"] == data["hipoteses"]
    assert data["acoes_remediacao"] == data["checklist_documental"]

    # JSON-serializable round-trip
    assert json.loads(json.dumps(data)) == data


def test_rules_based_uses_manual_rules_engine_source():
    """Path A.2 sem IA emite Source(type=manual, ref=rules_engine)."""
    scenario = next(s for s in SCENARIOS if s.name == "ai_off_rules_based")
    agent = DiagnosticoAgent(_ctx(chain_data=scenario.chain_data))

    with ExitStack() as stack:
        _enter_default_patches(stack, process_data=scenario.process_data, ai_on=False)
        result = agent.run()

    sources = result.data["sources"]
    manual_sources = [s for s in sources if s["type"] == "manual"]
    assert any(s["ref"] == "rules_engine" for s in manual_sources)


def test_no_evidence_fallback_logs_warning(caplog):
    """Quando não há documentos NEM legislation, fallback logged como warning."""
    caplog.set_level("WARNING", logger="app.agents.diagnostico")
    agent = DiagnosticoAgent(_ctx())

    with ExitStack() as stack:
        _enter_default_patches(
            stack,
            process_data={"process": {"id": 42}, "property": {}, "documents": []},
            ai_on=True,
        )
        complete = stack.enter_context(patch("app.agents.base.complete"))
        complete.return_value = _make_ai_response({
            "situacao_geral": "Sem evidências documentais.",
            "passivos_identificados": [],
            "acoes_remediacao": [],
            "risco_estimado": "medio",
        })
        result = agent.run()

    msgs = [r.message for r in caplog.records if r.name == "app.agents.diagnostico"]
    assert any("sources_fallback" in m for m in msgs)
    # Validation passou via fallback Source(type=manual, ref=agent_diagnostico)
    sources = result.data["sources"]
    assert any(s["ref"] == "agent_diagnostico" and s["excerpt"] == "no_evidence_available" for s in sources)


def test_metadata_carries_prioridades_and_observacoes():
    agent = DiagnosticoAgent(_ctx())
    with ExitStack() as stack:
        _enter_default_patches(
            stack,
            process_data={"process": {"id": 42}, "property": {}, "documents": []},
            ai_on=True,
        )
        complete = stack.enter_context(patch("app.agents.base.complete"))
        complete.return_value = _make_ai_response({
            "situacao_geral": "x",
            "passivos_identificados": [],
            "acoes_remediacao": [],
            "prioridade_acoes": ["acao_A_primeiro"],
            "observacoes": "obs_text",
            "risco_estimado": "baixo",
        })
        data = agent.run().data

    # Tarefa A Q3: metadata recebe prioridade_acoes + observacoes
    assert data["metadata"]["prioridade_acoes"] == ["acao_A_primeiro"]
    assert data["metadata"]["observacoes"] == "obs_text"
    # Dual-emit também
    assert data["prioridade_acoes"] == ["acao_A_primeiro"]
    assert data["observacoes"] == "obs_text"
