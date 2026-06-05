"""ExtractedFieldStaging repository (Ficha 01, FASE 1)."""

from __future__ import annotations

from typing import Optional, Sequence

from app.models.extracted_field_staging import (
    ExtractedFieldStaging,
    ExtractedFieldStatus,
)
from app.repositories.base import BaseRepository


class ExtractedFieldStagingRepository(BaseRepository[ExtractedFieldStaging]):
    model = ExtractedFieldStaging

    def list_by_process(
        self,
        process_id: int,
        *,
        status: Optional[ExtractedFieldStatus] = None,
        skip: int = 0,
        limit: int = 200,
    ) -> Sequence[ExtractedFieldStaging]:
        q = self._base_query().filter(
            ExtractedFieldStaging.process_id == process_id
        )
        if status is not None:
            q = q.filter(ExtractedFieldStaging.status == status)
        return (
            q.order_by(ExtractedFieldStaging.id.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
