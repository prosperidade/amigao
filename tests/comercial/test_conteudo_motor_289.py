"""#289 — o motor é comparado pelo CONTEÚDO (fatos_hash + regras_hash), não pelo ID da execução.

Decisão do André (25/09): execução nova sempre; desatualizar a cadeia comercial e reabrir a ciência
do alerta crítico só quando os fatos lidos ou as regras avaliadas mudam.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from tests.comercial.test_comercial_contrato import _escopo_aprovado, _metodos, _orcamento_aprovado, _rota_validada
from tests.motor_juridico.test_motor_contrato import _caso, _catalogo, _homologador, _login, _motor_ativo

from app.models.comercial import RedacaoComercial
from app.models.document import Document
from app.models.entrada_semantica import ClassificacaoDocumento
from app.services.comercial.base import motivos_de_desatualizacao


def _atualidades(client: TestClient, pid: int, hd) -> dict[str, dict]:
    red = client.get(f"/api/v1/processes/{pid}/comercial/redacao", headers=hd).json()
    orc = client.get(f"/api/v1/processes/{pid}/comercial/orcamento", headers=hd).json()["orcamento"]
    return {"relatorio": red["relatorio_preliminar"]["atualidade"],
            "escopo": red["especificacao_escopo"]["atualidade"], "orcamento": orc["atualidade"]}


def _novo_documento(db, p, especie: str) -> None:
    doc = Document(tenant_id=p.tenant_id, process_id=p.id, original_file_name=f"{especie}.pdf",
                   filename=f"{especie}.pdf", content_type="application/pdf",
                   storage_key=f"t/{uuid.uuid4().hex}", document_type=especie)
    db.add(doc)
    db.flush()
    db.add(ClassificacaoDocumento(tenant_id=p.tenant_id, documento_id=doc.id, versao=1, tipo_proposto=especie,
                                  motivo="teste #289"))
    db.commit()


def test_reexecutar_sem_fato_novo_nao_desatualiza_a_cadeia(client: TestClient, db_session):
    h, p, hd, rota, passos = _rota_validada(client, db_session)
    _metodos(client, hd)
    _escopo_aprovado(client, p.id, hd)
    _orcamento_aprovado(client, p.id, hd)
    assert all(a["estado"] == "vigente" for a in _atualidades(client, p.id, hd).values())

    r = client.post(f"/api/v1/processes/{p.id}/rota/gerar-motor", headers=hd)
    assert r.status_code == 201, r.text
    nova = client.post(f"/api/v1/processes/{p.id}/motor/avaliar", headers=hd).json()
    assert nova["execucao_id"] > r.json()["execucao"]["execucao_id"]  # execução nova sempre

    for nome, a in _atualidades(client, p.id, hd).items():
        assert a == {"estado": "vigente", "motivos": []}, (nome, a)


def test_fato_novo_desatualiza_com_o_motivo(client: TestClient, db_session):
    h, p, hd, rota, passos = _rota_validada(client, db_session)
    _metodos(client, hd)
    _escopo_aprovado(client, p.id, hd)
    _orcamento_aprovado(client, p.id, hd)
    _novo_documento(db_session, p, "ccir")
    client.post(f"/api/v1/processes/{p.id}/motor/avaliar", headers=hd)

    at = _atualidades(client, p.id, hd)
    assert at["escopo"]["estado"] == "desatualizado"
    assert any(m.startswith("Os fatos lidos pelo motor jurídico mudaram") for m in at["escopo"]["motivos"])
    assert not any("regras" in m for m in at["escopo"]["motivos"])
    assert at["orcamento"]["estado"] == "desatualizado"


def test_base_antiga_so_com_o_id_da_execucao_e_lida_pelo_conteudo(client: TestClient, db_session):
    h, p, hd, rota, passos = _rota_validada(client, db_session)
    _escopo_aprovado(client, p.id, hd)
    for r in db_session.query(RedacaoComercial).filter(RedacaoComercial.process_id == p.id):
        r.base = {k: v for k, v in r.base.items() if k != "motor"}  # como gravava antes do #289
    db_session.commit()
    client.post(f"/api/v1/processes/{p.id}/motor/avaliar", headers=hd)
    red = client.get(f"/api/v1/processes/{p.id}/comercial/redacao", headers=hd).json()
    assert red["especificacao_escopo"]["atualidade"] == {"estado": "vigente", "motivos": []}


def test_regra_diferente_desatualiza_mesmo_com_os_mesmos_fatos():
    antes = {"execucao_motor": 1, "motor": {"fatos_hash": "f", "regras_hash": "r1"}}
    agora = {"execucao_motor": 2, "motor": {"fatos_hash": "f", "regras_hash": "r2"}}
    assert motivos_de_desatualizacao(antes, agora) == ["As regras do motor jurídico mudaram (execução #2)"]
    igual = {"execucao_motor": 3, "motor": {"fatos_hash": "f", "regras_hash": "r1"}}
    assert motivos_de_desatualizacao(antes, igual) == []


def _caso_com_alerta(client: TestClient, db):
    h = _homologador(db)
    _catalogo(db)
    _motor_ativo(db, h)
    p = _caso(db, h.tenant_id, especies=("escritura_publica",), falecimento=True)
    db.commit()
    hd = _login(client, h.email)
    ex = client.post(f"/api/v1/processes/{p.id}/rota/gerar-motor", headers=hd).json()["execucao"]
    assert ex["alertas_sem_ciencia"], "o cenário precisa de alerta crítico"
    for av_id in ex["alertas_sem_ciencia"]:
        assert client.post(f"/api/v1/processes/{p.id}/motor/alertas/{av_id}/ciencia", headers=hd,
                           json={"justificativa": "inventário em andamento"}).status_code == 201
    return h, p, hd, ex


def test_ciencia_vale_para_execucao_de_mesmo_conteudo(client: TestClient, db_session):
    h, p, hd, ex = _caso_com_alerta(client, db_session)
    nova = client.post(f"/api/v1/processes/{p.id}/motor/avaliar", headers=hd).json()
    assert nova["execucao_id"] != ex["execucao_id"]
    assert nova["alertas_sem_ciencia"] == []
    herdada = next(a for a in nova["avaliacoes"] if a["avaliacao_id"] not in ex["alertas_sem_ciencia"]
                   and any(e.get("tipo") == "alerta_critico" for e in a["efeitos"]))
    assert herdada["ciencia"]["herdada"] is True
    assert herdada["ciencia"]["avaliacao_id"] in ex["alertas_sem_ciencia"]


def test_fato_novo_reabre_a_ciencia(client: TestClient, db_session):
    h, p, hd, ex = _caso_com_alerta(client, db_session)
    _novo_documento(db_session, p, "ccir")
    nova = client.post(f"/api/v1/processes/{p.id}/motor/avaliar", headers=hd).json()
    assert nova["fatos_hash"] != ex["fatos_hash"]
    assert nova["alertas_sem_ciencia"], "fato diferente: a ciência anterior não vale"
