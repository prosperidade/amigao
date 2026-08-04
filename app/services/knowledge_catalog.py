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
from typing import Any, Iterable, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.knowledge_catalog import KnowledgeChunk
from app.models.legislation import LegislationDocument
from app.services.chunking import TextChunk, chunk_text
from app.services.embeddings import (
    EMBEDDING_DIM,
    EspacoVetorialIncompativel,
    current_model,
    embed_batch,
    embed_text,
)
from app.services.vigencia import titulo_com_vigencia, vigencia_do_documento

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

    # ADR-037 — vigencia da norma. `vigencia_fim=None` = vigente. O rotulo
    # legivel ja vem embutido no `title`; estes campos existem para quem precisa
    # decidir em codigo (filtrar, ordenar, colorir na tela) sem parsear texto.
    vigencia_fim: _date | None = None
    sucessora_ref: str | None = None

    # Proveniencia (divida #97) — de onde veio o texto desta norma, e se a fonte
    # foi conferida. Viaja junto do trecho para que a tela possa dize-lo sem uma
    # segunda consulta.
    fonte_origem: str | None = None
    fonte_oficial: bool = False

    @property
    def historica(self) -> bool:
        return self.vigencia_fim is not None


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
    embedding_model: str,
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

    for chunk, vector in zip(chunks, embeddings, strict=False):
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
            "embedding_model": embedding_model,
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
    embedding_model: str | None = None,
) -> int:
    """Indexa texto avulso (oficio, manual, etc). Retorna chunks inseridos.

    `embedding_model` declara EM QUE ESPAÇO VETORIAL este texto está sendo
    escrito. Omitido, usa o provider configurado. Existe para o white-label
    (ADR-040): corpus com dois provedores significa dois índices, e a escrita
    precisa dizer qual está alimentando — nunca deduzir.
    """
    modelo = embedding_model or current_model()
    chunks = chunk_text(body)
    if not chunks:
        return 0

    # Filtra chunks ja indexados.
    hashes = [
        _hash_chunk(source_type, source_ref, c.index, c.text) for c in chunks
    ]
    existing = _existing_hashes(session, hashes)
    new_pairs = [
        (chunk, h) for chunk, h in zip(chunks, hashes, strict=False) if h not in existing
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
        embedding_model=modelo,
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

    # ADR-037 — o rótulo de norma revogada viaja NO DADO. Gravado aqui, no
    # título do chunk, ele chega a qualquer consumidor do trecho (inclusive ao
    # cabeçalho que o LegislacaoAgent monta para o modelo) sem que nenhum agente
    # precise saber que vigência existe.
    vig = vigencia_do_documento(doc)

    return index_text(
        session,
        source_type="legislation",
        source_ref=f"legislation_documents:{doc.id}",
        body=doc.full_text,
        title=titulo_com_vigencia(doc.title, vig),
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
            "vigencia_inicio": vig.inicio.isoformat() if vig.inicio else None,
            "vigencia_fim": vig.fim.isoformat() if vig.fim else None,
            "sucessora_ref": vig.sucessora_ref,
            "historica": vig.historica,
        },
    )


