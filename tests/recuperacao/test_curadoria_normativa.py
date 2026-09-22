"""Curadoria (ADR-075 §4, A1, A2): papel por área, transições, hash chain global, lote, A5."""

from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import text
from tests.recuperacao import catalogo_sintetico as cs

from app.models.zona_normativa import FonteNormativaProveniencia, TarefaRevisaoNormativa
from app.services.zona_normativa import curadoria as cur
from app.services.zona_normativa.integridade import conferir_originais

H = hashlib.sha256(b"original").hexdigest()


@pytest.fixture
def gente(db_session):
    admin = cs.usuario(db_session, "admin", superuser=True)
    isis = cs.usuario(db_session, "isis")
    eng = cs.usuario(db_session, "eng")
    cur.conceder_papel(db_session, concedente=admin, user_id=isis.id, papel="validar_fonte_normativa", area="*")
    cur.conceder_papel(db_session, concedente=admin, user_id=eng.id, papel="curar_corpus", area="GO")
    return admin, isis, eng


def _versao_go(db, **kw):
    f = cs.fonte(db, "lei|go||18104|2013", rotulo="Lei GO 18.104/2013", ente="go")
    return cs.versao(db, f, hash_original=H, storage_key="zona-normativa/originais/x.pdf", **kw)


def _propor(db, v, user):
    return cur.propor(db, versao_id=v.id, user=user, url_oficial="https://legisla.casacivil.go.gov.br/x",
                      texto_conferido_por="hash", vigencia="vigente", nota="conferido contra o portal")


def test_superusuario_concede_mas_nao_cura(db_session, gente):
    admin, _isis, _eng = gente
    v = _versao_go(db_session)
    with pytest.raises(cur.CuradoriaNegada):
        _propor(db_session, v, admin)


def test_papel_e_por_area(db_session, gente):
    _admin, _isis, eng = gente
    f = cs.fonte(db_session, "lei|mt||1|2020", ente="mt")
    v = cs.versao(db_session, f)
    with pytest.raises(cur.CuradoriaNegada):
        _propor(db_session, v, eng)          # eng só cura GO


def test_fluxo_bruto_proposto_validado_com_cadeia(db_session, gente):
    _admin, isis, eng = gente
    v = _versao_go(db_session)
    e1 = _propor(db_session, v, eng)
    assert v.status_validacao == "proposto" and v.vigencia_estado == "determinada"
    with pytest.raises(cur.CuradoriaNegada):
        cur.validar(db_session, versao_id=v.id, user=eng, nota="eu mesmo")   # propor ≠ validar
    e2 = cur.validar(db_session, versao_id=v.id, user=isis, nota="li a ficha")
    assert v.status_validacao == "validado"
    assert e2.hash_anterior == e1.hash_evento
    assert e2.area == "GO" and e2.papel_na_curadoria == "validar_fonte_normativa"
    assert cur.verificar_cadeia(db_session)["integra"] is True


def test_cadeia_detecta_adulteracao(db_session, gente):
    _admin, isis, eng = gente
    v = _versao_go(db_session)
    _propor(db_session, v, eng)
    cur.validar(db_session, versao_id=v.id, user=isis, nota="ok")
    # Em produção o gatilho barra o UPDATE; aqui (create_all, sem gatilho) simula-se a adulteração.
    db_session.execute(text("UPDATE validacao_norma SET nota = 'outra coisa' WHERE acao = 'validar'"))
    db_session.expire_all()
    r = cur.verificar_cadeia(db_session)
    assert r["integra"] is False


def test_validar_exige_original_a5(db_session, gente):
    _admin, isis, eng = gente
    f = cs.fonte(db_session, "lei|go||1|2001", ente="go")
    v = cs.versao(db_session, f)       # sem hash_original
    _propor(db_session, v, eng)
    with pytest.raises(cur.TransicaoInvalida, match="A5"):
        cur.validar(db_session, versao_id=v.id, user=isis, nota="ok")


