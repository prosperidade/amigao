"""Correção de corte no lugar (dívida #274): `catalogo.reaplicar_dispositivos`."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from tests.recuperacao import catalogo_sintetico as cs

from app.services.zona_normativa import catalogo, dispositivos

TEXTO = (
    "Art. 1º Um.\nArt. 2º Dois.\nArt. 6º Para o imposto a que se refere o\n"
    "Art. 29 da Lei número 5.172, considera-se rural.\nArt. 7º Sete.\nParágrafo único. Único.\n"
)
ROTULO = "Lei 5.868/1972"


def _embed(textos):
    return [cs.base(0)] * len(textos)


def _versao_com_corte_antigo(db, monkeypatch):
    f = cs.fonte(db, "lei|br||5868|1972", rotulo=ROTULO)
    v = cs.versao(db, f, status="proposto", texto=TEXTO)
    with monkeypatch.context() as m:  # a regra de antes: remissão abria artigo
        m.setattr(dispositivos, "e_remissao", lambda _t, _m: False)
        catalogo.reaplicar_dispositivos(db, v.id, rotulo=ROTULO, texto=TEXTO, embed=_embed,
                                        modelo_embedding=cs.MODELO, aplicar=True)
    return v


def _artigos(db, vid):
    return dict(db.execute(text(
        "SELECT artigo, id FROM dispositivo WHERE fonte_versao_id = :v AND tipo = 'artigo'"), {"v": vid}).all())


def test_espurio_sai_artigo_engolido_volta_e_ids_ficam(db_session, monkeypatch):
    v = _versao_com_corte_antigo(db_session, monkeypatch)
    antes = _artigos(db_session, v.id)
    assert set(antes) == {"1", "2", "6", "29"}  # o 7 estava dentro do falso 29

    medida = catalogo.reaplicar_dispositivos(db_session, v.id, rotulo=ROTULO, texto=TEXTO, embed=None,
                                             modelo_embedding=None)
    assert len(medida.saem) >= 2 and medida.entram  # só mede: nada mudou
    assert _artigos(db_session, v.id) == antes

    rec = catalogo.reaplicar_dispositivos(db_session, v.id, rotulo=ROTULO, texto=TEXTO, embed=_embed,
                                          modelo_embedding=cs.MODELO, aplicar=True)
    depois = _artigos(db_session, v.id)
    assert set(depois) == {"1", "2", "6", "7"}
    assert depois["1"] == antes["1"] and depois["2"] == antes["2"]  # mesmo caminho e hash, mesmo ID
    assert rec.trechos_removidos >= 1 and rec.trechos_novos >= 1
    sem_vetor = db_session.execute(text(
        "SELECT count(*) FROM trecho_normativo WHERE fonte_versao_id = :v AND embedding IS NULL"), {"v": v.id}).scalar()
    assert sem_vetor == 0
    unico = db_session.execute(text(
        "SELECT parent_id FROM dispositivo WHERE fonte_versao_id = :v AND paragrafo = 'unico'"), {"v": v.id}).scalar()
    assert unico == depois["7"]
    # Idempotente: rodar de novo não muda nada.
    de_novo = catalogo.reaplicar_dispositivos(db_session, v.id, rotulo=ROTULO, texto=TEXTO, embed=_embed,
                                              modelo_embedding=cs.MODELO, aplicar=True)
    assert (de_novo.saem, de_novo.entram) == ([], [])


def test_recusa_quando_o_que_sai_esta_citado(db_session, monkeypatch):
    v = _versao_com_corte_antigo(db_session, monkeypatch)
    # Referência externa simulada: o trecho do falso art. 29 faz o papel de quem cita.
    monkeypatch.setattr(catalogo, "REFERENCIAS_EXTERNAS", (("trecho_normativo", "dispositivo_id"),))
    with pytest.raises(catalogo.DispositivoCitado, match="trecho_normativo"):
        catalogo.reaplicar_dispositivos(db_session, v.id, rotulo=ROTULO, texto=TEXTO, embed=_embed,
                                        modelo_embedding=cs.MODELO, aplicar=True)
    assert set(_artigos(db_session, v.id)) == {"1", "2", "6", "29"}
