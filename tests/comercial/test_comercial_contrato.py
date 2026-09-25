"""Contrato do fechamento comercial (ADR-074): cadeia sem diagnóstico, Redator com evidência por
ID, orçamento por passo com métodos do tenant, atualidade sem retrocesso, proposta do orçamento.

Cenário: caso de GO com CAR e quatro matrículas (o #23 do gate), Rota gerada pelo motor com as
regras reais do gate sobre catálogo sintético, validada e fechada pela API.
"""

from __future__ import annotations

import hashlib
import uuid

from fastapi.testclient import TestClient
from tests.motor_juridico.test_motor_contrato import _caso, _catalogo, _homologador, _login, _motor_ativo
from tests.recuperacao import catalogo_sintetico as cs

from app.models.comercial import Orcamento
from app.models.evidence import EvidenceReview, EvidenceVersion
from app.models.rota import Rota, RotaStatus
from app.services.comercial import evidencia
from app.services.connected_agents import CHAINS, DEPENDENCIES

MAPEAR = "Mapear os componentes do imóvel (matrículas, posses e cadastros)"
CCIR = "Emitir ou regularizar o CCIR do imóvel"


def _rota_validada(client: TestClient, db, *, fechar: bool = True):
    """#23: CAR + 4 matrículas. Passos com fundamento viram item de proposta; os outros saem com motivo."""
    h = _homologador(db)
    _catalogo(db)
    _motor_ativo(db, h)
    p = _caso(db, h.tenant_id, especies=("car",) + ("certidao_matricula",) * 4)
    db.commit()
    hd = _login(client, h.email)
    r = client.post(f"/api/v1/processes/{p.id}/rota/gerar-motor", headers=hd)
    assert r.status_code == 201, r.text
    rota = r.json()["rota"]["rota"]
    passos = {}
    for passo in rota["passos"]:
        url = f"/api/v1/rotas/{rota['id']}/passos/{passo['id']}"
        if passo["fundamento_fonte_versao_id"] is None:
            assert client.delete(url, headers=hd, params={"motivo": f"norma fora do catálogo ({passo['titulo'][:20]})"}
                                 ).status_code == 204
            continue
        assert client.patch(url, headers=hd, json={"classificacao": "item_proposta"}).status_code == 200
        assert client.post(url + "/validar", headers=hd).status_code == 200, passo["titulo"]
        passos[passo["titulo"]] = passo
    if fechar:
        r = client.post(f"/api/v1/rotas/{rota['id']}/fechar", headers=hd)
        assert r.status_code == 200, r.text
    return h, p, hd, rota, passos


def _metodos(client: TestClient, hd):
    """Hora técnica padrão (8 h × R$ 250) e CCIR a preço fixo mapeado à regra REG-FUN-002."""
    r = client.post("/api/v1/comercial/metodos", headers=hd, json={
        "codigo": "hora_tecnica", "nome": "Hora técnica", "unidade": "hora", "valor_unitario": "250.00",
        "quantidade_padrao": "8", "padrao": True})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/comercial/metodos", headers=hd, json={
        "codigo": "ccir", "nome": "Emissão de CCIR", "unidade": "fixo", "valor_unitario": "900.00",
        "rule_ids": ["REG-FUN-002"]})
    assert r.status_code == 201, r.text


def _escopo_aprovado(client: TestClient, pid: int, hd) -> dict:
    r = client.post(f"/api/v1/processes/{pid}/comercial/redacao", headers=hd)
    assert r.status_code == 201, r.text
    escopo = r.json()["especificacao_escopo"]
    r = client.post(f"/api/v1/processes/{pid}/comercial/redacao/{escopo['id']}/revisar", headers=hd,
                    json={"acao": "aprovar", "justificativa": "escopo confere com a Rota"})
    assert r.status_code == 200, r.text
    return r.json()


def _orcamento_aprovado(client: TestClient, pid: int, hd) -> dict:
    r = client.post(f"/api/v1/processes/{pid}/comercial/orcamento", headers=hd)
    assert r.status_code == 201, r.text
    o = r.json()
    r = client.post(f"/api/v1/processes/{pid}/comercial/orcamento/{o['id']}/revisar", headers=hd,
                    json={"acao": "aprovar", "justificativa": "preços conferidos"})
    assert r.status_code == 200, r.text
    return r.json()


