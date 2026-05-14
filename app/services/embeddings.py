"""Embeddings — wrapper multi-provedor (OpenAI/Gemini) com saída fixa em 768 dim.

Sprint U (2026-04-27): Gemini gemini-embedding-001 como único provedor (free tier).
Sprint W (2026-05-14): adicionado OpenAI text-embedding-3-small após o reindex
batch dos compêndios MS/MT estourar a cota diária do free tier Gemini.

Dimensão fixa em 768 mantém compatibilidade com a coluna `vector(768)` e o
índice IVFFlat do `knowledge_catalog`. Os dois provedores suportam saída em
768:
- OpenAI: parâmetro `dimensions=768` (text-embedding-3-small default é 1536).
- Gemini: parâmetro `outputDimensionality=768`.

Seleção de provedor:
- settings.EMBEDDING_PROVIDER explícito (`openai` | `gemini`) tem prioridade.
- Sem isso, usa OpenAI se OPENAI_API_KEY presente; senão cai pra Gemini.

⚠ ATENÇÃO: vetores de provedores diferentes vivem em espaços vetoriais
incompatíveis. Trocar de provedor exige re-embedar TODOS os chunks existentes
para manter consistência nas queries. Existe um indicador no `knowledge_catalog`
via `extra_meta` opcional, mas a regra prática é: ao trocar, rode
`reindex_sync.py` depois de limpar a tabela.

Falhas levantam EmbeddingError — chamador decide se retry/skip.
"""

from __future__ import annotations

import logging
import time
from typing import Iterable

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 768

# OpenAI
OPENAI_EMBED_URL = "https://api.openai.com/v1/embeddings"
OPENAI_MODEL = "text-embedding-3-small"
# Limite de itens por chamada batch. OpenAI aceita até 2048; mantemos 100 pra
# ter granularidade no retry e progresso visível.
_OPENAI_BATCH_SIZE = 100

# Gemini (fallback / legacy)
GEMINI_MODEL = "gemini-embedding-001"
GEMINI_EMBED_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:embedContent"
)
# Gemini: throttle entre chamadas single (não tem batch sync). 2s = 30 RPM.
_GEMINI_THROTTLE_SECONDS = 2.0

# Retry com backoff exponencial em 429 (rate limit) e 5xx (instabilidade).
# Base 30s → 30, 60, 120, 240, 480 = até ~15 min antes de desistir.
_MAX_RETRIES = 5
_RETRY_BASE_SECONDS = 30.0


class EmbeddingError(RuntimeError):
    """Falha ao gerar embedding."""


def _select_provider() -> str:
    """Decide qual provedor usar. Settings explícito vence; senão OpenAI > Gemini."""
    explicit = (getattr(settings, "EMBEDDING_PROVIDER", "") or "").strip().lower()
    if explicit in ("openai", "gemini"):
        return explicit
    if (settings.OPENAI_API_KEY or "").strip():
        return "openai"
    return "gemini"


def current_model() -> str:
    """Nome do modelo do provider atualmente selecionado. Persistido por chunk
    em `knowledge_catalog.embedding_model` para auditoria e diagnóstico de
    incompatibilidade entre lotes."""
    return OPENAI_MODEL if _select_provider() == "openai" else GEMINI_MODEL


# Alias mantido por compat — callers antigos importam EMBEDDING_MODEL diretamente.
# Avaliado em import time, então reflete o provider escolhido no startup.
EMBEDDING_MODEL = OPENAI_MODEL if (settings.OPENAI_API_KEY or "").strip() else GEMINI_MODEL


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

def _openai_key() -> str:
    key = (settings.OPENAI_API_KEY or "").strip()
    if not key:
        raise EmbeddingError(
            "OPENAI_API_KEY ausente — provider 'openai' selecionado mas chave não setada."
        )
    return key


