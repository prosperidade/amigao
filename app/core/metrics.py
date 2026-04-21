from __future__ import annotations

import json
from dataclasses import dataclass
from threading import Lock
from typing import Iterable, Sequence

import redis
from fastapi import Request
from fastapi.responses import PlainTextResponse

from app.core.config import settings

PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def _escape_label(value: object) -> str:
    text = str(value)
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _format_labels(label_names: Sequence[str], label_values: Sequence[object]) -> str:
    if not label_names:
        return ""
    pairs = [f'{name}="{_escape_label(value)}"' for name, value in zip(label_names, label_values)]
    return "{" + ",".join(pairs) + "}"


class _BoundCounter:
    def __init__(self, metric: CounterMetric, label_values: tuple[object, ...]):
        self.metric = metric
        self.label_values = label_values

    def inc(self, amount: float = 1.0) -> None:
        self.metric.inc(self.label_values, amount)


class _BoundGauge:
    def __init__(self, metric: GaugeMetric, label_values: tuple[object, ...]):
        self.metric = metric
        self.label_values = label_values

    def set(self, value: float) -> None:
        self.metric.set(self.label_values, value)

    def inc(self, amount: float = 1.0) -> None:
        self.metric.inc(self.label_values, amount)

    def dec(self, amount: float = 1.0) -> None:
        self.metric.dec(self.label_values, amount)


class _BoundHistogram:
    def __init__(self, metric: HistogramMetric, label_values: tuple[object, ...]):
        self.metric = metric
        self.label_values = label_values

    def observe(self, value: float) -> None:
        self.metric.observe(self.label_values, value)


class BaseMetric:
    metric_type = "untyped"

    def __init__(self, name: str, help_text: str, label_names: Sequence[str] = ()) -> None:
        self.name = name
        self.help_text = help_text
        self.label_names = tuple(label_names)
        self._lock = Lock()

    def labels(self, **labels: object):
        label_values = tuple(labels[name] for name in self.label_names)
        return self._bind(label_values)

    def _bind(self, label_values: tuple[object, ...]):
        raise NotImplementedError

    def _render_header(self) -> list[str]:
        return [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} {self.metric_type}",
        ]

    def render_lines(self) -> list[str]:
        raise NotImplementedError


class CounterMetric(BaseMetric):
    metric_type = "counter"

    def __init__(self, name: str, help_text: str, label_names: Sequence[str] = ()) -> None:
        super().__init__(name, help_text, label_names)
        self._values: dict[tuple[object, ...], float] = {}

    def _bind(self, label_values: tuple[object, ...]) -> _BoundCounter:
        return _BoundCounter(self, label_values)

    def inc(self, label_values: tuple[object, ...], amount: float = 1.0) -> None:
        with self._lock:
            self._values[label_values] = self._values.get(label_values, 0.0) + amount

    def render_lines(self) -> list[str]:
        with self._lock:
            samples = list(self._values.items())
        lines = self._render_header()
        for label_values, value in samples:
            lines.append(f"{self.name}{_format_labels(self.label_names, label_values)} {value}")
        return lines


class GaugeMetric(BaseMetric):
    metric_type = "gauge"

    def __init__(self, name: str, help_text: str, label_names: Sequence[str] = ()) -> None:
        super().__init__(name, help_text, label_names)
        self._values: dict[tuple[object, ...], float] = {}

    def _bind(self, label_values: tuple[object, ...]) -> _BoundGauge:
        return _BoundGauge(self, label_values)

    def set(self, label_values: tuple[object, ...], value: float) -> None:
        with self._lock:
            self._values[label_values] = value

    def inc(self, label_values: tuple[object, ...], amount: float = 1.0) -> None:
        with self._lock:
            self._values[label_values] = self._values.get(label_values, 0.0) + amount

    def dec(self, label_values: tuple[object, ...], amount: float = 1.0) -> None:
        with self._lock:
            self._values[label_values] = self._values.get(label_values, 0.0) - amount

    def render_lines(self) -> list[str]:
        with self._lock:
            samples = list(self._values.items())
        lines = self._render_header()
        for label_values, value in samples:
            lines.append(f"{self.name}{_format_labels(self.label_names, label_values)} {value}")
        return lines


