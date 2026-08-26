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
    """PROMPT_5: findings_raw passou de `type`/`severity` para
    `codigo_alerta`/`familia`/`grade` (taxonomia rica). `grade` é o único
    eixo de severidade (4 níveis)."""

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
        # findings_raw carregam codigo_alerta + familia (PROMPT_5)
        raw_codigos = [f["codigo_alerta"] for f in data["findings_raw"]]
        assert "AREA_MATRICULA_X_CAR" in raw_codigos
        raw_familias = [f["familia"] for f in data["findings_raw"]]
        assert "area" in raw_familias

    def test_payload_marca_metodo_deterministic_tools(self):
        agent = AuditorImovelAgent(_ctx())
        with ExitStack() as stack:
            _enter_default_patches(stack)
            data = agent.run().data
        assert data["method"] == "deterministic_tools"
        assert data["requires_review"] is True

    def test_sem_geom_nao_levanta_e_NAO_emite_pendente(self):
        # ADR-020 (anti-regressão): sem geom o auditor roda normal, reporta
        # geom_present=False no payload, mas NÃO emite mais o finding/issue
        # VERIFICACAO_ESPACIAL_PENDENTE — virou nota derivada na leitura.
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
        raw_codigos = [f["codigo_alerta"] for f in data["findings_raw"]]
        assert "VERIFICACAO_ESPACIAL_PENDENTE" not in raw_codigos

    def test_geo_incra_ausente_aparece_no_payload(self):
        agent = AuditorImovelAgent(_ctx())
        with ExitStack() as stack:
            _enter_default_patches(stack, property_overrides={
                "matricula_text": "Matrícula sem certificação espacial.",
                "geom": object(),
            })
            data = agent.run().data
        raw_codigos = [f["codigo_alerta"] for f in data["findings_raw"]]
        assert "GEO_AUSENTE" in raw_codigos
        # grade=critico (4 níveis — sem severity 3-níveis)
        geo_finding = next(f for f in data["findings_raw"] if f["codigo_alerta"] == "GEO_AUSENTE")
        assert geo_finding["grade"] == "critico"
        assert geo_finding["familia"] == "geo_incra"

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


class TestRegistralFindingsFromMatriz:
    """ADR-062, item 4 — o achado de matrícula×CCIR/SIGEF/ITR/CAR nasce da
    matriz de inconsistências, não mais de `generate_acoes_from_divergencias`
    (consolidação). Testa a tradução pura (`MatrixRow` serializado → `AuditFinding`),
    sem DB — a comparação em si é responsabilidade de `inconsistency_matrix`."""

    def _agent(self):
        return AuditorImovelAgent(_ctx())

    def test_denominacao_divergente_vira_finding_do_catalogo(self):
        matriz = {"linhas": [
            {"item": "denominacao_imovel", "label": "Denominação do imóvel",
             "situacao": "divergente", "fontes": {"matricula": "Fazenda X", "ccir": "Fazenda Y"}},
        ]}
        findings = self._agent()._registral_findings_from_matriz(matriz)
        assert len(findings) == 1
        f = findings[0]
        assert f.codigo_alerta == "IDENT_NOME_IMOVEL_DIVERGENTE"
        assert f.familia == "identificacao"
        assert f.grade == "atencao"
        assert set(f.documentos_cruzados) == {"Matricula", "CCIR"}

    def test_codigo_incra_sncr_divergente_vira_finding_do_catalogo(self):
        matriz = {"linhas": [
            {"item": "codigo_incra_sncr", "label": "Código INCRA/SNCR",
             "situacao": "atencao", "fontes": {"ccir": "111", "itr": "222"}},
        ]}
        findings = self._agent()._registral_findings_from_matriz(matriz)
        assert len(findings) == 1
        assert findings[0].codigo_alerta == "IDENT_CODIGO_INCRA_SNCR_DIVERGENTE"

    def test_linha_consistente_nao_vira_finding(self):
        matriz = {"linhas": [
            {"item": "denominacao_imovel", "label": "Denominação do imóvel",
             "situacao": "consistente", "fontes": {"matricula": "Fazenda X"}},
        ]}
        assert self._agent()._registral_findings_from_matriz(matriz) == []

    def test_item_fora_do_catalogo_e_ignorado_nao_duplica(self):
        """`area_matricula:*` já tem emissor próprio (`property_audit.
        AREA_MATRICULA_X_*`) — não é redirecionado daqui para não duplicar."""
        matriz = {"linhas": [
            {"item": "area_matricula:2923", "label": "Área — matrícula 2923 (ha)",
             "situacao": "divergente", "fontes": {"matricula": 100, "ccir": 90}},
        ]}
        assert self._agent()._registral_findings_from_matriz(matriz) == []

    def test_matriz_vazia_ou_ausente_nao_quebra(self):
        agent = self._agent()
        assert agent._registral_findings_from_matriz({}) == []
        assert agent._registral_findings_from_matriz({"linhas": []}) == []
        assert agent._registral_findings_from_matriz(None) == []


class TestExecuteRedirecionaMatrizParaAchado:
    def test_findings_da_matriz_entram_no_payload(self):
        agent = AuditorImovelAgent(_ctx())
        with ExitStack() as stack:
            _enter_default_patches(stack)
            stack.enter_context(patch.object(
                AuditorImovelAgent, "_build_matriz_inconsistencias",
                return_value={"linhas": [
                    {"item": "denominacao_imovel", "label": "Denominação do imóvel",
                     "situacao": "divergente", "fontes": {"matricula": "X", "ccir": "Y"}},
                ]},
            ))
            data = agent.run().data
        raw_codigos = [f["codigo_alerta"] for f in data["findings_raw"]]
        assert "IDENT_NOME_IMOVEL_DIVERGENTE" in raw_codigos


class TestNaoTocaDiagnostico:
    """Garantia arquitetural: A2 NÃO importa nada de diagnostico.py (escopo do A3)."""

    def test_modulo_nao_importa_diagnostico(self):
        import inspect

        import app.agents.auditor_imovel as mod
        source = inspect.getsource(mod)
        assert "from app.agents.diagnostico" not in source
        assert "import app.agents.diagnostico" not in source