def _conclusao_do_diagnostico(db, tenant_id: int, process_id: int) -> EvidenceVersion:
    content = {"kind": "conclusao", "statement": "Hipótese do diagnóstico", "conclusion_class": "hipotese"}
    row = EvidenceVersion(tenant_id=tenant_id, process_id=process_id, object_id=f"conclusion:{uuid.uuid4().hex}",
                          version=1, kind="conclusao", content=content, agent_name="diagnostico",
                          content_hash=hashlib.sha256(str(content).encode()).hexdigest())
    db.add(row)
    db.flush()
    return row


# ---------------------------------------------------------------------------
# Cadeia (ruptura 4)
# ---------------------------------------------------------------------------

def test_cadeia_comercial_nao_roda_nem_espera_o_diagnostico():
    assert CHAINS["gerar_proposta"] == ["redator", "orcamento"]
    assert DEPENDENCIES["orcamento"] == ["redator"]
    assert "redator" not in DEPENDENCIES
    assert CHAINS["diagnostico_completo"][-1] == "diagnostico"


def test_cadeia_sem_rota_falha_com_motivo_e_retoma_ate_o_orcamento(client: TestClient, db_session):
    h, p, hd, rota, _ = _rota_validada(client, db_session, fechar=False)
    _metodos(client, hd)
    r = client.post("/api/v1/agents/chain", headers=hd, json={"chain_name": "gerar_proposta", "process_id": p.id})
    assert r.status_code == 200, r.text
    ex = r.json()
    assert ex["steps"][0]["status"] == "failed" and "Rota validada ausente" in ex["steps"][0]["error"]
    assert ex["steps"][1]["status"] == "awaiting_review"

    assert client.post(f"/api/v1/rotas/{rota['id']}/fechar", headers=hd).status_code == 200
    # Diagnóstico em revisão no caso: não impede nada, vira ressalva.
    _conclusao_do_diagnostico(db_session, h.tenant_id, p.id)
    db_session.commit()

    retoma = lambda ex: client.post(f"/api/v1/evidence/executions/{ex['id']}/resume", headers=hd,  # noqa: E731
                                    json={"expected_revision": ex["revision"]}).json()
    ex = retoma(ex)
    assert [s["status"] for s in ex["steps"]] == ["completed", "awaiting_review"]
    escopo = client.get(f"/api/v1/processes/{p.id}/comercial/redacao", headers=hd).json()["especificacao_escopo"]
    client.post(f"/api/v1/processes/{p.id}/comercial/redacao/{escopo['id']}/revisar", headers=hd,
                json={"acao": "aprovar", "justificativa": "ok"})
    ex = retoma(ex)
    assert [s["status"] for s in ex["steps"]] == ["completed", "completed"] and ex["completed"] is False
    o = client.get(f"/api/v1/processes/{p.id}/comercial/orcamento", headers=hd).json()["orcamento"]
    assert {x["tipo"] for x in o["ressalvas"]} == {"diagnostico_em_revisao"}
    client.post(f"/api/v1/processes/{p.id}/comercial/orcamento/{o['id']}/revisar", headers=hd,
                json={"acao": "aprovar", "justificativa": "ok"})
    ex = retoma(ex)
    assert ex["completed"] is True and ex["status"] == "completed"


def test_redator_fora_da_cadeia_comercial_e_capacidade_insuficiente():
    from app.services.agent_capabilities import capability_manifest

    assert capability_manifest("redator", {"chain": "gerar_proposta"})["status"] == "available"
    assert capability_manifest("orcamento", {"chain": "orcamento"})["status"] == "available"
    peca = capability_manifest("redator", {"chain": "gerar_documento"})
    assert peca["status"] == "capacidade_insuficiente"
    assert "Peça técnica definitiva" in peca["missing"][0]["reason"]


# ---------------------------------------------------------------------------
# Redator
# ---------------------------------------------------------------------------