def _openai_post(
    client: httpx.Client,
    *,
    inputs: list[str],
    key: str,
) -> list[list[float]]:
    """Chamada POST a /v1/embeddings com retry em 429/5xx."""
    payload = {
        "model": OPENAI_MODEL,
        "input": inputs,
        "dimensions": EMBEDDING_DIM,
        "encoding_format": "float",
    }
    headers = {"Authorization": f"Bearer {key}"}

    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = client.post(OPENAI_EMBED_URL, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise EmbeddingError(f"Falha HTTP ao embedar (openai): {exc}") from exc

        if response.status_code == 429 or response.status_code >= 500:
            if attempt < _MAX_RETRIES:
                delay = _RETRY_BASE_SECONDS * (2 ** attempt)
                logger.warning(
                    "openai %d (rate limit/instavel), retry %d/%d em %.1fs",
                    response.status_code, attempt + 1, _MAX_RETRIES, delay,
                )
                time.sleep(delay)
                continue
            raise EmbeddingError(
                f"Esgotou {_MAX_RETRIES} retries com status {response.status_code} "
                f"body={response.text[:300]}"
            )

        try:
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmbeddingError(
                f"Falha HTTP ao embedar (openai): {exc} body={response.text[:300]}"
            ) from exc

        data = response.json()
        items = data.get("data") or []
        if len(items) != len(inputs):
            raise EmbeddingError(
                f"Resposta openai retornou {len(items)} embeddings para {len(inputs)} inputs"
            )
        out: list[list[float]] = []
        for item in items:
            vec = item.get("embedding")
            if not isinstance(vec, list) or len(vec) != EMBEDDING_DIM:
                raise EmbeddingError(
                    f"openai: embedding com dim inesperada "
                    f"({len(vec) if isinstance(vec, list) else type(vec).__name__})"
                )
            out.append(vec)
        return out

    raise EmbeddingError("openai: loop de retry encerrou sem resposta")


def _openai_embed_batch(texts: list[str]) -> list[list[float]]:
    key = _openai_key()
    out: list[list[float]] = []
    total = len(texts)

    with httpx.Client(timeout=60.0) as client:
        for start in range(0, total, _OPENAI_BATCH_SIZE):
            chunk = texts[start:start + _OPENAI_BATCH_SIZE]
            batch_out = _openai_post(client, inputs=chunk, key=key)
            out.extend(batch_out)
            done = start + len(chunk)
            if done % 200 == 0 or done == total:
                logger.info("embeddings.batch(openai) progress %d/%d", done, total)
    return out


def _openai_embed_single(text: str) -> list[float]:
    key = _openai_key()
    with httpx.Client(timeout=60.0) as client:
        out = _openai_post(client, inputs=[text], key=key)
    return out[0]


# ---------------------------------------------------------------------------
# Gemini (legacy / fallback)
# ---------------------------------------------------------------------------

def _gemini_key() -> str:
    key = (settings.GEMINI_API_KEY or "").strip()
    if not key:
        raise EmbeddingError(
            "GEMINI_API_KEY ausente — provider 'gemini' selecionado mas chave não setada."
        )
    return key


def _gemini_embed_single(
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

    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = client.post(GEMINI_EMBED_URL, params={"key": key}, json=payload)
        except httpx.HTTPError as exc:
            raise EmbeddingError(f"Falha HTTP ao embedar (gemini): {exc}") from exc

        if response.status_code == 429 or response.status_code >= 500:
            if attempt < _MAX_RETRIES:
                delay = _RETRY_BASE_SECONDS * (2 ** attempt)
                logger.warning(
                    "gemini %d (rate limit/instavel), retry %d/%d em %.1fs",
                    response.status_code, attempt + 1, _MAX_RETRIES, delay,
                )
                time.sleep(delay)
                continue
            raise EmbeddingError(
                f"Esgotou {_MAX_RETRIES} retries com status {response.status_code}"
            )

        try:
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmbeddingError(f"Falha HTTP ao embedar (gemini): {exc}") from exc

        data = response.json()
        values = data.get("embedding", {}).get("values")
        if not isinstance(values, list) or len(values) != EMBEDDING_DIM:
            raise EmbeddingError(
                f"Resposta invalida do Gemini: esperado embedding[{EMBEDDING_DIM}] "
                f"recebido {len(values) if isinstance(values, list) else type(values).__name__}"
            )
        return values

    raise EmbeddingError("gemini: loop de retry encerrou sem resposta")


def _gemini_embed_batch(texts: list[str], task_type: str) -> list[list[float]]:
    key = _gemini_key()
    out: list[list[float]] = []
    total = len(texts)
    with httpx.Client(timeout=60.0) as client:
        for idx, text in enumerate(texts):
            try:
                values = _gemini_embed_single(client, text, key=key, task_type=task_type)
            except EmbeddingError as exc:
                raise EmbeddingError(f"Falha no item {idx + 1}/{total}: {exc}") from exc
            out.append(values)
            if (idx + 1) % 25 == 0 or (idx + 1) == total:
                logger.info("embeddings.batch(gemini) progress %d/%d", idx + 1, total)
            if idx < total - 1:
                time.sleep(_GEMINI_THROTTLE_SECONDS)
    return out


# ---------------------------------------------------------------------------
# API pública (não muda contrato — callers continuam iguais)
# ---------------------------------------------------------------------------

def embed_text(text: str, *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """Gera embedding para um único texto. `task_type` é ignorado pelo OpenAI."""
    if not text or not text.strip():
        raise EmbeddingError("Texto vazio nao pode ser embedado.")

    provider = _select_provider()
    if provider == "openai":
        return _openai_embed_single(text)
    key = _gemini_key()
    with httpx.Client(timeout=60.0) as client:
        return _gemini_embed_single(client, text, key=key, task_type=task_type)


def embed_batch(
    texts: Iterable[str],
    *,
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> list[list[float]]:
    """Gera embeddings em lote. OpenAI usa batch nativo (até 100/req); Gemini itera single."""
    items = [t for t in texts if t and t.strip()]
    if not items:
        return []

    provider = _select_provider()
    logger.info("embeddings.batch: %d itens via %s", len(items), provider)
    if provider == "openai":
        return _openai_embed_batch(items)
    return _gemini_embed_batch(items, task_type)
