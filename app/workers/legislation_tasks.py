"""
Celery tasks para monitoramento de legislacao.

- monitor_legislation: ciclo completo (todos os crawlers)
- monitor_legislation_dou: apenas DOU federal
- monitor_legislation_agencies: IBAMA e orgaos federais
- ingest_single_document: processar um documento especifico
"""

from __future__ import annotations

import logging

from app.core.celery_app import celery_app
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(
    name="workers.monitor_legislation",
    max_retries=1,
    soft_time_limit=600,
    time_limit=900,
)
def monitor_legislation(crawler_name: str | None = None) -> dict:
    """Executa ciclo de monitoramento de legislacao."""
    from app.services.legislation_monitor import run_monitoring_cycle

    db = SessionLocal()
    try:
        results = run_monitoring_cycle(db, crawler_name=crawler_name)
        summary = {
            "crawlers": len(results),
            "total_found": sum(r.documents_found for r in results),
            "total_new": sum(r.documents_new for r in results),
            "total_alerts": sum(r.alerts_created for r in results),
            "errors": sum(len(r.errors) for r in results),
            "details": [
                {
                    "crawler": r.crawler_name,
                    "found": r.documents_found,
                    "new": r.documents_new,
                    "skipped": r.documents_skipped,
                    "alerts": r.alerts_created,
                    "errors": r.errors[:5],
                }
                for r in results
            ],
        }
        logger.info("monitor_legislation completo: %s", summary)
        return summary
    except Exception as exc:
        logger.exception("monitor_legislation falhou: %s", exc)
        raise
    finally:
        db.close()


@celery_app.task(
    name="workers.monitor_legislation_dou",
    max_retries=1,
    soft_time_limit=300,
)
def monitor_legislation_dou() -> dict:
    """Monitora apenas DOU federal (diario)."""
    return monitor_legislation(crawler_name="dou")


@celery_app.task(
    name="workers.monitor_legislation_doe",
    max_retries=1,
    soft_time_limit=600,
)
def monitor_legislation_doe() -> dict:
    """Monitora DOEs de todos os 27 estados (diario)."""
    return monitor_legislation(crawler_name="doe")


@celery_app.task(
    name="workers.monitor_legislation_agencies",
    max_retries=1,
    soft_time_limit=300,
)
def monitor_legislation_agencies() -> dict:
    """Monitora IBAMA e orgaos federais (semanal)."""
    return monitor_legislation(crawler_name="ibama")


@celery_app.task(
    name="workers.ingest_legislation_document",
    max_retries=2,
    soft_time_limit=120,
)
def ingest_legislation_document_task(doc_id: int) -> dict:
    """Processa um documento legislativo especifico em background."""
    from app.services.legislation_service import ingest_legislation_document

    db = SessionLocal()
    try:
        doc = ingest_legislation_document(doc_id, db)
        db.commit()
        return {"doc_id": doc.id, "status": doc.status, "token_count": doc.token_count}
    except Exception as exc:
        db.rollback()
        logger.exception("ingest_legislation_document falhou para doc %d: %s", doc_id, exc)
        raise
    finally:
        db.close()
