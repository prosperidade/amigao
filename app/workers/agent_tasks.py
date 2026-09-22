"""
Celery tasks para execucao assincrona de agentes.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.exc import (
    DataError,
    IntegrityError,
    OperationalError,
    PendingRollbackError,
    ProgrammingError,
)

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="workers.resume_connected_execution", bind=True, max_retries=3, retry_backoff=True)
def resume_connected_execution(self, *, execution_id: str, tenant_id: int, user_id: int):
    return _connected_task(self, tenant_id, user_id, execution_id=execution_id)

# Erros DETERMINÍSTICOS: retry NUNCA resolve (schema ausente/errado, violação de
# constraint, input inválido) — só esconde o problema por horas em retry storm.
# Incidente 2026-06-06: `extracted_field_staging` não migrada em prod →
# UndefinedTable (ProgrammingError) → sessão abortada → `db.commit()` levantava
# PendingRollbackError → retry de 60s sem fim. Estes erros marcam o job `failed`
# com erro legível e PARAM. `OperationalError` NÃO entra aqui de propósito: é a
# classe transitória (conexão caída, deadlock) — essa continua com retry.
_DETERMINISTIC_ERRORS: tuple[type[Exception], ...] = (
    ValueError,            # pré-condição / input inválido (já tratado na rodada2)
    ProgrammingError,      # UndefinedTable, UndefinedColumn, erro de sintaxe SQL
    IntegrityError,        # FK / unique / not-null
    DataError,             # valor fora de range/tipo
    PendingRollbackError,  # sessão já abortada por erro determinístico anterior
)


def _connected_task(task, tenant_id, user_id, *, execution_id=None, process_id=None, name=None):
    from fastapi import HTTPException

    from app.db.session import SessionLocal
    from app.services.connected_agents import execution_data, resume_execution, start_execution
    try:
        with SessionLocal() as db:
            if execution_id is None:
                execution = start_execution(db, tenant_id, user_id, process_id, name,
                                            key=getattr(task.request, "id", None))
                execution_id = execution.id
                db.commit()  # persist the cursor before invoking an external provider
            result = resume_execution(db, tenant_id, user_id, execution_id)
            db.commit()
            return execution_data(result)
    except HTTPException as exc:
        if exc.status_code == 409:
            raise task.retry(exc=exc, countdown=5)
        # Falha de agente em fila não tem tela para avisar ninguém: sem este log
        # ela some (22/09/2026 — a cadeia OCR→extrator devolvia 404 "Caso não
        # encontrado" e nada aparecia em lugar nenhum). Erro, não warning: quem
        # pediu a extração não recebeu extração.
        logger.error(
            "agente %s não executou [%s]: %s (tenant=%s processo=%s execucao=%s)",
            name or "?", exc.status_code, exc.detail, tenant_id, process_id, execution_id,
        )
        return {"status": "failed", "error": exc.detail}
    except _DETERMINISTIC_ERRORS as exc:
        # A fresh transaction may record the failed cursor; never reuse an aborted one.
        if execution_id:
            from app.models.evidence import AgentExecution
            with SessionLocal() as db:
                execution = db.query(AgentExecution).filter(AgentExecution.id == execution_id,
                    AgentExecution.tenant_id == tenant_id).first()
                if execution:
                    execution.status = "failed"
                    execution.waiting_reason = type(exc).__name__
                    db.commit()
        return {"status": "failed", "error": str(exc)}
    except OperationalError as exc:
        raise task.retry(exc=exc, countdown=30)


def _persist_failed_job(
    *,
    tenant_id: int,
    user_id: Optional[int],
    process_id: Optional[int],
    agent_name: str,
    job_type: Any,
    error: str,
) -> None:
    """Best-effort: registra um AIJob `failed` numa sessão LIMPA.

    Quando o erro determinístico envenena a transação, o job `running` criado
    pelo agente é descartado no rollback (some do histórico). Aqui recriamos um
    registro `failed` com o erro legível, em sessão nova, para a execução não
    desaparecer da UI. Nunca levanta (best-effort)."""
    if job_type is None:
        return
    from datetime import UTC, datetime  # noqa: PLC0415

    from app.db.session import SessionLocal  # noqa: PLC0415
    from app.models.ai_job import AIJob, AIJobStatus  # noqa: PLC0415

    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        db.add(AIJob(
            tenant_id=tenant_id,
            created_by_user_id=user_id,
            entity_type="process" if process_id else "agent",
            entity_id=process_id,
            job_type=job_type,
            status=AIJobStatus.failed,
            agent_name=agent_name,
            error=str(error)[:2000],
            started_at=now,
            finished_at=now,
        ))
        db.commit()
    except Exception as exc:  # noqa: BLE001 — best-effort, não pode derrubar a task
        db.rollback()
        logger.warning("agent_task: falha ao persistir job failed de %s: %s", agent_name, exc)
    finally:
        db.close()


@celery_app.task(
    name="workers.run_agent",
    bind=True,
    max_retries=2,
    soft_time_limit=300,
)
def run_agent(
    self,
    *,
    agent_name: str,
    tenant_id: int,
    user_id: Optional[int] = None,
    process_id: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Old queue messages still go through authorization and current policy."""
    from app.services.agent_capabilities import ACTIVE_AGENTS
    if agent_name not in ACTIVE_AGENTS:
        return {"status": "agente_desativado", "agent": agent_name}
    return _connected_task(self, tenant_id, user_id, process_id=process_id, name=agent_name)


@celery_app.task(
    name="workers.run_agent_chain",
    bind=True,
    max_retries=1,
    soft_time_limit=600,
)
def run_agent_chain(
    self,
    *,
    chain_name: str,
    tenant_id: int,
    user_id: Optional[int] = None,
    process_id: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
    stop_on_review: bool = True,
) -> dict[str, Any]:
    """Persisted chain; returned steps alone never establish completion."""
    from app.services.connected_agents import CHAINS
    if chain_name not in CHAINS:
        return {"status": "agente_desativado", "chain": chain_name}
    return _connected_task(self, tenant_id, user_id, process_id=process_id, name=chain_name)


@celery_app.task(
    name="workers.vigia_scheduled_check",
    bind=True,
    soft_time_limit=300,
)
def vigia_scheduled_check(
    self,
    *,
    tenant_id: int,
) -> dict[str, Any]:
    """Frozen by ADR-069, including messages already queued."""
    return {"status": "agente_desativado"}


@celery_app.task(
    name="workers.vigia_all_tenants",
    soft_time_limit=600,
)
def vigia_all_tenants() -> dict[str, Any]:
    """Frozen by ADR-069, including messages already queued."""
    return {"status": "agente_desativado"}


@celery_app.task(
    name="workers.acompanhamento_check_all",
    soft_time_limit=600,
)
def acompanhamento_check_all() -> dict[str, Any]:
    """Frozen by ADR-069, including messages already queued."""
    return {"status": "agente_desativado"}
