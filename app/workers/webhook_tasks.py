"""
Webhook alert delivery with Celery retry — Sprint 7

Replaces the synchronous fire-and-forget dispatch in app/core/alerts.py
with an async task that retries with exponential backoff.
"""

import logging

import httpx

from app.core.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(
    name="workers.send_webhook_alert",
    bind=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=120,
    soft_time_limit=30,
)
def send_webhook_alert(
    self,
    url: str,
    raw_payload_hex: str,
    headers: dict,
):
    """Envia webhook de alerta operacional com retry exponencial via Celery."""
    raw_payload = bytes.fromhex(raw_payload_hex)
    try:
        with httpx.Client(timeout=settings.ALERT_WEBHOOK_TIMEOUT_SECONDS) as client:
            response = client.post(url, content=raw_payload, headers=headers)
            response.raise_for_status()
        logger.info("Webhook enviado com sucesso: %s status=%d", url, response.status_code)
        return {"status": "success", "status_code": response.status_code}
    except Exception as exc:
        logger.warning(
            "Webhook falhou (tentativa %d/%d): %s — %s",
            self.request.retries + 1,
            self.max_retries + 1,
            url,
            exc,
        )
        raise self.retry(exc=exc)
