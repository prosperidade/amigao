from datetime import datetime

from pydantic import BaseModel


class AuditLogRead(BaseModel):
    id: int
    tenant_id: int
    user_id: int | None = None
    entity_type: str
    entity_id: int
    action: str
    old_value: str | None = None
    new_value: str | None = None
    details: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    hash_sha256: str | None = None
    hash_previous: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
