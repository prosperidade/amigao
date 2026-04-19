"""
Modelos de Checklist Documental — Sprint 1

ChecklistTemplate  : template de documentos necessários por tipo de demanda (global ou por tenant)
ProcessChecklist   : instância do checklist gerada para um processo específico
"""

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class ChecklistTemplate(Base):
    """Template de checklist de documentos para um tipo de demanda."""
    __tablename__ = "checklist_templates"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=True, index=True)  # None = global

    demand_type = Column(String, nullable=False, index=True)  # ex: "car", "licenciamento"
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Lista de itens: [{id, label, doc_type, category, required, description, validation_tip}]
    items = Column(JSON, nullable=False, default=list)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    checklists = relationship("ProcessChecklist", back_populates="template")


class ProcessChecklist(Base):
    """Instância de checklist vinculada a um processo específico."""
    __tablename__ = "process_checklists"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    process_id = Column(Integer, ForeignKey("processes.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)
    template_id = Column(Integer, ForeignKey("checklist_templates.id", ondelete="SET NULL"), nullable=True)

    # Cópia dos itens com status: [{...template_item, status: pending|received|waived, document_id, waiver_reason}]
    items = Column(JSON, nullable=False, default=list)

    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    template = relationship("ChecklistTemplate", back_populates="checklists")
    process = relationship("Process")
