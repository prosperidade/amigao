"""
Sistema de eventos dos agentes.

Emite via publish_realtime_event (Redis pub/sub existente)
e registra em AuditLog para rastreabilidade.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from app.agents.base import AgentContext, AgentResult

logger = logging.getLogger(__name__)


def emit_agent_event(
    agent_name: str,
    status: str,  # "started" | "completed" | "failed"
    ctx: AgentContext,
    *,
    result: Optional[AgentResult] = None,
    error: str | None = None,
) -> None:
    """
    Emite evento de agente via Redis pub/sub e registra audit log.

    event_type: agent.{agent_name}.{status}
    """
    event_type = f"agent.{agent_name}.{status}"
    payload: dict[str, Any] = {
        "agent_name": agent_name,
        "trace_id": ctx.trace_id,
        "process_id": ctx.process_id,
        "status": status,
    }

    if result is not None:
        payload["confidence"] = result.confidence
        payload["requires_review"] = result.requires_review
        payload["ai_job_id"] = result.ai_job_id
        payload["duration_ms"] = result.duration_ms

    if error:
        payload["error"] = error[:500]

    # Publicar via Redis (fire-and-forget, nao bloqueia agente)
    try:
        from app.services.notifications import publish_realtime_event  # noqa: PLC0415

        publish_realtime_event(
            tenant_id=ctx.tenant_id,
            event_type=event_type,
            payload=payload,
        )
    except Exception as exc:
        logger.warning("agent_event: falha ao publicar evento '%s': %s", event_type, exc)

    # Audit log
    try:
        from app.services.notifications import register_notification_audit  # noqa: PLC0415

        register_notification_audit(
            db=ctx.session,
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            entity_type="agent",
            entity_id=ctx.process_id or 0,
            action=event_type,
            details=payload,
        )
    except Exception as exc:
        logger.warning("agent_event: falha ao registrar audit '%s': %s", event_type, exc)
