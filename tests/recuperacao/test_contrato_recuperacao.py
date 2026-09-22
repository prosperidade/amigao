"""Contrato da recuperação normativa (ADR-075 §7) — todo PR, vetores sintéticos, sem API.

Filtro antes do ranking; nunca relaxa; vazio com a razão; uma vaga por
dispositivo; interpretação anexada sem ocupar vaga; consulta por identidade.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from tests.recuperacao import catalogo_sintetico as cs

from app.services.zona_normativa.recuperacao import Contexto, recuperar

HOJE = date(2026, 9, 22)
DEC = "decreto|br||6514|2008"


def _ctx(**kw) -> Contexto:
    base = dict(pergunta="descumprimento de embargo sanção", uso="descoberta", data_referencia=HOJE,
                objetivo="defesa", esferas=("federal",), uf="GO")
    base.update(kw)
    return Contexto(**base)


def _buscar(db, ctx, q=0, modelo=cs.MODELO):
    return recuperar(db, ctx, embed_query=lambda _t: cs.base(q), modelo=modelo)


@pytest.fixture
def decreto(db_session):
    f = cs.fonte(db_session, DEC, rotulo="Decreto 6.514/2008", objetivos=["defesa"])
    v = cs.versao(db_session, f, status="validado")
    d18 = cs.dispositivo(db_session, v, "18", rotulo_fonte="Decreto 6.514/2008")
    d3 = cs.dispositivo(db_session, v, "3", rotulo_fonte="Decreto 6.514/2008")
    cs.trecho(db_session, v, d18, "Art. 18. O descumprimento total ou parcial de embargo", 0)
    cs.trecho(db_session, v, d18, "parágrafo único do art. 18 embargo", 1)
    cs.trecho(db_session, v, d3, "Art. 3º As infrações administrativas são punidas", 2)
    return f, v, d18


def test_ranking_so_dentro_do_elegivel(db_session, decreto):
    # Trecho IDÊNTICO à pergunta, mas de outra UF: não pode aparecer, por mais parecido que seja.
    f_ms = cs.fonte(db_session, "lei|ms||1|2020", ente="ms", objetivos=["defesa"])
    v_ms = cs.versao(db_session, f_ms)
    cs.trecho(db_session, v_ms, cs.dispositivo(db_session, v_ms, "1"), "embargo sanção descumprimento", 0)
    r = _buscar(db_session, _ctx(esferas=("federal", "estadual"), uf="GO"))
    assert r.vazio is None
    assert all(t.fonte_id != f_ms.id for t in r.trechos)
    assert r.metodo == "hibrido_rrf"


def test_nunca_relaxa_vazio_com_razao_e_filtro(db_session, decreto):
    # Peça só cita validado; o objetivo pedido não bate com nada → vazio, não "busquei sem".
    r = _buscar(db_session, _ctx(objetivo="outorga"))
    assert r.trechos == []
    assert r.vazio.razao == "sem_fonte_elegivel"
    assert r.vazio.filtro_que_esvaziou == "objetivo"


def test_peca_so_cita_validado(db_session):
    f = cs.fonte(db_session, "lei|br||1|2000", objetivos=["defesa"])
    v = cs.versao(db_session, f, status="proposto")
    cs.trecho(db_session, v, cs.dispositivo(db_session, v, "1"), "embargo", 0)
    r = _buscar(db_session, _ctx(uso="peca"))
    assert r.trechos == [] and r.vazio.razao == "sem_fonte_elegivel"
    assert r.vazio.filtro_que_esvaziou == "status"
    r2 = _buscar(db_session, _ctx(uso="interno"))
    assert r2.trechos and "proposto_com_selo" in r2.trechos[0].marcas


@pytest.mark.parametrize("campo,valor,filtro", [
    ("data_referencia", None, "data_referencia"),
    ("objetivo", "nao_identificado", "objetivo"),
    ("objetivo", None, "objetivo"),
    ("esferas", (), "esferas"),
    ("uf", None, "uf"),
])
def test_contexto_insuficiente(db_session, decreto, campo, valor, filtro):
    kw = {campo: valor}
    if campo == "uf":
        kw["esferas"] = ("estadual",)
    r = _buscar(db_session, _ctx(**kw))
    assert r.vazio.razao == "contexto_insuficiente"
    assert r.vazio.filtro_que_esvaziou == filtro


def test_fora_da_cobertura(db_session, decreto):
    r = _buscar(db_session, _ctx(esferas=("estadual",), uf="RR"))
    assert r.vazio.razao == "fora_da_cobertura"


def test_espaco_vetorial_incompativel(db_session, decreto):
    r = _buscar(db_session, _ctx(), modelo="outro-modelo")
    assert r.vazio.razao == "espaco_vetorial_incompativel"


def test_falha_de_busca_sobe_como_razao(db_session, decreto):
    def quebra(_t):
        raise RuntimeError("provedor fora")
    r = recuperar(db_session, _ctx(), embed_query=quebra, modelo=cs.MODELO)
    assert r.trechos == [] and r.vazio.razao == "falha_de_busca"
    assert "provedor fora" in r.vazio.detalhe


def test_uma_vaga_por_dispositivo_entre_versoes(db_session, decreto):
    f, _v, _d = decreto
    # Mesma norma, outra redação (outra coletânea): o art. 18 não ganha segunda vaga.
    v2 = cs.versao(db_session, f, status="validado", texto="outra redação")
    cs.trecho(db_session, v2, cs.dispositivo(db_session, v2, "18", rotulo_fonte="Decreto 6.514/2008"),
              "Art. 18 descumprimento de embargo (compilado)", 0)
    r = _buscar(db_session, _ctx(limite=5))
    chaves = [(t.fonte_id, t.artigo) for t in r.trechos]
    assert len(chaves) == len(set(chaves))
    assert chaves.count((f.id, "18")) == 1


def test_interpretacao_anexada_nao_ocupa_vaga(db_session, decreto):
    f, _v, _d18 = decreto
    ojn = cs.fonte(db_session, "ojn|br|pfe-ibama|6|2009", rotulo="OJN 06/2009", nivel="interpretacao")
    vo = cs.versao(db_session, ojn, status="validado")
    # A OJN é a MAIS parecida com a pergunta (vetor idêntico): ainda assim não disputa vaga.
    for _ in range(6):
        cs.trecho(db_session, vo, cs.dispositivo(db_session, vo, None, rotulo_fonte=f"OJN {_}"), "embargo", 0)
    cs.ligar(db_session, ojn, f, "18")
    r = _buscar(db_session, _ctx(limite=8))
    assert all(t.nivel != "interpretacao" for t in r.trechos)
    art18 = next(t for t in r.trechos if t.artigo == "18")
    assert [i["interpretacao_fonte_id"] for i in art18.interpretacoes] == [ojn.id]
    art3 = next((t for t in r.trechos if t.artigo == "3"), None)
    assert art3 is None or art3.interpretacoes == []


def test_consulta_por_identidade_na_pergunta(db_session, decreto):
    r = _buscar(db_session, _ctx(pergunta="qual a sanção do art. 18 do Decreto 6.514/2008?"))
    assert r.metodo == "identidade"
    assert r.trechos and {t.artigo for t in r.trechos} == {"18"}


def test_identidade_dispositivo_inexistente(db_session, decreto):
    r = _buscar(db_session, _ctx(norma="Decreto 6.514/2008", artigo="999"))
    assert r.vazio.razao == "sem_fonte_elegivel" and r.vazio.filtro_que_esvaziou == "dispositivo"


def test_identidade_norma_fora_do_catalogo(db_session, decreto):
    r = _buscar(db_session, _ctx(norma="Lei 9.999/2031", artigo="1"))
    assert r.vazio.razao == "fora_da_cobertura"


def test_vigencia_na_data_de_referencia(db_session):
    rev = cs.fonte(db_session, "decreto|br||3179|1999", objetivos=["defesa"])
    vr = cs.versao(db_session, rev, status="validado", fim=date(2008, 7, 22))
    cs.trecho(db_session, vr, cs.dispositivo(db_session, vr, "1"), "embargo antigo", 0)
    hoje = _buscar(db_session, _ctx(uso="peca"))
    assert hoje.trechos == [] and hoje.vazio.filtro_que_esvaziou == "vigencia"
    fato_2007 = _buscar(db_session, _ctx(uso="peca", data_referencia=date(2007, 5, 1)))
    assert fato_2007.trechos and "historica" in fato_2007.trechos[0].marcas


def test_vigencia_nao_determinada_nao_vira_vigente(db_session):
    f = cs.fonte(db_session, "lei|br||2|2000", objetivos=["defesa"])
    v = cs.versao(db_session, f, status="validado", vigencia_estado="nao_determinada")
    cs.trecho(db_session, v, cs.dispositivo(db_session, v, "1"), "embargo", 0)
    assert _buscar(db_session, _ctx(uso="peca")).vazio.filtro_que_esvaziou == "vigencia"
    r = _buscar(db_session, _ctx(uso="descoberta"))
    assert r.trechos and "vigencia_nao_determinada" in r.trechos[0].marcas


def test_original_divergente_bloqueia_citacao(db_session):
    f = cs.fonte(db_session, "lei|br||3|2000", objetivos=["defesa"])
    v = cs.versao(db_session, f, status="validado", bloqueio="original_divergente")
    cs.trecho(db_session, v, cs.dispositivo(db_session, v, "1"), "embargo", 0)
    assert _buscar(db_session, _ctx(uso="peca")).vazio.filtro_que_esvaziou == "bloqueio_original"
    assert _buscar(db_session, _ctx(uso="interno")).vazio.filtro_que_esvaziou == "bloqueio_original"


def test_nivel_nao_determinado_nunca_e_candidato(db_session):
    f = cs.fonte(db_session, "nao_determinado|doc1|0", nivel="nao_determinado", determinada=False)
    v = cs.versao(db_session, f)
    cs.trecho(db_session, v, None, "embargo sanção", 0)
    r = _buscar(db_session, _ctx())
    assert r.trechos == []


def test_objetivo_nao_declarado_entra_marcado(db_session):
    f = cs.fonte(db_session, "lei|br||4|2000", objetivos=None)
    v = cs.versao(db_session, f)
    cs.trecho(db_session, v, cs.dispositivo(db_session, v, "1"), "embargo", 0)
    r = _buscar(db_session, _ctx())
    assert r.trechos and "objetivo_nao_declarado" in r.trechos[0].marcas


def test_a3_so_precedente_pode_ser_privado(db_session):
    u = cs.usuario(db_session, "a3")
    with pytest.raises(IntegrityError), db_session.begin_nested():
        cs.fonte(db_session, "lei|br||5|2000", tenant_id=u.tenant_id)


def test_a3_precedente_nasce_privado(db_session):
    with pytest.raises(IntegrityError), db_session.begin_nested():
        cs.fonte(db_session, "precedente|go||1|2025", nivel="precedente", tenant_id=None)


def test_identidade_sem_ente_resolve_pela_esfera_pedida(db_session):
    # Achado no percurso autenticado (22/09): "Lei 18.104/2013" sem "GO" virava lei FEDERAL.
    f = cs.fonte(db_session, "lei|go||18104|2013", rotulo="Lei GO 18.104/2013", ente="go", objetivos=["car"])
    v = cs.versao(db_session, f)
    cs.trecho(db_session, v, cs.dispositivo(db_session, v, "29", rotulo_fonte="Lei GO 18.104/2013"), "compensação", 0)
    ctx = _ctx(pergunta="o que diz o art. 29 da Lei 18.104/2013?", objetivo="car", esferas=("estadual",), uf="GO")
    r = _buscar(db_session, ctx)
    assert r.metodo == "identidade" and [t.artigo for t in r.trechos] == ["29"]


def test_identidade_ambigua_entre_uniao_e_uf_nao_escolhe(db_session):
    for ente in ("br", "go"):
        f = cs.fonte(db_session, f"lei|{ente}||7|2001", ente=ente, objetivos=["car"])
        cs.dispositivo(db_session, cs.versao(db_session, f), "1")
    ctx = _ctx(pergunta="art. 1 da Lei 7/2001", objetivo="car", esferas=("federal", "estadual"), uf="GO")
    r = _buscar(db_session, ctx)
    assert r.vazio.razao == "contexto_insuficiente" and "diga a esfera" in r.vazio.detalhe
