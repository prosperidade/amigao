from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.types import PortableJSON


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)

    # Sprint F Bloco 2 (Camada 4 — Configurações):
    # JSON aninhado com preferências do usuário organizadas em 4 grupos:
    # profile, notifications, operational, ai. Ver app/schemas/user_preferences.py.
    preferences = Column(PortableJSON, nullable=True, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tenant = relationship("Tenant")
