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

A FRONTEIRA DESTE REPLAY, dita em voz alta (auditoria de 12/09): o arquivo
guarda ROTEAMENTO, não conteúdo. Não tem `atributos`, `field_value` real,
`decided_value` nem `consolidated_at`. Portanto o que esta suíte prova é para
QUAL decisão cada linha vai — e só isso. Concordância, divergência, proposta,
vigência, titularidade e estado da decisão NÃO são medidos aqui: dependem de
dados que o arquivo não carrega, e afirmá-los a partir deste replay seria
inventar. A prova semântica pede o staging completo do #23, que hoje só existe
no dump de produção.
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
    # 26 decisões novas para 30 linhas — e o número é honesto sobre o que
    # mudou: só 13 linhas COLAPSAM (georreferenciamento 7→4, limitações 4→3,
    # município/UF 2→2). As outras 17 (cabeçalho) viram uma decisão CADA, por
    # atributo, como a SPEC manda. O ganho ali não é clique a menos: é a linha
    # deixar de ser solta e virar fato que acumula fonte, proposta e estado.
    assert len(resultado.decisoes) == 46, (
        f"20 decisões antes desta frente + 26 novas (antes: {DECISOES_ANTES})"
    )
    # Nenhuma linha some: toda linha do staging ou está numa decisão ou está
    # solta, com motivo — nunca em lugar nenhum.
    em_decisoes = sum(len(d.staging_ids) for d in resultado.decisoes)
    assert em_decisoes + len(resultado.sem_agrupamento) == 118


# ---------------------------------------------------------------------------
# Grupo 1 — o que ganhou chave
# ---------------------------------------------------------------------------

def test_cabecalho_da_matricula_vira_uma_decisao_por_atributo(resultado):
    """A primeira versão juntava os cinco atributos numa decisão só.

    A auditoria de 12/09 reprovou com a SPEC: a régua agrupa evidências do
    MESMO atributo, e cartório, denominação, registro anterior e NIRF são
    atributos diferentes — "divergência" entre um cartório e um NIRF não
    significa nada. Cada um é a sua decisão; o bloco visual, se a Isis quiser,
    é apresentação, não chave.
    """
    chaves = _chaves(resultado)
    for numero in ("3181", "3313", "3673", "4387"):
        for aspecto in ("cartorio", "denominacao", "registro_anterior", "nirf_cib"):
            assert f"matricula:{numero}:{aspecto}" in chaves

    # Denominação anterior só a 3.313 tem.
    assert "matricula:3313:denominacao_anterior" in chaves
    assert "matricula:3181:denominacao_anterior" not in chaves

    d = next(d for d in resultado.decisoes if d.chave == ("matricula", "3313", "cartorio"))
    assert d.label == "Cartório — matrícula 3313"
    assert [e.campo for e in d.evidencias] == ["cartorio"]
    assert d.fonte_autoritativa_doc == "matricula"

    # NIRF/CIB é número da Receita que a matrícula só CITA — sem autoridade
    # registral eleita.
    nirf = next(d for d in resultado.decisoes if d.chave == ("matricula", "3313", "nirf_cib"))
    assert nirf.fonte_autoritativa_doc is None


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


def test_municipio_e_uf_sao_dois_atributos_e_duas_decisoes(resultado):
    """Mesma régua do cabeçalho, aplicada ao imóvel.

    A primeira versão fez uma decisão "localização" com os dois. Se cartório ≠
    denominação obriga a separar, município ≠ UF obriga igual — e a SPEC não
    determina uma decisão única de localização.
    """
    municipio = next(d for d in resultado.decisoes if d.chave[2] == "municipio")
    uf = next(d for d in resultado.decisoes if d.chave[2] == "uf")
    assert [e.campo for e in municipio.evidencias] == ["municipality"]
    assert [e.campo for e in uf.evidencias] == ["state"]
    assert municipio.label == "Município do imóvel"
    assert uf.label == "UF do imóvel"
    # Sem fonte autoritativa eleita: CAR e matrícula afirmam a localização por
    # razões diferentes, e esconder a divergência seria pior que mostrá-la.
    assert municipio.fonte_autoritativa_doc is None
    assert uf.fonte_autoritativa_doc is None


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


def test_a_frase_da_baixa_nao_promete_o_que_o_codigo_nao_faz(resultado):
    """A auditoria pegou a frase anterior superdeclarando.

    Ela dizia que a baixa "entra na decisão do ato que encerra". Não entra: a
    LINHA continua solta; o que chega à decisão de gravames é o EFEITO dela (a
    vigência calculada). Motivo que descreve o desejo em vez do código é a
    mesma doença que esta frente veio tratar.
    """
    baixas = [s for s in resultado.sem_agrupamento if s["motivo"].startswith("baixa")]
    assert len(baixas) == 18
    motivo = baixas[0]["motivo"]
    assert "o que ela produz" in motivo and "fica individual" in motivo
    assert "entra na decisão do ato que encerra" not in motivo


# ---------------------------------------------------------------------------
# Dois atos não são duas versões de um fato
# ---------------------------------------------------------------------------

def test_dois_arrendamentos_na_mesma_matricula_nao_competem():
    """Achado ao escrever esta frente, antes do PR.

    O replay acima carrega `field_name`/`tipo_observacao`/`hint` reais, mas o
    `razao_linha_a_linha.json` não guarda `atributos` — então lá as duas
    averbações de arrendamento da 3.181 chegam sem `ato` e sem `vigencia`. Com
    o dado completo, as duas cairiam no MESMO `campo` ("observacao") e o ramo de
    texto de `_comparar` as poria uma contra a outra: "divergem" entre dois
    contratos que coexistem, e uma proposta que descartaria o outro.

    É o mesmo motivo pelo qual `gravames` já não compara valor. A fixture aqui
    tem os `atributos` que produção grava (`observacao_registral`), justamente
    para exercitar o caminho que o replay não alcança.
    """
    def _arrendamento(sid: int, ato: str, texto: str) -> ExtractedFieldStaging:
        return ExtractedFieldStaging(
            id=sid, tenant_id=1, process_id=1, document_id=548,
            source_doc_type="matricula", field_name="observacao",
            field_value={"value": texto},
            target_entity=None, target_field=None,
            matricula_hint="3181", tipo_observacao="arrendamento",
            atributos={"ato": ato, "vigencia": "vigente"},
            status=ExtractedFieldStatus.pendente,
        )

    resultado = build_decisions([
        _arrendamento(101, "AV.10", "Arrendamento — 15 anos, 01/01/2013 a 01/01/2028"),
        _arrendamento(102, "AV.11", "Arrendamento parcial — 120,0000 ha"),
    ])

    assert len(resultado.decisoes) == 1
    d = resultado.decisoes[0]
    assert d.chave == ("matricula", "3181", "limitacoes")
    # O rótulo de cada evidência é o ATO, não a coluna.
    assert {e.campo for e in d.evidencias} == {"AV.10", "AV.11"}
    # Coexistem — nunca "divergem".
    assert d.concordancia == "concordam"
    assert d.nivel_divergencia is None
    # E a proposta é a síntese dos dois, não um deles.
    assert "AV.10" in str(d.valor_proposto) and "AV.11" in str(d.valor_proposto)
