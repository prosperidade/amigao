from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Boolean, Text, Date
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from app.models.base import Base


class ClientType(str, enum.Enum):
    pf = "pf"
    pj = "pj"


class ClientStatus(str, enum.Enum):
    lead = "lead"
    active = "active"
    inactive = "inactive"
    delinquent = "delinquent"


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

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    tenant = relationship("Tenant")
    processes = relationship("Process", back_populates="client")
