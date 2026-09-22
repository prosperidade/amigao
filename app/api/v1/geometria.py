"""Geometria do caso (ADR-072): ler arquivo, ver medições, rodar o confronto, escolher a feição."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.document import Document
from app.models.user import User
from app.services import geometria
from app.services.evidence import authorize, lock_case

router = APIRouter()
Db = Annotated[Session, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_internal_user)]


class ProjecaoRequest(BaseModel):
    feicao_id: int
    motivo: str = Field(min_length=1)


@router.get("/{process_id}/geometria")
def painel_geometria(process_id: int, db: Db, user: UserDep):
    authorize(db, user.tenant_id, user.id, process_id)
    return geometria.painel(db, user.tenant_id, process_id)


@router.post("/{process_id}/geometria/documentos/{document_id}/ler")
def ler_geometria(process_id: int, document_id: int, db: Db, user: UserDep):
    authorize(db, user.tenant_id, user.id, process_id)
    lock_case(db, user.tenant_id, process_id)
    doc = db.query(Document).filter_by(id=document_id, tenant_id=user.tenant_id, process_id=process_id,
                                       deleted_at=None).first()
    if doc is None or not geometria.eh_arquivo_geo(doc):
        raise HTTPException(404, "Arquivo geoespacial não encontrado neste caso")
    leitura = geometria.processar_documento(db, doc, user_id=user.id)
    if leitura.estado == "lido":
        geometria.executar_confronto(db, user.tenant_id, process_id, user_id=user.id)
    db.commit()
    return geometria.painel(db, user.tenant_id, process_id)


@router.post("/{process_id}/geometria/confronto")
def rodar_confronto(process_id: int, db: Db, user: UserDep):
    authorize(db, user.tenant_id, user.id, process_id)
    lock_case(db, user.tenant_id, process_id)
    geometria.executar_confronto(db, user.tenant_id, process_id, user_id=user.id)
    db.commit()
    return geometria.painel(db, user.tenant_id, process_id)


@router.post("/{process_id}/geometria/projecao")
def escolher_projecao(process_id: int, body: ProjecaoRequest, db: Db, user: UserDep):
    authorize(db, user.tenant_id, user.id, process_id)
    lock_case(db, user.tenant_id, process_id)
    geometria.escolher_projecao(db, user.tenant_id, user.id, process_id, body.feicao_id, body.motivo)
    db.commit()
    return geometria.painel(db, user.tenant_id, process_id)
