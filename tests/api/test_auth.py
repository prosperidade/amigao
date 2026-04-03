from fastapi.testclient import TestClient
from jose import jwt

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.tenant import Tenant
from app.models.user import User


def test_login_access_token(client: TestClient, db_session):
    tenant = Tenant(name="Tenant Teste")
    db_session.add(tenant)
    db_session.flush()
    user = User(
        email="admin@example.com",
        full_name="Admin Teste",
        hashed_password=get_password_hash("segredo123"),
        tenant_id=tenant.id,
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    db_session.commit()

    login_data = {
        "username": "admin@example.com",
        "password": "segredo123"
    }
    r = client.post("/api/v1/auth/login", data=login_data)

    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]

def test_login_invalid_credentials(client: TestClient):
    login_data = {
        "username": "invalid@example.com",
        "password": "wrongpassword"
    }
    r = client.post("/api/v1/auth/login", data=login_data)
    assert r.status_code == 401

def test_login_client_portal_token_includes_explicit_profile(client: TestClient, db_session):
    tenant = Tenant(name="Tenant Portal")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        email="cliente.portal@example.com",
        full_name="Cliente Portal",
        hashed_password=get_password_hash("cliente123"),
        tenant_id=tenant.id,
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()

    portal_client = Client(
        tenant_id=tenant.id,
        full_name="Cliente Portal",
        email="cliente.portal@example.com",
        client_type=ClientType.pf,
        status=ClientStatus.active,
    )
    db_session.add(portal_client)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "cliente.portal@example.com", "password": "cliente123"},
        headers={"X-Auth-Profile": "client_portal"},
    )

    assert response.status_code == 200
    token = response.json()["access_token"]
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["profile"] == "client_portal"
    assert payload["client_id"] == portal_client.id


def test_login_internal_profile_header_overrides_portal_inference(client: TestClient, db_session):
    tenant = Tenant(name="Tenant Hibrido")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        email="cliente.hibrido@example.com",
        full_name="Cliente Hibrido",
        hashed_password=get_password_hash("cliente123"),
        tenant_id=tenant.id,
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()

    portal_client = Client(
        tenant_id=tenant.id,
        full_name="Cliente Hibrido",
        email="cliente.hibrido@example.com",
        client_type=ClientType.pf,
        status=ClientStatus.active,
    )
    db_session.add(portal_client)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "cliente.hibrido@example.com", "password": "cliente123"},
        headers={"X-Auth-Profile": "internal"},
    )

    assert response.status_code == 200
    token = response.json()["access_token"]
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["profile"] == "internal"
    assert payload.get("client_id") is None
