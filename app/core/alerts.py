import logging
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.core.metrics import record_alert
from app.core.logging import request_id_ctx
from app.core.tracing import current_trace_context


logger = logging.getLogger(__name__)

_SEVERITY_TO_LEVEL = {
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

_SEVERITY_RANK = {
    "info": 10,
    "warning": 20,
    "error": 30,
    "critical": 40,
}


def _should_dispatch_webhook(severity: str) -> bool:
    if not settings.ALERT_WEBHOOK_URL:
        return False
    return _SEVERITY_RANK.get(severity, 20) >= _SEVERITY_RANK.get(settings.ALERT_WEBHOOK_MIN_SEVERITY, 30)


def _dispatch_webhook(*, category: str, severity: str, message: str, metadata: dict | None) -> None:
    if not _should_dispatch_webhook(severity):
        return

    trace_context = current_trace_context()
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": settings.SERVICE_NAME,
        "environment": settings.ENVIRONMENT,
        "category": category,
        "severity": severity,
        "message": message,
        "request_id": request_id_ctx.get("-"),
        "trace_id": trace_context["trace_id"],
        "span_id": trace_context["span_id"],
        "metadata": metadata or {},
    }
    try:
        with httpx.Client(timeout=settings.ALERT_WEBHOOK_TIMEOUT_SECONDS) as client:
            response = client.post(settings.ALERT_WEBHOOK_URL, json=payload)
            response.raise_for_status()
    except Exception as exc:
        logger.warning(
            "Falha ao disparar webhook de alerta",
            extra={
                "action": "operational.alert.webhook_failed",
                "metadata": {
                    "category": category,
                    "severity": severity,
                    "error": str(exc),
                },
            },
        )


def emit_operational_alert(
    *,
    category: str,
    severity: str,
    message: str,
    metadata: dict | None = None,
) -> None:
    record_alert(category, severity)
    _dispatch_webhook(category=category, severity=severity, message=message, metadata=metadata)
    logger.log(
        _SEVERITY_TO_LEVEL.get(severity, logging.WARNING),
        message,
        extra={
            "action": "operational.alert",
            "metadata": {
                "category": category,
                "severity": severity,
                **(metadata or {}),
            },
        },
    )
