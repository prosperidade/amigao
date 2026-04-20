"""
Tasks Celery do fluxo de Intake/Cadastro.

Regente Sprint F Bloco 3 — decisão sócia 2026-04-19:
rascunhos de cadastro (IntakeDraft) expiram em 15 dias após a última edição
e são limpos 1x/dia por esta task.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.intake_draft import IntakeDraft, IntakeDraftState

logger = logging.getLogger(__name__)


@celery_app.task(
    name="workers.cleanup_expired_intake_drafts",
    bind=True,
    max_retries=3,
    retry_backoff=True,
)
def cleanup_expired_intake_drafts(self) -> dict:
    """Remove rascunhos expirados (expires_at < now).

    Regras:
      - só toca drafts em estado `rascunho` ou `pronto_para_criar`
      - drafts em estado `card_criado` ou `base_complementada` nunca são deletados
        (já viraram processo; expires_at deles é NULL via backfill)
    """
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        expired = (
            db.query(IntakeDraft)
            .filter(
                IntakeDraft.expires_at.isnot(None),
                IntakeDraft.expires_at < now,
                IntakeDraft.state.in_(
                    [IntakeDraftState.rascunho, IntakeDraftState.pronto_para_criar]
                ),
            )
            .all()
        )
        count = len(expired)
        for draft in expired:
            db.delete(draft)
        db.commit()
        logger.info("cleanup_expired_intake_drafts: removidos %d rascunho(s)", count)
        return {"deleted": count, "at": now.isoformat()}
    except Exception as exc:
        db.rollback()
        logger.exception("cleanup_expired_intake_drafts falhou: %s", exc)
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()
