"""Dedupe de autos de infração por (órgão, número) — #78 lote B.

19 documentos de auto de infração raramente são 19 autos: são páginas, vias e
anexos. Sem agrupar, o consultor veria 19 passivos idênticos na Visão geral.
"""

from __future__ import annotations

from app.agents.diagnostico import _chave_auto


def test_mesma_numeracao_grafias_diferentes_e_o_mesmo_auto():
    a = {"numero_auto": "AI nº 123.456/2024", "orgao_autuante": "IBAMA"}
    b = {"numero_auto": "ai-123456-2024", "orgao_autuante": "ibama"}
    assert _chave_auto(a) == _chave_auto(b)


def test_ordinal_unicode_nao_quebra_a_chave():
    """`'º'.isalnum()` é True em Unicode — filtrar por alnum deixaria o "º" numa
    grafia e não na outra, e os dois autos não casariam."""
    com_ordinal = {"numero_auto": "nº 555/2024", "orgao_autuante": "IBAMA"}
    sem_ordinal = {"numero_auto": "555/2024", "orgao_autuante": "IBAMA"}
    assert _chave_auto(com_ordinal) == _chave_auto(sem_ordinal)


def test_orgaos_diferentes_nao_colidem():
    """Número igual de órgãos distintos são autos DIFERENTES — fundi-los criaria
    um passivo inexistente."""
    ibama = {"numero_auto": "123456", "orgao_autuante": "IBAMA"}
    semad = {"numero_auto": "123456", "orgao_autuante": "SEMAD"}
    assert _chave_auto(ibama) != _chave_auto(semad)


def test_sem_numero_nao_agrupa():
    """Sem identificador, juntar seria adivinhar — o chamador trata como avulso."""
    assert _chave_auto({"numero_auto": None, "orgao_autuante": "IBAMA"}) == ""
    assert _chave_auto({"numero_auto": "", "orgao_autuante": "IBAMA"}) == ""
    assert _chave_auto({"numero_auto": "sem numero legivel"}) == ""


def test_sem_orgao_ainda_agrupa_por_numero():
    a = {"numero_auto": "123456/2024"}
    b = {"numero_auto": "123.456-2024"}
    assert _chave_auto(a) == _chave_auto(b) == ":1234562024"
