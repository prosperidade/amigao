from celery import Celery
from app.core.config import settings

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
