"""Skills procedurais por agente. Sprint A1 — Forma B (filesystem on-demand).

Ver app/skills/README.md para a convenção.
"""

from app.skills._registry import (
    SkillContent,
    SkillMetadata,
    SkillParseError,
    discover_skills,
    invalidate_cache,
    load_skill,
)

__all__ = [
    "SkillContent",
    "SkillMetadata",
    "SkillParseError",
    "discover_skills",
    "invalidate_cache",
    "load_skill",
]
