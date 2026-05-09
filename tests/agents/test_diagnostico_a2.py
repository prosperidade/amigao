"""Testes da migração do DiagnosticoAgent para DiagnosticoPreliminarContent —
Sprint A2-diagnostico-A.

Cobre:
* A.1 — path IA (execute() com LLM stubado retornando JSON estruturado).
* A.2 — path fallback (_rules_based_diagnosis sem IA).
* Mapeamento risco_estimado (str) → riscos (list[Risco]).
* Cascata de Source (documents → legislation → fallback manual).
* Dual-emit das chaves antigas preservadas no payload.
* metadata["prioridade_acoes"] + metadata["observacoes"].
* lacunas = [] em V1.
* Caminho de erro: input malformado levanta DiagnosticoOutputValidationError.
"""

from __future__ import annotations

import json
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from app.agents.base import AgentContext
from app.agents.diagnostico import (
    DiagnosticoAgent,
    DiagnosticoOutputValidationError,
)


def _make_ai_response(payload: dict | str):
    from app.core.ai_gateway import AIResponse
    content = json.dumps(payload, ensure_ascii=False) if isinstance(payload, dict) else payload
    return AIResponse(
        content=content,
        model_used="mock-model",
        tokens_in=50,
        tokens_out=120,
        cost_usd=0.0001,
        duration_ms=150,
        provider="mock",
    )


def _ctx(*, chain_data: dict | None = None, metadata: dict | None = None) -> AgentContext:
    return AgentContext(
        tenant_id=1,
        user_id=1,
        process_id=42,  # validate_preconditions exige process_id
        session=MagicMock(),
        metadata=metadata or {},
        chain_data=chain_data or {},
    )


def _enter_default_patches(stack: ExitStack):
    """Bypass dos checks de cost + recall_memory (MagicMock truthy bug do A2-redator-C2)."""
    stack.enter_context(patch("app.agents.base.check_tenant_cost_limit"))
    stack.enter_context(patch("app.agents.base.check_tenant_monthly_budget"))
    # _load_process_data faz query real; por padrão retornamos dict vazio
    stack.enter_context(patch.object(
        DiagnosticoAgent, "_load_process_data",
        return_value={"process": {"id": 42}, "property": {}, "documents": []},
    ))
    # recall_memory (MemPalace) — mockar pra evitar MagicMock truthy
    stack.enter_context(patch.object(DiagnosticoAgent, "recall_memory", return_value={}))
    # get_active_prompt → None força fallback hardcoded (mesmo bug do A2-redator-C2)
    stack.enter_context(patch("app.agents.base.get_active_prompt", return_value=None))


@pytest.fixture(autouse=True)
def _isolate_skills(tmp_path, monkeypatch):
    monkeypatch.setattr("app.skills._registry.SKILLS_ROOT", tmp_path)
    from app.skills._registry import invalidate_cache
    invalidate_cache()


# ---------------------------------------------------------------------------
# A.1 — path IA
# ---------------------------------------------------------------------------

