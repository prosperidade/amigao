"""
Portable column types for cross-database compatibility.

Allows models to use JSONB on PostgreSQL while falling back to plain JSON
on SQLite (used in tests).
"""

from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator

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
