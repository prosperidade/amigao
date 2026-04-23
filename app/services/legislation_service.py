"""
LegislationService — processa e busca documentos legislativos.

Estrategia: armazena texto completo, sem chunking.
Na consulta, filtra documentos relevantes por metadados e envia
o texto integral no contexto do Gemini (2M tokens window).
"""

from __future__ import annotations

import hashlib
import logging
from typing import Optional

from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.models.legislation import LegislationDocument

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Extratores de texto
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extrai texto de PDF usando pypdf."""
    try:
        import io

        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages)
    except ImportError:
        logger.warning("pypdf nao instalado — fallback para texto vazio")
        return ""


def extract_text_from_html(html: str) -> str:
    """Extrai texto limpo de HTML."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    except ImportError:
        logger.warning("beautifulsoup4 nao instalado — retornando HTML raw")
        return html


def _estimate_tokens(text: str) -> int:
    """Estimativa simples: ~4 chars por token em portugues."""
    return len(text) // 4


# ---------------------------------------------------------------------------
# Ingestao de documento
# ---------------------------------------------------------------------------

def ingest_legislation_document(
    doc_id: int,
    db: Session,
    *,
    raw_text: str | None = None,
    file_bytes: bytes | None = None,
    html_content: str | None = None,
) -> LegislationDocument:
    """
    Processa um documento legislativo: extrai texto, calcula hash, armazena texto completo.
    """
    doc = db.query(LegislationDocument).filter(LegislationDocument.id == doc_id).first()
    if not doc:
        raise ValueError(f"LegislationDocument {doc_id} nao encontrado")

    doc.status = "processing"
    db.flush()

    try:
        # 1. Extrair texto
        if raw_text:
            text = raw_text
        elif file_bytes:
            text = extract_text_from_pdf(file_bytes)
        elif html_content:
            text = extract_text_from_html(html_content)
        else:
            raise ValueError("Nenhuma fonte de texto fornecida")

        if not text.strip():
            doc.status = "failed"
            doc.error_message = "Texto extraido vazio"
            db.flush()
            return doc

        # 2. Armazenar texto completo
        doc.full_text = text
        doc.content_hash = hashlib.sha256(text.encode()).hexdigest()
        doc.token_count = _estimate_tokens(text)
        doc.status = "indexed"
        doc.error_message = None
        db.flush()

        logger.info(
            "legislation doc %d processado: ~%d tokens",
            doc_id, doc.token_count,
        )
        return doc

    except Exception as exc:
        doc.status = "failed"
        doc.error_message = str(exc)[:500]
        db.flush()
        logger.exception("Erro processando legislation doc %d", doc_id)
        raise


# ---------------------------------------------------------------------------
# Busca de documentos relevantes por metadados
# ---------------------------------------------------------------------------

def search_legislation(
    db: Session,
    *,
    uf: Optional[str] = None,
    scope: Optional[str] = None,
    agency: Optional[str] = None,
    demand_type: Optional[str] = None,
    keyword: Optional[str] = None,
    max_results: int = 20,
    max_total_tokens: int = 500_000,
) -> list[LegislationDocument]:
    """
    Busca documentos legislativos por metadados.
    Retorna documentos ordenados por relevancia ate o limite de tokens.
    O texto completo sera enviado no contexto do Gemini.
    """
    q = (
        db.query(LegislationDocument)
        .filter(LegislationDocument.status == "indexed")
        .filter(LegislationDocument.full_text.isnot(None))
    )

    # Filtros por metadados
    if uf:
        # Federal se aplica a todos + estadual do UF especifico
        q = q.filter(
            (LegislationDocument.uf == uf) | (LegislationDocument.uf.is_(None))
        )
    if scope:
        q = q.filter(LegislationDocument.scope == scope)
    if agency:
        q = q.filter(LegislationDocument.agency == agency)

    # Sprint -1 C — filtro por demand_type no array JSONB demand_types.
    # Docs com demand_types=NULL ficam FORA quando demand_type é especificado
    # (prioriza diploma especializado sobre diploma genérico).
    if demand_type:
        q = q.filter(
            cast(LegislationDocument.demand_types, JSONB).contains([demand_type])
        )

    # Busca textual por keyword no titulo ou texto
    if keyword:
        q = q.filter(
            LegislationDocument.title.ilike(f"%{keyword}%")
            | LegislationDocument.full_text.ilike(f"%{keyword}%")
        )

    # Ordenar por federal primeiro, depois por data
    docs = (
        q.order_by(
            LegislationDocument.scope.asc(),  # federal vem antes
            LegislationDocument.effective_date.desc().nulls_last(),
        )
        .limit(max_results)
        .all()
    )

    # Limitar por budget de tokens
    selected: list[LegislationDocument] = []
    total_tokens = 0
    for doc in docs:
        if total_tokens + doc.token_count > max_total_tokens:
            break
        selected.append(doc)
        total_tokens += doc.token_count

    logger.info(
        "legislation search: uf=%s, scope=%s, agency=%s, results=%d, tokens=%d",
        uf, scope, agency, len(selected), total_tokens,
    )
    return selected


def build_legislation_context(docs: list[LegislationDocument]) -> str:
    """
    Monta o contexto legislativo para enviar ao LLM.
    Cada documento e separado com header identificador.
    """
    if not docs:
        return ""

    parts: list[str] = []
    for doc in docs:
        header = f"--- {doc.identifier or doc.title} ({doc.scope}"
        if doc.uf:
            header += f"/{doc.uf}"
        if doc.agency:
            header += f" - {doc.agency}"
        header += ") ---"

        parts.append(header)
        parts.append(doc.full_text or "")
        parts.append("")

    return "\n".join(parts)
