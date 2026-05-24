"""Testes unitários do property_audit — funções puras determinísticas.

Sprint A2 (Onda 2 da Fase 2). Sem DB, sem LLM, sem mocks pesados.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.property_audit import (
    AuditFinding,
    audit_property,
    compare_areas,
    finding_to_issue_type,
    has_geo_incra,
)


class TestCompareAreas:
    def test_iguais_nao_divergem(self):
        cmp = compare_areas(100, 100)
        assert cmp.divergent is False
        assert cmp.diff_ha == Decimal("0")
        assert cmp.diff_pct == Decimal("0")

    def test_diferenca_pequena_dentro_da_tolerancia(self):
        # 100 vs 100.5 = 0.5% < 1% default
        cmp = compare_areas(100, Decimal("100.5"))
        assert cmp.divergent is False

    def test_diferenca_grande_acima_da_tolerancia(self):
        # 120 vs 95 = >20%
        cmp = compare_areas(120, 95)
        assert cmp.divergent is True
        assert cmp.diff_ha == Decimal("25")
        assert cmp.diff_pct > Decimal("0.10")

    @pytest.mark.parametrize("a,b", [(None, 100), (100, None), (None, None), (0, 100), (100, 0)])
    def test_lado_ausente_ou_zero_marcado_como_divergente(self, a, b):
        cmp = compare_areas(a, b)
        assert cmp.divergent is True

    def test_tolerancia_custom(self):
        # 100 vs 102 = 2%. Com tolerância 5%, não diverge.
        cmp = compare_areas(100, 102, tolerance_pct=Decimal("0.05"))
        assert cmp.divergent is False
        # Com tolerância 1% (default), diverge.
        cmp2 = compare_areas(100, 102)
        assert cmp2.divergent is True

    def test_aceita_str_e_float(self):
        cmp = compare_areas("100.0", 100.0)
        assert cmp.divergent is False


class TestHasGeoIncra:
    @pytest.mark.parametrize("text", [
        "Imóvel georreferenciado conforme Lei 10.267/2001",
        "Cadastrado no SIGEF",
        "GEO certificado pelo INCRA — código SIGEF",
        "CNIR ativo",
        "Lei nº 10.267",
    ])
    def test_detecta_mencao(self, text):
        assert has_geo_incra(text) is True

    @pytest.mark.parametrize("text", [
        "Imóvel rural na zona X.",
        "",
        None,
        "Matrícula sem qualquer menção a certificação espacial oficial.",
    ])
    def test_nao_detecta_quando_ausente(self, text):
        assert has_geo_incra(text) is False


class TestAuditPropertyDeterministico:
    def test_property_vazio_nao_levanta_emite_so_finding_de_geom_pendente(self):
        findings = audit_property(property_data={})
        # com property_data sem geom, emite o aviso de geom pendente
        types = [f.type for f in findings]
        assert "verificacao_espacial_pendente" in types

    def test_areas_divergentes_matricula_e_car_gera_finding(self):
        findings = audit_property(property_data={
            "area_documental_ha": 100,
            "car_area_ha": 80,  # 20% diff
            "geom": None,
        })
        area_findings = [f for f in findings if f.type == "area_divergente"]
        assert len(area_findings) >= 1
        # Severidade critical pra diff >= 10%
        assert any(f.severity == "critical" for f in area_findings)

    def test_areas_dentro_da_tolerancia_nao_geram_finding(self):
        findings = audit_property(property_data={
            "area_documental_ha": 100,
            "car_area_ha": 100,
            "geom": object(),  # geom presente — não emite pendente
        })
        area_findings = [f for f in findings if f.type == "area_divergente"]
        assert area_findings == []

    def test_geo_incra_ausente_gera_finding_critical(self):
        findings = audit_property(property_data={
            "matricula_text": "Imóvel rural sem outras menções.",
            "geom": object(),
        })
        geo_findings = [f for f in findings if f.type == "geo_incra_ausente"]
        assert len(geo_findings) == 1
        assert geo_findings[0].severity == "critical"

    def test_geo_incra_presente_nao_gera_finding(self):
        findings = audit_property(property_data={
            "matricula_text": "Imóvel georreferenciado conforme Lei 10.267",
            "geom": object(),
        })
        assert not any(f.type == "geo_incra_ausente" for f in findings)

    def test_rl_divergente_gera_finding_warning(self):
        findings = audit_property(property_data={
            "rl_declared_ha": 50,
            "rl_averbada_ha": 30,
            "geom": object(),
        })
        rl_findings = [f for f in findings if f.type == "rl_divergente"]
        assert len(rl_findings) == 1
        assert rl_findings[0].severity == "warning"

    def test_sem_geom_marca_verificacao_espacial_pendente(self):
        findings = audit_property(property_data={"area_documental_ha": 100, "car_area_ha": 100})
        pendente = [f for f in findings if f.type == "verificacao_espacial_pendente"]
        assert len(pendente) == 1
        assert pendente[0].severity == "info"

    def test_com_geom_nao_marca_verificacao_espacial_pendente(self):
        findings = audit_property(property_data={"geom": object()})
        pendente = [f for f in findings if f.type == "verificacao_espacial_pendente"]
        assert pendente == []

    def test_cruzamento_completo_caso_real(self):
        """Caso composto: matrícula 100ha, CAR 80ha, CCIR 100ha, sem GEO, RL divergente."""
        findings = audit_property(
            property_data={
                "area_documental_ha": 100,
                "car_area_ha": 80,
                "ccir_area_ha": 100,
                "matricula_text": "Matrícula sem certificação espacial.",
                "rl_declared_ha": 20,
                "rl_averbada_ha": 18,  # 10% diff > 1% tolerance
                "geom": None,
            },
        )
        types = sorted(f.type for f in findings)
        # esperado: area_divergente (mat×CAR), area_divergente (CAR×CCIR), geo_incra_ausente,
        # rl_divergente, verificacao_espacial_pendente.
        assert "area_divergente" in types
        assert "geo_incra_ausente" in types
        assert "rl_divergente" in types
        assert "verificacao_espacial_pendente" in types


class TestFindingToIssueType:
    @pytest.mark.parametrize("finding_type,expected", [
        ("area_divergente", "area_divergente"),
        ("rl_divergente", "outro"),
        ("geo_incra_ausente", "outro"),
        ("verificacao_espacial_pendente", "outro"),
        ("tipo_inexistente", "outro"),
    ])
    def test_mapeamento(self, finding_type, expected):
        f = AuditFinding(
            type=finding_type, severity="warning", tema="x",
            descricao="x", impacto="x", evidencia={},
        )
        assert finding_to_issue_type(f) == expected
