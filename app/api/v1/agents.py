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

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents import AgentContext, AgentRegistry, OrchestratorAgent
from app.agents.orchestrator import CHAINS
from app.api.deps import get_current_internal_user, get_db
from app.core.config import settings
from app.models.user import User

DbDep = Annotated[Session, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_internal_user)]
from app.schemas.agent import (
    AgentInfo,
    AgentRunRequest,
    AgentRunResponse,
    AsyncTaskResponse,
    ChainRunRequest,
    ChainRunResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_context(
    db: DbDep,
    user: UserDep,
    process_id: int | None,
    metadata: dict,
) -> AgentContext:
    return AgentContext(
        tenant_id=user.tenant_id,
        user_id=user.id,
        process_id=process_id,
        session=db,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Execucao sincrona
# ---------------------------------------------------------------------------

@router.post("/run", response_model=AgentRunResponse)
def run_agent_sync(
    body: AgentRunRequest,
    db: DbDep,
    current_user: UserDep,
) -> AgentRunResponse:
    """Executa um agente individual de forma sincrona."""
    if not settings.ai_configured:
        # Alguns agentes (vigia, financeiro) funcionam sem IA
        pass

    ctx = _build_context(db, current_user, body.process_id, body.metadata)

    try:
        agent = AgentRegistry.create(body.agent_name, ctx)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    result = agent.run()
    db.commit()

    return AgentRunResponse(
        success=result.success,
        data=result.data,
        confidence=result.confidence,
        ai_job_id=result.ai_job_id,
        suggestions=result.suggestions,
        requires_review=result.requires_review,
        agent_name=result.agent_name,
        duration_ms=result.duration_ms,
        error=result.error,
    )


@router.post("/chain", response_model=ChainRunResponse)
def run_chain_sync(
    body: ChainRunRequest,
    db: DbDep,
    current_user: UserDep,
) -> ChainRunResponse:
    """Executa uma chain de agentes de forma sincrona."""
    ctx = _build_context(db, current_user, body.process_id, body.metadata)

    try:
        results = OrchestratorAgent.execute_chain(
            body.chain_name,
            ctx,
            stop_on_review=body.stop_on_review,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    db.commit()

    steps = [
        AgentRunResponse(
            success=r.success,
            data=r.data,
            confidence=r.confidence,
            ai_job_id=r.ai_job_id,
            suggestions=r.suggestions,
            requires_review=r.requires_review,
            agent_name=r.agent_name,
            duration_ms=r.duration_ms,
            error=r.error,
        )
        for r in results
    ]

    chain_agents = CHAINS.get(body.chain_name, [])
    completed = len(results) == len(chain_agents) and all(r.success for r in results)
    stopped_for_review = any(r.requires_review for r in results)

    return ChainRunResponse(
        chain_name=body.chain_name,
        steps=steps,
        completed=completed,
        stopped_for_review=stopped_for_review,
        total_duration_ms=sum(r.duration_ms for r in results),
    )


# ---------------------------------------------------------------------------
# Execucao assincrona (Celery)
# ---------------------------------------------------------------------------

@router.post("/run-async", response_model=AsyncTaskResponse, status_code=202)
def run_agent_async(
    body: AgentRunRequest,
    db: DbDep,
    current_user: UserDep,
) -> AsyncTaskResponse:
    """Enfileira execucao de agente via Celery."""
    # Validar que o agente existe
    if not AgentRegistry.get(body.agent_name):
        raise HTTPException(status_code=400, detail=f"Agente '{body.agent_name}' nao encontrado")

    from app.workers.agent_tasks import run_agent  # noqa: PLC0415

    task = run_agent.delay(
        agent_name=body.agent_name,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        process_id=body.process_id,
        metadata=body.metadata,
    )

    return AsyncTaskResponse(
        task_id=task.id,
        status="queued",
        agent_name=body.agent_name,
        process_id=body.process_id,
    )


@router.post("/chain-async", response_model=AsyncTaskResponse, status_code=202)
def run_chain_async(
    body: ChainRunRequest,
    db: DbDep,
    current_user: UserDep,
) -> AsyncTaskResponse:
    """Enfileira execucao de chain via Celery."""
    if body.chain_name not in CHAINS:
        raise HTTPException(status_code=400, detail=f"Chain '{body.chain_name}' nao encontrada")

    from app.workers.agent_tasks import run_agent_chain  # noqa: PLC0415

    task = run_agent_chain.delay(
        chain_name=body.chain_name,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        process_id=body.process_id,
        metadata=body.metadata,
        stop_on_review=body.stop_on_review,
    )

    return AsyncTaskResponse(
        task_id=task.id,
        status="queued",
        chain_name=body.chain_name,
        process_id=body.process_id,
    )


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

@router.get("/registry", response_model=list[AgentInfo])
def list_agents(current_user: UserDep) -> list[AgentInfo]:
    """Lista todos os agentes registrados."""
    return [AgentInfo(**a) for a in AgentRegistry.list_agents()]


@router.get("/chains")
def list_chains(current_user: UserDep) -> dict[str, list[str]]:
    """Lista todas as chains disponiveis."""
    return OrchestratorAgent.list_chains()
