from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import bcrypt
from jose import jwt

from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def create_access_token(
    subject: str | int,
    tenant_id: int,
    expires_delta: Optional[timedelta] = None,
    client_id: Optional[int] = None,
    profile: Literal["internal", "client_portal"] = "internal",
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject), "tenant_id": tenant_id, "profile": profile}
    if client_id is not None:
        to_encode["client_id"] = client_id
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt
