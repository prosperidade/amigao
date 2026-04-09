"""
LegislationMonitor — orquestrador do ciclo de monitoramento.

Fluxo: crawl → dedup → ingest → match processos ativos → criar alertas.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.legislation import LegislationDocument
from app.models.legislation_alert import LegislationAlert
from app.models.process import Process, ProcessStatus
from app.services.crawlers.base_crawler import CrawledDocument, get_crawler, list_crawlers
from app.services.legislation_service import ingest_legislation_document

logger = logging.getLogger(__name__)


@dataclass
class MonitoringResult:
    crawler_name: str
    documents_found: int
    documents_new: int
    documents_skipped: int
    alerts_created: int
    errors: list[str]


def run_monitoring_cycle(
    db: Session,
    *,
    crawler_name: Optional[str] = None,
) -> list[MonitoringResult]:
    """
    Executa ciclo completo de monitoramento.
    Se crawler_name e None, roda todos os crawlers registrados.
    """
    names = [crawler_name] if crawler_name else list_crawlers()
    results: list[MonitoringResult] = []

    for name in names:
        result = _run_single_crawler(db, name)
        results.append(result)
        db.commit()

    total_new = sum(r.documents_new for r in results)
    total_alerts = sum(r.alerts_created for r in results)
    logger.info(
        "monitoramento completo: %d crawlers, %d docs novos, %d alertas",
        len(results), total_new, total_alerts,
    )
    return results


def _run_single_crawler(db: Session, crawler_name: str) -> MonitoringResult:
    """Executa um crawler individual e processa resultados."""
    errors: list[str] = []

    try:
        crawler = get_crawler(crawler_name)
    except ValueError as exc:
        return MonitoringResult(
            crawler_name=crawler_name,
            documents_found=0, documents_new=0, documents_skipped=0,
            alerts_created=0, errors=[str(exc)],
        )

    crawled_docs = crawler.safe_crawl()
    new_count = 0
    skipped = 0
    alerts_count = 0

    for cdoc in crawled_docs:
        try:
            # Dedup: verificar se documento ja existe
            existing = _find_existing(db, cdoc)
            if existing:
                # Verificar se conteudo mudou
                if existing.content_hash == cdoc.content_hash:
                    skipped += 1
                    continue
                # Conteudo mudou — atualizar
                existing.full_text = cdoc.content
                ingest_legislation_document(existing.id, db, raw_text=cdoc.content)
                alerts_count += _create_alerts_for_document(db, existing, "updated")
                new_count += 1
            else:
                # Novo documento
                doc = LegislationDocument(
                    tenant_id=None,
                    title=cdoc.title,
                    source_type=cdoc.source_type,
                    identifier=cdoc.identifier,
                    uf=cdoc.uf,
                    scope=cdoc.scope,
                    agency=cdoc.agency,
                    effective_date=None,
                    url=cdoc.source_url,
                    demand_types=cdoc.demand_types or None,
                    keywords=cdoc.keywords or None,
                    status="pending",
                )
                db.add(doc)
                db.flush()

                ingest_legislation_document(doc.id, db, raw_text=cdoc.content)
                alerts_count += _create_alerts_for_document(db, doc, "new_legislation")
                new_count += 1

        except Exception as exc:
            errors.append(f"{cdoc.identifier}: {exc}")
            logger.warning("Erro ingerindo doc '%s': %s", cdoc.identifier, exc)

    return MonitoringResult(
        crawler_name=crawler_name,
        documents_found=len(crawled_docs),
        documents_new=new_count,
        documents_skipped=skipped,
        alerts_created=alerts_count,
        errors=errors,
    )


def _find_existing(db: Session, cdoc: CrawledDocument) -> Optional[LegislationDocument]:
    """Busca documento existente por identifier + scope."""
    if not cdoc.identifier:
        return None
    return (
        db.query(LegislationDocument)
        .filter(
            LegislationDocument.identifier == cdoc.identifier,
            LegislationDocument.scope == cdoc.scope,
        )
        .first()
    )


def _create_alerts_for_document(
    db: Session,
    doc: LegislationDocument,
    alert_type: str,
) -> int:
    """Cria alertas para processos ativos que podem ser afetados pela nova legislacao."""
    # Buscar processos ativos que matcham por UF + demand_type
    q = (
        db.query(Process)
        .filter(
            Process.deleted_at.is_(None),
            Process.status.notin_([
                ProcessStatus.cancelado,
                ProcessStatus.arquivado,
                ProcessStatus.concluido,
            ]),
        )
    )

    # Filtrar por UF se legislacao e estadual
    if doc.uf:
        from app.models.property import Property
        q = q.join(Property, Process.property_id == Property.id).filter(
            Property.state == doc.uf
        )

    processes = q.limit(100).all()
    count = 0

    for process in processes:
        # Verificar match de demand_type
        if doc.demand_types and process.demand_type:
            if process.demand_type.value not in doc.demand_types:
                continue

        alert = LegislationAlert(
            tenant_id=process.tenant_id,
            process_id=process.id,
            document_id=doc.id,
            alert_type=alert_type,
            severity="info" if alert_type == "new_legislation" else "warning",
            message=_build_alert_message(doc, alert_type),
        )
        db.add(alert)
        count += 1

    if count:
        db.flush()
        logger.info("Criados %d alertas para doc '%s' (%s)", count, doc.identifier, alert_type)

    return count


def _build_alert_message(doc: LegislationDocument, alert_type: str) -> str:
    """Monta mensagem descritiva do alerta."""
    scope_label = {"federal": "Federal", "estadual": f"Estadual ({doc.uf})", "municipal": "Municipal"}
    scope = scope_label.get(doc.scope, doc.scope)

    if alert_type == "new_legislation":
        return f"Nova legislação {scope}: {doc.identifier or doc.title}. Verifique se impacta o caminho regulatório deste caso."
    if alert_type == "updated":
        return f"Legislação atualizada {scope}: {doc.identifier or doc.title}. O conteúdo foi alterado — revise o enquadramento."
    return f"Alerta legislativo: {doc.identifier or doc.title}"
