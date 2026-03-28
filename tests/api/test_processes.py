from fastapi.testclient import TestClient

import app.workers.tasks as worker_tasks
from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.process import Process, ProcessStatus
from app.models.tenant import Tenant
from app.models.user import User


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

def test_create_process_unauthorized(client: TestClient):
    data = {"title": "Licenciamento de Teste", "client_id": 1}
    r = client.post("/api/v1/processes/", json=data)
    assert r.status_code == 401

def test_get_processes_unauthorized(client: TestClient):
    r = client.get("/api/v1/processes/")
    assert r.status_code == 401


def test_client_portal_only_sees_own_processes(client: TestClient, db_session):
    tenant = Tenant(name="Tenant Escopo")
    db_session.add(tenant)
    db_session.flush()

    portal_user = User(
        email="cliente.escopo@example.com",
        full_name="Cliente Escopo",
        hashed_password=get_password_hash("cliente123"),
        tenant_id=tenant.id,
        is_active=True,
    )
    internal_user = User(
        email="consultor@example.com",
        full_name="Consultor",
        hashed_password=get_password_hash("consultor123"),
        tenant_id=tenant.id,
        is_active=True,
    )
    db_session.add_all([portal_user, internal_user])
    db_session.flush()

    own_client = Client(
        tenant_id=tenant.id,
        full_name="Cliente Escopo",
        email="cliente.escopo@example.com",
        client_type=ClientType.pf,
        status=ClientStatus.active,
    )
    other_client = Client(
        tenant_id=tenant.id,
        full_name="Outro Cliente",
        email="outro.cliente@example.com",
        client_type=ClientType.pf,
        status=ClientStatus.active,
    )
    db_session.add_all([own_client, other_client])
    db_session.flush()

    own_process = Process(
        tenant_id=tenant.id,
        client_id=own_client.id,
        title="Licenciamento Cliente",
        process_type="licenciamento",
        status=ProcessStatus.triagem,
    )
    other_process = Process(
        tenant_id=tenant.id,
        client_id=other_client.id,
        title="Licenciamento Outro Cliente",
        process_type="licenciamento",
        status=ProcessStatus.triagem,
    )
    db_session.add_all([own_process, other_process])
    db_session.commit()

    portal_headers = _login(client, "cliente.escopo@example.com", "cliente123")
    internal_headers = _login(client, "consultor@example.com", "consultor123")

    portal_response = client.get("/api/v1/processes/", headers=portal_headers)
    internal_response = client.get("/api/v1/processes/", headers=internal_headers)

    assert portal_response.status_code == 200
    assert [item["id"] for item in portal_response.json()] == [own_process.id]

    assert internal_response.status_code == 200
    assert sorted(item["id"] for item in internal_response.json()) == sorted([own_process.id, other_process.id])


def test_client_portal_cannot_access_other_client_process(client: TestClient, db_session):
    tenant = Tenant(name="Tenant Processo")
    db_session.add(tenant)
    db_session.flush()

    portal_user = User(
        email="cliente.processo@example.com",
        full_name="Cliente Processo",
        hashed_password=get_password_hash("cliente123"),
        tenant_id=tenant.id,
        is_active=True,
    )
    db_session.add(portal_user)
    db_session.flush()

    own_client = Client(
        tenant_id=tenant.id,
        full_name="Cliente Processo",
        email="cliente.processo@example.com",
        client_type=ClientType.pf,
        status=ClientStatus.active,
    )
    other_client = Client(
        tenant_id=tenant.id,
        full_name="Outro Processo",
        email="outro.processo@example.com",
        client_type=ClientType.pf,
        status=ClientStatus.active,
    )
    db_session.add_all([own_client, other_client])
    db_session.flush()

    own_process = Process(
        tenant_id=tenant.id,
        client_id=own_client.id,
        title="Meu Processo",
        process_type="licenciamento",
        status=ProcessStatus.triagem,
    )
    other_process = Process(
        tenant_id=tenant.id,
        client_id=other_client.id,
        title="Processo Alheio",
        process_type="licenciamento",
        status=ProcessStatus.triagem,
    )
    db_session.add_all([own_process, other_process])
    db_session.commit()

    headers = _login(client, "cliente.processo@example.com", "cliente123")
    own_response = client.get(f"/api/v1/processes/{own_process.id}", headers=headers)
    other_response = client.get(f"/api/v1/processes/{other_process.id}", headers=headers)

    assert own_response.status_code == 200
    assert own_response.json()["id"] == own_process.id
    assert other_response.status_code == 404


def test_update_process_status_enqueues_notification(client: TestClient, db_session, monkeypatch):
    tenant = Tenant(name="Tenant Notificacao")
    db_session.add(tenant)
    db_session.flush()

    internal_user = User(
        email="consultor.notifica@example.com",
        full_name="Consultor Notifica",
        hashed_password=get_password_hash("consultor123"),
        tenant_id=tenant.id,
        is_active=True,
    )
    db_session.add(internal_user)
    db_session.flush()

    process_client = Client(
        tenant_id=tenant.id,
        full_name="Cliente Notificado",
        email="cliente.notificado@example.com",
        client_type=ClientType.pf,
        status=ClientStatus.active,
    )
    db_session.add(process_client)
    db_session.flush()

    process = Process(
        tenant_id=tenant.id,
        client_id=process_client.id,
        title="Processo Notificável",
        process_type="licenciamento",
        status=ProcessStatus.triagem,
    )
    db_session.add(process)
    db_session.commit()

    captured: dict[str, object] = {}

    def fake_delay(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(worker_tasks.notify_process_status_changed, "delay", fake_delay)

    headers = _login(client, "consultor.notifica@example.com", "consultor123")
    response = client.post(
        f"/api/v1/processes/{process.id}/status",
        json={"status": "diagnostico"},
        headers=headers,
    )

    assert response.status_code == 200
    assert captured == {
        "tenant_id": tenant.id,
        "process_id": process.id,
        "old_status": "triagem",
        "new_status": "diagnostico",
        "actor_user_id": internal_user.id,
    }
