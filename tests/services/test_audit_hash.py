"""Dívida #18 — verificação da hash chain de AuditLog.

Cobre o verificador puro ``_verify_chain`` (sem DB) e o wrapper
``verify_audit_chain`` (com DB via Testcontainers).
"""

from __future__ import annotations

from sqlalchemy import text

from app.models.audit_log import AuditLog
from app.services.audit_hash import (
    _verify_chain,
    compute_audit_hash,
    verify_audit_chain,
)


def _stamped(audit_id: int, tenant_id: int, action: str, prev: str | None, *, new_value=None) -> AuditLog:
    """Cria um AuditLog em memória já carimbado corretamente."""
    a = AuditLog(
        tenant_id=tenant_id,
        user_id=1,
        entity_type="process",
        entity_id=1,
        action=action,
        new_value=new_value,
    )
    a.id = audit_id
    a.hash_previous = prev
    a.hash_sha256 = compute_audit_hash(a, prev)
    return a


def _valid_chain() -> list[AuditLog]:
    a1 = _stamped(1, 1, "created", None)
    a2 = _stamped(2, 1, "updated", a1.hash_sha256)
    a3 = _stamped(3, 1, "deleted", a2.hash_sha256)
    return [a1, a2, a3]


# ---------------------------------------------------------------------------
# _verify_chain (puro, sem DB)
# ---------------------------------------------------------------------------

def test_empty_chain_is_ok() -> None:
    assert _verify_chain([]) == []


def test_single_valid_element_is_ok() -> None:
    assert _verify_chain([_stamped(1, 1, "created", None)]) == []


def test_valid_chain_returns_no_broken_links() -> None:
    assert _verify_chain(_valid_chain()) == []


def test_content_tampering_is_detected() -> None:
    chain = _valid_chain()
    # adultera um campo auditado DEPOIS de carimbado, sem re-stampar
    chain[1].new_value = "VALOR-ADULTERADO"

    broken = _verify_chain(chain)

    assert len(broken) == 1
    assert broken[0].reason == "content_tampered"
    assert broken[0].position == 1
    assert broken[0].audit_id == 2


def test_removed_row_breaks_the_link() -> None:
    a1, a2, a3 = _valid_chain()
    # a2 foi removido — a3.hash_previous aponta para a2, não para a1
    broken = _verify_chain([a1, a3])

    assert len(broken) == 1
    assert broken[0].reason == "broken_previous_link"
    assert broken[0].position == 1
    assert broken[0].audit_id == 3
    assert broken[0].expected == a1.hash_sha256
    assert broken[0].found == a2.hash_sha256


# ---------------------------------------------------------------------------
# verify_audit_chain (com DB real)
# ---------------------------------------------------------------------------

def test_verify_audit_chain_clean_then_tampered(db_session) -> None:
    from app.models.tenant import Tenant
    from app.services.notifications import register_notification_audit

    tenant = Tenant(name="T Audit Chain")
    db_session.add(tenant)
    db_session.flush()

    for action in ("created", "updated", "deleted"):
        register_notification_audit(
            db=db_session,
            tenant_id=tenant.id,
            entity_type="process",
            entity_id=1,
            action=action,
            details={"step": action},
        )
    db_session.flush()

    # cadeia íntegra
    assert verify_audit_chain(db_session, tenant.id) == []

    # adultera uma linha por SQL direto (simula tampering fora da app)
    db_session.execute(
        text("UPDATE audit_logs SET action = 'HACKED' WHERE tenant_id = :t AND action = 'updated'"),
        {"t": tenant.id},
    )
    db_session.flush()
    db_session.expire_all()

    broken = verify_audit_chain(db_session, tenant.id)
    assert any(b.reason == "content_tampered" for b in broken)


def test_verify_audit_chain_isolates_tenant(db_session) -> None:
    """Tenant sem registros carimbados ⇒ cadeia vazia (íntegra)."""
    from app.models.tenant import Tenant

    tenant = Tenant(name="T Sem Audit")
    db_session.add(tenant)
    db_session.flush()

    assert verify_audit_chain(db_session, tenant.id) == []
