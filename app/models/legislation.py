"""
Legislation models — base de conhecimento legislativo.

LegislationDocument: metadata + texto completo do documento (lei, decreto, resolucao, IN, portaria).

Estrategia: armazenar texto completo e enviar direto no contexto do Gemini (2M tokens)
ao inves de chunking + embeddings. Isso preserva o contexto integral da legislacao.
"""

from __future__ import annotations

import enum

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    ForeignKey,
)
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.types import PortableJSON


class LegislationScope(str, enum.Enum):
    federal = "federal"
    estadual = "estadual"
    municipal = "municipal"


class LegislationSourceType(str, enum.Enum):
    lei = "lei"
    decreto = "decreto"
    resolucao = "resolucao"
    instrucao_normativa = "instrucao_normativa"
    portaria = "portaria"
    nota_tecnica = "nota_tecnica"
    manual = "manual"


class LegislationStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    indexed = "indexed"
    failed = "failed"


class LegislationDocument(Base):
    """Documento legislativo na base de conhecimento."""
    __tablename__ = "legislation_documents"

    id = Column(Integer, primary_key=True, index=True)
    # tenant_id nullable — None = documento global (legislacao federal)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    title = Column(String, nullable=False)
    source_type = Column(String, nullable=False)  # lei, decreto, resolucao, etc.
    identifier = Column(String, nullable=True, index=True)  # "Lei 12.651/2012"

    # Escopo geografico
    uf = Column(String(2), nullable=True, index=True)  # None = federal
    scope = Column(String, nullable=False, default="federal")  # federal/estadual/municipal
    municipality = Column(String, nullable=True)

    # Orgao emissor
    agency = Column(String, nullable=True, index=True)  # IBAMA, SEMA-MT, etc.

    # Datas
    effective_date = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    # Armazenamento
    url = Column(String, nullable=True)
    file_path = Column(String, nullable=True)  # MinIO storage key

    # Texto completo extraido (enviado direto no contexto do Gemini)
    full_text = Column(Text, nullable=True)
    token_count = Column(Integer, nullable=False, default=0)

    # Processamento
    status = Column(String, nullable=False, default="pending")
    content_hash = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)

    # Metadados para filtragem na busca
    demand_types = Column(PortableJSON, nullable=True)  # ["car", "licenciamento", ...]
    keywords = Column(PortableJSON, nullable=True)  # palavras-chave extraidas
    extra_metadata = Column(PortableJSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
