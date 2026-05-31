"""Schemas de auditoria — verificação da hash chain (dívida #18)."""

from pydantic import BaseModel


class BrokenLinkOut(BaseModel):
    """Um elo quebrado na hash chain de AuditLog."""

    audit_id: int | None
    position: int
    reason: str  # "content_tampered" | "broken_previous_link"
    expected: str | None = None
    found: str | None = None


class AuditChainVerifyOut(BaseModel):
    """Resultado da verificação de integridade da trilha de um tenant."""

    tenant_id: int
    total_checked: int
    ok: bool
    broken_links: list[BrokenLinkOut]
