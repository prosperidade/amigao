from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.models.communication import CommunicationThread as ThreadModel
from app.models.communication import Message as MessageModel
from app.models.user import User
from app.schemas.communication import CommunicationThread, CommunicationThreadCreate, Message, MessageCreate
from app.services.tenant_guard import exigir_relacoes_do_tenant

router = APIRouter()

@router.post("/", response_model=CommunicationThread)
def create_thread(
    *,
    db: Session = Depends(deps.get_db),
    thread_in: CommunicationThreadCreate,
    current_user: User = Depends(deps.get_current_internal_user),
):
    dados = thread_in.model_dump()
    # `process_id` e `client_id` vêm do corpo. Achado da varredura de classe do
    # Passo 0 — fora da lista D1-D7, incluído por decisão de escopo.
    exigir_relacoes_do_tenant(db, current_user.tenant_id, dados)
    db_obj = ThreadModel(
        **dados,
        tenant_id=current_user.tenant_id
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

@router.get("/", response_model=list[CommunicationThread])
def get_threads(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    process_id: Optional[int] = None,
    current_user: User = Depends(deps.get_current_internal_user),
):
    query = db.query(ThreadModel).filter(ThreadModel.tenant_id == current_user.tenant_id)
    if process_id:
        query = query.filter(ThreadModel.process_id == process_id)
    return query.offset(skip).limit(limit).all()

@router.post("/{thread_id}/messages", response_model=Message)
def add_message(
    *,
    db: Session = Depends(deps.get_db),
    thread_id: int,
    message_in: MessageCreate,
    current_user: User = Depends(deps.get_current_internal_user),
):
    thread_obj = db.query(ThreadModel).filter(
        ThreadModel.id == thread_id,
        ThreadModel.tenant_id == current_user.tenant_id
    ).first()
    if not thread_obj:
        raise HTTPException(status_code=404, detail="Thread not found")

    msg_obj = MessageModel(
        **message_in.model_dump(),
        thread_id=thread_id,
        sender_id=current_user.id
    )
    db.add(msg_obj)
    db.commit()
    db.refresh(msg_obj)
    return msg_obj
