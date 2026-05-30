"""
Testes da criptografia de segredos com Fernet (ADR-014).

Cobre: round-trip, handling de None, chave errada (InvalidToken) e rotação via
MultiFernet (chave antiga continua decriptável).
"""

import secrets
from contextlib import contextmanager

import pytest
from cryptography.fernet import InvalidToken

from app.core.config import override_settings
from app.core.encryption import decrypt_str, encrypt_str, get_fernet

# Chaves Fernet válidas e distintas, fixas para determinismo.
KEY_A = "k9rAqkESM_sjrWwOXc0pEx6Iv04Tp7qqNAkgbIW7q4U="  # default em .env/tests
KEY_B = "G31ZxxdHNpXrz2QEEME0kpkSALvn3O_ni8k6uj8s7EU="
KEY_OLD = "idHgX9KDoxbaOdTtVjysIJTqTxYM_YdwfAML1Cp7KFY="


@pytest.fixture(autouse=True)
def _clear_fernet_cache():
    """Garante que cada teste construa o Fernet a partir das settings vigentes."""
    get_fernet.cache_clear()
    yield
    get_fernet.cache_clear()


@contextmanager
def _use_keys(current: str, old: str | None = None):
    """Reconfigura as chaves de criptografia e reconstrói o Fernet."""
    with override_settings(
        CREDENTIAL_ENCRYPTION_KEY=current,
        CREDENTIAL_ENCRYPTION_KEY_OLD=old,
    ):
        get_fernet.cache_clear()
        try:
            yield
        finally:
            get_fernet.cache_clear()


def test_round_trip_preserva_plaintext():
    plaintext = "senha-do-portal-SEMA-" + secrets.token_hex(16)
    ciphertext = encrypt_str(plaintext)
    assert ciphertext != plaintext
    assert decrypt_str(ciphertext) == plaintext


def test_none_entra_none_sai():
    assert encrypt_str(None) is None
    assert decrypt_str(None) is None


def test_string_vazia_faz_round_trip():
    # String vazia não é None — deve ser encriptada e voltar como "".
    ciphertext = encrypt_str("")
    assert ciphertext is not None
    assert decrypt_str(ciphertext) == ""


def test_chave_errada_levanta_invalid_token():
    with _use_keys(KEY_A):
        ciphertext = encrypt_str("segredo")
    with _use_keys(KEY_B):
        with pytest.raises(InvalidToken, match="chave errada ou dado corrompido"):
            decrypt_str(ciphertext)


def test_multifernet_aceita_chave_antiga_em_rotacao():
    # Dado encriptado com a chave antiga...
    with _use_keys(KEY_OLD):
        ciphertext = encrypt_str("segredo-legado")
    # ...continua decriptável quando KEY_OLD está em settings (rotação em curso).
    with _use_keys(KEY_B, old=KEY_OLD):
        assert decrypt_str(ciphertext) == "segredo-legado"
        # E novos segredos saem com a chave nova (decriptáveis sem a antiga).
        novo = encrypt_str("segredo-novo")
    with _use_keys(KEY_B):
        assert decrypt_str(novo) == "segredo-novo"
