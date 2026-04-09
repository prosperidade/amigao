"""Schemas Pydantic para legislacao."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class LegislationDocumentCreate(BaseModel):
    title: str
    source_type: str  # lei, decreto, resolucao, instrucao_normativa, portaria
    identifier: Optional[str] = None  # "Lei 12.651/2012"
    uf: Optional[str] = None
    scope: str = "federal"
    municipality: Optional[str] = None
    agency: Optional[str] = None
    effective_date: Optional[datetime] = None
    url: Optional[str] = None
    demand_types: Optional[list[str]] = None
    keywords: Optional[list[str]] = None
    full_text: Optional[str] = None  # texto completo (alternativa ao upload)


class LegislationDocumentRead(BaseModel):
    id: int
    tenant_id: Optional[int] = None
    title: str
    source_type: str
    identifier: Optional[str] = None
    uf: Optional[str] = None
    scope: str
    municipality: Optional[str] = None
    agency: Optional[str] = None
    effective_date: Optional[datetime] = None
    url: Optional[str] = None
    status: str
    token_count: int
    demand_types: Optional[list[str]] = None
    keywords: Optional[list[str]] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class LegislationSearchRequest(BaseModel):
    uf: Optional[str] = None
    scope: Optional[str] = None
    agency: Optional[str] = None
    demand_type: Optional[str] = None
    keyword: Optional[str] = None
    max_results: int = 20


class LegislationSearchResponse(BaseModel):
    documents: list[LegislationDocumentRead]
    total_tokens: int
