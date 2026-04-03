"""
Modelo de Proposta Comercial — Sprint 4
"""

import enum

from sqlalchemy import JSON, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class ProposalStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    accepted = "accepted"
    rejected = "rejected"
    expired = "expired"


class Proposal(Base):
    __tablename__ = "proposals"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    process_id = Column(Integer, ForeignKey("processes.id"), nullable=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)

    status = Column(Enum(ProposalStatus), default=ProposalStatus.draft, nullable=False)
    version_number = Column(Integer, default=1, nullable=False)

    # Conteúdo
    title = Column(String, nullable=False)
    scope_items = Column(JSON, nullable=False, default=list)  # [{description, unit, qty, unit_price, total}]
    total_value = Column(Float, nullable=True)
    validity_days = Column(Integer, default=30)
    payment_terms = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Complexidade usada na geração automática
    complexity = Column(String, nullable=True)   # "baixa" | "media" | "alta"

    # Rastreabilidade
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tenant = relationship("Tenant")
    process = relationship("Process")
    client = relationship("Client")
    creator = relationship("User", foreign_keys=[created_by_user_id])
    contracts = relationship("Contract", back_populates="proposal")
