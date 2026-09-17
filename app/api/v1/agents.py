"""
API Router para o sistema de agentes IA.

Endpoints:
  POST /agents/run         — Executa agente sincrono
  POST /agents/run-async   — Executa agente via Celery (202)
  POST /agents/chain       — Executa chain sincrona
  POST /agents/chain-async — Executa chain via Celery (202)
  GET  /agents/registry    — Lista agentes disponiveis
  GET  /agents/chains      — Lista chains disponiveis
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents import AgentContext, AgentRegistry
from app.api.deps import get_current_internal_user, get_db
from app.models.user import User
from app.schemas.agent import (
    AgentInfo,
    AgentRunRequest,
    ChainRunRequest,
)

DbDep = Annotated[Session, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_internal_user)]

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_context(db, user, process_id, metadata):
    from app.services.evidence import build_envelope
    envelope = build_envelope(db, user.tenant_id, user.id, process_id)
    return AgentContext(tenant_id=user.tenant_id, user_id=user.id, process_id=process_id,
                        session=db, metadata={"uf": envelope.case.get("uf"), "demand_type": envelope.objective})


def _start(db, user, body, name, asynchronous):
    from app.services.connected_agents import (
        CHAINS,
        execution_data,
        legacy_step_result,
        resume_execution,
        start_execution,
    )
    execution = start_execution(db, user.tenant_id, user.id, body.process_id, name, body.idempotency_key)
    if asynchronous:
        db.commit()
        from app.workers.agent_tasks import resume_connected_execution
        task = resume_connected_execution.delay(execution_id=execution.id, tenant_id=user.tenant_id, user_id=user.id)
        return {**execution_data(execution), "task_id": task.id}
    execution = resume_execution(db, user.tenant_id, user.id, execution.id)
    db.commit()
    data = execution_data(execution)
    if name not in CHAINS:
        return {**legacy_step_result(db, execution, execution.steps[0]), **data}
    return {**data, "chain_name": name, "stopped_for_review": execution.status == "awaiting_review",
            "total_duration_ms": 0, "results": [legacy_step_result(db, execution, s) for s in execution.steps]}


@router.post("/run")
def run_agent_sync(body: AgentRunRequest, db: DbDep, current_user: UserDep):
    return _start(db, current_user, body, body.agent_name, False)


@router.post("/chain")
def run_chain_sync(body: ChainRunRequest, db: DbDep, current_user: UserDep):
    return _start(db, current_user, body, body.chain_name, False)


@router.post("/run-async", status_code=202)
def run_agent_async(body: AgentRunRequest, db: DbDep, current_user: UserDep):
    return _start(db, current_user, body, body.agent_name, True)


@router.post("/chain-async", status_code=202)
def run_chain_async(body: ChainRunRequest, db: DbDep, current_user: UserDep):
    return _start(db, current_user, body, body.chain_name, True)


@router.get("/registry", response_model=list[AgentInfo])
def list_agents(current_user: UserDep):
    from app.services.agent_capabilities import ACTIVE_AGENTS
    return [AgentInfo(**a) for a in AgentRegistry.list_agents() if a["name"] in ACTIVE_AGENTS]


@router.get("/chains")
def list_chains(current_user: UserDep):
    from app.services.connected_agents import CHAINS
    return CHAINS.copy()


# ---------------------------------------------------------------------------
# Sprint R — Budget mensal por tenant
# ---------------------------------------------------------------------------

@router.get("/budget")
def get_budget(db: DbDep, current_user: UserDep) -> dict[str, object]:
    """
    Retorna uso de IA do tenant no mês corrente vs teto mensal.

    limit=0 ⇒ ilimitado (pct=0, alert=false).
    """
    from app.core.ai_gateway import (  # noqa: PLC0415
        _month_window_utc,
        get_tenant_monthly_budget,
        get_tenant_monthly_spend,
    )

    limit = get_tenant_monthly_budget(current_user.tenant_id, db)
    used = get_tenant_monthly_spend(current_user.tenant_id, db)
    _, period_end = _month_window_utc()

    pct = 0.0
    if limit > 0:
        pct = min(100.0, round((used / limit) * 100.0, 2))

    return {
        "used_usd": round(used, 6),
        "limit_usd": round(limit, 2),
        "pct": pct,
        "unlimited": limit <= 0,
        "alert": limit > 0 and used >= limit * 0.8,
        "period_end": period_end.isoformat(),
    }
