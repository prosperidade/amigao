from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime
from app.models.task import TaskStatus, TaskPriority


class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    process_id: Optional[int] = None
    property_id: Optional[int] = None
    document_id: Optional[int] = None
    
    status: TaskStatus = TaskStatus.a_fazer
    priority: TaskPriority = TaskPriority.medium

    assigned_to_user_id: Optional[int] = None
    due_date: Optional[datetime] = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    process_id: Optional[int] = None
    property_id: Optional[int] = None
    document_id: Optional[int] = None
    
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None

    assigned_to_user_id: Optional[int] = None
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


class Task(TaskBase):
    id: int
    tenant_id: int
    created_by_user_id: int
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    allowed_transitions: list[TaskStatus] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
