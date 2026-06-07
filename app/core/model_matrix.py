"""
Matriz de equivalência agente × provider (fix/llm-consistencia 2026-06-07).

PROBLEMA QUE RESOLVE
--------------------
Agentes que passavam ``model=`` explícito ao gateway (diagnostico, legislacao)
rodavam num ÚNICO modelo, sem cadeia de fallback: um 503/timeout do provider
derrubava a execução inteira ("uma hora vai, outra não"). Além disso, o produto
é BYOK — o consultor configura as PRÓPRIAS chaves e pode ter UM provider só
(Anthropic, OpenAI OU Gemini). Modelos hardcoded por agente quebram nesse modelo.

COMO FUNCIONA
-------------
Cada agente declara, em ordem de preferência, o modelo equivalente em CADA
provider. Em runtime resolvemos:

    providers disponíveis (chaves presentes)
      → modelo PREFERIDO do agente que esteja disponível (primário preservado)
      → fallback de resiliência APENAS entre os providers disponíveis.

Se o tenant/casa tem só 1 provider, todos os agentes rodam nele, sem erro de
config. O modelo PRIMÁRIO de cada agente é preservado (vem das settings) — esta
matriz só ACRESCENTA equivalentes para fallback, nunca troca o primário.

Todos os modelos saem de ``settings`` (env-configurável) — nada hardcoded aqui,
para que o próximo deprecation de modelo seja troca de variável, não de código
(lição: gemini-2.0-flash descontinuado quebrou o sistema 2×).

EMBEDDINGS
----------
Anthropic NÃO tem API de embeddings. Embeddings continuam resolvidos por
``EMBEDDING_PROVIDER`` (OpenAI/Gemini, chave da casa) — esta matriz cobre só
geração de texto. Ver docs/trabalhos/llm_consistencia.md.
"""

from __future__ import annotations

from typing import Optional

# Providers da CASA suportados nesta matriz (têm chave própria nas settings).
# DeepSeek e outros providers BYOK chegam pela rota user_preferences do gateway,
# não por esta matriz.
_HOUSE_PROVIDERS = ("openai", "google", "anthropic")


def provider_of(model: str) -> str:
    """Infere o provider a partir do nome do modelo (convenção LiteLLM)."""
    m = (model or "").lower()
    if m.startswith("gemini/") or m.startswith("google/"):
        return "google"
    if m.startswith("anthropic/") or m.startswith("claude"):
        return "anthropic"
    if m.startswith("deepseek"):
        return "deepseek"
    # gpt-*, o1-*, openai/* e default
    return "openai"


def available_house_providers(settings) -> dict[str, str]:
    """Mapeia provider da casa → api_key, apenas para chaves realmente presentes."""
    keys = {
        "openai": getattr(settings, "OPENAI_API_KEY", "") or "",
        "google": getattr(settings, "GEMINI_API_KEY", "") or "",
        "anthropic": getattr(settings, "ANTHROPIC_API_KEY", "") or "",
    }
    return {p: k for p, k in keys.items() if k}


def build_agent_model_matrix(settings) -> dict[str, list[tuple[str, str]]]:
    """Monta a matriz agente → [(provider, modelo), ...] em ordem de preferência.

    Todos os modelos vêm de settings (env-configurável). A ordem de cada linha é
    a ordem de preferência GLOBAL do agente (primeiro = primário preferido).
    """
    openai_cheap = getattr(settings, "AI_DEFAULT_MODEL", "gpt-4o-mini")
    gemini_flash = getattr(settings, "GEMINI_LEGAL_MODEL", "gemini/gemini-2.5-flash")
    gemini_pro = getattr(settings, "GEMINI_LEGAL_LONG_MODEL", "gemini/gemini-2.5-pro")
    claude_mid = getattr(settings, "CLAUDE_LEGAL_MODEL", "claude-sonnet-4-20250514")
    claude_cheap = getattr(settings, "AI_HAIKU_MODEL", "claude-haiku-4-5-20251001")
    diag_openai = getattr(settings, "AI_DIAGNOSTICO_MODEL", "gpt-4.1") or openai_cheap
    legal_openai = getattr(settings, "AI_LEGAL_MODEL_OPENAI", "gpt-4.1-mini")

    # Agentes "pesados" (raciocínio complexo): preferem modelos capazes.
    heavy = [("openai", diag_openai), ("google", gemini_pro), ("anthropic", claude_mid)]
    # Agentes "econômicos" (extração/classificação/rotina): modelos baratos.
    cheap = [("openai", openai_cheap), ("google", gemini_flash), ("anthropic", claude_cheap)]

    return {
        "diagnostico": heavy,
        "redator": heavy,
        "legislacao": [
            ("google", gemini_flash),
            ("openai", legal_openai),
            ("anthropic", claude_mid),
        ],
        "extrator": cheap,
        "atendimento": cheap,
        "vigia": cheap,
        "auditor_imovel": cheap,
        "financeiro": cheap,
        "acompanhamento": cheap,
        "marketing": cheap,
        "orcamento": cheap,
    }


def _default_row(settings) -> list[tuple[str, str]]:
    return [
        ("openai", getattr(settings, "AI_DEFAULT_MODEL", "gpt-4o-mini")),
        ("google", getattr(settings, "GEMINI_LEGAL_MODEL", "gemini/gemini-2.5-flash")),
        ("anthropic", getattr(settings, "AI_HAIKU_MODEL", "claude-haiku-4-5-20251001")),
    ]


def resolve_agent_models(
    agent_name: str,
    settings,
    *,
    primary_model: Optional[str] = None,
) -> list[tuple[str, str]]:
    """Resolve a lista ordenada de (modelo_litellm, api_key) para um agente.

    Regras:
      - Restringe aos providers da casa com chave disponível.
      - Se ``primary_model`` é dado e seu provider está disponível, ele vem
        PRIMEIRO (preserva o primário do agente — esta matriz só adiciona
        fallback, nunca troca o primário).
      - Depois, os equivalentes do agente em OUTROS providers disponíveis,
        na ordem de preferência da matriz, sem duplicar.
      - Se NENHUM provider da casa tem chave, devolve o primário/placeholder
        sem key (litellm decide se falha) — não explode resolução.
    """
    available = available_house_providers(settings)
    matrix = build_agent_model_matrix(settings)
    row = matrix.get(agent_name) or _default_row(settings)

    ordered: list[tuple[str, str]] = []
    seen_models: set[str] = set()
    used_providers: set[str] = set()

    # 1) Primário preferido do agente (preservado), se seu provider tem chave.
    if primary_model:
        prov = provider_of(primary_model)
        if prov in available:
            ordered.append((primary_model, available[prov]))
            seen_models.add(primary_model)
            used_providers.add(prov)

    # 2) Equivalentes da matriz nos providers disponíveis (resiliência).
    for prov, model in row:
        if prov not in available or prov in used_providers or model in seen_models:
            continue
        ordered.append((model, available[prov]))
        seen_models.add(model)
        used_providers.add(prov)

    if ordered:
        return ordered

    # 3) Nenhuma chave da casa: não explode — devolve primário/placeholder.
    fallback = primary_model or row[0][1]
    return [(fallback, "")]
