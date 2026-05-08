"""Integração das skills com BaseAgent — Sprint A1 Tarefa A.

Verifica que ``BaseAgent.call_llm`` injeta automaticamente o corpo das skills
aplicáveis no ``system`` antes de chamar o gateway. Testes unitários do seam
de injeção (não dependem de DB real — usam MagicMock no lugar de ``Session``,
o que mantém os testes rodáveis em qualquer ambiente, incluindo dentro de
containers sem Docker-in-Docker).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.agents.base import AgentContext, BaseAgent
from app.models.ai_job import AIJobType
from app.skills._registry import invalidate_cache


def _make_ai_response(content: str = '{"ok": true}'):
    from app.core.ai_gateway import AIResponse
    return AIResponse(
        content=content,
        model_used="mock-model",
        tokens_in=10,
        tokens_out=5,
        cost_usd=0.0,
        duration_ms=10,
        provider="mock",
    )


def _write_skill(
    root: Path,
    name: str,
    *,
    agent: str,
    body: str,
    applies_to: dict[str, list[str]] | None = None,
) -> Path:
    parts = name.split("/")
    skill_dir = root.joinpath(*parts)
    skill_dir.mkdir(parents=True, exist_ok=True)
    front = ["---", f"name: {name}", f"agent: {agent}", 'version: "0.1.0"', 'description: "test"']
    if applies_to:
        front.append("applies_to:")
        for k, v in applies_to.items():
            front.append(f"  {k}: {v}")
    front.append("---")
    front.append("")
    front.append(body)
    target = skill_dir / "SKILL.md"
    target.write_text("\n".join(front), encoding="utf-8")
    return target


@pytest.fixture(autouse=True)
def _isolate_registry(tmp_path, monkeypatch):
    """Aponta o registry para uma pasta temporária + limpa cache."""
    monkeypatch.setattr("app.skills._registry.SKILLS_ROOT", tmp_path)
    invalidate_cache()
    yield
    invalidate_cache()


class _FakeAgent(BaseAgent):
    name = "redator"
    description = "fake redator"
    job_type = AIJobType.gerar_documento

    def execute(self) -> dict[str, Any]:  # pragma: no cover
        return {}

    def _fallback_prompts(self) -> dict[str, str]:
        return {}


def _make_agent(**meta_kwargs) -> _FakeAgent:
    """Cria um _FakeAgent com session mockada — não toca em DB."""
    ctx = AgentContext(
        tenant_id=1,
        user_id=None,
        process_id=None,
        session=MagicMock(),
        metadata=meta_kwargs,
    )
    return _FakeAgent(ctx)


# ---------------------------------------------------------------------------
# _load_skills_for_context
# ---------------------------------------------------------------------------

def test_load_skills_returns_empty_when_no_skills_folder() -> None:
    agent = _make_agent(demand_type="car")
    assert agent._load_skills_for_context() == []


def test_load_skills_filters_by_agent_name(tmp_path: Path) -> None:
    _write_skill(tmp_path, "extrator/foo", agent="extrator", body="EXTRATOR")
    _write_skill(tmp_path, "redator/bar", agent="redator", body="REDATOR")

    agent = _make_agent()
    skills = agent._load_skills_for_context()
    names = [s.metadata.name for s in skills]
    assert "redator/bar" in names
    assert "extrator/foo" not in names


def test_load_skills_filters_by_demand_type(tmp_path: Path) -> None:
    _write_skill(
        tmp_path, "redator/oficio", agent="redator", body="OFICIO",
        applies_to={"demand_types": '["car"]'},
    )

    # demand_type não bate
    agent = _make_agent(demand_type="licenciamento")
    assert agent._load_skills_for_context() == []

    # demand_type bate
    agent = _make_agent(demand_type="car")
    skills = agent._load_skills_for_context()
    assert len(skills) == 1
    assert skills[0].body.strip() == "OFICIO"


def test_load_skills_empty_applies_to_does_not_restrict(tmp_path: Path) -> None:
    _write_skill(tmp_path, "redator/generic", agent="redator", body="GENERIC")
    agent = _make_agent()  # sem demand_type
    skills = agent._load_skills_for_context()
    assert len(skills) == 1


# ---------------------------------------------------------------------------
# _compose_system_with_skills
# ---------------------------------------------------------------------------

def test_compose_keeps_base_when_no_skills(tmp_path: Path) -> None:
    agent = _make_agent(demand_type="car")
    composed = agent._compose_system_with_skills("BASE_PROMPT")
    assert composed == "BASE_PROMPT"


def test_compose_appends_skill_body_with_markers(tmp_path: Path) -> None:
    _write_skill(tmp_path, "redator/oficio", agent="redator", body="CORPO_OFICIO")
    agent = _make_agent()

    composed = agent._compose_system_with_skills("BASE_PROMPT")
    assert "BASE_PROMPT" in composed
    assert "<!-- skills:start -->" in composed
    assert "Skill: redator/oficio v0.1.0" in composed
    assert "CORPO_OFICIO" in composed
    assert "<!-- skills:end -->" in composed
    # ordem: base ANTES do start, end DEPOIS do corpo
    assert composed.index("BASE_PROMPT") < composed.index("<!-- skills:start -->")
    assert composed.index("CORPO_OFICIO") < composed.index("<!-- skills:end -->")


def test_compose_concatenates_multiple_skills(tmp_path: Path) -> None:
    _write_skill(tmp_path, "redator/a", agent="redator", body="CORPO_A")
    _write_skill(tmp_path, "redator/b", agent="redator", body="CORPO_B")

    agent = _make_agent()
    composed = agent._compose_system_with_skills("BASE")
    assert "CORPO_A" in composed
    assert "CORPO_B" in composed
    # 1 par de markers para todas as skills
    assert composed.count("<!-- skills:start -->") == 1
    assert composed.count("<!-- skills:end -->") == 1


def test_compose_handles_empty_base_prompt(tmp_path: Path) -> None:
    _write_skill(tmp_path, "redator/x", agent="redator", body="ONLY_SKILL")
    agent = _make_agent()
    composed = agent._compose_system_with_skills("")
    assert "ONLY_SKILL" in composed
    assert "<!-- skills:start -->" in composed


# ---------------------------------------------------------------------------
# call_llm wrapping
# ---------------------------------------------------------------------------

def test_call_llm_injects_composed_system(tmp_path: Path) -> None:
    _write_skill(tmp_path, "redator/oficio", agent="redator", body="CORPO_INJ")
    agent = _make_agent(demand_type="car")

    with patch("app.agents.base.complete") as mock_complete:
        mock_complete.return_value = _make_ai_response()
        agent.call_llm("USER_PROMPT", system="BASE_SYSTEM")

    mock_complete.assert_called_once()
    composed = mock_complete.call_args.kwargs["system"]
    assert "BASE_SYSTEM" in composed
    assert "CORPO_INJ" in composed
    # user prompt continua intacto
    assert mock_complete.call_args.args[0] == "USER_PROMPT"


def test_call_llm_passthrough_when_no_skill_match(tmp_path: Path) -> None:
    _write_skill(
        tmp_path, "redator/oficio", agent="redator", body="NAO_USADO",
        applies_to={"demand_types": '["car"]'},
    )
    agent = _make_agent(demand_type="licenciamento")

    with patch("app.agents.base.complete") as mock_complete:
        mock_complete.return_value = _make_ai_response()
        agent.call_llm("USER", system="ORIGINAL")

    composed = mock_complete.call_args.kwargs["system"]
    assert composed == "ORIGINAL"


# ---------------------------------------------------------------------------
# Smoke test contra a pasta real do projeto
# ---------------------------------------------------------------------------

def test_real_redator_template_loads_with_template_demand_type(monkeypatch) -> None:
    """Aponta de volta para o SKILLS_ROOT real e verifica que o placeholder
    é injetado quando ``demand_type='template'``.
    """
    from app.skills import _registry as reg
    real_root = Path(reg.__file__).resolve().parent
    monkeypatch.setattr(reg, "SKILLS_ROOT", real_root)
    invalidate_cache()

    agent = _make_agent(demand_type="template")
    composed = agent._compose_system_with_skills("BASE")
    assert "redator/_template" in composed
    assert "Skill placeholder — redator" in composed


def test_real_extrator_template_requires_both_keys(monkeypatch) -> None:
    """A skill ``extrator/_template`` exige demand_type=template E doc_type=template."""
    from app.skills import _registry as reg
    real_root = Path(reg.__file__).resolve().parent
    monkeypatch.setattr(reg, "SKILLS_ROOT", real_root)
    invalidate_cache()

    # _FakeAgent.name="redator" — vamos criar um fake extrator
    class _FakeExtrator(BaseAgent):
        name = "extrator"
        description = ""
        job_type = AIJobType.extract_document

        def execute(self) -> dict[str, Any]:  # pragma: no cover
            return {}

        def _fallback_prompts(self) -> dict[str, str]:
            return {}

    ctx = AgentContext(
        tenant_id=1, user_id=None, process_id=None,
        session=MagicMock(),
        metadata={"demand_type": "template"},  # falta doc_type
    )
    agent = _FakeExtrator(ctx)
    composed = agent._compose_system_with_skills("BASE")
    assert "extrator/_template" not in composed

    ctx2 = AgentContext(
        tenant_id=1, user_id=None, process_id=None,
        session=MagicMock(),
        metadata={"demand_type": "template", "doc_type": "template"},
    )
    agent2 = _FakeExtrator(ctx2)
    composed2 = agent2._compose_system_with_skills("BASE")
    assert "extrator/_template" in composed2
