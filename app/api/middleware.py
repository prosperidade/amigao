from time import perf_counter
import uuid
import logging
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.core.alerts import emit_operational_alert
from app.core.config import settings
from app.core.logging import request_id_ctx, tenant_id_ctx, user_id_ctx
from app.core.metrics import record_http_request, route_path, track_http_in_progress
from app.core.tracing import build_traceparent, parse_traceparent, reset_trace_context, set_trace_context

logger = logging.getLogger(__name__)


def _extract_auth_context(request: Request) -> tuple[str, str]:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return "-", request.headers.get("X-Tenant-Id", "-")

    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except (JWTError, Exception):
        return "-", request.headers.get("X-Tenant-Id", "-")

    user_id = str(payload.get("sub", "-"))
    tenant_id = str(payload.get("tenant_id", request.headers.get("X-Tenant-Id", "-")))
    return user_id, tenant_id


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware que:
    - Gera um request_id único por requisição
    - Extrai X-Tenant-Id do header (quando disponível)
    - Injeta ambos nas context vars para logging estruturado
    - Loga entrada e saída de cada request
    """

    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())[:8]
        user_id, tenant_header = _extract_auth_context(request)
        incoming_trace_id, _ = parse_traceparent(request.headers.get("traceparent"))
        trace_token, span_token, trace_id, span_id = set_trace_context(trace_id=incoming_trace_id)
        path = route_path(request)
        start = perf_counter()

        # Definir context vars para esta requisição
        token_req = request_id_ctx.set(req_id)
        token_ten = tenant_id_ctx.set(tenant_header)
        token_user = user_id_ctx.set(user_id)
        track_http_in_progress(request.method, path, 1)

        logger.info(
            "HTTP request started",
            extra={
                "action": "http.request.started",
                "metadata": {
                    "method": request.method,
                    "path": path,
                },
            },
        )

        try:
            response = await call_next(request)
            duration_seconds = perf_counter() - start
            record_http_request(request.method, path, response.status_code, duration_seconds)
            threshold_ms = settings.slow_request_threshold_for(path)
            if duration_seconds * 1000 > threshold_ms:
                emit_operational_alert(
                    category="latency",
                    severity="warning",
                    message="Request acima do SLO de latência",
                    metadata={
                        "method": request.method,
                        "path": path,
                        "status_code": response.status_code,
                        "threshold_ms": threshold_ms,
                        "duration_ms": round(duration_seconds * 1000, 2),
                    },
                )
            logger.info(
                "HTTP request finished",
                extra={
                    "action": "http.request.finished",
                    "metadata": {
                        "method": request.method,
                        "path": path,
                        "status_code": response.status_code,
                        "duration_ms": round(duration_seconds * 1000, 2),
                    },
                },
            )
            response.headers["X-Request-Id"] = req_id
            response.headers["traceparent"] = build_traceparent(trace_id, span_id)
        except Exception as exc:
            duration_seconds = perf_counter() - start
            record_http_request(request.method, path, 500, duration_seconds)
            emit_operational_alert(
                category="api_error",
                severity="error",
                message="Unhandled exception durante request HTTP",
                metadata={
                    "method": request.method,
                    "path": path,
                    "duration_ms": round(duration_seconds * 1000, 2),
                },
            )
            logger.exception(
                "Unhandled error during request",
                extra={
                    "action": "http.request.failed",
                    "metadata": {
                        "method": request.method,
                        "path": path,
                        "duration_ms": round(duration_seconds * 1000, 2),
                        "error": str(exc),
                    },
                },
            )
            raise
        finally:
            track_http_in_progress(request.method, path, -1)
            request_id_ctx.reset(token_req)
            tenant_id_ctx.reset(token_ten)
            user_id_ctx.reset(token_user)
            reset_trace_context(trace_token, span_token)

        return response
