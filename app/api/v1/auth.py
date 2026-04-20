from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.api.deps import get_current_active_user, get_db
from app.core import security
from app.core.config import settings
from app.core.rate_limit import limiter
from app.models.client import Client
from app.models.user import User
from app.schemas.token import Token
from app.schemas.user import User as UserSchema
from app.schemas.user_preferences import (
    PasswordChangeRequest,
    PreferencesUpdate,
    UserMeResponse,
    UserPreferences,
    UserProfileUpdate,
)

router = APIRouter()


def _get_user_by_email(db: Session, normalized_email: str) -> User | None:
    user = db.query(User).filter(User.email == normalized_email).first()
    if user:
        return user
    return (
        db.query(User)
        .filter(func.lower(func.trim(User.email)) == normalized_email)
        .first()
    )


def _get_portal_client_by_email(db: Session, tenant_id: int, normalized_email: str) -> Client | None:
    portal_client = (
        db.query(Client)
        .filter(
            Client.tenant_id == tenant_id,
            Client.email == normalized_email,
        )
        .first()
    )
    if portal_client:
        return portal_client
    return (
        db.query(Client)
        .filter(
            Client.tenant_id == tenant_id,
            Client.email.isnot(None),
            func.lower(func.trim(Client.email)) == normalized_email,
        )
        .first()
    )


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
def login_access_token(
    request: Request,
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_profile: str | None = Header(default=None, alias="X-Auth-Profile"),
) -> Any:
    """
    Login com email e senha. Retorna um token JWT.
    """
    normalized_email = form_data.username.strip().lower()
    user = _get_user_by_email(db, normalized_email)
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário inativo",
        )

    requested_profile = auth_profile.strip().lower() if auth_profile else None
    if requested_profile not in {None, "internal", "client_portal"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Perfil de autenticação inválido",
        )

    portal_client_id = None
    access_profile = "internal"

    if requested_profile == "client_portal":
        portal_client = _get_portal_client_by_email(db, user.tenant_id, normalized_email)
        if not portal_client:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuário sem acesso ao portal do cliente",
            )
        portal_client_id = portal_client.id
        access_profile = "client_portal"
    elif requested_profile is None and not user.is_superuser:
        portal_client = _get_portal_client_by_email(db, user.tenant_id, normalized_email)
        if portal_client:
            portal_client_id = portal_client.id
            access_profile = "client_portal"

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            subject=user.id,
            tenant_id=user.tenant_id,
            expires_delta=access_token_expires,
            client_id=portal_client_id,
            profile=access_profile,
        ),
        "token_type": "bearer",
    }


@router.get("/me", response_model=UserSchema)
def read_users_me(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retorna os dados do usuário autenticado.
    """
    return current_user


# ── Regente Sprint F Bloco 2 — Configurações (Camada 4) ────────────────────

@router.get("/me/full", response_model=UserMeResponse)
def read_me_full(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Retorna usuário autenticado + preferências expandidas (6 abas do Settings)."""
    raw_prefs = current_user.preferences or {}
    prefs = UserPreferences(**raw_prefs) if isinstance(raw_prefs, dict) else UserPreferences()
    return UserMeResponse(
        id=current_user.id,
        tenant_id=current_user.tenant_id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser,
        preferences=prefs,
    )


@router.patch("/me", response_model=UserMeResponse)
def update_me(
    body: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Atualiza nome e/ou email do próprio usuário."""
    if body.email is not None:
        new_email = body.email.strip().lower()
        if new_email != current_user.email:
            existing = _get_user_by_email(db, new_email)
            if existing and existing.id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email já em uso",
                )
            current_user.email = new_email
    if body.full_name is not None:
        current_user.full_name = body.full_name.strip()
    db.commit()
    db.refresh(current_user)
    return read_me_full(current_user)  # reusa serialização


@router.patch("/me/preferences", response_model=UserPreferences)
def update_me_preferences(
    body: PreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Merge parcial nas preferências (aceita qualquer subset dos 4 grupos)."""
    # Carrega estado atual e aplica merge por grupo.
    raw_prefs = current_user.preferences or {}
    if not isinstance(raw_prefs, dict):
        raw_prefs = {}
    current = UserPreferences(**raw_prefs)
    patch = body.model_dump(exclude_unset=True, exclude_none=True)
    merged = current.model_copy(update=patch)

    current_user.preferences = merged.model_dump()
    db.commit()
    db.refresh(current_user)
    return merged


@router.post("/password-change", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """Troca a senha do usuário autenticado. Exige senha atual correta."""
    if not security.verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha atual incorreta",
        )
    current_user.hashed_password = security.get_password_hash(body.new_password)
    db.commit()


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Logout do usuário. Em uma arquitetura JWT stateless, o frontend é responsável por 
    remover o token localmente. Este endpoint serve para validar o token atual e 
    poderia ser estendido para invalidar o token em uma blacklist (Redis) no futuro.
    """
    return {"detail": "Logout realizado com sucesso. O cliente deve remover o token."}
