"""
AIJob model — Sprint 5

Registra cada chamada ao LLM: entrada, saída, custo, duração, entidade vinculada.
Usado para auditoria, controle de custo por tenant e billing futuro.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text

from app.models.base import Base
from app.models.types import PortableJSON


class AIJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class AIJobType(str, enum.Enum):
    # Existentes
    classify_demand = "classify_demand"
    extract_document = "extract_document"
    generate_proposal = "generate_proposal"
    generate_dossier_summary = "generate_dossier_summary"
    # Agentes novos
    diagnostico_propriedade = "diagnostico_propriedade"
    consulta_regulatoria = "consulta_regulatoria"
    gerar_documento = "gerar_documento"
    analise_financeira = "analise_financeira"
    acompanhamento_processo = "acompanhamento_processo"
    monitoramento_vigia = "monitoramento_vigia"
    gerar_conteudo_marketing = "gerar_conteudo_marketing"
    # RAG / Regulatório
    embedding_generation = "embedding_generation"
    enquadramento_regulatorio = "enquadramento_regulatorio"
    monitoramento_legislacao = "monitoramento_legislacao"


class AIJob(Base):
    __tablename__ = "ai_jobs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

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
    input_payload = Column(PortableJSON, nullable=True)   # prompt / dados de entrada
    result = Column(PortableJSON, nullable=True)           # saída estruturada
    raw_output = Column(Text, nullable=True)        # texto bruto retornado pelo LLM
    error = Column(Text, nullable=True)

    # Campos do sistema de agentes
    agent_name = Column(String(50), nullable=True, index=True)
    chain_trace_id = Column(String(32), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
