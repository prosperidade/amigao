"""
Centralised AIJob persistence helper.

Accepts an optional external SQLAlchemy session.  When no session is provided
it creates (and closes) its own via ``SessionLocal``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.ai_job import AIJob, AIJobStatus, AIJobType

logger = logging.getLogger(__name__)


def persist_ai_job(
    *,
    tenant_id: int,
    job_type: AIJobType,
    input_payload: dict[str, Any],
    result: dict[str, Any],
    raw_output: str,
    model_used: Optional[str] = None,
    provider: Optional[str] = None,
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
    cost_usd: Optional[float] = None,
    duration_ms: Optional[int] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    status: AIJobStatus = AIJobStatus.completed,
    db: Optional[Session] = None,
) -> Optional[int]:
    """Persist an AIJob and return its id, or ``None`` on failure.

    Parameters
    ----------
    db : Session, optional
        When provided the caller owns the transaction (no commit/close here).
        When ``None`` a fresh ``SessionLocal`` is created, committed and closed.
    """
    owns_session = db is None
    try:
        if owns_session:
            from app.db.session import SessionLocal  # noqa: PLC0415
            db = SessionLocal()

        now = datetime.now(UTC)
        job = AIJob(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            job_type=job_type,
            status=status,
            model_used=model_used,
            provider=provider,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            duration_ms=duration_ms,
            input_payload=input_payload,
            result=result,
            raw_output=raw_output,
            started_at=now,
            finished_at=now,
        )
        db.add(job)
        if owns_session:
            db.commit()
            db.refresh(job)
        else:
            db.flush()
        return job.id
    except Exception as exc:
        logger.warning("persist_ai_job: falha ao persistir AIJob: %s", exc)
        if owns_session and db is not None:
            db.rollback()
        return None
    finally:
        if owns_session and db is not None:
            db.close()
