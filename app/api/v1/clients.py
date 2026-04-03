from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.user import User
from app.repositories import ClientRepository
from app.schemas.client import Client, ClientCreate, ClientUpdate

router = APIRouter()


@router.get("/", response_model=list[Client])
def list_clients(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Lista todos os clientes do tenant autenticado."""
    repo = ClientRepository(db, current_user.tenant_id)
    return repo.list(skip=skip, limit=limit)


@router.post("/", response_model=Client, status_code=status.HTTP_201_CREATED)
def create_client(
    *,
    db: Session = Depends(get_db),
    client_in: ClientCreate,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Cria um novo cliente para o tenant autenticado."""
    repo = ClientRepository(db, current_user.tenant_id)
    client = repo.create(client_in.model_dump())
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
    repo = ClientRepository(db, current_user.tenant_id)
    return repo.get_or_404(client_id, detail="Cliente não encontrado")


@router.put("/{client_id}", response_model=Client)
@router.patch("/{client_id}", response_model=Client)
def update_client(
    client_id: int,
    *,
    db: Session = Depends(get_db),
    client_in: ClientUpdate,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Atualiza os dados de um cliente."""
    repo = ClientRepository(db, current_user.tenant_id)
    client = repo.update(client_id, client_in.model_dump(exclude_unset=True), detail="Cliente não encontrado")
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
    repo = ClientRepository(db, current_user.tenant_id)
    repo.delete(client_id, detail="Cliente não encontrado")
    db.commit()
