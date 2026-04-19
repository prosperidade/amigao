"""Tests for cross-tenant data isolation."""

from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.process import Process, ProcessStatus
from app.models.tenant import Tenant
from app.models.user import User


def _make_tenant_with_user(db_session, suffix: str) -> tuple[Tenant, User, dict[str, str]]:
    """Create a tenant + user and return (tenant, user, auth_headers)."""
    tenant = Tenant(name=f"Tenant {suffix}")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        email=f"user-{suffix}@example.com",
        full_name=f"User {suffix}",
        hashed_password=get_password_hash("senha123"),
        tenant_id=tenant.id,
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()

    token = create_access_token(
        subject=user.id,
        tenant_id=tenant.id,
        expires_delta=timedelta(minutes=30),
    )
    headers = {"Authorization": f"Bearer {token}"}
    return tenant, user, headers


def test_user_cannot_access_process_from_another_tenant(client: TestClient, db_session):
    """User from tenant B must get 404 when accessing a process owned by tenant A."""
    tenant_a, user_a, _ = _make_tenant_with_user(db_session, "A")
    _, _, headers_b = _make_tenant_with_user(db_session, "B")

    client_a = Client(
        tenant_id=tenant_a.id,
        full_name="Cliente A",
        email="cliente-a@example.com",
        client_type=ClientType.pf,
        status=ClientStatus.active,
    )
    db_session.add(client_a)
    db_session.flush()

    process_a = Process(
        tenant_id=tenant_a.id,
        client_id=client_a.id,
        title="Processo Tenant A",
        process_type="licenciamento",
        status=ProcessStatus.triagem,
    )
    db_session.add(process_a)
    db_session.commit()

    # Tenant B tries to access Tenant A's process → should get 404
    r = client.get(f"/api/v1/processes/{process_a.id}", headers=headers_b)
    assert r.status_code == 404


def test_dashboard_does_not_leak_cross_tenant_data(client: TestClient, db_session):
    """Dashboard summary for tenant B must not include tenant A's processes."""
    tenant_a, _, _ = _make_tenant_with_user(db_session, "DashA")
    _, _, headers_b = _make_tenant_with_user(db_session, "DashB")

    client_a = Client(
        tenant_id=tenant_a.id,
        full_name="Cliente DashA",
        email="cliente-dash-a@example.com",
        client_type=ClientType.pf,
        status=ClientStatus.active,
    )
    db_session.add(client_a)
    db_session.flush()

    process_a = Process(
        tenant_id=tenant_a.id,
        client_id=client_a.id,
        title="Processo Exclusivo Tenant A",
        process_type="licenciamento",
        status=ProcessStatus.triagem,
    )
    db_session.add(process_a)
    db_session.commit()

    # Tenant B's dashboard must have zero processes
    r = client.get("/api/v1/dashboard/summary", headers=headers_b)
    assert r.status_code == 200
    body = r.json()
    assert body["active_processes"] == 0
    assert body["total_clients"] == 0


def test_token_with_mismatched_tenant_id_is_rejected(client: TestClient, db_session):
    """A token forged with a wrong tenant_id must be rejected with 403."""
    tenant_a, user_a, _ = _make_tenant_with_user(db_session, "Forge")

    # Create token with tenant_id=99999 (doesn't match user's actual tenant)
    forged_token = create_access_token(
        subject=user_a.id,
        tenant_id=99999,
        expires_delta=timedelta(minutes=30),
    )
    headers = {"Authorization": f"Bearer {forged_token}"}

    r = client.get("/api/v1/dashboard/summary", headers=headers)
    assert r.status_code == 403
    assert "tenant" in r.json()["detail"].lower()
