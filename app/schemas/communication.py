from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class MessageBase(BaseModel):
    content: str
    is_internal: bool = False

class MessageCreate(MessageBase):
    pass

class Message(MessageBase):
    id: int
    thread_id: int
    sender_id: Optional[int] = None
    status: str
    external_msg_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CommunicationThreadBase(BaseModel):
    process_id: Optional[int] = None
    client_id: Optional[int] = None
    title: str
    channel: str
    external_id: Optional[str] = None

class CommunicationThreadCreate(CommunicationThreadBase):
    pass

class CommunicationThread(CommunicationThreadBase):
    id: int
    tenant_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    messages: list[Message] = []

    model_config = ConfigDict(from_attributes=True)
