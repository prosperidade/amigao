"""Testes do AI Gateway — Sprint -1 Tarefas A (Gemini) e B (cost limit per job)."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.ai_gateway import (
    AI_HOURLY_COST_LIMIT_USD,
    AIGatewayError,
    _build_model_list,
    complete,
)

# ---------------------------------------------------------------------------
# Sprint -1 A — ordem da fallback chain
# ---------------------------------------------------------------------------


def _settings_stub(*, openai: str = "", gemini: str = "", anthropic: str = "",
                   default_model: str = "gpt-4o-mini",
                   fallback_model: str = "gemini/gemini-1.5-flash") -> SimpleNamespace:
    return SimpleNamespace(
        OPENAI_API_KEY=openai,
        GEMINI_API_KEY=gemini,
        ANTHROPIC_API_KEY=anthropic,
        AI_DEFAULT_MODEL=default_model,
        AI_FALLBACK_MODEL=fallback_model,
    )


def test_build_model_list_all_keys_populated_orders_openai_gemini_claude():
    """Sprint -1 A: com as 3 keys presentes, ordem é OpenAI → Gemini → Claude Haiku."""
    settings = _settings_stub(openai="sk-proj-abc", gemini="AIza123", anthropic="sk-ant-xyz")

    models = _build_model_list(settings)

    assert [m for m, _ in models] == [
        "gpt-4o-mini",
        "gemini/gemini-1.5-flash",
        "claude-haiku-4-5-20251001",
    ]


def test_build_model_list_when_default_is_gemini_starts_with_gemini():
    """Sprint -1 A: se AI_DEFAULT_MODEL=gemini/..., Gemini lidera a fallback chain."""
    settings = _settings_stub(
        openai="sk-proj-abc",
        gemini="AIza123",
        anthropic="sk-ant-xyz",
        default_model="gemini/gemini-2.0-flash",
        fallback_model="gpt-4o-mini",
    )

    models = _build_model_list(settings)

    assert models[0][0] == "gemini/gemini-2.0-flash"


def test_build_model_list_skips_missing_keys():
    """Keys ausentes são removidas — ordem preserva o resto."""
    settings = _settings_stub(openai="sk-proj-abc", gemini="", anthropic="sk-ant-xyz")

    models = _build_model_list(settings)

    assert [m for m, _ in models] == ["gpt-4o-mini", "claude-haiku-4-5-20251001"]


def test_build_model_list_no_keys_returns_default_placeholder():
    """Nenhuma key: retorna pelo menos o default (litellm decide se falha)."""
    settings = _settings_stub()

    models = _build_model_list(settings)

    assert models == [("gpt-4o-mini", "")]


# ---------------------------------------------------------------------------
# Sprint -1 B — cost limit por job
# ---------------------------------------------------------------------------


def _litellm_response_stub(content: str, tokens_in: int, tokens_out: int):
    """Fabrica uma resposta no formato litellm espera."""
    usage = SimpleNamespace(prompt_tokens=tokens_in, completion_tokens=tokens_out)
    choice = SimpleNamespace(message=SimpleNamespace(content=content))
    return SimpleNamespace(choices=[choice], usage=usage)


def _build_settings_for_complete(**overrides) -> SimpleNamespace:
    s = _settings_stub(openai="sk-proj-abc", **{
        k: v for k, v in overrides.items()
        if k in ("gemini", "anthropic", "default_model", "fallback_model")
    })
    s.AI_MAX_TOKENS = overrides.get("AI_MAX_TOKENS", 2048)
    s.AI_TEMPERATURE = overrides.get("AI_TEMPERATURE", 0.2)
    s.AI_TIMEOUT_SECONDS = overrides.get("AI_TIMEOUT_SECONDS", 30.0)
    s.AI_MAX_COST_PER_JOB_USD = overrides.get("AI_MAX_COST_PER_JOB_USD", 0.10)
    return s


@pytest.fixture
def fake_litellm():
    """Injeta um litellm mock em sys.modules (complete() faz import tardio)."""
    mock = MagicMock()
    saved = sys.modules.get("litellm")
    sys.modules["litellm"] = mock
    try:
        yield mock
    finally:
        if saved is not None:
            sys.modules["litellm"] = saved
        else:
            sys.modules.pop("litellm", None)


def test_cost_limit_per_job_blocks_expensive_call(fake_litellm):
    """Sprint -1 B: job acima de AI_MAX_COST_PER_JOB_USD é bloqueado com AIGatewayError."""
    fake_litellm.completion.return_value = _litellm_response_stub(
        "resposta", tokens_in=100_000, tokens_out=1_000
    )
    fake_litellm.completion_cost.return_value = 1.50  # excede 0.10

    with (
        patch("app.core.config.settings", _build_settings_for_complete()),
        pytest.raises(AIGatewayError) as exc_info,
    ):
        complete("prompt grande", system="você é um oráculo")

    assert "cost" in exc_info.value.message.lower()
    assert exc_info.value.cost_usd == pytest.approx(1.50)
    assert exc_info.value.tokens_in == 100_000
    assert exc_info.value.tokens_out == 1_000


def test_cost_limit_per_job_allows_cheap_call(fake_litellm):
    """Sprint -1 B: job abaixo do limite passa normalmente."""
    fake_litellm.completion.return_value = _litellm_response_stub(
        "ok", tokens_in=200, tokens_out=50
    )
    fake_litellm.completion_cost.return_value = 0.005

    with patch("app.core.config.settings", _build_settings_for_complete()):
        result = complete("prompt pequeno")

    assert result.content == "ok"
    assert result.cost_usd == pytest.approx(0.005)


def test_cost_limit_skipped_when_cost_is_zero_or_none(fake_litellm):
    """Se litellm não retornar custo (cost=0.0), não bloqueia — apenas loga."""
    fake_litellm.completion.return_value = _litellm_response_stub(
        "ok", tokens_in=100, tokens_out=20
    )
    fake_litellm.completion_cost.return_value = 0.0  # provider sem tabela de preço

    with patch("app.core.config.settings", _build_settings_for_complete()):
        result = complete("prompt")

    assert result.content == "ok"
    assert result.cost_usd == 0.0


# ---------------------------------------------------------------------------
# Constantes / contratos
# ---------------------------------------------------------------------------


def test_hourly_cost_limit_constant_is_documented_value():
    """Contrato documentado no CONTEXTO_ARQUITETURAL: 5.0 USD/hora por tenant."""
    assert AI_HOURLY_COST_LIMIT_USD == 5.0
