from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Float, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base
from geoalchemy2 import Geometry


class Property(Base):
    """Imóvel rural — entidade central fundiária."""
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)

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

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tenant = relationship("Tenant")
    client = relationship("Client")
