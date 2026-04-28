"""knowledge_catalog service — indexacao e busca semantica.

Sprint U (2026-04-27).

API publica:
- `index_legislation_document(session, doc_id)`: re-indexa um LegislationDocument
  (idempotente via content_hash do chunk).
- `index_text(session, source_type, source_ref, text, **metadata)`: indexa
  texto avulso (oficio, manual, jurisprudencia).
- `search(session, query, *, ...)`: top-k por similaridade cosseno com filtros.

A coluna `embedding` e gravada/lida via SQL puro porque o tipo `vector` da
pgvector nao tem reflexao no SQLAlchemy sem o pacote python `pgvector`,
e queremos manter requirements.txt enxuto.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import date as _date
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.knowledge_catalog import KnowledgeChunk
from app.models.legislation import LegislationDocument
from app.services.chunking import TextChunk, chunk_text
from app.services.embeddings import EMBEDDING_DIM, EMBEDDING_MODEL, embed_batch, embed_text

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Resultado de busca semantica."""

    id: int
    source_type: str
    source_ref: str
    title: str | None
    section: str | None
    chunk_text: str
    jurisdiction: str | None
    uf: str | None
    agency: str | None
    identifier: str | None
    similarity: float  # 0.0..1.0 (cosseno; 1.0 = identico)


def _vector_literal(values: list[float]) -> str:
    """Converte list[float] em literal pgvector ('[v1,v2,...]')."""
    return "[" + ",".join(f"{v:.7f}" for v in values) + "]"


def _hash_chunk(source_type: str, source_ref: str, chunk_index: int, body: str) -> str:
    h = hashlib.sha256()
    h.update(source_type.encode("utf-8"))
    h.update(b"\x00")
    h.update(source_ref.encode("utf-8"))
    h.update(b"\x00")
    h.update(str(chunk_index).encode("ascii"))
    h.update(b"\x00")
    h.update(body.encode("utf-8"))
    return h.hexdigest()


def _existing_hashes(session: Session, hashes: Iterable[str]) -> set[str]:
    rows = (
        session.query(KnowledgeChunk.content_hash)
        .filter(KnowledgeChunk.content_hash.in_(list(hashes)))
        .all()
    )
    return {row[0] for row in rows}


def _insert_chunks(
    session: Session,
    *,
    source_type: str,
    source_ref: str,
    chunks: list[TextChunk],
    embeddings: list[list[float]],
    base_metadata: dict[str, Any],
    extra_metadata: dict[str, Any] | None,
) -> int:
    """Insere chunks novos via SQL puro (necessario para a coluna vector)."""
    if not chunks:
        return 0
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"chunks={len(chunks)} != embeddings={len(embeddings)} — "
            "tamanho do batch divergente."
        )

    sql = text(
        """
        INSERT INTO knowledge_catalog (
            tenant_id, source_type, source_ref, chunk_index,
            title, section, chunk_text, chunk_tokens,
            jurisdiction, uf, agency, identifier, effective_date,
            embedding, embedding_model, embedding_dim,
            content_hash, extra_metadata
        ) VALUES (
            :tenant_id, :source_type, :source_ref, :chunk_index,
            :title, :section, :chunk_text, :chunk_tokens,
            :jurisdiction, :uf, :agency, :identifier, :effective_date,
            CAST(:embedding AS vector), :embedding_model, :embedding_dim,
            :content_hash, CAST(:extra_metadata AS jsonb)
        )
        ON CONFLICT (content_hash) DO NOTHING
        """
    )

    inserted = 0
    import json as _json

    for chunk, vector in zip(chunks, embeddings):
        params = {
            "tenant_id": base_metadata.get("tenant_id"),
            "source_type": source_type,
            "source_ref": source_ref,
            "chunk_index": chunk.index,
            "title": base_metadata.get("title"),
            "section": chunk.section,
            "chunk_text": chunk.text,
            "chunk_tokens": chunk.tokens,
            "jurisdiction": base_metadata.get("jurisdiction"),
            "uf": base_metadata.get("uf"),
            "agency": base_metadata.get("agency"),
            "identifier": base_metadata.get("identifier"),
            "effective_date": base_metadata.get("effective_date"),
            "embedding": _vector_literal(vector),
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dim": EMBEDDING_DIM,
            "content_hash": _hash_chunk(source_type, source_ref, chunk.index, chunk.text),
            "extra_metadata": _json.dumps(extra_metadata) if extra_metadata else None,
        }
        result = session.execute(sql, params)
        inserted += result.rowcount or 0

    session.flush()
    return inserted


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------

