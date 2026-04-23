"""
AI Gateway — Sprint 5 (Wave 2)

Gateway multi-provider via litellm com:
- Fallback automático entre providers (OpenAI → Gemini → Claude)
- Registro de custo e tokens por chamada
- Timeout e proteção de custo máximo por job
- Modo degradado quando IA não está configurada (retorna None)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AIResponse:
    content: str
    model_used: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    duration_ms: int
    provider: str


@dataclass
class AIGatewayError(Exception):
    message: str
    last_error: Optional[str] = None


AI_HOURLY_COST_LIMIT_USD = 5.0  # limite padrão por tenant por hora


def check_tenant_cost_limit(
    tenant_id: int,
    db: "Session",
    limit_usd: float = AI_HOURLY_COST_LIMIT_USD,
) -> float:
    """Retorna custo acumulado na última hora. Levanta HTTPException se exceder limite."""
    from datetime import UTC, datetime, timedelta

    from fastapi import HTTPException
    from sqlalchemy import func

    from app.models.ai_job import AIJob

    one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
    total_cost = (
        db.query(func.coalesce(func.sum(AIJob.cost_usd), 0.0))
        .filter(
            AIJob.tenant_id == tenant_id,
            AIJob.created_at >= one_hour_ago,
        )
        .scalar()
    )
    if total_cost >= limit_usd:
        raise HTTPException(
            status_code=429,
            detail=f"Limite de custo de IA excedido: ${total_cost:.2f}/${limit_usd:.2f} na última hora",
        )
    return float(total_cost)


def _month_window_utc() -> "tuple[datetime, datetime]":
    """Retorna (início do mês UTC, início do próximo mês UTC)."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        next_start = start.replace(year=start.year + 1, month=1)
    else:
        next_start = start.replace(month=start.month + 1)
    return start, next_start


def get_tenant_monthly_budget(tenant_id: int, db: "Session") -> float:
    """Retorna o teto mensal vigente para o tenant (override > default global)."""
    from app.core.config import settings
    from app.models.tenant import Tenant

    tenant_budget = (
        db.query(Tenant.ai_monthly_budget_usd).filter(Tenant.id == tenant_id).scalar()
    )
    if tenant_budget is not None:
        return float(tenant_budget)
    return float(settings.AI_BUDGET_USD_MONTHLY_PER_TENANT_DEFAULT)


def get_tenant_monthly_spend(tenant_id: int, db: "Session") -> float:
    """Retorna custo acumulado de IA do tenant no mês corrente (UTC)."""
    from sqlalchemy import func

    from app.models.ai_job import AIJob

    start, next_start = _month_window_utc()
    total = (
        db.query(func.coalesce(func.sum(AIJob.cost_usd), 0.0))
        .filter(
            AIJob.tenant_id == tenant_id,
            AIJob.created_at >= start,
            AIJob.created_at < next_start,
        )
        .scalar()
    )
    return float(total or 0.0)


def check_tenant_monthly_budget(tenant_id: int, db: "Session") -> float:
    """
    Valida o teto mensal de IA do tenant. Retorna o custo acumulado no mês.
    Levanta HTTPException 429 se estourou. limit=0 ⇒ ilimitado.
    """
    from fastapi import HTTPException

    limit = get_tenant_monthly_budget(tenant_id, db)
    if limit <= 0:
        return get_tenant_monthly_spend(tenant_id, db)

    spent = get_tenant_monthly_spend(tenant_id, db)
    if spent >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Orçamento mensal de IA excedido: ${spent:.2f}/${limit:.2f} no mês corrente",
        )
    return spent


def _build_model_list(settings) -> list[tuple[str, str]]:
    """Monta lista de (modelo, api_key) em ordem de preferência baseado nas chaves disponíveis."""
    candidates: list[tuple[str, str, str]] = [
        (settings.OPENAI_API_KEY, settings.AI_DEFAULT_MODEL, settings.OPENAI_API_KEY),
        (settings.GEMINI_API_KEY, settings.AI_FALLBACK_MODEL, settings.GEMINI_API_KEY),
        (settings.ANTHROPIC_API_KEY, "claude-haiku-4-5-20251001", settings.ANTHROPIC_API_KEY),
    ]
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for key, model, api_key in candidates:
        if key and model not in seen:
            seen.add(model)
            result.append((model, api_key))
    return result or [(settings.AI_DEFAULT_MODEL, "")]


def complete(
    prompt: str,
    *,
    system: str = "",
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> AIResponse:
    """
    Envia um prompt para o LLM e retorna AIResponse.

    Tenta os modelos em ordem de fallback. Lança AIGatewayError se todos falharem.
    Deve ser chamado somente quando settings.ai_configured == True.
    """
    # Import tardio para evitar erro de import quando IA desabilitada
    import litellm  # noqa: PLC0415

    from app.core.config import settings

    models: list[tuple[str, str]] = [(model, "")] if model else _build_model_list(settings)
    _max_tokens = max_tokens or settings.AI_MAX_TOKENS
    _temperature = temperature if temperature is not None else settings.AI_TEMPERATURE
    _timeout = settings.AI_TIMEOUT_SECONDS

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_error: Optional[str] = None
    for attempt_model, api_key in models:
        try:
            t0 = time.monotonic()
            response = litellm.completion(
                model=attempt_model,
                messages=messages,
                max_tokens=_max_tokens,
                temperature=_temperature,
                timeout=_timeout,
                api_key=api_key or None,
            )
            elapsed_ms = int((time.monotonic() - t0) * 1000)

            content = response.choices[0].message.content or ""
            usage = response.usage or {}
            tokens_in = getattr(usage, "prompt_tokens", 0) or 0
            tokens_out = getattr(usage, "completion_tokens", 0) or 0

            # litellm calcula custo automaticamente quando disponível
            try:
                cost = litellm.completion_cost(completion_response=response) or 0.0
            except Exception:
                cost = 0.0

            provider = attempt_model.split("/")[0] if "/" in attempt_model else attempt_model.split("-")[0]

            logger.info(
                "ai_gateway.complete model=%s tokens_in=%d tokens_out=%d cost_usd=%.6f ms=%d",
                attempt_model, tokens_in, tokens_out, cost, elapsed_ms,
            )

            return AIResponse(
                content=content,
                model_used=attempt_model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost,
                duration_ms=elapsed_ms,
                provider=provider,
            )

        except Exception as exc:
            last_error = str(exc)
            logger.warning("ai_gateway.complete fallback model=%s error=%s", attempt_model, exc)
            continue

    raise AIGatewayError(
        message=f"Todos os providers falharam. Último erro: {last_error}",
        last_error=last_error,
    )
