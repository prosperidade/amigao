"""Frente L — as 58 linhas soltas da Conferência do caso #23.

A Frente K deixou o percurso de navegador inteiro verde e, no rodapé,
`57 pendente(s)`: a Conferência agrupava 21 decisões e cobrava da consultora um
clique avulso para cada uma das outras linhas. O razão linha a linha daquela
rodada (`docs/trabalhos/consolidacao_real/razao_linha_a_linha.json`, 118 linhas
do staging REAL de produção da ELODI) registra as 58 — é a mesma medição, com
5 linhas a mais do que o percurso de navegador, que rodou com 113.

Esta suíte replica aquele staging contra `build_decisions`. Nada aqui é
inventado: doc_type, field_name, tipo_observacao, target e hint de matrícula
vêm do arquivo, como a regra da suíte de reconciliação exige ("toda fixture de
reconciliação nasce de linha real de staging").
"""

from __future__ import annotations

import json
import pathlib

import pytest

from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
from app.services.reconciliation_decisions import build_decisions

RAZAO = (
    pathlib.Path(__file__).resolve().parents[2]
    / "docs" / "trabalhos" / "consolidacao_real" / "razao_linha_a_linha.json"
)

# O que a Frente K mediu, antes desta frente.
SOLTAS_ANTES = 58
DECISOES_ANTES = 20  # 21 grupos no arquivo, sendo um deles o balde "(sem agrupamento)"


def _linhas_reais() -> list[ExtractedFieldStaging]:
    dados = json.loads(RAZAO.read_text(encoding="utf-8"))
    linhas = []
    for registro in dados["linhas"]:
        alvo = registro.get("target") or ""
        entidade, _, campo = alvo.partition(".")
        linhas.append(ExtractedFieldStaging(
            id=registro["staging_id"],
            tenant_id=1,
            process_id=1,
            document_id=registro.get("documento"),
            source_doc_type=registro.get("doc_type"),
            field_name=registro.get("field_name"),
            field_value={"value": registro.get("field_name")},
            target_entity=None if entidade in ("", "—") else entidade,
            target_field=None if campo in ("", "—") else campo,
            matricula_hint=registro.get("matricula"),
            tipo_observacao=registro.get("tipo_observacao"),
            status=ExtractedFieldStatus.pendente,
        ))
    return linhas


@pytest.fixture(scope="module")
def resultado():
    return build_decisions(_linhas_reais())


def _chaves(resultado) -> set[str]:
    return {f"{d.chave[0]}:{d.chave[1]}:{d.chave[2]}" for d in resultado.decisoes}


# ---------------------------------------------------------------------------
# O número — de 58 para 28
# ---------------------------------------------------------------------------

def test_as_soltas_caem_de_58_para_28(resultado):
    assert len(resultado.sem_agrupamento) == 28, (
        "30 das 58 linhas soltas ganharam chave natural nesta frente "
        f"(antes: {SOLTAS_ANTES})"
    )
    assert len(resultado.decisoes) == 32, (
        f"as 30 linhas viraram 12 decisões (antes: {DECISOES_ANTES})"
    )
    # Nenhuma linha some: toda linha do staging ou está numa decisão ou está
    # solta, com motivo — nunca em lugar nenhum.
    em_decisoes = sum(len(d.staging_ids) for d in resultado.decisoes)
    assert em_decisoes + len(resultado.sem_agrupamento) == 118


# ---------------------------------------------------------------------------
# Grupo 1 — o que ganhou chave
# ---------------------------------------------------------------------------

def test_cabecalho_da_matricula_vira_uma_decisao_por_matricula(resultado):
    chaves = _chaves(resultado)
    for numero in ("3181", "3313", "3673", "4387"):
        assert f"matricula:{numero}:identificacao_matricula" in chaves

    d = next(d for d in resultado.decisoes if d.chave == ("matricula", "3313", "identificacao_matricula"))
    campos = {e.campo for e in d.evidencias}
    # A 3.313 é a única com denominação anterior — 5 cliques viraram 1.
    assert campos == {
        "cartorio", "denominacao_imovel", "denominacao_anterior",
        "registro_anterior", "nirf_cib",
    }
    assert d.label == "Identificação da matrícula 3313"


def test_georreferenciamento_reune_o_codigo_e_a_averbacao(resultado):
    d = next(d for d in resultado.decisoes if d.chave == ("matricula", "3181", "georreferenciamento"))
    campos = [e.campo for e in d.evidencias]
    tipos = [e.tipo_observacao for e in d.evidencias]
    assert "geo_certificacao_codigo" in campos, "o código é a linha que GRAVA"
    assert "georreferenciamento" in tipos, "a averbação é o mesmo ato, não outro"
    assert d.label == "Georreferenciamento — matrícula 3181"

    # A 4.387 tem o código e nenhuma averbação: fonte única, decisão mesmo assim.
    so_codigo = next(d for d in resultado.decisoes if d.chave == ("matricula", "4387", "georreferenciamento"))
    assert [e.campo for e in so_codigo.evidencias] == ["geo_certificacao_codigo"]


def test_limitacoes_de_uso_ganham_decisao_por_matricula(resultado):
    chaves = _chaves(resultado)
    assert "matricula:3181:limitacoes" in chaves   # 2 arrendamentos
    assert "matricula:3313:limitacoes" in chaves   # 1 arrendamento
    assert "matricula:3673:limitacoes" in chaves   # 1 compromisso de compra e venda

    d = next(d for d in resultado.decisoes if d.chave == ("matricula", "3181", "limitacoes"))
    assert len(d.evidencias) == 2
    assert {e.tipo_observacao for e in d.evidencias} == {"arrendamento"}
    assert d.label == "Limitações de uso e posse — matrícula 3181"


def test_municipio_e_uf_sao_um_fato_so(resultado):
    d = next(d for d in resultado.decisoes if d.chave[2] == "localizacao")
    assert {e.campo for e in d.evidencias} == {"municipality", "state"}
    assert d.label == "Localização do imóvel"
    # Sem fonte autoritativa eleita: CAR e matrícula afirmam a localização por
    # razões diferentes, e esconder a divergência seria pior que mostrá-la.
    assert d.fonte_autoritativa_doc is None


# ---------------------------------------------------------------------------
# Grupo 2 — o que fica de fora, e por quê
# ---------------------------------------------------------------------------

def test_toda_solta_que_sobra_diz_a_propria_razao(resultado):
    generico = "tipo sem chave natural mapeada nesta frente"
    sem_razao = [s for s in resultado.sem_agrupamento if generico in (s["motivo"] or "")]
    assert sem_razao == [], (
        "solta sem razão própria é solta que ninguém examinou: "
        f"{[(s['staging_id'], s['field_name']) for s in sem_razao]}"
    )
    assert all((s["motivo"] or "").strip() for s in resultado.sem_agrupamento)


def test_as_28_sobras_sao_as_quatro_familias_esperadas(resultado):
    import collections

    familias = collections.Counter(
        s["motivo"].split(" —")[0] for s in resultado.sem_agrupamento
    )
    assert familias == {
        "baixa": 18,
        "ato que o vocabulário não cobre": 5,   # nao_classificado
        "aditivo": 3,
        "APP declarada pelo CAR": 1,
        "módulos fiscais": 1,
    }


def test_baixa_continua_fora_porque_e_aresta_de_outro_ato(resultado):
    baixas = [s for s in resultado.sem_agrupamento if s["motivo"].startswith("baixa")]
    assert len(baixas) == 18
    assert "aresta de outro ato" in baixas[0]["motivo"]
