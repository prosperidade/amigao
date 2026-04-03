"""
Modelos de Trilha Regulatória — Sprint 3

WorkflowTemplate  : template de etapas regulatórias por tipo de demanda (global ou por tenant)
"""

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.models.base import Base


class WorkflowTemplate(Base):
    """Template de trilha regulatória (sequência de etapas) por tipo de demanda."""
    __tablename__ = "workflow_templates"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)  # None = global

    demand_type = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Lista de etapas:
    # [{order, title, description, task_type, estimated_days, depends_on: [order]}]
    steps = Column(JSON, nullable=False, default=list)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
