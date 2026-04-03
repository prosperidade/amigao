from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app.repositories import PropertyRepository
from app.schemas.property import Property, PropertyCreate, PropertyUpdate

router = APIRouter()


@router.post("/", response_model=Property)
def create_property(
    *,
    db: Session = Depends(deps.get_db),
    property_in: PropertyCreate,
    current_user: User = Depends(deps.get_current_internal_user),
):
    repo = PropertyRepository(db, current_user.tenant_id)
    db_obj = repo.create(property_in.model_dump())
    db.commit()
    db.refresh(db_obj)
    return db_obj


@router.get("/", response_model=list[Property])
def get_properties(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    client_id: Optional[int] = None,
    current_user: User = Depends(deps.get_current_internal_user),
):
    repo = PropertyRepository(db, current_user.tenant_id)
    if client_id:
        return repo.list_by_client(client_id, skip=skip, limit=limit)
    return repo.list(skip=skip, limit=limit)


@router.get("/{id}", response_model=Property)
def get_property(
    id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_internal_user),
):
    repo = PropertyRepository(db, current_user.tenant_id)
    return repo.get_or_404(id, detail="Property not found")


@router.patch("/{id}", response_model=Property)
def update_property(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    property_in: PropertyUpdate,
    current_user: User = Depends(deps.get_current_internal_user),
):
    repo = PropertyRepository(db, current_user.tenant_id)
    property_obj = repo.update(id, property_in.model_dump(exclude_unset=True), detail="Property not found")
    db.commit()
    db.refresh(property_obj)
    return property_obj
