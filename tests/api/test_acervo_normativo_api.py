"""API do acervo normativo e porta de escrita do corpus (ADR-075 A2)."""

from __future__ import annotations

import hashlib
from datetime import timedelta

import pytest
from tests.recuperacao import catalogo_sintetico as cs

from app.api.v1 import acervo_normativo
from app.core.security import create_access_token
from app.services.zona_normativa import curadoria


def _headers(u) -> dict[str, str]:
    tok = create_access_token(subject=u.id, tenant_id=u.tenant_id, expires_delta=timedelta(minutes=30))
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def pessoas(db_session):
    admin = cs.usuario(db_session, "api-admin", superuser=True)
    comum = cs.usuario(db_session, "api-comum", tenant_id=admin.tenant_id)
    return admin, comum


def test_a2_escrita_no_corpus_legado_exige_curadoria(client, db_session, pessoas):
    admin, comum = pessoas
    corpo = {"title": "Lei X", "source_type": "lei", "scope": "federal", "full_text": "Art. 1º x"}
    for u in (comum, admin):   # superusuário sem papel também não escreve
        assert client.post("/api/v1/legislation/documents", json=corpo, headers=_headers(u)).status_code == 403
        assert client.post("/api/v1/knowledge/index", json={
            "source_type": "legislation", "source_ref": "x", "body": "texto"}, headers=_headers(u)).status_code == 403
    curadoria.conceder_papel(db_session, concedente=admin, user_id=comum.id, papel="curar_corpus", area="*")
    r = client.post("/api/v1/legislation/documents", json=corpo, headers=_headers(comum))
    assert r.status_code == 201, r.text


def test_leitura_e_de_todo_usuario_interno(client, db_session, pessoas, monkeypatch):
    _admin, comum = pessoas
    f = cs.fonte(db_session, "decreto|br||6514|2008", rotulo="Decreto 6.514/2008", objetivos=["defesa"])
    v = cs.versao(db_session, f, status="validado")
    cs.trecho(db_session, v, cs.dispositivo(db_session, v, "18", rotulo_fonte="Decreto 6.514/2008"),
              "Art. 18. descumprimento de embargo", 0)
    monkeypatch.setattr(acervo_normativo, "_embed_query", lambda _t: cs.base(0))
    monkeypatch.setattr(acervo_normativo, "_modelo", lambda: cs.MODELO)
    r = client.post("/api/v1/acervo-normativo/recuperar", headers=_headers(comum), json={
        "pergunta": "embargo", "uso": "peca", "data_referencia": "2026-09-22", "objetivo": "defesa",
        "esferas": ["federal"], "uf": "GO"})
    assert r.status_code == 200
    j = r.json()
    assert j["vazio"] is None and j["trechos"][0]["caminho"] == "Decreto 6.514/2008, art. 18"
    r2 = client.post("/api/v1/acervo-normativo/recuperar", headers=_headers(comum), json={
        "pergunta": "embargo", "uso": "peca", "data_referencia": "2026-09-22", "objetivo": "nao_identificado",
        "esferas": ["federal"]})
    assert r2.json()["vazio"]["razao"] == "contexto_insuficiente"
    ficha = client.get(f"/api/v1/acervo-normativo/fontes/{f.id}", headers=_headers(comum)).json()
    assert ficha["versoes"][0]["status_validacao"] == "validado"


def test_percurso_de_curadoria_pela_api(client, db_session, pessoas):
    admin, comum = pessoas
    f = cs.fonte(db_session, "lei|go||18104|2013", rotulo="Lei GO 18.104/2013", ente="go")
    v = cs.versao(db_session, f, hash_original=hashlib.sha256(b"x").hexdigest(), storage_key="k")
    # Sem papel: 403. Conceder é de superusuário.
    prop = {"url_oficial": "https://legisla.casacivil.go.gov.br/x", "texto_conferido_por": "hash",
            "vigencia": "vigente", "nota": "conferido"}
    assert client.post(f"/api/v1/acervo-normativo/versoes/{v.id}/propor", json=prop,
                       headers=_headers(comum)).status_code == 403
    assert client.post("/api/v1/acervo-normativo/curadores", headers=_headers(comum), json={
        "user_id": comum.id, "papel": "curar_corpus", "area": "GO"}).status_code == 403
    for papel in ("curar_corpus", "validar_fonte_normativa"):
        assert client.post("/api/v1/acervo-normativo/curadores", headers=_headers(admin), json={
            "user_id": comum.id, "papel": papel, "area": "GO"}).status_code == 200
    assert client.post(f"/api/v1/acervo-normativo/versoes/{v.id}/propor", json=prop,
                       headers=_headers(comum)).status_code == 200
    r = client.post(f"/api/v1/acervo-normativo/versoes/{v.id}/validar", json={"nota": "li a ficha"},
                    headers=_headers(comum))
    assert r.status_code == 200 and r.json()["para"] == "validado"
    assert client.get("/api/v1/acervo-normativo/cadeia", headers=_headers(comum)).json()["integra"] is True
    # Transição inválida vira 422 com o motivo, não 500.
    r = client.post(f"/api/v1/acervo-normativo/versoes/{v.id}/validar", json={"nota": "de novo"},
                    headers=_headers(comum))
    assert r.status_code == 422
