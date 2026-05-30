"""
Serviço de preferências de IA do usuário (white label — André 2026-05-28).

O grupo `ai` em `User.preferences` (JSONB) ganhou provider/model/api_key. A chave
é criptografada (ADR-014) ANTES de gravar e nunca volta em plaintext. Como o
storage é JSONB (não coluna String), não dá pra usar `EncryptedString` direto —
usamos `encrypt_str`/`decrypt_str` na borda do service.

Invariantes:
  - `preferences['ai']['api_key_encrypted']` guarda o ciphertext (única forma persistida).
  - `api_key` (plaintext) NUNCA é gravado nem retornado.
  - Save sem `api_key` preserva o `api_key_encrypted` existente (não apaga).
"""
from __future__ import annotations

from typing import Any, Optional

from app.core.encryption import decrypt_str, encrypt_str


# Lookup table de modelos por provider (hardcoded — ajustar ao trocar provider chinês).
AVAILABLE_MODELS: dict[str, list[str]] = {
    "anthropic": [
        "claude-sonnet-4-20250514",
        "claude-haiku-4-5-20251001",
        "claude-opus-4-20250514",
    ],
    "google": ["gemini-2.5-flash", "gemini-2.5-pro"],
    "openai": ["gpt-4o-mini", "gpt-4o"],
    "deepseek": ["deepseek-chat", "deepseek-reasoner"],
}

# Campos comportamentais + provider/model que persistem em plaintext no JSONB.
_AI_PLAIN_KEYS = {
    "assistance_level",
    "summary_length",
    "show_suggestions_in_flow",
    "show_auto_summaries",
    "require_human_validation_before_advance",
    "save_ai_readings_history",
    "provider",
    "model",
}
# Campos que NUNCA são persistidos (write-only ou só-saída).
_AI_TRANSIENT_KEYS = {"api_key", "api_key_masked", "api_key_set"}


def save_ai_preferences(stored_ai: Optional[dict], ai_patch: Optional[dict]) -> dict:
    """Reconcilia o grupo `ai` preservando `api_key_encrypted`.

    Recebe o dict `ai` já gravado e o patch vindo do PATCH. Devolve o dict a
    persistir (com `api_key_encrypted`, sem plaintext).
    """
    result = dict(stored_ai or {})
    for k in _AI_TRANSIENT_KEYS:
        result.pop(k, None)
    if not ai_patch:
        return result
    for key, value in ai_patch.items():
        if key in _AI_PLAIN_KEYS:
            result[key] = value
    new_key = (ai_patch.get("api_key") or "").strip()
    if new_key:
        result["api_key_encrypted"] = encrypt_str(new_key)
    return result


def _decrypt_api_key(stored_ai: Optional[dict]) -> Optional[str]:
    enc = (stored_ai or {}).get("api_key_encrypted")
    if not enc:
        return None
    try:
        return decrypt_str(enc)
    except Exception:
        return None


def public_ai(stored_ai: Optional[dict]) -> dict:
    """Versão do grupo `ai` para SAÍDA: sem plaintext, com masked + flag."""
    stored_ai = stored_ai or {}
    out: dict[str, Any] = {
        k: v
        for k, v in stored_ai.items()
        if k not in _AI_TRANSIENT_KEYS and k != "api_key_encrypted"
    }
    key = _decrypt_api_key(stored_ai)
    out["api_key"] = None
    out["api_key_masked"] = (f"…{key[-4:]}" if key and len(key) >= 4 else ("****" if key else None))
    out["api_key_set"] = bool(key)
    return out


def preferences_for_output(raw_prefs: Optional[dict]) -> dict:
    """Prefs completas para resposta de API com o grupo `ai` mascarado."""
    raw = dict(raw_prefs or {})
    raw["ai"] = public_ai(raw.get("ai"))
    return raw


def get_ai_runtime(user) -> Optional[dict]:
    """Para o gateway LLM: {provider, model, api_key} decifrado, ou None se
    a configuração do usuário estiver incompleta (cai no default global)."""
    stored = ((user.preferences or {}).get("ai")) or {}
    key = _decrypt_api_key(stored)
    provider = stored.get("provider")
    model = stored.get("model")
    if provider and model and key:
        return {"provider": provider, "model": model, "api_key": key}
    return None
