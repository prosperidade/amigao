"""
ocr_tasks — Task Celery que roda OCR antes do agente extrator.

Sprint V hardening (2026-05-08). Auto-trigger em /confirm-upload (2026-05-16):
todo PDF persistido passa por esta task; o frontend acompanha via WebSocket.

Pipeline:
  1. Cache self: skip se Document.extracted_text já populado (a menos que force=True).
  2. Cache twin: skip se outro Document do mesmo tenant com mesmo SHA-256
     já tem texto extraído (re-upload do mesmo arquivo).
  3. Budget guard: respeita o teto mensal de IA do tenant antes de chamar Gemini.
  4. OCR via app.services.ocr_pdf (pypdf → Gemini Vision → OpenAI Vision).
  5. AIJob persistido (job_type=extract_document, agent_name='ocr_pdf') para audit.
  6. Evento WebSocket document.ocr.completed / document.ocr.failed por tenant.
  7. Despacha o agente extrator com metadata padronizada.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Optional

from app.core.celery_app import celery_app
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(
    name="workers.ocr_then_extract",
    bind=True,
    max_retries=2,
    retry_backoff=True,
    retry_backoff_max=120,
    soft_time_limit=180,
)
def ocr_then_extract(
    self,
    doc_id: int,
    tenant_id: int,
    user_id: int,
    draft_id: Optional[int] = None,
    force: bool = False,
) -> dict[str, Any]:
    from app.core.ai_gateway import check_tenant_monthly_budget  # noqa: PLC0415
    from app.models.ai_job import AIJob, AIJobStatus, AIJobType  # noqa: PLC0415
    from app.models.document import Document, OcrStatus  # noqa: PLC0415
    from app.services.notifications import publish_realtime_event  # noqa: PLC0415
    from app.services.ocr_pdf import compute_sha256, extract_text_from_pdf  # noqa: PLC0415
    from app.services.storage import get_storage_service  # noqa: PLC0415
    from app.workers.agent_tasks import run_agent  # noqa: PLC0415

    db = SessionLocal()
    try:
        doc = (
            db.query(Document)
            .filter(Document.id == doc_id, Document.tenant_id == tenant_id)
            .first()
        )
        if not doc:
            logger.warning(
                "ocr_then_extract: doc %s não encontrado para tenant %s",
                doc_id, tenant_id,
            )
            return {"status": "not_found", "doc_id": doc_id}

        # 1) Cache self — texto já existe (force=True bypassa pra re-OCR)
        if (doc.extracted_text or "").strip() and not force:
            logger.info(
                "ocr_then_extract: doc=%s cache_hit_self chars=%d",
                doc_id, len(doc.extracted_text),
            )
            _emit_ocr_event(
                publish_realtime_event, tenant_id, doc,
                status_label="completed", method="cache_self",
                chars=len(doc.extracted_text), cost_usd=0.0,
            )
            _dispatch_extrator(run_agent, doc, draft_id, tenant_id, user_id)
            return {
                "status": "cache_hit_self",
                "doc_id": doc_id,
                "chars": len(doc.extracted_text),
            }

        doc.ocr_status = OcrStatus.processing
        db.add(doc)
        db.commit()

        # 2) Download bytes
        storage = get_storage_service()
        pdf_bytes = storage.download_bytes(doc.storage_key)
        if not pdf_bytes:
            doc.ocr_status = OcrStatus.failed
            db.add(doc)
            db.commit()
            logger.warning(
                "ocr_then_extract: storage_key=%s sem bytes (MinIO)",
                doc.storage_key,
            )
            _emit_ocr_event(
                publish_realtime_event, tenant_id, doc,
                status_label="failed", method="none",
                chars=0, cost_usd=0.0, error="no_bytes",
            )
            return {"status": "no_bytes", "doc_id": doc_id}

        # Sempre persiste o checksum no doc (audit/dedup futuro)
        checksum = compute_sha256(pdf_bytes)
        if not doc.checksum_sha256:
            doc.checksum_sha256 = checksum
            db.add(doc)
            db.commit()

        # 3) Cache twin — mesmo arquivo já foi OCR'd antes
        twin = (
            db.query(Document)
            .filter(
                Document.tenant_id == tenant_id,
                Document.checksum_sha256 == checksum,
                Document.id != doc.id,
                Document.extracted_text.isnot(None),
                Document.deleted_at.is_(None),
            )
            .order_by(Document.id.desc())
            .first()
        )
        if twin and (twin.extracted_text or "").strip():
            doc.extracted_text = twin.extracted_text
            doc.extracted_at = datetime.now(UTC)
            doc.ocr_status = OcrStatus.done
            doc.confidence_score = twin.confidence_score
            db.add(doc)
            db.commit()
            logger.info(
                "ocr_then_extract: doc=%s cache_hit_twin twin=%s chars=%d",
                doc_id, twin.id, len(twin.extracted_text),
            )
            _emit_ocr_event(
                publish_realtime_event, tenant_id, doc,
                status_label="completed", method="cache_twin",
                chars=len(twin.extracted_text), cost_usd=0.0,
                twin_id=twin.id,
            )
            _dispatch_extrator(run_agent, doc, draft_id, tenant_id, user_id)
            return {
                "status": "cache_hit_twin",
                "doc_id": doc_id,
                "twin_id": twin.id,
                "chars": len(twin.extracted_text),
            }

        # 4) Budget guard — antes de gastar com Gemini
        try:
            check_tenant_monthly_budget(tenant_id, db)
        except Exception as exc:
            doc.ocr_status = OcrStatus.failed
            db.add(doc)
            db.commit()
            logger.warning(
                "ocr_then_extract: budget guard rejeitou tenant=%s doc=%s: %s",
                tenant_id, doc_id, exc,
            )
            _emit_ocr_event(
                publish_realtime_event, tenant_id, doc,
                status_label="skipped_budget", method="none",
                chars=0, cost_usd=0.0, error=str(exc),
            )
            return {
                "status": "budget_exceeded",
                "doc_id": doc_id,
                "error": str(exc),
            }

        # 5) OCR
        started_at = datetime.now(UTC)
        result = extract_text_from_pdf(
            pdf_bytes,
            mime_type=doc.content_type or "application/pdf",
        )
        finished_at = datetime.now(UTC)

        # 6) Persiste AIJob (audit + cost tracking)
        ai_job = AIJob(
            tenant_id=tenant_id,
            created_by_user_id=user_id,
            entity_type="document",
            entity_id=doc.id,
            job_type=AIJobType.extract_document,
            status=AIJobStatus.completed if result.text else AIJobStatus.failed,
            agent_name="ocr_pdf",
            model_used=result.model_used or None,
            provider=result.provider or None,
            tokens_in=result.tokens_in or None,
            tokens_out=result.tokens_out or None,
            cost_usd=result.cost_usd or None,
            duration_ms=result.duration_ms or None,
            input_payload={
                "doc_id": doc.id,
                "method": result.method,
                "checksum": checksum,
                "size_bytes": len(pdf_bytes),
                "content_type": doc.content_type,
            },
            result={
                "method": result.method,
                "chars": result.chars,
                # Não guardamos o texto inteiro aqui pra não inflar a tabela
                # (já fica em Document.extracted_text). Preview ajuda no debug.
                "text_preview": (result.text or "")[:500],
            },
            error=result.error,
            started_at=started_at,
            finished_at=finished_at,
        )
        db.add(ai_job)

        if result.text:
            doc.extracted_text = result.text
            doc.extracted_at = finished_at
            doc.ocr_status = OcrStatus.done
            # pypdf é determinístico; Gemini Vision pode alucinar — confidence
            # menor sinaliza "review_required" pra UI futura.
            doc.confidence_score = 0.95 if result.method == "pypdf" else 0.70
        else:
            doc.ocr_status = OcrStatus.failed

        db.add(doc)
        db.commit()

        logger.info(
            "ocr_then_extract: doc=%s method=%s chars=%d cost_usd=%.6f ms=%d ai_job=%s",
            doc_id, result.method, result.chars, result.cost_usd,
            result.duration_ms, ai_job.id,
        )

        _emit_ocr_event(
            publish_realtime_event, tenant_id, doc,
            status_label="completed" if result.text else "failed",
            method=result.method,
            chars=result.chars,
            cost_usd=result.cost_usd,
            ai_job_id=ai_job.id,
            error=result.error if not result.text else None,
        )

        if result.text:
            _dispatch_extrator(run_agent, doc, draft_id, tenant_id, user_id)
        return {
            "status": "ocr_ok" if result.text else "ocr_failed",
            "doc_id": doc_id,
            "method": result.method,
            "chars": result.chars,
            "cost_usd": result.cost_usd,
            "ai_job_id": ai_job.id,
        }

    except Exception as exc:
        db.rollback()
        logger.exception("ocr_then_extract: doc=%s falhou: %s", doc_id, exc)
        try:
            raise self.retry(exc=exc, countdown=30)
        except Exception:
            return {"status": "error", "doc_id": doc_id, "error": str(exc)}
    finally:
        db.close()


def _dispatch_extrator(run_agent, doc, draft_id, tenant_id, user_id) -> None:
    """Enfileira o agente extrator com a mesma metadata do fluxo /import original."""
    run_agent.delay(
        agent_name="extrator",
        tenant_id=tenant_id,
        user_id=user_id,
        process_id=None,
        metadata={
            "document_id": doc.id,
            "storage_key": doc.storage_key,
            "document_type": doc.document_type,
            "intake_draft_id": draft_id,
        },
    )


def _emit_ocr_event(
    publish_realtime_event,
    tenant_id: int,
    doc,
    *,
    status_label: str,
    method: str,
    chars: int,
    cost_usd: float,
    ai_job_id: Optional[int] = None,
    twin_id: Optional[int] = None,
    error: Optional[str] = None,
) -> None:
    """Emite document.ocr.completed (sucesso/cache) ou document.ocr.failed.

    Falha de publicação é logada e absorvida — nunca derruba a task de OCR.
    """
    event_type = "document.ocr.failed" if status_label in ("failed", "skipped_budget") else "document.ocr.completed"
    payload: dict[str, Any] = {
        "document_id": doc.id,
        "process_id": doc.process_id,
        "client_id": doc.client_id,
        "status": status_label,
        "method": method,
        "chars": chars,
        "cost_usd": cost_usd,
    }
    if ai_job_id is not None:
        payload["ai_job_id"] = ai_job_id
    if twin_id is not None:
        payload["twin_id"] = twin_id
    if error:
        payload["error"] = error
    try:
        publish_realtime_event(
            tenant_id=tenant_id,
            event_type=event_type,
            payload=payload,
        )
    except Exception as exc:  # noqa: BLE001 — defensive: WS failure shouldn't fail OCR
        logger.warning(
            "ocr_then_extract: falha ao publicar %s para doc=%s: %s",
            event_type, doc.id, exc,
        )
