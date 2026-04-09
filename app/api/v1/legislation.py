"""
Legislation API — CRUD e busca de documentos legislativos.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.legislation import LegislationDocument
from app.models.user import User
from app.schemas.legislation import (
    LegislationDocumentCreate,
    LegislationDocumentRead,
    LegislationSearchRequest,
    LegislationSearchResponse,
)
from app.services.legislation_service import (
    build_legislation_context,
    ingest_legislation_document,
    search_legislation,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/documents", response_model=LegislationDocumentRead, status_code=status.HTTP_201_CREATED)
def create_legislation_document(
    *,
    db: Session = Depends(get_db),
    body: LegislationDocumentCreate,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Registra um novo documento legislativo com texto direto."""
    doc = LegislationDocument(
        tenant_id=None,  # legislacao e global
        title=body.title,
        source_type=body.source_type,
        identifier=body.identifier,
        uf=body.uf,
        scope=body.scope,
        municipality=body.municipality,
        agency=body.agency,
        effective_date=body.effective_date,
        url=body.url,
        demand_types=body.demand_types,
        keywords=body.keywords,
        status="pending",
    )
    db.add(doc)
    db.flush()

    if body.full_text:
        ingest_legislation_document(doc.id, db, raw_text=body.full_text)

    db.commit()
    db.refresh(doc)
    return doc


@router.post("/documents/{doc_id}/upload", response_model=LegislationDocumentRead)
def upload_legislation_pdf(
    doc_id: int,
    *,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Upload de PDF para um documento legislativo existente."""
    doc = db.query(LegislationDocument).filter(LegislationDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento nao encontrado")

    file_bytes = file.file.read()
    ingest_legislation_document(doc.id, db, file_bytes=file_bytes)

    db.commit()
    db.refresh(doc)
    return doc


@router.get("/documents", response_model=list[LegislationDocumentRead])
def list_legislation_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
    scope: Optional[str] = Query(None),
    uf: Optional[str] = Query(None),
    agency: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = 0,
    limit: int = 50,
) -> Any:
    """Lista documentos legislativos com filtros."""
    q = db.query(LegislationDocument)

    if scope:
        q = q.filter(LegislationDocument.scope == scope)
    if uf:
        q = q.filter((LegislationDocument.uf == uf) | (LegislationDocument.uf.is_(None)))
    if agency:
        q = q.filter(LegislationDocument.agency == agency)
    if status_filter:
        q = q.filter(LegislationDocument.status == status_filter)

    return q.order_by(LegislationDocument.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/documents/{doc_id}", response_model=LegislationDocumentRead)
def get_legislation_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Retorna um documento legislativo pelo ID."""
    doc = db.query(LegislationDocument).filter(LegislationDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento nao encontrado")
    return doc


@router.post("/search", response_model=LegislationSearchResponse)
def search_legislation_endpoint(
    *,
    db: Session = Depends(get_db),
    body: LegislationSearchRequest,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Busca documentos legislativos por metadados para context loading."""
    docs = search_legislation(
        db,
        uf=body.uf,
        scope=body.scope,
        agency=body.agency,
        demand_type=body.demand_type,
        keyword=body.keyword,
        max_results=body.max_results,
    )
    total_tokens = sum(d.token_count for d in docs)
    return LegislationSearchResponse(documents=docs, total_tokens=total_tokens)


@router.post("/documents/{doc_id}/reindex", response_model=LegislationDocumentRead)
def reindex_legislation_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Re-processa o texto de um documento legislativo."""
    doc = db.query(LegislationDocument).filter(LegislationDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento nao encontrado")
    if not doc.full_text:
        raise HTTPException(status_code=400, detail="Documento sem texto — faca upload primeiro")

    ingest_legislation_document(doc.id, db, raw_text=doc.full_text)
    db.commit()
    db.refresh(doc)
    return doc
