"""Legislation Alerts API — alertas de nova legislacao relevante."""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.legislation_alert import LegislationAlert
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


class LegislationAlertRead(BaseModel):
    id: int
    tenant_id: int
    process_id: Optional[int] = None
    document_id: int
    alert_type: str
    severity: str
    message: str
    is_read: bool
    created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


@router.get("/alerts", response_model=list[LegislationAlertRead])
def list_legislation_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
    is_read: Optional[bool] = Query(None),
    process_id: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 50,
) -> Any:
    """Lista alertas de legislacao para o tenant."""
    q = db.query(LegislationAlert).filter(
        LegislationAlert.tenant_id == current_user.tenant_id,
    )
    if is_read is not None:
        q = q.filter(LegislationAlert.is_read == is_read)
    if process_id is not None:
        q = q.filter(LegislationAlert.process_id == process_id)

    return q.order_by(LegislationAlert.created_at.desc()).offset(skip).limit(limit).all()


@router.patch("/alerts/{alert_id}/read")
def mark_alert_read(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> dict:
    """Marca alerta como lido."""
    alert = (
        db.query(LegislationAlert)
        .filter(
            LegislationAlert.id == alert_id,
            LegislationAlert.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta nao encontrado")

    alert.is_read = True
    db.commit()
    return {"ok": True}


@router.post("/monitor/trigger")
def trigger_monitoring(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
    crawler: Optional[str] = Query(None),
) -> dict:
    """Dispara ciclo de monitoramento manualmente (admin)."""
    from app.workers.legislation_tasks import monitor_legislation

    task = monitor_legislation.delay(crawler_name=crawler)
    return {"task_id": task.id, "status": "queued", "crawler": crawler or "all"}
