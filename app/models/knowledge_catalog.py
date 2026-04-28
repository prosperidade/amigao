"""KnowledgeChunk — catalogo semantico (RAG via pgvector).

Sprint U (2026-04-27). Cada linha e um pedaco de conhecimento (chunk) de uma
fonte indexavel: legislacao, oficios da socia, manuais, jurisprudencia, etc.

A coluna `embedding` e um vector(768) gerado pelo Gemini text-embedding-004.
Como o tipo `vector` precisa do pgvector e nao queremos importar o pacote
Python `pgvector` so para o ORM, declaramos a coluna como tipo opaco aqui
e fazemos as queries de similaridade via SQL puro em
`app/services/knowledge_catalog.py`.
"""

from __future__ import annotations

import enum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.types import UserDefinedType

from app.models.base import Base


class SourceType(str, enum.Enum):
    """Tipos de fonte aceitos no catalogo. Reflete `source_type` (string)."""

    legislation = "legislation"
    oficio = "oficio"
    manual = "manual"
    jurisprudence = "jurisprudence"
    skill = "skill"
    other = "other"


class _Vector(UserDefinedType):
    """Tipo opaco para a coluna pgvector — sem dependencia de `pgvector` Python.

    Nao tentamos converter no SQLAlchemy. Inserts e queries usam SQL puro
    em `app/services/knowledge_catalog.py`.
    """

    cache_ok = True

    def __init__(self, dim: int = 768) -> None:
        self.dim = dim

    def get_col_spec(self, **kw: Any) -> str:  # noqa: ARG002
        return f"vector({self.dim})"


class KnowledgeChunk(Base):
    """Chunk de conhecimento indexavel via embedding semantico."""

    __tablename__ = "knowledge_catalog"

    id = Column(BigInteger, primary_key=True)

    # NULL = global (legislacao federal, manuais publicos).
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Origem do chunk.
    source_type = Column(String(50), nullable=False)
    source_ref = Column(String(255), nullable=False)
    chunk_index = Column(Integer, nullable=False, default=0)

    # Conteudo.
    title = Column(String(500), nullable=True)
    section = Column(String(255), nullable=True)
    chunk_text = Column(Text, nullable=False)
    chunk_tokens = Column(Integer, nullable=False, default=0)

    # Metadados juridicos para filtragem.
    jurisdiction = Column(String(20), nullable=True)
    uf = Column(String(2), nullable=True)
    agency = Column(String(100), nullable=True)
    identifier = Column(String(255), nullable=True)
    effective_date = Column(Date, nullable=True)

    # Embedding (vector(768)).
    embedding = Column(_Vector(768), nullable=True)
    embedding_model = Column(String(100), nullable=True)
    embedding_dim = Column(Integer, nullable=True)

    # Idempotencia: evita reindexar o mesmo conteudo.
    content_hash = Column(String(64), nullable=False, unique=True)
    extra_metadata = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
