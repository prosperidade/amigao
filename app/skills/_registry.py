"""Skill registry — descobre e carrega skills procedurais do filesystem.

Sprint A1 (Tarefa A) — Forma B: skills moram em ``app/skills/<agent>/<skill>/SKILL.md``.
Cada SKILL.md tem front-matter YAML + corpo markdown. O corpo é injetado no
system prompt do agente quando o contexto da execução der match.

Convenção:
- ``app/skills/<agent>/<skill_name>/SKILL.md``
- ``name`` no front-matter == ``<agent>/<skill_name>``
- Pastas começando com ``_`` (ex.: ``_template``) são placeholders técnicos —
  ainda assim descobertas; o filtro de domínio fica nas próprias regras
  ``applies_to``.

Cache:
- Em memória, invalidado por mtime de cada arquivo.
- Multi-worker (Gunicorn/uvicorn): cada processo tem o próprio cache. OK pra
  esta sprint — ver ``# TODO(perf)`` abaixo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any

import yaml

logger = logging.getLogger(__name__)

SKILLS_ROOT = Path(__file__).resolve().parent
SKILL_FILENAME = "SKILL.md"
FRONT_MATTER_DELIMITER = "---"


# ---------------------------------------------------------------------------
# Tipos públicos
# ---------------------------------------------------------------------------

class SkillParseError(ValueError):
    """Erro tipado ao parsear front-matter de um SKILL.md."""


@dataclass(frozen=True)
class SkillMetadata:
    """Metadados de uma skill, lidos do front-matter."""

    name: str                                   # ex.: "redator/_template"
    agent: str                                  # ex.: "redator"
    version: str                                # ex.: "0.1.0"
    description: str
    applies_to: dict[str, list[str]] = field(default_factory=dict)
    path: Path | None = None                    # caminho absoluto ao SKILL.md


@dataclass(frozen=True)
class SkillContent:
    """Conteúdo completo de uma skill — metadados + corpo markdown."""

    metadata: SkillMetadata
    body: str


# ---------------------------------------------------------------------------
# Cache (mtime-invalidated)
# ---------------------------------------------------------------------------

# TODO(perf): em produção multi-worker, cada processo paga o primeiro hit. Aceitável
# enquanto skills ficam em filesystem; quando migrar pra MinIO/DB (Sprint > A1),
# trocar por cache compartilhado (Redis) com TTL.

_cache_lock = RLock()
_content_cache: dict[Path, tuple[float, SkillContent]] = {}


def invalidate_cache() -> None:
    """Limpa o cache de skills. Útil em testes e em hot-reload manual."""
    with _cache_lock:
        _content_cache.clear()


# ---------------------------------------------------------------------------
# Discovery + load
# ---------------------------------------------------------------------------

def discover_skills(root: Path | None = None) -> dict[str, SkillMetadata]:
    """Varre ``root`` (default ``app/skills/``) e retorna {name: SkillMetadata}.

    Skills com front-matter inválido são ignoradas (log estruturado em WARNING)
    para não derrubar o boot.
    """
    base = root or SKILLS_ROOT
    found: dict[str, SkillMetadata] = {}

    if not base.exists():
        return found

    for skill_path in sorted(base.rglob(SKILL_FILENAME)):
        try:
            content = _read_skill(skill_path)
        except SkillParseError as exc:
            logger.warning(
                "skills.discover: SKILL.md inválido em %s: %s",
                skill_path, exc,
            )
            continue
        meta = content.metadata
        if meta.name in found:
            logger.warning(
                "skills.discover: nome duplicado '%s' (mantendo %s, ignorando %s)",
                meta.name, found[meta.name].path, meta.path,
            )
            continue
        found[meta.name] = meta

    return found


def load_skill(name: str, root: Path | None = None) -> SkillContent | None:
    """Carrega uma skill pelo ``name`` (ex.: ``redator/_template``).

    Retorna ``None`` quando não existe. Levanta ``SkillParseError`` se o arquivo
    existe mas o front-matter está malformado.
    """
    base = root or SKILLS_ROOT
    parts = name.split("/")
    candidate = base.joinpath(*parts) / SKILL_FILENAME
    if not candidate.exists():
        return None

    return _read_skill(candidate)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _read_skill(path: Path) -> SkillContent:
    """Lê SKILL.md com cache mtime-invalidated."""
    try:
        mtime = path.stat().st_mtime
    except OSError as exc:
        raise SkillParseError(f"não consigo stat({path}): {exc}") from exc

    with _cache_lock:
        cached = _content_cache.get(path)
        if cached is not None and cached[0] == mtime:
            return cached[1]

    raw = path.read_text(encoding="utf-8")
    front, body = _split_front_matter(raw, path=path)
    parsed = _parse_front_matter(front, path=path)
    metadata = _build_metadata(parsed, path=path)
    content = SkillContent(metadata=metadata, body=body.strip())

    with _cache_lock:
        _content_cache[path] = (mtime, content)
    return content


def _split_front_matter(raw: str, *, path: Path) -> tuple[str, str]:
    text = raw.lstrip("﻿")  # strip BOM se existir
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONT_MATTER_DELIMITER:
        raise SkillParseError(f"{path}: front-matter ausente (esperado '---' na linha 1)")

    end_idx: int | None = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == FRONT_MATTER_DELIMITER:
            end_idx = idx
            break

    if end_idx is None:
        raise SkillParseError(f"{path}: delimitador '---' de fechamento do front-matter não encontrado")

    front = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1:])
    return front, body


def _parse_front_matter(front: str, *, path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(front) or {}
    except yaml.YAMLError as exc:
        raise SkillParseError(f"{path}: YAML inválido no front-matter: {exc}") from exc
    if not isinstance(data, dict):
        raise SkillParseError(f"{path}: front-matter deve ser um mapping YAML, recebeu {type(data).__name__}")
    return data


def _build_metadata(parsed: dict[str, Any], *, path: Path) -> SkillMetadata:
    name = parsed.get("name")
    agent = parsed.get("agent")
    if not isinstance(name, str) or not name:
        raise SkillParseError(f"{path}: campo 'name' obrigatório no front-matter")
    if not isinstance(agent, str) or not agent:
        raise SkillParseError(f"{path}: campo 'agent' obrigatório no front-matter")

    applies_raw = parsed.get("applies_to", {}) or {}
    if not isinstance(applies_raw, dict):
        raise SkillParseError(f"{path}: 'applies_to' deve ser um mapping, recebeu {type(applies_raw).__name__}")
    applies_to: dict[str, list[str]] = {}
    for key, value in applies_raw.items():
        if value is None:
            applies_to[str(key)] = []
            continue
        if not isinstance(value, list):
            raise SkillParseError(f"{path}: 'applies_to.{key}' deve ser uma lista, recebeu {type(value).__name__}")
        applies_to[str(key)] = [str(v) for v in value]

    version = str(parsed.get("version", "0.0.0"))
    description = str(parsed.get("description", ""))

    return SkillMetadata(
        name=name,
        agent=agent,
        version=version,
        description=description,
        applies_to=applies_to,
        path=path,
    )


# ---------------------------------------------------------------------------
# Matching helpers (usado pelo BaseAgent)
# ---------------------------------------------------------------------------

def matches_context(metadata: SkillMetadata, *, agent: str, ctx_metadata: dict[str, Any]) -> bool:
    """Verifica se uma skill é aplicável ao contexto atual.

    Regras (todas conjuntivas):
    - skill.agent == agent
    - para cada chave em ``applies_to`` cuja lista é não-vazia:
      o valor singular correspondente em ``ctx_metadata`` (ex.: ``demand_type``,
      ``doc_type``) deve estar na lista.

    Lista vazia em ``applies_to.<chave>`` significa "não restringe".
    """
    if metadata.agent != agent:
        return False

    for key, allowed in metadata.applies_to.items():
        if not allowed:
            continue
        # Convenção: chaves plurais ("demand_types") casam com o singular ("demand_type")
        singular = key[:-1] if key.endswith("s") else key
        ctx_value = ctx_metadata.get(singular)
        if ctx_value is None:
            return False
        if str(ctx_value) not in allowed:
            return False
    return True
