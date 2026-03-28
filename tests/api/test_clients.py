from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.tenant import Tenant
from app.models.user import User


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

def test_create_client_unauthorized(client: TestClient):
    data = {
        "name": "Test Client",
        "email": "client@example.com",
        "document": "12345678901",
        "client_type": "pf"
    }
    # No auth token provided, should get 401
    r = client.post("/api/v1/clients/", json=data)
    assert r.status_code == 401

def test_get_clients_unauthorized(client: TestClient):
    r = client.get("/api/v1/clients/")
    assert r.status_code == 401


def test_client_portal_cannot_list_clients(client: TestClient, db_session):
    tenant = Tenant(name="Tenant Portal")
    db_session.add(tenant)
    db_session.flush()

    portal_user = User(
        email="cliente.portal@example.com",
        full_name="Cliente Portal",
        hashed_password=get_password_hash("cliente123"),
        tenant_id=tenant.id,
        is_active=True,
        is_superuser=False,
    )
    db_session.add(portal_user)
    db_session.flush()

    client_record = Client(
        tenant_id=tenant.id,
        full_name="Cliente Portal",
        email="cliente.portal@example.com",
        client_type=ClientType.pf,
        status=ClientStatus.active,
    )
    db_session.add(client_record)
    db_session.commit()

    headers = _login(client, "cliente.portal@example.com", "cliente123")
    response = client.get("/api/v1/clients/", headers=headers)

    assert response.status_code == 403
