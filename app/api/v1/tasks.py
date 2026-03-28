from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.api import deps
from app.models.task import Task as TaskModel
from app.models.user import User
from app.schemas.task import TaskCreate, TaskUpdate, Task

router = APIRouter()

@router.post("/", response_model=Task)
def create_task(
    *,
    db: Session = Depends(deps.get_db),
    task_in: TaskCreate,
    current_user: User = Depends(deps.get_current_internal_user),
):
    db_obj = TaskModel(
        **task_in.model_dump(), 
        tenant_id=current_user.tenant_id,
        created_by_user_id=current_user.id
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

@router.get("/", response_model=List[Task])
def get_tasks(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    process_id: Optional[int] = None,
    current_user: User = Depends(deps.get_current_internal_user),
):
    query = db.query(TaskModel).filter(TaskModel.tenant_id == current_user.tenant_id)
    if process_id:
        query = query.filter(TaskModel.process_id == process_id)
    return query.offset(skip).limit(limit).all()

@router.get("/{id}", response_model=Task)
def get_task(
    id: int, 
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_internal_user),
):
    task_obj = db.query(TaskModel).filter(
        TaskModel.id == id,
        TaskModel.tenant_id == current_user.tenant_id
    ).first()
    if not task_obj:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_obj

@router.patch("/{id}", response_model=Task)
def update_task(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    task_in: TaskUpdate,
    current_user: User = Depends(deps.get_current_internal_user),
):
    task_obj = db.query(TaskModel).filter(
        TaskModel.id == id,
        TaskModel.tenant_id == current_user.tenant_id
    ).first()
    if not task_obj:
        raise HTTPException(status_code=404, detail="Task not found")
        
    update_data = task_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task_obj, field, value)
        
    db.commit()
    db.refresh(task_obj)
    return task_obj
