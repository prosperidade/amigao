"""Hardening 2026-06-06 (Item C): run_agent / run_agent_chain distinguem erro
DETERMINÍSTICO (schema ausente, constraint, input inválido — retry nunca resolve)
de TRANSITÓRIO (rede, timeout, deadlock — retry resolve).

Incidente que originou o fix: `extracted_field_staging` não migrada em prod →
UndefinedTable (ProgrammingError) → `db.commit()` levantava → retry de 60s sem fim
sobre um erro que retry jamais corrige.

Os testes chamam a função da task diretamente com `self.retry` monkeypatchado para
um sinal — assim provamos SEM depender do eager-retry do Celery: determinístico
NÃO chama retry (retorna failed); transitório chama.
"""

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

import app.agents as agents
from app.workers.agent_tasks import _DETERMINISTIC_ERRORS, run_agent, run_agent_chain


class _RetrySignal(Exception):
    """Sentinela: levantada no lugar de self.retry para detectar tentativa de retry."""


def _orig(msg: str) -> Exception:
    return Exception(msg)


def _raise(exc):
    def _f(*_a, **_k):
        raise exc
    return _f


# --- classificação ---------------------------------------------------------

def test_deterministic_error_set():
    assert issubclass(ProgrammingError, _DETERMINISTIC_ERRORS)  # UndefinedTable/Column
    assert issubclass(IntegrityError, _DETERMINISTIC_ERRORS)
    assert issubclass(ValueError, _DETERMINISTIC_ERRORS)
    # transitório NÃO é determinístico → continua com retry
    assert not issubclass(OperationalError, _DETERMINISTIC_ERRORS)


# --- run_agent -------------------------------------------------------------

class _FakeAgent:
    """Sem atributo job_type → _persist_failed_job é pulado (não toca o banco)."""

    def __init__(self, exc):
        self._exc = exc

    def run(self):
        raise self._exc


def _patch_run_agent(monkeypatch, exc):
    calls = {"retry": 0}
    monkeypatch.setattr(agents.AgentRegistry, "create", lambda name, ctx: _FakeAgent(exc))

    def _fake_retry(*_a, **_k):
        calls["retry"] += 1
        raise _RetrySignal()

    monkeypatch.setattr(run_agent, "retry", _fake_retry)
    return calls


def test_run_agent_no_retry_on_undefined_table(monkeypatch):
    calls = _patch_run_agent(
        monkeypatch, ProgrammingError("INSERT ...", {}, _orig('relation "x" does not exist')),
    )
    result = run_agent.run(
        agent_name="extrator", tenant_id=1, user_id=None, process_id=None, metadata={},
    )
    assert result["status"] == "failed"
    assert calls["retry"] == 0
    assert "does not exist" in result["error"]


def test_run_agent_no_retry_on_integrity_error(monkeypatch):
    calls = _patch_run_agent(monkeypatch, IntegrityError("INSERT ...", {}, _orig("unique violation")))
    result = run_agent.run(
        agent_name="extrator", tenant_id=1, user_id=None, process_id=None, metadata={},
    )
    assert result["status"] == "failed"
    assert calls["retry"] == 0


def test_run_agent_retries_on_transient(monkeypatch):
    calls = _patch_run_agent(monkeypatch, OperationalError("SELECT 1", {}, _orig("connection reset")))
    with pytest.raises(_RetrySignal):
        run_agent.run(
            agent_name="extrator", tenant_id=1, user_id=None, process_id=None, metadata={},
        )
    assert calls["retry"] == 1


# --- run_agent_chain -------------------------------------------------------

def _patch_chain_retry(monkeypatch):
    calls = {"retry": 0}

    def _fake_retry(*_a, **_k):
        calls["retry"] += 1
        raise _RetrySignal()

    monkeypatch.setattr(run_agent_chain, "retry", _fake_retry)
    return calls


def test_run_agent_chain_no_retry_on_deterministic(monkeypatch):
    monkeypatch.setattr(
        agents.OrchestratorAgent, "execute_chain",
        _raise(ProgrammingError("INSERT ...", {}, _orig('relation "x" does not exist'))),
    )
    calls = _patch_chain_retry(monkeypatch)
    result = run_agent_chain.run(chain_name="diagnostico_completo", tenant_id=1)
    assert result["status"] == "failed"
    assert calls["retry"] == 0
    assert "does not exist" in result["error"]


def test_run_agent_chain_retries_on_transient(monkeypatch):
    monkeypatch.setattr(
        agents.OrchestratorAgent, "execute_chain",
        _raise(OperationalError("SELECT 1", {}, _orig("deadlock detected"))),
    )
    calls = _patch_chain_retry(monkeypatch)
    with pytest.raises(_RetrySignal):
        run_agent_chain.run(chain_name="diagnostico_completo", tenant_id=1)
    assert calls["retry"] == 1
