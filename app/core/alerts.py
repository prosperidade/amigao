import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from app.core.config import settings
from app.core.logging import request_id_ctx
from app.core.metrics import record_alert
from app.core.tracing import build_traceparent, current_trace_context, parse_traceparent

logger = logging.getLogger(__name__)

_WEBHOOK_ALERT_ID_HEADER = "X-Amigao-Alert-Id"
_WEBHOOK_SERVICE_HEADER = "X-Amigao-Service"
_WEBHOOK_ENVIRONMENT_HEADER = "X-Amigao-Environment"
_WEBHOOK_SIGNATURE_HEADER = "X-Amigao-Signature-256"

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


def _build_webhook_payload(*, category: str, severity: str, message: str, metadata: dict | None) -> tuple[dict, str]:
    trace_context = current_trace_context()
    traceparent = build_traceparent(trace_context["trace_id"], trace_context["span_id"])
    normalized_trace_id, normalized_span_id = parse_traceparent(traceparent)
    payload = {
        "alert_id": str(uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "service": settings.SERVICE_NAME,
        "environment": settings.ENVIRONMENT,
        "category": category,
        "severity": severity,
        "message": message,
        "request_id": request_id_ctx.get("-"),
        "trace_id": normalized_trace_id or trace_context["trace_id"],
        "span_id": normalized_span_id or trace_context["span_id"],
        "metadata": metadata or {},
    }
    return payload, traceparent


def _serialize_webhook_payload(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")


def _build_webhook_signature(raw_payload: bytes) -> str:
    secret = settings.alert_webhook_signing_secret
    if not secret:
        return ""
    digest = hmac.new(secret.encode("utf-8"), raw_payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _build_webhook_headers(*, payload: dict, raw_payload: bytes, traceparent: str) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        _WEBHOOK_ALERT_ID_HEADER: payload["alert_id"],
        _WEBHOOK_SERVICE_HEADER: payload["service"],
        _WEBHOOK_ENVIRONMENT_HEADER: payload["environment"],
        "traceparent": traceparent,
    }
    if settings.alert_webhook_auth_token:
        headers[settings.alert_webhook_auth_header] = settings.alert_webhook_auth_token
    signature = _build_webhook_signature(raw_payload)
    if signature:
        headers[_WEBHOOK_SIGNATURE_HEADER] = signature
    return headers


def _dispatch_webhook(*, category: str, severity: str, message: str, metadata: dict | None) -> None:
    if not _should_dispatch_webhook(severity):
        return

    payload, traceparent = _build_webhook_payload(
        category=category,
        severity=severity,
        message=message,
        metadata=metadata,
    )
    raw_payload = _serialize_webhook_payload(payload)
    headers = _build_webhook_headers(payload=payload, raw_payload=raw_payload, traceparent=traceparent)

    # Dispatch via Celery task with retry (instead of synchronous fire-and-forget)
    try:
        from app.workers.webhook_tasks import send_webhook_alert
        send_webhook_alert.delay(
            url=settings.ALERT_WEBHOOK_URL,
            raw_payload_hex=raw_payload.hex(),
            headers=headers,
        )
    except Exception as exc:
        # Fallback: if Celery broker is unreachable, log and move on
        logger.warning(
            "Falha ao enfileirar webhook de alerta no Celery",
            extra={
                "action": "operational.alert.webhook_enqueue_failed",
                "metadata": {
                    "category": category,
                    "severity": severity,
                    "alert_id": payload["alert_id"],
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
