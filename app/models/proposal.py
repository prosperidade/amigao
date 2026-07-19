"""
Modelo de Proposta Comercial — Sprint 4
"""

import enum

from sqlalchemy import JSON, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.types import PortableJSON


class ProposalStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    accepted = "accepted"
    rejected = "rejected"
    expired = "expired"


class Proposal(Base):
    __tablename__ = "proposals"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    process_id = Column(Integer, ForeignKey("processes.id", ondelete="SET NULL"), nullable=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False, index=True)

    status = Column(Enum(ProposalStatus), default=ProposalStatus.draft, nullable=False)
    version_number = Column(Integer, default=1, nullable=False)

    # S5-A — a proposta NASCE da Rota validada (não da tabela de preços). `rota_id`
    # é a proveniência no nível da proposta (rastreabilidade fina fica em cada
    # scope_item via `rota_passo_id`). SET NULL: a proposta sobrevive se a Rota
    # for removida (o snapshot do escopo já está materializado em scope_items).
    rota_id = Column(Integer, ForeignKey("rotas.id", ondelete="SET NULL"), nullable=True, index=True)
    # Renegociação: uma recusa/expiração pode gerar a versão N+1, linkada à
    # anterior (histórico preservado — nunca se sobrescreve a versão recusada).
    previous_version_id = Column(
        Integer, ForeignKey("proposals.id", ondelete="SET NULL"), nullable=True
    )

    # Conteúdo
    title = Column(String, nullable=False)
    scope_items = Column(JSON, nullable=False, default=list)  # [{description, unit, qty, unit_price, total}]
    total_value = Column(Float, nullable=True)
    validity_days = Column(Integer, default=30)
    payment_terms = Column(Text, nullable=True)
    # S5-B — parcelas ESTRUTURADAS: [{numero, vencimento, valor}]. Alimentam a
    # cláusula 2ª do contrato e a validação de consistência "soma das parcelas ==
    # total do bloco" (classe de erro real dos contratos manuais da Mirante).
    # Vazio = o gerador sintetiza uma parcela única à vista (soma trivial confere);
    # o consultor pode editar via PATCH. Ver app/services/mirante_documents.py.
    payment_installments = Column(PortableJSON, nullable=False, default=list, server_default="[]")
    notes = Column(Text, nullable=True)

    # Complexidade usada na geração automática
    complexity = Column(String, nullable=True)   # "baixa" | "media" | "alta"

    # Rastreabilidade
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
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
    rota = relationship("Rota", foreign_keys=[rota_id])
    # Cadeia de versões (renegociação): `previous_version` = a versão recusada que
    # originou esta; `next_versions` = as renegociações geradas a partir desta.
    previous_version = relationship(
        "Proposal", remote_side=[id], foreign_keys=[previous_version_id],
        back_populates="next_versions",
    )
    next_versions = relationship(
        "Proposal", foreign_keys=[previous_version_id], back_populates="previous_version",
    )