@dataclass
class _HistogramState:
    bucket_counts: list[int]
    count: int = 0
    total_sum: float = 0.0


class HistogramMetric(BaseMetric):
    metric_type = "histogram"

    def __init__(
        self,
        name: str,
        help_text: str,
        label_names: Sequence[str] = (),
        buckets: Sequence[float] = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    ) -> None:
        super().__init__(name, help_text, label_names)
        self.buckets = tuple(buckets)
        self._values: dict[tuple[object, ...], _HistogramState] = {}

    def _bind(self, label_values: tuple[object, ...]) -> _BoundHistogram:
        return _BoundHistogram(self, label_values)

    def observe(self, label_values: tuple[object, ...], value: float) -> None:
        with self._lock:
            state = self._values.setdefault(
                label_values,
                _HistogramState(bucket_counts=[0 for _ in self.buckets]),
            )
            state.count += 1
            state.total_sum += value
            for index, bucket in enumerate(self.buckets):
                if value <= bucket:
                    state.bucket_counts[index] += 1

    def render_lines(self) -> list[str]:
        with self._lock:
            samples = list(self._values.items())
        lines = self._render_header()
        for label_values, state in samples:
            for bucket, count in zip(self.buckets, state.bucket_counts):
                labels = self.label_names + ("le",)
                values = label_values + (bucket,)
                lines.append(f"{self.name}_bucket{_format_labels(labels, values)} {count}")
            labels = self.label_names + ("le",)
            values = label_values + ("+Inf",)
            lines.append(f"{self.name}_bucket{_format_labels(labels, values)} {state.count}")
            lines.append(f"{self.name}_sum{_format_labels(self.label_names, label_values)} {state.total_sum}")
            lines.append(f"{self.name}_count{_format_labels(self.label_names, label_values)} {state.count}")
        return lines


HTTP_REQUESTS_TOTAL = CounterMetric(
    "amigao_http_requests_total",
    "Total de requests HTTP processados",
    ("service", "method", "path", "status"),
)
HTTP_REQUEST_DURATION_SECONDS = HistogramMetric(
    "amigao_http_request_duration_seconds",
    "Duracao das requests HTTP em segundos",
    ("service", "method", "path"),
)
HTTP_REQUESTS_IN_PROGRESS = GaugeMetric(
    "amigao_http_requests_in_progress",
    "Requests HTTP em andamento",
    ("service", "method", "path"),
)
CELERY_TASKS_TOTAL = CounterMetric(
    "amigao_celery_tasks_total",
    "Execucoes de tasks Celery por estado",
    ("service", "task_name", "state"),
)
CELERY_TASK_DURATION_SECONDS = HistogramMetric(
    "amigao_celery_task_duration_seconds",
    "Duracao das tasks Celery em segundos",
    ("service", "task_name"),
)
CELERY_QUEUE_DEPTH = GaugeMetric(
    "amigao_celery_queue_depth",
    "Tamanho atual das filas Celery monitoradas",
    ("service", "queue"),
)
ALERTS_TOTAL = CounterMetric(
    "amigao_alerts_total",
    "Alertas operacionais emitidos",
    ("service", "category", "severity"),
)
EMAIL_DELIVERY_TOTAL = CounterMetric(
    "amigao_email_delivery_total",
    "Tentativas de entrega de e-mail",
    ("service", "result"),
)
REALTIME_EVENTS_TOTAL = CounterMetric(
    "amigao_realtime_events_total",
    "Publicacoes realtime por resultado",
    ("service", "scope", "event", "result"),
)
WEBSOCKET_CONNECTIONS = GaugeMetric(
    "amigao_websocket_connections",
    "Conexoes websocket ativas",
    ("service", "scope"),
)
DOCUMENT_UPLOADS_TOTAL = CounterMetric(
    "amigao_document_uploads_total",
    "Confirmacoes de upload de documentos",
    ("service", "source", "result"),
)
AI_SUMMARIES_TOTAL = CounterMetric(
    "amigao_ai_summaries_total",
    "Geracao de resumos por IA",
    ("service", "result"),
)
AI_SUMMARY_DURATION_SECONDS = HistogramMetric(
    "amigao_ai_summary_duration_seconds",
    "Duracao da geracao de resumos por IA",
    ("service", "result"),
)
TASK_TRANSITIONS_TOTAL = CounterMetric(
    "amigao_task_transitions_total",
    "Transicoes de status de tarefa",
    ("service", "from_status", "to_status", "result"),
)