def test_propor_exige_url_oficial_e_identidade(db_session, gente):
    _admin, _isis, eng = gente
    v = _versao_go(db_session)
    with pytest.raises(cur.TransicaoInvalida):
        cur.propor(db_session, versao_id=v.id, user=eng, url_oficial="", texto_conferido_por="hash",
                   vigencia="nao_sei", nota="x")
    f = cs.fonte(db_session, "nao_determinado|doc1|5", ente="go", nivel="nao_determinado", determinada=False)
    v2 = cs.versao(db_session, f)
    with pytest.raises(cur.TransicaoInvalida, match="identidade"):
        _propor(db_session, v2, eng)


def test_devolucao_volta_a_bruto_com_nota(db_session, gente):
    _admin, isis, eng = gente
    v = _versao_go(db_session)
    _propor(db_session, v, eng)
    with pytest.raises(cur.TransicaoInvalida):
        cur.devolver(db_session, versao_id=v.id, user=isis, nota="  ")
    ev = cur.devolver(db_session, versao_id=v.id, user=isis, nota="fronteira errada na p. 12")
    assert v.status_validacao == "bruto" and ev.decisao == "devolvido"


def test_lote_por_coletanea(db_session, gente):
    _admin, isis, eng = gente
    from app.models.legislation import LegislationDocument
    doc = LegislationDocument(title="Coletânea GO", source_type="manual", scope="estadual", uf="GO")
    db_session.add(doc)
    db_session.flush()
    boas = []
    for n in range(3):
        f = cs.fonte(db_session, f"lei|go||{100 + n}|2020", ente="go")
        v = cs.versao(db_session, f, hash_original=H, storage_key="k")
        db_session.add(FonteNormativaProveniencia(
            fonte_versao_id=v.id, legislation_document_id=doc.id, documento_origem_rotulo="Coletânea GO",
            sinal_fronteira="impressao", trecho_hash=v.hash_texto, offset_inicio=n * 10,
            url_impressa="legisla.casacivil.go.gov.br/ato/1", motivos_revisao=None))
        boas.append(v)
    f = cs.fonte(db_session, "lei|go||200|2020", ente="go")
    ambigua = cs.versao(db_session, f, hash_original=H, storage_key="k")
    db_session.add(FonteNormativaProveniencia(
        fonte_versao_id=ambigua.id, legislation_document_id=doc.id, documento_origem_rotulo="Coletânea GO",
        sinal_fronteira="impressao", trecho_hash=ambigua.hash_texto, offset_inicio=99,
        url_impressa="legisla.casacivil.go.gov.br/ato/2", motivos_revisao=["inicio_estimado"]))
    db_session.flush()
    p = cur.propor_lote_coletanea(db_session, legislation_document_id=doc.id, user=eng, nota="lote conferido")
    assert p["propostas"] == 3 and [x["versao"] for x in p["puladas"]] == [ambigua.id]
    r = cur.validar_lote_coletanea(db_session, legislation_document_id=doc.id, user=isis,
                                   nota="fronteiras conferidas", excluir_versoes={boas[0].id})
    assert r["validadas"] == 2
    assert boas[0].status_validacao == "proposto" and boas[1].status_validacao == "validado"


class _StorageFalso:
    def __init__(self, conteudo: dict[str, bytes]):
        self.conteudo = conteudo

    def download_bytes(self, chave: str) -> bytes:
        return self.conteudo.get(chave, b"")


def test_conferencia_de_original_bloqueia_divergente_e_ausente(db_session):
    f = cs.fonte(db_session, "lei|br||77|2000")
    boa = cs.versao(db_session, f, texto="a", hash_original=H, storage_key="k-boa")
    adulterada = cs.versao(db_session, f, texto="b", hash_original=H, storage_key="k-ruim")
    sumida = cs.versao(db_session, f, texto="c", hash_original=H, storage_key="k-sumiu")
    out = conferir_originais(db_session, _StorageFalso({"k-boa": b"original", "k-ruim": b"adulterado"}))
    assert out["conferem"] == 1 and out["divergentes"] == 1 and out["ausentes"] == 1
    assert boa.bloqueio_citacao is None and boa.original_conferido_em is not None
    assert adulterada.bloqueio_citacao == "original_divergente"
    assert sumida.bloqueio_citacao == "original_ausente_no_storage"
    tipos = {t.tipo for t in db_session.query(TarefaRevisaoNormativa).filter(
        TarefaRevisaoNormativa.fonte_versao_id.in_([adulterada.id, sumida.id]))}
    assert tipos == {"original_divergente", "original_ausente"}
