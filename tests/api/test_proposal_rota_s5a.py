"""S5-A — a proposta nasce da Rota validada + máquina de estados.

Cobre: escopo rastreável (item→passo), bloqueio sem Rota validada, precificação
via PRICE_TABLE, transições (válidas e inválidas), renegociação com histórico,
expiração derivada, e gate E6 (has_proposal_accepted) intacto.
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
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

def test_escopo_nasce_dos_passos_faturaveis_rastreavel(client: TestClient, db_session):
    tenant, _cli, _prop, proc = _setup(db_session, "rota.ok@ex.com")
    rota = _rota_validada(db_session, tenant, proc, billable=2, direcao=1)
    passo_ids = [p.id for p in rota.passos if p.classificacao == RotaPassoClassificacao.item_proposta]
    db_session.commit()
    h = _login(client, "rota.ok@ex.com")

    r = client.get(f"/api/v1/proposals/generate-draft?process_id={proc.id}", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    # só os 2 faturáveis viram itens (a 'direção' não entra no escopo cobrável)
    assert len(body["scope_items"]) == 2
    # cada item aponta o passo de origem (rastreável)
    assert {it["rota_passo_id"] for it in body["scope_items"]} == set(passo_ids)
    # PRICE_TABLE precifica: car/baixa 800–1500 → sugerido 1200 distribuído
    assert body["suggested_value"] == 1200
    assert sum(it["total"] for it in body["scope_items"]) == 1200
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
    assert "faturáveis" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Máquina de estados
# ---------------------------------------------------------------------------

def _criar(client, h, cli_id, proc_id):
    return client.post("/api/v1/proposals/", headers=h, json={
        "client_id": cli_id, "process_id": proc_id, "title": "P",
        "scope_items": [], "total_value": 1000, "validity_days": 30,
    }).json()["id"]


def test_transicoes_validas_draft_send_accept(client: TestClient, db_session):
    tenant, cli, _prop, proc = _setup(db_session, "tr.ok@ex.com")
    db_session.commit()
    h = _login(client, "tr.ok@ex.com")
    pid = _criar(client, h, cli.id, proc.id)
    assert client.post(f"/api/v1/proposals/{pid}/send", headers=h).json()["status"] == "sent"
    acc = client.post(f"/api/v1/proposals/{pid}/accept", headers=h)
    assert acc.status_code == 200
    assert acc.json()["status"] == "accepted"


def test_aceitar_rascunho_bloqueado(client: TestClient, db_session):
    """S5-A tornou a máquina ESTRITA: aceitar exige 'enviada' (antes aceitava draft)."""
    tenant, cli, _prop, proc = _setup(db_session, "tr.draft@ex.com")
    db_session.commit()
    h = _login(client, "tr.draft@ex.com")
    pid = _criar(client, h, cli.id, proc.id)
    r = client.post(f"/api/v1/proposals/{pid}/accept", headers=h)
    assert r.status_code == 422
    assert "enviada" in r.json()["detail"]


def test_recusa_e_nova_versao_preserva_historico(client: TestClient, db_session):
    tenant, cli, _prop, proc = _setup(db_session, "reneg@ex.com")
    db_session.commit()
    h = _login(client, "reneg@ex.com")
    pid = _criar(client, h, cli.id, proc.id)
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
    pid = _criar(client, h, cli.id, proc.id)
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
    # mas pode virar nova versão
    nv = client.post(f"/api/v1/proposals/{p.id}/nova-versao", headers=h)
    assert nv.status_code == 201
    assert nv.json()["version_number"] == 2


def test_gate_e6_intacto_apos_aceite(client: TestClient, db_session):
    """O gate E6 (has_proposal_accepted) segue lendo o estado 'accepted' — S5-A
    mudou COMO o escopo nasce, não o contrato do gate."""
    tenant, cli, _prop, proc = _setup(db_session, "gate@ex.com")
    db_session.commit()
    h = _login(client, "gate@ex.com")
    assert has_proposal_accepted(db_session, tenant.id, proc.id) is False
    pid = _criar(client, h, cli.id, proc.id)
    client.post(f"/api/v1/proposals/{pid}/send", headers=h)
    client.post(f"/api/v1/proposals/{pid}/accept", headers=h)
    db_session.expire_all()
    assert has_proposal_accepted(db_session, tenant.id, proc.id) is True
