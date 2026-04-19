"""Hash chain service for AuditLog integrity."""

import hashlib
import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def compute_audit_hash(audit: AuditLog, previous_hash: Optional[str] = None) -> str:
    """Calcula SHA-256 do registro de auditoria incluindo hash anterior."""
    payload = json.dumps(
        {
            "tenant_id": audit.tenant_id,
            "user_id": audit.user_id,
            "entity_type": audit.entity_type,
            "entity_id": audit.entity_id,
            "action": audit.action,
            "old_value": audit.old_value,
            "new_value": audit.new_value,
            "details": audit.details,
            "previous_hash": previous_hash or "",
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_last_hash_for_tenant(db: Session, tenant_id: int) -> Optional[str]:
    """Retorna o hash do último registro de auditoria do tenant."""
    last = (
        db.query(AuditLog.hash_sha256)
        .filter(
            AuditLog.tenant_id == tenant_id,
            AuditLog.hash_sha256.isnot(None),
        )
        .order_by(AuditLog.id.desc())
        .first()
    )
    return last[0] if last else None


def stamp_audit_hash(db: Session, audit: AuditLog) -> None:
    """Calcula e atribui hash_sha256 e hash_previous ao registro."""
    previous = get_last_hash_for_tenant(db, audit.tenant_id)
    audit.hash_previous = previous
    audit.hash_sha256 = compute_audit_hash(audit, previous)
