"""
ExtractedFieldStaging — Ficha 01 (Dicionário de Extração do Intake), FASE 1.

Princípio da Ficha 01: "agentes propõem (staging), consultor decide (Alertas),
sistema grava (base)". Extrator/Auditor escrevem campos extraídos AQUI, nunca na
base (Cliente / Imóvel / Matrícula). A base só é gravada na confirmação do
consultor (fase 4).

Distinção de schema: campo EXTRAÍDO carrega confiança + status de validação
(esta entidade); campo DERIVADO carrega rastreabilidade (qual agente, com base
em quê) — ``created_by_agent`` + ``ai_job_id``.

Esta FASE 1 instala só o schema; nada escreve no staging ainda (extrator passa a
escrever na fase 2). Ver ``docs/trabalhos/ficha01_fase1.md``.
"""

import enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.types import PortableJSON


class ExtractedFieldStatus(str, enum.Enum):
    """Ciclo de validação de um campo extraído (decidido pelo consultor)."""

    pendente = "pendente"
    consistente = "consistente"
    divergente_transcricao = "divergente_transcricao"
    divergente_fundo = "divergente_fundo"
    aceito = "aceito"
    rejeitado = "rejeitado"


class ExtractedFieldStaging(Base):
    """Campo extraído em staging — proposta de agente, não base confirmada."""

    __tablename__ = "extracted_field_staging"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    process_id = Column(
        Integer, ForeignKey("processes.id", ondelete="CASCADE"), nullable=True, index=True
    )
    document_id = Column(
        Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Tipo de documento de origem (rg_cpf, endereco, car, ccir, matricula, itr,
    # sigef, outro). String livre nesta fase — taxonomia evolui sem migration.
    source_doc_type = Column(String(50), nullable=True)

    field_name = Column(String, nullable=False)
    # {"valor": ..., "unidade": ...} quando houver unidade.
    field_value = Column(PortableJSON, nullable=True)
    confidence = Column(String(10), nullable=True)  # high | medium | low

    # Destino na base (decisão final é do consultor na fase 4).
    target_entity = Column(String(20), nullable=True)  # cliente | imovel | matricula
    target_field = Column(String, nullable=True)
    # Nº da matrícula a que o campo se refere, quando identificável; vínculo
    # definitivo é decisão do consultor.
    matricula_hint = Column(String, nullable=True)

    status = Column(
        Enum(ExtractedFieldStatus, name="extractedfieldstatus"),
        nullable=False,
        default=ExtractedFieldStatus.pendente,
        index=True,
    )

    # Preenchidos na decisão do consultor (fase 4).
    decided_value = Column(PortableJSON, nullable=True)
    decided_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at = Column(DateTime(timezone=True), nullable=True)

    # Rastreabilidade da origem (qual agente, qual job).
    created_by_agent = Column(String(50), nullable=True)  # extrator | auditor
    ai_job_id = Column(
        Integer, ForeignKey("ai_jobs.id", ondelete="SET NULL"), nullable=True
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tenant = relationship("Tenant")

    __table_args__ = (
        Index(
            "ix_staging_tenant_process_status",
            "tenant_id",
            "process_id",
            "status",
        ),
    )
