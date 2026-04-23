"""Smoke tests Sprint R — endpoint /api/v1/agents/budget."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.ai_job import AIJob, AIJobStatus, AIJobType
from app.models.tenant import Tenant
from app.models.user import User


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _seed(db_session, budget_usd: float | None = None):
    tenant = Tenant(name="Budget Tenant", ai_monthly_budget_usd=budget_usd)
    db_session.add(tenant)
    db_session.flush()

    user = User(
        email="budget@example.com",
        full_name="Budget User",
        hashed_password=get_password_hash("budget123456"),
        tenant_id=tenant.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    return tenant, user


def test_budget_unlimited_by_default(client: TestClient, db_session):
    """Sem teto explícito e sem default global → retorna unlimited=True."""
    _seed(db_session)
    headers = _login(client, "budget@example.com", "budget123456")

    resp = client.get("/api/v1/agents/budget", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["unlimited"] is True
    assert data["used_usd"] == 0.0
    assert data["limit_usd"] == 0.0
    assert data["alert"] is False


def test_budget_with_limit_counts_current_month_only(client: TestClient, db_session):
    """Limite de 1.00 USD com 2 jobs totalizando 0.30 → used=0.30, pct=30, alert=False."""
    tenant, _user = _seed(db_session, budget_usd=1.0)
    headers = _login(client, "budget@example.com", "budget123456")

    now = datetime.now(UTC)
    for cost in (0.10, 0.20):
        db_session.add(
            AIJob(
                tenant_id=tenant.id,
                job_type=AIJobType.classify_demand,
                status=AIJobStatus.completed,
                cost_usd=cost,
                created_at=now,
            )
        )
    db_session.flush()

    resp = client.get("/api/v1/agents/budget", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["unlimited"] is False
    assert round(data["used_usd"], 2) == 0.30
    assert data["limit_usd"] == 1.0
    assert 29.0 <= data["pct"] <= 31.0
    assert data["alert"] is False


def test_budget_alert_triggers_at_80_percent(client: TestClient, db_session):
    """85% do teto → alert=True."""
    tenant, _user = _seed(db_session, budget_usd=1.0)
    headers = _login(client, "budget@example.com", "budget123456")

    db_session.add(
        AIJob(
            tenant_id=tenant.id,
            job_type=AIJobType.classify_demand,
            status=AIJobStatus.completed,
            cost_usd=0.85,
            created_at=datetime.now(UTC),
        )
    )
    db_session.flush()

    resp = client.get("/api/v1/agents/budget", headers=headers)
    data = resp.json()
    assert data["alert"] is True
    assert 84.0 <= data["pct"] <= 86.0


def test_budget_unauthenticated_returns_401(client: TestClient):
    """Sem token retorna 401."""
    resp = client.get("/api/v1/agents/budget")
    assert resp.status_code == 401