# Sprint O (2026-04-21) — Observabilidade Camada 4. Labels: agent_name, result
# (success|failure), tenant (id como string). Sem PII — apenas identificadores.
AGENT_EXECUTIONS_TOTAL = CounterMetric(
    "amigao_agent_executions_total",
    "Execucoes de agentes IA por resultado",
    ("service", "agent_name", "result", "tenant"),
)
AGENT_EXECUTION_DURATION_SECONDS = HistogramMetric(
    "amigao_agent_execution_duration_seconds",
    "Duracao das execucoes de agentes IA em segundos",
    ("service", "agent_name"),
)
AGENT_EXECUTION_COST_USD = CounterMetric(
    "amigao_agent_execution_cost_usd_total",
    "Custo acumulado das execucoes de agentes em USD",
    ("service", "agent_name", "tenant"),
)

_SHARED_WORKER_COUNTER_METRICS = {
    CELERY_TASKS_TOTAL.name: CELERY_TASKS_TOTAL,
    ALERTS_TOTAL.name: ALERTS_TOTAL,
    EMAIL_DELIVERY_TOTAL.name: EMAIL_DELIVERY_TOTAL,
}
_SHARED_WORKER_HISTOGRAM_METRICS = {
    CELERY_TASK_DURATION_SECONDS.name: CELERY_TASK_DURATION_SECONDS,
}
_SHARED_WORKER_METRICS_PREFIX = "amigao:metrics:worker"


def _service_name() -> str:
    return settings.SERVICE_NAME


def _shared_metrics_client():
    return redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=0.2,
        socket_timeout=0.2,
    )


def _shared_worker_metrics_enabled() -> bool:
    return _service_name() == "worker"


def _serialize_metric_labels(label_values: Sequence[object]) -> str:
    return json.dumps(list(label_values), ensure_ascii=False, separators=(",", ":"))


def _deserialize_metric_labels(raw_value: str, *, expected_size: int) -> tuple[object, ...]:
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        parsed = []

    if not isinstance(parsed, list):
        parsed = []

    normalized = list(parsed[:expected_size])
    if len(normalized) < expected_size:
        normalized.extend("" for _ in range(expected_size - len(normalized)))
    return tuple(normalized)


def _shared_counter_key(metric_name: str) -> str:
    return f"{_SHARED_WORKER_METRICS_PREFIX}:counter:{metric_name}"


def _shared_histogram_count_key(metric_name: str) -> str:
    return f"{_SHARED_WORKER_METRICS_PREFIX}:histogram:{metric_name}:count"


def _shared_histogram_sum_key(metric_name: str) -> str:
    return f"{_SHARED_WORKER_METRICS_PREFIX}:histogram:{metric_name}:sum"


def _shared_histogram_bucket_key(metric_name: str, bucket: float) -> str:
    return f"{_SHARED_WORKER_METRICS_PREFIX}:histogram:{metric_name}:bucket:{bucket}"


def _persist_shared_counter(metric: CounterMetric, label_values: tuple[object, ...], amount: float = 1.0) -> None:
    if not _shared_worker_metrics_enabled():
        return

    try:
        _shared_metrics_client().hincrbyfloat(
            _shared_counter_key(metric.name),
            _serialize_metric_labels(label_values),
            amount,
        )
    except Exception:
        return


def _persist_shared_histogram(metric: HistogramMetric, label_values: tuple[object, ...], value: float) -> None:
    if not _shared_worker_metrics_enabled():
        return

    label_key = _serialize_metric_labels(label_values)
    try:
        pipeline = _shared_metrics_client().pipeline()
        pipeline.hincrby(_shared_histogram_count_key(metric.name), label_key, 1)
        pipeline.hincrbyfloat(_shared_histogram_sum_key(metric.name), label_key, value)
        for bucket in metric.buckets:
            if value <= bucket:
                pipeline.hincrby(_shared_histogram_bucket_key(metric.name, bucket), label_key, 1)
        pipeline.execute()
    except Exception:
        return


def _read_shared_hash(key: str) -> dict[str, str]:
    try:
        return _shared_metrics_client().hgetall(key)
    except Exception:
        return {}


