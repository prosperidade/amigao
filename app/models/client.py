import enum

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.types import PortableJSON


class ClientType(str, enum.Enum):
    pf = "pf"
    pj = "pj"


class ClientStatus(str, enum.Enum):
    lead = "lead"
    active = "active"
    inactive = "inactive"
    delinquent = "delinquent"
    blocked = "blocked"


# ENT-002 — identidade é o conjunto de DÍGITOS do documento, não a string
# digitada. O índice é FUNCIONAL por isso: "29.091.958/0001-17" e
# "29091958000117" são a mesma pessoa e um índice na coluna crua deixaria os
# dois entrarem (foi o duplicado da ELODI, spec Isis §4.2.3). Parcial: nulo,
# vazio e apagado logicamente não disputam unicidade. Por TENANT, nunca global
# — o mesmo produtor pode ser cliente de duas consultorias (Princípio 4).
_DOC_DIGITOS = "regexp_replace(cpf_cnpj, '[^0-9]', '', 'g')"


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    client_type = Column(Enum(ClientType), default=ClientType.pf, nullable=False)
    full_name = Column(String, nullable=False)
    legal_name = Column(String, nullable=True)   # razão social para PJ
    cpf_cnpj = Column(String, index=True)
    email = Column(String)
    phone = Column(String)
    secondary_phone = Column(String, nullable=True)
    birth_date = Column(Date, nullable=True)

    status = Column(Enum(ClientStatus), default=ClientStatus.lead, nullable=False)
    source_channel = Column(String, nullable=True)   # whatsapp, indicacao, email, etc.
    notes = Column(Text, nullable=True)
    extra_json = Column(Text, nullable=True)   # JSON extra sem schema fixo

    # Sprint V (A1+F2) — proveniência por campo: {field: "raw"|"ai_extracted"|"human_validated"}.
    # Permite à UI exibir badge "extraído pela IA" e ao consultor validar manualmente.
    field_sources = Column(PortableJSON, nullable=True, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # `ddl_if`: a expressão usa regexp_replace, que só existe no PostgreSQL.
    # `tests/models/test_types.py` faz create_all da metadata inteira em
    # SQLite; sem o guard de dialeto, o CREATE INDEX quebraria aquele teste.
    __table_args__ = (
        Index(
            "uq_clients_tenant_documento_normalizado",
            text("tenant_id"),
            text(_DOC_DIGITOS),
            unique=True,
            postgresql_where=text(
                f"cpf_cnpj IS NOT NULL AND deleted_at IS NULL AND {_DOC_DIGITOS} <> ''"
            ),
        ).ddl_if(dialect="postgresql"),
    )

    tenant = relationship("Tenant")
    processes = relationship("Process", back_populates="client")
    # ENT-001 — representantes da PJ. Subordinados: somem com o cliente.
    # `lazy="selectin"`: o representante agora viaja no schema de resposta do
    # Client, e o endpoint de LISTA devolve N clientes. Com lazy padrão isso
    # seria um SELECT por cliente (N+1) toda vez que a tela de clientes abre;
    # com selectin é UM SELECT a mais para o lote inteiro.
    representatives = relationship(
        "ClientRepresentative", back_populates="client",
        cascade="all, delete-orphan", passive_deletes=True,
        lazy="selectin",
    )
