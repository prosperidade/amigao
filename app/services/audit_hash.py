"""Hash chain service for AuditLog integrity."""

import hashlib
import json
from dataclasses import dataclass
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


# ---------------------------------------------------------------------------
# Verificação da cadeia (dívida #18)
# ---------------------------------------------------------------------------

@dataclass
class BrokenLink:
    """Um elo quebrado detectado ao verificar a hash chain de um tenant.

    ``reason``:
    - ``"content_tampered"``: o ``hash_sha256`` persistido não bate com o hash
      recomputado a partir dos campos do registro (alguém alterou um campo
      auditado depois de carimbado).
    - ``"broken_previous_link"``: o ``hash_previous`` do registro não aponta para
      o ``hash_sha256`` do registro anterior da cadeia (registro removido,
      reordenado ou inserido fora de ordem).
    """

    audit_id: Optional[int]
    position: int
    reason: str
    expected: Optional[str]
    found: Optional[str]


def _verify_chain(audits: list[AuditLog]) -> list[BrokenLink]:
    """Verifica uma sequência JÁ ORDENADA (por id asc) de registros carimbados.

    Função pura (sem DB) — recebe os registros e devolve os elos quebrados. Faz
    duas checagens ortogonais por registro: integridade do elo (``hash_previous``)
    e integridade do conteúdo (``hash_sha256`` recomputado).
    """
    broken: list[BrokenLink] = []
    prev_hash: Optional[str] = None
    for position, audit in enumerate(audits):
        # 1. Integridade do elo: hash_previous deve apontar para o anterior.
        if audit.hash_previous != prev_hash:
            broken.append(BrokenLink(
                audit_id=audit.id,
                position=position,
                reason="broken_previous_link",
                expected=prev_hash,
                found=audit.hash_previous,
            ))
        # 2. Integridade do conteúdo: recomputa com o hash_previous PERSISTIDO,
        #    isolando adulteração dos campos do próprio registro.
        recomputed = compute_audit_hash(audit, audit.hash_previous)
        if recomputed != audit.hash_sha256:
            broken.append(BrokenLink(
                audit_id=audit.id,
                position=position,
                reason="content_tampered",
                expected=recomputed,
                found=audit.hash_sha256,
            ))
        prev_hash = audit.hash_sha256
    return broken


def verify_audit_chain(db: Session, tenant_id: int) -> list[BrokenLink]:
    """Percorre a hash chain de um tenant e devolve os elos quebrados.

    Considera apenas registros carimbados (``hash_sha256`` não nulo), em ordem de
    ``id`` ascendente — a mesma base sobre a qual ``stamp_audit_hash`` encadeia
    (ver ``get_last_hash_for_tenant``). Lista vazia ⇒ cadeia íntegra.
    """
    audits = (
        db.query(AuditLog)
        .filter(
            AuditLog.tenant_id == tenant_id,
            AuditLog.hash_sha256.isnot(None),
        )
        .order_by(AuditLog.id.asc())
        .all()
    )
    return _verify_chain(audits)