def index_text(
    session: Session,
    *,
    source_type: str,
    source_ref: str,
    body: str,
    title: str | None = None,
    tenant_id: int | None = None,
    jurisdiction: str | None = None,
    uf: str | None = None,
    agency: str | None = None,
    identifier: str | None = None,
    effective_date: _date | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> int:
    """Indexa texto avulso (oficio, manual, etc). Retorna chunks inseridos."""
    chunks = chunk_text(body)
    if not chunks:
        return 0

    # Filtra chunks ja indexados.
    hashes = [
        _hash_chunk(source_type, source_ref, c.index, c.text) for c in chunks
    ]
    existing = _existing_hashes(session, hashes)
    new_pairs = [
        (chunk, h) for chunk, h in zip(chunks, hashes) if h not in existing
    ]
    if not new_pairs:
        logger.info(
            "knowledge.index skip source=%s ref=%s — todos os %d chunks ja indexados",
            source_type, source_ref, len(chunks),
        )
        return 0

    new_chunks = [c for c, _ in new_pairs]
    embeddings = embed_batch([c.text for c in new_chunks])

    base_metadata = {
        "tenant_id": tenant_id,
        "title": title,
        "jurisdiction": jurisdiction,
        "uf": uf,
        "agency": agency,
        "identifier": identifier,
        "effective_date": effective_date,
    }
    inserted = _insert_chunks(
        session,
        source_type=source_type,
        source_ref=source_ref,
        chunks=new_chunks,
        embeddings=embeddings,
        base_metadata=base_metadata,
        extra_metadata=extra_metadata,
    )
    logger.info(
        "knowledge.index ok source=%s ref=%s inserted=%d skipped=%d",
        source_type, source_ref, inserted, len(chunks) - inserted,
    )
    return inserted


def index_legislation_document(session: Session, doc_id: int) -> int:
    """Re-indexa um LegislationDocument no knowledge_catalog (idempotente)."""
    doc = session.get(LegislationDocument, doc_id)
    if doc is None:
        raise ValueError(f"LegislationDocument id={doc_id} nao encontrado.")
    if not doc.full_text:
        logger.info("knowledge.index skip doc=%d — full_text vazio", doc_id)
        return 0

    return index_text(
        session,
        source_type="legislation",
        source_ref=f"legislation_documents:{doc.id}",
        body=doc.full_text,
        title=doc.title,
        tenant_id=doc.tenant_id,
        jurisdiction=doc.scope,
        uf=doc.uf,
        agency=doc.agency,
        identifier=doc.identifier,
        effective_date=doc.effective_date.date() if doc.effective_date else None,
        extra_metadata={
            "demand_types": doc.demand_types,
            "keywords": doc.keywords,
            "source_type_legislation": doc.source_type,
        },
    )


def search(
    session: Session,
    query: str,
    *,
    limit: int = 10,
    tenant_id: int | None = None,
    source_type: str | None = None,
    jurisdiction: str | None = None,
    uf: str | None = None,
    identifier: str | None = None,
    min_similarity: float = 0.0,
) -> list[SearchResult]:
    """Busca top-k chunks por similaridade cosseno.

    `tenant_id`: se informado, retorna chunks do tenant + chunks globais (NULL).
                 se None, retorna apenas globais.
    """
    if not query or not query.strip():
        return []

    query_vector = embed_text(query, task_type="RETRIEVAL_QUERY")
    vector_literal = _vector_literal(query_vector)

    where: list[str] = []
    params: dict[str, Any] = {"vector": vector_literal, "limit": limit}

    if tenant_id is not None:
        where.append("(tenant_id IS NULL OR tenant_id = :tenant_id)")
        params["tenant_id"] = tenant_id
    else:
        where.append("tenant_id IS NULL")

    if source_type:
        where.append("source_type = :source_type")
        params["source_type"] = source_type
    if jurisdiction:
        where.append("jurisdiction = :jurisdiction")
        params["jurisdiction"] = jurisdiction
    if uf:
        where.append("uf = :uf")
        params["uf"] = uf
    if identifier:
        where.append("identifier = :identifier")
        params["identifier"] = identifier

    where_sql = " AND ".join(where) if where else "TRUE"
    sql = text(
        f"""
        SELECT
            id, source_type, source_ref, title, section, chunk_text,
            jurisdiction, uf, agency, identifier,
            1.0 - (embedding <=> CAST(:vector AS vector)) AS similarity
        FROM knowledge_catalog
        WHERE {where_sql}
        ORDER BY embedding <=> CAST(:vector AS vector)
        LIMIT :limit
        """
    )
    rows = session.execute(sql, params).all()

    out: list[SearchResult] = []
    for row in rows:
        sim = float(row.similarity)
        if sim < min_similarity:
            continue
        out.append(
            SearchResult(
                id=row.id,
                source_type=row.source_type,
                source_ref=row.source_ref,
                title=row.title,
                section=row.section,
                chunk_text=row.chunk_text,
                jurisdiction=row.jurisdiction,
                uf=row.uf,
                agency=row.agency,
                identifier=row.identifier,
                similarity=sim,
            )
        )
    return out
