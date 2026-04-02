import hashlib
import hmac
import json
import logging

import httpx

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
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            captured["timeout"] = kwargs.get("timeout")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def post(self, url: str, *, content: bytes, headers: dict[str, str]):
            captured["url"] = url
            captured["content"] = content
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr(alerts.httpx, "Client", FakeClient)
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

    payload = json.loads(captured["content"].decode("utf-8"))
    headers = captured["headers"]

    assert captured["url"] == "https://alerts.example/webhook"
    assert captured["timeout"] == 4.5
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
        captured["content"],
        hashlib.sha256,
    ).hexdigest()


def test_dispatch_webhook_logs_failure_metadata(monkeypatch, caplog) -> None:
    class FailingClient:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def post(self, url: str, *, content: bytes, headers: dict[str, str]):
            raise httpx.ConnectError("network down")

    monkeypatch.setattr(alerts.httpx, "Client", FailingClient)
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

    records = [record for record in caplog.records if getattr(record, "action", "") == "operational.alert.webhook_failed"]

    assert len(records) == 1
    metadata = records[0].metadata
    assert metadata["category"] == "email_delivery"
    assert metadata["severity"] == "error"
    assert metadata["auth_enabled"] is False
    assert metadata["signature_enabled"] is False
    assert metadata["error"] == "network down"
    assert metadata["alert_id"]
