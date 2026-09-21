"""Authorized review and resumption endpoints; no job-completed shortcut."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.evidence import AgentExecution, EvidenceInvalidation, EvidenceVersion, RetornoColeta
from app.models.process import Process
from app.models.user import User
from app.schemas.evidence import ReviewRequest
from app.services.connected_agents import execution_data, get_execution, resume_execution
from app.services.evidence import (
    authorize,
    build_envelope,
    lock_case,
    review_object,
    reviews_by_evidence,
    versions,
)

router = APIRouter()
Db = Annotated[Session, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_internal_user)]


class ResumeRequest(BaseModel):
    expected_revision: int = Field(ge=0)
    recompute_stale: bool = False


class ReclassificacaoRequest(BaseModel):
    tipo: str
    motivo: str = Field(min_length=1)
    expected_version: int = Field(ge=0)


@router.post("/cases/{process_id}/documents/{document_id}/associate")
def associar_documento(process_id: int, document_id: int, db: Db, user: UserDep):
    from app.models.document import Document
    authorize(db, user.tenant_id, user.id, process_id)
    lock_case(db, user.tenant_id, process_id)
    doc = db.query(Document).filter_by(id=document_id, tenant_id=user.tenant_id,
        deleted_at=None).with_for_update().first()
    if doc is None:
        raise HTTPException(404, "Documento não encontrado")
    if doc.process_id not in (None, process_id):
        raise HTTPException(409, "Documento já pertence a outro caso")
    doc.process_id = process_id
    db.commit()
    return {"document_id": doc.id, "process_id": process_id}


@router.get("/cases/{process_id}/documents")
def documentos_do_caso(process_id: int, db: Db, user: UserDep):
    from app.models.document import Document
    from app.services.entrada_semantica import classificacao_atual
    authorize(db, user.tenant_id, user.id, process_id)
    result = []
    for doc in db.query(Document).filter_by(tenant_id=user.tenant_id, process_id=process_id, deleted_at=None).order_by(Document.id):
        c = classificacao_atual(db, doc)
        result.append({"id": doc.id, "filename": doc.original_file_name,
            "tipo": (c.tipo_revisado or c.tipo_proposto) if c else doc.document_type,
            "classificacao_versao": c.versao if c else 0, "review_required": doc.review_required,
            "extraction_status": doc.extraction_status,
            "rejeicoes": (db.query(EvidenceVersion).filter_by(
                tenant_id=user.tenant_id, process_id=process_id,
                object_id=f"extracao:rejeicoes:{doc.id}").order_by(EvidenceVersion.version.desc()).first())})
        report = (result[-1]["rejeicoes"].content["attributes"].get("normalized") or {}) if result[-1]["rejeicoes"] else {}
        result[-1]["rejeicoes"] = report.get("rejeicoes", [])
        result[-1]["campos_sem_suporte"] = report.get("campos_sem_suporte", [])
        result[-1]["reparos"] = report.get("reparos", [])
    return result


@router.post("/cases/{process_id}/documents/{document_id}/reclassify")
def reclassificar_documento(process_id: int, document_id: int, body: ReclassificacaoRequest, db: Db, user: UserDep):
    from app.schemas.entrada_semantica import EspecieDocumental
    from app.services.entrada_semantica import reclassificar
    if body.tipo not in EspecieDocumental._value2member_map_:
        raise HTTPException(422, "Espécie documental inválida")
    result = reclassificar(db, user.tenant_id, user.id, process_id, document_id,
        body.tipo, body.motivo, body.expected_version)
    db.commit()
    return result


@router.get("/cases/{process_id}/sources/{object_id}/versions/{version}")
def source_version(process_id: int, object_id: str, version: int, db: Db, user: UserDep):
    # Archive does not erase authorized evidence history.
    case = db.query(Process).filter(Process.id == process_id, Process.tenant_id == user.tenant_id).first()
    if case is None:
        raise HTTPException(404, "Caso não encontrado")
    row = db.query(EvidenceVersion).filter(EvidenceVersion.tenant_id == user.tenant_id,
        EvidenceVersion.process_id == process_id, EvidenceVersion.object_id == object_id,
        EvidenceVersion.version == version).first()
    if row is None:
        raise HTTPException(404, "Evidência não encontrada")
    return {"object": row.content, "source": row.source_record}


@router.get("/cases/{process_id}")
def case_evidence(process_id: int, db: Db, user: UserDep):
    envelope = build_envelope(db, user.tenant_id, user.id, process_id)
    rows = []
    invalidations = db.query(EvidenceInvalidation).filter(
        EvidenceInvalidation.tenant_id == user.tenant_id, EvidenceInvalidation.process_id == process_id).all()
    invalid = {i.evidence_id for i in invalidations}
    superseded = {i.evidence_id for i in invalidations if "superada_por" in (i.reason or {})}
    reviews = reviews_by_evidence(db, user.tenant_id, process_id)
    for row in versions(db, user.tenant_id, process_id):
        if row.kind not in {"conclusao", "observacao"}:
            continue
        history = reviews.get(row.id, [])
        review = history[-1] if history else None
        rows.append({"object": row.content, "stale": row.id in invalid, "superseded": row.id in superseded,
                     "history": [{"action": r.action, "author": r.author_id, "justification": r.justification,
                                  "at": r.created_at, "revision": r.revision, "premises": r.premises} for r in history],
                     "revision": review.revision if review else 0,
                     "review": {"action": review.action, "author": review.author_id,
                                "justification": review.justification, "at": review.created_at,
                                "premises": review.premises} if review else None})
    executions = db.query(AgentExecution).filter(AgentExecution.tenant_id == user.tenant_id,
        AgentExecution.process_id == process_id).order_by(AgentExecution.created_at).all()
    db.commit()
    return {"envelope": envelope, "objects": rows, "executions": [execution_data(e) for e in executions]}


@router.post("/cases/{process_id}/objects/{object_id}/review")
def review(process_id: int, object_id: str, body: ReviewRequest, db: Db, user: UserDep):
    result = review_object(db, user.tenant_id, user.id, process_id, object_id, body)
    db.commit()
    return result


@router.get("/executions/{execution_id}")
def execution(execution_id: str, db: Db, user: UserDep):
    return execution_data(get_execution(db, user.tenant_id, user.id, execution_id))


@router.post("/executions/{execution_id}/resume")
def resume(execution_id: str, body: ResumeRequest, db: Db, user: UserDep):
    result = resume_execution(db, user.tenant_id, user.id, execution_id, body.expected_revision,
                              recompute_stale=body.recompute_stale)
    db.commit()
    return execution_data(result)


@router.post("/cases/{process_id}/return-to-collection")
def return_to_collection(process_id: int, db: Db, user: UserDep):
    authorize(db, user.tenant_id, user.id, process_id)
    lock_case(db, user.tenant_id, process_id, wait=False)
    pending = db.query(EvidenceInvalidation).filter(EvidenceInvalidation.tenant_id == user.tenant_id,
        EvidenceInvalidation.process_id == process_id, EvidenceInvalidation.returned_at.is_(None),
        ~db.query(RetornoColeta.id).filter(RetornoColeta.invalidacao_id == EvidenceInvalidation.id,
            RetornoColeta.tenant_id == user.tenant_id, RetornoColeta.process_id == process_id).exists()).all()
    # A re-extraction superseding its previous version is not a collection pendency.
    pending = [i for i in pending if "superada_por" not in (i.reason or {})]
    if not pending:
        raise HTTPException(409, "Não há pendência de coleta dependente")
    case = db.query(Process).filter(Process.id == process_id, Process.tenant_id == user.tenant_id).one()
    previous = case.macroetapa
    case.macroetapa = "coleta_documental"
    for item in pending:
        db.add(RetornoColeta(tenant_id=user.tenant_id, process_id=process_id,
            invalidacao_id=item.id, author_id=user.id, previous_stage=previous))
    db.commit()
    return {"macroetapa": case.macroetapa, "previous_stage": previous}
