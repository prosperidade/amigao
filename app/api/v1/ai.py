"""
AI Jobs API — Sprint 5

  POST /ai/classify              — classifica demanda via LLM (síncrono)
  POST /ai/extract               — extrai campos de documento via LLM (síncrono)
  POST /ai/jobs/classify-async   — dispara classificação como task Celery
  POST /ai/jobs/extract-async    — dispara extração como task Celery
  GET  /ai/jobs                  — lista jobs do tenant
  GET  /ai/jobs/{id}             — detalhe do job
  GET  /ai/status                — retorna se IA está configurada/habilitada
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.core.config import settings
from app.models.ai_job import AIJob
from app.models.user import User

router = APIRouter(prefix="/ai", tags=["IA"])
logger = logging.getLogger(__name__)

DbDep = Annotated[Session, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_internal_user)]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ClassifyRequest(BaseModel):
    description: str
    process_type: Optional[str] = None
    urgency: Optional[str] = None
    source_channel: Optional[str] = None
    process_id: Optional[int] = None
    save_job: bool = True


class ExtractRequest(BaseModel):
    text: str
    doc_type: str
    document_id: Optional[int] = None
    save_job: bool = True


class ClassifyAsyncRequest(BaseModel):
    process_id: int


class ExtractAsyncRequest(BaseModel):
    document_id: int


# ---------------------------------------------------------------------------
# GET /ai/status
# ---------------------------------------------------------------------------

@router.get("/status")
def ai_status(current_user: UserDep) -> dict[str, Any]:
    """Retorna se a IA está configurada e habilitada para o ambiente."""
    return {
        "ai_enabled": settings.AI_ENABLED,
        "ai_configured": settings.ai_configured,
        "default_model": settings.AI_DEFAULT_MODEL if settings.ai_configured else None,
        "providers_available": _available_providers(),
    }


# ---------------------------------------------------------------------------
# POST /ai/classify
# ---------------------------------------------------------------------------

@router.post("/classify")
def classify_demand(
    body: ClassifyRequest,
    db: DbDep,
    current_user: UserDep,
) -> dict[str, Any]:
    """
    Classifica a demanda usando regras + LLM.
    Retorna classificação enriquecida e o ai_job_id se LLM foi usado.
    """
    from app.core.ai_gateway import check_tenant_cost_limit  # noqa: PLC0415
    from app.services.llm_classifier import classify_demand_with_llm  # noqa: PLC0415

    if settings.ai_configured:
        check_tenant_cost_limit(current_user.tenant_id, db)

    result, ai_job_id = classify_demand_with_llm(
        description=body.description,
        process_type=body.process_type,
        urgency=body.urgency,
        source_channel=body.source_channel,
        tenant_id=current_user.tenant_id,
        save_job=body.save_job,
    )

    return {
        "demand_type": result.demand_type,
        "demand_label": result.demand_label,
        "confidence": result.confidence,
        "initial_diagnosis": result.initial_diagnosis,
        "required_documents": result.required_documents,
        "suggested_next_steps": result.suggested_next_steps,
        "urgency_flag": result.urgency_flag,
        "relevant_agencies": result.relevant_agencies,
        "llm_used": ai_job_id is not None,
        "ai_job_id": ai_job_id,
    }


# ---------------------------------------------------------------------------
# POST /ai/extract
# ---------------------------------------------------------------------------

@router.post("/extract")
def extract_document(
    body: ExtractRequest,
    db: DbDep,
    current_user: UserDep,
) -> dict[str, Any]:
    """
    Extrai campos estruturados de um documento via LLM.
    Retorna os campos extraídos e o ai_job_id.
    """
    from app.services.document_extractor import extract_document_fields, supported_doc_types  # noqa: PLC0415

    if not settings.ai_configured:
        raise HTTPException(
            status_code=503,
            detail="IA não está configurada neste ambiente. Configure AI_ENABLED=true e ao menos uma chave de API.",
        )

    from app.core.ai_gateway import check_tenant_cost_limit  # noqa: PLC0415

    check_tenant_cost_limit(current_user.tenant_id, db)

    if body.doc_type not in supported_doc_types():
        raise HTTPException(
            status_code=422,
            detail=f"Tipo de documento não suportado. Suportados: {supported_doc_types()}",
        )

    fields, ai_job_id = extract_document_fields(
        text=body.text,
        doc_type=body.doc_type,
        document_id=body.document_id,
        tenant_id=current_user.tenant_id,
        save_job=body.save_job,
    )

    return {
        "doc_type": body.doc_type,
        "extracted_fields": fields,
        "ai_job_id": ai_job_id,
    }


# ---------------------------------------------------------------------------
# POST /ai/jobs/classify-async
# ---------------------------------------------------------------------------

@router.post("/jobs/classify-async", status_code=202)
def classify_async(
    body: ClassifyAsyncRequest,
    db: DbDep,
    current_user: UserDep,
) -> dict[str, Any]:
    """Dispara classificação LLM assíncrona via Celery para um processo existente."""
    from app.core.ai_gateway import check_tenant_cost_limit  # noqa: PLC0415
    from app.workers.ai_tasks import run_llm_classification  # noqa: PLC0415

    if not settings.ai_configured:
        raise HTTPException(status_code=503, detail="IA não configurada.")

    check_tenant_cost_limit(current_user.tenant_id, db)

    task = run_llm_classification.delay(
        process_id=body.process_id,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
    )
    return {"task_id": task.id, "status": "queued", "process_id": body.process_id}


# ---------------------------------------------------------------------------
# POST /ai/jobs/extract-async
# ---------------------------------------------------------------------------

@router.post("/jobs/extract-async", status_code=202)
def extract_async(
    body: ExtractAsyncRequest,
    db: DbDep,
    current_user: UserDep,
) -> dict[str, Any]:
    """Dispara extração de documento LLM assíncrona via Celery."""
    from app.core.ai_gateway import check_tenant_cost_limit  # noqa: PLC0415
    from app.workers.ai_tasks import run_document_extraction  # noqa: PLC0415

    if not settings.ai_configured:
        raise HTTPException(status_code=503, detail="IA não configurada.")

    check_tenant_cost_limit(current_user.tenant_id, db)

    task = run_document_extraction.delay(
        document_id=body.document_id,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
    )
    return {"task_id": task.id, "status": "queued", "document_id": body.document_id}


# ---------------------------------------------------------------------------
# GET /ai/jobs
# ---------------------------------------------------------------------------

@router.get("/jobs")
def list_jobs(
    db: DbDep,
    current_user: UserDep,
    entity_type: Annotated[Optional[str], Query()] = None,
    entity_id: Annotated[Optional[int], Query()] = None,
    job_type: Annotated[Optional[str], Query()] = None,
    status: Annotated[Optional[str], Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[dict[str, Any]]:
    q = db.query(AIJob).filter(AIJob.tenant_id == current_user.tenant_id)
    if entity_type:
        q = q.filter(AIJob.entity_type == entity_type)
    if entity_id is not None:
        q = q.filter(AIJob.entity_id == entity_id)
    if job_type:
        q = q.filter(AIJob.job_type == job_type)
    if status:
        q = q.filter(AIJob.status == status)
    jobs = q.order_by(AIJob.created_at.desc()).offset(skip).limit(limit).all()
    return [_serialize_job(j) for j in jobs]


# ---------------------------------------------------------------------------
# GET /ai/jobs/{id}
# ---------------------------------------------------------------------------

@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: DbDep, current_user: UserDep) -> dict[str, Any]:
    job = db.query(AIJob).filter(
        AIJob.id == job_id,
        AIJob.tenant_id == current_user.tenant_id,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    return _serialize_job(job)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_job(j: AIJob) -> dict[str, Any]:
    return {
        "id": j.id,
        "entity_type": j.entity_type,
        "entity_id": j.entity_id,
        "job_type": j.job_type.value if j.job_type else None,
        "status": j.status.value if j.status else None,
        "model_used": j.model_used,
        "provider": j.provider,
        "tokens_in": j.tokens_in,
        "tokens_out": j.tokens_out,
        "cost_usd": j.cost_usd,
        "duration_ms": j.duration_ms,
        "result": j.result,
        "error": j.error,
        "created_at": j.created_at,
        "finished_at": j.finished_at,
    }


def _available_providers() -> list[str]:
    providers = []
    if settings.OPENAI_API_KEY:
        providers.append("openai")
    if settings.GEMINI_API_KEY:
        providers.append("gemini")
    if settings.ANTHROPIC_API_KEY:
        providers.append("anthropic")
    return providers
