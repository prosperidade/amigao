import logging
import sys
from contextvars import ContextVar

# Context vars para rastreamento por requisição
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
tenant_id_ctx: ContextVar[str] = ContextVar("tenant_id", default="-")


class ContextFilter(logging.Filter):
    """Injeta request_id e tenant_id nos registros de log."""
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get("-")
        record.tenant_id = tenant_id_ctx.get("-")
        return True


def setup_logging(level: str = "INFO") -> None:
    """Configura logging estruturado para toda a aplicação."""
    fmt = "%(asctime)s | %(levelname)-8s | req=%(request_id)s tenant=%(tenant_id)s | %(name)s - %(message)s"
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt))
    handler.addFilter(ContextFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = [handler]

    # Silenciar logs excessivos de libs externas
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
