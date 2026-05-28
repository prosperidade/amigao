from fastapi.testclient import TestClient

import app.workers.tasks as worker_tasks
from app.core.security import get_password_hash
from app.models.audit_log import AuditLog
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


def test_get_process_timeline_serializes_audit_logs(client: TestClient, db_session):
    tenant = Tenant(name="Tenant Timeline")
    db_session.add(tenant)
    db_session.flush()

    internal_user = User(
        email="consultor.timeline@example.com",
        full_name="Consultor Timeline",
        hashed_password=get_password_hash("consultor123"),
        tenant_id=tenant.id,
        is_active=True,
    )
    db_session.add(internal_user)
    db_session.flush()

    process_client = Client(
        tenant_id=tenant.id,
        full_name="Cliente Timeline",
        email="cliente.timeline@example.com",
        client_type=ClientType.pf,
        status=ClientStatus.active,
    )
    db_session.add(process_client)
    db_session.flush()

    process = Process(
        tenant_id=tenant.id,
        client_id=process_client.id,
        title="Processo Timeline",
        process_type="licenciamento",
        status=ProcessStatus.triagem,
    )
    db_session.add(process)
    db_session.flush()

    db_session.add_all(
        [
            AuditLog(
                tenant_id=tenant.id,
                user_id=internal_user.id,
                entity_type="process",
                entity_id=process.id,
                action="created",
                details="Processo criado via API",
            ),
            AuditLog(
                tenant_id=tenant.id,
                user_id=internal_user.id,
                entity_type="process",
                entity_id=process.id,
                action="notification_process_status_changed",
                details='{"channels":["email"],"email_sent":true}',
            ),
        ]
    )
    db_session.commit()

    headers = _login(client, "consultor.timeline@example.com", "consultor123")
    response = client.get(f"/api/v1/processes/{process.id}/timeline", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert sorted(item["action"] for item in payload) == [
        "created",
        "notification_process_status_changed",
    ]
    assert all(item["entity_id"] == process.id for item in payload)
    assert any(item["details"] == '{"channels":["email"],"email_sent":true}' for item in payload)


# ---------------------------------------------------------------------------
# fix/extrator-por-processo — POST /processes/{id}/extract
# ---------------------------------------------------------------------------


def _seed_process_with_docs(db_session, *, num_with_text: int, num_without_text: int):
    """Helper: cria tenant + user + client + process + N docs (com/sem extracted_text)."""
    from app.models.document import Document, OcrStatus

    tenant = Tenant(name="Tenant Extract")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        email="consultor.extract@example.com",
        full_name="Consultor Extract",
        hashed_password=get_password_hash("extract123"),
        tenant_id=tenant.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    process_client = Client(
        tenant_id=tenant.id,
        full_name="Cliente Extract",
        email="cliente.extract@example.com",
        client_type=ClientType.pf,
        status=ClientStatus.active,
    )
    db_session.add(process_client)
    db_session.flush()

    process = Process(
        tenant_id=tenant.id,
        client_id=process_client.id,
        title="Processo Extract",
        process_type="licenciamento",
        status=ProcessStatus.triagem,
    )
    db_session.add(process)
    db_session.flush()

    docs_with_text = []
    for i in range(num_with_text):
        d = Document(
            tenant_id=tenant.id,
            process_id=process.id,
            client_id=process_client.id,
            original_file_name=f"with-text-{i}.pdf",
            filename=f"with-text-{i}.pdf",
            content_type="application/pdf",
            storage_key=f"tenant_{tenant.id}/with-text-{i}.pdf",
            document_type="matricula",
            ocr_status=OcrStatus.done,
            extracted_text=f"Texto extraído do doc {i} — MATRÍCULA Nº 123",
        )
        db_session.add(d)
        docs_with_text.append(d)

    docs_no_text = []
    for i in range(num_without_text):
        d = Document(
            tenant_id=tenant.id,
            process_id=process.id,
            client_id=process_client.id,
            original_file_name=f"no-text-{i}.pdf",
            filename=f"no-text-{i}.pdf",
            content_type="application/pdf",
            storage_key=f"tenant_{tenant.id}/no-text-{i}.pdf",
            document_type="ccir",
            ocr_status=OcrStatus.pending,
        )
        db_session.add(d)
        docs_no_text.append(d)

    db_session.commit()
    return tenant, user, process, docs_with_text, docs_no_text


def test_extract_dispatches_extrator_for_cached_docs_and_ocr_for_others(
    client: TestClient, db_session, monkeypatch
):
    """3 docs: 2 com extracted_text → extrator direto; 1 sem → chain ocr_then_extract."""
    from app.workers import agent_tasks, ocr_tasks

    tenant, _user, process, docs_with, docs_no = _seed_process_with_docs(
        db_session, num_with_text=2, num_without_text=1
    )

    extract_calls: list[dict] = []
    ocr_calls: list[dict] = []

    class _FakeAsync:
        def __init__(self, id_: str):
            self.id = id_

    def fake_run_agent_delay(**kwargs):
        extract_calls.append(kwargs)
        return _FakeAsync(f"task-extract-{len(extract_calls)}")

    def fake_ocr_delay(**kwargs):
        ocr_calls.append(kwargs)
        return _FakeAsync(f"task-ocr-{len(ocr_calls)}")

    monkeypatch.setattr(agent_tasks.run_agent, "delay", fake_run_agent_delay)
    monkeypatch.setattr(ocr_tasks.ocr_then_extract, "delay", fake_ocr_delay)

    headers = _login(client, "consultor.extract@example.com", "extract123")
    response = client.post(
        f"/api/v1/processes/{process.id}/extract",
        json={},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["process_id"] == process.id
    assert payload["total_docs"] == 3
    assert len(payload["jobs"]) == 2
    assert len(payload["pending_ocr"]) == 1
    assert all(j["method"] == "extract" for j in payload["jobs"])
    assert payload["pending_ocr"][0]["method"] == "ocr_then_extract"

    # Confirma que as tasks foram efetivamente enfileiradas
    assert len(extract_calls) == 2
    assert len(ocr_calls) == 1
    assert extract_calls[0]["agent_name"] == "extrator"
    assert extract_calls[0]["process_id"] == process.id
    assert ocr_calls[0]["doc_id"] == docs_no[0].id
    assert ocr_calls[0]["force"] is False

    # AuditLog gravado
    audit = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.entity_type == "process",
            AuditLog.entity_id == process.id,
            AuditLog.action == "extractor_dispatched",
        )
        .one()
    )
    assert "2 job(s)" in audit.details and "1 chain" in audit.details


