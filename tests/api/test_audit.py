"""Dívida #18 — endpoint admin de verificação da hash chain.

GET /api/v1/admin/audit/verify-chain — read-only, superusuário, tenant do JWT.
"""

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import get_password_hash
from app.models.tenant import Tenant
from app.models.user import User
from app.services.notifications import register_notification_audit

_VERIFY_URL = "/api/v1/admin/audit/verify-chain"


def _login(tc: TestClient, email: str, password: str) -> dict[str, str]:
    r = tc.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup_user(db_session, *, email: str, is_superuser: bool) -> int:
    tenant = Tenant(name=f"T {email}")
    db_session.add(tenant)
    db_session.flush()
    user = User(
        email=email,
        full_name="Admin Audit",
        hashed_password=get_password_hash("Senha1"),
        tenant_id=tenant.id,
        is_active=True,
        is_superuser=is_superuser,
    )
    db_session.add(user)
    db_session.commit()
    return tenant.id


def _seed_audit_rows(db_session, tenant_id: int) -> None:
    for action in ("created", "updated", "deleted"):
        register_notification_audit(
            db=db_session,
            tenant_id=tenant_id,
            entity_type="process",
            entity_id=1,
            action=action,
            details={"step": action},
        )
    db_session.commit()


def test_verify_chain_clean_for_superuser(client: TestClient, db_session):
    tenant_id = _setup_user(db_session, email="super.clean@example.com", is_superuser=True)
    _seed_audit_rows(db_session, tenant_id)
    headers = _login(client, "super.clean@example.com", "Senha1")

    r = client.get(_VERIFY_URL, headers=headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tenant_id"] == tenant_id
    assert body["total_checked"] == 3
    assert body["ok"] is True
    assert body["broken_links"] == []


def test_verify_chain_detects_tampering(client: TestClient, db_session):
    tenant_id = _setup_user(db_session, email="super.tamper@example.com", is_superuser=True)
    _seed_audit_rows(db_session, tenant_id)
    # adultera uma linha por SQL direto
    db_session.execute(
        text("UPDATE audit_logs SET action = 'HACKED' WHERE tenant_id = :t AND action = 'updated'"),
        {"t": tenant_id},
    )
    db_session.commit()
    headers = _login(client, "super.tamper@example.com", "Senha1")

    r = client.get(_VERIFY_URL, headers=headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is False
    assert len(body["broken_links"]) >= 1
    assert any(b["reason"] == "content_tampered" for b in body["broken_links"])


def test_verify_chain_forbidden_for_non_superuser(client: TestClient, db_session):
    _setup_user(db_session, email="naosuper@example.com", is_superuser=False)
    headers = _login(client, "naosuper@example.com", "Senha1")

    r = client.get(_VERIFY_URL, headers=headers)

    assert r.status_code == 403
