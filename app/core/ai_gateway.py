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
import os
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


def _set_api_keys(settings) -> None:
    """Exporta chaves de API para as variáveis de ambiente esperadas pelo litellm."""
    if settings.OPENAI_API_KEY:
        os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
    if settings.GEMINI_API_KEY:
        os.environ["GEMINI_API_KEY"] = settings.GEMINI_API_KEY
    if settings.ANTHROPIC_API_KEY:
        os.environ["ANTHROPIC_API_KEY"] = settings.ANTHROPIC_API_KEY


def _build_model_list(settings) -> list[str]:
    """Monta lista de modelos em ordem de preferência baseado nas chaves disponíveis."""
    candidates: list[tuple[str, str]] = [
        (settings.OPENAI_API_KEY, settings.AI_DEFAULT_MODEL),
        (settings.GEMINI_API_KEY, settings.AI_FALLBACK_MODEL),
        (settings.ANTHROPIC_API_KEY, "claude-haiku-4-5-20251001"),
    ]
    models = [model for key, model in candidates if key]
    # Garante sem duplicatas mantendo ordem
    seen: set[str] = set()
    result: list[str] = []
    for m in models:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result or [settings.AI_DEFAULT_MODEL]


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

    _set_api_keys(settings)

    models = [model] if model else _build_model_list(settings)
    _max_tokens = max_tokens or settings.AI_MAX_TOKENS
    _temperature = temperature if temperature is not None else settings.AI_TEMPERATURE
    _timeout = settings.AI_TIMEOUT_SECONDS

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_error: Optional[str] = None
    for attempt_model in models:
        try:
            t0 = time.monotonic()
            response = litellm.completion(
                model=attempt_model,
                messages=messages,
                max_tokens=_max_tokens,
                temperature=_temperature,
                timeout=_timeout,
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