def test_relatorio_e_escopo_cada_afirmacao_com_evidencia_resolvida(client: TestClient, db_session):
    h, p, hd, rota, passos = _rota_validada(client, db_session)
    r = client.post(f"/api/v1/processes/{p.id}/comercial/redacao", headers=hd)
    assert r.status_code == 201, r.text
    rel, esc = r.json()["relatorio_preliminar"], r.json()["especificacao_escopo"]
    for doc in (rel, esc):
        secoes = doc["conteudo"]["secoes"]
        assert all(a["evidencias"] for s in secoes for a in s["afirmacoes"])
        assert evidencia.verificar(db_session, secoes, tenant_id=h.tenant_id, process_id=p.id) == []
        assert doc["atualidade"] == {"estado": "vigente", "motivos": []}

    por_chave = {s["chave"]: s["afirmacoes"] for s in esc["conteudo"]["secoes"]}
    incluidos = {a["id"]: a for a in por_chave["incluido"]}
    ccir = incluidos[f"escopo:{passos[CCIR]['id']}"]
    dispositivos = [e["id"] for e in ccir["evidencias"] if e["tipo"] == "dispositivo"]
    assert dispositivos == [passos[CCIR]["fundamento_dispositivo_id"]]
    assert "Lei 5.868/1972" in ccir["texto"] or "art. 2" in ccir["texto"]
    # Os dois passos sem norma saíram com motivo: "fora do escopo", com o motivo gravado.
    assert len(por_chave["fora"]) == 2 and all("norma fora do catálogo" in a["texto"] for a in por_chave["fora"])

    situacao = {a["id"]: a for s in rel["conteudo"]["secoes"] if s["chave"] == "situacao" for a in s["afirmacoes"]}
    matriculas = situacao["situacao:dominio.matriculas_no_dossie"]
    assert "4 certidão" in matriculas["texto"]
    assert len([e for e in matriculas["evidencias"] if e["tipo"] == "documento"]) == 4
    assert "Não consta CCIR" in situacao["situacao:ccir.no_dossie"]["texto"]
    lacunas = [a for s in rel["conteudo"]["secoes"] if s["chave"] == "lacunas" for a in s["afirmacoes"]]
    assert any("situação do titular" in a["texto"] for a in lacunas)


def test_evidencia_inexistente_ou_de_outro_caso_e_recusada(client: TestClient, db_session):
    h, p, hd, rota, passos = _rota_validada(client, db_session)
    outro = _caso(db_session, h.tenant_id, especies=("car",))
    doc_alheio = db_session.execute(
        __import__("sqlalchemy").text("SELECT id FROM documents WHERE process_id = :p"), {"p": outro.id}).scalar()
    secoes = [{"chave": "x", "afirmacoes": [
        evidencia.afirmacao("a1", "sem prova", []),
        evidencia.afirmacao("a2", "dispositivo inventado", [evidencia.ref("dispositivo", 999_999, "x")]),
        evidencia.afirmacao("a3", "documento de outro caso", [evidencia.ref("documento", doc_alheio, "x")]),
        evidencia.afirmacao("a4", "passo real", [evidencia.ref("rota_passo", passos[CCIR]["id"], "ok")]),
    ]}]
    falhas = evidencia.verificar(db_session, secoes, tenant_id=h.tenant_id, process_id=p.id)
    assert len(falhas) == 3
    assert any(f.startswith("a1:") for f in falhas) and any("dispositivo 999999" in f for f in falhas)
    assert any(f.startswith("a3:") for f in falhas) and not any(f.startswith("a4:") for f in falhas)


def test_redacao_sem_rota_validada_e_422(client: TestClient, db_session):
    h, p, hd, rota, _ = _rota_validada(client, db_session, fechar=False)
    r = client.post(f"/api/v1/processes/{p.id}/comercial/redacao", headers=hd)
    assert r.status_code == 422 and "Rota validada ausente" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Orçamento
# ---------------------------------------------------------------------------

