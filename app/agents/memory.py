"""
MemPalace integration for the Agent framework.

Provides non-blocking memory operations:
- diary_write: logs agent executions (input summary + result)
- diary_read: recalls recent agent activity
- kg_add: stores structured facts in the knowledge graph
- search: semantic search across the palace

All operations are fire-and-forget: MemPalace failures never break agent execution.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Palace path (local, never cloud)
PALACE_PATH = os.path.expanduser("~/.mempalace/palace")
WING = "amigao_do_meio_ambiente"

# Lazy-loaded module reference
_mcp = None


def _get_mcp():
    """Lazy import of mempalace.mcp_server to avoid import-time failures."""
    global _mcp
    if _mcp is None:
        try:
            from mempalace import mcp_server
            _mcp = mcp_server
        except ImportError:
            logger.debug("mempalace not installed — memory features disabled")
    return _mcp


def is_available() -> bool:
    """Check if MemPalace is installed and palace exists."""
    return _get_mcp() is not None and os.path.isdir(PALACE_PATH)


# ---------------------------------------------------------------------------
# Diary operations (per-agent execution log)
# ---------------------------------------------------------------------------

def diary_write(agent_name: str, entry: str, topic: str = "execution") -> None:
    """Write a diary entry for an agent. Non-blocking, never raises."""
    mcp = _get_mcp()
    if mcp is None:
        return
    try:
        mcp.tool_diary_write(agent_name=agent_name, entry=entry, topic=topic)
    except Exception as exc:
        logger.debug("mempalace diary_write failed for %s: %s", agent_name, exc)


def diary_read(agent_name: str, last_n: int = 5) -> list[dict[str, Any]]:
    """Read recent diary entries for an agent. Returns empty list on failure."""
    mcp = _get_mcp()
    if mcp is None:
        return []
    try:
        result = mcp.tool_diary_read(agent_name=agent_name, last_n=last_n)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("entries", [])
        return []
    except Exception as exc:
        logger.debug("mempalace diary_read failed for %s: %s", agent_name, exc)
        return []


# ---------------------------------------------------------------------------
# Knowledge Graph operations
# ---------------------------------------------------------------------------

def kg_add(subject: str, predicate: str, obj: str, source: str | None = None) -> None:
    """Add a fact to the knowledge graph. Non-blocking, never raises."""
    mcp = _get_mcp()
    if mcp is None:
        return
    try:
        mcp.tool_kg_add(
            subject=subject,
            predicate=predicate,
            object=obj,
            source_closet=source,
        )
    except Exception as exc:
        logger.debug("mempalace kg_add failed: %s", exc)


def kg_query(entity: str) -> list[dict[str, Any]]:
    """Query the knowledge graph for an entity. Returns empty list on failure."""
    mcp = _get_mcp()
    if mcp is None:
        return []
    try:
        result = mcp.tool_kg_query(entity=entity)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("triples", [])
        return []
    except Exception as exc:
        logger.debug("mempalace kg_query failed for %s: %s", entity, exc)
        return []


# ---------------------------------------------------------------------------
# Semantic search
# ---------------------------------------------------------------------------

def search(query: str, room: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
    """Semantic search across the palace. Returns empty list on failure."""
    mcp = _get_mcp()
    if mcp is None:
        return []
    try:
        result = mcp.search_memories(
            query=query,
            palace_path=PALACE_PATH,
            wing=WING,
            room=room,
            n_results=limit,
        )
        if isinstance(result, dict):
            return result.get("results", [])
        return []
    except Exception as exc:
        logger.debug("mempalace search failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Drawer operations (store content in a room)
# ---------------------------------------------------------------------------

def save_to_room(room: str, content: str, source_file: str | None = None) -> None:
    """Save content to a specific room. Non-blocking, never raises."""
    mcp = _get_mcp()
    if mcp is None:
        return
    try:
        mcp.tool_add_drawer(
            wing=WING,
            room=room,
            content=content,
            source_file=source_file,
            added_by="agent_framework",
        )
    except Exception as exc:
        logger.debug("mempalace save_to_room failed for %s: %s", room, exc)


# ---------------------------------------------------------------------------
# High-level helpers for BaseAgent integration
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
    """
    Log a complete agent execution to MemPalace.

    Called automatically by BaseAgent.run() after execution.
    Writes diary entry + knowledge graph facts.
    """
    # Diary entry with execution details
    entry = (
        f"[{'OK' if success else 'FAIL'}] conf={confidence} ms={duration_ms}"
        f"{f' process={process_id}' if process_id else ''}\n"
        f"IN: {ctx_summary[:300]}\n"
        f"OUT: {result_summary[:500]}"
    )
    diary_write(agent_name, entry, topic=palace_room)

    # Knowledge graph: agent executed on process
    if process_id and success:
        kg_add(
            subject=f"process_{process_id}",
            predicate=f"analyzed_by_{agent_name}",
            obj=f"confidence={confidence}",
            source=f"agent_{agent_name}",
        )


def recall_agent_context(agent_name: str, query: str | None = None) -> dict[str, Any]:
    """
    Recall context for an agent from MemPalace.

    Returns dict with recent diary entries and optional search results.
    Used by agents that want to enrich their prompts with historical context.
    """
    context: dict[str, Any] = {
        "recent_diary": diary_read(agent_name, last_n=3),
    }

    if query:
        context["search_results"] = search(query, limit=3)

    return context
