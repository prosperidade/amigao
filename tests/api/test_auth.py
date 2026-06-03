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


# ── White label: provider de LLM por consultor (André 2026-05-28) ──────────

def _setup_and_login(client: TestClient, db_session, email: str) -> tuple[dict, int]:
    tenant = Tenant(name=f"T {email}")
    db_session.add(tenant)
    db_session.flush()
    user = User(
        email=email,
        full_name="Consultor LLM",
        hashed_password=get_password_hash("Consultor1"),
        tenant_id=tenant.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    r = client.post("/api/v1/auth/login", data={"username": email, "password": "Consultor1"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, user.id


def test_patch_ai_api_key_stored_encrypted_not_plaintext(client: TestClient, db_session):
    """PATCH /auth/me/preferences com ai.api_key: nunca em texto plano no banco."""
    import json

    from sqlalchemy import text

    headers, user_id = _setup_and_login(client, db_session, "llm.enc@example.com")
    r = client.patch(
        "/api/v1/auth/me/preferences",
        json={"ai": {"provider": "openai", "model": "gpt-4o", "api_key": "sk-PLAINTEXT-SECRET-1234"}},
        headers=headers,
    )
    assert r.status_code == 200

    # SQL direto: o JSONB não pode conter o plaintext; precisa do ciphertext.
    db_session.expire_all()
    raw = db_session.execute(
        text("SELECT preferences FROM users WHERE id = :id"), {"id": user_id}
    ).scalar()
    blob = json.dumps(raw)
    assert "sk-PLAINTEXT-SECRET-1234" not in blob
    assert "api_key_encrypted" in blob
    assert raw["ai"].get("api_key") in (None, "")  # nunca plaintext persistido


def test_get_me_returns_masked_api_key_never_plaintext(client: TestClient, db_session):
    headers, _ = _setup_and_login(client, db_session, "llm.mask@example.com")
    client.patch(
        "/api/v1/auth/me/preferences",
        json={"ai": {"provider": "anthropic", "model": "claude-sonnet-4-20250514", "api_key": "sk-ant-WXYZ"}},
        headers=headers,
    )
    r = client.get("/api/v1/auth/me/full", headers=headers)
    assert r.status_code == 200
    ai = r.json()["preferences"]["ai"]
    assert ai["api_key"] is None
    assert ai["api_key_set"] is True
    assert ai["api_key_masked"].endswith("WXYZ")
    assert ai["provider"] == "anthropic"


def test_patch_ai_without_key_preserves_existing(client: TestClient, db_session):
    headers, _ = _setup_and_login(client, db_session, "llm.keep@example.com")
    client.patch(
        "/api/v1/auth/me/preferences",
        json={"ai": {"provider": "openai", "model": "gpt-4o", "api_key": "sk-keepme"}},
        headers=headers,
    )
    # patch só do summary_length — não pode apagar a chave
    client.patch(
        "/api/v1/auth/me/preferences",
        json={"ai": {"summary_length": "short"}},
        headers=headers,
    )
    r = client.get("/api/v1/auth/me/full", headers=headers)
    ai = r.json()["preferences"]["ai"]
    assert ai["api_key_set"] is True
    assert ai["summary_length"] == "short"


def test_available_models_returns_four_providers(client: TestClient, db_session):
    headers, _ = _setup_and_login(client, db_session, "llm.models@example.com")
    r = client.get("/api/v1/auth/me/preferences/ai/available-models", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) == {"anthropic", "google", "openai", "deepseek"}
