"""Testes do AI Gateway — Sprint -1 Tarefas A (Gemini) e B (cost limit per job)."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.ai_gateway import (
    AI_HOURLY_COST_LIMIT_USD,
    AIGatewayError,
    AITruncationError,
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
    """Sprint -1 A: com as 3 keys presentes, ordem é OpenAI → Gemini → Claude (Sonnet 5 desde 21/09)."""
    settings = _settings_stub(openai="sk-proj-abc", gemini="AIza123", anthropic="sk-ant-xyz")

    models = _build_model_list(settings)

    assert [m for m, _ in models] == [
        "gpt-4o-mini",
        "gemini/gemini-1.5-flash",
        "claude-sonnet-5",
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

    assert [m for m, _ in models] == ["gpt-4o-mini", "claude-sonnet-5"]


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
    s.AI_MAX_RETRIES = overrides.get("AI_MAX_RETRIES", 2)
    s.AI_RETRY_BACKOFF_SECONDS = overrides.get("AI_RETRY_BACKOFF_SECONDS", 0.0)
    s.AI_MAX_COST_PER_JOB_USD = overrides.get("AI_MAX_COST_PER_JOB_USD", 0.10)
    s.AI_MAX_TOKENS_CEILING = overrides.get("AI_MAX_TOKENS_CEILING", 32_768)
    return s


def _litellm_response_fr(content: str, tokens_in: int, tokens_out: int, finish_reason: str):
    """Como _litellm_response_stub, mas com finish_reason no choice (fix/llm-consistencia)."""
    usage = SimpleNamespace(prompt_tokens=tokens_in, completion_tokens=tokens_out)
    choice = SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], usage=usage)


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


def test_cost_limit_skipped_when_computed_cost_is_zero(fake_litellm):
    """Custo CALCULADO zero (preço declarado zero) não bloqueia. Preço desconhecido
    não chega aqui: falha antes da chamada (dívida #256, testes abaixo)."""
    fake_litellm.completion.return_value = _litellm_response_stub(
        "ok", tokens_in=100, tokens_out=20
    )
    fake_litellm.completion_cost.return_value = 0.0

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


# ---------------------------------------------------------------------------
# White label — provider plugável por consultor (André 2026-05-28)
# ---------------------------------------------------------------------------


def test_complete_uses_user_provider_model_and_key(fake_litellm):
    """complete(user_preferences=...) usa provider/modelo/chave do usuário."""
    fake_litellm.completion.return_value = _litellm_response_stub("ok", 100, 20)
    fake_litellm.completion_cost.return_value = 0.001

    with patch("app.core.config.settings", _build_settings_for_complete()):
        complete(
            "prompt",
            user_preferences={"provider": "openai", "model": "gpt-4o", "api_key": "sk-user-key"},
        )

    _, kwargs = fake_litellm.completion.call_args
    assert kwargs["model"] == "openai/gpt-4o"
    assert kwargs["api_key"] == "sk-user-key"


def test_complete_user_none_falls_back_to_global(fake_litellm):
    """Sem user_preferences, usa a cadeia global (default model das settings)."""
    fake_litellm.completion.return_value = _litellm_response_stub("ok", 100, 20)
    fake_litellm.completion_cost.return_value = 0.001

    with patch("app.core.config.settings", _build_settings_for_complete()):
        complete("prompt", user_preferences=None)

    _, kwargs = fake_litellm.completion.call_args
    assert kwargs["model"] == "gpt-4o-mini"  # default global


def test_complete_incomplete_user_pref_falls_back_to_global(fake_litellm):
    """Pref do usuário sem api_key → ignora e usa global (não meio-configura)."""
    fake_litellm.completion.return_value = _litellm_response_stub("ok", 10, 5)
    fake_litellm.completion_cost.return_value = 0.0

    with patch("app.core.config.settings", _build_settings_for_complete()):
        complete("prompt", user_preferences={"provider": "openai", "model": "gpt-4o"})

    _, kwargs = fake_litellm.completion.call_args
    assert kwargs["model"] == "gpt-4o-mini"


def test_complete_user_auth_error_does_not_fallback_global(fake_litellm):
    """Falha de AUTH com a chave do consultor NÃO cai no fallback global."""
    fake_litellm.completion.side_effect = Exception("AuthenticationError: invalid api key")

    with (
        patch("app.core.config.settings", _build_settings_for_complete(gemini="AIza", anthropic="sk-ant")),
        pytest.raises(AIGatewayError) as exc_info,
    ):
        complete(
            "prompt",
            user_preferences={"provider": "deepseek", "model": "deepseek-chat", "api_key": "sk-bad"},
        )

    # mensagem clara + só UMA tentativa (não tentou os providers globais)
    assert "Credenciais de IA do consultor inválidas" in exc_info.value.message
    assert fake_litellm.completion.call_count == 1


# ---------------------------------------------------------------------------
# Item D (teste Isis rodada 1) — retry para erros transitórios + timeout são
# ---------------------------------------------------------------------------

def test_transient_error_retries_then_succeeds(fake_litellm):
    """Timeout transitório (ex.: legislação) NÃO derruba a chamada: retry com
    backoff e na 3ª tentativa retorna. Cobre o caso `model=` explícito (1 só
    modelo, sem cadeia de fallback)."""
    timeout_err = type("Timeout", (Exception,), {})
    fake_litellm.Timeout = timeout_err
    fake_litellm.completion.side_effect = [
        timeout_err("Connection timed out"),
        timeout_err("Connection timed out"),
        _litellm_response_stub("base legal ok", 100, 20),
    ]
    fake_litellm.completion_cost.return_value = 0.001

    with (
        patch("app.core.config.settings", _build_settings_for_complete()),
        patch("app.core.ai_gateway.time.sleep") as sleep_mock,
    ):
        result = complete("consulta legislacao", model="gpt-4o-mini")

    assert result.content == "base legal ok"
    # 1 inicial + 2 retries: a 3ª venceu
    assert fake_litellm.completion.call_count == 3
    assert sleep_mock.call_count == 2
    # timeout explícito (NUNCA None) chega ao litellm — prova contra
    # "Connection timed out after None seconds"
    _, kwargs = fake_litellm.completion.call_args
    assert kwargs["timeout"] == 30.0


def test_transient_error_exhausts_retries_then_raises(fake_litellm):
    """Se o erro transitório persiste além do teto de retries, propaga como
    AIGatewayError (não fica em loop infinito)."""
    timeout_err = type("Timeout", (Exception,), {})
    fake_litellm.Timeout = timeout_err
    fake_litellm.completion.side_effect = timeout_err("sempre indisponível")

    with (
        patch("app.core.config.settings", _build_settings_for_complete(AI_MAX_RETRIES=2)),
        patch("app.core.ai_gateway.time.sleep"),
        pytest.raises(AIGatewayError),
    ):
        complete("consulta", model="gpt-4o-mini")

    # 1 inicial + 2 retries = 3 tentativas no único modelo
    assert fake_litellm.completion.call_count == 3


def test_timeout_falsy_setting_defaults_to_30(fake_litellm):
    """Blindagem: AI_TIMEOUT_SECONDS None/0 não vira `timeout=None` no litellm."""
    fake_litellm.completion.return_value = _litellm_response_stub("ok", 10, 2)
    fake_litellm.completion_cost.return_value = 0.0

    with patch(
        "app.core.config.settings",
        _build_settings_for_complete(AI_TIMEOUT_SECONDS=0),
    ):
        complete("prompt", model="gpt-4o-mini")

    _, kwargs = fake_litellm.completion.call_args
    assert kwargs["timeout"] == 30.0


# ---------------------------------------------------------------------------
# fix/llm-consistencia — Item 1: finish_reason + truncamento
# ---------------------------------------------------------------------------

def test_finish_reason_is_captured(fake_litellm):
    """O finish_reason do provider é capturado e exposto no AIResponse."""
    fake_litellm.completion.return_value = _litellm_response_fr("ok", 100, 20, "stop")
    fake_litellm.completion_cost.return_value = 0.001

    with patch("app.core.config.settings", _build_settings_for_complete()):
        result = complete("prompt", model="gpt-4o-mini")

    assert result.finish_reason == "stop"


def test_truncation_retries_with_bigger_max_tokens_then_succeeds(fake_litellm):
    """finish_reason=length → 1 retry automático com max_tokens MAIOR; se a 2ª
    fechar, retorna normalmente (não vira erro)."""
    fake_litellm.completion.side_effect = [
        _litellm_response_fr("{trunca", 100, 2048, "length"),
        _litellm_response_fr('{"ok": true}', 100, 800, "stop"),
    ]
    fake_litellm.completion_cost.return_value = 0.001

    with patch(
        "app.core.config.settings",
        _build_settings_for_complete(AI_MAX_TOKENS=2048, AI_MAX_TOKENS_CEILING=8192),
    ):
        result = complete("prompt grande", model="gpt-4.1")

    assert result.content == '{"ok": true}'
    assert result.finish_reason == "stop"
    assert fake_litellm.completion.call_count == 2
    # 1ª chamada com 2048, 2ª com o dobro (4096)
    first_mt = fake_litellm.completion.call_args_list[0].kwargs["max_tokens"]
    second_mt = fake_litellm.completion.call_args_list[1].kwargs["max_tokens"]
    assert first_mt == 2048
    assert second_mt == 4096


def test_persistent_truncation_raises_specific_error(fake_litellm):
    """Se trunca mesmo no teto → AITruncationError com mensagem ESPECÍFICA e
    legível (distinta do erro de parse). NÃO cascateia pra outro provider."""
    fake_litellm.completion.return_value = _litellm_response_fr("{trunca", 100, 4096, "length")
    fake_litellm.completion_cost.return_value = 0.001

    with (
        patch(
            "app.core.config.settings",
            _build_settings_for_complete(
                gemini="AIza", anthropic="sk-ant",
                AI_MAX_TOKENS=2048, AI_MAX_TOKENS_CEILING=4096,
            ),
        ),
        pytest.raises(AITruncationError) as exc_info,
    ):
        complete("prompt enorme", model="gpt-4.1")

    assert "truncada" in exc_info.value.message.lower()
    assert "limite de tokens" in exc_info.value.message.lower()
    # 2048 → 4096 (teto), ainda length → para. Só o modelo primário foi tentado
    # (não cascateou pro gemini/anthropic — o teto seria o mesmo).
    assert fake_litellm.completion.call_count == 2


# ---------------------------------------------------------------------------
# fix/llm-consistencia — Item 2: matriz/fallback por agente (agent_name)
# ---------------------------------------------------------------------------

def test_agent_name_falls_back_to_equivalent_provider_on_503(fake_litellm):
    """Legislação refém do Gemini: com agent_name, um 503 do primário (Gemini)
    cai pro equivalente OpenAI disponível — antes derrubava a consulta."""
    svc_err = type("ServiceUnavailableError", (Exception,), {})
    fake_litellm.ServiceUnavailableError = svc_err
    fake_litellm.completion.side_effect = [
        svc_err("503 model overloaded"),          # Gemini (primário) cai
        _litellm_response_fr("base legal ok", 100, 50, "stop"),  # OpenAI equivalente
    ]
    fake_litellm.completion_cost.return_value = 0.001

    s = _build_settings_for_complete(gemini="AIza", AI_MAX_RETRIES=0)
    s.AI_LEGAL_MODEL_OPENAI = "gpt-5.6-luna"
    with patch("app.core.config.settings", s):
        result = complete(
            "consulta legislacao",
            model="gemini/gemini-2.5-flash",
            agent_name="legislacao",
        )

    assert result.content == "base legal ok"
    # caiu pro 2º modelo da matriz (OpenAI, Luna desde 21/09)
    assert result.model_used == "gpt-5.6-luna"
    assert fake_litellm.completion.call_count == 2


def test_agent_name_single_provider_does_not_error(fake_litellm):
    """BYOK de provider único (só Anthropic): o agente roda nele sem erro de
    config — a matriz restringe aos providers disponíveis."""
    fake_litellm.completion.return_value = _litellm_response_fr("ok", 10, 5, "stop")
    fake_litellm.completion_cost.return_value = 0.0

    s = _build_settings_for_complete(AI_MAX_RETRIES=0)
    s.OPENAI_API_KEY = ""        # sem OpenAI
    s.GEMINI_API_KEY = ""        # sem Gemini
    s.ANTHROPIC_API_KEY = "sk-ant-only"  # só Anthropic
    with patch("app.core.config.settings", s):
        result = complete("diagnostico", model="gpt-4.1", agent_name="diagnostico")

    # primário (gpt-4.1/OpenAI) indisponível → resolveu pro equivalente Anthropic
    assert result.model_used.startswith("claude")
    _, kwargs = fake_litellm.completion.call_args
    assert kwargs["api_key"] == "sk-ant-only"


def test_extrator_luna_failure_never_calls_another_provider(fake_litellm):
    fake_litellm.completion.side_effect = RuntimeError("controlled provider failure")
    config = _build_settings_for_complete(gemini="google-key", anthropic="anthropic-key", AI_MAX_RETRIES=0)
    with patch("app.core.config.settings", config), pytest.raises(AIGatewayError):
        complete("controlled", model="gpt-5.6-luna", agent_name="extrator", allow_fallback=False)
    assert fake_litellm.completion.call_count == 1
    assert fake_litellm.completion.call_args.kwargs["model"] == "gpt-5.6-luna"


def test_extrator_luna_missing_key_fails_before_provider(fake_litellm):
    config = _build_settings_for_complete(gemini="google-key")
    config.OPENAI_API_KEY = ""
    with patch("app.core.config.settings", config), pytest.raises(AIGatewayError):
        complete("controlled", model="gpt-5.6-luna", agent_name="extrator", allow_fallback=False)
    fake_litellm.completion.assert_not_called()


# Both refusals seen on 21/09/2026: LiteLLM's local check (model unknown to its map) and
# the OpenAI 400 when LiteLLM knows the model and lets the request through.
TEMPERATURE_REFUSALS = [
    ("UnsupportedParamsError", "gpt-5 models don't support temperature=0. Only temperature=1 is supported."),
    ("BadRequestError", "OpenAIException - Unsupported value: 'temperature' does not support 0 with this model. "
                        "Only the default (1) value is supported."),
]


@pytest.mark.parametrize("model", ["gpt-5.6-luna", "gpt-5.6-terra"])
@pytest.mark.parametrize("refusal", TEMPERATURE_REFUSALS, ids=[r[0] for r in TEMPERATURE_REFUSALS])
def test_gpt5_family_temperature_adapts_from_the_refusal(fake_litellm, monkeypatch, model, refusal):
    from app.core import ai_gateway
    monkeypatch.setattr(ai_gateway, "_SO_TEMPERATURA_PADRAO", set())
    error = type(refusal[0], (Exception,), {})
    setattr(fake_litellm, refusal[0], error)

    def completion(**kwargs):
        if kwargs["temperature"] != 1:
            raise error(refusal[1])
        return _litellm_response_fr('{"ok":true}', 10, 5, "stop")
    fake_litellm.completion.side_effect = completion
    fake_litellm.completion_cost.return_value = 0.0001
    config = _build_settings_for_complete()
    config.AI_EXTRATOR_MODEL = model
    with patch("app.core.config.settings", config):
        for _ in range(2):
            result = complete("controlled", model=model, agent_name="extrator", allow_fallback=False, temperature=0)
    assert result.model_used == model
    # Refused once, then the process remembers the model.
    assert [c.kwargs["temperature"] for c in fake_litellm.completion.call_args_list] == [0, 1, 1]


def test_unsupported_param_other_than_temperature_is_not_retried(fake_litellm, monkeypatch):
    from app.core import ai_gateway
    monkeypatch.setattr(ai_gateway, "_SO_TEMPERATURA_PADRAO", set())

    class UnsupportedParamsError(Exception):
        pass
    fake_litellm.UnsupportedParamsError = UnsupportedParamsError
    fake_litellm.completion.side_effect = UnsupportedParamsError("max_tokens is not supported")
    with patch("app.core.config.settings", _build_settings_for_complete()), pytest.raises(AIGatewayError):
        complete("controlled", model="gpt-5.6-luna", agent_name="extrator", allow_fallback=False, temperature=0)
    assert fake_litellm.completion.call_count == 1


def test_model_without_price_fails_before_the_call(fake_litellm):
    """Dívida #256: sem preço o custo sairia zero e o teto por job não atuaria."""
    fake_litellm.get_model_info.return_value = {"litellm_provider": "openai"}
    with (patch("app.core.config.settings", _build_settings_for_complete()),
          pytest.raises(AIGatewayError) as caught):
        complete("prompt", model="gpt-sem-preco")
    assert caught.value.message.startswith("Modelo sem preço na tabela local: gpt-sem-preco")
    fake_litellm.completion.assert_not_called()


def test_cost_not_computed_is_an_error_not_zero(fake_litellm):
    fake_litellm.completion.return_value = _litellm_response_stub("ok", tokens_in=100, tokens_out=20)
    fake_litellm.completion_cost.side_effect = ValueError("model not mapped")
    with (patch("app.core.config.settings", _build_settings_for_complete()),
          pytest.raises(AIGatewayError) as caught):
        complete("prompt")
    assert caught.value.message.startswith("Custo não calculado")
    assert (caught.value.tokens_in, caught.value.tokens_out) == (100, 20)
