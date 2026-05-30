"""
Criptografia de segredos por usuário/cliente — Fernet (AES-128-CBC + HMAC-SHA256).

Ver ADR-014 (docs/adr/014-cripto-segredos-usuario.md).

Uso transparente via type decorator ``EncryptedString`` (app/models/types.py).
A chave-mestra vive em ``CREDENTIAL_ENCRYPTION_KEY`` (separada do SECRET_KEY do
JWT). ``CREDENTIAL_ENCRYPTION_KEY_OLD`` (opcional) habilita rotação via MultiFernet.
"""

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core import config


@lru_cache
def get_fernet() -> MultiFernet:
    """Constrói o MultiFernet com a chave principal e, opcionalmente, a antiga.

    A ordem importa: a primeira chave é usada para *encriptar*; todas são tentadas
    na *decriptação*. Mantendo a chave nova primeiro, dados novos já saem com ela
    durante uma rotação, enquanto dados antigos seguem decriptáveis pela antiga.

    Lê ``config.settings`` dinamicamente (respeita ``override_settings``).
    Cacheado — ``get_fernet.cache_clear()`` força releitura (usado em testes que
    trocam a chave em runtime).
    """
    settings = config.settings
    keys = [Fernet(settings.CREDENTIAL_ENCRYPTION_KEY.encode())]
    old_key = (settings.CREDENTIAL_ENCRYPTION_KEY_OLD or "").strip()
    if old_key:
        keys.append(Fernet(old_key.encode()))
    return MultiFernet(keys)


def encrypt_str(plaintext: str | None) -> str | None:
    """Encripta uma string. ``None`` entra, ``None`` sai.

    Retorna o ciphertext como string urlsafe-base64 (pronto para coluna String).
    """
    if plaintext is None:
        return None
    token = get_fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_str(ciphertext: str | None) -> str | None:
    """Decripta um ciphertext. ``None`` entra, ``None`` sai.

    Levanta ``InvalidToken`` com mensagem clara se o token for inválido (chave
    errada ou dado corrompido).
    """
    if ciphertext is None:
        return None
    try:
        plaintext = get_fernet().decrypt(ciphertext.encode("utf-8"))
    except InvalidToken as exc:
        raise InvalidToken(
            "Cipher inválido - chave errada ou dado corrompido."
        ) from exc
    return plaintext.decode("utf-8")
