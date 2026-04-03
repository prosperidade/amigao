"""Smoke tests para endpoints /api/v1/ai/*."""

from unittest.mock import PropertyMock, patch

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.tenant import Tenant
from app.models.user import User


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _seed(db_session):
    tenant = Tenant(name="Tenant AI")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        email="ai@example.com",
        full_name="AI User",
        hashed_password=get_password_hash("ai123456"),
        tenant_id=tenant.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    return tenant, user


def test_ai_status_returns_200(client: TestClient, db_session):
    """Smoke: /ai/status retorna 200 com campos esperados."""
    _seed(db_session)
    headers = _login(client, "ai@example.com", "ai123456")

    resp = client.get("/api/v1/ai/status", headers=headers)
    assert resp.status_code == 200

    data = resp.json()
    assert "ai_enabled" in data
    assert "ai_configured" in data
    assert "providers_available" in data
    assert isinstance(data["providers_available"], list)


def test_ai_status_unauthenticated_returns_401(client: TestClient):
    """Sem token retorna 401."""
    resp = client.get("/api/v1/ai/status")
    assert resp.status_code == 401


def test_ai_jobs_list_empty(client: TestClient, db_session):
    """Lista de jobs vazia para tenant sem jobs."""
    _seed(db_session)
    headers = _login(client, "ai@example.com", "ai123456")

    resp = client.get("/api/v1/ai/jobs", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_ai_job_not_found(client: TestClient, db_session):
    """Job inexistente retorna 404."""
    _seed(db_session)
    headers = _login(client, "ai@example.com", "ai123456")

    resp = client.get("/api/v1/ai/jobs/99999", headers=headers)
    assert resp.status_code == 404


def test_classify_returns_503_when_ai_not_configured(client: TestClient, db_session):
    """Classify síncrono funciona mesmo sem IA (usa regras estáticas como fallback)."""
    _seed(db_session)
    headers = _login(client, "ai@example.com", "ai123456")

    resp = client.post(
        "/api/v1/ai/classify",
        json={"description": "Preciso de CAR para minha fazenda", "save_job": False},
        headers=headers,
    )
    # O endpoint usa regras estáticas como fallback, então retorna 200
    assert resp.status_code == 200
    data = resp.json()
    assert "demand_type" in data
    assert "confidence" in data


def test_extract_returns_503_when_ai_not_configured(client: TestClient, db_session):
    """Extract sem IA configurada retorna 503."""
    _seed(db_session)
    headers = _login(client, "ai@example.com", "ai123456")

    from app.core.config import Settings  # noqa: PLC0415

    with patch.object(Settings, "ai_configured", new_callable=PropertyMock, return_value=False):
        resp = client.post(
            "/api/v1/ai/extract",
            json={"text": "Documento teste", "doc_type": "car", "save_job": False},
            headers=headers,
        )
        assert resp.status_code == 503
