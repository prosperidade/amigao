"""
E2E Test — Document upload flow: presigned URL → confirm upload → verify in DB.
"""
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.process import Process, ProcessStatus
from app.models.tenant import Tenant
from app.models.user import User
from app.services.storage import StorageService


def _login(tc: TestClient, email: str, password: str) -> dict[str, str]:
    resp = tc.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _setup_tenant_with_process(db_session):
    """Create tenant, user, client, and process for document tests."""
    tenant = Tenant(name="Tenant Doc E2E")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        email="doc.e2e@example.com",
        full_name="User Doc E2E",
        hashed_password=get_password_hash("DocTest1"),
        tenant_id=tenant.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    cl = Client(
        tenant_id=tenant.id,
        full_name="Cliente Doc E2E",
        email="cliente.doc.e2e@example.com",
        client_type=ClientType.pf,
        status=ClientStatus.active,
    )
    db_session.add(cl)
    db_session.flush()

    process = Process(
        tenant_id=tenant.id,
        client_id=cl.id,
        title="Processo Doc E2E",
        process_type="licenciamento",
        status=ProcessStatus.triagem,
    )
    db_session.add(process)
    db_session.commit()

    return tenant, user, cl, process


def test_upload_url_returns_presigned_data(client: TestClient, db_session, monkeypatch):
    """POST /documents/upload-url returns upload_url and storage_key."""
    tenant, user, cl, process = _setup_tenant_with_process(db_session)

    mock_storage = MagicMock(spec=StorageService)
    mock_storage.generate_presigned_put_url.return_value = {
        "upload_url": "http://minio:9000/amigao-docs/presigned-url",
        "storage_key": f"tenant_{tenant.id}/process_{process.id}/relatorio.pdf",
        "expires_in": 300,
    }
    monkeypatch.setattr(
        "app.api.v1.documents._get_storage_service", lambda: mock_storage
    )

    headers = _login(client, "doc.e2e@example.com", "DocTest1")

    resp = client.post(
        "/api/v1/documents/upload-url",
        json={
            "process_id": process.id,
            "filename": "relatorio.pdf",
            "content_type": "application/pdf",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "upload_url" in data
    assert "storage_key" in data
    assert "expires_in" in data
    mock_storage.generate_presigned_put_url.assert_called_once()


def test_confirm_upload_persists_document(client: TestClient, db_session, monkeypatch):
    """POST /documents/confirm-upload persists document and it appears in listing."""
    tenant, user, cl, process = _setup_tenant_with_process(db_session)

    # Mock the worker task to avoid Celery dependency
    import app.workers.tasks as worker_tasks
    monkeypatch.setattr(worker_tasks.notify_document_uploaded, "delay", lambda **kw: None)

    headers = _login(client, "doc.e2e@example.com", "DocTest1")

    storage_key = f"tenant_{tenant.id}/process_{process.id}/laudo_ambiental.pdf"
    confirm_resp = client.post(
        "/api/v1/documents/confirm-upload",
        json={
            "process_id": process.id,
            "storage_key": storage_key,
            "filename": "laudo_ambiental.pdf",
            "content_type": "application/pdf",
            "file_size_bytes": 4096,
            "document_type": "laudo",
            "document_category": "ambiental",
        },
        headers=headers,
    )
    assert confirm_resp.status_code == 200
    doc_data = confirm_resp.json()
    assert doc_data["filename"] == "laudo_ambiental.pdf"
    assert doc_data["storage_key"] == storage_key
    assert doc_data["file_size_bytes"] == 4096
    doc_id = doc_data["id"]

    # Verify document appears in listing
    list_resp = client.get(
        f"/api/v1/documents/?process_id={process.id}",
        headers=headers,
    )
    assert list_resp.status_code == 200
    docs = list_resp.json()
    assert any(d["id"] == doc_id for d in docs)


def test_upload_url_rejects_forbidden_extension(client: TestClient, db_session, monkeypatch):
    """POST /documents/upload-url rejects .exe files."""
    tenant, user, cl, process = _setup_tenant_with_process(db_session)

    mock_storage = MagicMock(spec=StorageService)
    monkeypatch.setattr(
        "app.api.v1.documents._get_storage_service", lambda: mock_storage
    )

    headers = _login(client, "doc.e2e@example.com", "DocTest1")

    resp = client.post(
        "/api/v1/documents/upload-url",
        json={
            "process_id": process.id,
            "filename": "malware.exe",
            "content_type": "application/octet-stream",
        },
        headers=headers,
    )
    assert resp.status_code == 400
    assert "não permitida" in resp.json()["detail"]


def test_confirm_upload_rejects_oversized_file(client: TestClient, db_session):
    """confirm-upload rejects file_size_bytes > 100MB via schema validation."""
    tenant, user, cl, process = _setup_tenant_with_process(db_session)

    headers = _login(client, "doc.e2e@example.com", "DocTest1")

    resp = client.post(
        "/api/v1/documents/confirm-upload",
        json={
            "process_id": process.id,
            "storage_key": "test/oversized.pdf",
            "filename": "oversized.pdf",
            "content_type": "application/pdf",
            "file_size_bytes": 200_000_000,  # 200 MB > 100 MB limit
        },
        headers=headers,
    )
    assert resp.status_code == 422
