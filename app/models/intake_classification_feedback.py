"""Feedback loop do AtendimentoAgent — Sprint A1 (Tarefa E).

Cada vez que o consultor explicitamente classifica o ``demand_type`` de um
processo (via ``POST /processes/{id}/classify``), uma linha é gravada aqui.
Quando a classificação humana difere da última saída do ``AtendimentoAgent``
para o mesmo intake, isso é considerado uma "correção" — input para a
métrica de precisão.

Decisão da Fase 0 (Q8): tabela dedicada (não reuso de ``audit_log`` /
``AIJob.result``). Mais explícito, mais fácil agregar nas stats.

Convenção de denominador (resolve Risk #6 da Fase 0):
* só conta correções **explícitas** — só grava quando o consultor chama
  ``/classify`` de fato. Casos onde o processo é simplesmente arquivado/
  abandonado sem classificação não inflam o denominador.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class IntakeClassificationFeedback(Base):
    """Histórico de correções humanas sobre a classificação inicial de demanda."""

    __tablename__ = "intake_classification_feedback"

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
    intake_draft_id = Column(
        Integer,
        ForeignKey("intake_drafts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Classificação que a IA produziu na última execução do AtendimentoAgent
    # vinculada ao mesmo intake_draft / processo. Pode ser None quando a IA
    # não rodou (regras estáticas resolveram sozinhas, por exemplo).
    ai_demand_type = Column(String, nullable=True)
    ai_confidence = Column(Float, nullable=True)
    ai_run_id = Column(
        Integer,
        ForeignKey("ai_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Classificação canônica decidida pelo consultor.
    corrected_demand_type = Column(String, nullable=False)
    corrected_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    corrected_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    process = relationship("Process", foreign_keys=[process_id])
    corrected_by = relationship("User", foreign_keys=[corrected_by_user_id])
