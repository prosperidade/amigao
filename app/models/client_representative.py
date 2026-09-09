"""
Representante da pessoa jurídica — ENT-001 (spec Isis v0.1 §6).

Regra de produto: "O CNPJ é pessoa principal, titular/contratante no escopo do
caso. Joel deve ter papel 'representante da pessoa jurídica'. Seu documento
comprova representação/identidade, não titularidade do imóvel."

O representante NÃO é Client: não contrata, não tem caso, não tem imóvel. É
registro SUBORDINADO ao Client PJ — some com ele (CASCADE) e só existe no
contexto dele.

Por que TABELA e não JSONB no Client (ADR-063, decidido por medição):
  1. A consolidação grava campo a campo por `_write_entity`, que é genérica
     sobre objeto ORM: allowlist de colunas + coerção por tipo + reconciliação
     de valor divergente + `field_sources` por campo + AuditLog do anterior→novo.
     Uma tabela herda essas cinco garantias sem uma linha nova; um JSONB exigiria
     um caminho de escrita paralelo — sem proveniência por campo e sem
     reconciliação. Foi exatamente a escrita sem guard que produziu o P3.
  2. Cardinalidade é N e real: PJ com sócio-administrador + procurador é o caso
     comum, e a mesma pessoa física representa duas PJs (linhas distintas,
     nenhuma delas titular).
  3. `field_sources` é por (entidade, COLUNA) — o selo de oficialização do
     Sprint 3 e o "Aceito ≠ Gravado" da Conferência dependem dele.
"""

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.types import PortableJSON

# Papéis conhecidos. String(50) e NÃO Enum de propósito: o vocabulário é
# evolutivo (a própria spec já cita "inventariante" como referência processual
# em caso de falecimento, §2.1) e o precedente do projeto — `knowledge_catalog.
# source_type` — mostra que valor novo em coluna String não custa migration.
PAPEIS_REPRESENTANTE = (
    "representante_legal",   # padrão quando o documento não qualifica o vínculo
    "socio_administrador",
    "procurador",
    "inventariante",
    "outro",
)
PAPEL_PADRAO = "representante_legal"


class ClientRepresentative(Base):
    """Pessoa física que representa um Client PJ. Nunca titular do imóvel."""

    __tablename__ = "client_representatives"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    client_id = Column(
        Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Todos nullable menos o vínculo: a consolidação escreve CAMPO A CAMPO
    # (nome numa passagem, CPF noutra), então a linha precisa existir válida
    # com dado parcial. Quem exige o conjunto mínimo é a tela, não o schema.
    full_name = Column(String, nullable=True)
    cpf = Column(String, nullable=True, index=True)
    rg = Column(String, nullable=True)
    birth_date = Column(Date, nullable=True)
    papel = Column(String(50), nullable=False, default=PAPEL_PADRAO)
    # Âncora da consolidação: linhas de staging do MESMO documento descrevem a
    # MESMA pessoa. É o que permite gravar campo a campo (nome numa passagem,
    # CPF noutra) sem criar duas linhas, e o que faz uma segunda CNH virar um
    # segundo representante em vez de sobrescrever o primeiro.
    source_document_id = Column(
        Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)

    # Mesma semântica do Client/Property/Matricula: {coluna: "raw" |
    # "ai_extracted" | "human_validated" | "pendente_oficializacao"}.
    field_sources = Column(PortableJSON, nullable=True, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    client = relationship("Client", back_populates="representatives")

    __table_args__ = (
        Index("ix_client_repr_tenant_client", "tenant_id", "client_id"),
    )
