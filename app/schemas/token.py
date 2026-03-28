from typing import Literal, Optional

from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    tenant_id: Optional[int] = None
    client_id: Optional[int] = None
    profile: Literal["internal", "client_portal"] = "internal"
