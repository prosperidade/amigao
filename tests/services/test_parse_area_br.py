"""Item 1 (validação Isis 16/06) — parse de área BR definitivo + golden tests.

parse_area_ha é a porta ÚNICA de conversão de área. Estes goldens travam TODOS
os formatos reais do staging para que a regressão "1.010,7113 → 1,0107113" (ponto
de milhar lido como decimal) nunca mais passe. Também cobre a defesa relativa da
matriz (área de imóvel « soma das matrículas = artefato de parse, não passivo).
"""

from types import SimpleNamespace

import pytest

from app.services.inconsistency_matrix import (
    build_matrix,
    is_area_plausible,
    parse_area_ha,
)

# --- parse_area_ha: golden de TODOS os formatos de entrada ------------------

@pytest.mark.parametrize(
    "entrada,esperado",
    [
        # STRING CRUA formato BR (o que faltava no golden do #71 — a regressão real)
        ("1.010,7113", 1010.7113),
        ("660,6561", 660.6561),
        ("3.502.445,851", 3502445.851),
        ("349,9022", 349.9022),
        ("58,7654", 58.7654),
        # US / limpo
        ("660.6561", 660.6561),
        ("1010.7113", 1010.7113),
        # com unidade (m² → ha; ha é no-op)
        ("660,6561 ha", 660.6561),
        ("6.606.561,00 m²", 660.6561),
        # número já tipado
        (660.6561, 660.6561),
        (1010, 1010.0),
        # dict serializado {value:...} (envelope do #72)
        ({"value": 349.9022, "confidence": "high"}, 349.9022),
        ({"value": "1.010,7113"}, 1010.7113),
    ],
)
def test_parse_area_ha_formatos(entrada, esperado):
    out = parse_area_ha(entrada)
    assert out == pytest.approx(esperado, rel=1e-9)


def test_parse_area_ha_unidade_m2_explicita():
    # unidade marcada separada do valor
    assert parse_area_ha("6606561,00", "m²") == pytest.approx(660.6561, rel=1e-9)


@pytest.mark.parametrize("lixo", [None, "", "-", ",", ".", [], {}, ["x"], True, "n/a"])
def test_parse_area_ha_rejeita_nao_numerico(lixo):
    assert parse_area_ha(lixo) is None


def test_regressao_milhar_br_nao_vira_decimal():
    """A regressão exata da Isis: '1.010,7113' jamais pode virar 1,0107113."""
    out = parse_area_ha("1.010,7113")
    assert out == pytest.approx(1010.7113, rel=1e-9)
    assert out > 1000  # nunca ~1 ha


# --- ordem de grandeza ------------------------------------------------------

@pytest.mark.parametrize("ha,ok", [
    (0.1, True), (660.6561, True), (100000.0, True),
    (0.05, False), (100000.1, False), (3500000.0, False), (None, False),
])
def test_is_area_plausible(ha, ok):
    assert is_area_plausible(ha) is ok


# --- matriz: defesa relativa (imóvel « soma das matrículas) -----------------

def _row(source_doc_type, field_name, value, *, matricula_hint=None):
    return SimpleNamespace(
        source_doc_type=source_doc_type, field_name=field_name,
        field_value={"value": value, "unidade": "ha"}, matricula_hint=matricula_hint,
        status="pendente", document_id=None,
    )


def test_imovel_implausivelmente_menor_vira_revisao_nao_passivo():
    """Caso real Isis: RAT do imóvel veio 1,0107113 (separador de milhar perdido
    no extrator) enquanto a soma das matrículas é ~1010 ha. Isso NÃO pode virar
    'divergência de área de ~1010 ha' — é artefato de parse → linha de revisão."""
    rows = [
        _row("matricula", "area_registrada_ha", "660,6561", matricula_hint="4698"),
        _row("matricula", "area_registrada_ha", "349,9022", matricula_hint="6776"),
        # RAT (imóvel) mal-parseado: ~1 ha em vez de 1010,7113
        _row("rat", "area_vetorizada_ha", 1.0107113),
    ]
    matriz = build_matrix(rows).matriz
    itens = {ln["item"]: ln for ln in matriz["linhas"]}
    # NÃO existe falsa divergência de área total
    assert "area_total" not in itens or itens["area_total"]["situacao"] != "divergente"
    # existe linha de revisão sinalizando o artefato de parse
    assert "area_revisao" in itens
    assert itens["area_revisao"]["situacao"] == "atencao"


def test_imovel_coerente_com_soma_nao_dispara_revisao():
    """Quando o RAT vem correto (1010,7113), confere com a soma — sem revisão."""
    rows = [
        _row("matricula", "area_registrada_ha", "660,6561", matricula_hint="4698"),
        _row("matricula", "area_registrada_ha", "349,9022", matricula_hint="6776"),
        _row("rat", "area_vetorizada_ha", "1.010,5583"),
    ]
    matriz = build_matrix(rows).matriz
    itens = {ln["item"]: ln for ln in matriz["linhas"]}
    assert "area_revisao" not in itens
    assert itens["area_total"]["situacao"] == "consistente"
