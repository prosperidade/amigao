"""Smoke tests para o endpoint /api/v1/dashboard/summary."""

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.process import Process, ProcessStatus
from app.models.tenant import Tenant
from app.models.user import User


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _seed(db_session):
    tenant = Tenant(name="Tenant Dashboard")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        email="dash@example.com",
        full_name="Dash User",
        hashed_password=get_password_hash("dash1234"),
        tenant_id=tenant.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    cl = Client(
        tenant_id=tenant.id,
        full_name="Cliente Dash",
        email="cliente.dash@example.com",
        client_type=ClientType.pf,
        status=ClientStatus.active,
    )
    db_session.add(cl)
    db_session.flush()

    proc = Process(
        tenant_id=tenant.id,
        client_id=cl.id,
        title="Processo Dash",
        process_type="licenciamento",
        status=ProcessStatus.triagem,
    )
    db_session.add(proc)
    db_session.flush()

    return tenant, user, cl, proc


def test_dashboard_summary_returns_200(client: TestClient, db_session):
    """Smoke: endpoint retorna 200 com estrutura esperada."""
    tenant, user, cl, proc = _seed(db_session)
    headers = _login(client, "dash@example.com", "dash1234")

    resp = client.get("/api/v1/dashboard/summary", headers=headers)
    assert resp.status_code == 200

    data = resp.json()
    assert "active_processes" in data
    assert "overdue_tasks" in data
    assert "total_clients" in data
    assert "total_properties" in data
    assert "recent_activities" in data
    assert "my_pending_tasks" in data
    assert isinstance(data["recent_activities"], list)
    assert isinstance(data["my_pending_tasks"], list)


def test_dashboard_counts_tenant_scoped(client: TestClient, db_session):
    """Contagens refletem dados do tenant correto."""
    tenant, user, cl, proc = _seed(db_session)
    headers = _login(client, "dash@example.com", "dash1234")

    resp = client.get("/api/v1/dashboard/summary", headers=headers)
    data = resp.json()

    assert data["active_processes"] >= 1
    assert data["total_clients"] >= 1


def test_dashboard_unauthenticated_returns_401(client: TestClient):
    """Sem token retorna 401."""
    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 401


# ── Filtro de audiência do feed (linguagem de consultor · ADR-025) ───────────

def _add_audit(db_session, tenant_id, *, entity_type, entity_id, action, user_id=None):
    from app.models.audit_log import AuditLog

    log = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        details="{}",
    )
    db_session.add(log)
    db_session.flush()
    return log


def test_feed_esconde_eventos_de_sistema_sem_caso(client: TestClient, db_session):
    """Vigia diário (agent, entity_id=0) e reset não aparecem na vitrine do consultor."""
    tenant, user, cl, proc = _seed(db_session)
    # Evento DE CASO (deve aparecer)
    _add_audit(db_session, tenant.id, entity_type="process", entity_id=proc.id, action="created")
    # Eventos de SISTEMA (não devem aparecer)
    _add_audit(db_session, tenant.id, entity_type="agent", entity_id=0, action="agent.vigia.completed")
    _add_audit(db_session, tenant.id, entity_type="reset", entity_id=0, action="reset_casos_teste")
    _add_audit(db_session, tenant.id, entity_type="user", entity_id=user.id, action="ai_key_used")
    db_session.commit()

    headers = _login(client, "dash@example.com", "dash1234")
    resp = client.get("/api/v1/dashboard/summary", headers=headers, params={"view": "executivo"})
    assert resp.status_code == 200

    actions = {a["action"] for a in resp.json()["recent_activities"]}
    assert "created" in actions
    assert "agent.vigia.completed" not in actions
    assert "reset_casos_teste" not in actions
    assert "ai_key_used" not in actions


def test_feed_mostra_agente_rodado_sobre_um_caso_com_nome(client: TestClient, db_session):
    """Evento de agente COM processo (entity_id>0) aparece e resolve o nome do caso."""
    tenant, user, cl, proc = _seed(db_session)
    _add_audit(db_session, tenant.id, entity_type="agent", entity_id=proc.id, action="agent.diagnostico.completed")
    db_session.commit()

    headers = _login(client, "dash@example.com", "dash1234")
    resp = client.get("/api/v1/dashboard/summary", headers=headers, params={"view": "executivo"})
    activities = resp.json()["recent_activities"]

    diag = next(a for a in activities if a["action"] == "agent.diagnostico.completed")
    assert diag["entity_label"] == "Processo Dash"  # título do Process resolvido, sem N+1


def test_feed_sistema_permanece_auditado(client: TestClient, db_session):
    """O evento de sistema some da VITRINE, mas continua gravado (auditoria intocada)."""
    from app.models.audit_log import AuditLog

    tenant, user, cl, proc = _seed(db_session)
    _add_audit(db_session, tenant.id, entity_type="reset", entity_id=0, action="reset_casos_teste")
    db_session.commit()

    # A linha existe no banco — só não aparece no feed.
    assert (
        db_session.query(AuditLog)
        .filter(AuditLog.tenant_id == tenant.id, AuditLog.action == "reset_casos_teste")
        .count()
        == 1
    )


# ── Feed só mostra casos VIVOS (linhas órfãs de caso apagado somem) · ADR-026 ─

def test_feed_esconde_evento_de_caso_apagado(client: TestClient, db_session):
    """Caso apagado deixa linha órfã no audit_logs — some da vitrine, fica no banco."""
    from app.models.audit_log import AuditLog

    tenant, user, cl, proc = _seed(db_session)
    proc_id = proc.id

    # Um evento no caso VIVO e outro num caso que será apagado.
    _add_audit(db_session, tenant.id, entity_type="process", entity_id=proc_id, action="created")
    _add_audit(db_session, tenant.id, entity_type="agent", entity_id=999, action="agent.diagnostico.completed")
    db_session.flush()

    # Simula o wipe: o Process 999 nunca existiu / foi apagado (aqui não há Process 999).
    db_session.commit()

    headers = _login(client, "dash@example.com", "dash1234")
    resp = client.get("/api/v1/dashboard/summary", headers=headers, params={"view": "executivo"})
    activities = resp.json()["recent_activities"]
    entity_ids = {(a["entity_type"], a["entity_id"]) for a in activities}

    assert ("process", proc_id) in entity_ids            # caso vivo aparece
    assert ("agent", 999) not in entity_ids              # caso inexistente (órfão) some

    # A linha órfã continua gravada — só não aparece na vitrine.
    assert (
        db_session.query(AuditLog)
        .filter(AuditLog.tenant_id == tenant.id, AuditLog.entity_id == 999)
        .count()
        == 1
    )


def test_feed_esconde_evento_de_processo_soft_deleted(client: TestClient, db_session):
    """Process soft-deleted (deleted_at) também some da vitrine."""
    from datetime import UTC, datetime

    tenant, user, cl, proc = _seed(db_session)
    _add_audit(db_session, tenant.id, entity_type="process", entity_id=proc.id, action="status_changed")
    proc.deleted_at = datetime.now(UTC)  # soft delete
    db_session.commit()

    headers = _login(client, "dash@example.com", "dash1234")
    resp = client.get("/api/v1/dashboard/summary", headers=headers, params={"view": "executivo"})
    entity_ids = {(a["entity_type"], a["entity_id"]) for a in resp.json()["recent_activities"]}
    assert ("process", proc.id) not in entity_ids