class TestPathIA:
    def test_execute_emits_diagnostico_preliminar_content_shape(self):
        agent = DiagnosticoAgent(_ctx())
        llm_payload = {
            "situacao_geral": "Imóvel com pendência no SICAR.",
            "passivos_identificados": ["CAR pendente", "Embargo ativo"],
            "acoes_remediacao": ["Resolver pendência", "Defender auto"],
            "prioridade_acoes": ["resolver_car_primeiro"],
            "risco_estimado": "alto",
            "observacoes": "Caso urgente.",
        }
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response(llm_payload)
            result = agent.run()

        assert result.success is True
        assert result.requires_review is True
        data = result.data

        # campos novos do schema
        assert data["content"] == "Imóvel com pendência no SICAR."
        assert data["hipoteses"] == ["CAR pendente", "Embargo ativo"]
        assert data["lacunas"] == []
        assert data["checklist_documental"] == ["Resolver pendência", "Defender auto"]
        assert len(data["riscos"]) == 1
        assert data["riscos"][0]["severidade"] == "alto"
        assert data["riscos"][0]["descricao"].startswith("Imóvel com pendência")
        # sources fallback (sem documentos nem legislation)
        assert len(data["sources"]) >= 1
        # metadata leva prioridade_acoes + observacoes
        assert data["metadata"]["prioridade_acoes"] == ["resolver_car_primeiro"]
        assert data["metadata"]["observacoes"] == "Caso urgente."

        # dual-emit: chaves antigas preservadas
        assert data["situacao_geral"] == "Imóvel com pendência no SICAR."
        assert data["passivos_identificados"] == ["CAR pendente", "Embargo ativo"]
        assert data["acoes_remediacao"] == ["Resolver pendência", "Defender auto"]
        assert data["prioridade_acoes"] == ["resolver_car_primeiro"]
        assert data["risco_estimado"] == "alto"
        assert data["observacoes"] == "Caso urgente."

    def test_execute_with_documents_in_process_data(self):
        agent = DiagnosticoAgent(_ctx())
        with ExitStack() as stack:
            stack.enter_context(patch("app.agents.base.check_tenant_cost_limit"))
            stack.enter_context(patch("app.agents.base.check_tenant_monthly_budget"))
            stack.enter_context(patch.object(
                DiagnosticoAgent, "_load_process_data",
                return_value={
                    "process": {"id": 42, "demand_type": "car"},
                    "property": {"state": "GO", "biome": "Cerrado"},
                    "documents": [
                        {"id": 1, "document_type": "matricula"},
                        {"id": 2, "document_type": "car"},
                    ],
                },
            ))
            stack.enter_context(patch.object(DiagnosticoAgent, "recall_memory", return_value={}))
            stack.enter_context(patch("app.agents.base.get_active_prompt", return_value=None))
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response({
                "situacao_geral": "OK",
                "passivos_identificados": [],
                "acoes_remediacao": [],
                "risco_estimado": "baixo",
            })
            result = agent.run()

        sources = result.data["sources"]
        types = [s["type"] for s in sources]
        refs = [s["ref"] for s in sources]
        # 2 documentos viraram Source(type="document")
        assert types.count("document") == 2
        assert "1" in refs and "2" in refs

    def test_execute_with_legal_context(self):
        agent = DiagnosticoAgent(
            _ctx(chain_data={"legislacao": {"legislacao_aplicavel": ["Lei 12.651/2012", "Lei 9.605/1998"]}})
        )
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response({
                "situacao_geral": "Análise legal.",
                "passivos_identificados": [],
                "acoes_remediacao": [],
                "risco_estimado": "medio",
            })
            result = agent.run()

        sources = result.data["sources"]
        legislation_refs = [s["ref"] for s in sources if s["type"] == "legislation"]
        assert "Lei 12.651/2012" in legislation_refs
        assert "Lei 9.605/1998" in legislation_refs

    def test_execute_normalizes_invalid_severidade_to_medio(self):
        agent = DiagnosticoAgent(_ctx())
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response({
                "situacao_geral": "x",
                "passivos_identificados": [],
                "acoes_remediacao": [],
                "risco_estimado": "extremo",  # fora do enum
            })
            result = agent.run()
        assert result.data["risco_estimado"] == "medio"
        assert result.data["riscos"][0]["severidade"] == "medio"

    def test_execute_handles_empty_situacao_geral(self):
        """LLM retorna content vazio — payload tem placeholder mínimo (validator não-vazio)."""
        agent = DiagnosticoAgent(_ctx())
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response({
                "situacao_geral": "",
                "passivos_identificados": [],
                "acoes_remediacao": [],
            })
            result = agent.run()
        assert result.success is True
        assert result.data["content"] != ""  # placeholder
        # mas dual-emit preserva o vazio original
        assert result.data["situacao_geral"] == ""


# ---------------------------------------------------------------------------
# A.2 — path fallback (regras sem IA)
# ---------------------------------------------------------------------------

class TestPathRulesBased:
    def _run_with_settings_off(self, *, process_data: dict) -> dict:
        agent = DiagnosticoAgent(_ctx())
        mock_settings = MagicMock()
        mock_settings.ai_configured = False

        with ExitStack() as stack:
            _enter_default_patches(stack)
            stack.enter_context(patch.object(
                DiagnosticoAgent, "_load_process_data",
                return_value=process_data,
            ))
            stack.enter_context(patch("app.core.config.settings", mock_settings))
            result = agent.run()
        assert result.success is True
        return result.data

    def test_rules_based_emits_schema_with_manual_source(self):
        data = self._run_with_settings_off(process_data={
            "process": {"id": 42},
            "property": {"has_embargo": False, "car_code": None},
            "documents": [],
        })
        # Schema novo
        assert data["content"] == "Diagnostico baseado em regras (IA indisponivel)"
        assert data["hipoteses"] == ["CAR nao cadastrado"]
        assert data["checklist_documental"] == ["Realizar inscricao no CAR"]
        assert data["lacunas"] == []
        assert len(data["riscos"]) == 1
        assert data["riscos"][0]["severidade"] == "medio"

        # Source manual rules_engine
        manual_sources = [s for s in data["sources"] if s["type"] == "manual"]
        assert len(manual_sources) >= 1
        assert any(s["ref"] == "rules_engine" for s in manual_sources)

        # Dual-emit
        assert data["passivos_identificados"] == ["CAR nao cadastrado"]
        assert data["risco_estimado"] == "medio"

    def test_rules_based_with_embargo_marks_high_risk(self):
        data = self._run_with_settings_off(process_data={
            "process": {"id": 42},
            "property": {"has_embargo": True, "car_code": "GO-123"},
            "documents": [],
        })
        assert data["risco_estimado"] == "alto"
        assert data["riscos"][0]["severidade"] == "alto"
        assert "Imovel com embargo ativo" in data["passivos_identificados"]


