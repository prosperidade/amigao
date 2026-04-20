from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.types import PortableJSON


class Property(Base):
    """Imóvel rural — entidade central fundiária."""
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False, index=True)

    name = Column(String, nullable=False)
    registry_number = Column(String, nullable=True)   # matrícula
    ccir = Column(String, nullable=True)
    nirf = Column(String, nullable=True)
    car_code = Column(String, nullable=True)
    car_status = Column(String, nullable=True)         # ativo, pendente, cancelado, etc.

    total_area_ha = Column(Float, nullable=True)
    municipality = Column(String, nullable=True)
    state = Column(String(2), nullable=True)           # UF
    biome = Column(String, nullable=True)

    geom = Column(Geometry(geometry_type="GEOMETRY", srid=4674), nullable=True)

    has_embargo = Column(Boolean, default=False)
    status = Column(String, default="active")         # active, inactive, archived
    notes = Column(Text, nullable=True)

    # Regente Cam2 CAM2IH-007 — origem por campo: raw | ai_extracted | human_validated
    # Ex: {"car_code": "human_validated", "registry_number": "ai_extracted", ...}
    field_sources = Column(PortableJSON, nullable=True, default=dict)

    # Regente Cam2 CAM2IH-003/004 (Sprint H) — campos técnicos do Dashboard + Aba Informações
    rl_status = Column(String, nullable=True)           # averbada | proposta | pendente | cancelada
    app_area_ha = Column(Float, nullable=True)
    regulatory_issues = Column(PortableJSON, nullable=True, default=list)  # [{tipo, descricao, severidade}]
    area_documental_ha = Column(Float, nullable=True)
    area_grafica_ha = Column(Float, nullable=True)
    tipologia = Column(String, nullable=True)           # agricultura | pecuaria | misto | outro
    strategic_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tenant = relationship("Tenant")
    client = relationship("Client")
