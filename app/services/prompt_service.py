"""
Prompt Service — Sprint IA-1

Servico centralizado para busca de PromptTemplates no banco.
Prioridade: tenant-specific > global (tenant_id=None).
Cache in-process com TTL curto para evitar query por inferencia.
Fallback hardcoded quando DB nao retornar prompt.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.prompt_template import PromptTemplate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache in-process simples (dict + TTL)
# ---------------------------------------------------------------------------

_cache: dict[str, tuple[PromptTemplate, float]] = {}
_CACHE_TTL_SECONDS = 60.0


def _cache_key(slug: str, tenant_id: Optional[int]) -> str:
    return f"{slug}::{tenant_id}"


def invalidate_cache(slug: Optional[str] = None) -> None:
    """Limpa cache. Se slug fornecido, limpa apenas entradas desse slug."""
    if slug is None:
        _cache.clear()
        return
    keys_to_drop = [k for k in _cache if k.startswith(f"{slug}::")]
    for k in keys_to_drop:
        _cache.pop(k, None)


# ---------------------------------------------------------------------------
# Lookup principal
# ---------------------------------------------------------------------------

def get_active_prompt(
    slug: str,
    db: Session,
    *,
    tenant_id: Optional[int] = None,
) -> Optional[PromptTemplate]:
    """
    Retorna a versao mais recente e ativa de um prompt pelo slug.

    Prioridade:
      1. Versao tenant-specific (tenant_id fornecido, match exato)
      2. Versao global (tenant_id IS NULL)

    Retorna None se nenhum prompt ativo for encontrado.
    """
    ck = _cache_key(slug, tenant_id)
    cached = _cache.get(ck)
    if cached is not None:
        obj, ts = cached
        if (time.monotonic() - ts) < _CACHE_TTL_SECONDS:
            return obj

    prompt = _query_active(slug, tenant_id, db)
    if prompt is None and tenant_id is not None:
        prompt = _query_active(slug, None, db)

    if prompt is not None:
        _cache[ck] = (prompt, time.monotonic())

    return prompt


def _query_active(slug: str, tenant_id: Optional[int], db: Session) -> Optional[PromptTemplate]:
    q = (
        db.query(PromptTemplate)
        .filter(
            PromptTemplate.slug == slug,
            PromptTemplate.is_active.is_(True),
        )
    )
    if tenant_id is not None:
        q = q.filter(PromptTemplate.tenant_id == tenant_id)
    else:
        q = q.filter(PromptTemplate.tenant_id.is_(None))

    return q.order_by(desc(PromptTemplate.version)).first()


# ---------------------------------------------------------------------------
# Helper: render template com variaveis
# ---------------------------------------------------------------------------

def render_prompt(template: PromptTemplate, variables: dict[str, str]) -> str:
    """Substitui placeholders {key} no content do template."""
    content = template.content
    for key, value in variables.items():
        content = content.replace(f"{{{key}}}", str(value))
    return content


# ---------------------------------------------------------------------------
# Criacao de nova versao (auto-increment)
# ---------------------------------------------------------------------------

def create_new_version(
    slug: str,
    db: Session,
    *,
    content: str,
    tenant_id: Optional[int] = None,
    input_schema: Optional[dict] = None,
    output_schema: Optional[dict] = None,
    model_hint: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> PromptTemplate:
    """
    Cria nova versao do prompt (version auto-incremented).
    Desativa a versao anterior automaticamente.
    """
    current = get_active_prompt(slug, db, tenant_id=tenant_id)

    next_version = 1
    if current is not None:
        next_version = current.version + 1
        current.is_active = False
        db.flush()

    new_prompt = PromptTemplate(
        slug=slug,
        category=current.category if current else _infer_category(slug),
        role=current.role if current else _infer_role(slug),
        version=next_version,
        content=content,
        tenant_id=tenant_id,
        input_schema=input_schema,
        output_schema=output_schema,
        model_hint=model_hint,
        temperature=temperature,
        max_tokens=max_tokens,
        is_active=True,
    )
    db.add(new_prompt)
    db.flush()

    invalidate_cache(slug)
    logger.info("prompt_service: created %s v%d tenant=%s", slug, next_version, tenant_id)
    return new_prompt


def _infer_category(slug: str):
    from app.models.prompt_template import PromptCategory  # noqa: PLC0415
    if slug.startswith("classify"):
        return PromptCategory.classify
    if slug.startswith("extract"):
        return PromptCategory.extract
    if slug.startswith("summarize") or slug.startswith("summary"):
        return PromptCategory.summarize
    return PromptCategory.proposal


def _infer_role(slug: str):
    from app.models.prompt_template import PromptRole  # noqa: PLC0415
    if "system" in slug:
        return PromptRole.system
    return PromptRole.user
