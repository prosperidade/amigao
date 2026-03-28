from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.api import deps
from app.models.property import Property as PropertyModel
from app.models.user import User
from app.schemas.property import PropertyCreate, PropertyUpdate, Property

router = APIRouter()

@router.post("/", response_model=Property)
def create_property(
    *,
    db: Session = Depends(deps.get_db),
    property_in: PropertyCreate,
    current_user: User = Depends(deps.get_current_internal_user),
):
    db_obj = PropertyModel(**property_in.dict(), tenant_id=current_user.tenant_id)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

@router.get("/", response_model=List[Property])
def get_properties(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    client_id: Optional[int] = None,
    current_user: User = Depends(deps.get_current_internal_user),
):
    query = db.query(PropertyModel).filter(PropertyModel.tenant_id == current_user.tenant_id)
    if client_id:
        query = query.filter(PropertyModel.client_id == client_id)
    return query.offset(skip).limit(limit).all()

@router.get("/{id}", response_model=Property)
def get_property(
    id: int, 
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_internal_user),
):
    property_obj = db.query(PropertyModel).filter(
        PropertyModel.id == id,
        PropertyModel.tenant_id == current_user.tenant_id
    ).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")
    return property_obj

@router.patch("/{id}", response_model=Property)
def update_property(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    property_in: PropertyUpdate,
    current_user: User = Depends(deps.get_current_internal_user),
):
    property_obj = db.query(PropertyModel).filter(
        PropertyModel.id == id,
        PropertyModel.tenant_id == current_user.tenant_id
    ).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")
        
    update_data = property_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(property_obj, field, value)
        
    db.commit()
    db.refresh(property_obj)
    return property_obj
