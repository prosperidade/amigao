"""
ProcessDecision — Decisões críticas registradas ao longo do caso.

Regente Camada 3 (Sprint E) — "Aba Decisões" como componente de 1ª classe.
Baseado em `CAMADA 3 - WORKSPACE EDIT1.pdf` da sócia.

Cada decisão transforma análise em governança. Registra:
  - o que foi decidido
  - por quê
  - com base em quê (evidências, documentos, leituras IA)
  - por quem
  - qual impacto no caso
  - qual próximo passo gerado

Valor estratégico: base para rastreabilidade, auditoria interna e
reaproveitamento de memória entre casos. Fundação da visão govtech.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.types import PortableJSON


class DecisionType(str, enum.Enum):
    """Tipos de decisão por natureza (PDF Camada 3 da sócia)."""
    triagem = "triagem"
    documental = "documental"
    tecnica = "tecnica"
    regulatoria = "regulatoria"
    comercial = "comercial"
    contratual = "contratual"
    bloqueio = "bloqueio"
    avanco_etapa = "avanco_etapa"


class DecisionStatus(str, enum.Enum):
    """Ciclo de vida da decisão."""
    proposta = "proposta"       # Sugerida (por IA ou consultor) aguardando validação
    validada = "validada"       # Aceita e aplicada ao caso
    revisada = "revisada"       # Foi alterada após validação inicial
    substituida = "substituida" # Sobreposta por outra decisão mais recente


DECISION_TYPE_LABELS: dict[DecisionType, str] = {
    DecisionType.triagem: "Triagem",
    DecisionType.documental: "Documental",
    DecisionType.tecnica: "Técnica",
    DecisionType.regulatoria: "Regulatória",
    DecisionType.comercial: "Comercial",
    DecisionType.contratual: "Contratual",
    DecisionType.bloqueio: "Bloqueio",
    DecisionType.avanco_etapa: "Avanço de etapa",
}

DECISION_STATUS_LABELS: dict[DecisionStatus, str] = {
    DecisionStatus.proposta: "Proposta",
    DecisionStatus.validada: "Validada",
    DecisionStatus.revisada: "Revisada",
    DecisionStatus.substituida: "Substituída",
}


class ProcessDecision(Base):
    __tablename__ = "process_decisions"

    id = Column(Integer, primary_key=True, index=True)

    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    process_id = Column(
        Integer,
        ForeignKey("processes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Etapa em que a decisão aconteceu (uma das 7 macroetapas).
    macroetapa = Column(String, nullable=False, index=True)

    # Categoria da decisão (ver DecisionType).
    decision_type = Column(String, nullable=False, index=True)

    # Texto curto do que foi decidido.
    decision_text = Column(Text, nullable=False)

    # Por que foi decidido assim.
    justification = Column(Text, nullable=True)

    # Evidências que sustentaram a decisão:
    #   {"documents": [doc_id, ...], "stage_outputs": [id, ...],
    #    "ai_readings": [ai_job_id, ...], "notes": "texto livre"}
    basis = Column(PortableJSON, nullable=True, default=dict)

    # Quem validou / autor da decisão.
    decided_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Data em que a decisão foi efetivamente tomada (pode diferir de created_at
    # quando proposta por IA e validada depois).
    decided_at = Column(DateTime(timezone=True), nullable=True)

    # Impacto descritivo no andamento do caso.
    impact = Column(Text, nullable=True)

    # Ação/saída gerada a partir desta decisão.
    next_step = Column(Text, nullable=True)

    # Status do ciclo de vida.
    status = Column(
        String,
        nullable=False,
        default=DecisionStatus.proposta.value,
        index=True,
    )

    # Se esta decisão substituiu uma anterior, referência para rastreio.
    supersedes_decision_id = Column(
        Integer,
        ForeignKey("process_decisions.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # Relacionamentos
    process = relationship("Process", backref="decisions")
    superseded_by = relationship(
        "ProcessDecision",
        remote_side=[id],
        foreign_keys=[supersedes_decision_id],
    )

    def soft_delete(self, when: datetime | None = None) -> None:
        self.deleted_at = when or datetime.utcnow()
