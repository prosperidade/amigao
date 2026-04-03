"""Smoke tests para o endpoint /api/v1/dashboard/summary."""

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.process import Process, ProcessStatus
from app.models.tenant import Tenant
from app.models.user import User


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _seed(db_session):
    tenant = Tenant(name="Tenant Dashboard")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        email="dash@example.com",
        full_name="Dash User",
        hashed_password=get_password_hash("dash1234"),
        tenant_id=tenant.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    cl = Client(
        tenant_id=tenant.id,
        full_name="Cliente Dash",
        email="cliente.dash@example.com",
        client_type=ClientType.pf,
        status=ClientStatus.active,
    )
    db_session.add(cl)
    db_session.flush()

    proc = Process(
        tenant_id=tenant.id,
        client_id=cl.id,
        title="Processo Dash",
        process_type="licenciamento",
        status=ProcessStatus.triagem,
    )
    db_session.add(proc)
    db_session.flush()

    return tenant, user, cl, proc


def test_dashboard_summary_returns_200(client: TestClient, db_session):
    """Smoke: endpoint retorna 200 com estrutura esperada."""
    tenant, user, cl, proc = _seed(db_session)
    headers = _login(client, "dash@example.com", "dash1234")

    resp = client.get("/api/v1/dashboard/summary", headers=headers)
    assert resp.status_code == 200

    data = resp.json()
    assert "active_processes" in data
    assert "overdue_tasks" in data
    assert "total_clients" in data
    assert "total_properties" in data
    assert "recent_activities" in data
    assert "my_pending_tasks" in data
    assert isinstance(data["recent_activities"], list)
    assert isinstance(data["my_pending_tasks"], list)


def test_dashboard_counts_tenant_scoped(client: TestClient, db_session):
    """Contagens refletem dados do tenant correto."""
    tenant, user, cl, proc = _seed(db_session)
    headers = _login(client, "dash@example.com", "dash1234")

    resp = client.get("/api/v1/dashboard/summary", headers=headers)
    data = resp.json()

    assert data["active_processes"] >= 1
    assert data["total_clients"] >= 1


def test_dashboard_unauthenticated_returns_401(client: TestClient):
    """Sem token retorna 401."""
    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 401