def test_orcamento_exige_escopo_aprovado_e_metodo_padrao(client: TestClient, db_session):
    h, p, hd, rota, _ = _rota_validada(client, db_session)
    r = client.post(f"/api/v1/processes/{p.id}/comercial/orcamento", headers=hd)
    assert r.status_code == 422 and "Especificação de escopo ausente" in r.json()["detail"]
    client.post(f"/api/v1/processes/{p.id}/comercial/redacao", headers=hd)
    r = client.post(f"/api/v1/processes/{p.id}/comercial/orcamento", headers=hd)
    assert r.status_code == 422 and "não foi aprovada" in r.json()["detail"]
    escopo = client.get(f"/api/v1/processes/{p.id}/comercial/redacao", headers=hd).json()["especificacao_escopo"]
    client.post(f"/api/v1/processes/{p.id}/comercial/redacao/{escopo['id']}/revisar", headers=hd,
                json={"acao": "aprovar", "justificativa": "ok"})
    r = client.post(f"/api/v1/processes/{p.id}/comercial/orcamento", headers=hd)
    assert r.status_code == 422 and "métodos de orçamento" in r.json()["detail"]
    client.post("/api/v1/comercial/metodos", headers=hd, json={
        "codigo": "ccir", "nome": "CCIR", "unidade": "fixo", "valor_unitario": "900", "rule_ids": ["REG-FUN-002"]})
    r = client.post(f"/api/v1/processes/{p.id}/comercial/orcamento", headers=hd)
    assert r.status_code == 422 and "método padrão" in r.json()["detail"]


def test_orcamento_um_item_por_passo_com_metodo_do_tenant(client: TestClient, db_session):
    h, p, hd, rota, passos = _rota_validada(client, db_session)
    _metodos(client, hd)
    _escopo_aprovado(client, p.id, hd)
    o = _orcamento_aprovado(client, p.id, hd)
    itens = {i["rota_passo_id"]: i for i in o["itens"]}
    assert set(itens) == {passos[MAPEAR]["id"], passos[CCIR]["id"]}
    assert itens[passos[CCIR]["id"]]["escolha"] == "regra" and itens[passos[CCIR]["id"]]["total"] == "900.00"
    mapear = itens[passos[MAPEAR]["id"]]
    assert (mapear["escolha"], mapear["total"], mapear["calculo"]) == ("padrao", "2000.00",
                                                                        "8 h × R$ 250,00 = R$ 2.000,00")
    assert o["total"] == "2900.00"
    assert [f["motivo"] for f in o["fora"]] and all("norma fora do catálogo" in f["motivo"] for f in o["fora"])
    assert {x["tipo"] for x in o["ressalvas"]} == {"sem_diagnostico"}


def test_remover_passo_com_motivo_desatualiza_sem_retroceder_e_some_do_orcamento(client: TestClient, db_session):
    h, p, hd, rota, passos = _rota_validada(client, db_session)
    _metodos(client, hd)
    _escopo_aprovado(client, p.id, hd)
    antes = _orcamento_aprovado(client, p.id, hd)
    macro_antes = db_session.execute(__import__("sqlalchemy").text(
        "SELECT macroetapa FROM processes WHERE id = :p"), {"p": p.id}).scalar()

    url = f"/api/v1/rotas/{rota['id']}/passos/{passos[MAPEAR]['id']}"
    assert client.delete(url, headers=hd, params={"motivo": "cliente já tem o mapeamento"}).status_code == 204

    lido = client.get(f"/api/v1/processes/{p.id}/comercial/orcamento", headers=hd).json()["orcamento"]
    assert lido["id"] == antes["id"] and lido["estado_revisao"] == "aprovada"  # a aprovação não se perde
    assert lido["atualidade"]["estado"] == "desatualizado"
    assert any("cliente já tem o mapeamento" in m for m in lido["atualidade"]["motivos"])
    db_session.expire_all()
    assert db_session.get(Rota, rota["id"]).status == RotaStatus.validada  # não retrocede
    assert db_session.execute(__import__("sqlalchemy").text(
        "SELECT macroetapa FROM processes WHERE id = :p"), {"p": p.id}).scalar() == macro_antes
    # Aprovar versão desatualizada é recusado; orçamento novo exige o escopo novo.
    r = client.post(f"/api/v1/processes/{p.id}/comercial/orcamento/{antes['id']}/revisar", headers=hd,
                    json={"acao": "aprovar", "justificativa": "x"})
    assert r.status_code == 422
    r = client.post(f"/api/v1/processes/{p.id}/comercial/orcamento", headers=hd)
    assert r.status_code == 422 and "desatualizada" in r.json()["detail"]

    _escopo_aprovado(client, p.id, hd)
    novo = _orcamento_aprovado(client, p.id, hd)
    assert novo["versao"] == antes["versao"] + 1 and novo["total"] == "900.00"
    assert [i["rota_passo_id"] for i in novo["itens"]] == [passos[CCIR]["id"]]
    assert any(f["rota_passo_id"] == passos[MAPEAR]["id"] and "cliente já tem o mapeamento" in f["motivo"]
               for f in novo["fora"])
    versoes = client.get(f"/api/v1/processes/{p.id}/comercial/orcamento", headers=hd).json()["versoes"]
    assert [v["superada_em"] is not None for v in versoes] == [True, False]


