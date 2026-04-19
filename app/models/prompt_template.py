"""
PromptTemplate model — Sprint IA-1

Armazena templates de prompt versionados no PostgreSQL.
Permite governanca de LLM em producao: versionamento, rollback,
override por tenant, e validacao de input/output via JSON Schema.
"""

from __future__ import annotations

import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.types import PortableJSON


class PromptCategory(str, enum.Enum):
    classify = "classify"
    extract = "extract"
    summarize = "summarize"
    proposal = "proposal"
    # Categorias dos agentes
    diagnostico = "diagnostico"
    legislacao = "legislacao"
    redator = "redator"
    financeiro = "financeiro"
    acompanhamento = "acompanhamento"
    vigia = "vigia"
    marketing = "marketing"


class PromptRole(str, enum.Enum):
    system = "system"
    user = "user"
    few_shot = "few_shot"


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    __table_args__ = (
        UniqueConstraint("slug", "version", "tenant_id", name="uq_prompt_slug_version_tenant"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=True, index=True)

    slug = Column(String(100), nullable=False, index=True)
    category = Column(Enum(PromptCategory, name="promptcategory"), nullable=False, index=True)
    role = Column(Enum(PromptRole, name="promptrole"), nullable=False)
    version = Column(Integer, nullable=False, default=1)

    content = Column(Text, nullable=False)

    input_schema = Column(PortableJSON, nullable=True)
    output_schema = Column(PortableJSON, nullable=True)

    model_hint = Column(String(100), nullable=True)
    temperature = Column(Float, nullable=True)
    max_tokens = Column(Integer, nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
