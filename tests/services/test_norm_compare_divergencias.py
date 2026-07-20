"""Forense caso Isis — normalização de comparação de divergências (skill da Isis).

O matcher normaliza ANTES de comparar (casefold, acentos, apóstrofos, pontuação,
espaços, abreviações de logradouro, UF de município). "SÃO JOÃO D'ALIANÇA" ≡
"São João d'Aliança" ≡ "São João D'aliança-GO" NÃO é divergência. Diferença de
conteúdo real (Lote×Gleba) permanece divergência.
"""

from types import SimpleNamespace

from app.services.inconsistency_matrix import build_matrix, norm_compare
from app.services.staging_consolidation import _group_conflict_values

# ── norm_compare (unidade) ────────────────────────────────────────────────

def test_municipio_variantes_do_relatorio_da_isis_colapsam():
    # As três grafias EXATAS que apareceram no relatório dela.
    a = norm_compare("SÃO JOÃO D'ALIANÇA", field="municipality")
    b = norm_compare("São João d'Aliança", field="municipality")
    c = norm_compare("São João D'aliança-GO", field="municipality")
    assert a == b == c == "sao joao dalianca"


def test_municipio_descola_uf_no_fim_mas_preserva_nome():
    assert norm_compare("Goiânia-GO", field="municipality") == "goiania"
    # sem sufixo de UF em campo que não é município: mantém tudo
    assert norm_compare("São João D'aliança-GO", field="denominacao") == "sao joao dalianca go"


def test_denominacao_grafia_equivalente_colapsa_mas_conteudo_distinto_nao():
    assert norm_compare("Fazenda São Jorge", field="denominacao") == \
        norm_compare("FAZENDA SAO JORGE", field="denominacao")
    # Lote 1 B vs Gleba 01 B — divergência REAL (não colapsa)
    assert norm_compare("Fazenda São Jorge Lote 1 B", field="denominacao") != \
        norm_compare("Fazenda São Jorge Gleba 01 B", field="denominacao")


def test_logradouro_abreviado_normaliza():
    assert norm_compare("R. das Flores") == norm_compare("Rua das Flores")
    assert norm_compare("Av. Brasil") == norm_compare("Avenida Brasil")


# ── _group_conflict_values (consolidação) ─────────────────────────────────

def _row(value, target_field):
    return SimpleNamespace(field_value={"value": value}, decided_value=None,
                           target_field=target_field)


def test_grupo_municipio_variantes_nao_conflita():
    rows = [
        _row("SÃO JOÃO D'ALIANÇA", "municipality"),
        _row("São João D'aliança-GO", "municipality"),
    ]
    # 1 valor distinto após normalização → NÃO vira divergência/ação
    assert len(_group_conflict_values(rows, "municipality")) == 1


def test_grupo_municipio_diferente_de_verdade_conflita():
    rows = [_row("Goiânia", "municipality"), _row("Anápolis", "municipality")]
    assert len(_group_conflict_values(rows, "municipality")) == 2


# ── build_matrix (denominação) ────────────────────────────────────────────

def _mrow(source_doc_type, field_name, value, *, matricula_hint=None):
    return SimpleNamespace(source_doc_type=source_doc_type, field_name=field_name,
                           field_value={"value": value}, matricula_hint=matricula_hint,
                           status="pendente")


def test_matriz_denominacao_grafia_equivalente_fica_consistente():
    rows = [
        _mrow("matricula", "denominacao", "Fazenda São Jorge", matricula_hint="4698"),
        _mrow("ccir", "denominacao", "FAZENDA SAO JORGE"),
    ]
    linhas = {ln["item"]: ln for ln in build_matrix(rows).matriz["linhas"]}
    assert linhas["denominacao_imovel"]["situacao"] == "consistente"
