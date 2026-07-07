"""Testes unitários do property_audit — funções puras determinísticas.

Sprint A2 (Onda 2 da Fase 2). Sem DB, sem LLM, sem mocks pesados.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.property_audit import (
    GRADE_ALTO,
    GRADE_ATENCAO,
    GRADE_CRITICO,
    GRADE_INFORMATIVO,
    audit_property,
    compare_areas,
    grade_area_divergence,
    grade_overlap_severity,
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
    """PROMPT_5 Onda A: filtros por `codigo_alerta`/`familia` (taxonomia rica)
    em vez do `type` genérico antigo. `grade` é o único eixo de severidade
    (4 níveis) — saiu `severity` de 3 níveis do AuditFinding."""

    def test_property_vazio_nao_levanta_e_nao_emite_geom_pendente(self):
        # ADR-020: property vazio sem geom NÃO emite mais nada — a "verificação
        # espacial pendente" virou nota derivada na leitura, não finding.
        findings = audit_property(property_data={})
        codigos = [f.codigo_alerta for f in findings]
        assert "VERIFICACAO_ESPACIAL_PENDENTE" not in codigos
        assert findings == []

    def test_areas_divergentes_matricula_e_car_gera_finding(self):
        findings = audit_property(property_data={
            "area_documental_ha": 100,
            "car_area_ha": 80,  # 20% diff
            "geom": None,
        })
        area_findings = [f for f in findings if f.familia == "area"]
        assert len(area_findings) >= 1
        # 20% diff → grade=critico (>10%)
        assert any(f.grade == GRADE_CRITICO for f in area_findings)
        # codigo_alerta específico do par matrícula × CAR
        assert any(f.codigo_alerta == "AREA_MATRICULA_X_CAR" for f in area_findings)

    def test_areas_dentro_da_tolerancia_emitem_finding_informativo(self):
        """Onda C: SEMPRE emite finding. Áreas iguais (Δ=0) viram informativo,
        não são suprimidas — auditoria sabe que o cruzamento foi feito."""
        findings = audit_property(property_data={
            "area_documental_ha": 100,
            "car_area_ha": 100,
            "geom": object(),  # geom presente — não emite pendente
        })
        area_findings = [f for f in findings if f.familia == "area"]
        # 1 cruzamento possível: matrícula × CAR (CCIR/ITR são None → skipping).
        assert len(area_findings) == 1
        assert area_findings[0].grade == GRADE_INFORMATIVO
        assert area_findings[0].codigo_alerta == "AREA_MATRICULA_X_CAR"
        assert area_findings[0].documentos_cruzados == ["Matricula", "CAR"]

    def test_geo_incra_ausente_gera_finding_critico(self):
        findings = audit_property(property_data={
            "matricula_text": "Imóvel rural sem outras menções.",
            "geom": object(),
        })
        geo_findings = [f for f in findings if f.codigo_alerta == "GEO_AUSENTE"]
        assert len(geo_findings) == 1
        assert geo_findings[0].grade == GRADE_CRITICO
        assert geo_findings[0].familia == "geo_incra"

    def test_geo_incra_presente_nao_gera_finding(self):
        findings = audit_property(property_data={
            "matricula_text": "Imóvel georreferenciado conforme Lei 10.267",
            "geom": object(),
        })
        assert not any(f.codigo_alerta == "GEO_AUSENTE" for f in findings)

    def test_rl_divergente_gera_finding_ambiental(self):
        findings = audit_property(property_data={
            "rl_declared_ha": 50,
            "rl_averbada_ha": 30,
            "geom": object(),
        })
        rl_findings = [f for f in findings if f.codigo_alerta == "RL_MATRICULA_DIVERGENTE_RL_CAR"]
        assert len(rl_findings) == 1
        assert rl_findings[0].familia == "ambiental"
        # 40% diff → critico pela régua
        assert rl_findings[0].grade == GRADE_CRITICO

    def test_sem_geom_NAO_emite_verificacao_espacial_pendente(self):
        # ADR-020 (anti-regressão): sem geom NÃO vira mais finding/issue — a nota
        # "verificação espacial pendente" é derivada na leitura (endpoint).
        findings = audit_property(property_data={"area_documental_ha": 100, "car_area_ha": 100})
        pendente = [f for f in findings if f.codigo_alerta == "VERIFICACAO_ESPACIAL_PENDENTE"]
        assert pendente == []

    def test_com_geom_nao_marca_verificacao_espacial_pendente(self):
        findings = audit_property(property_data={"geom": object()})
        pendente = [f for f in findings if f.codigo_alerta == "VERIFICACAO_ESPACIAL_PENDENTE"]
        assert pendente == []

    def test_cruzamento_completo_caso_real(self):
        """Caso composto: matrícula 100ha, CAR 80ha, CCIR 100ha, sem GEO,
        RL divergente. PROMPT_5: cada par tem codigo_alerta próprio."""
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
        codigos = sorted({f.codigo_alerta for f in findings})
        # esperado: pares matrícula × CAR, matrícula × CCIR, CAR × CCIR (área);
        # GEO_AUSENTE; RL_MATRICULA_DIVERGENTE_RL_CAR.
        assert "AREA_MATRICULA_X_CAR" in codigos
        assert "AREA_MATRICULA_X_CCIR" in codigos
        assert "AREA_CAR_X_CCIR" in codigos
        assert "GEO_AUSENTE" in codigos
        assert "RL_MATRICULA_DIVERGENTE_RL_CAR" in codigos
        # ADR-020: geom None NÃO emite mais o pendente (virou nota derivada).
        assert "VERIFICACAO_ESPACIAL_PENDENTE" not in codigos


class TestFindingToIssueTypeRemoved:
    """PROMPT_5: `_FINDING_TO_ISSUE_TYPE` / `finding_to_issue_type` removidos.
    Agora cada AuditFinding.codigo_alerta vai DIRETO para
    RegulatoryIssue.codigo_alerta (FK no catálogo). Sem mapeamento intermediário."""

    def test_finding_to_issue_type_nao_existe_mais(self):
        from app.services import property_audit
        assert not hasattr(property_audit, "finding_to_issue_type")
        assert not hasattr(property_audit, "_FINDING_TO_ISSUE_TYPE")


# ---------------------------------------------------------------------------
# Onda C — Régua de 4 faixas para divergência de área
# ---------------------------------------------------------------------------

class TestGradeAreaDivergence:
    """Régua de 4 faixas (validada pela sócia)."""

    @pytest.mark.parametrize("diff_pct,expected", [
        (Decimal("0"), GRADE_INFORMATIVO),
        (Decimal("0.005"), GRADE_INFORMATIVO),    # 0.5%
        (Decimal("0.01"), GRADE_INFORMATIVO),     # exato 1%, ainda dentro
        (Decimal("0.011"), GRADE_ATENCAO),        # 1.1% → atencao
        (Decimal("0.03"), GRADE_ATENCAO),         # 3%
        (Decimal("0.05"), GRADE_ATENCAO),         # exato 5%, ainda atencao
        (Decimal("0.051"), GRADE_ALTO),           # 5.1% → alto
        (Decimal("0.08"), GRADE_ALTO),            # 8%
        (Decimal("0.10"), GRADE_ALTO),            # exato 10%, ainda alto
        (Decimal("0.101"), GRADE_CRITICO),        # 10.1% → critico
        (Decimal("0.50"), GRADE_CRITICO),         # 50%
        (Decimal("2.0"), GRADE_CRITICO),          # 200%
    ])
    def test_faixas(self, diff_pct, expected):
        assert grade_area_divergence(diff_pct) == expected

    def test_dado_ausente_vira_atencao(self):
        """diff_pct=None → atencao (não consigo cruzar; precisa do dado faltante)."""
        assert grade_area_divergence(None) == GRADE_ATENCAO

    def test_tolerancia_configuravel_aperta(self):
        """Tolerância 0.5% → 1% vira atencao (em vez de informativo)."""
        assert grade_area_divergence(Decimal("0.005"), tolerance_pct=Decimal("0.005")) == GRADE_INFORMATIVO
        # 1% com tolerância 0.5% deveria virar atencao (passa do limite info)
        assert grade_area_divergence(Decimal("0.01"), tolerance_pct=Decimal("0.005")) == GRADE_ATENCAO

    def test_tolerancia_configuravel_relaxa(self):
        """Tolerância 5% → diferença 3% vira informativo (em vez de atencao)."""
        assert grade_area_divergence(Decimal("0.03"), tolerance_pct=Decimal("0.05")) == GRADE_INFORMATIVO


class TestGradeOverlapSeverity:
    def test_sobreposicao_eh_sempre_critico(self):
        """Independente do percentual ou da área — sobreposição com terceiro/UC/
        assentamento/terra pública/matrícula vizinha é sempre `critico`."""
        assert grade_overlap_severity() == GRADE_CRITICO


class TestAuditPropertySempreEmiteFinding:
    """Onda C: a régua substituiu o filtro `if divergent`. Toda comparação
    de área com pelo menos um lado disponível produz finding."""

    def test_areas_iguais_emitem_informativo(self):
        findings = audit_property(property_data={
            "area_documental_ha": 100,
            "car_area_ha": 100,
            "geom": object(),
        })
        area = [f for f in findings if f.familia == "area"]
        assert len(area) == 1
        # PROMPT_5: grade é o único eixo (4 níveis). Saiu severity 3-níveis.
        assert area[0].grade == GRADE_INFORMATIVO

    def test_diferenca_3pct_vira_atencao(self):
        findings = audit_property(property_data={
            "area_documental_ha": 100,
            "car_area_ha": 97,  # 3% diff
            "geom": object(),
        })
        area = [f for f in findings if f.familia == "area"]
        assert area[0].grade == GRADE_ATENCAO

    def test_diferenca_8pct_vira_alto(self):
        findings = audit_property(property_data={
            "area_documental_ha": 100,
            "car_area_ha": 92,  # 8% diff
            "geom": object(),
        })
        area = [f for f in findings if f.familia == "area"]
        assert area[0].grade == GRADE_ALTO

    def test_diferenca_20pct_vira_critico(self):
        findings = audit_property(property_data={
            "area_documental_ha": 100,
            "car_area_ha": 80,  # 20% diff
            "geom": object(),
        })
        area = [f for f in findings if f.familia == "area"]
        assert area[0].grade == GRADE_CRITICO

    def test_um_lado_ausente_nao_gera_finding_de_divergencia(self):
        """Dado ausente em um lado NÃO vira finding de `area_divergente` — não
        há cruzamento real. A detecção de documento faltante fica em domínio
        próprio (TODO sprint posterior, quando a sócia validar o conjunto
        canônico de documentos esperados por demand_type)."""
        findings = audit_property(property_data={
            "area_documental_ha": 100,
            "car_area_ha": None,
            "geom": object(),
        })
        area = [f for f in findings if f.familia == "area"]
        # Nenhum par tem AMBOS os lados → zero findings de area_divergente.
        assert area == []

    def test_tolerancia_custom_relaxa_a_classificacao(self):
        """Mesma diferença, tolerância diferente → grau diferente."""
        # 2% diff: default 1% → atencao
        findings_default = audit_property(property_data={
            "area_documental_ha": 100, "car_area_ha": 98, "geom": object(),
        })
        area_default = [f for f in findings_default if f.familia == "area"][0]
        assert area_default.grade == GRADE_ATENCAO

        # Mesmo 2% com tolerância 5% → informativo
        findings_relaxed = audit_property(
            property_data={"area_documental_ha": 100, "car_area_ha": 98, "geom": object()},
            tolerance_pct=Decimal("0.05"),
        )
        area_relaxed = [f for f in findings_relaxed if f.familia == "area"][0]
        assert area_relaxed.grade == GRADE_INFORMATIVO
        # Evidencia carrega a tolerância usada (auditável)
        assert area_relaxed.evidencia["tolerance_pct_used"] == "0.05"

    def test_evidencia_inclui_tolerance_pct_usado(self):
        findings = audit_property(property_data={
            "area_documental_ha": 100, "car_area_ha": 92, "geom": object(),
        })
        area = [f for f in findings if f.familia == "area"][0]
        assert "tolerance_pct_used" in area.evidencia
        assert area.evidencia["tolerance_pct_used"] == "0.01"  # default


class TestCcirExercicioAnterior:
    """Fase 0 (gap-analysis Ficha 07, item 8) — CCIR é documento ANUAL; o
    catálogo já tinha o código CCIR_EXERCICIO_ANTERIOR (regulatory_catalog_seed),
    faltava o emissor determinístico."""

    def test_exercicio_defasado_emite_finding(self):
        findings = audit_property(
            property_data={"exercicio_ccir": 2024},
            ano_corrente=2026,
        )
        ccir = [f for f in findings if f.codigo_alerta == "CCIR_EXERCICIO_ANTERIOR"]
        assert len(ccir) == 1
        assert ccir[0].familia == "fiscal"
        assert ccir[0].grade == GRADE_ATENCAO
        assert ccir[0].evidencia == {"exercicio_ccir": 2024, "ano_corrente": 2026}

    def test_exercicio_vigente_nao_emite_finding(self):
        findings = audit_property(
            property_data={"exercicio_ccir": 2026},
            ano_corrente=2026,
        )
        assert [f for f in findings if f.codigo_alerta == "CCIR_EXERCICIO_ANTERIOR"] == []

    def test_sem_exercicio_ccir_nao_emite_finding(self):
        findings = audit_property(property_data={}, ano_corrente=2026)
        assert [f for f in findings if f.codigo_alerta == "CCIR_EXERCICIO_ANTERIOR"] == []

    def test_sem_ano_corrente_nao_emite_finding(self):
        """`ano_corrente` é explícito (função pura) — sem ele, nunca compara."""
        findings = audit_property(property_data={"exercicio_ccir": 2020})
        assert [f for f in findings if f.codigo_alerta == "CCIR_EXERCICIO_ANTERIOR"] == []
