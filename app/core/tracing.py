import secrets
from contextvars import ContextVar
from typing import Optional


trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="-")
span_id_ctx: ContextVar[str] = ContextVar("span_id", default="-")


def generate_trace_id() -> str:
    return secrets.token_hex(16)


def generate_span_id() -> str:
    return secrets.token_hex(8)


def _is_hex(value: str, expected_length: int) -> bool:
    if len(value) != expected_length:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def parse_traceparent(header_value: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not header_value:
        return None, None

    parts = header_value.split("-")
    if len(parts) != 4:
        return None, None

    _, trace_id, parent_span_id, _ = parts
    if not _is_hex(trace_id, 32) or not _is_hex(parent_span_id, 16):
        return None, None

    return trace_id, parent_span_id


def build_traceparent(trace_id: Optional[str] = None, span_id: Optional[str] = None) -> str:
    resolved_trace_id = trace_id if trace_id and _is_hex(trace_id, 32) else generate_trace_id()
    resolved_span_id = span_id if span_id and _is_hex(span_id, 16) else generate_span_id()
    return f"00-{resolved_trace_id}-{resolved_span_id}-01"


def set_trace_context(
    *,
    trace_id: Optional[str] = None,
    span_id: Optional[str] = None,
) -> tuple[object, object, str, str]:
    resolved_trace_id = trace_id if trace_id and _is_hex(trace_id, 32) else generate_trace_id()
    resolved_span_id = span_id if span_id and _is_hex(span_id, 16) else generate_span_id()
    trace_token = trace_id_ctx.set(resolved_trace_id)
    span_token = span_id_ctx.set(resolved_span_id)
    return trace_token, span_token, resolved_trace_id, resolved_span_id


def reset_trace_context(trace_token: object, span_token: object) -> None:
    trace_id_ctx.reset(trace_token)
    span_id_ctx.reset(span_token)


def current_trace_context() -> dict[str, str]:
    return {
        "trace_id": trace_id_ctx.get("-"),
        "span_id": span_id_ctx.get("-"),
    }