def search(
    session: Session,
    query: str,
    *,
    limit: int = 10,
    tenant_id: int | None = None,
    source_type: str | None = None,
    jurisdiction: str | Sequence[str] | None = None,
    uf: str | None = None,
    identifier: str | None = None,
    demand_type: str | None = None,
    vigente_em: _date | None = None,
    embedding_model: str | None = None,
    min_similarity: float = 0.0,
) -> list[SearchResult]:
    """Busca top-k chunks por similaridade cosseno.

    `tenant_id`: se informado, retorna chunks do tenant + chunks globais (NULL).
                 se None, retorna apenas globais.

    `vigente_em`: data do FATO. Restringe aos trechos de normas que valiam
                 naquela data — a defesa de um auto de 2007 recupera o Decreto
                 3.179/1999, e a consulta sobre um fato de hoje não. Omitido
                 (padrão), a busca traz tudo: a norma histórica continua
                 recuperável e chega ROTULADA como tal (ADR-037), porque
                 escondê-la seria pior que trazê-la avisada.
    """
    if not query or not query.strip():
        return []

    # TRAVA DE ESPAÇO VETORIAL (dívida #114). O vetor da consulta e os vetores
    # do índice PRECISAM vir do mesmo modelo: embeddings de provedores diferentes
    # são espaços distintos, e comparar distâncias entre eles não falha — devolve
    # trechos com similaridade de aparência normal e conteúdo aleatório. Pior que
    # o `probes=1` da #113: lá eram vizinhos subótimos do MESMO espaço.
    #
    # A busca passa a MIRAR um espaço: filtra pelo modelo esperado. Quem quiser
    # consultar outro índice (white-label, experimento) passa `embedding_model`
    # explicitamente — nunca por acidente de configuração.
    modelo = embedding_model or current_model()

    query_vector = embed_text(query, task_type="RETRIEVAL_QUERY")
    vector_literal = _vector_literal(query_vector)

    where: list[str] = ["kc.embedding_model = :embedding_model"]
    # LEFT JOIN sempre presente: e dele que saem vigencia e demand_types. Chunk
    # que nao vem de `legislation_documents` (oficio, manual) casa com NULL e
    # segue no resultado — por isso LEFT, nao INNER.
    join_sql = (
        "LEFT JOIN legislation_documents ld "
        "ON kc.source_type = 'legislation' "
        "AND kc.source_ref = CONCAT('legislation_documents:', ld.id::text)"
    )
    params: dict[str, Any] = {
        "vector": vector_literal, "limit": limit, "embedding_model": modelo,
    }

    if tenant_id is not None:
        where.append("(kc.tenant_id IS NULL OR kc.tenant_id = :tenant_id)")
        params["tenant_id"] = tenant_id
    else:
        where.append("kc.tenant_id IS NULL")

    if source_type:
        where.append("kc.source_type = :source_type")
        params["source_type"] = source_type
    if jurisdiction:
        # Aceita lista (ADR-034): a esfera FEDERAL do domínio corresponde a duas
        # jurisdições no corpus — `federal` e `nacional` (resoluções CONAMA e
        # afins). Exigir uma só deixaria metade da fundamentação federal de fora.
        juris = [jurisdiction] if isinstance(jurisdiction, str) else list(jurisdiction)
        if len(juris) == 1:
            where.append("kc.jurisdiction = :jurisdiction")
            params["jurisdiction"] = juris[0]
        else:
            marcadores = []
            for i, j in enumerate(juris):
                chave = f"jurisdiction_{i}"
                marcadores.append(f":{chave}")
                params[chave] = j
            where.append(f"kc.jurisdiction IN ({', '.join(marcadores)})")
    if uf:
        # Federal (uf IS NULL) é aplicável a qualquer UF — filtrar por UF não pode
        # excluir a legislação federal (caso #12: 761 chunks federais ficavam de
        # fora, restando só os 4.280 de GO). Inclui ambos.
        where.append("(kc.uf = :uf OR kc.uf IS NULL)")
        params["uf"] = uf
    if identifier:
        where.append("kc.identifier = :identifier")
        params["identifier"] = identifier
    if demand_type:
        # O predicado `@>` ja falha em linha NULL, entao o LEFT JOIN se comporta
        # como INNER aqui — mesmo resultado de antes, sem um segundo JOIN.
        where.append("CAST(ld.demand_types AS jsonb) @> CAST(:demand_types_filter AS jsonb)")
        import json as _json

        params["demand_types_filter"] = _json.dumps([demand_type])
    if vigente_em:
        # ADR-037 — vigente NA DATA DO FATO. Documento sem vigencia declarada
        # (todo o corpus anterior a esta coluna) conta como vigente: a ausencia
        # de curadoria nao pode apagar trecho da busca.
        where.append(
            "((ld.vigencia_inicio IS NULL OR ld.vigencia_inicio <= :vigente_em) "
            "AND (ld.vigencia_fim IS NULL OR ld.vigencia_fim >= :vigente_em))"
        )
        params["vigente_em"] = vigente_em

    where_sql = " AND ".join(where) if where else "TRUE"
    sql = text(
        f"""
        SELECT
            kc.id, kc.source_type, kc.source_ref, kc.title, kc.section, kc.chunk_text,
            kc.jurisdiction, kc.uf, kc.agency, kc.identifier,
            ld.vigencia_fim AS vigencia_fim, ld.sucessora_ref AS sucessora_ref,
            ld.fonte_origem AS fonte_origem, ld.fonte_oficial AS fonte_oficial,
            1.0 - (kc.embedding <=> CAST(:vector AS vector)) AS similarity
        FROM knowledge_catalog kc
        {join_sql}
        WHERE {where_sql}
        ORDER BY kc.embedding <=> CAST(:vector AS vector)
        LIMIT :limit
        """
    )
    # O índice de vetor é IVFFlat — busca APROXIMADA. Com o `probes=1` que o
    # pgvector traz de fábrica, ela varre ~1% dos vetores e devolve vizinhos que
    # não são os mais próximos, EM SILÊNCIO — porque sempre devolve alguma coisa.
    # Medido em 03/08 na pergunta de retificação de CAR: o trecho mais similar do
    # corpus (IN MMA 02/2014, similaridade 0,7286) não estava entre os 8
    # devolvidos, e o 8º devolvido tinha 0,3996. Não era o corpus que havia
    # piorado — era o índice que não estava olhando.
    from app.core.config import settings  # noqa: PLC0415

    _probes = int(getattr(settings, "RAG_IVFFLAT_PROBES", 10) or 0)
    if _probes > 0:
        try:
            # Inteiro interpolado (não bind param): `SET LOCAL` não aceita
            # parâmetro. O valor vem de settings e é forçado a int acima.
            session.execute(text(f"SET LOCAL ivfflat.probes = {_probes:d}"))
        except Exception as exc:  # noqa: BLE001 — banco sem pgvector (testes)
            logger.debug("knowledge.search: ivfflat.probes não aplicável (%s)", exc)

    rows = session.execute(sql, params).all()

    # Corpus POVOADO e nenhum vetor no espaço da consulta = configuração trocada.
    # Devolver lista vazia aqui seria a falha silenciosa que a #114 existe para
    # impedir: o agente diria "não encontrei fundamentação" quando o problema é
    # estar perguntando no idioma errado. Recusa alto, com o que fazer.
    if not rows:
        modelos = [
            (m, n) for m, n in session.execute(
                text(
                    "SELECT embedding_model, count(*) FROM knowledge_catalog "
                    "GROUP BY 1 ORDER BY 2 DESC"
                )
            ).all()
        ]
        outros = [m for m, _ in modelos if m and m != modelo]
        if outros:
            total = sum(n for _, n in modelos)
            logger.error(
                "knowledge.search ESPACO VETORIAL INCOMPATIVEL: consulta em %r, "
                "corpus tem %d chunks em %s. Ajuste EMBEDDING_PROVIDER ou reindexe.",
                modelo, total, ", ".join(sorted(outros)),
            )
            raise EspacoVetorialIncompativel(
                f"A busca foi feita no espaço vetorial {modelo!r}, mas o corpus "
                f"está indexado em {', '.join(sorted(outros))}. Vetores de modelos "
                "diferentes não são comparáveis — a busca devolveria ruído com "
                "aparência de resultado. Ajuste EMBEDDING_PROVIDER para o modelo "
                "do índice, ou reindexe o corpus no modelo desejado."
            )

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
                vigencia_fim=row.vigencia_fim,
                sucessora_ref=row.sucessora_ref,
                fonte_origem=row.fonte_origem,
                fonte_oficial=bool(row.fonte_oficial),
            )
        )
    return out