def _render_shared_counter_samples(metric: CounterMetric) -> list[str]:
    if metric.name not in _SHARED_WORKER_COUNTER_METRICS:
        return []

    lines: list[str] = []
    samples = _read_shared_hash(_shared_counter_key(metric.name))
    for raw_labels in sorted(samples):
        label_values = _deserialize_metric_labels(raw_labels, expected_size=len(metric.label_names))
        lines.append(
            f"{metric.name}{_format_labels(metric.label_names, label_values)} {float(samples[raw_labels])}"
        )
    return lines


def _render_shared_histogram_samples(metric: HistogramMetric) -> list[str]:
    if metric.name not in _SHARED_WORKER_HISTOGRAM_METRICS:
        return []

    count_samples = _read_shared_hash(_shared_histogram_count_key(metric.name))
    sum_samples = _read_shared_hash(_shared_histogram_sum_key(metric.name))
    bucket_samples = {
        bucket: _read_shared_hash(_shared_histogram_bucket_key(metric.name, bucket))
        for bucket in metric.buckets
    }

    label_keys = set(count_samples) | set(sum_samples)
    for sample_set in bucket_samples.values():
        label_keys.update(sample_set)

    lines: list[str] = []
    for raw_labels in sorted(label_keys):
        label_values = _deserialize_metric_labels(raw_labels, expected_size=len(metric.label_names))
        count_value = int(float(count_samples.get(raw_labels, 0)))
        sum_value = float(sum_samples.get(raw_labels, 0.0))
        for bucket in metric.buckets:
            labels = metric.label_names + ("le",)
            values = label_values + (bucket,)
            bucket_value = int(float(bucket_samples[bucket].get(raw_labels, 0)))
            lines.append(f"{metric.name}_bucket{_format_labels(labels, values)} {bucket_value}")
        labels = metric.label_names + ("le",)
        values = label_values + ("+Inf",)
        lines.append(f"{metric.name}_bucket{_format_labels(labels, values)} {count_value}")
        lines.append(f"{metric.name}_sum{_format_labels(metric.label_names, label_values)} {sum_value}")
        lines.append(f"{metric.name}_count{_format_labels(metric.label_names, label_values)} {count_value}")
    return lines


def _render_shared_metric_samples(metric: BaseMetric) -> list[str]:
    if isinstance(metric, CounterMetric):
        return _render_shared_counter_samples(metric)
    if isinstance(metric, HistogramMetric):
        return _render_shared_histogram_samples(metric)
    return []


def route_path(request: Request) -> str:
    route = request.scope.get("route")
    if route and getattr(route, "path", None):
        return route.path
    return request.url.path


