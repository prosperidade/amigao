"""
audio_tasks — task Celery que TRANSCREVE áudio de reunião (dívida #103 · ADR-060).

Irmã de `ocr_tasks.ocr_then_extract`, e de propósito com a mesma anatomia: o áudio
não ganha pipeline paralelo, ganha o mesmo pipeline com outra forma de leitura.
Por isso reusa daqui de fora o estado (`Document.ocr_status`/`ocr_error`), o evento
de WebSocket (`document.ocr.*`), o cache SHA-256, o budget guard e o AIJob.

Pipeline:
  1. Cache self: skip se `Document.extracted_text` já populado (a menos que force).
  2. Cache twin: outro Document do mesmo tenant com o mesmo SHA-256 já transcrito
     (o mesmo áudio subido no rascunho e de novo no caso não paga duas vezes).
  3. Budget guard: teto mensal de IA do tenant antes de gastar.
  4. Transcrição via `app.services.transcricao_audio` (Whisper atrás do ai_gateway).
  5. GANCHO opcional de resumo estruturado (AUDIO_TRANSCRICAO_RESUMO_ENABLED).
  6. AIJob persistido (job_type=extract_document, agent_name='transcricao_audio').
  7. Evento WebSocket document.ocr.completed / document.ocr.failed por tenant.

O que ela deliberadamente NÃO faz: despachar o agente `extrator`. Conversa de
reunião não é documento cadastral — deixar o extrator garimpar matrícula e área
numa transcrição de fala espontânea encheria o staging de campo inventado a partir
de "acho que é uns quatrocentos hectares". A transcrição chega ao diagnóstico pelo
canal de TEXTO (`_documentos_com_trecho`), que é onde ela vale como fonte.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Optional

from celery.exceptions import MaxRetriesExceededError

from app.core.celery_app import celery_app
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


def _preferencias_ia(db, *, tenant_id: int, user_id: int) -> Optional[dict]:
    """Preferências de IA do consultor (BYOK), ou None para cair no default global.

    Best-effort: usuário ausente ou chave indecifrável não pode derrubar a
    transcrição — nesse caso roda na conta do sistema, como os demais agentes.
    """
    from app.models.user import User  # noqa: PLC0415
    from app.services.user_preferences import get_ai_runtime  # noqa: PLC0415

    try:
        user = (
            db.query(User)
            .filter(User.id == user_id, User.tenant_id == tenant_id)
            .first()
        )
        return get_ai_runtime(user) if user else None
    except Exception as exc:  # noqa: BLE001 — preferência não é pré-requisito
        logger.warning("transcribe_audio_document: prefs de IA indisponíveis: %s", exc)
        return None


@celery_app.task(
    name="workers.transcribe_audio_document",
    bind=True,
    max_retries=2,
    retry_backoff=True,
    retry_backoff_max=120,
    # Uma reunião de 30 min leva ~40-90s no Whisper; o teto do provedor (25 MB)
    # limita o pior caso. 600s dá folga para retry de 503 sem deixar a fila do
    # worker (pool=solo) travada indefinidamente.
    soft_time_limit=600,
)
def transcribe_audio_document(
    self,
    doc_id: int,
    tenant_id: int,
    user_id: int,
    draft_id: Optional[int] = None,
    force: bool = False,
) -> dict[str, Any]:
    from app.core.ai_gateway import check_tenant_monthly_budget  # noqa: PLC0415
    from app.core.config import settings  # noqa: PLC0415
    from app.models.ai_job import AIJob, AIJobStatus, AIJobType  # noqa: PLC0415
    from app.models.document import Document, OcrStatus  # noqa: PLC0415
    from app.services.notifications import publish_realtime_event  # noqa: PLC0415
    from app.services.ocr_pdf import compute_sha256  # noqa: PLC0415
    from app.services.storage import StorageDownloadError, get_storage_service  # noqa: PLC0415
    from app.services.transcricao_audio import resumir_reuniao, transcrever_audio  # noqa: PLC0415
    from app.workers.ocr_tasks import emit_leitura_event  # noqa: PLC0415

    db = SessionLocal()
    try:
        doc = (
            db.query(Document)
            .filter(Document.id == doc_id, Document.tenant_id == tenant_id)
            .first()
        )
        if not doc:
            logger.warning(
                "transcribe_audio_document: doc %s não encontrado para tenant %s",
                doc_id, tenant_id,
            )
            return {"status": "not_found", "doc_id": doc_id}

        # 1) Cache self — já transcrito (force=True bypassa para re-transcrever)
        if (doc.extracted_text or "").strip() and not force:
            logger.info(
                "transcribe_audio_document: doc=%s cache_hit_self chars=%d",
                doc_id, len(doc.extracted_text),
            )
            emit_leitura_event(
                publish_realtime_event, tenant_id, doc,
                status_label="completed", method="cache_self",
                chars=len(doc.extracted_text), cost_usd=0.0,
            )
            return {
                "status": "cache_hit_self",
                "doc_id": doc_id,
                "chars": len(doc.extracted_text),
            }

        doc.ocr_status = OcrStatus.processing
        doc.ocr_error = None
        db.add(doc)
        db.commit()

        # 2) Download dos bytes
        storage = get_storage_service()
        try:
            audio_bytes = storage.download_bytes(doc.storage_key)
        except StorageDownloadError as exc:
            doc.ocr_status = OcrStatus.failed
            doc.ocr_error = f"Falha ao baixar o áudio do storage ({exc.code}). Tente reprocessar."
            db.add(doc)
            db.commit()
            logger.error(
                "transcribe_audio_document: storage_key=%s erro de download [%s]: %s",
                doc.storage_key, exc.code, exc,
            )
            emit_leitura_event(
                publish_realtime_event, tenant_id, doc,
                status_label="failed", method="none",
                chars=0, cost_usd=0.0, error=f"storage_error:{exc.code}",
            )
            return {"status": "storage_error", "doc_id": doc_id, "code": exc.code}

        if not audio_bytes:
            doc.ocr_status = OcrStatus.failed
            doc.ocr_error = (
                "Áudio não encontrado no storage (pode ter falhado no upload). "
                "Reenvie a gravação."
            )
            db.add(doc)
            db.commit()
            emit_leitura_event(
                publish_realtime_event, tenant_id, doc,
                status_label="failed", method="none",
                chars=0, cost_usd=0.0, error="no_bytes",
            )
            return {"status": "no_bytes", "doc_id": doc_id}

        checksum = compute_sha256(audio_bytes)
        if not doc.checksum_sha256:
            doc.checksum_sha256 = checksum
            db.add(doc)
            db.commit()

        # 3) Cache twin — o mesmo áudio subido no rascunho e de novo no caso não
        # paga transcrição duas vezes.
        twin = None
        if not force:
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
            doc.ocr_error = None
            doc.confidence_score = twin.confidence_score
            db.add(doc)
            db.commit()
            logger.info(
                "transcribe_audio_document: doc=%s cache_hit_twin twin=%s chars=%d",
                doc_id, twin.id, len(twin.extracted_text),
            )
            emit_leitura_event(
                publish_realtime_event, tenant_id, doc,
                status_label="completed", method="cache_twin",
                chars=len(twin.extracted_text), cost_usd=0.0, twin_id=twin.id,
            )
            return {
                "status": "cache_hit_twin",
                "doc_id": doc_id,
                "twin_id": twin.id,
                "chars": len(twin.extracted_text),
            }

        # 4) Budget guard — antes de gastar
        try:
            check_tenant_monthly_budget(tenant_id, db)
        except Exception as exc:
            doc.ocr_status = OcrStatus.failed
            doc.ocr_error = "Orçamento mensal de IA do escritório esgotado — transcrição não executada."
            db.add(doc)
            db.commit()
            logger.warning(
                "transcribe_audio_document: budget guard rejeitou tenant=%s doc=%s: %s",
                tenant_id, doc_id, exc,
            )
            emit_leitura_event(
                publish_realtime_event, tenant_id, doc,
                status_label="skipped_budget", method="none",
                chars=0, cost_usd=0.0, error=str(exc),
            )
            return {"status": "budget_exceeded", "doc_id": doc_id, "error": str(exc)}

        # 5) Transcrição. BYOK: se o consultor configurou chave própria, a
        # transcrição sai na conta dele — mesma regra dos demais agentes.
        prefs = _preferencias_ia(db, tenant_id=tenant_id, user_id=user_id)
        started_at = datetime.now(UTC)
        result = transcrever_audio(
            audio_bytes,
            filename=doc.original_file_name or doc.filename or "audio",
            mime_type=doc.content_type or doc.mime_type,
            user_preferences=prefs,
        )

        # 6) GANCHO do resumo estruturado (decisão 3a da Isis, pendente). Desligado
        # por default: esta rodada entrega a transcrição BRUTA. Falha aqui NUNCA
        # derruba a transcrição — o resumo é acréscimo.
        custo_resumo = 0.0
        texto_final = result.text
        if result.text and settings.AUDIO_TRANSCRICAO_RESUMO_ENABLED:
            bloco, custo_resumo = resumir_reuniao(result.text, user_preferences=prefs)
            if bloco:
                texto_final = f"{bloco}\n\n---\n\n{result.text}"

        finished_at = datetime.now(UTC)
        custo_total = result.cost_usd + custo_resumo

        # 7) AIJob (audit + custo). `job_type=extract_document` porque é o mesmo
        # ato do ponto de vista do caso: extrair o texto de um arquivo anexado.
        ai_job = AIJob(
            tenant_id=tenant_id,
            created_by_user_id=user_id,
            entity_type="document",
            entity_id=doc.id,
            job_type=AIJobType.extract_document,
            status=AIJobStatus.completed if texto_final else AIJobStatus.failed,
            agent_name="transcricao_audio",
            model_used=result.model_used or None,
            provider=result.provider or None,
            # cost_usd=0.0 é "custo conhecido e zero" (ex.: falhou antes de gastar);
            # `or None` colapsaria isso em "desconhecido" e quebraria a agregação.
            cost_usd=custo_total,
            duration_ms=result.duration_ms or None,
            input_payload={
                "doc_id": doc.id,
                "method": result.method,
                "checksum": checksum,
                "size_bytes": len(audio_bytes),
                "content_type": doc.content_type,
                "audio_seconds": round(result.audio_seconds, 2),
                "duracao_fonte": result.duracao_fonte,
                "resumo_habilitado": bool(settings.AUDIO_TRANSCRICAO_RESUMO_ENABLED),
            },
            result={
                "method": result.method,
                "chars": len(texto_final),
                "audio_seconds": round(result.audio_seconds, 2),
                "custo_transcricao_usd": result.cost_usd,
                "custo_resumo_usd": custo_resumo,
                "text_preview": (texto_final or "")[:500],
            },
            error=result.error,
            started_at=started_at,
            finished_at=finished_at,
        )
        db.add(ai_job)

        if texto_final:
            doc.extracted_text = texto_final
            doc.extracted_at = finished_at
            doc.ocr_status = OcrStatus.done
            doc.ocr_error = None
            # Transcrição de fala espontânea erra nome próprio, número e sigla com
            # frequência bem maior que um PDF digital. 0.70 alinha com o patamar do
            # OCR por visão e sinaliza "confira antes de tratar como fato".
            doc.confidence_score = 0.70
        else:
            doc.ocr_status = OcrStatus.failed
            doc.ocr_error = (result.error or "A transcrição não produziu texto.")[:500]

        db.add(doc)
        db.commit()

        logger.info(
            "transcribe_audio_document: doc=%s method=%s chars=%d audio_s=%.1f (%s) "
            "cost_usd=%.6f ms=%d ai_job=%s",
            doc_id, result.method, len(texto_final), result.audio_seconds,
            result.duracao_fonte, custo_total, result.duration_ms, ai_job.id,
        )

        emit_leitura_event(
            publish_realtime_event, tenant_id, doc,
            status_label="completed" if texto_final else "failed",
            method=result.method,
            chars=len(texto_final),
            cost_usd=custo_total,
            ai_job_id=ai_job.id,
            error=result.error if not texto_final else None,
        )

        return {
            "status": "transcricao_ok" if texto_final else "transcricao_falhou",
            "doc_id": doc_id,
            "method": result.method,
            "chars": len(texto_final),
            "audio_seconds": result.audio_seconds,
            "cost_usd": custo_total,
            "ai_job_id": ai_job.id,
        }

    except Exception as exc:
        db.rollback()
        logger.exception("transcribe_audio_document: doc=%s falhou: %s", doc_id, exc)
        try:
            # self.retry() levanta Retry, que DEVE propagar — engoli-la deixaria o
            # documento preso em 'processing' para sempre.
            raise self.retry(exc=exc, countdown=30)
        except MaxRetriesExceededError:
            from app.workers.ocr_tasks import mark_leitura_failed as _mark  # noqa: PLC0415
            _mark(doc_id, tenant_id, f"Transcrição falhou após novas tentativas: {exc}")
            return {"status": "error", "doc_id": doc_id, "error": str(exc)}
    finally:
        db.close()