def test_diagnostico_em_revisao_e_ressalva_e_revisao_posterior_desatualiza(client: TestClient, db_session):
    h, p, hd, rota, passos = _rota_validada(client, db_session)
    _metodos(client, hd)
    conclusao = _conclusao_do_diagnostico(db_session, h.tenant_id, p.id)
    db_session.commit()
    _escopo_aprovado(client, p.id, hd)
    o = _orcamento_aprovado(client, p.id, hd)
    assert o["ressalvas"][0]["tipo"] == "diagnostico_em_revisao"
    assert o["ressalvas"][0]["conclusoes"] == [conclusao.id]

    db_session.add(EvidenceReview(tenant_id=h.tenant_id, process_id=p.id, evidence_id=conclusao.id, revision=1,
                                  action="aprovar", author_id=h.id, justification="ok", premises=[]))
    db_session.commit()
    lido = client.get(f"/api/v1/processes/{p.id}/comercial/orcamento", headers=hd).json()["orcamento"]
    assert lido["atualidade"]["estado"] == "desatualizado"
    assert any("diagnóstico mudou" in m for m in lido["atualidade"]["motivos"])


def test_escolha_do_consultor_gera_versao_e_sobrevive(client: TestClient, db_session):
    h, p, hd, rota, passos = _rota_validada(client, db_session)
    _metodos(client, hd)
    _escopo_aprovado(client, p.id, hd)
    v1 = _orcamento_aprovado(client, p.id, hd)
    r = client.patch(f"/api/v1/processes/{p.id}/comercial/orcamento/passos/{passos[MAPEAR]['id']}", headers=hd,
                     json={"quantidade": "10"})
    assert r.status_code == 201, r.text
    v2 = r.json()
    assert v2["versao"] == v1["versao"] + 1 and v2["estado_revisao"] == "proposta"
    mapear = next(i for i in v2["itens"] if i["rota_passo_id"] == passos[MAPEAR]["id"])
    assert mapear["total"] == "2500.00" and "quantidade do consultor" in mapear["calculo"]
    # "10" enviado e "10.00" relido do banco são a mesma escolha: a v2 nasce atual e aprovável.
    lida = client.get(f"/api/v1/processes/{p.id}/comercial/orcamento", headers=hd).json()["orcamento"]
    assert lida["id"] == v2["id"] and lida["atualidade"] == {"estado": "vigente", "motivos": []}
    r = client.post(f"/api/v1/processes/{p.id}/comercial/orcamento/{v2['id']}/revisar", headers=hd,
                    json={"acao": "aprovar", "justificativa": "quantidade conferida"})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/processes/{p.id}/comercial/orcamento", headers=hd)
    v3 = r.json()
    assert next(i for i in v3["itens"] if i["rota_passo_id"] == passos[MAPEAR]["id"])["total"] == "2500.00"
    r = client.patch(f"/api/v1/processes/{p.id}/comercial/orcamento/passos/{passos[MAPEAR]['id']}", headers=hd,
                     json={"metodo_codigo": "inexistente"})
    assert r.status_code == 422


