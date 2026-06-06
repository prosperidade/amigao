"""Fase 2 robusta — "DEPOIS": com a classificação corrigida (certidão 6776 →
matricula, não sigef), as DUAS matrículas chegam ao staging e a matriz passa a
mostrar a denominação DIVERGENTE. Valores reais do caso São Jorge.

Antes: 6776 caía em sigef → denominação vinha de 1 fonte só → "consistente".
Depois: 4698 e 6776 são `matricula` → denominação divergente entre as fontes.
"""

from types import SimpleNamespace

from app.services.inconsistency_matrix import build_matrix


def _row(source_doc_type, field_name, value, *, matricula_hint=None, unidade=None):
    fv = {"value": value}
    if unidade:
        fv["unidade"] = unidade
    return SimpleNamespace(
        source_doc_type=source_doc_type, field_name=field_name,
        field_value=fv, matricula_hint=matricula_hint, status="pendente",
    )


def _staging_depois():
    """Staging como o pipeline CORRIGIDO produz (ambas certidões = matricula)."""
    return [
        # matrícula 4698 (Lote 1B) — "FAZENDA SÃO JORGE - GLEBA 01 B"
        _row("matricula", "area_registrada_ha", "660,6561", matricula_hint="4698", unidade="ha"),
        _row("matricula", "denominacao", "Fazenda São Jorge - Gleba 01 B", matricula_hint="4698"),
        # matrícula 6776 (Lote 1C) — registrada como "Shangri-lá (Parte 2)" (antes ia p/ sigef)
        _row("matricula", "area_registrada_ha", "349,9022", matricula_hint="6776", unidade="ha"),
        _row("matricula", "denominacao", "Fazenda Shangri-lá (Parte 2)", matricula_hint="6776"),
        # RAT (parecer) — área do imóvel + pendências
        _row("rat", "area_vetorizada_ha", 1010.7113, unidade="ha"),
        _row("rat", "pendencias_rat", [
            {"categoria": "Unidades de Conservação",
             "detalhamento": "sobreposição do imóvel com Unidade de Conservação",
             "recomendacao": "esclarecer"},
        ]),
    ]


def _by_item(matriz):
    return {ln["item"]: ln for ln in matriz["linhas"]}


def test_denominacao_divergente_com_as_duas_matriculas():
    matriz = build_matrix(_staging_depois()).matriz
    lin = _by_item(matriz)["denominacao_imovel"]
    assert lin["situacao"] == "divergente"
    # as duas variações reais aparecem, cada uma na sua fonte (matrícula)
    valores = " | ".join(str(v).lower() for v in lin["fontes"].values())
    assert "gleba 01 b" in valores
    assert "shangri" in valores


def test_area_multi_fonte_aparece():
    """Com as 2 matrículas + RAT, a área vira linha (antes nem aparecia)."""
    matriz = build_matrix(_staging_depois()).matriz
    lin = _by_item(matriz)["area_total"]
    assert lin["fontes"]["soma_matriculas"] == 1010.5583
    assert lin["fontes"]["rat"] == 1010.7113
    assert lin["situacao"] in ("divergente", "atencao")
