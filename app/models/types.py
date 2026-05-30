"""
Portable column types for cross-database compatibility.

Allows models to use JSONB on PostgreSQL while falling back to plain JSON
on SQLite (used in tests).
"""

from sqlalchemy import JSON, String
from sqlalchemy.types import TypeDecorator

from app.core.encryption import decrypt_str, encrypt_str

try:
    from sqlalchemy.dialects.postgresql import JSONB as _PG_JSONB
except ImportError:  # pragma: no cover
    _PG_JSONB = None


class PortableJSON(TypeDecorator):
    """JSONB on PostgreSQL, plain JSON elsewhere (e.g. SQLite in tests)."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and _PG_JSONB is not None:
            return dialect.type_descriptor(_PG_JSONB())
        return dialect.type_descriptor(JSON())


class EncryptedString(TypeDecorator):
    """Coluna criptografada em repouso com Fernet (ADR-014).

    O round-trip acontece no nível do ORM: encrypt no bind (flush), decrypt no
    result (load). O código de negócio lê/escreve plaintext; o banco guarda só o
    ciphertext urlsafe-base64. Uso: ``Column(EncryptedString(256))``.

    O ``length`` passado dimensiona a coluna em caracteres de *ciphertext* (que é
    maior que o plaintext); dimensione com folga.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt_str(value)

    def process_result_value(self, value, dialect):
        return decrypt_str(value)
