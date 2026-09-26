"""S5-A — a proposta nasce da Rota validada + máquina de estados.

Cobre: escopo rastreável (item→passo), bloqueio sem Rota validada, transições (válidas e
inválidas), renegociação com histórico, expiração derivada, e gate E6 (has_proposal_accepted)
intacto. Desde a #284 (ADR-081) o preço vem do orçamento aprovado do tenant — a PRICE_TABLE saiu.
"""

import time
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from tests.comercial.apoio import orcamento_aprovado

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.comercial import Orcamento
from app.models.document import Document, OcrStatus
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.proposal import Proposal, ProposalStatus
from app.models.rota import (
    Rota,
    RotaPasso,
    RotaPassoClassificacao,
    RotaPassoStatus,
    RotaStatus,
)
from app.models.tenant import Tenant
from app.models.user import User
from app.services.macroetapa_engine import has_proposal_accepted


def _login(client: TestClient, email: str, password: str = "x12345") -> dict[str, str]:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup(db_session, email):
    tenant = Tenant(name=f"T {email}")
    db_session.add(tenant)
    db_session.flush()
    user = User(email=email, full_name="Consultor", hashed_password=get_password_hash("x12345"),
                tenant_id=tenant.id, is_active=True, is_superuser=True)
    cli = Client(tenant_id=tenant.id, full_name="Cliente", email=f"c.{email}",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add_all([user, cli])
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda")
    db_session.add(prop)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Caso CAR", process_type="car", status=ProcessStatus.triagem,
                   demand_type=DemandType.car)
    db_session.add(proc)
    db_session.flush()
    return tenant, cli, prop, proc


def _rota_validada(db_session, tenant, proc, *, billable=2, direcao=1, demand="car"):
    """Rota validada com N passos faturáveis (item_proposta) + M de direção."""
    rota = Rota(tenant_id=tenant.id, process_id=proc.id, demand_type=demand,
                status=RotaStatus.validada)
    db_session.add(rota)
    db_session.flush()
    ordem = 0
    for i in range(billable):
        db_session.add(RotaPasso(
            tenant_id=tenant.id, rota_id=rota.id, ordem=ordem, titulo=f"Serviço faturável {i+1}",
            descricao=f"Detalhe do serviço {i+1}", norma_ref=f"Lei {i+1}", prazo_estimado_dias=10,
            classificacao=RotaPassoClassificacao.item_proposta,
            status=RotaPassoStatus.validado, sources=[], dedupe_key=f"{proc.id}-fat-{i}",
        ))
        ordem += 1
    for j in range(direcao):
        db_session.add(RotaPasso(
            tenant_id=tenant.id, rota_id=rota.id, ordem=ordem, titulo=f"Orientação {j+1}",
            classificacao=RotaPassoClassificacao.direcao,
            status=RotaPassoStatus.validado, sources=[], dedupe_key=f"{proc.id}-dir-{j}",
        ))
        ordem += 1
    db_session.flush()
    return rota


# ---------------------------------------------------------------------------
# Rota → Proposta (escopo rastreável + precificação)
# ---------------------------------------------------------------------------

def _usuario(db_session, tenant) -> User:
    return db_session.query(User).filter(User.tenant_id == tenant.id).first()


def test_rota_assinada_sem_orcamento_pede_o_orcamento(client: TestClient, db_session):
    """ADR-081: sem orçamento não há preço — nada de tabela de código."""
    tenant, _cli, _prop, proc = _setup(db_session, "rota.semorc@ex.com")
    _rota_validada(db_session, tenant, proc, billable=2, direcao=1)
    db_session.commit()
    h = _login(client, "rota.semorc@ex.com")

    r = client.get(f"/api/v1/proposals/generate-draft?process_id={proc.id}", headers=h)
    assert r.status_code == 422
    assert "orçamento" in r.json()["detail"]