# ---------------------------------------------------------------------------
# Helpers — derivação de Source isoladamente
# ---------------------------------------------------------------------------

class TestSourceDerivation:
    def test_documents_become_document_sources(self):
        agent = DiagnosticoAgent(_ctx())
        sources = agent._derive_sources(
            documents=[{"id": 1, "document_type": "matricula"}, {"id": 2, "document_type": "car"}],
            legal_data={},
            origin="ai",
        )
        types = [s.type for s in sources]
        assert types.count("document") == 2
        assert sources[0].excerpt == "matricula"

    def test_legal_data_becomes_legislation_sources(self):
        agent = DiagnosticoAgent(_ctx())
        sources = agent._derive_sources(
            documents=[],
            legal_data={"legislacao_aplicavel": ["Lei 12.651/2012"]},
            origin="ai",
        )
        assert any(s.type == "legislation" for s in sources)

    def test_caps_documents_at_10_and_legislation_at_5(self):
        agent = DiagnosticoAgent(_ctx())
        sources = agent._derive_sources(
            documents=[{"id": i, "document_type": "x"} for i in range(20)],
            legal_data={"legislacao_aplicavel": [f"Lei {i}/2020" for i in range(20)]},
            origin="ai",
        )
        doc_count = sum(1 for s in sources if s.type == "document")
        leg_count = sum(1 for s in sources if s.type == "legislation")
        assert doc_count == 10
        assert leg_count == 5

    def test_fallback_manual_when_both_empty(self, caplog):
        caplog.set_level("WARNING", logger="app.agents.diagnostico")
        agent = DiagnosticoAgent(_ctx())
        sources = agent._derive_sources(documents=[], legal_data={}, origin="ai")
        assert len(sources) == 1
        assert sources[0].type == "manual"
        assert sources[0].ref == "agent_diagnostico"
        assert sources[0].excerpt == "no_evidence_available"
        # Log warning sinaliza diagnóstico sem evidência documental
        assert any("sources_fallback" in r.message for r in caplog.records)

    def test_skips_documents_without_id(self):
        agent = DiagnosticoAgent(_ctx())
        sources = agent._derive_sources(
            documents=[{"document_type": "x"}, {"id": 1, "document_type": "y"}],
            legal_data={},
            origin="ai",
        )
        # 1 document (apenas id=1) + 0 fallback (já tem source válido)
        doc_sources = [s for s in sources if s.type == "document"]
        assert len(doc_sources) == 1


# ---------------------------------------------------------------------------
# Validation error path
# ---------------------------------------------------------------------------

class TestValidationError:
    def test_invalid_payload_raises_typed_error(self):
        """Forçar ValidationError no schema construtor (test isolado de _build_payload)."""
        agent = DiagnosticoAgent(_ctx())
        # passar sources=[] viola _sources_non_empty validator
        with pytest.raises(DiagnosticoOutputValidationError):
            agent._build_payload(
                situacao_geral="x",
                passivos=[],
                acoes=[],
                prioridades=[],
                risco_estimado="medio",
                observacoes="",
                sources=[],  # vazio — viola schema
            )


# ---------------------------------------------------------------------------
# JSON-serializability + lacunas log INFO
# ---------------------------------------------------------------------------

class TestSerializability:
    def test_payload_round_trip_via_json(self):
        agent = DiagnosticoAgent(_ctx())
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response({
                "situacao_geral": "ok",
                "passivos_identificados": ["a", "b"],
                "acoes_remediacao": ["x"],
                "risco_estimado": "alto",
                "observacoes": "obs",
            })
            data = agent.run().data
        text = json.dumps(data)
        rebuilt = json.loads(text)
        assert rebuilt == data


class TestLacunasLogInfo:
    def test_logs_info_about_empty_lacunas(self, caplog):
        caplog.set_level("INFO", logger="app.agents.diagnostico")
        agent = DiagnosticoAgent(_ctx())
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response({
                "situacao_geral": "ok",
                "passivos_identificados": [],
                "acoes_remediacao": [],
                "risco_estimado": "baixo",
            })
            agent.run()
        msgs = [r.message for r in caplog.records if r.name == "app.agents.diagnostico"]
        assert any("lacunas_empty" in m for m in msgs)
