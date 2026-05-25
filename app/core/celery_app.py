from time import perf_counter

from celery import Celery
from celery.schedules import crontab
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
    # Upstash/Redis cloud: reduzir polling para caber no plano pago básico
    # (~$0.20 por 100k cmds). Numeros observados 24-25/05: 533k cmds em 3 dias
    # com Andre+socia testando = ~177k/dia, 96% reads (polling idle do worker).
    # Mudancas abaixo cortam o polling em ~80-90% sem prejudicar UX:
    #
    # - visibility_timeout: 3600 (mantido) — cobre tasks longas (OCR ~3min)
    # - polling_interval: 5.0 — BRPOP de queue a cada 5s (default ~1s).
    #   Tasks novas demoram ate ~5s pra serem pegas. Imperceptivel pra
    #   trigger humano; o consultor nao percebe diferenca entre 1s e 5s
    #   no inicio de uma extracao OCR que dura minutos.
    # - broker_heartbeat: 240 — PING ao broker a cada 4min (default 30s).
    #   Reduz mensagens de keepalive em 8x.
    # - worker_prefetch_multiplier: 1 — worker pega uma task de cada vez
    #   antes de pedir mais (default 4). Combina com pool=solo do Render.
    broker_transport_options={
        "visibility_timeout": 3600,
        "polling_interval": 5.0,
    },
    broker_heartbeat=240,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "monitor-legislation-dou-daily": {
            "task": "workers.monitor_legislation_dou",
            "schedule": crontab(hour=6, minute=0),  # 06:00 BRT diario
        },
        "monitor-legislation-doe-daily": {
            "task": "workers.monitor_legislation_doe",
            "schedule": crontab(hour=6, minute=30),  # 06:30 BRT diario
        },
        "monitor-legislation-agencies-weekly": {
            "task": "workers.monitor_legislation_agencies",
            "schedule": crontab(hour=3, minute=0, day_of_week=1),  # segunda 03:00
        },
        "vigia-scheduled-check": {
            "task": "workers.vigia_all_tenants",
            # Reduzido de 6h (4/dia) para 12h (2/dia). Vigia roda sem LLM
            # checando prazos em ProcessTask; 2 execuções/dia (manhã/noite)
            # cobrem o ciclo de trabalho da sócia hoje.
            "schedule": crontab(hour="6,18", minute=15),
        },
        "acompanhamento-check-processes": {
            "task": "workers.acompanhamento_check_all",
            # Reduzido de 30min (48/dia) para 2h (12/dia). Sem inbox connector
            # ativo, o acompanhamento atual é leve. Quando o connector real
            # de e-mail entrar (dívida P2), reavaliar.
            "schedule": crontab(minute=0, hour="*/2"),
        },
        # Sprint F Bloco 3 — expira rascunhos de cadastro após 15 dias.
        "cleanup-expired-intake-drafts": {
            "task": "workers.cleanup_expired_intake_drafts",
            "schedule": crontab(hour=2, minute=30),  # 02:30 BRT diário (off-peak)
        },
    },
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
