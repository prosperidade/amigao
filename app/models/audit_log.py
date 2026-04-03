from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class AuditLog(Base):
    """Modelo genérico de log de auditoria para rastreamento de ações no sistema."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    entity_type = Column(String, nullable=False, index=True) # Ex: 'process', 'task'
    entity_id = Column(Integer, nullable=False, index=True)

    action = Column(String, nullable=False) # Ex: 'status_changed', 'created', 'updated'

    old_value = Column(String, nullable=True)
    new_value = Column(String, nullable=True)
    details = Column(Text, nullable=True) # Para armazenar JSON com mais info se necessário

    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)

    hash_sha256 = Column(String, nullable=True)
    hash_previous = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    tenant = relationship("Tenant")
    user = relationship("User")
