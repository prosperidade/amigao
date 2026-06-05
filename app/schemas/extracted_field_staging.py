"""Schemas Pydantic v2 do staging de campos extraídos (Ficha 01, FASE 1).

Apenas leitura nesta fase — o staging é escrito pelos agentes (fase 2) e decidido
pelo consultor na tela de Alertas (fase 4).
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from app.models.extracted_field_staging import ExtractedFieldStatus


class ExtractedFieldStagingOut(BaseModel):
    id: int
    tenant_id: int
    process_id: Optional[int] = None
    document_id: Optional[int] = None
    source_doc_type: Optional[str] = None
    field_name: str
    field_value: Optional[Any] = None
    confidence: Optional[str] = None
    target_entity: Optional[str] = None
    target_field: Optional[str] = None
    matricula_hint: Optional[str] = None
    status: ExtractedFieldStatus
    decided_value: Optional[Any] = None
    decided_by_user_id: Optional[int] = None
    decided_at: Optional[datetime] = None
    created_by_agent: Optional[str] = None
    ai_job_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
