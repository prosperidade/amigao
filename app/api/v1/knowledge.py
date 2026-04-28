"""Knowledge API — busca semantica e indexacao do knowledge_catalog.

Sprint U (2026-04-27).

Endpoints:
- `GET  /api/v1/knowledge/search` — busca top-k chunks por similaridade.
- `POST /api/v1/knowledge/index`  — indexa texto avulso (oficio, manual).
- `POST /api/v1/knowledge/reindex-legislation` — re-indexa todo corpus legislativo.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeIndexResponse,
    KnowledgeIndexTextRequest,
    KnowledgeSearchHit,
    KnowledgeSearchResponse,
)
from app.services.embeddings import EmbeddingError
from app.services.knowledge_catalog import index_text, search

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/search", response_model=KnowledgeSearchResponse)
def knowledge_search(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
    q: str = Query(..., min_length=2, description="Texto livre da busca."),
    limit: int = Query(10, ge=1, le=50),
    source_type: Optional[str] = Query(None, description="legislation, oficio, manual..."),
    jurisdiction: Optional[str] = Query(None, description="federal, estadual, municipal"),
    uf: Optional[str] = Query(None, min_length=2, max_length=2),
    identifier: Optional[str] = None,
    min_similarity: float = Query(0.0, ge=-1.0, le=1.0),
) -> Any:
    """Busca top-k chunks por similaridade cosseno.

    O tenant_id do usuario filtra para chunks globais (NULL) + do proprio tenant.
    """
    try:
        results = search(
            db,
            q,
            limit=limit,
            tenant_id=current_user.tenant_id,
            source_type=source_type,
            jurisdiction=jurisdiction,
            uf=uf,
            identifier=identifier,
            min_similarity=min_similarity,
        )
    except EmbeddingError as exc:
        logger.warning("knowledge.search embed_error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Embeddings indisponiveis: {exc}",
        ) from exc

    hits = [
        KnowledgeSearchHit(
            id=r.id,
            source_type=r.source_type,
            source_ref=r.source_ref,
            title=r.title,
            section=r.section,
            chunk_text=r.chunk_text,
            jurisdiction=r.jurisdiction,
            uf=r.uf,
            agency=r.agency,
            identifier=r.identifier,
            similarity=r.similarity,
        )
        for r in results
    ]
    return KnowledgeSearchResponse(query=q, results=hits, total=len(hits))


@router.post(
    "/index",
    response_model=KnowledgeIndexResponse,
    status_code=status.HTTP_201_CREATED,
)
def knowledge_index_text(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
    body: KnowledgeIndexTextRequest,
) -> Any:
    """Indexa texto avulso (oficio, manual, jurisprudencia)."""
    try:
        inserted = index_text(
            db,
            source_type=body.source_type,
            source_ref=body.source_ref,
            body=body.body,
            title=body.title,
            tenant_id=current_user.tenant_id,
            jurisdiction=body.jurisdiction,
            uf=body.uf,
            agency=body.agency,
            identifier=body.identifier,
        )
        db.commit()
    except EmbeddingError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Embeddings indisponiveis: {exc}",
        ) from exc

    # `skipped` so e exato com a contagem original — calculamos via re-chunking aqui
    # se quisermos. Por ora retornamos 0; service ja loga skipped/inserted.
    return KnowledgeIndexResponse(
        source_type=body.source_type,
        source_ref=body.source_ref,
        inserted=inserted,
        skipped=0,
    )


@router.post("/reindex-legislation", status_code=status.HTTP_202_ACCEPTED)
def knowledge_reindex_legislation(
    *,
    current_user: User = Depends(get_current_internal_user),
) -> dict[str, Any]:
    """Enfileira re-indexacao de todo o corpus de legislation_documents."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas superusuarios podem disparar re-indexacao em massa.",
        )
    from app.workers.knowledge_indexer import reindex_all_legislation

    task = reindex_all_legislation.delay()
    return {"status": "queued", "task_id": task.id}
