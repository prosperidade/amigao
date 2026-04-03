from time import perf_counter

from celery import Celery
from celery.signals import before_task_publish, task_failure, task_postrun, task_prerun

from app.core.alerts import emit_operational_alert
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.metrics import record_celery_task
from app.core.tracing import current_trace_context, reset_trace_context, set_trace_context

setup_logging()
celery_app = Celery(
    "amigao_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=False,
    task_track_started=True,
)

# Auto-descobrir tasks no módulo workers
celery_app.autodiscover_tasks(["app.workers"])

_task_started_at: dict[str, float] = {}


@before_task_publish.connect
def inject_trace_headers(headers=None, **kwargs):
    if headers is None:
        return
    trace_context = current_trace_context()
    if trace_context["trace_id"] == "-":
        return
    headers["trace_id"] = trace_context["trace_id"]
    headers["parent_span_id"] = trace_context["span_id"]


@task_prerun.connect
def observe_task_prerun(task_id=None, task=None, **kwargs):
    if task is None:
        return
    headers = getattr(getattr(task, "request", None), "headers", None) or {}
    trace_id = headers.get("trace_id")
    trace_token, span_token, _, _ = set_trace_context(trace_id=trace_id)
    task.request._trace_tokens = trace_token, span_token
    if task_id is not None:
        _task_started_at[task_id] = perf_counter()
    record_celery_task(task.name, "started")


@task_postrun.connect
def observe_task_postrun(task_id=None, task=None, state=None, **kwargs):
    if task is not None:
        duration = None
        if task_id in _task_started_at:
            duration = perf_counter() - _task_started_at.pop(task_id)
        record_celery_task(task.name, (state or "unknown").lower(), duration)
        tokens = getattr(getattr(task, "request", None), "_trace_tokens", None)
        if tokens:
            reset_trace_context(tokens[0], tokens[1])


@task_failure.connect
def observe_task_failure(task_id=None, exception=None, sender=None, **kwargs):
    emit_operational_alert(
        category="celery_task_failure",
        severity="error",
        message="Task Celery falhou",
        metadata={
            "task_id": task_id,
            "task_name": getattr(sender, "name", "-"),
            "error": str(exception),
        },
    )
