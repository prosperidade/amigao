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


def test_confirm_upload_enqueues_portal_notification(client: TestClient, db_session, monkeypatch):
    tenant = Tenant(name="Tenant Documentos")
    db_session.add(tenant)
    db_session.flush()

    portal_user = User(
        email="cliente.documento@example.com",
        full_name="Cliente Documento",
        hashed_password=get_password_hash("cliente123"),
        tenant_id=tenant.id,
        is_active=True,
    )
    db_session.add(portal_user)
    db_session.flush()

    process_client = Client(
        tenant_id=tenant.id,
        full_name="Cliente Documento",
        email="cliente.documento@example.com",
        client_type=ClientType.pf,
        status=ClientStatus.active,
    )
    db_session.add(process_client)
    db_session.flush()

    process = Process(
        tenant_id=tenant.id,
        client_id=process_client.id,
        title="Processo com Upload",
        process_type="licenciamento",
        status=ProcessStatus.triagem,
    )
    db_session.add(process)
    db_session.commit()

    captured: dict[str, object] = {}

    def fake_delay(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(worker_tasks.notify_document_uploaded, "delay", fake_delay)

    headers = _login(client, "cliente.documento@example.com", "cliente123")
    response = client.post(
        "/api/v1/documents/confirm-upload",
        json={
            "process_id": process.id,
            "storage_key": "tenant_1/process_1/upload-confirmado.pdf",
            "filename": "upload-confirmado.pdf",
            "content_type": "application/pdf",
            "file_size_bytes": 2048,
            "document_type": "comprovante",
            "document_category": "ambiental",
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert captured == {
        "tenant_id": tenant.id,
        "process_id": process.id,
        "document_id": body["id"],
        "actor_user_id": portal_user.id,
        "source": "client_portal",
    }