def test_preco_novo_e_versao_e_o_orcamento_guarda_a_foto(client: TestClient, db_session):
    h, p, hd, rota, passos = _rota_validada(client, db_session)
    _metodos(client, hd)
    _escopo_aprovado(client, p.id, hd)
    o = _orcamento_aprovado(client, p.id, hd)
    r = client.post("/api/v1/comercial/metodos", headers=hd, json={
        "codigo": "hora_tecnica", "nome": "Hora técnica", "unidade": "hora", "valor_unitario": "300.00",
        "quantidade_padrao": "8", "padrao": True})
    assert r.status_code == 201 and r.json()["versao"] == 2
    lido = client.get(f"/api/v1/processes/{p.id}/comercial/orcamento", headers=hd).json()["orcamento"]
    assert lido["total"] == o["total"]  # foto
    assert any("hora_tecnica" in m for m in lido["atualidade"]["motivos"])
    # Segundo método padrão é recusado.
    r = client.post("/api/v1/comercial/metodos", headers=hd, json={
        "codigo": "outro", "nome": "Outro", "unidade": "fixo", "valor_unitario": "1", "padrao": True})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Proposta (emenda ao ADR-028)
# ---------------------------------------------------------------------------

def test_proposta_nasce_do_orcamento_e_nao_aceita_sobre_orcamento_desatualizado(client: TestClient, db_session):
    h, p, hd, rota, passos = _rota_validada(client, db_session)
    _metodos(client, hd)
    _escopo_aprovado(client, p.id, hd)
    o = _orcamento_aprovado(client, p.id, hd)

    draft = client.get("/api/v1/proposals/generate-draft", headers=hd, params={"process_id": p.id})
    assert draft.status_code == 200, draft.text
    draft = draft.json()
    assert draft["orcamento_id"] == o["id"] and draft["suggested_value"] == 2900.0
    assert {i["orcamento_item_id"] for i in draft["scope_items"]} == {i["id"] for i in o["itens"]}

    r = client.post("/api/v1/proposals/", headers=hd, json={
        "client_id": p.client_id, "process_id": p.id, "title": "Proposta", "orcamento_id": o["id"],
        "scope_items": [{"description": "inventado", "total": 1}], "total_value": 1})
    assert r.status_code == 201, r.text
    prop = r.json()
    assert prop["orcamento_id"] == o["id"] and prop["total_value"] == 2900.0
    assert [i["description"] for i in prop["scope_items"]] == [i["descricao"] for i in o["itens"]]
    r = client.patch(f"/api/v1/proposals/{prop['id']}", headers=hd, json={"total_value": 10})
    assert r.status_code == 422

    assert client.post(f"/api/v1/proposals/{prop['id']}/send", headers=hd).status_code == 200
    url = f"/api/v1/rotas/{rota['id']}/passos/{passos[MAPEAR]['id']}"
    assert client.delete(url, headers=hd, params={"motivo": "fora do contrato"}).status_code == 204
    r = client.post(f"/api/v1/proposals/{prop['id']}/accept", headers=hd)
    assert r.status_code == 422 and "orçamento" in r.json()["detail"]


def test_proposta_nao_nasce_de_orcamento_nao_aprovado(client: TestClient, db_session):
    h, p, hd, rota, passos = _rota_validada(client, db_session)
    _metodos(client, hd)
    _escopo_aprovado(client, p.id, hd)
    client.post(f"/api/v1/processes/{p.id}/comercial/orcamento", headers=hd)
    r = client.get("/api/v1/proposals/generate-draft", headers=hd, params={"process_id": p.id})
    assert r.status_code == 422 and "não foi aprovado" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Isolamento
# ---------------------------------------------------------------------------

