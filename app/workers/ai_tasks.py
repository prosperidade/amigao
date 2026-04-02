"""
AI Tasks — Sprint 5 (Wave 2)

Tasks Celery para processamento assíncrono de IA:
- run_llm_classification: classifica demanda de um processo via LLM
- run_document_extraction: extrai campos estruturados de um documento via LLM

Ambas as tasks persistem AIJob e atualizam os campos relevantes no processo/documento.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.ai_job import AIJob, AIJobStatus, AIJobType
from app.models.document import Document
from app.models.process import Process

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Task: classificação de demanda
# ---------------------------------------------------------------------------

@celery_app.task(name="workers.run_llm_classification", bind=True, max_retries=2)
def run_llm_classification(self, *, process_id: int, tenant_id: int, user_id: int | None = None):
    """
    Classifica a demanda do processo via LLM e atualiza initial_diagnosis + demand_type.
    Persiste um AIJob com o resultado.
    """
    db = SessionLocal()
    job: AIJob | None = None
    try:
        process = db.query(Process).filter(
            Process.id == process_id,
            Process.tenant_id == tenant_id,
        ).first()

        if not process:
            logger.warning("run_llm_classification: processo %d não encontrado", process_id)
            return {"status": "not_found", "process_id": process_id}

        # Cria job em estado running
        job = AIJob(
            tenant_id=tenant_id,
            created_by_user_id=user_id,
            entity_type="process",
            entity_id=process_id,
            job_type=AIJobType.classify_demand,
            status=AIJobStatus.running,
            started_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        description = getattr(process, "description", "") or ""
        demand_type = getattr(process, "demand_type", None)

        from app.services.llm_classifier import classify_demand_with_llm  # noqa: PLC0415

        result, _ = classify_demand_with_llm(
            description=description,
            process_type=demand_type,
            urgency=getattr(process, "urgency", None),
            source_channel=getattr(process, "intake_source", None),
            tenant_id=tenant_id,
            save_job=False,  # não salvar novo job — já temos este
        )

        # Atualiza processo com resultado da classificação
        if not demand_type or demand_type == "nao_identificado":
            process.demand_type = result.demand_type
        process.initial_diagnosis = result.initial_diagnosis

        # Fecha job como completed
        job.status = AIJobStatus.completed
        job.finished_at = datetime.now(timezone.utc)
        job.result = {
            "demand_type": result.demand_type,
            "confidence": result.confidence,
            "urgency_flag": result.urgency_flag,
        }
        job.raw_output = result.initial_diagnosis

        db.add(process)
        db.add(job)
        db.commit()

        logger.info(
            "run_llm_classification: process_id=%d demand_type=%s confidence=%s",
            process_id, result.demand_type, result.confidence,
        )
        return {"status": "success", "process_id": process_id, "demand_type": result.demand_type}

    except Exception as exc:
        logger.exception("run_llm_classification: erro process_id=%d: %s", process_id, exc)
        if job:
            try:
                job.status = AIJobStatus.failed
                job.error = str(exc)
                job.finished_at = datetime.now(timezone.utc)
                db.add(job)
                db.commit()
            except Exception:
                pass
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Task: extração de documento
# ---------------------------------------------------------------------------

@celery_app.task(name="workers.run_document_extraction", bind=True, max_retries=2)
def run_document_extraction(self, *, document_id: int, tenant_id: int, user_id: int | None = None):
    """
    Extrai campos estruturados de um documento via LLM.
    O texto do documento deve estar no campo `extracted_text` ou será buscado via OCR futuro.
    Persiste um AIJob com os campos extraídos.
    """
    db = SessionLocal()
    job: AIJob | None = None
    try:
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
        ).first()

        if not document:
            logger.warning("run_document_extraction: documento %d não encontrado", document_id)
            return {"status": "not_found", "document_id": document_id}

        # Texto do documento — campo extracted_text se disponível
        text = getattr(document, "extracted_text", None) or ""
        if not text.strip():
            logger.info(
                "run_document_extraction: documento %d sem texto extraído, pulando",
                document_id,
            )
            return {"status": "no_text", "document_id": document_id}

        doc_type = getattr(document, "document_type", "outro") or "outro"

        # Cria job em estado running
        job = AIJob(
            tenant_id=tenant_id,
            created_by_user_id=user_id,
            entity_type="document",
            entity_id=document_id,
            job_type=AIJobType.extract_document,
            status=AIJobStatus.running,
            started_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        from app.services.document_extractor import extract_document_fields  # noqa: PLC0415

        fields, _ = extract_document_fields(
            text=text,
            doc_type=doc_type,
            document_id=document_id,
            tenant_id=tenant_id,
            save_job=False,
        )

        # Armazena resultado na extração do documento se campo disponível
        if hasattr(document, "extracted_fields") and fields:
            document.extracted_fields = fields

        job.status = AIJobStatus.completed
        job.finished_at = datetime.now(timezone.utc)
        job.result = fields

        db.add(job)
        if hasattr(document, "extracted_fields") and fields:
            db.add(document)
        db.commit()

        logger.info(
            "run_document_extraction: document_id=%d doc_type=%s fields=%d",
            document_id, doc_type, len(fields),
        )
        return {"status": "success", "document_id": document_id, "fields_count": len(fields)}

    except Exception as exc:
        logger.exception("run_document_extraction: erro document_id=%d: %s", document_id, exc)
        if job:
            try:
                job.status = AIJobStatus.failed
                job.error = str(exc)
                job.finished_at = datetime.now(timezone.utc)
                db.add(job)
                db.commit()
            except Exception:
                pass
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()
