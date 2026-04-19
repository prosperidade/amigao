import hashlib
import hmac
import json
import logging
from unittest.mock import MagicMock

from app.core import alerts
from app.core.logging import request_id_ctx
from app.core.tracing import reset_trace_context, set_trace_context


def test_should_dispatch_webhook_respects_min_severity(monkeypatch) -> None:
    monkeypatch.setattr(alerts.settings, "ALERT_WEBHOOK_URL", "https://alerts.example/webhook")
    monkeypatch.setattr(alerts.settings, "ALERT_WEBHOOK_MIN_SEVERITY", "error")

    assert alerts._should_dispatch_webhook("warning") is False
    assert alerts._should_dispatch_webhook("error") is True
    assert alerts._should_dispatch_webhook("critical") is True


def test_dispatch_webhook_sends_auth_signature_and_traceparent(monkeypatch) -> None:
    """Verify that _dispatch_webhook enqueues a Celery task with correct payload and headers."""
    captured: dict[str, object] = {}

    mock_delay = MagicMock(side_effect=lambda **kwargs: captured.update(kwargs))

    import app.workers.webhook_tasks as wt
    monkeypatch.setattr(wt.send_webhook_alert, "delay", mock_delay)

    monkeypatch.setattr(alerts.settings, "ALERT_WEBHOOK_URL", "https://alerts.example/webhook")
    monkeypatch.setattr(alerts.settings, "ALERT_WEBHOOK_TIMEOUT_SECONDS", 4.5)
    monkeypatch.setattr(alerts.settings, "ALERT_WEBHOOK_MIN_SEVERITY", "warning")
    monkeypatch.setattr(alerts.settings, "ALERT_WEBHOOK_AUTH_HEADER", "Authorization")
    monkeypatch.setattr(alerts.settings, "ALERT_WEBHOOK_AUTH_TOKEN", "Bearer webhook-token")
    monkeypatch.setattr(alerts.settings, "ALERT_WEBHOOK_SIGNING_SECRET", "signing-secret")

    request_token = request_id_ctx.set("req-123")
    trace_token, span_token, _, _ = set_trace_context(
        trace_id="a" * 32,
        span_id="b" * 16,
    )
    try:
        alerts._dispatch_webhook(
            category="smoke_test",
            severity="warning",
            message="Webhook hardening smoke",
            metadata={"source": "pytest"},
        )
    finally:
        request_id_ctx.reset(request_token)
        reset_trace_context(trace_token, span_token)

    mock_delay.assert_called_once()
    assert captured["url"] == "https://alerts.example/webhook"

    raw_payload = bytes.fromhex(captured["raw_payload_hex"])
    payload = json.loads(raw_payload.decode("utf-8"))
    headers = captured["headers"]

    assert payload["category"] == "smoke_test"
    assert payload["severity"] == "warning"
    assert payload["message"] == "Webhook hardening smoke"
    assert payload["request_id"] == "req-123"
    assert payload["trace_id"] == "a" * 32
    assert payload["span_id"] == "b" * 16
    assert payload["metadata"] == {"source": "pytest"}
    assert payload["alert_id"]
    assert headers["Authorization"] == "Bearer webhook-token"
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert headers["X-Amigao-Alert-Id"] == payload["alert_id"]
    assert headers["X-Amigao-Service"] == alerts.settings.SERVICE_NAME
    assert headers["X-Amigao-Environment"] == alerts.settings.ENVIRONMENT
    assert headers["traceparent"] == f"00-{'a' * 32}-{'b' * 16}-01"
    assert headers["X-Amigao-Signature-256"] == "sha256=" + hmac.new(
        b"signing-secret",
        raw_payload,
        hashlib.sha256,
    ).hexdigest()


def test_dispatch_webhook_logs_failure_on_enqueue_error(monkeypatch, caplog) -> None:
    """Verify that when Celery enqueue fails, a warning is logged."""
    import app.workers.webhook_tasks as wt
    monkeypatch.setattr(
        wt.send_webhook_alert, "delay",
        MagicMock(side_effect=ConnectionError("broker down")),
    )
    monkeypatch.setattr(alerts.settings, "ALERT_WEBHOOK_URL", "https://alerts.example/webhook")
    monkeypatch.setattr(alerts.settings, "ALERT_WEBHOOK_MIN_SEVERITY", "warning")
    monkeypatch.setattr(alerts.settings, "ALERT_WEBHOOK_AUTH_TOKEN", "")
    monkeypatch.setattr(alerts.settings, "ALERT_WEBHOOK_SIGNING_SECRET", "")

    with caplog.at_level(logging.WARNING):
        alerts._dispatch_webhook(
            category="email_delivery",
            severity="error",
            message="Webhook delivery failed",
            metadata={"source": "pytest"},
        )

    records = [
        record for record in caplog.records
        if getattr(record, "action", "") == "operational.alert.webhook_enqueue_failed"
    ]

    assert len(records) == 1
    metadata = records[0].metadata
    assert metadata["category"] == "email_delivery"
    assert metadata["severity"] == "error"
    assert metadata["error"] == "broker down"
    assert metadata["alert_id"]
