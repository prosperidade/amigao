"""Integração do citation_evaluator no RedatorAgent — Sprint A1 Tarefa B."""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from app.agents.base import AgentContext
from app.agents.redator import RedatorAgent


def _make_ai_response(content: str):
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


def _ctx(*, chain_data: dict | None = None, metadata: dict | None = None) -> AgentContext:
    return AgentContext(
        tenant_id=1,
        user_id=None,
        process_id=None,
        session=MagicMock(),
        metadata=metadata or {"document_template": "oficio"},
        chain_data=chain_data or {},
    )


def _enter_default_patches(stack: ExitStack):
    """Bypass dos checks de cost — não relevantes pra estes testes."""
    stack.enter_context(patch("app.agents.base.check_tenant_cost_limit"))
    stack.enter_context(patch("app.agents.base.check_tenant_monthly_budget"))


@pytest.fixture(autouse=True)
def _isolate_skills(tmp_path, monkeypatch):
    """Aponta SKILLS_ROOT pra pasta vazia — sem interferência de skills reais."""
    monkeypatch.setattr("app.skills._registry.SKILLS_ROOT", tmp_path)
    from app.skills._registry import invalidate_cache
    invalidate_cache()


def test_no_legal_context_skips_validation():
    """Sem chain_data['legislacao'] não tem o que cruzar — nenhum citation_issues."""
    agent = RedatorAgent(_ctx())
    output = "Conforme a Lei 12.651/2012 e a Lei 9.605/1998..."

    with ExitStack() as stack:
        _enter_default_patches(stack)
        mock_complete = stack.enter_context(patch("app.agents.base.complete"))
        mock_complete.return_value = _make_ai_response(output)
        result = agent.run()

    assert result.success is True
    assert "citation_issues" not in result.data
    assert "citation_total" not in result.data


def test_all_citations_valid_marks_review_with_no_issues():
    legal_data = {"legislacao_aplicavel": ["Lei 12.651/2012", "Lei 9.605/1998"]}
    agent = RedatorAgent(_ctx(chain_data={"legislacao": legal_data}))
    output = "Conforme a Lei 12.651/2012 e a Lei nº 9.605/1998..."

    with ExitStack() as stack:
        _enter_default_patches(stack)
        mock_complete = stack.enter_context(patch("app.agents.base.complete"))
        mock_complete.return_value = _make_ai_response(output)
        result = agent.run()

    assert result.success is True
    assert result.requires_review is True
    assert result.data["citation_valid"] is True
    assert result.data["citation_total"] == 2
    assert result.data["citation_issues"] == []
    assert result.data["citation_coverage_ratio"] == 1.0


def test_invalid_citation_populates_issues_and_keeps_review_true():
    legal_data = {"legislacao_aplicavel": ["Lei 12.651/2012"]}
    agent = RedatorAgent(_ctx(chain_data={"legislacao": legal_data}))
    # cita uma lei FORA do contexto → vai pra invalid
    output = "Conforme a Lei 12.651/2012 e a inexistente Lei 99.999/2099..."

    with ExitStack() as stack:
        _enter_default_patches(stack)
        mock_complete = stack.enter_context(patch("app.agents.base.complete"))
        mock_complete.return_value = _make_ai_response(output)
        result = agent.run()

    assert result.requires_review is True
    assert result.data["citation_valid"] is False
    assert result.data["citation_total"] == 2
    assert len(result.data["citation_issues"]) == 1
    assert result.data["citation_issues"][0]["numero"] == "99.999"
    assert result.data["citation_coverage_ratio"] == pytest.approx(0.5)


def test_no_citations_in_output_returns_no_issues():
    legal_data = {"legislacao_aplicavel": ["Lei 12.651/2012"]}
    agent = RedatorAgent(_ctx(chain_data={"legislacao": legal_data}))
    output = "Documento sem qualquer citação legal específica."

    with ExitStack() as stack:
        _enter_default_patches(stack)
        mock_complete = stack.enter_context(patch("app.agents.base.complete"))
        mock_complete.return_value = _make_ai_response(output)
        result = agent.run()

    # legal_data tem contexto, mas output não cita nada → skip silencioso
    assert "citation_issues" not in result.data


def test_normas_estaduais_count_as_legitimate_context():
    legal_data = {
        "legislacao_aplicavel": ["Lei 12.651/2012"],
        "normas_estaduais": ["Lei Complementar 140/2011"],
    }
    agent = RedatorAgent(_ctx(chain_data={"legislacao": legal_data}))
    output = "Lei 12.651/2012 e Lei Complementar 140/2011 aplicam-se..."

    with ExitStack() as stack:
        _enter_default_patches(stack)
        mock_complete = stack.enter_context(patch("app.agents.base.complete"))
        mock_complete.return_value = _make_ai_response(output)
        result = agent.run()

    assert result.data["citation_valid"] is True
    assert result.data["citation_total"] == 2
