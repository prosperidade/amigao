"""
Credentials API — cofre de logins de portais por cliente (PR 2.3).

CRUD tenant-scoped sobre `Credential`. A senha é criptografada em repouso
(ADR-014, coluna `EncryptedString`) e NUNCA volta em plaintext nas respostas.
Toda operação é auditada (AuditLog, hash chain SHA-256).
"""
import logging
from datetime import UTC
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.audit_log import AuditLog
from app.models.client import Client as ClientModel
from app.models.credential import Credential
from app.models.user import User
from app.schemas.credential import CredentialCreate, CredentialResponse, CredentialUpdate

router = APIRouter()
logger = logging.getLogger(__name__)


def _to_response(cred: Credential) -> CredentialResponse:
    """Serializa SEM expor a senha — só `has_password`."""
    return CredentialResponse(
        id=cred.id,
        client_id=cred.client_id,
        portal=cred.portal,
        label=cred.label,
        login=cred.login,
        url=cred.url,
        notes=cred.notes,
        has_password=bool(cred.password_encrypted),
        created_at=cred.created_at.isoformat() if cred.created_at else None,
    )


def _audit(db: Session, user: User, cred_id: int, action: str, details: str) -> None:
    audit = AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        entity_type="credential",
        entity_id=cred_id,
        action=action,
        details=details,
    )
    db.add(audit)
    db.flush()
    from app.services.audit_hash import stamp_audit_hash  # noqa: PLC0415
    stamp_audit_hash(db, audit)


def _load_or_404(db: Session, cred_id: int, tenant_id: int) -> Credential:
    cred = (
        db.query(Credential)
        .filter(
            Credential.id == cred_id,
            Credential.tenant_id == tenant_id,
            Credential.deleted_at.is_(None),
        )
        .first()
    )
    if not cred:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credencial não encontrada.")
    return cred


@router.post("", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
def create_credential(
    *,
    payload: CredentialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    # Tenant isolation: o cliente precisa ser do mesmo tenant.
    client = (
        db.query(ClientModel)
        .filter(ClientModel.id == payload.client_id, ClientModel.tenant_id == current_user.tenant_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado.")

    cred = Credential(
        tenant_id=current_user.tenant_id,
        client_id=payload.client_id,
        portal=payload.portal,
        label=payload.label,
        login=payload.login,
        password_encrypted=(payload.password or None),  # EncryptedString cifra no flush
        url=payload.url,
        notes=payload.notes,
    )
    db.add(cred)
    db.flush()
    _audit(db, current_user, cred.id, "created", f"Credencial '{cred.portal}' criada para cliente {cred.client_id}.")
    db.commit()
    db.refresh(cred)
    return _to_response(cred)


@router.get("", response_model=list[CredentialResponse])
def list_credentials(
    client_id: Optional[int] = Query(None, description="Filtra por cliente."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    q = db.query(Credential).filter(
        Credential.tenant_id == current_user.tenant_id,
        Credential.deleted_at.is_(None),
    )
    if client_id is not None:
        q = q.filter(Credential.client_id == client_id)
    return [_to_response(c) for c in q.order_by(Credential.id.desc()).all()]


@router.get("/{cred_id}", response_model=CredentialResponse)
def get_credential(
    cred_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    return _to_response(_load_or_404(db, cred_id, current_user.tenant_id))


@router.patch("/{cred_id}", response_model=CredentialResponse)
def update_credential(
    cred_id: int,
    payload: CredentialUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    cred = _load_or_404(db, cred_id, current_user.tenant_id)
    data = payload.model_dump(exclude_unset=True)
    # Senha: só atualiza se veio NÃO-vazia; ausente/vazia preserva a atual.
    new_password = data.pop("password", None)
    if new_password:
        cred.password_encrypted = new_password
    for field in ("portal", "label", "login", "url", "notes"):
        if field in data:
            setattr(cred, field, data[field])
    _audit(db, current_user, cred.id, "updated", f"Credencial {cred.id} atualizada.")
    db.commit()
    db.refresh(cred)
    return _to_response(cred)


@router.delete("/{cred_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_credential(
    cred_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> None:
    from datetime import datetime  # noqa: PLC0415

    cred = _load_or_404(db, cred_id, current_user.tenant_id)
    cred.deleted_at = datetime.now(UTC)
    _audit(db, current_user, cred.id, "deleted", f"Credencial {cred.id} removida (soft delete).")
    db.commit()
