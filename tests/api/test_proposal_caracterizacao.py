"""Caracterização (S5-A, item 1) — congela o comportamento ATUAL de proposta
ANTES de mudar qualquer linha. Cobertura de proposal era ZERO.

Documenta o que o sistema FAZ hoje (certo ou errado):
- a proposta nasce da PRICE_TABLE (scope_base por demand_type), não da Rota;
- o lifecycle é permissivo (aceita a partir de rascunho, recusa não versiona;
  não há estado 'expirada' derivado).

Os gates E5/E6/E7 já têm caracterização própria em
``tests/services/test_macroetapa_engine_rota_proposta_contrato.py`` — este
arquivo cobre a GERAÇÃO e o LIFECYCLE via API, que estavam descobertos.

NOTA: o S5-A muda deliberadamente parte deste comportamento (escopo passa a
nascer da Rota; máquina de estados fica estrita). Os testes que mudam são
atualizados nos commits de implementação, com o racional — é o fluxo
caracterizar→mudar.
"""

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.process import DemandType, Process, ProcessStatus
from app.models.proposal import Proposal, ProposalStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User
from app.services.proposal_generator import generate_proposal_draft


def _login(client: TestClient, email: str, password: str = "x12345") -> dict[str, str]:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup(db_session, email="prop.carac@example.com"):
    tenant = Tenant(name="Caract Proposta")
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


# ---------------------------------------------------------------------------
# Gerador legado — escopo nasce da PRICE_TABLE (scope_base por demand_type)
# ---------------------------------------------------------------------------

def test_gerador_legado_escopo_vem_da_price_table(db_session):
    tenant, _cli, _prop, proc = _setup(db_session)
    db_session.commit()

    draft = generate_proposal_draft(db_session, proc.id, tenant.id)

    # HOJE: escopo = scope_base fixo do tipo 'car' (6 itens), NÃO da Rota.
    assert draft.demand_type == "car"
    assert draft.complexity == "baixa"           # sem checklist/tasks/urgência
    assert len(draft.scope_items) == 6
    assert draft.scope_items[0]["description"].startswith("Levantamento")
    # nenhum item aponta para passo de rota (rastreabilidade inexistente hoje)
    assert all("rota_passo_id" not in it for it in draft.scope_items)
    # faixa car/baixa 800–1500 → sugerido = ponto médio arredondado à centena
    assert draft.suggested_value == 1200
    assert draft.estimated_days == 15


def test_generate_draft_endpoint_atual(client: TestClient, db_session):
    tenant, _cli, _prop, proc = _setup(db_session)
    db_session.commit()
    h = _login(client, "prop.carac@example.com")

    r = client.get(f"/api/v1/proposals/generate-draft?process_id={proc.id}", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    # HOJE o endpoint gera SEM exigir Rota validada (nasce da tabela).
    assert body["demand_type"] == "car"
    assert len(body["scope_items"]) == 6


# ---------------------------------------------------------------------------
# Lifecycle atual via API — permissivo (freeze das quirks)
# ---------------------------------------------------------------------------

def test_criar_proposta_nasce_draft_com_validade(client: TestClient, db_session):
    tenant, cli, _prop, proc = _setup(db_session)
    db_session.commit()
    h = _login(client, "prop.carac@example.com")

    r = client.post("/api/v1/proposals/", headers=h, json={
        "client_id": cli.id, "process_id": proc.id, "title": "Proposta X",
        "scope_items": [{"description": "Serviço", "unit": "serv.", "qty": 1,
                         "unit_price": 1000, "total": 1000}],
        "total_value": 1000, "validity_days": 30,
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "draft"
    assert body["expires_at"] is not None       # validade gravada na criação


def test_lifecycle_atual_permissivo(client: TestClient, db_session):
    tenant, cli, _prop, proc = _setup(db_session)
    db_session.commit()
    h = _login(client, "prop.carac@example.com")

    def _mk():
        return client.post("/api/v1/proposals/", headers=h, json={
            "client_id": cli.id, "process_id": proc.id, "title": "P",
            "scope_items": [], "total_value": 1000, "validity_days": 30,
        }).json()["id"]

    # send: draft → sent
    pid = _mk()
    assert client.post(f"/api/v1/proposals/{pid}/send", headers=h).json()["status"] == "sent"

    # accept: HOJE aceita DIRETO de draft (permissivo — S5-A vai restringir a 'sent')
    pid2 = _mk()
    assert client.post(f"/api/v1/proposals/{pid2}/accept", headers=h).json()["status"] == "accepted"

    # reject: sent → rejected, e NÃO cria nova versão (versionamento inexistente hoje)
    pid3 = _mk()
    client.post(f"/api/v1/proposals/{pid3}/send", headers=h)
    rej = client.post(f"/api/v1/proposals/{pid3}/reject", headers=h, json={"reason": "caro"})
    assert rej.json()["status"] == "rejected"
    total = client.get(f"/api/v1/proposals/?process_id={proc.id}", headers=h).json()
    # 3 propostas criadas, nenhuma renegociação gerada automaticamente
    assert len([p for p in total if p["id"] in {pid, pid2, pid3}]) == 3


def test_update_so_em_draft(client: TestClient, db_session):
    tenant, cli, _prop, proc = _setup(db_session)
    db_session.commit()
    h = _login(client, "prop.carac@example.com")
    pid = client.post("/api/v1/proposals/", headers=h, json={
        "client_id": cli.id, "process_id": proc.id, "title": "P",
        "scope_items": [], "validity_days": 30,
    }).json()["id"]
    client.post(f"/api/v1/proposals/{pid}/send", headers=h)
    # enviada não edita
    r = client.patch(f"/api/v1/proposals/{pid}", headers=h, json={"title": "novo"})
    assert r.status_code == 422


def test_sem_estado_expirada_hoje(db_session):
    """HOJE não há estado derivado 'expirada': o enum tem o valor, mas nenhum
    fluxo o atribui (expires_at fica no passado sem efeito)."""
    from datetime import UTC, datetime, timedelta

    tenant, cli, _prop, proc = _setup(db_session)
    p = Proposal(
        tenant_id=tenant.id, process_id=proc.id, client_id=cli.id,
        status=ProposalStatus.sent, title="P", scope_items=[],
        expires_at=datetime.now(UTC) - timedelta(days=1),   # já venceu
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    # continua 'sent' — nada deriva 'expired' hoje
    assert p.status == ProposalStatus.sent