def record_http_request(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    labels = {
        "service": _service_name(),
        "method": method,
        "path": path,
    }
    HTTP_REQUESTS_TOTAL.labels(**labels, status=str(status_code)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(**labels).observe(duration_seconds)


def track_http_in_progress(method: str, path: str, delta: int) -> None:
    bound = HTTP_REQUESTS_IN_PROGRESS.labels(service=_service_name(), method=method, path=path)
    if delta >= 0:
        bound.inc(delta)
    else:
        bound.dec(abs(delta))


def record_celery_task(task_name: str, state: str, duration_seconds: float | None = None) -> None:
    service_name = _service_name()
    counter_labels = (service_name, task_name, state)
    CELERY_TASKS_TOTAL.labels(service=service_name, task_name=task_name, state=state).inc()
    _persist_shared_counter(CELERY_TASKS_TOTAL, counter_labels)
    if duration_seconds is not None:
        histogram_labels = (service_name, task_name)
        CELERY_TASK_DURATION_SECONDS.labels(service=service_name, task_name=task_name).observe(duration_seconds)
        _persist_shared_histogram(CELERY_TASK_DURATION_SECONDS, histogram_labels, duration_seconds)


def update_celery_queue_depth(queue_name: str, depth: int) -> None:
    CELERY_QUEUE_DEPTH.labels(service="worker", queue=queue_name).set(depth)


def record_alert(category: str, severity: str) -> None:
    service_name = _service_name()
    label_values = (service_name, category, severity)
    ALERTS_TOTAL.labels(service=service_name, category=category, severity=severity).inc()
    _persist_shared_counter(ALERTS_TOTAL, label_values)


def record_email_delivery(result: str) -> None:
    service_name = _service_name()
    label_values = (service_name, result)
    EMAIL_DELIVERY_TOTAL.labels(service=service_name, result=result).inc()
    _persist_shared_counter(EMAIL_DELIVERY_TOTAL, label_values)


def record_realtime_event(scope: str, event: str, result: str) -> None:
    REALTIME_EVENTS_TOTAL.labels(service=_service_name(), scope=scope, event=event, result=result).inc()


def update_websocket_connections(scope: str, delta: int) -> None:
    bound = WEBSOCKET_CONNECTIONS.labels(service=_service_name(), scope=scope)
    if delta >= 0:
        bound.inc(delta)
    else:
        bound.dec(abs(delta))


def record_document_upload(source: str, result: str) -> None:
    DOCUMENT_UPLOADS_TOTAL.labels(service=_service_name(), source=source, result=result).inc()


def record_ai_summary(result: str, duration_seconds: float | None = None) -> None:
    AI_SUMMARIES_TOTAL.labels(service=_service_name(), result=result).inc()
    if duration_seconds is not None:
        AI_SUMMARY_DURATION_SECONDS.labels(service=_service_name(), result=result).observe(duration_seconds)


def record_task_transition(from_status: str, to_status: str, result: str) -> None:
    TASK_TRANSITIONS_TOTAL.labels(
        service=_service_name(),
        from_status=from_status,
        to_status=to_status,
        result=result,
    ).inc()


def record_agent_execution(
    agent_name: str,
    result: str,
    duration_seconds: float | None = None,
    *,
    tenant_id: int | None = None,
    cost_usd: float | None = None,
) -> None:
    """Sprint O — telemetria Prometheus por execução de agente IA."""
    service_name = _service_name()
    tenant_label = str(tenant_id) if tenant_id is not None else ""
    AGENT_EXECUTIONS_TOTAL.labels(
        service=service_name,
        agent_name=agent_name,
        result=result,
        tenant=tenant_label,
    ).inc()
    if duration_seconds is not None:
        AGENT_EXECUTION_DURATION_SECONDS.labels(
            service=service_name,
            agent_name=agent_name,
        ).observe(duration_seconds)
    if cost_usd is not None and cost_usd > 0:
        AGENT_EXECUTION_COST_USD.labels(
            service=service_name,
            agent_name=agent_name,
            tenant=tenant_label,
        ).inc(cost_usd)


def _queue_names() -> list[str]:
    return [queue.strip() for queue in settings.PROMETHEUS_QUEUE_NAMES.split(",") if queue.strip()]


def refresh_operational_metrics() -> None:
    queue_names = _queue_names()
    if not queue_names:
        return

    client = None
    try:
        client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        for queue_name in queue_names:
            try:
                update_celery_queue_depth(queue_name, int(client.llen(queue_name)))
            except Exception:
                continue
    except Exception:
        return
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def render_metrics() -> str:
    metrics: Iterable[BaseMetric] = (
        HTTP_REQUESTS_TOTAL,
        HTTP_REQUEST_DURATION_SECONDS,
        HTTP_REQUESTS_IN_PROGRESS,
        CELERY_TASKS_TOTAL,
        CELERY_TASK_DURATION_SECONDS,
        CELERY_QUEUE_DEPTH,
        ALERTS_TOTAL,
        EMAIL_DELIVERY_TOTAL,
        REALTIME_EVENTS_TOTAL,
        WEBSOCKET_CONNECTIONS,
        DOCUMENT_UPLOADS_TOTAL,
        AI_SUMMARIES_TOTAL,
        AI_SUMMARY_DURATION_SECONDS,
        TASK_TRANSITIONS_TOTAL,
        AGENT_EXECUTIONS_TOTAL,
        AGENT_EXECUTION_DURATION_SECONDS,
        AGENT_EXECUTION_COST_USD,
    )
    lines: list[str] = []
    for metric in metrics:
        lines.extend(metric.render_lines())
        lines.extend(_render_shared_metric_samples(metric))
    return "\n".join(lines) + "\n"


def metrics_response() -> PlainTextResponse:
    refresh_operational_metrics()
    return PlainTextResponse(render_metrics(), media_type=PROMETHEUS_CONTENT_TYPE)
