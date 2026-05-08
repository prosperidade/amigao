"""Testes do skill registry — Sprint A1 Tarefa A."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.skills._registry import (
    SkillContent,
    SkillMetadata,
    SkillParseError,
    discover_skills,
    invalidate_cache,
    load_skill,
    matches_context,
)


def _write_skill(root: Path, name: str, *, agent: str, body: str = "corpo", **fm) -> Path:
    """Cria um SKILL.md no caminho ``root/<name parts>/SKILL.md``."""
    parts = name.split("/")
    skill_dir = root.joinpath(*parts)
    skill_dir.mkdir(parents=True, exist_ok=True)
    front_lines = ["---", f"name: {name}", f"agent: {agent}"]
    for key, value in fm.items():
        if isinstance(value, dict):
            front_lines.append(f"{key}:")
            for k, v in value.items():
                front_lines.append(f"  {k}: {v}")
        else:
            front_lines.append(f"{key}: {value}")
    front_lines.append("---")
    front_lines.append("")
    front_lines.append(body)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("\n".join(front_lines), encoding="utf-8")
    return skill_file


@pytest.fixture(autouse=True)
def _clear_cache():
    invalidate_cache()
    yield
    invalidate_cache()


def test_discover_returns_empty_when_root_empty(tmp_path: Path) -> None:
    assert discover_skills(root=tmp_path) == {}


def test_discover_returns_empty_when_root_missing(tmp_path: Path) -> None:
    missing = tmp_path / "noexist"
    assert discover_skills(root=missing) == {}


def test_discover_lists_placeholder(tmp_path: Path) -> None:
    _write_skill(
        tmp_path, "redator/_template",
        agent="redator", version='"0.1.0"',
        description='"placeholder"',
        applies_to={"demand_types": '["template"]', "doc_types": "[]"},
    )
    result = discover_skills(root=tmp_path)
    assert "redator/_template" in result
    meta = result["redator/_template"]
    assert isinstance(meta, SkillMetadata)
    assert meta.agent == "redator"
    assert meta.applies_to == {"demand_types": ["template"], "doc_types": []}


def test_load_skill_parses_front_matter_and_body(tmp_path: Path) -> None:
    _write_skill(
        tmp_path, "redator/oficio",
        agent="redator", version='"1.0.0"',
        description='"Oficio gabarito"',
        body="# Estrutura\n\nPasso 1.",
    )
    content = load_skill("redator/oficio", root=tmp_path)
    assert isinstance(content, SkillContent)
    assert content.metadata.name == "redator/oficio"
    assert content.metadata.version == "1.0.0"
    assert "# Estrutura" in content.body
    assert "Passo 1." in content.body


def test_load_skill_missing_returns_none(tmp_path: Path) -> None:
    assert load_skill("naoexiste/nada", root=tmp_path) is None


def test_load_skill_invalid_front_matter_raises(tmp_path: Path) -> None:
    skill_dir = tmp_path / "redator" / "broken"
    skill_dir.mkdir(parents=True)
    # YAML válido mas sem front-matter delimitado
    (skill_dir / "SKILL.md").write_text("name: x\nagent: redator\n", encoding="utf-8")
    with pytest.raises(SkillParseError):
        load_skill("redator/broken", root=tmp_path)


def test_load_skill_yaml_error_raises(tmp_path: Path) -> None:
    skill_dir = tmp_path / "redator" / "yamlbad"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: [unclosed list\nagent: redator\n---\nbody\n",
        encoding="utf-8",
    )
    with pytest.raises(SkillParseError):
        load_skill("redator/yamlbad", root=tmp_path)


def test_load_skill_missing_required_field_raises(tmp_path: Path) -> None:
    skill_dir = tmp_path / "redator" / "noagent"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: redator/noagent\n---\nbody\n",
        encoding="utf-8",
    )
    with pytest.raises(SkillParseError):
        load_skill("redator/noagent", root=tmp_path)


def test_cache_invalidates_on_mtime_change(tmp_path: Path) -> None:
    skill_path = _write_skill(
        tmp_path, "redator/cached",
        agent="redator",
        body="corpo v1",
    )
    first = load_skill("redator/cached", root=tmp_path)
    assert first is not None
    assert "v1" in first.body

    # Reescreve com mtime mais novo
    time.sleep(0.05)
    skill_path.write_text(
        "---\nname: redator/cached\nagent: redator\n---\ncorpo v2\n",
        encoding="utf-8",
    )
    # Garante mtime estritamente maior
    new_mtime = skill_path.stat().st_mtime + 1
    import os
    os.utime(skill_path, (new_mtime, new_mtime))

    second = load_skill("redator/cached", root=tmp_path)
    assert second is not None
    assert "v2" in second.body
    assert second is not first  # cache substituído


def test_discover_skips_invalid_without_breaking(tmp_path: Path) -> None:
    # 1 skill válida
    _write_skill(tmp_path, "redator/ok", agent="redator")
    # 1 skill inválida (front-matter sem delimitador)
    bad_dir = tmp_path / "redator" / "bad"
    bad_dir.mkdir(parents=True)
    (bad_dir / "SKILL.md").write_text("nada\n", encoding="utf-8")
    found = discover_skills(root=tmp_path)
    assert "redator/ok" in found
    assert "redator/bad" not in found


def test_matches_context_filters_by_agent() -> None:
    meta = SkillMetadata(
        name="redator/x", agent="redator",
        version="1", description="", applies_to={},
    )
    assert matches_context(meta, agent="redator", ctx_metadata={}) is True
    assert matches_context(meta, agent="extrator", ctx_metadata={}) is False


def test_matches_context_filters_by_demand_type() -> None:
    meta = SkillMetadata(
        name="redator/oficio", agent="redator",
        version="1", description="",
        applies_to={"demand_types": ["car", "retificacao_car"]},
    )
    assert matches_context(meta, agent="redator", ctx_metadata={"demand_type": "car"}) is True
    assert matches_context(meta, agent="redator", ctx_metadata={"demand_type": "licenciamento"}) is False
    assert matches_context(meta, agent="redator", ctx_metadata={}) is False


def test_matches_context_empty_list_does_not_restrict() -> None:
    meta = SkillMetadata(
        name="redator/x", agent="redator",
        version="1", description="",
        applies_to={"demand_types": [], "doc_types": []},
    )
    assert matches_context(meta, agent="redator", ctx_metadata={}) is True
    assert matches_context(meta, agent="redator", ctx_metadata={"demand_type": "car"}) is True


def test_matches_context_multiple_keys_are_conjunctive() -> None:
    meta = SkillMetadata(
        name="extrator/car", agent="extrator",
        version="1", description="",
        applies_to={"demand_types": ["car"], "doc_types": ["car_sicar"]},
    )
    # falta doc_type
    assert matches_context(meta, agent="extrator", ctx_metadata={"demand_type": "car"}) is False
    # ambos batem
    assert matches_context(
        meta, agent="extrator",
        ctx_metadata={"demand_type": "car", "doc_type": "car_sicar"},
    ) is True
