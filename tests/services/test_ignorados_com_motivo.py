"""Nenhuma linha aceita sai sem motivo (dívida #200).

Origem: leitura de PRODUÇÃO de 03/08 (processo 16, o caso da Isis). No lote das
15:19 a consolidação gravou **zero** campos — 3 voltaram como divergência
devolvida e 3 saíram em ``ignorados`` assim:

    ["imovel.rat_protocolo", "imovel.modulos_fiscais", "imovel.regulatory_issues"]

Identificador nu. Desses três, um estava sendo **jogado fora** (módulos fiscais,
que não tinha coluna) e dois eram **recusa por decisão** — e a tela mostrava a
mesma coisa para os dois casos, que pedem ações opostas da consultora.

O que estes testes fixam:

* toda linha de ``ignorados`` carrega o motivo, em português de consultora;
* recusa declarada diz o PORQUÊ (e não se confunde com lacuna de mapeamento);
* falta de coluna não se confunde com "coluna existe mas não gravamos aqui";
* ``modulos_fiscais`` agora **pousa** — ganhou destino.
"""

from __future__ import annotations

import pytest

from app.models.property import Property
from app.services.staging_consolidation import (
    _IMOVEL_FIELDS,
    motivo_sem_destino,
)

# ---------------------------------------------------------------------------
# Recusa declarada — decisão, com o porquê
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "campo,trecho_esperado",
    [
        ("rat_protocolo", "identifica o RAT"),
        ("rat_data_emissao", "identifica o RAT"),
        ("regulatory_issues", "alertas na Visão geral"),
        ("total_area_ha", "soma das matrículas"),
    ],
)
def test_recusa_declarada_diz_o_porque(campo, trecho_esperado):
    motivo = motivo_sem_destino("imovel", campo)
    assert motivo is not None
    assert trecho_esperado in motivo
    # Não pode se disfarçar de lacuna: quem lê tem que entender que é decisão,
    # não esquecimento — senão vai pedir um campo que ninguém vai criar.
    assert "a pedir" not in motivo


def test_protocolo_e_data_do_rat_nao_viram_campo_do_imovel():
    """A linha de corte que a #200 estabeleceu: metadado do DOCUMENTO ≠ atributo
    do IMÓVEL. Dois RATs de datas diferentes são dois documentos."""
    assert "rat_protocolo" not in _IMOVEL_FIELDS
    assert "rat_data_emissao" not in _IMOVEL_FIELDS
    assert "rat_protocolo" not in Property.__table__.columns
    assert "rat_data_emissao" not in Property.__table__.columns


# ---------------------------------------------------------------------------
# Destino — módulos fiscais deixou de ser descartado
# ---------------------------------------------------------------------------


def test_modulos_fiscais_agora_tem_casa():
    """Do outro lado da linha: módulos fiscais é atributo do imóvel (área ÷
    módulo fiscal do município) e decide porte — logo, exceção do Código
    Florestal. Era extraído do RAT e descartado a cada consolidação."""
    assert "modulos_fiscais" in Property.__table__.columns
    assert "modulos_fiscais" in _IMOVEL_FIELDS
    # None = tem casa, vai gravar normalmente.
    assert motivo_sem_destino("imovel", "modulos_fiscais") is None


def test_modulos_fiscais_e_fracionario():
    """Integer arredondaria 3,7 → 3 e mudaria o lado do limiar de 4 MF."""
    from sqlalchemy import Float
    assert isinstance(Property.__table__.columns["modulos_fiscais"].type, Float)


# ---------------------------------------------------------------------------
# Lacuna real — distinta de recusa, com a saída certa
# ---------------------------------------------------------------------------


def test_campo_sem_coluna_pede_campo_novo():
    motivo = motivo_sem_destino("imovel", "campo_que_nao_existe_em_lugar_nenhum")
    assert motivo is not None
    assert "ainda não tem campo" in motivo
    assert "a pedir" in motivo  # diz o que fazer


def test_coluna_existente_fora_da_allowlist_e_caso_diferente():
    """`strategic_notes` É coluna do imóvel e NÃO é preenchida pela consolidação.

    Antes esse caso e o "não existe coluna" produziam a mesma string. São
    problemas diferentes: um é ajuste de mapeamento, o outro é campo a criar.
    """
    assert "strategic_notes" in Property.__table__.columns
    assert "strategic_notes" not in _IMOVEL_FIELDS
    motivo = motivo_sem_destino("imovel", "strategic_notes")
    assert motivo is not None
    assert "existe na ficha do imóvel" in motivo
    assert "ainda não tem campo" not in motivo


def test_sem_campo_de_destino_tem_motivo_proprio():
    assert "sem campo de destino" in (motivo_sem_destino("imovel", None) or "")
    assert "sem campo de destino" in (motivo_sem_destino("imovel", "  ") or "")


def test_entidade_desconhecida_nao_devolve_none():
    """`None` significa "tem casa, vai gravar". Entidade desconhecida NÃO tem
    casa — devolver None aqui faria a linha sumir sem motivo, que é a #200 de
    volta por outra porta."""
    motivo = motivo_sem_destino("entidade_inexistente", "qualquer_campo")
    assert motivo is not None
    assert "destino desconhecido" in motivo


def test_campo_com_casa_devolve_none():
    """Contrapositiva: campo normal não pode ganhar motivo (senão a tela
    acusaria problema em quem gravou certo)."""
    assert motivo_sem_destino("imovel", "car_code") is None
    assert motivo_sem_destino("cliente", "full_name") is None
    assert motivo_sem_destino("matricula", "numero_matricula") is None


# ---------------------------------------------------------------------------
# Linguagem — a mensagem é lida pela consultora, não pelo log
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entidade,campo",
    [
        ("imovel", "rat_protocolo"),
        ("imovel", "campo_inexistente"),
        ("imovel", "strategic_notes"),
        ("cliente", "campo_inexistente"),
        ("matricula", "campo_inexistente"),
    ],
)
def test_motivo_nao_usa_vocabulario_de_log(entidade, campo):
    motivo = motivo_sem_destino(entidade, campo) or ""
    for jargao in ("target_field", "target_entity", "allowlist", "None",
                   "incoercível", "column", "NULL"):
        assert jargao not in motivo, f"'{jargao}' vazou para a tela em {entidade}.{campo}"
