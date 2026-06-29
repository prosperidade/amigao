"""Fase 0.2 — Movimentação do card (inicializar checklist + elo evento→card).

Prova o ciclo da Ficha 07 §6 de forma determinística (sem LLM/broker):
  caso nasce com checklist → rodar agentes da etapa marca o checklist →
  card fica "pronto para avançar" → consultor confirma → card anda E1→E2.

Causa medida no #78 (docs/trabalhos/diagnostico_movimentacao.md): intake não
criava `MacroetapaChecklist` (gate travado em False) e não havia elo
evento→card.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.audit_log import AuditLog
from app.models.client import Client, ClientStatus, ClientType
from app.models.macroetapa import Macroetapa, MacroetapaChecklist
from app.models.process import Process, ProcessStatus
from app.models.tenant import Tenant
from app.models.user import User
from app.services.macroetapa_engine import (
    initialize_macroetapa_checklists,
    mark_stage_agents_done,
)


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _seed(db_session, *, macroetapa: str | None = "entrada_demanda") -> tuple[Tenant, User, Process]:
    tenant = Tenant(name="Tenant Mov")
    db_session.add(tenant)
    db_session.flush()
    user = User(
        email="consultor@example.com",
        full_name="Consultor",
        hashed_password=get_password_hash("senha123"),
        tenant_id=tenant.id,
        is_active=True,
    )
    cli = Client(
        tenant_id=tenant.id, full_name="Cliente Mov", email="cli@example.com",
        client_type=ClientType.pf, status=ClientStatus.active,
    )
    db_session.add_all([user, cli])
    db_session.flush()
    process = Process(
        tenant_id=tenant.id, client_id=cli.id, title="Caso Mov",
        process_type="car", status=ProcessStatus.triagem, macroetapa=macroetapa,
    )
    db_session.add(process)
    db_session.commit()
    return tenant, user, process


def _checklists(db_session, process_id: int) -> list[MacroetapaChecklist]:
    return (
        db_session.query(MacroetapaChecklist)
        .filter(MacroetapaChecklist.process_id == process_id)
        .all()
    )


# ---------------------------------------------------------------------------
# 1. Inicialização do checklist (nascimento do caso)
# ---------------------------------------------------------------------------

def test_initialize_creates_seven_checklists_with_e1_actions(db_session):
    tenant, _, process = _seed(db_session)
    assert _checklists(db_session, process.id) == []  # nasce sem (simula pré-Fase 0.2)

    created = initialize_macroetapa_checklists(db_session, process, tenant.id)
    db_session.commit()

    cls = _checklists(db_session, process.id)
    assert len(cls) == 7
    e1 = next(c for c in cls if c.macroetapa == Macroetapa.entrada_demanda.value)
    assert len(e1.actions) > 0
    assert all(not a["completed"] for a in e1.actions)
    assert len(created) == 7

    # Idempotente: rodar de novo não duplica.
    again = initialize_macroetapa_checklists(db_session, process, tenant.id)
    assert again == []
    assert len(_checklists(db_session, process.id)) == 7


def test_legacy_process_backfilled_on_status_read(client: TestClient, db_session):
    """Os 2 casos de prod nasceram sem checklist — self-heal na 1ª leitura."""
    _seed(db_session)
    process = db_session.query(Process).first()
    assert _checklists(db_session, process.id) == []

    headers = _login(client, "consultor@example.com", "senha123")
    r = client.get(f"/api/v1/processes/{process.id}/macroetapa/status", headers=headers)
    assert r.status_code == 200, r.text

    db_session.expire_all()
    assert len(_checklists(db_session, process.id)) == 7


# ---------------------------------------------------------------------------
# 2. Elo evento→card: rodar agentes marca o checklist → pronto para avançar
# ---------------------------------------------------------------------------

def test_mark_stage_agents_done_completes_checklist_and_unlocks_gate(client: TestClient, db_session):
    tenant, _, process = _seed(db_session)
    initialize_macroetapa_checklists(db_session, process, tenant.id)
    db_session.commit()
    headers = _login(client, "consultor@example.com", "senha123")

    # Antes de rodar os agentes: gate travado (checklist 0%).
    before = client.get(f"/api/v1/processes/{process.id}/can-advance", headers=headers).json()
    assert before["can_advance"] is False

    # Simula a conclusão dos agentes da etapa (o que o worker faz no sucesso).
    cl = mark_stage_agents_done(db_session, process, tenant_id=tenant.id, chain_name="intake")
    db_session.commit()
    assert cl is not None
    assert cl.completion_pct == 100.0
    assert all(a["completed"] for a in cl.actions)

    # Agora o card fica pronto para avançar e o gate libera.
    after = client.get(f"/api/v1/processes/{process.id}/can-advance", headers=headers).json()
    assert after["can_advance"] is True
    assert after["current_state"] == "pronta_para_avancar"
    assert after["next_macroetapa"] == "diagnostico_preliminar"


def test_mark_stage_agents_done_ignores_foreign_chain(db_session):
    """Chain avulsa de outra etapa NÃO marca a etapa corrente (guard)."""
    tenant, _, process = _seed(db_session)
    initialize_macroetapa_checklists(db_session, process, tenant.id)
    db_session.commit()

    # entrada_demanda → chain "intake"; "analise_regulatoria" é de outra etapa.
    res = mark_stage_agents_done(db_session, process, tenant_id=tenant.id, chain_name="analise_regulatoria")
    assert res is None
    e1 = next(c for c in _checklists(db_session, process.id)
              if c.macroetapa == Macroetapa.entrada_demanda.value)
    assert all(not a["completed"] for a in e1.actions)


# ---------------------------------------------------------------------------
# 3. "Rodar agentes da etapa" (endpoint) — dispara a chain da etapa atual
# ---------------------------------------------------------------------------

def test_run_stage_agents_dispatches_current_chain(client: TestClient, db_session, monkeypatch):
    tenant, _, process = _seed(db_session)
    initialize_macroetapa_checklists(db_session, process, tenant.id)
    db_session.commit()
    headers = _login(client, "consultor@example.com", "senha123")

    import app.workers.agent_tasks as at
    fake_delay = MagicMock()
    monkeypatch.setattr(at.run_agent_chain, "delay", fake_delay)

    r = client.post(f"/api/v1/processes/{process.id}/macroetapa/run-agents", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dispatched"] is True
    assert body["chain_name"] == "intake"
    assert body["macroetapa"] == "entrada_demanda"

    fake_delay.assert_called_once()
    assert fake_delay.call_args.kwargs["chain_name"] == "intake"
    assert fake_delay.call_args.kwargs["process_id"] == process.id

    # Audit do disparo registrado.
    audits = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_id == process.id, AuditLog.action == "stage_agents_dispatched")
        .all()
    )
    assert len(audits) == 1


def test_run_stage_agents_manual_stage_not_dispatched(client: TestClient, db_session, monkeypatch):
    """Etapa sem chain (coleta_documental) é manual — não dispara."""
    tenant, _, process = _seed(db_session, macroetapa="coleta_documental")
    initialize_macroetapa_checklists(db_session, process, tenant.id)
    db_session.commit()
    headers = _login(client, "consultor@example.com", "senha123")

    import app.workers.agent_tasks as at
    fake_delay = MagicMock()
    monkeypatch.setattr(at.run_agent_chain, "delay", fake_delay)

    r = client.post(f"/api/v1/processes/{process.id}/macroetapa/run-agents", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["dispatched"] is False
    assert r.json()["chain_name"] is None
    fake_delay.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Avanço confirmado pelo consultor — card anda (E1→E2), sem disparar chain
# ---------------------------------------------------------------------------

def test_card_advances_e1_to_e2_after_agents(client: TestClient, db_session, monkeypatch):
    tenant, _, process = _seed(db_session)
    initialize_macroetapa_checklists(db_session, process, tenant.id)
    mark_stage_agents_done(db_session, process, tenant_id=tenant.id, chain_name="intake")
    db_session.commit()
    headers = _login(client, "consultor@example.com", "senha123")

    # De-inversão (ADR-017): avançar NÃO dispara a chain de agentes.
    import app.workers.agent_tasks as at
    fake_delay = MagicMock()
    monkeypatch.setattr(at.run_agent_chain, "delay", fake_delay)

    r = client.post(
        f"/api/v1/processes/{process.id}/macroetapa",
        headers=headers, json={"macroetapa": "diagnostico_preliminar"},
    )
    assert r.status_code == 200, r.text

    db_session.expire_all()
    moved = db_session.query(Process).filter(Process.id == process.id).first()
    assert moved.macroetapa == "diagnostico_preliminar"
    fake_delay.assert_not_called()

    changed = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_id == process.id, AuditLog.action == "macroetapa_changed")
        .all()
    )
    assert len(changed) == 1


def test_advance_blocked_before_running_agents(client: TestClient, db_session):
    """Sem rodar os agentes (checklist 0%), o gate trava o avanço (409)."""
    tenant, _, process = _seed(db_session)
    initialize_macroetapa_checklists(db_session, process, tenant.id)
    db_session.commit()
    headers = _login(client, "consultor@example.com", "senha123")

    r = client.post(
        f"/api/v1/processes/{process.id}/macroetapa",
        headers=headers, json={"macroetapa": "diagnostico_preliminar"},
    )
    assert r.status_code == 409
    db_session.expire_all()
    still = db_session.query(Process).filter(Process.id == process.id).first()
    assert still.macroetapa == "entrada_demanda"
