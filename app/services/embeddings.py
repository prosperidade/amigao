"""Embeddings — wrapper sobre Gemini gemini-embedding-001.

Sprint U (2026-04-27). Single provider (Gemini) com o modelo gratuito.
Saida e fixada em 768 dimensoes via outputDimensionality, mantendo
compatibilidade com a coluna vector(768) e o indice IVFFlat.

text-embedding-004 foi descontinuado da v1beta; gemini-embedding-001 e o
substituto estavel. O endpoint sincrono so aceita um documento por chamada
(batchEmbedContents nao e suportado para esta familia — apenas o
asyncBatchEmbedContent, que e operation-based). Por isso embed_batch
itera em chamadas single com leve throttle pra respeitar o free tier
(~100 RPM).

Falhas levantam EmbeddingError — chamador decide se retry/skip.
"""

from __future__ import annotations

import logging
import time
from typing import Iterable

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768

GEMINI_EMBED_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{EMBEDDING_MODEL}:embedContent"
)

# Free tier permite ~100 RPM. 0.65s entre chamadas mantem margem segura.
_THROTTLE_SECONDS = 0.65


class EmbeddingError(RuntimeError):
    """Falha ao gerar embedding."""


def _ensure_key() -> str:
    key = (settings.GEMINI_API_KEY or "").strip()
    if not key:
        raise EmbeddingError(
            "GEMINI_API_KEY ausente — embeddings nao funcionam sem a chave do Gemini."
        )
    return key


def _embed_single(
    client: httpx.Client,
    text: str,
    *,
    key: str,
    task_type: str,
) -> list[float]:
    payload = {
        "content": {"parts": [{"text": text}]},
        "taskType": task_type,
        "outputDimensionality": EMBEDDING_DIM,
    }
    try:
        response = client.post(
            GEMINI_EMBED_URL,
            params={"key": key},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as exc:
        raise EmbeddingError(f"Falha HTTP ao embedar: {exc}") from exc

    values = data.get("embedding", {}).get("values")
    if not isinstance(values, list) or len(values) != EMBEDDING_DIM:
        raise EmbeddingError(
            f"Resposta invalida do Gemini: esperado embedding[{EMBEDDING_DIM}] "
            f"recebido {len(values) if isinstance(values, list) else type(values).__name__}"
        )
    return values


def embed_text(text: str, *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """Gera embedding para um unico texto. Use para queries curtas."""
    if not text or not text.strip():
        raise EmbeddingError("Texto vazio nao pode ser embedado.")

    key = _ensure_key()
    with httpx.Client(timeout=30.0) as client:
        return _embed_single(client, text, key=key, task_type=task_type)


def embed_batch(
    texts: Iterable[str],
    *,
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> list[list[float]]:
    """Gera embeddings em lote via chamadas sincronas single + throttling."""
    items = [t for t in texts if t and t.strip()]
    if not items:
        return []

    key = _ensure_key()
    out: list[list[float]] = []
    total = len(items)

    with httpx.Client(timeout=30.0) as client:
        for idx, text in enumerate(items):
            try:
                values = _embed_single(client, text, key=key, task_type=task_type)
            except EmbeddingError as exc:
                raise EmbeddingError(
                    f"Falha no item {idx + 1}/{total}: {exc}"
                ) from exc
            out.append(values)
            if (idx + 1) % 25 == 0 or (idx + 1) == total:
                logger.info("embeddings.batch progress %d/%d", idx + 1, total)
            if idx < total - 1:
                time.sleep(_THROTTLE_SECONDS)

    return out