def test_extract_returns_404_when_process_has_no_documents(
    client: TestClient, db_session, monkeypatch
):
    tenant, _user, process, _, _ = _seed_process_with_docs(
        db_session, num_with_text=0, num_without_text=0
    )
    headers = _login(client, "consultor.extract@example.com", "extract123")
    response = client.post(
        f"/api/v1/processes/{process.id}/extract", json={}, headers=headers
    )
    assert response.status_code == 404
    assert "sem documentos" in response.json()["detail"].lower()


def test_extract_force_true_routes_cached_docs_through_ocr(
    client: TestClient, db_session, monkeypatch
):
    """Com force=True, mesmo docs com extracted_text vão pra ocr_then_extract (re-OCR)."""
    from app.workers import agent_tasks, ocr_tasks

    tenant, _user, process, _, _ = _seed_process_with_docs(
        db_session, num_with_text=2, num_without_text=0
    )

    extract_calls: list[dict] = []
    ocr_calls: list[dict] = []

    class _FakeAsync:
        def __init__(self, id_: str):
            self.id = id_

    monkeypatch.setattr(
        agent_tasks.run_agent, "delay",
        lambda **kw: (extract_calls.append(kw), _FakeAsync("x"))[1],
    )
    monkeypatch.setattr(
        ocr_tasks.ocr_then_extract, "delay",
        lambda **kw: (ocr_calls.append(kw), _FakeAsync("y"))[1],
    )

    headers = _login(client, "consultor.extract@example.com", "extract123")
    response = client.post(
        f"/api/v1/processes/{process.id}/extract",
        json={"force": True},
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["jobs"]) == 0
    assert len(payload["pending_ocr"]) == 2
    assert len(extract_calls) == 0
    assert len(ocr_calls) == 2
    assert all(c["force"] is True for c in ocr_calls)
