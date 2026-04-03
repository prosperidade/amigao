"""
Base repository — tenant-scoped CRUD operations.

Every concrete repository inherits from ``BaseRepository`` and gets
list / get / create / update / delete for free.  All queries are
automatically scoped to the caller's ``tenant_id``.
"""

from __future__ import annotations

from typing import Any, Generic, Optional, Sequence, TypeVar

from sqlalchemy.orm import Session

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Tenant-scoped CRUD repository."""

    model: type[ModelT]

    def __init__(self, db: Session, tenant_id: int) -> None:
        self.db = db
        self.tenant_id = tenant_id

    # -- Queries ---------------------------------------------------------------

    def _base_query(self):
        return self.db.query(self.model).filter(
            self.model.tenant_id == self.tenant_id,  # type: ignore[attr-defined]
        )

    def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[list] = None,
    ) -> Sequence[ModelT]:
        q = self._base_query()
        for f in filters or []:
            q = q.filter(f)
        return q.offset(skip).limit(limit).all()

    def get(self, entity_id: int) -> Optional[ModelT]:
        return self._base_query().filter(self.model.id == entity_id).first()  # type: ignore[attr-defined]

    def get_or_404(self, entity_id: int, *, detail: str = "Not found") -> ModelT:
        obj = self.get(entity_id)
        if obj is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=detail)
        return obj

    # -- Mutations -------------------------------------------------------------

    def create(self, data: dict[str, Any]) -> ModelT:
        obj = self.model(**data, tenant_id=self.tenant_id)  # type: ignore[call-arg]
        self.db.add(obj)
        self.db.flush()
        return obj

    def update(self, entity_id: int, data: dict[str, Any], *, detail: str = "Not found") -> ModelT:
        obj = self.get_or_404(entity_id, detail=detail)
        for field, value in data.items():
            setattr(obj, field, value)
        self.db.flush()
        return obj

    def delete(self, entity_id: int, *, detail: str = "Not found") -> None:
        obj = self.get_or_404(entity_id, detail=detail)
        self.db.delete(obj)
        self.db.flush()
