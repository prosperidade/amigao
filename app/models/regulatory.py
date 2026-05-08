"""Modelos regulatórios — Sprint A1 (Tarefa D1).

Fecha o gap **B3** do audit (`docs/AUDITORIA_FLUXO_2026-04-29.md`):
"Diagnóstico regulatório não tem versão própria — mistura com
Process.initial_diagnosis (Intake)". Cria duas entidades de 1ª classe:

* ``RegulatoryDiagnosis``: diagnóstico regulatório formal e versionado,
  com FK para o ``Process`` e validação humana opcional. Conteúdo em JSONB
  (typicamente um ``DiagnosticoPreliminarContent`` da Tarefa C).
* ``RegulatoryIssue``: inconsistência detectada no imóvel (ex.: área
  divergente, sobreposição com APP). Vive vinculada a ``Property``
  (e opcionalmente a um ``Document`` fonte). **Não** existe tabela
  associativa N–N com ``RegulatoryDiagnosis`` (decisão Q4 da Fase 0):
  quando um diagnóstico quiser referenciar issues, lista IDs no próprio
  ``content`` JSONB.

Esta sprint só introduz **estrutura** — populamento e endpoints de escrita
ficam para Sprint A2/Y. Tarefa D2 expõe leitura.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.types import PortableJSON

# ---------------------------------------------------------------------------
# Enums (compartilhados pela migration via string values)
# ---------------------------------------------------------------------------

class RegulatoryIssueType(str, enum.Enum):
    area_divergente = "area_divergente"
    sobreposicao_app = "sobreposicao_app"
    sobreposicao_reserva = "sobreposicao_reserva"
    poligono_fora_matricula = "poligono_fora_matricula"
    outro = "outro"


class RegulatoryIssueSeverity(str, enum.Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class RegulatoryDiagnosis(Base):
    """Diagnóstico regulatório versionado de um processo.

    A unicidade ``(process_id, version)`` garante que cada versão é única
    para um dado processo. Versionamento simples (inteiro crescente) — o
    caller é responsável por incrementar quando criar nova versão.
    """

    __tablename__ = "regulatory_diagnoses"
    __table_args__ = (
        UniqueConstraint("process_id", "version", name="uq_regulatory_diagnoses_process_version"),
    )

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

    # Conteúdo livre — typicamente DiagnosticoPreliminarContent (schemas Tarefa C).
    # Pode incluir referência a issues via content["issue_ids"]: list[int].
    content = Column(PortableJSON, nullable=False, default=dict)

    version = Column(Integer, nullable=False, default=1)

    # Validação humana (opcional)
    validated_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    validated_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )

    process = relationship("Process", backref="regulatory_diagnoses")
    validated_by = relationship("User", foreign_keys=[validated_by_user_id])


class RegulatoryIssue(Base):
    """Inconsistência regulatória detectada em um imóvel.

    Vinculada diretamente a ``Property`` (obrigatório) e opcionalmente a um
    ``Document`` fonte. **Não** se relaciona via FK com ``RegulatoryDiagnosis``
    (Q4): quando um diagnóstico quiser referenciar issues, lista IDs no
    próprio ``content`` JSONB.
    """

    __tablename__ = "regulatory_issues"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    property_id = Column(
        Integer,
        ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    type = Column(
        Enum(RegulatoryIssueType, name="regulatory_issue_type"),
        nullable=False,
        index=True,
    )
    severity = Column(
        Enum(RegulatoryIssueSeverity, name="regulatory_issue_severity"),
        nullable=False,
        default=RegulatoryIssueSeverity.warning,
    )

    payload = Column(PortableJSON, nullable=True)
    detected_by = Column(String, nullable=True)  # nome do agente ou "manual"

    detected_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    property = relationship("Property", backref="regulatory_issues")
    document = relationship("Document", foreign_keys=[document_id])
