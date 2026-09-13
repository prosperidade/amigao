"""Frente L — as funções puras do gate de OCR (`scripts/gate_ocr_originais.py`).

A auditoria de 12/09 derrubou a primeira versão rodando a função pura:
`_areas("926,36.54") == []`. O gate dizia procurar "a mesma área com outra
pontuação" e não achava justamente o exemplo do enunciado, porque comparava
STRING: o regex aceitava trocar a vírgula, não o ponto adicional.

`926,36.54` é notação registral antiga — 926 hectares, 36 ares, 54 centiares —
e é o MESMO número que `926,3654`. Quem sabe disso no projeto é
`parse_area_ha`, a porta única; o gate passou a compará-las por NÚMERO.

Estes testes existem para que a regressão não volte em silêncio: o gate não
roda em CI (precisa de credencial de produção), então as funções que decidem o
veredito precisam de rede própria.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

_CAMINHO = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "gate_ocr_originais.py"


@pytest.fixture(scope="module")
def gate():
    spec = importlib.util.spec_from_file_location("gate_ocr_originais", _CAMINHO)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


# ---------------------------------------------------------------------------
# O defeito que a auditoria achou
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("escrita", ["926,3654", "926,36.54"])
def test_a_mesma_area_em_qualquer_notacao_e_encontrada(gate, escrita):
    achado = gate._areas_presentes(f"área de {escrita} ha", {"3181": 926.3654})
    assert achado == {"3181": True}, (
        f"{escrita} é o mesmo número que 926,3654 — a comparação é por valor, "
        "não por string (foi o defeito reprovado em 12/09)"
    )


def test_notacao_americana_nao_e_aceita_de_proposito(gate):
    """`926.3654` fica de fora — e isso é escolha, não esquecimento.

    Em português o ponto é separador de milhar: aceitar `\d+\.\d+` faria
    `2.180` (dois mil cento e oitenta) ser lido como 2,180 ha e casar com
    qualquer coisa por acidente. Se um OCR devolver o número em notação
    americana, o gate REPROVA o documento e um humano olha — falha barulhenta.
    O contrário (extrator frouxo) seria falha silenciosa, que é o que este
    projeto não aceita.
    """
    assert gate._areas_presentes("área de 926.3654", {"3181": 926.3654}) == {"3181": False}


def test_um_centiare_de_diferenca_e_outra_area(gate):
    """A tolerância existe para ruído de float, não para aceitar divergência."""
    assert gate._areas_presentes("área de 926,3655", {"3181": 926.3654}) == {"3181": False}


def test_area_ausente_nao_e_inventada(gate):
    achado = gate._areas_presentes("documento sem área nenhuma", {"3181": 926.3654})
    assert achado == {"3181": False}


def test_as_quatro_matriculas_e_o_total_do_caso_23(gate):
    texto = (
        "Matrícula 3.181 com 926,3654 ha; matrícula 3.313 com 725,46.63; "
        "matrícula 3.673 com 212,3553 e matrícula 4.387 com 316,2053. "
        "Área total do imóvel: 2.180,3923 ha."
    )
    esperadas = {**gate.MATRICULAS_23, "total": gate.TOTAL_23}
    assert gate._areas_presentes(texto, esperadas) == {
        "3181": True, "3313": True, "3673": True, "4387": True, "total": True,
    }
    assert gate._matriculas_presentes(texto) == {
        "3181": True, "3313": True, "3673": True, "4387": True,
    }


def test_matricula_ausente_aparece_como_ausente(gate):
    assert gate._matriculas_presentes("só a 3.181 aqui") == {
        "3181": True, "3313": False, "3673": False, "4387": False,
    }


# ---------------------------------------------------------------------------
# A terceira pergunta: o doc 551 revela o representante?
# ---------------------------------------------------------------------------

def test_representante_e_reconhecido_quando_o_texto_o_traz(gate):
    texto = "CARTEIRA NACIONAL DE HABILITAÇÃO\nNome: JOEL ... CPF 123.456.789-00"
    assert "joel" in gate._le_o_representante(texto)
    assert "cpf" in gate._le_o_representante(texto)


def test_boilerplate_de_assinatura_nao_conta_como_leitura(gate):
    """O texto que produção tem hoje no 551 — 444 chars sem conteúdo (dívida #223)."""
    boilerplate = "QR-CODE Assinador Serpro SENATRAN Documento assinado digitalmente"
    assert gate._le_o_representante(boilerplate) == []


# ---------------------------------------------------------------------------
# A primeira pergunta: limiar com veredito
# ---------------------------------------------------------------------------

def test_similaridade_ignora_quebra_de_linha_mas_nao_conteudo(gate):
    a = "Art. 1º  Fica instituído\no regime desta Lei."
    b = "art. 1º fica instituído o regime desta lei."
    assert gate._similaridade(a, b) == 1.0, "espaço e caixa não são conteúdo"
    assert gate._similaridade(a, "texto completamente diferente") < gate.LIMIAR_SIMILARIDADE
