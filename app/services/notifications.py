import json
import logging
from typing import Optional

import redis
from sqlalchemy.orm import Session

from app.core.alerts import emit_operational_alert
from app.core.config import settings
from app.core.metrics import record_realtime_event
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def publish_realtime_event(
    *,
    tenant_id: int,
    event_type: str,
    payload: dict,
    client_id: Optional[int] = None,
) -> bool:
    scope = "client" if client_id is not None else "tenant"
    message = {
        "tenant_id": tenant_id,
        "client_id": client_id,
        "scope": scope,
        "event": event_type,
        "payload": payload,
    }

    client = None
    try:
        client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        client.publish(
            settings.REALTIME_EVENTS_CHANNEL,
            json.dumps(message, ensure_ascii=False),
        )
        record_realtime_event(scope, event_type, "success")
        return True
    except Exception as exc:
        record_realtime_event(scope, event_type, "failed")
        emit_operational_alert(
            category="realtime_publish",
            severity="error",
            message="Falha ao publicar evento realtime",
            metadata={"event_type": event_type, "scope": scope, "error": str(exc)},
        )
        logger.warning(
            "Falha ao publicar evento realtime '%s' no Redis: %s",
            event_type,
            exc,
        )
        return False
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def register_notification_audit(
    *,
    db: Session,
    tenant_id: int,
    entity_type: str,
    entity_id: int,
    action: str,
    user_id: Optional[int] = None,
    details: Optional[dict] = None,
) -> None:
    audit = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        details=json.dumps(details or {}, ensure_ascii=False),
    )
    db.add(audit)
