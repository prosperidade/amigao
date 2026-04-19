"""
Modelo de Template de Contrato — Sprint 4
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class ContractTemplate(Base):
    """Template de contrato com variáveis substituíveis."""
    __tablename__ = "contract_templates"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=True, index=True)  # None = global

    demand_type = Column(String, nullable=True, index=True)  # None = genérico
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Corpo do contrato com variáveis {{cliente.nome}}, {{imovel.matricula}}, etc.
    content_template = Column(Text, nullable=False)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    contracts = relationship("Contract", back_populates="template")
