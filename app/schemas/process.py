from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.process import ProcessStatus


class ProcessBase(BaseModel):
    title: str
    process_type: Optional[str] = "licenciamento"
    client_id: int
    description: Optional[str] = None
    status: ProcessStatus = ProcessStatus.triagem
    property_id: Optional[int] = None
    priority: Optional[str] = None
    urgency: Optional[str] = None
    responsible_user_id: Optional[int] = None
    due_date: Optional[datetime] = None


class ProcessCreate(ProcessBase):
    pass


class ProcessUpdate(BaseModel):
    title: Optional[str] = None
    process_type: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProcessStatus] = None


class ProcessStatusUpdate(BaseModel):
    status: ProcessStatus


class Process(ProcessBase):
    id: int
    tenant_id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}
