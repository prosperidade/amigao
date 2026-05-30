"""
Testes do serviço de preferências de IA (white label — provider por consultor).

Foco: a api_key do consultor é criptografada antes de gravar, nunca volta em
plaintext, e um save sem api_key preserva a chave existente.
"""
from app.core.encryption import decrypt_str
from app.services.user_preferences import (
    AVAILABLE_MODELS,
    get_ai_runtime,
    public_ai,
    save_ai_preferences,
)


class _FakeUser:
    def __init__(self, prefs):
        self.preferences = prefs


def test_save_encrypts_api_key_and_drops_plaintext():
    saved = save_ai_preferences(
        {}, {"provider": "openai", "model": "gpt-4o", "api_key": "sk-secret-abcd"}
    )
    # plaintext nunca persiste; só o ciphertext
    assert "api_key" not in saved
    assert "api_key_encrypted" in saved
    assert saved["api_key_encrypted"] != "sk-secret-abcd"
    # decifra de volta corretamente
    assert decrypt_str(saved["api_key_encrypted"]) == "sk-secret-abcd"
    assert saved["provider"] == "openai"
    assert saved["model"] == "gpt-4o"


def test_save_without_api_key_preserves_existing():
    saved = save_ai_preferences({}, {"provider": "openai", "model": "gpt-4o", "api_key": "sk-keep"})
    enc = saved["api_key_encrypted"]
    # novo save sem api_key (só troca o modelo) NÃO apaga a chave
    saved2 = save_ai_preferences(saved, {"model": "gpt-4o-mini"})
    assert saved2["api_key_encrypted"] == enc
    assert saved2["model"] == "gpt-4o-mini"


def test_save_empty_api_key_does_not_overwrite():
    saved = save_ai_preferences({}, {"provider": "openai", "model": "gpt-4o", "api_key": "sk-keep"})
    enc = saved["api_key_encrypted"]
    saved2 = save_ai_preferences(saved, {"api_key": "   "})  # vazio/whitespace
    assert saved2["api_key_encrypted"] == enc


def test_public_ai_masks_and_never_exposes_plaintext():
    saved = save_ai_preferences({}, {"provider": "anthropic", "model": "claude-sonnet-4-20250514", "api_key": "sk-ant-XYZ9"})
    pub = public_ai(saved)
    assert pub["api_key"] is None
    assert pub["api_key_set"] is True
    assert pub["api_key_masked"].endswith("XYZ9")
    assert "api_key_encrypted" not in pub
    assert pub["provider"] == "anthropic"


def test_public_ai_without_key_reports_not_set():
    pub = public_ai({"provider": "openai", "model": "gpt-4o"})
    assert pub["api_key_set"] is False
    assert pub["api_key_masked"] is None


def test_get_ai_runtime_returns_decrypted_when_complete():
    saved = save_ai_preferences({}, {"provider": "deepseek", "model": "deepseek-chat", "api_key": "sk-ds-1"})
    runtime = get_ai_runtime(_FakeUser({"ai": saved}))
    assert runtime == {"provider": "deepseek", "model": "deepseek-chat", "api_key": "sk-ds-1"}


def test_get_ai_runtime_none_when_incomplete():
    # sem api_key
    assert get_ai_runtime(_FakeUser({"ai": {"provider": "openai", "model": "gpt-4o"}})) is None
    # sem provider/model
    assert get_ai_runtime(_FakeUser({"ai": {}})) is None
    # sem preferences
    assert get_ai_runtime(_FakeUser(None)) is None


def test_available_models_has_four_providers():
    assert set(AVAILABLE_MODELS.keys()) == {"anthropic", "google", "openai", "deepseek"}
    for models in AVAILABLE_MODELS.values():
        assert isinstance(models, list) and models
