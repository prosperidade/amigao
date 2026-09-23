"""Contrato da linguagem restrita e da lógica de três valores (ADR-073 §2).

Sem banco: a linguagem é interpretação pura de uma árvore JSON.
"""

from __future__ import annotations

import itertools

import pytest

from app.services.motor_juridico import importador
from app.services.motor_juridico.linguagem import (
    avaliar,
    fatos_da_condicao,
    validar_aplicabilidade,
    validar_condicao,
)

D = "determinado"


def _f(valor, estado=D):
    return {"valor": valor, "estado": estado}


def _bool(nome: str, v: bool | None) -> dict:
    """Folha booleana com o valor de Kleene pedido (None = fato desconhecido)."""
    return {nome: _f(None, "desconhecido") if v is None else _f(v)}


def _folha(nome: str) -> dict:
    return {"fato": nome, "op": "verdadeiro"}


VALORES = (True, False, None)


@pytest.mark.parametrize("a,b", list(itertools.product(VALORES, VALORES)))
def test_kleene_todos_e_algum(a, b):
    fatos = {**_bool("car.no_dossie", a), **_bool("ccir.no_dossie", b)}
    filhos = [_folha("car.no_dossie"), _folha("ccir.no_dossie")]

    todos, _ = avaliar({"todos": filhos}, fatos)
    algum, _ = avaliar({"algum": filhos}, fatos)

    esperado_todos = False if False in (a, b) else (True if (a, b) == (True, True) else None)
    esperado_algum = True if True in (a, b) else (False if (a, b) == (False, False) else None)
    assert todos is esperado_todos
    assert algum is esperado_algum


@pytest.mark.parametrize("v,esperado", [(True, False), (False, True), (None, None)])
def test_nao_inverte_e_preserva_o_desconhecido(v, esperado):
    valor, faltantes = avaliar({"nao": _folha("car.no_dossie")}, _bool("car.no_dossie", v))
    assert valor is esperado
    assert faltantes == ({"car.no_dossie"} if v is None else set())


def test_desconhecido_nunca_vira_falso():
    """O ponto do ADR: 'não sei se é rural' não é 'não é rural'."""
    cond = {"fato": "imovel.natureza", "op": "eq", "valor": "rural"}
    assert avaliar(cond, {"imovel.natureza": _f(None, "desconhecido")}) == (None, {"imovel.natureza"})
    assert avaliar(cond, {}) == (None, {"imovel.natureza"})
    assert avaliar({"nao": cond}, {})[0] is None


def test_falso_decide_mesmo_com_irmao_desconhecido():
    cond = {"todos": [{"fato": "imovel.natureza", "op": "eq", "valor": "rural"},
                      {"fato": "dominio.matriculas_no_dossie", "op": "ge", "valor": 2}]}
    valor, faltantes = avaliar(cond, {"dominio.matriculas_no_dossie": _f(0)})
    assert valor is False and faltantes == set()


def test_faltantes_so_os_que_decidiriam():
    cond = {"todos": [{"fato": "imovel.natureza", "op": "eq", "valor": "rural"},
                      {"fato": "titular.falecimento_declarado", "op": "verdadeiro"},
                      {"fato": "car.no_dossie", "op": "verdadeiro"}]}
    valor, faltantes = avaliar(cond, {"car.no_dossie": _f(True)})
    assert valor is None
    assert faltantes == {"imovel.natureza", "titular.falecimento_declarado"}


@pytest.mark.parametrize("op,valor,fato,esperado", [
    ("eq", "GO", "GO", True), ("ne", "GO", "MT", True), ("in", ["GO", "MT"], "MT", True),
    ("in", ["GO"], "SP", False),
])
def test_operadores_de_texto(op, valor, fato, esperado):
    assert avaliar({"fato": "caso.uf", "op": op, "valor": valor}, {"caso.uf": _f(fato)})[0] is esperado


@pytest.mark.parametrize("op,valor,esperado", [
    ("gt", 1, True), ("ge", 2, True), ("lt", 2, False), ("le", 2, True), ("eq", 3, False),
])
def test_operadores_de_ordem(op, valor, esperado):
    cond = {"fato": "dominio.matriculas_no_dossie", "op": op, "valor": valor}
    assert avaliar(cond, {"dominio.matriculas_no_dossie": _f(2)})[0] is esperado


def test_existe_nunca_e_desconhecido():
    cond = {"fato": "caso.uf", "op": "existe"}
    assert avaliar(cond, {"caso.uf": _f("GO")}) == (True, set())
    assert avaliar(cond, {}) == (False, set())


@pytest.mark.parametrize("cond,trecho", [
    ({"fato": "imovel.area_ha", "op": "gt", "valor": 1}, "fora do vocabulário"),
    ({"fato": "caso.uf", "op": "parece", "valor": "GO"}, "operador"),
    ({"fato": "caso.uf", "op": "gt", "valor": 1}, "exige fato inteiro"),
    ({"fato": "caso.uf", "op": "verdadeiro"}, "exige fato booleano"),
    ({"fato": "car.no_dossie", "op": "eq", "valor": "sim"}, "incompatível"),
    ({"fato": "caso.uf", "op": "in", "valor": []}, "lista não vazia"),
    ({"fato": "caso.uf", "op": "eq"}, "exige valor"),
    ({"fato": "caso.uf", "op": "existe", "valor": "GO"}, "não leva valor"),
    ({"todos": []}, "lista não vazia"),
    ({"todos": [{"fato": "caso.uf", "op": "existe"}], "algum": []}, "chave extra"),
    ({"fato": "caso.uf", "op": "eq", "valor": "GO", "codigo": "import os"}, "chave desconhecida"),
    ({}, "não vazio"),
])
def test_publicacao_recusa_com_motivo(cond, trecho):
    erros = validar_condicao(cond)
    assert erros and trecho in erros[0]


def test_aplicabilidade_por_esfera_ainda_nao_existe():
    assert validar_aplicabilidade({"ufs": ["GO"], "esferas": None, "objetivos": None}) == []
    assert "esferas" in validar_aplicabilidade({"ufs": None, "esferas": ["estadual"]})[0]
    assert "ufs" in validar_aplicabilidade({"ufs": ["Goiás"]})[0]


def test_gate_4b_traducao_valida_e_fundamentos_declarados():
    dados = importador.carregar()
    ids = [r["rule_id"] for r in dados["regras"]]
    assert ids == ["REG-BR-CAR-001", "REG-BR-CAR-002", "REG-BR-CAR-007", "REG-FUN-002",
                   "REG-FUN-012", "REG-GO-CAR-001"]
    for r in dados["regras"]:
        assert importador.validar_regra(r) == [], r["rule_id"]
        f = r["fundamento"]
        assert f["fonte"].count("|") == 4 and f["artigo"], r["rule_id"]
        assert f["origem_dispositivo"] in ("matriz", "proposta_engenharia")
        assert fatos_da_condicao(r["condicao"])
    # As identidades são curadas, não derivadas: nenhuma IN da SEMAD com órgão colado.
    assert all("semadgo" not in r["fundamento"]["fonte"] for r in dados["regras"])
