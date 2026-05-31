"""Dívida #33 — auditoria do USO server-side da api_key do consultor.

Verifica que ``BaseAgent.call_llm`` registra um ``AuditLog`` (``action="ai_key_used"``)
quando a chave própria do consultor (white label, ADR-014) é usada, com a chave
SEMPRE mascarada — e que o caminho global (sem chave do usuário) não audita.

Testes unitários do seam (não dependem de DB real — ``Session`` é MagicMock e o
helper de auditoria é patchado, o que mantém os testes rodáveis em qualquer
ambiente, inclusive sem Docker).
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from app.agents.base import AgentContext, BaseAgent
from app.models.ai_job import AIJobType

_PLAINTEXT_KEY = "sk-ant-SUPER-SECRET-7890"
_USER_PREFS = {"provider": "anthropic", "model": "claude-x", "api_key": _PLAINTEXT_KEY}


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


class _FakeAgent(BaseAgent):
    name = "financeiro"  # agente sem skill formal → system prompt fica intacto
    description = "fake financeiro"
    job_type = AIJobType.analise_financeira

    def execute(self) -> dict[str, Any]:  # pragma: no cover
        return {}

    def _fallback_prompts(self) -> dict[str, str]:
        return {}


def _make_agent(user_id: int | None = 7) -> _FakeAgent:
    ctx = AgentContext(
        tenant_id=1,
        user_id=user_id,
        process_id=42,
        session=MagicMock(),
    )
    return _FakeAgent(ctx)


# ---------------------------------------------------------------------------
# Audita quando a chave do consultor é usada
# ---------------------------------------------------------------------------

def test_audits_ai_key_use_when_user_prefs_present() -> None:
    agent = _make_agent()

    with patch("app.agents.base.complete") as mock_complete, patch(
        "app.services.notifications.register_notification_audit"
    ) as mock_audit:
        mock_complete.return_value = _make_ai_response()
        agent.call_llm("PROMPT", system="SYS", user_preferences=dict(_USER_PREFS))

    mock_audit.assert_called_once()
    kwargs = mock_audit.call_args.kwargs
    assert kwargs["action"] == "ai_key_used"
    assert kwargs["entity_type"] == "user"
    assert kwargs["entity_id"] == 7
    assert kwargs["tenant_id"] == 1
    details = kwargs["details"]
    assert details["provider"] == "anthropic"
    assert details["model"] == "claude-x"
    # chave mascarada: termina nos últimos 4, e o plaintext NUNCA aparece
    assert details["api_key_masked"].endswith("7890")
    assert _PLAINTEXT_KEY not in json.dumps(details, ensure_ascii=False)


def test_masked_key_never_leaks_plaintext_anywhere() -> None:
    agent = _make_agent()
    with patch("app.agents.base.complete") as mock_complete, patch(
        "app.services.notifications.register_notification_audit"
    ) as mock_audit:
        mock_complete.return_value = _make_ai_response()
        agent.call_llm("P", system="S", user_preferences=dict(_USER_PREFS))

    # nenhum argumento do audit pode conter o plaintext
    blob = json.dumps(
        {"args": str(mock_audit.call_args.args), "kwargs": str(mock_audit.call_args.kwargs)},
        ensure_ascii=False,
    )
    assert _PLAINTEXT_KEY not in blob


# ---------------------------------------------------------------------------
# Não audita no caminho global (sem chave do consultor)
# ---------------------------------------------------------------------------

def test_no_audit_when_no_user_prefs() -> None:
    agent = _make_agent(user_id=None)  # _resolve_user_ai_preferences → None

    with patch("app.agents.base.complete") as mock_complete, patch(
        "app.services.notifications.register_notification_audit"
    ) as mock_audit:
        mock_complete.return_value = _make_ai_response()
        agent.call_llm("PROMPT", system="SYS")

    mock_audit.assert_not_called()


# ---------------------------------------------------------------------------
# Dedupe: no máximo uma auditoria por execução de agente
# ---------------------------------------------------------------------------

def test_audit_only_once_per_agent_run() -> None:
    agent = _make_agent()

    with patch("app.agents.base.complete") as mock_complete, patch(
        "app.services.notifications.register_notification_audit"
    ) as mock_audit:
        mock_complete.return_value = _make_ai_response()
        agent.call_llm("P1", system="S", user_preferences=dict(_USER_PREFS))
        agent.call_llm("P2", system="S", user_preferences=dict(_USER_PREFS))

    mock_audit.assert_called_once()


# ---------------------------------------------------------------------------
# Best-effort: falha na auditoria não derruba a chamada do agente
# ---------------------------------------------------------------------------

def test_audit_failure_does_not_break_call_llm() -> None:
    agent = _make_agent()

    with patch("app.agents.base.complete") as mock_complete, patch(
        "app.services.notifications.register_notification_audit",
        side_effect=RuntimeError("db down"),
    ):
        mock_complete.return_value = _make_ai_response()
        # não deve levantar
        resp = agent.call_llm("PROMPT", system="SYS", user_preferences=dict(_USER_PREFS))

    assert resp.content == '{"ok": true}'
    mock_complete.assert_called_once()
