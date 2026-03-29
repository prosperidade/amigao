import json
import logging
import sys
from datetime import datetime, timezone
from contextvars import ContextVar

from app.core.config import settings
from app.core.tracing import span_id_ctx, trace_id_ctx

# Context vars para rastreamento por requisição
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
tenant_id_ctx: ContextVar[str] = ContextVar("tenant_id", default="-")
user_id_ctx: ContextVar[str] = ContextVar("user_id", default="-")

_STANDARD_LOG_RECORD_FIELDS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime",
}


class ContextFilter(logging.Filter):
    """Injeta contexto de observabilidade nos registros de log."""
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get("-")
        record.tenant_id = tenant_id_ctx.get("-")
        record.user_id = user_id_ctx.get("-")
        record.trace_id = trace_id_ctx.get("-")
        record.span_id = span_id_ctx.get("-")
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        metadata = getattr(record, "metadata", None)
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "service": settings.SERVICE_NAME,
            "logger": record.name,
            "tenant_id": getattr(record, "tenant_id", tenant_id_ctx.get("-")),
            "user_id": getattr(record, "user_id", user_id_ctx.get("-")),
            "request_id": getattr(record, "request_id", request_id_ctx.get("-")),
            "trace_id": getattr(record, "trace_id", trace_id_ctx.get("-")),
            "span_id": getattr(record, "span_id", span_id_ctx.get("-")),
            "action": getattr(record, "action", record.name),
            "message": record.getMessage(),
            "metadata": metadata if isinstance(metadata, dict) else {},
        }

        for key, value in record.__dict__.items():
            if key in _STANDARD_LOG_RECORD_FIELDS or key in payload or key == "metadata":
                continue
            payload["metadata"][key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str | None = None) -> None:
    """Configura logging estruturado para toda a aplicação."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(ContextFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level or settings.LOG_LEVEL)
    root_logger.handlers = [handler]

    # Silenciar logs excessivos de libs externas
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Retorna logger padronizado para módulos da aplicação."""
    return logging.getLogger(name)
