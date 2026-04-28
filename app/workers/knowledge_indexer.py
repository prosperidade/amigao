"""Celery tasks para popular o knowledge_catalog (Sprint U).

- `index_legislation_document_task(doc_id)`: re-indexa um documento.
- `reindex_all_legislation()`: dispara um task por documento `indexed`.
- `index_arbitrary_text_task(...)`: indexa texto avulso (oficio, manual).
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.legislation import LegislationDocument, LegislationStatus

logger = logging.getLogger(__name__)


@celery_app.task(
    name="workers.knowledge.index_legislation_document",
    max_retries=3,
    retry_backoff=True,
    soft_time_limit=300,
    time_limit=600,
)
def index_legislation_document_task(doc_id: int) -> dict[str, Any]:
    """Indexa um LegislationDocument no knowledge_catalog."""
    from app.services.knowledge_catalog import index_legislation_document

    db = SessionLocal()
    try:
        inserted = index_legislation_document(db, doc_id)
        db.commit()
        logger.info("knowledge.indexer doc=%d inserted=%d", doc_id, inserted)
        return {"doc_id": doc_id, "inserted": inserted}
    except Exception as exc:
        db.rollback()
        logger.exception("knowledge.indexer doc=%d falhou: %s", doc_id, exc)
        raise
    finally:
        db.close()


@celery_app.task(
    name="workers.knowledge.reindex_all_legislation",
    max_retries=1,
    soft_time_limit=120,
)
def reindex_all_legislation() -> dict[str, Any]:
    """Enfileira um task de indexacao para cada documento indexed.

    Idempotente: o service de indexacao salta chunks com content_hash repetido.
    """
    db = SessionLocal()
    try:
        ids = [
            row.id
            for row in db.query(LegislationDocument.id)
            .filter(LegislationDocument.status == LegislationStatus.indexed.value)
            .filter(LegislationDocument.full_text.isnot(None))
            .all()
        ]
    finally:
        db.close()

    for doc_id in ids:
        index_legislation_document_task.delay(doc_id)

    logger.info("knowledge.reindex_all enfileirados=%d", len(ids))
    return {"queued": len(ids), "doc_ids": ids[:50]}


@celery_app.task(
    name="workers.knowledge.index_arbitrary_text",
    max_retries=3,
    retry_backoff=True,
    soft_time_limit=300,
    time_limit=600,
)
def index_arbitrary_text_task(
    *,
    source_type: str,
    source_ref: str,
    body: str,
    title: str | None = None,
    tenant_id: int | None = None,
    jurisdiction: str | None = None,
    uf: str | None = None,
    agency: str | None = None,
    identifier: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Indexa texto avulso (oficio, manual, jurisprudencia)."""
    from app.services.knowledge_catalog import index_text

    db = SessionLocal()
    try:
        inserted = index_text(
            db,
            source_type=source_type,
            source_ref=source_ref,
            body=body,
            title=title,
            tenant_id=tenant_id,
            jurisdiction=jurisdiction,
            uf=uf,
            agency=agency,
            identifier=identifier,
            extra_metadata=extra_metadata,
        )
        db.commit()
        return {
            "source_type": source_type,
            "source_ref": source_ref,
            "inserted": inserted,
        }
    except Exception as exc:
        db.rollback()
        logger.exception(
            "knowledge.index_arbitrary source=%s ref=%s falhou: %s",
            source_type, source_ref, exc,
        )
        raise
    finally:
        db.close()
