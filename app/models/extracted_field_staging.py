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

    # ── "Aceito" ≠ "Gravado" (validação Isis 30/07 e 02/08) ─────────────────
    # Preenchido pela consolidação quando o valor DESTA linha está na base;
    # limpo por qualquer nova decisão do consultor (a decisão volta a ser
    # proposta). Enquanto isto não existia, uma linha gravada e uma linha
    # recusada eram visualmente idênticas na Conferência — foi assim que 16
    # campos gravados de fato viraram "gravou apenas três" na cadeira da
    # consultora.
    #
    # Por que uma coluna própria e não derivar de `field_sources` do destino:
    # `field_sources` é por (entidade, COLUNA) e diz apenas "esta coluna foi
    # validada por humano alguma vez". Ele não distingue a linha que pousou da
    # linha que foi RECUSADA sobre uma coluna já consolidada — que é exatamente
    # o caminho da reconciliação (`_write_entity`: valor novo diverge de campo
    # já `human_validated` ⇒ NÃO sobrescreve). Nesse caminho `field_sources`
    # diz "human_validated" e a linha não gravou nada: derivar dali produziria
    # "Gravado" em cima de um valor que a base recusou. Não é hipótese —
    # aconteceu no caso 16 em produção (audit_log 1675, reconciliações de
    # `numero_matricula` e `codigo_incra_sncr`). Some-se a isso que resolver o
    # destino de uma linha de matrícula exige repetir a cascata de âncora e o
    # guard fantasma a cada GET.
    consolidated_at = Column(DateTime(timezone=True), nullable=True)

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
