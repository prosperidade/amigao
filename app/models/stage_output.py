"""
StageOutput — Saídas/artefatos formais de cada macroetapa.

Regente Camada 3 (CAM3WS-006): cada etapa produz artefatos específicos que
ficam disponíveis nas etapas seguintes como "memória validada":

  Etapa 2 (diagnóstico preliminar):
    - ficha_inicial, hipotese_preliminar, urgencia, lacunas
  Etapa 4 (diagnóstico técnico):
    - problema_real, complexidade, risco_inicial, resumo_tecnico
  Etapa 5 (caminho regulatório):
    - caminho_principal, caminho_alternativo, plano_contingencia
  Etapa 6 (orçamento):
    - proposta_emitida, proposta_negociada, aceite_comercial
  Etapa 7 (contrato):
    - minuta, contrato_assinado, kickoff
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.types import PortableJSON


class StageOutput(Base):
    __tablename__ = "stage_outputs"

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

    # Etapa que produziu
    macroetapa = Column(String, nullable=False, index=True)

    # Tipo do artefato — ex: "diagnostico_preliminar", "resumo_tecnico", "proposta"
    output_type = Column(String, nullable=False, index=True)

    # Título curto exibido no workspace
    title = Column(String, nullable=False)

    # Conteúdo livre (texto longo OU JSON estruturado em content_data)
    content = Column(Text, nullable=True)
    content_data = Column(PortableJSON, nullable=True, default=dict)

    # Origem: agente IA ou usuário humano
    produced_by_agent = Column(String, nullable=True)
    produced_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Validação humana (espelha CAM3WS-005)
    needs_human_validation = Column(Boolean, default=False, nullable=False)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    validated_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    process = relationship("Process", backref="stage_outputs")
