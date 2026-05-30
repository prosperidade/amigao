"""
Credential — login/senha de portais externos por cliente (PR 2.3).

Cofre de credenciais de terceiros: SEMA, IBAMA, SICAR, INCRA, banco, etc. A
**senha** vive criptografada em repouso na coluna `password_encrypted` via o type
decorator `EncryptedString` (ADR-014) — o ORM lê/escreve plaintext, o banco só
guarda ciphertext. O `login` (usuário) é um identificador e fica em plaintext.

Primeiro consumidor real do `EncryptedString` em coluna de tabela (fecha a
dívida #27 — a PR LLM usou cripto em JSONB, não em coluna String).
"""
import enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.types import EncryptedString


class PortalType(str, enum.Enum):
    """Portais conhecidos. Coluna é String(50) (não enum Postgres) — aceitar um
    portal novo NÃO exige migration, só adicionar o valor aqui."""
    sema = "sema"
    ibama = "ibama"
    sicar = "sicar"
    incra = "incra"
    banco = "banco"
    cooperativa = "cooperativa"
    outro = "outro"


class Credential(Base):
    __tablename__ = "credentials"

    id = Column(Integer, primary_key=True, index=True)
    # Multi-tenant: toda query filtra por tenant_id (validado na escrita).
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Credencial pertence a um cliente; cascade ao deletar o cliente.
    client_id = Column(
        Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True
    )

    portal = Column(String(50), nullable=False)            # ver PortalType
    label = Column(String, nullable=True)                  # ex.: "SEMA-GO — produtor X"
    login = Column(String, nullable=True)                  # usuário (identificador, plaintext)
    # Senha criptografada em repouso (ADR-014). Plaintext no ORM, ciphertext no banco.
    password_encrypted = Column(EncryptedString, nullable=True)
    url = Column(String, nullable=True)                    # URL do portal
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    tenant = relationship("Tenant")
    client = relationship("Client")
