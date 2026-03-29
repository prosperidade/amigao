from app.models.client import Client, ClientStatus, ClientType
from app.models.process import Process, ProcessPriority, ProcessStatus
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.tenant import Tenant
from app.models.user import User
from app.workers import pdf_generator


class FakeStorageService:
    def __init__(self):
        self.upload_calls = []

    def download_bytes(self, storage_key: str) -> bytes:
        return b""

    def upload_bytes(self, content: bytes, filename: str, content_type: str, tenant_id: int, process_id: int) -> dict:
        self.upload_calls.append(
            {
                "content": content,
                "filename": filename,
                "content_type": content_type,
                "tenant_id": tenant_id,
                "process_id": process_id,
            }
        )
        return {
            "storage_key": f"tenant_{tenant_id}/process_{process_id}/{filename}",
            "file_size_bytes": len(content),
            "checksum_sha256": "fake-checksum",
        }


def test_generate_process_visit_report_persists_document(db_session, monkeypatch):
    tenant = Tenant(name="Tenant PDF")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        tenant_id=tenant.id,
        email="consultor.pdf@example.com",
        hashed_password="hash",
        full_name="Consultor PDF",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    client = Client(
        tenant_id=tenant.id,
        full_name="Cliente PDF",
        email="cliente.pdf@example.com",
        client_type=ClientType.pf,
        status=ClientStatus.active,
    )
    db_session.add(client)
    db_session.flush()

    process = Process(
        tenant_id=tenant.id,
        client_id=client.id,
        title="Processo PDF",
        process_type="licenciamento",
        status=ProcessStatus.execucao,
        priority=ProcessPriority.media,
        description="Descricao resumida do processo para o PDF.",
        ai_summary="Resumo executivo sintetico para o cliente.",
    )
    db_session.add(process)
    db_session.flush()

    task = Task(
        tenant_id=tenant.id,
        process_id=process.id,
        title="Vistoria em campo",
        status=TaskStatus.concluida,
        priority=TaskPriority.medium,
        created_by_user_id=user.id,
    )
    db_session.add(task)
    db_session.commit()
    process_id = process.id
    tenant_id = tenant.id

    fake_storage = FakeStorageService()
    monkeypatch.setattr(pdf_generator, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(pdf_generator, "StorageService", lambda: fake_storage)

    result = pdf_generator.generate_process_visit_report(tenant_id=tenant_id, process_id=process_id)

    assert result["status"] == "success"
    assert result["document_id"] > 0
    assert len(fake_storage.upload_calls) == 1
    assert fake_storage.upload_calls[0]["filename"] == f"Relatorio_Visita_{process_id}.pdf"