def test_escopo_nasce_do_orcamento_rastreavel_ao_passo(client: TestClient, db_session):
    tenant, _cli, _prop, proc = _setup(db_session, "rota.ok@ex.com")
    rota = _rota_validada(db_session, tenant, proc, billable=2, direcao=1)
    passo_ids = [p.id for p in rota.passos if p.classificacao == RotaPassoClassificacao.item_proposta]
    orc = orcamento_aprovado(db_session, process=proc, user_id=_usuario(db_session, tenant).id)
    db_session.commit()
    h = _login(client, "rota.ok@ex.com")

    r = client.get(f"/api/v1/proposals/generate-draft?process_id={proc.id}", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    # só os 2 faturáveis viram itens (a 'direção' não entra no escopo cobrável)
    assert len(body["scope_items"]) == 2
    assert {it["rota_passo_id"] for it in body["scope_items"]} == set(passo_ids)
    # o preço é o do orçamento do tenant: 2 passos × 4 h × R$ 150
    assert body["suggested_value"] == 1200 == float(orc.total)
    assert body["orcamento_id"] == orc.id
    assert body["rota_id"] == rota.id


def test_proposta_sem_rota_validada_bloqueada(client: TestClient, db_session):
    tenant, _cli, _prop, proc = _setup(db_session, "rota.none@ex.com")
    # Rota existe mas só como proposta (não validada) → gate não satisfeito.
    db_session.add(Rota(tenant_id=tenant.id, process_id=proc.id, demand_type="car",
                        status=RotaStatus.proposta))
    db_session.commit()
    h = _login(client, "rota.none@ex.com")

    r = client.get(f"/api/v1/proposals/generate-draft?process_id={proc.id}", headers=h)
    assert r.status_code == 422
    assert "Rota" in r.json()["detail"]


def test_rota_validada_sem_passo_faturavel_bloqueada(client: TestClient, db_session):
    tenant, _cli, _prop, proc = _setup(db_session, "rota.nofat@ex.com")
    _rota_validada(db_session, tenant, proc, billable=0, direcao=2)
    db_session.commit()
    h = _login(client, "rota.nofat@ex.com")

    r = client.get(f"/api/v1/proposals/generate-draft?process_id={proc.id}", headers=h)
    assert r.status_code == 422
    assert "orçamento" in r.json()["detail"]
    # e o escopo não se especifica sem passo cobrado: o Redator recusa, dizendo por quê
    r = client.post(f"/api/v1/processes/{proc.id}/comercial/redacao", headers=h)
    assert r.status_code == 422
    assert "item de proposta" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Máquina de estados
# ---------------------------------------------------------------------------

def _criar(client, h, db_session, cli, proc):
    """Proposta do caso: Rota assinada → orçamento aprovado → proposta (ADR-081)."""
    tenant_id = proc.tenant_id
    if not db_session.query(Rota).filter(Rota.process_id == proc.id, Rota.status == RotaStatus.validada).first():
        _rota_validada(db_session, db_session.get(Tenant, tenant_id), proc)
        orcamento_aprovado(db_session, process=proc,
                           user_id=db_session.query(User).filter(User.tenant_id == tenant_id).first().id)
        db_session.commit()
    r = client.post("/api/v1/proposals/", headers=h, json={
        "client_id": cli.id, "process_id": proc.id, "title": "P", "validity_days": 30,
    })
    assert r.status_code == 201, r.text
    assert r.json()["orcamento_id"] is not None
    return r.json()["id"]


def test_transicoes_validas_draft_send_accept(client: TestClient, db_session):
    tenant, cli, _prop, proc = _setup(db_session, "tr.ok@ex.com")
    db_session.commit()
    h = _login(client, "tr.ok@ex.com")
    pid = _criar(client, h, db_session, cli, proc)
    assert client.post(f"/api/v1/proposals/{pid}/send", headers=h).json()["status"] == "sent"
    acc = client.post(f"/api/v1/proposals/{pid}/accept", headers=h)
    assert acc.status_code == 200
    assert acc.json()["status"] == "accepted"


def test_aceite_recusa_proposta_desatualizada_com_razao(client: TestClient, db_session):
    tenant, cli, _prop, proc = _setup(db_session, "tr.stale@ex.com")
    db_session.commit()
    h = _login(client, "tr.stale@ex.com")
    pid = _criar(client, h, db_session, cli, proc)
    assert client.post(f"/api/v1/proposals/{pid}/send", headers=h).status_code == 200

    proposta = db_session.query(Proposal).filter(Proposal.id == pid).one()
    # O documento entra depois da proposta (relógio do Postgres) E do orçamento (relógio do
    # Python): os dois relógios podem divergir por milissegundos, então o marco é o maior deles.
    orcamento = db_session.get(Orcamento, proposta.orcamento_id)
    entrada = max(proposta.created_at, orcamento.created_at) + timedelta(milliseconds=1)
    doc = Document(
        tenant_id=tenant.id, process_id=proc.id, client_id=cli.id,
        original_file_name="matricula-nova.pdf", filename="matricula-nova.pdf",
        content_type="application/pdf", storage_key=f"stale/{tenant.id}/{proc.id}",
        ocr_status=OcrStatus.done,
        created_at=entrada,
    )
    db_session.add(doc)
    db_session.commit()

    resposta = client.post(f"/api/v1/proposals/{pid}/accept", headers=h)
    assert resposta.status_code == 422
    detalhe = resposta.json()["detail"]
    assert "desatualizada" in detalhe.lower()
    assert "matricula-nova.pdf" in detalhe
    # O bloqueio nomeia o movimento REAL (ADR-039: bloqueio de fluxo diz o
    # próximo passo). "Gere uma nova versão" sozinho apontaria porta trancada:
    # `nova-versao` exige recusada/expirada — de `sent` não sai.
    assert "recuse" in detalhe.lower()
    db_session.refresh(proposta)
    assert proposta.status == ProposalStatus.sent

    # E o caminho que a mensagem indica funciona de fato: recusar → nova versão.
    # Desde a #284 a nova versão nasce do orçamento aprovado e ATUAL: o documento novo
    # desatualizou o orçamento, então ela é recusada até o consultor refazer escopo e orçamento.
    rec = client.post(f"/api/v1/proposals/{pid}/reject", headers=h, json={"reason": "escopo desatualizado"})
    assert rec.status_code == 200, rec.text
    nova = client.post(f"/api/v1/proposals/{pid}/nova-versao", headers=h)
    assert nova.status_code == 422
    assert "desatualizado" in nova.json()["detail"]
    # Regerar depois do documento: espera o relógio local passar do marco de entrada.
    while datetime.now(UTC) <= entrada:
        time.sleep(0.01)
    novo_orc = orcamento_aprovado(db_session, process=proc, user_id=_usuario(db_session, tenant).id)
    db_session.commit()
    nova = client.post(f"/api/v1/proposals/{pid}/nova-versao", headers=h)
    assert nova.status_code == 201, nova.text
    assert nova.json()["status"] == "draft"
    assert nova.json()["orcamento_id"] == novo_orc.id


def test_aceitar_rascunho_bloqueado(client: TestClient, db_session):
    """S5-A tornou a máquina ESTRITA: aceitar exige 'enviada' (antes aceitava draft)."""
    tenant, cli, _prop, proc = _setup(db_session, "tr.draft@ex.com")
    db_session.commit()
    h = _login(client, "tr.draft@ex.com")
    pid = _criar(client, h, db_session, cli, proc)
    r = client.post(f"/api/v1/proposals/{pid}/accept", headers=h)
    assert r.status_code == 422
    assert "enviada" in r.json()["detail"]


def test_recusa_e_nova_versao_preserva_historico(client: TestClient, db_session):
    tenant, cli, _prop, proc = _setup(db_session, "reneg@ex.com")
    db_session.commit()
    h = _login(client, "reneg@ex.com")
    pid = _criar(client, h, db_session, cli, proc)
    client.post(f"/api/v1/proposals/{pid}/send", headers=h)
    client.post(f"/api/v1/proposals/{pid}/reject", headers=h, json={"reason": "caro"})

    nv = client.post(f"/api/v1/proposals/{pid}/nova-versao", headers=h)
    assert nv.status_code == 201, nv.text
    nova = nv.json()
    assert nova["version_number"] == 2
    assert nova["previous_version_id"] == pid
    assert nova["status"] == "draft"
    # a recusada segue existindo (histórico preservado)
    old = client.get(f"/api/v1/proposals/{pid}", headers=h).json()
    assert old["status"] == "rejected"


def test_nova_versao_so_de_recusada_ou_expirada(client: TestClient, db_session):
    tenant, cli, _prop, proc = _setup(db_session, "reneg.bad@ex.com")
    db_session.commit()
    h = _login(client, "reneg.bad@ex.com")
    pid = _criar(client, h, db_session, cli, proc)
    # rascunho não gera nova versão
    r = client.post(f"/api/v1/proposals/{pid}/nova-versao", headers=h)
    assert r.status_code == 422


def test_expirada_derivada_no_read_e_nao_aceita(client: TestClient, db_session):
    tenant, cli, _prop, proc = _setup(db_session, "exp@ex.com")
    # enviada com validade já vencida
    p = Proposal(tenant_id=tenant.id, process_id=proc.id, client_id=cli.id,
                 status=ProposalStatus.sent, title="P", scope_items=[], validity_days=30,
                 sent_at=datetime.now(UTC) - timedelta(days=40),
                 expires_at=datetime.now(UTC) - timedelta(days=10))
    db_session.add(p)
    db_session.commit()
    h = _login(client, "exp@ex.com")

    got = client.get(f"/api/v1/proposals/{p.id}", headers=h).json()
    # status persistido segue 'sent', mas o efetivo é 'expired' (derivado no read)
    assert got["status"] == "sent"
    assert got["effective_status"] == "expired"
    # aceitar uma expirada é bloqueado
    r = client.post(f"/api/v1/proposals/{p.id}/accept", headers=h)
    assert r.status_code == 422
    assert "expirada" in r.json()["detail"].lower()
    # Proposta antiga sem orçamento (como as precificadas pela tabela de código): a nova versão
    # só nasce depois da Rota assinada e do orçamento aprovado (ADR-081).
    nv = client.post(f"/api/v1/proposals/{p.id}/nova-versao", headers=h)
    assert nv.status_code == 422
    assert "Rota" in nv.json()["detail"]
    _rota_validada(db_session, tenant, proc)
    orc = orcamento_aprovado(db_session, process=proc, user_id=_usuario(db_session, tenant).id)
    db_session.commit()
    nv = client.post(f"/api/v1/proposals/{p.id}/nova-versao", headers=h)
    assert nv.status_code == 201, nv.text
    assert nv.json()["version_number"] == 2
    assert nv.json()["orcamento_id"] == orc.id


def test_gate_e6_intacto_apos_aceite(client: TestClient, db_session):
    """O gate E6 (has_proposal_accepted) segue lendo o estado 'accepted' — S5-A
    mudou COMO o escopo nasce, não o contrato do gate."""
    tenant, cli, _prop, proc = _setup(db_session, "gate@ex.com")
    db_session.commit()
    h = _login(client, "gate@ex.com")
    assert has_proposal_accepted(db_session, tenant.id, proc.id) is False
    pid = _criar(client, h, db_session, cli, proc)
    client.post(f"/api/v1/proposals/{pid}/send", headers=h)
    client.post(f"/api/v1/proposals/{pid}/accept", headers=h)
    db_session.expire_all()
    assert has_proposal_accepted(db_session, tenant.id, proc.id) is True


def test_rascunho_antigo_sem_orcamento_nao_e_enviado(client: TestClient, db_session):
    """ADR-081: rascunho de caso precificado pela tabela antiga não vai ao cliente; a aceita segue."""
    tenant, cli, _prop, proc = _setup(db_session, "legado@ex.com")
    antigo = Proposal(tenant_id=tenant.id, process_id=proc.id, client_id=cli.id, status=ProposalStatus.draft,
                      title="Antiga", scope_items=[{"description": "Serviço", "total": 1200}], total_value=1200,
                      validity_days=30)
    aceita = Proposal(tenant_id=tenant.id, process_id=proc.id, client_id=cli.id, status=ProposalStatus.accepted,
                      title="Aceita", scope_items=[], total_value=1500, validity_days=30)
    db_session.add_all([antigo, aceita])
    db_session.commit()
    h = _login(client, "legado@ex.com")

    r = client.post(f"/api/v1/proposals/{antigo.id}/send", headers=h)
    assert r.status_code == 422
    assert "orçamento" in r.json()["detail"]
    got = client.get(f"/api/v1/proposals/{aceita.id}", headers=h).json()
    assert got["status"] == "accepted" and got["total_value"] == 1500
