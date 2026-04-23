"""
MemPalace integration layer — STUB NO-OP desde 2026-04-23.

Contexto: o pacote PyPI `mempalace` foi abandonado em 2026-04-23 por sinais fortes
de supply-chain attack (49k stars em 18 dias, wheel de 213 KB incompatível com o
escopo prometido, autor ofuscado, primeira release em v2/v3). Ver ADR em
docs/adr/adr_mempalace_REVOKED.md.

Este módulo mantém as MESMAS assinaturas públicas que o código anterior expunha
(`diary_write`, `diary_read`, `kg_add`, `kg_query`, `search`, `save_to_room`,
`recall_agent_context`, `log_agent_execution`, `is_available`) como no-ops que
retornam valores neutros. Isso preserva os call sites dos 10 agentes e do
BaseAgent sem quebrar o fluxo, até que a Sprint U (pgvector) substitua este
arquivo pelo novo backend de memória.

NA PRÓXIMA RODADA DEDICADA: deletar este arquivo inteiro, remover `palace_room`
dos 10 agentes, e limpar os hooks `_mempalace_log`, `_mempalace_log_failure`,
`recall_memory`, `remember`, `remember_fact` do BaseAgent. Ver ADR para
checklist completo.

Zero import de `mempalace`. Zero chamada de rede. Zero acesso a disco.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def is_available() -> bool:
    """Stub: memória está permanentemente indisponível até pgvector entrar em produção."""
    return False


# ---------------------------------------------------------------------------
# Diary (no-op)
# ---------------------------------------------------------------------------

def diary_write(agent_name: str, entry: str, topic: str = "execution") -> None:
    """Stub no-op. Ver ADR docs/adr/adr_mempalace_REVOKED.md."""
    return None


def diary_read(agent_name: str, last_n: int = 5) -> list[dict[str, Any]]:
    """Stub no-op — retorna lista vazia."""
    return []


# ---------------------------------------------------------------------------
# Knowledge Graph (no-op)
# ---------------------------------------------------------------------------

def kg_add(subject: str, predicate: str, obj: str, source: str | None = None) -> None:
    """Stub no-op."""
    return None


def kg_query(entity: str) -> list[dict[str, Any]]:
    """Stub no-op — retorna lista vazia."""
    return []


# ---------------------------------------------------------------------------
# Semantic search (no-op)
# ---------------------------------------------------------------------------

def search(query: str, room: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
    """Stub no-op — retorna lista vazia."""
    return []


# ---------------------------------------------------------------------------
# Drawer operations (no-op)
# ---------------------------------------------------------------------------

def save_to_room(room: str, content: str, source_file: str | None = None) -> None:
    """Stub no-op."""
    return None


# ---------------------------------------------------------------------------
# High-level helpers para BaseAgent (no-op preservando assinaturas)
# ---------------------------------------------------------------------------

def log_agent_execution(
    agent_name: str,
    palace_room: str,
    ctx_summary: str,
    result_summary: str,
    success: bool,
    confidence: str,
    duration_ms: int,
    process_id: int | None = None,
) -> None:
    """Stub no-op. Chamado por BaseAgent._mempalace_log e _mempalace_log_failure."""
    return None


def recall_agent_context(agent_name: str, query: str | None = None) -> dict[str, Any]:
    """Stub no-op. Retorna a mesma estrutura que a versão antiga retornaria vazia.

    Estrutura preservada para compatibilidade com DiagnosticoAgent e LegislacaoAgent,
    que acessam `.get("recent_diary")` e `.get("search_results")`.
    """
    return {"recent_diary": [], "search_results": []}
