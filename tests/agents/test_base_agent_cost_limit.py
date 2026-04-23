"""Sprint -1 B — _fail_job preserva métricas do AIGatewayError (auditoria cost_exceeded)."""

from __future__ import annotations

import time

from app.agents.atendimento import AtendimentoAgent
from app.agents.base import AgentContext
from app.core.ai_gateway import AIGatewayError
from app.models.ai_job import AIJob, AIJobStatus, AIJobType
from app.models.tenant import Tenant
from app.models.user import User


def _seed(db):
    tenant = Tenant(name="Cost Tenant")
    db.add(tenant)
    db.flush()
    user = User(
        email="cost@example.com",
        full_name="Cost User",
        hashed_password="x" * 60,
        tenant_id=tenant.id,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return tenant, user


def test_fail_job_preserves_cost_tokens_model_from_ai_gateway_error(db_session):
    """
    Cenário Sprint -1 B: agente recebe AIGatewayError(cost_exceeded).
    Expectativa: _fail_job persiste cost_usd, tokens_in/out, model_used no AIJob
    para auditoria do limite financeiro.
    """
    tenant, user = _seed(db_session)

    ctx = AgentContext(
        tenant_id=tenant.id,
        user_id=user.id,
        process_id=None,
        session=db_session,
        metadata={"description": "teste de classificação de demanda"},
    )
    agent = AtendimentoAgent(ctx)
    agent._started_at = time.monotonic()

    # Cria AIJob manualmente (como BaseAgent._create_running_job faria)
    job = AIJob(
        tenant_id=tenant.id,
        created_by_user_id=user.id,
        job_type=AIJobType.classify_demand,
        status=AIJobStatus.running,
        agent_name="atendimento",
    )
    db_session.add(job)
    db_session.flush()

    cost_error = AIGatewayError(
        message="Job cost $1.5000 exceeded max $0.1000",
        last_error="cost_exceeded model=gemini/gemini-2.0-flash",
        cost_usd=1.5,
        tokens_in=120_000,
        tokens_out=8_000,
        model_used="gemini/gemini-2.0-flash",
    )

    agent._fail_job(job, cost_error)
    db_session.flush()
    db_session.refresh(job)

    assert job.status == AIJobStatus.failed
    assert job.cost_usd == 1.5
    assert job.tokens_in == 120_000
    assert job.tokens_out == 8_000
    assert job.model_used == "gemini/gemini-2.0-flash"
    assert "exceeded" in (job.error or "").lower()


def test_fail_job_with_regular_exception_does_not_touch_cost_fields(db_session):
    """Exceções comuns (ValueError etc.) não têm cost/tokens — não sobrescreve o AIJob."""
    tenant, user = _seed(db_session)

    ctx = AgentContext(
        tenant_id=tenant.id,
        user_id=user.id,
        process_id=None,
        session=db_session,
        metadata={},
    )
    agent = AtendimentoAgent(ctx)
    agent._started_at = time.monotonic()

    job = AIJob(
        tenant_id=tenant.id,
        created_by_user_id=user.id,
        job_type=AIJobType.classify_demand,
        status=AIJobStatus.running,
        agent_name="atendimento",
        cost_usd=0.001,  # valor prévio
        tokens_in=50,
    )
    db_session.add(job)
    db_session.flush()

    agent._fail_job(job, ValueError("invalid payload"))
    db_session.flush()
    db_session.refresh(job)

    assert job.status == AIJobStatus.failed
    assert "invalid payload" in (job.error or "")
    # Campos financeiros intactos (não são sobrescritos)
    assert job.cost_usd == 0.001
    assert job.tokens_in == 50
