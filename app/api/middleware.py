import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.core.logging import request_id_ctx, tenant_id_ctx

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware que:
    - Gera um request_id único por requisição
    - Extrai X-Tenant-Id do header (quando disponível)
    - Injeta ambos nas context vars para logging estruturado
    - Loga entrada e saída de cada request
    """

    async def dispatch(self, request: Request, call_next):
        req_id = str(uuid.uuid4())[:8]
        tenant_header = request.headers.get("X-Tenant-Id", "-")

        # Definir context vars para esta requisição
        token_req = request_id_ctx.set(req_id)
        token_ten = tenant_id_ctx.set(tenant_header)

        logger.info(f"→ {request.method} {request.url.path}")

        try:
            response = await call_next(request)
            logger.info(f"← {request.method} {request.url.path} [{response.status_code}]")
        except Exception as exc:
            logger.exception(f"Unhandled error: {exc}")
            raise
        finally:
            request_id_ctx.reset(token_req)
            tenant_id_ctx.reset(token_ten)

        return response
