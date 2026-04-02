"""
AIJob model — Sprint 5

Registra cada chamada ao LLM: entrada, saída, custo, duração, entidade vinculada.
Usado para auditoria, controle de custo por tenant e billing futuro.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
)
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import Base


class AIJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class AIJobType(str, enum.Enum):
    classify_demand = "classify_demand"
    extract_document = "extract_document"
    generate_proposal = "generate_proposal"
    generate_dossier_summary = "generate_dossier_summary"


class AIJob(Base):
    __tablename__ = "ai_jobs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Entidade vinculada (processo, documento, proposta, etc.)
    entity_type = Column(String(50), nullable=True)   # "process" | "document" | "proposal"
    entity_id = Column(Integer, nullable=True)

    job_type = Column(Enum(AIJobType), nullable=False, index=True)
    status = Column(Enum(AIJobStatus), nullable=False, default=AIJobStatus.pending, index=True)

    # LLM metadata
    model_used = Column(String(100), nullable=True)
    provider = Column(String(50), nullable=True)
    tokens_in = Column(Integer, nullable=True)
    tokens_out = Column(Integer, nullable=True)
    cost_usd = Column(Float, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Payload
    input_payload = Column(JSONB, nullable=True)   # prompt / dados de entrada
    result = Column(JSONB, nullable=True)           # saída estruturada
    raw_output = Column(Text, nullable=True)        # texto bruto retornado pelo LLM
    error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
