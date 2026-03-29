from app.core import metrics


class FakeMetricsRedis:
    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.hashes.get(key, {}))

    def hincrbyfloat(self, key: str, field: str, amount: float) -> float:
        bucket = self.hashes.setdefault(key, {})
        updated = float(bucket.get(field, "0")) + float(amount)
        bucket[field] = str(updated)
        return updated

    def hincrby(self, key: str, field: str, amount: int) -> int:
        bucket = self.hashes.setdefault(key, {})
        updated = int(float(bucket.get(field, "0"))) + int(amount)
        bucket[field] = str(updated)
        return updated

    def pipeline(self):
        return self

    def execute(self) -> list[object]:
        return []


def _clear_metric_state(*metric_objects) -> None:
    for metric_object in metric_objects:
        metric_object._values.clear()


def test_metrics_endpoint_exposes_http_metrics(client):
    health_response = client.get("/health")
    assert health_response.status_code == 200

    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    assert "amigao_http_requests_total" in metrics_response.text
    assert "amigao_http_request_duration_seconds" in metrics_response.text


def test_metrics_endpoint_includes_shared_worker_metrics(client, monkeypatch):
    fake_redis = FakeMetricsRedis()
    monkeypatch.setattr(metrics, "_shared_metrics_client", lambda: fake_redis)
    monkeypatch.setattr(metrics.settings, "SERVICE_NAME", "worker")

    _clear_metric_state(
        metrics.CELERY_TASKS_TOTAL,
        metrics.CELERY_TASK_DURATION_SECONDS,
        metrics.ALERTS_TOTAL,
        metrics.EMAIL_DELIVERY_TOTAL,
    )

    metrics.record_celery_task("workers.send_email_notification", "success", 0.42)
    metrics.record_alert("email_delivery", "error")
    metrics.record_email_delivery("success")

    _clear_metric_state(
        metrics.CELERY_TASKS_TOTAL,
        metrics.CELERY_TASK_DURATION_SECONDS,
        metrics.ALERTS_TOTAL,
        metrics.EMAIL_DELIVERY_TOTAL,
    )
    monkeypatch.setattr(metrics.settings, "SERVICE_NAME", "api")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert (
        'amigao_celery_tasks_total{service="worker",task_name="workers.send_email_notification",state="success"} 1.0'
        in response.text
    )
    assert (
        'amigao_celery_task_duration_seconds_sum{service="worker",task_name="workers.send_email_notification"} 0.42'
        in response.text
    )
    assert 'amigao_alerts_total{service="worker",category="email_delivery",severity="error"} 1.0' in response.text
    assert 'amigao_email_delivery_total{service="worker",result="success"} 1.0' in response.text
