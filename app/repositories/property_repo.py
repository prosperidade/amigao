"""Property repository."""

from __future__ import annotations

from typing import Sequence

from app.models.property import Property
from app.repositories.base import BaseRepository


class PropertyRepository(BaseRepository[Property]):
    model = Property

    def list_by_client(
        self, client_id: int, *, skip: int = 0, limit: int = 100
    ) -> Sequence[Property]:
        return (
            self._base_query()
            .filter(Property.client_id == client_id)
            .offset(skip)
            .limit(limit)
            .all()
        )
