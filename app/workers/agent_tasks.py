"""
Celery tasks para execucao assincrona de agentes.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


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
    """Execucao generica de um agente via Celery."""
    from app.agents import AgentContext, AgentRegistry  # noqa: PLC0415
    from app.db.session import SessionLocal  # noqa: PLC0415

    db = SessionLocal()
    try:
        ctx = AgentContext(
            tenant_id=tenant_id,
            user_id=user_id,
            process_id=process_id,
            session=db,
            metadata=metadata or {},
        )
        agent = AgentRegistry.create(agent_name, ctx)
        result = agent.run()
        db.commit()

        logger.info(
            "agent_task: %s completed success=%s job_id=%s",
            agent_name, result.success, result.ai_job_id,
        )
        return {
            "status": "success" if result.success else "failed",
            "agent": agent_name,
            "data": result.data,
            "ai_job_id": result.ai_job_id,
            "confidence": result.confidence,
            "requires_review": result.requires_review,
            "error": result.error,
        }
    except Exception as exc:
        db.rollback()
        logger.error("agent_task: %s failed: %s", agent_name, exc)
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()


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
    """Execucao de chain de agentes via Celery."""
    from app.agents import AgentContext, OrchestratorAgent  # noqa: PLC0415
    from app.db.session import SessionLocal  # noqa: PLC0415

    db = SessionLocal()
    try:
        ctx = AgentContext(
            tenant_id=tenant_id,
            user_id=user_id,
            process_id=process_id,
            session=db,
            metadata=metadata or {},
        )
        results = OrchestratorAgent.execute_chain(
            chain_name, ctx, stop_on_review=stop_on_review,
        )
        db.commit()

        return {
            "status": "success",
            "chain": chain_name,
            "steps": [
                {
                    "agent": r.agent_name,
                    "success": r.success,
                    "ai_job_id": r.ai_job_id,
                    "confidence": r.confidence,
                    "requires_review": r.requires_review,
                }
                for r in results
            ],
        }
    except Exception as exc:
        db.rollback()
        logger.error("agent_chain_task: %s failed: %s", chain_name, exc)
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()


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
    """Task agendado (Celery Beat) para o VigiaAgent."""
    from app.agents import AgentContext, AgentRegistry  # noqa: PLC0415
    from app.db.session import SessionLocal  # noqa: PLC0415

    db = SessionLocal()
    try:
        ctx = AgentContext(
            tenant_id=tenant_id,
            user_id=None,
            process_id=None,
            session=db,
            metadata={"check_type": "all"},
        )
        agent = AgentRegistry.create("vigia", ctx)
        result = agent.run()
        db.commit()

        alerts_count = len(result.data.get("alerts", []))
        logger.info(
            "vigia_scheduled: tenant=%d alerts=%d",
            tenant_id, alerts_count,
        )

        # Publicar alertas via Redis
        if alerts_count > 0:
            try:
                from app.services.notifications import publish_realtime_event  # noqa: PLC0415
                for alert in result.data.get("alerts", []):
                    publish_realtime_event(
                        tenant_id=tenant_id,
                        event_type="vigia.alert",
                        payload=alert,
                    )
            except Exception as exc:
                logger.warning("vigia_scheduled: falha ao publicar alertas: %s", exc)

        return {
            "status": "success",
            "alerts_count": alerts_count,
            "tenant_id": tenant_id,
        }
    except Exception as exc:
        db.rollback()
        logger.error("vigia_scheduled: tenant=%d failed: %s", tenant_id, exc)
        raise
    finally:
        db.close()


@celery_app.task(
    name="workers.vigia_all_tenants",
    soft_time_limit=600,
)
def vigia_all_tenants() -> dict[str, Any]:
    """
    Celery Beat task: lista tenants ativos e dispara vigia_scheduled_check para cada um.
    Roda a cada 6h via beat_schedule.
    """
    from app.db.session import SessionLocal  # noqa: PLC0415
    from app.models.user import User  # noqa: PLC0415

    db = SessionLocal()
    try:
        tenant_ids = (
            db.query(User.tenant_id)
            .filter(User.is_active == True)
            .distinct()
            .all()
        )
        tenant_ids = [t[0] for t in tenant_ids if t[0] is not None]

        for tid in tenant_ids:
            vigia_scheduled_check.delay(tenant_id=tid)

        logger.info("vigia_all_tenants: dispatched for %d tenants", len(tenant_ids))
        return {"status": "dispatched", "tenant_count": len(tenant_ids)}
    except Exception as exc:
        logger.error("vigia_all_tenants failed: %s", exc)
        raise
    finally:
        db.close()


@celery_app.task(
    name="workers.acompanhamento_check_all",
    soft_time_limit=600,
)
def acompanhamento_check_all() -> dict[str, Any]:
    """
    Celery Beat task: verifica processos em status 'aguardando_orgao'
    e dispara agente acompanhamento para cada um.
    Roda a cada 30min via beat_schedule.
    """
    from app.db.session import SessionLocal  # noqa: PLC0415
    from app.models.process import Process, ProcessStatus  # noqa: PLC0415

    db = SessionLocal()
    try:
        processes = (
            db.query(Process.id, Process.tenant_id)
            .filter(
                Process.status == ProcessStatus.aguardando_orgao,
                Process.deleted_at.is_(None),
            )
            .limit(100)
            .all()
        )

        dispatched = 0
        for proc_id, tenant_id in processes:
            run_agent.delay(
                agent_name="acompanhamento",
                tenant_id=tenant_id,
                process_id=proc_id,
                metadata={"check_type": "scheduled"},
            )
            dispatched += 1

        logger.info("acompanhamento_check_all: dispatched for %d processes", dispatched)
        return {"status": "dispatched", "process_count": dispatched}
    except Exception as exc:
        logger.error("acompanhamento_check_all failed: %s", exc)
        raise
    finally:
        db.close()