def test_outro_tenant_nao_le_orcamento_nem_metodos(client: TestClient, db_session):
    h, p, hd, rota, passos = _rota_validada(client, db_session)
    _metodos(client, hd)
    _escopo_aprovado(client, p.id, hd)
    _orcamento_aprovado(client, p.id, hd)
    intruso = cs.usuario(db_session, "intruso-comercial")
    db_session.commit()
    hi = _login(client, intruso.email)
    assert client.get(f"/api/v1/processes/{p.id}/comercial/orcamento", headers=hi).status_code == 404
    assert client.get(f"/api/v1/processes/{p.id}/comercial/redacao", headers=hi).status_code == 404
    assert client.post(f"/api/v1/processes/{p.id}/comercial/orcamento", headers=hi).status_code == 404
    assert client.get("/api/v1/comercial/metodos", headers=hi).json() == {"correntes": [], "versoes": []}
    assert db_session.query(Orcamento).filter(Orcamento.tenant_id == intruso.tenant_id).count() == 0


def test_cadeia_de_novo_reaproveita_o_que_esta_atual_e_aprovado(client: TestClient, db_session):
    h, p, hd, rota, passos = _rota_validada(client, db_session)
    _metodos(client, hd)
    escopo = _escopo_aprovado(client, p.id, hd)
    o = _orcamento_aprovado(client, p.id, hd)
    ex = client.post("/api/v1/agents/chain", headers=hd, json={"chain_name": "gerar_proposta", "process_id": p.id}).json()
    assert ex["completed"] is True
    lido = client.get(f"/api/v1/processes/{p.id}/comercial/redacao", headers=hd).json()
    assert lido["especificacao_escopo"]["id"] == escopo["id"] and lido["especificacao_escopo"]["estado_revisao"] == "aprovada"
    assert client.get(f"/api/v1/processes/{p.id}/comercial/orcamento", headers=hd).json()["orcamento"]["id"] == o["id"]


def test_alerta_com_ciencia_na_execucao_mais_recente_aparece_como_ciente(client: TestClient, db_session):
    """Regressão do #25 de dev: passos da execução N, ciência do alerta na N+1 (a que o `fechar` exige)."""
    h = _homologador(db_session)
    _catalogo(db_session)
    _motor_ativo(db_session, h)
    p = _caso(db_session, h.tenant_id, especies=("escritura_publica",), falecimento=True)
    db_session.commit()
    hd = _login(client, h.email)
    rota = client.post(f"/api/v1/processes/{p.id}/rota/gerar-motor", headers=hd).json()["rota"]["rota"]
    for passo in rota["passos"]:
        url = f"/api/v1/rotas/{rota['id']}/passos/{passo['id']}"
        if passo["fundamento_fonte_versao_id"] is None:
            client.delete(url, headers=hd, params={"motivo": "norma ausente"})
        else:
            client.patch(url, headers=hd, json={"classificacao": "item_proposta"})
            client.post(url + "/validar", headers=hd)
    nova = client.post(f"/api/v1/processes/{p.id}/motor/avaliar", headers=hd).json()
    for av_id in nova["alertas_sem_ciencia"]:
        assert client.post(f"/api/v1/processes/{p.id}/motor/alertas/{av_id}/ciencia", headers=hd,
                           json={"justificativa": "inventário em andamento"}).status_code == 201
    assert client.post(f"/api/v1/rotas/{rota['id']}/fechar", headers=hd).status_code == 200
    rel = client.post(f"/api/v1/processes/{p.id}/comercial/redacao", headers=hd).json()["relatorio_preliminar"]
    alertas = next(s for s in rel["conteudo"]["secoes"] if s["chave"] == "alertas")["afirmacoes"]
    assert alertas and all("Ciência registrada" in a["texto"] for a in alertas)
    assert all(any(e["tipo"] == "ciencia_alerta" for e in a["evidencias"]) for a in alertas)



# ---------------------------------------------------------------------------
# Achados da revisão independente
# ---------------------------------------------------------------------------

def test_escopo_rejeitado_depois_arrasta_o_orcamento(client: TestClient, db_session):
    h, p, hd, rota, passos = _rota_validada(client, db_session)
    _metodos(client, hd)
    escopo = _escopo_aprovado(client, p.id, hd)
    _orcamento_aprovado(client, p.id, hd)
    r = client.post(f"/api/v1/processes/{p.id}/comercial/redacao/{escopo['id']}/revisar", headers=hd,
                    json={"acao": "rejeitar", "justificativa": "escopo não confere"})
    assert r.status_code == 200
    lido = client.get(f"/api/v1/processes/{p.id}/comercial/orcamento", headers=hd).json()["orcamento"]
    assert lido["atualidade"]["estado"] == "desatualizado"
    assert any("não está aprovada" in m for m in lido["atualidade"]["motivos"])
    r = client.get("/api/v1/proposals/generate-draft", headers=hd, params={"process_id": p.id})
    assert r.status_code == 422


