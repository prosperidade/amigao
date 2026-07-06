"""Sprint 1 (Ficha 07) — ramo condicional na saída da E2 (E2→E3 / E2→E4).

Prova, contra o BD real, os dois caminhos do ramo do Diagnóstico Preliminar:

  - COM documento essencial pendente  → avança para a Coleta Documental (E3);
  - SEM documento essencial pendente  → pula a coleta e vai direto para o
    Diagnóstico Técnico (E4), e a E3 fica marcada como "skipped" no stepper.

O avanço continua CONFIRMADO pelo consultor (#82 / ADR-017): o ramo só decide
o DESTINO recomendado (`next_macroetapa`); o POST /macroetapa é o consultor.
O gate de prontidão (checklist 100% + diagnóstico assinado) continua valendo.
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.audit_log import AuditLog
from app.models.checklist_template import ProcessChecklist
from app.models.client import Client, ClientStatus, ClientType
from app.models.macroetapa import Macroetapa
from app.models.process import Process, ProcessStatus
from app.models.regulatory import RegulatoryDiagnosis
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


def _seed_e2_ready(db_session, *, required_pending: bool) -> tuple[Tenant, User, Process]:
    """Caso na E2 com a etapa PRONTA para avançar: checklist da E2 a 100% +
    diagnóstico regulatório ASSINADO. `required_pending` controla se há um
    documento essencial pendente no ProcessChecklist (o sinal do ramo)."""
    tenant = Tenant(name="Tenant Ramo E2")
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
        tenant_id=tenant.id, full_name="Cliente Ramo", email="cli@example.com",
        client_type=ClientType.pf, status=ClientStatus.active,
    )
    db_session.add_all([user, cli])
    db_session.flush()
    process = Process(
        tenant_id=tenant.id, client_id=cli.id, title="Caso Ramo E2",
        process_type="car", status=ProcessStatus.diagnostico,
        macroetapa=Macroetapa.diagnostico_preliminar.value,
    )
    db_session.add(process)
    db_session.flush()

    # Checklist das 7 etapas + E2 levada a 100% (agentes da etapa concluídos).
    initialize_macroetapa_checklists(db_session, process, tenant.id)
    cl = mark_stage_agents_done(
        db_session, process, tenant_id=tenant.id, chain_name="diagnostico_completo"
    )
    assert cl is not None and cl.completion_pct == 100.0

    # Diagnóstico regulatório ASSINADO (gate da etapa de diagnóstico).
    db_session.add(RegulatoryDiagnosis(
        tenant_id=tenant.id, process_id=process.id, content={}, version=1,
        validated_at=datetime.now(UTC), validated_by_user_id=user.id,
    ))

    # Fase 0 (gap-analysis Ficha 07, item 2) — Consolidação já rodou (sinal
    # que `has_consolidated` consulta); sem isso a E2 não libera mais.
    db_session.add(AuditLog(
        tenant_id=tenant.id, entity_type="process", entity_id=process.id,
        action="consolidar", details="{}",
    ))

    # ProcessChecklist documental: 1 item obrigatório, pendente ou recebido.
    status = "pending" if required_pending else "received"
    db_session.add(ProcessChecklist(
        tenant_id=tenant.id, process_id=process.id,
        items=[{
            "id": "doc_matricula", "label": "Matrícula atualizada",
            "doc_type": "matricula", "required": True, "status": status,
            "document_id": None, "waiver_reason": None,
        }],
    ))
    db_session.commit()
    return tenant, user, process


def test_e2_com_doc_essencial_pendente_vai_para_coleta(client: TestClient, db_session):
    _seed_e2_ready(db_session, required_pending=True)
    process = db_session.query(Process).first()
    headers = _login(client, "consultor@example.com", "senha123")

    # O ramo recomenda a coleta (E3); doc pendente NÃO trava (roteia).
    ca = client.get(f"/api/v1/processes/{process.id}/can-advance", headers=headers).json()
    assert ca["can_advance"] is True, ca
    assert ca["next_macroetapa"] == Macroetapa.coleta_documental.value

    # Consultor confirma o avanço para a coleta.
    r = client.post(
        f"/api/v1/processes/{process.id}/macroetapa",
        headers=headers, json={"macroetapa": Macroetapa.coleta_documental.value},
    )
    assert r.status_code == 200, r.text
    db_session.expire_all()
    moved = db_session.query(Process).filter(Process.id == process.id).first()
    assert moved.macroetapa == Macroetapa.coleta_documental.value

    changed = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_id == process.id, AuditLog.action == "macroetapa_changed")
        .all()
    )
    assert len(changed) == 1
    assert changed[0].new_value == Macroetapa.coleta_documental.value


def test_e2_sem_doc_essencial_pendente_pula_para_diagnostico_tecnico(client: TestClient, db_session):
    _seed_e2_ready(db_session, required_pending=False)
    process = db_session.query(Process).first()
    headers = _login(client, "consultor@example.com", "senha123")

    # Sem doc pendente, o ramo recomenda PULAR a coleta → diagnóstico técnico.
    ca = client.get(f"/api/v1/processes/{process.id}/can-advance", headers=headers).json()
    assert ca["can_advance"] is True, ca
    assert ca["next_macroetapa"] == Macroetapa.diagnostico_tecnico.value

    # Consultor confirma o avanço direto para o diagnóstico técnico (E4).
    r = client.post(
        f"/api/v1/processes/{process.id}/macroetapa",
        headers=headers, json={"macroetapa": Macroetapa.diagnostico_tecnico.value},
    )
    assert r.status_code == 200, r.text
    db_session.expire_all()
    moved = db_session.query(Process).filter(Process.id == process.id).first()
    assert moved.macroetapa == Macroetapa.diagnostico_tecnico.value

    changed = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_id == process.id, AuditLog.action == "macroetapa_changed")
        .all()
    )
    assert len(changed) == 1
    assert changed[0].new_value == Macroetapa.diagnostico_tecnico.value

    # O stepper não mente: a coleta pulada aparece como "skipped", não "completed".
    status = client.get(
        f"/api/v1/processes/{process.id}/macroetapa/status", headers=headers
    ).json()
    coleta = next(
        s for s in status["steps"] if s["macroetapa"] == Macroetapa.coleta_documental.value
    )
    assert coleta["status"] == "skipped"
    tecnico = next(
        s for s in status["steps"] if s["macroetapa"] == Macroetapa.diagnostico_tecnico.value
    )
    assert tecnico["status"] == "active"


def test_e4_alcancavel_sem_passar_por_e3(client: TestClient, db_session):
    """O gate da E4 não exige a E3: chegando direto da E2, a E4 é a etapa atual
    e o caso segue operável (regra: entrada da E4 é CONDIÇÃO, não 'E3 anterior')."""
    _seed_e2_ready(db_session, required_pending=False)
    process = db_session.query(Process).first()
    headers = _login(client, "consultor@example.com", "senha123")
    client.post(
        f"/api/v1/processes/{process.id}/macroetapa",
        headers=headers, json={"macroetapa": Macroetapa.diagnostico_tecnico.value},
    )
    db_session.expire_all()
    moved = db_session.query(Process).filter(Process.id == process.id).first()
    assert moved.macroetapa == Macroetapa.diagnostico_tecnico.value
