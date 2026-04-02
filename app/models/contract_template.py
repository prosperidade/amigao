"""
Modelo de Template de Contrato — Sprint 4
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base


class ContractTemplate(Base):
    """Template de contrato com variáveis substituíveis."""
    __tablename__ = "contract_templates"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)  # None = global

    demand_type = Column(String, nullable=True, index=True)  # None = genérico
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Corpo do contrato com variáveis {{cliente.nome}}, {{imovel.matricula}}, etc.
    content_template = Column(Text, nullable=False)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    contracts = relationship("Contract", back_populates="template")
