"""O clique da tela (#278/#282): toda evidência citada abre pelo ID, com as travas da verificação.

`GET /processes/{id}/evidencias/{tipo}/{ref_id}` devolve o que está gravado por trás de cada
``{tipo, id}`` do relatório, do escopo e da Rota. Fora do caso ou do tenant é 404 — nunca "o
mais parecido".
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import text
from tests.comercial.test_comercial_contrato import CCIR, _rota_validada
from tests.motor_juridico.test_motor_contrato import _caso, _login
from tests.recuperacao import catalogo_sintetico as cs


def _url(pid: int, tipo: str, ref_id: int) -> str:
    return f"/api/v1/processes/{pid}/evidencias/{tipo}/{ref_id}"


def test_toda_evidencia_do_relatorio_e_do_escopo_abre_pelo_id(client: TestClient, db_session):
    h, p, hd, rota, passos = _rota_validada(client, db_session)
    r = client.post(f"/api/v1/processes/{p.id}/comercial/redacao", headers=hd)
    assert r.status_code == 201, r.text
    refs = {(e["tipo"], e["id"]) for doc in r.json().values() for s in doc["conteudo"]["secoes"]
            for a in s["afirmacoes"] for e in a["evidencias"]}
    assert {t for t, _ in refs} >= {"execucao_motor", "avaliacao_regra", "documento", "dispositivo", "rota_passo"}
    for tipo, ref_id in sorted(refs):
        d = client.get(_url(p.id, tipo, ref_id), headers=hd)
        assert d.status_code == 200, (tipo, ref_id, d.text)
        corpo = d.json()
        assert (corpo["tipo"], corpo["id"]) == (tipo, ref_id)
        assert corpo["titulo"]
        # O que o detalhe cita também abre: a tela segue a cadeia sem beco.
        for sub in corpo["refs"]:
            assert client.get(_url(p.id, sub["tipo"], sub["id"]), headers=hd).status_code == 200, sub
        if tipo == "documento":
            assert corpo["documento_id"] == ref_id


def test_fundamento_do_passo_abre_o_texto_do_dispositivo(client: TestClient, db_session):
    h, p, hd, rota, passos = _rota_validada(client, db_session)
    passo = passos[CCIR]
    d = client.get(_url(p.id, "dispositivo", passo["fundamento_dispositivo_id"]), headers=hd).json()
    assert d["texto"] and "art" in d["titulo"].lower() and " — " not in d["titulo"]
    assert [r["tipo"] for r in d["refs"]] == ["fonte_versao"]
    assert d["refs"][0]["id"] == passo["fundamento_fonte_versao_id"]

    detalhe_passo = client.get(_url(p.id, "rota_passo", passo["id"]), headers=hd).json()
    assert ("dispositivo", passo["fundamento_dispositivo_id"]) in {(r["tipo"], r["id"]) for r in detalhe_passo["refs"]}
    assert ("avaliacao_regra", passo["origem_avaliacao_id"]) in {(r["tipo"], r["id"]) for r in detalhe_passo["refs"]}


def test_passo_removido_abre_com_o_motivo(client: TestClient, db_session):
    h, p, hd, rota, passos = _rota_validada(client, db_session)
    removido = db_session.execute(
        text("SELECT id FROM rota_passos WHERE rota_id = :r AND deleted_at IS NOT NULL ORDER BY id LIMIT 1"),
        {"r": rota["id"]}).scalar()
    d = client.get(_url(p.id, "rota_passo", removido), headers=hd).json()
    campos = {c["rotulo"]: c["valor"] for c in d["campos"]}
    assert "norma fora do catálogo" in campos["Motivo da remoção"]


def test_fora_do_caso_do_tenant_ou_tipo_desconhecido_e_404(client: TestClient, db_session):
    h, p, hd, rota, passos = _rota_validada(client, db_session)
    outro = _caso(db_session, h.tenant_id, especies=("car",))
    db_session.commit()
    doc_alheio = db_session.execute(text("SELECT id FROM documents WHERE process_id = :p"), {"p": outro.id}).scalar()
    passo_id = passos[CCIR]["id"]

    assert client.get(_url(p.id, "documento", doc_alheio), headers=hd).status_code == 404
    assert client.get(_url(outro.id, "rota_passo", passo_id), headers=hd).status_code == 404
    assert client.get(_url(p.id, "dispositivo", 999_999), headers=hd).status_code == 404
    assert client.get(_url(p.id, "inventado", passo_id), headers=hd).status_code == 404

    intruso = cs.usuario(db_session, "intruso-evidencia")
    db_session.commit()
    hi = _login(client, intruso.email)
    assert client.get(_url(p.id, "rota_passo", passo_id), headers=hi).status_code == 404