def test_metodo_novo_mapeado_a_regra_desatualiza_o_orcamento(client: TestClient, db_session):
    h, p, hd, rota, passos = _rota_validada(client, db_session)
    _metodos(client, hd)
    _escopo_aprovado(client, p.id, hd)
    _orcamento_aprovado(client, p.id, hd)
    r = client.post("/api/v1/comercial/metodos", headers=hd, json={
        "codigo": "mapeamento", "nome": "Mapeamento", "unidade": "fixo", "valor_unitario": "1200",
        "rule_ids": ["REG-BR-CAR-007"]})
    assert r.status_code == 201
    lido = client.get(f"/api/v1/processes/{p.id}/comercial/orcamento", headers=hd).json()["orcamento"]
    assert lido["atualidade"]["estado"] == "desatualizado"
    assert any(f"passo {passos[MAPEAR]['id']} mudaria" in m for m in lido["atualidade"]["motivos"])


def test_nova_versao_da_proposta_renegocia_sobre_o_orcamento(client: TestClient, db_session):
    h, p, hd, rota, passos = _rota_validada(client, db_session)
    _metodos(client, hd)
    _escopo_aprovado(client, p.id, hd)
    o = _orcamento_aprovado(client, p.id, hd)
    prop = client.post("/api/v1/proposals/", headers=hd, json={
        "client_id": p.client_id, "process_id": p.id, "title": "Proposta"}).json()
    assert prop["orcamento_id"] == o["id"]
    client.post(f"/api/v1/proposals/{prop['id']}/send", headers=hd)
    client.post(f"/api/v1/proposals/{prop['id']}/reject", headers=hd)
    r = client.post(f"/api/v1/proposals/{prop['id']}/nova-versao", headers=hd)
    assert r.status_code == 201, r.text
    nova = r.json()
    assert nova["orcamento_id"] == o["id"] and nova["total_value"] == 2900.0
    assert {i["orcamento_item_id"] for i in nova["scope_items"]} == {i["id"] for i in o["itens"]}
    assert client.patch(f"/api/v1/proposals/{nova['id']}", headers=hd, json={"total_value": 1}).status_code == 422


def test_retomada_com_recalculo_reinicia_o_orcamento_junto_do_escopo(client: TestClient, db_session):
    h, p, hd, rota, passos = _rota_validada(client, db_session)
    _metodos(client, hd)
    ex = client.post("/api/v1/agents/chain", headers=hd, json={"chain_name": "gerar_proposta", "process_id": p.id}).json()
    escopo = client.get(f"/api/v1/processes/{p.id}/comercial/redacao", headers=hd).json()["especificacao_escopo"]
    client.post(f"/api/v1/processes/{p.id}/comercial/redacao/{escopo['id']}/revisar", headers=hd,
                json={"acao": "aprovar", "justificativa": "ok"})
    ex = client.post(f"/api/v1/evidence/executions/{ex['id']}/resume", headers=hd,
                     json={"expected_revision": ex["revision"]}).json()
    assert [s["status"] for s in ex["steps"]] == ["completed", "completed"]
    url = f"/api/v1/rotas/{rota['id']}/passos/{passos[MAPEAR]['id']}"
    assert client.delete(url, headers=hd, params={"motivo": "fora"}).status_code == 204
    ex = client.post(f"/api/v1/evidence/executions/{ex['id']}/resume", headers=hd,
                     json={"expected_revision": ex["revision"], "recompute_stale": True}).json()
    # O redator reroda (escopo novo, em revisão); o orçamento volta a esperar por ele.
    assert [s["status"] for s in ex["steps"]] == ["completed", "awaiting_review"]
    assert ex["steps"][1]["history"]
