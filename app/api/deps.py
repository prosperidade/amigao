from dataclasses import dataclass
from typing import Generator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import ExpiredSignatureError, jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.client import Client
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.token import TokenPayload

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)


@dataclass
class AccessContext:
    user: User
    tenant: Tenant
    client: Optional[Client] = None
    profile: str = "internal"

    @property
    def tenant_id(self) -> int:
        return self.user.tenant_id

    @property
    def client_id(self) -> Optional[int]:
        return self.client.id if self.client else None

    @property
    def is_client_portal(self) -> bool:
        return self.profile == "client_portal"


def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


def get_token_payload(token: str = Depends(reusable_oauth2)) -> TokenPayload:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        token_data = TokenPayload(**payload)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token inválido",
        )
    except ValidationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Payload do token inválido",
        )
    if not token_data.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token inválido",
        )
    return token_data


def get_current_user(
    db: Session = Depends(get_db), token_data: TokenPayload = Depends(get_token_payload)
) -> User:
    user = db.query(User).filter(User.id == int(token_data.sub)).first() # type: ignore
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    if token_data.tenant_id is not None and user.tenant_id != token_data.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: tenant incompatível",
        )
    return user

def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuário inativo")
    return current_user

def get_current_tenant(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado")
    return tenant


def get_access_context(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    token_data: TokenPayload = Depends(get_token_payload),
) -> AccessContext:
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado")

    if token_data.profile == "client_portal" and token_data.client_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Escopo do portal do cliente inválido",
        )
    if token_data.profile != "client_portal" and token_data.client_id is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Escopo interno inválido",
        )

    client = None
    if token_data.profile == "client_portal":
        client = (
            db.query(Client)
            .filter(Client.id == token_data.client_id, Client.tenant_id == tenant.id)
            .first()
        )
        if not client:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Escopo do portal do cliente inválido",
            )

    return AccessContext(user=current_user, tenant=tenant, client=client, profile=token_data.profile)


def get_current_internal_user(
    current_user: User = Depends(get_current_active_user),
    token_data: TokenPayload = Depends(get_token_payload),
) -> User:
    if token_data.profile == "client_portal" or token_data.client_id is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito ao portal do cliente",
        )
    return current_user
