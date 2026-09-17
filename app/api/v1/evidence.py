"""Authorized review and resumption endpoints; no job-completed shortcut."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.evidence import AgentExecution, EvidenceInvalidation, EvidenceReview, EvidenceVersion
from app.models.process import Process
from app.models.user import User
from app.schemas.evidence import ReviewRequest
from app.services.connected_agents import execution_data, get_execution, resume_execution
from app.services.evidence import authorize, build_envelope, last_review, lock_case, review_object, versions

router = APIRouter()
Db = Annotated[Session, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_internal_user)]


class ResumeRequest(BaseModel):
    expected_revision: int = Field(ge=0)
    recompute_stale: bool = False


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
    invalid = {i.evidence_id for i in db.query(EvidenceInvalidation).filter(
        EvidenceInvalidation.tenant_id == user.tenant_id, EvidenceInvalidation.process_id == process_id).all()}
    for row in versions(db, user.tenant_id, process_id):
        if row.kind not in {"conclusao", "observacao"}:
            continue
        review = last_review(db, row)
        history = db.query(EvidenceReview).filter(EvidenceReview.tenant_id == user.tenant_id,
            EvidenceReview.process_id == process_id, EvidenceReview.evidence_id == row.id).order_by(EvidenceReview.revision).all()
        rows.append({"object": row.content, "stale": row.id in invalid,
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
        EvidenceInvalidation.process_id == process_id, EvidenceInvalidation.returned_at.is_(None)).all()
    if not pending:
        raise HTTPException(409, "Não há pendência de coleta dependente")
    case = db.query(Process).filter(Process.id == process_id, Process.tenant_id == user.tenant_id).one()
    previous = case.macroetapa
    case.macroetapa = "coleta_documental"
    for item in pending:
        item.returned_at = datetime.now(UTC)
        item.returned_by_user_id = user.id
        item.reason = {**item.reason, "previous_stage": previous, "requested_stage": case.macroetapa}
    db.commit()
    return {"macroetapa": case.macroetapa, "previous_stage": previous}
