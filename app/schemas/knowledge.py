"""Schemas Pydantic — knowledge_catalog (busca semantica).

Sprint U (2026-04-27).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class KnowledgeSearchHit(BaseModel):
    """Um chunk retornado por uma busca semantica."""

    id: int
    source_type: str
    source_ref: str
    title: Optional[str] = None
    section: Optional[str] = None
    chunk_text: str
    jurisdiction: Optional[str] = None
    uf: Optional[str] = None
    agency: Optional[str] = None
    identifier: Optional[str] = None
    similarity: float = Field(..., ge=-1.0, le=1.0)


class KnowledgeSearchResponse(BaseModel):
    """Resposta padrao do endpoint de busca."""

    query: str
    results: list[KnowledgeSearchHit]
    total: int


class KnowledgeIndexTextRequest(BaseModel):
    """Indexar texto avulso no catalogo."""

    source_type: str = Field(..., description="oficio | manual | jurisprudence | other")
    source_ref: str = Field(..., description="Identificador unico da fonte (ex: 'oficio:42')")
    title: Optional[str] = None
    body: str = Field(..., min_length=10)
    jurisdiction: Optional[str] = None
    uf: Optional[str] = None
    agency: Optional[str] = None
    identifier: Optional[str] = None


class KnowledgeIndexResponse(BaseModel):
    source_type: str
    source_ref: str
    inserted: int
    skipped: int
