"""Testes do AuditorImovelAgent — Sprint A2 (Onda 2 da Fase 2).

Foco em integração agente↔tools determinísticas. A matemática profunda fica
em tests/services/test_property_audit.py (puro).
"""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from app.agents.auditor_imovel import AuditorImovelAgent
from app.agents.base import AgentContext


def _ctx(*, chain_data: dict | None = None) -> AgentContext:
    return AgentContext(
        tenant_id=1,
        user_id=1,
        process_id=42,
        session=MagicMock(),
        metadata={},
        chain_data=chain_data or {},
    )


def _enter_default_patches(stack: ExitStack, property_overrides: dict | None = None):
    stack.enter_context(patch("app.agents.base.check_tenant_cost_limit"))
    stack.enter_context(patch("app.agents.base.check_tenant_monthly_budget"))
    stack.enter_context(patch("app.agents.base.get_active_prompt", return_value=None))
    base_property = {"id": 99, "geom": None}
    if property_overrides:
        base_property.update(property_overrides)
    stack.enter_context(patch.object(
        AuditorImovelAgent, "_load_process_data",
        return_value={
            "process": {"id": 42},
            "property": base_property,
            "documents": [],
        },
    ))
    # Bypass do persist_issues (não testamos DB aqui)
    stack.enter_context(patch.object(
        AuditorImovelAgent, "_persist_issues",
        return_value=[101, 102],
    ))


class TestAgenteRegistro:
    def test_agente_registrado_no_registry(self):
        from app.agents.base import AgentRegistry
        assert AgentRegistry.get("auditor_imovel") is AuditorImovelAgent

    def test_validate_preconditions_exige_process_id(self):
        ctx = AgentContext(
            tenant_id=1, user_id=1, process_id=None,
            session=MagicMock(), metadata={}, chain_data={},
        )
        agent = AuditorImovelAgent(ctx)
        with pytest.raises(ValueError, match="process_id"):
            agent.validate_preconditions()


class TestExecuteSemLLM:
    def test_areas_divergentes_emitem_divergencia_no_payload(self):
        agent = AuditorImovelAgent(_ctx())
        with ExitStack() as stack:
            _enter_default_patches(stack, property_overrides={
                "area_documental_ha": 100,
                "car_area_ha": 80,
                "geom": None,
            })
            result = agent.run()

        assert result.success is True
        assert result.requires_review is True
        data = result.data
        # tem pelo menos 1 divergência de área
        areas = [d for d in data["divergencias"] if "área" in d["tema"]]
        assert len(areas) >= 1
        # e tem raw findings com type='area_divergente'
        raw_types = [f["type"] for f in data["findings_raw"]]
        assert "area_divergente" in raw_types

    def test_payload_marca_metodo_deterministic_tools(self):
        agent = AuditorImovelAgent(_ctx())
        with ExitStack() as stack:
            _enter_default_patches(stack)
            data = agent.run().data
        assert data["method"] == "deterministic_tools"
        assert data["requires_review"] is True

    def test_sem_geom_nao_levanta_e_marca_pendente(self):
        agent = AuditorImovelAgent(_ctx())
        with ExitStack() as stack:
            _enter_default_patches(stack, property_overrides={
                "area_documental_ha": 100,
                "car_area_ha": 100,  # iguais — sem area_divergente
                "geom": None,
            })
            result = agent.run()

        assert result.success is True
        data = result.data
        assert data["geom_present"] is False
        raw_types = [f["type"] for f in data["findings_raw"]]
        assert "verificacao_espacial_pendente" in raw_types

    def test_geo_incra_ausente_aparece_no_payload(self):
        agent = AuditorImovelAgent(_ctx())
        with ExitStack() as stack:
            _enter_default_patches(stack, property_overrides={
                "matricula_text": "Matrícula sem certificação espacial.",
                "geom": object(),
            })
            data = agent.run().data
        raw_types = [f["type"] for f in data["findings_raw"]]
        assert "geo_incra_ausente" in raw_types
        # severidade critical no raw findings
        geo_finding = next(f for f in data["findings_raw"] if f["type"] == "geo_incra_ausente")
        assert geo_finding["severity"] == "critical"

    def test_payload_inclui_contagem_e_descricao(self):
        agent = AuditorImovelAgent(_ctx())
        with ExitStack() as stack:
            _enter_default_patches(stack, property_overrides={
                "area_documental_ha": 100,
                "car_area_ha": 50,  # 50% diff
                "matricula_text": "sem geo",
                "geom": None,
            })
            data = agent.run().data
        # content sumariza N divergencias
        assert "divergência" in data["content"].lower()
        # divergências, findings_raw, issue_ids são populados
        assert len(data["divergencias"]) >= 2
        assert data["issue_ids"] == [101, 102]  # do mock


class TestNaoTocaDiagnostico:
    """Garantia arquitetural: A2 NÃO importa nada de diagnostico.py (escopo do A3)."""

    def test_modulo_nao_importa_diagnostico(self):
        import app.agents.auditor_imovel as mod
        import inspect
        source = inspect.getsource(mod)
        assert "from app.agents.diagnostico" not in source
        assert "import app.agents.diagnostico" not in source
