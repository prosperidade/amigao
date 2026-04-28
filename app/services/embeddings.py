"""Embeddings — wrapper sobre Gemini text-embedding-004.

Sprint U (2026-04-27). Single provider (Gemini) com o modelo gratuito até
o limite de 1500 RPM. O dim e 768. Falhas levantam EmbeddingError —
chamador decide se retry/skip.

A escolha do Gemini casa com a Sprint O (provider default do agente
legislacao) e a chave ja esta no .env. Nao usamos litellm aqui porque
litellm trata o endpoint de embeddings de cada provider como um caso
separado e o suporte a Gemini embeddings ainda e instavel.
"""

from __future__ import annotations

import logging
from typing import Iterable

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

GEMINI_EMBED_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "text-embedding-004:embedContent"
)
GEMINI_BATCH_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "text-embedding-004:batchEmbedContents"
)

EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_DIM = 768

# Gemini batch endpoint aceita ate 100 docs por requisicao.
_BATCH_LIMIT = 100


class EmbeddingError(RuntimeError):
    """Falha ao gerar embedding."""


def _ensure_key() -> str:
    key = (settings.GEMINI_API_KEY or "").strip()
    if not key:
        raise EmbeddingError(
            "GEMINI_API_KEY ausente — embeddings nao funcionam sem a chave do Gemini."
        )
    return key


def embed_text(text: str, *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """Gera embedding para um unico texto. Use para queries curtas."""
    if not text or not text.strip():
        raise EmbeddingError("Texto vazio nao pode ser embedado.")

    key = _ensure_key()
    payload = {
        "model": f"models/{EMBEDDING_MODEL}",
        "content": {"parts": [{"text": text}]},
        "taskType": task_type,
    }
    try:
        with httpx.Client(timeout=30.0) as client:
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


def embed_batch(
    texts: Iterable[str],
    *,
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> list[list[float]]:
    """Gera embeddings em lote. Quebra automaticamente em sub-batches de 100."""
    items = [t for t in texts if t and t.strip()]
    if not items:
        return []

    key = _ensure_key()
    out: list[list[float]] = []

    for start in range(0, len(items), _BATCH_LIMIT):
        chunk = items[start : start + _BATCH_LIMIT]
        payload = {
            "requests": [
                {
                    "model": f"models/{EMBEDDING_MODEL}",
                    "content": {"parts": [{"text": text}]},
                    "taskType": task_type,
                }
                for text in chunk
            ]
        }

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    GEMINI_BATCH_URL,
                    params={"key": key},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise EmbeddingError(
                f"Falha HTTP no batch (offset={start}, size={len(chunk)}): {exc}"
            ) from exc

        embeddings = data.get("embeddings") or []
        if len(embeddings) != len(chunk):
            raise EmbeddingError(
                f"Gemini retornou {len(embeddings)} embeddings, esperado {len(chunk)}"
            )
        for emb in embeddings:
            values = emb.get("values")
            if not isinstance(values, list) or len(values) != EMBEDDING_DIM:
                raise EmbeddingError("Embedding invalido no batch.")
            out.append(values)

        logger.info(
            "embeddings.batch ok offset=%d size=%d total=%d",
            start, len(chunk), len(items),
        )

    return out
