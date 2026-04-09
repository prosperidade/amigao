"""
ClaudeClient — client direto Anthropic SDK para raciocinio juridico.

Usa anthropic SDK diretamente (nao litellm) para controle fino do modelo
e rastreabilidade de custo. Retorna AIResponse compativel com o sistema de agentes.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from app.core.ai_gateway import AIResponse
from app.core.config import settings

logger = logging.getLogger(__name__)

# Custo por 1M tokens (claude-sonnet-4-20250514)
_COSTS = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
}


class ClaudeClient:
    """Client direto para Anthropic Claude via SDK."""

    def __init__(self) -> None:
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY nao configurada")

        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        except ImportError:
            raise RuntimeError("Pacote 'anthropic' nao instalado — pip install anthropic")

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
    ) -> AIResponse:
        """Envia prompt ao Claude e retorna AIResponse compativel."""
        model = model or settings.CLAUDE_LEGAL_MODEL
        max_tokens = max_tokens or settings.CLAUDE_LEGAL_MAX_TOKENS
        temperature = temperature if temperature is not None else settings.CLAUDE_LEGAL_TEMPERATURE

        start = time.perf_counter()

        messages = [{"role": "user", "content": prompt}]

        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        response = self._client.messages.create(**kwargs)

        duration_ms = int((time.perf_counter() - start) * 1000)

        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens

        # Calcular custo
        cost_table = _COSTS.get(model, {"input": 3.0, "output": 15.0})
        cost_usd = (
            (tokens_in / 1_000_000) * cost_table["input"]
            + (tokens_out / 1_000_000) * cost_table["output"]
        )

        logger.info(
            "claude complete: model=%s, tokens_in=%d, tokens_out=%d, cost=$%.4f, duration=%dms",
            model, tokens_in, tokens_out, cost_usd, duration_ms,
        )

        return AIResponse(
            content=content,
            model_used=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=round(cost_usd, 6),
            duration_ms=duration_ms,
            provider="anthropic",
        )
