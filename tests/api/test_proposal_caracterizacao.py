"""Caracterização (S5-A, item 1) — comportamento de proposta que o S5-A PRESERVA.

Cobertura de proposal era ZERO. A caracterização ORIGINAL (commit a7ea04e)
congelou também o comportamento que o S5-A mudou de propósito — escopo da
PRICE_TABLE, lifecycle permissivo, sem 'expirada' derivada. Esses testes foram
reescritos para o novo comportamento em ``test_proposal_rota_s5a.py`` (fluxo
caracterizar→mudar; o snapshot antigo permanece no histórico git).

Este arquivo mantém o que NÃO mudou: criação nasce em rascunho com validade, e
edição só em rascunho.
"""

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User


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


def test_criar_proposta_nasce_draft_com_validade(client: TestClient, db_session):
    """PRESERVADO: criar proposta nasce em rascunho com validade gravada."""
    _tenant, cli, _prop, proc = _setup(db_session)
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
    assert body["expires_at"] is not None


def test_update_so_em_draft(client: TestClient, db_session):
    """PRESERVADO: proposta enviada não pode ser editada (422)."""
    _tenant, cli, _prop, proc = _setup(db_session)
    db_session.commit()
    h = _login(client, "prop.carac@example.com")
    pid = client.post("/api/v1/proposals/", headers=h, json={
        "client_id": cli.id, "process_id": proc.id, "title": "P",
        "scope_items": [], "validity_days": 30,
    }).json()["id"]
    client.post(f"/api/v1/proposals/{pid}/send", headers=h)
    r = client.patch(f"/api/v1/proposals/{pid}", headers=h, json={"title": "novo"})
    assert r.status_code == 422
