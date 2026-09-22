"""Leitura geoespacial no worker (ADR-072). Falha fica gravada em ``arquivo_geo``."""
from __future__ import annotations

from app.core.celery_app import celery_app
from app.core.logging import get_logger
from app.db.session import SessionLocal

logger = get_logger(__name__)


def enfileirar_geometria(document_id: int, tenant_id: int) -> None:
    """Chamado pelos guards de upload; falha ao enfileirar não derruba o upload.

    O arquivo continua guardado e o consultor tem "Ler geometria" na tela.
    """
    try:
        processar_geometria.delay(document_id=document_id, tenant_id=tenant_id)
    except Exception as exc:  # noqa: BLE001 — broker fora do ar não pode perder o upload
        logger.warning("geometria: não enfileirou doc=%s: %s", document_id, exc)


@celery_app.task(name="workers.processar_geometria", bind=True, max_retries=3, retry_backoff=True)
def processar_geometria(self, document_id: int, tenant_id: int) -> dict:
    from app.models.document import Document
    from app.services import geometria

    with SessionLocal() as db:
        doc = db.query(Document).filter_by(id=document_id, tenant_id=tenant_id, deleted_at=None).first()
        if doc is None:
            return {"status": "not_found", "document_id": document_id}
        leitura = geometria.processar_documento(db, doc)
        if leitura.estado == "lido" and doc.process_id:
            geometria.executar_confronto(db, tenant_id, doc.process_id)
        db.commit()
        resultado = {"status": leitura.estado, "document_id": document_id, "leitura": leitura.numero,
                     "falha": leitura.falha_codigo}
    # Indisponibilidade de storage é transitória; a falha já ficou registrada.
    if resultado["falha"] == "storage_indisponivel" and self.request.retries < self.max_retries:
        raise self.retry(countdown=30)
    return resultado
