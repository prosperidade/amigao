"""Matricula repository (Ficha 01, FASE 1)."""

from __future__ import annotations

from typing import Sequence

from app.models.matricula import Matricula
from app.repositories.base import BaseRepository


class MatriculaRepository(BaseRepository[Matricula]):
    model = Matricula

    def list_by_property(
        self, property_id: int, *, skip: int = 0, limit: int = 100
    ) -> Sequence[Matricula]:
        return (
            self._base_query()
            .filter(Matricula.property_id == property_id)
            .order_by(Matricula.id.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
