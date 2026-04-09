"""LegislationAlert — alerta de nova legislacao relevante para processos ativos."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class LegislationAlert(Base):
    __tablename__ = "legislation_alerts"

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
        nullable=True,
        index=True,
    )
    document_id = Column(
        Integer,
        ForeignKey("legislation_documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    alert_type = Column(String, nullable=False)  # new_legislation, updated, revoked, crawler_error
    severity = Column(String, nullable=False, default="info")  # info, warning, error
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    process = relationship("Process")
    legislation_document = relationship("LegislationDocument")
