"""Endpoint admin de verificação da hash chain de AuditLog (dívida #18).

Read-only, restrito a superusuário. Tenant vem sempre do JWT (nunca de header).
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit import AuditChainVerifyOut, BrokenLinkOut
from app.services.audit_hash import verify_audit_chain

router = APIRouter()


@router.get("/audit/verify-chain", response_model=AuditChainVerifyOut)
def verify_audit_chain_endpoint(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Verifica a integridade da hash chain de ``AuditLog`` do tenant do usuário.

    Recomputa cada hash em ordem e compara com o persistido (conteúdo + elo).
    Devolve a lista de elos quebrados (vazia ⇒ trilha íntegra). Restrito a
    superusuário — a trilha é multi-tenant e a verificação é operação sensível.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas superusuarios podem verificar a trilha de auditoria.",
        )

    broken = verify_audit_chain(db, current_user.tenant_id)
    total_checked = (
        db.query(AuditLog)
        .filter(
            AuditLog.tenant_id == current_user.tenant_id,
            AuditLog.hash_sha256.isnot(None),
        )
        .count()
    )
    return AuditChainVerifyOut(
        tenant_id=current_user.tenant_id,
        total_checked=total_checked,
        ok=len(broken) == 0,
        broken_links=[
            BrokenLinkOut(
                audit_id=b.audit_id,
                position=b.position,
                reason=b.reason,
                expected=b.expected,
                found=b.found,
            )
            for b in broken
        ],
    )
