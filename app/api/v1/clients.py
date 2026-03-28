from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.client import Client as ClientModel
from app.models.user import User
from app.schemas.client import Client, ClientCreate, ClientUpdate

router = APIRouter()


@router.get("/", response_model=List[Client])
def list_clients(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Lista todos os clientes do tenant autenticado."""
    clients = (
        db.query(ClientModel)
        .filter(ClientModel.tenant_id == current_user.tenant_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return clients


@router.post("/", response_model=Client, status_code=status.HTTP_201_CREATED)
def create_client(
    *,
    db: Session = Depends(get_db),
    client_in: ClientCreate,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Cria um novo cliente para o tenant autenticado."""
    client = ClientModel(
        **client_in.dict(exclude={"tenant_id"}),
        tenant_id=current_user.tenant_id,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("/{client_id}", response_model=Client)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Retorna um cliente pelo ID."""
    client = (
        db.query(ClientModel)
        .filter(ClientModel.id == client_id, ClientModel.tenant_id == current_user.tenant_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    return client


@router.put("/{client_id}", response_model=Client)
def update_client(
    client_id: int,
    *,
    db: Session = Depends(get_db),
    client_in: ClientUpdate,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Atualiza os dados de um cliente."""
    client = (
        db.query(ClientModel)
        .filter(ClientModel.id == client_id, ClientModel.tenant_id == current_user.tenant_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    update_data = client_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(client, field, value)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> None:
    """Remove um cliente."""
    client = (
        db.query(ClientModel)
        .filter(ClientModel.id == client_id, ClientModel.tenant_id == current_user.tenant_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    db.delete(client)
    db.commit()
