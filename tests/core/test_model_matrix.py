"""Testes da matriz de equivalência agente×provider — fix/llm-consistencia (2026-06-07)."""

from __future__ import annotations

from types import SimpleNamespace

from app.core.model_matrix import (
    available_house_providers,
    provider_of,
    resolve_agent_models,
)


def _settings(*, openai="", gemini="", anthropic="") -> SimpleNamespace:
    # Só as chaves; o resto vem por getattr-default em build_agent_model_matrix.
    return SimpleNamespace(
        OPENAI_API_KEY=openai,
        GEMINI_API_KEY=gemini,
        ANTHROPIC_API_KEY=anthropic,
    )


# ---------------------------------------------------------------------------
# provider_of / available_house_providers
# ---------------------------------------------------------------------------

def test_provider_of_infers_from_model_name():
    assert provider_of("gpt-4.1") == "openai"
    assert provider_of("gpt-4o-mini") == "openai"
    assert provider_of("gemini/gemini-2.5-flash") == "google"
    assert provider_of("claude-sonnet-4-20250514") == "anthropic"
    assert provider_of("anthropic/claude-haiku-4-5-20251001") == "anthropic"
    assert provider_of("deepseek-chat") == "deepseek"


def test_available_house_providers_only_present_keys():
    avail = available_house_providers(_settings(openai="sk", anthropic="sk-ant"))
    assert set(avail) == {"openai", "anthropic"}
    assert avail["openai"] == "sk"


# ---------------------------------------------------------------------------
# resolve_agent_models — primário preservado + fallback entre disponíveis
# ---------------------------------------------------------------------------

def test_primary_preserved_first_then_equivalents():
    """Diagnóstico com as 3 chaves: primário (gpt-4.1) em 1º, depois equivalentes
    em OUTROS providers (gemini-pro, claude). Primário NUNCA é trocado."""
    models = resolve_agent_models(
        "diagnostico", _settings(openai="sk-o", gemini="sk-g", anthropic="sk-a"),
        primary_model="gpt-4.1",
    )
    names = [m for m, _ in models]
    assert names[0] == "gpt-4.1"  # primário preservado em 1º
    assert any("gemini" in n for n in names[1:])
    assert any(n.startswith("claude") for n in names[1:])
    # cada provider aparece 1×
    assert len(names) == 3


def test_fallback_restricted_to_available_providers():
    """Só openai+gemini disponíveis → anthropic não entra na cadeia."""
    models = resolve_agent_models(
        "legislacao", _settings(openai="sk-o", gemini="sk-g"),
        primary_model="gemini/gemini-2.5-flash",
    )
    names = [m for m, _ in models]
    assert names[0] == "gemini/gemini-2.5-flash"  # primário
    assert any(n == "gpt-4.1-mini" for n in names)  # equivalente openai
    assert not any(n.startswith("claude") for n in names)  # anthropic indisponível


def test_single_provider_tenant_resolves_without_error():
    """BYOK provider único (só Anthropic): primário OpenAI indisponível →
    resolve pro equivalente Anthropic. 1 modelo, sem erro de config."""
    models = resolve_agent_models(
        "diagnostico", _settings(anthropic="sk-a"), primary_model="gpt-4.1",
    )
    assert len(models) == 1
    name, key = models[0]
    assert name.startswith("claude")
    assert key == "sk-a"


def test_no_keys_does_not_explode():
    """Nenhuma chave da casa → devolve o primário/placeholder sem key (litellm
    decide se falha), em vez de estourar a resolução."""
    models = resolve_agent_models("diagnostico", _settings(), primary_model="gpt-4.1")
    assert models == [("gpt-4.1", "")]


def test_unknown_agent_uses_default_row():
    """Agente sem linha dedicada cai na linha default (não quebra)."""
    models = resolve_agent_models(
        "agente_inexistente", _settings(openai="sk-o"), primary_model=None,
    )
    names = [m for m, _ in models]
    assert names and names[0]  # resolveu algo do default
