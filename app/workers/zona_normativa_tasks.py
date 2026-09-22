"""Conferência periódica dos originais normativos (ADR-075 adendo A5).

Recalcula o hash dos bytes originais guardados no storage e compara com o que a
versão registrou. Divergência bloqueia a versão para citação e abre tarefa de
revisão — "fonte normativa adulterada" é zero tolerância. Catálogo vazio é no-op.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.celery_app import celery_app
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(
    name="workers.zona_normativa.conferir_originais",
    max_retries=3,
    retry_backoff=True,
    soft_time_limit=900,
    time_limit=1200,
)
def conferir_originais_normativos() -> dict[str, Any]:
    from app.services.storage import get_storage_service  # noqa: PLC0415
    from app.services.zona_normativa.integridade import conferir_originais  # noqa: PLC0415

    db = SessionLocal()
    try:
        out = conferir_originais(db, get_storage_service())
        db.commit()
        nivel = logging.ERROR if (out["divergentes"] or out["ausentes"]) else logging.INFO
        logger.log(nivel, "zona_normativa.conferencia_originais %s", out)
        return out
    except Exception:
        db.rollback()
        logger.exception("zona_normativa.conferencia_originais falhou")
        raise
    finally:
        db.close()
