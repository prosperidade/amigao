from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PropertyBase(BaseModel):
    client_id: int
    name: str
    registry_number: Optional[str] = None
    ccir: Optional[str] = None
    nirf: Optional[str] = None
    car_code: Optional[str] = None
    car_status: Optional[str] = None
    total_area_ha: Optional[float] = None
    municipality: Optional[str] = None
    state: Optional[str] = None
    biome: Optional[str] = None
    has_embargo: bool = False
    status: str = "active"
    notes: Optional[str] = None


class PropertyCreate(PropertyBase):
    pass


class PropertyUpdate(BaseModel):
    name: Optional[str] = None
    registry_number: Optional[str] = None
    ccir: Optional[str] = None
    nirf: Optional[str] = None
    car_code: Optional[str] = None
    car_status: Optional[str] = None
    total_area_ha: Optional[float] = None
    municipality: Optional[str] = None
    state: Optional[str] = None
    biome: Optional[str] = None
    has_embargo: Optional[bool] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class Property(PropertyBase):
    id: int
    tenant_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
