"""
Modelo de Contrato — Sprint 4
"""

import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class ContractStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    signed = "signed"
    cancelled = "cancelled"


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    proposal_id = Column(Integer, ForeignKey("proposals.id", ondelete="SET NULL"), nullable=True, index=True)
    process_id = Column(Integer, ForeignKey("processes.id", ondelete="SET NULL"), nullable=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False, index=True)
    template_id = Column(Integer, ForeignKey("contract_templates.id", ondelete="SET NULL"), nullable=True)

    status = Column(Enum(ContractStatus), default=ContractStatus.draft, nullable=False)
    title = Column(String, nullable=False)

    # Conteúdo final (após substituição de variáveis)
    content = Column(Text, nullable=True)

    # PDF armazenado no MinIO
    pdf_storage_key = Column(String, nullable=True)

    # Assinatura (Wave 2 — campos reservados)
    signed_at = Column(DateTime(timezone=True), nullable=True)
    signed_by_client = Column(Boolean, default=False)

    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tenant = relationship("Tenant")
    proposal = relationship("Proposal", back_populates="contracts")
    process = relationship("Process")
    client = relationship("Client")
    template = relationship("ContractTemplate", back_populates="contracts")
    creator = relationship("User", foreign_keys=[created_by_user_id])
