from app.models.client import Client, ClientStatus, ClientType
from app.models.process import Process, ProcessPriority, ProcessStatus
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.tenant import Tenant
from app.models.user import User
from app.workers import pdf_generator


class FakeStorageService:
    """Storage fake para testes — sem rede, sem MinIO.

    Cobre os 3 modos:
    - logo_bytes=b"" (default): logo "não cadastrado" → silêncio, b"".
    - logo_bytes=<conteúdo>: logo encontrado → bytes reais.
    - logo_raises=Exception: simula MinIO offline → raise; o caller
      deve degradar graciosamente (PDF sem logo + warning).
    """

    def __init__(self, logo_bytes: bytes = b"", logo_raises: Exception | None = None):
        self.upload_calls = []
        self._logo_bytes = logo_bytes
        self._logo_raises = logo_raises

    def download_bytes(self, storage_key: str) -> bytes:
        if self._logo_raises is not None:
            raise self._logo_raises
        return self._logo_bytes

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


def _seed_process(db_session) -> tuple[int, int]:
    """Seeds tenant + user + client + process + task. Retorna (tenant_id, process_id)."""
    tenant = Tenant(name="Tenant PDF")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        tenant_id=tenant.id,
        email=f"consultor.pdf.{tenant.id}@example.com",
        hashed_password="hash",
        full_name="Consultor PDF",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    client = Client(
        tenant_id=tenant.id,
        full_name="Cliente PDF",
        email=f"cliente.pdf.{tenant.id}@example.com",
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
    return tenant.id, process.id


def _patch_storage(monkeypatch, db_session, fake_storage):
    """Patcha pdf_generator para usar fake_storage e a sessão de teste.

    Importante: o módulo chama `get_storage_service()` (lru_cache), não
    `StorageService()` direto — patcha o getter para garantir que retorna o
    fake; e limpa o cache antes para descartar qualquer instância "real"
    cacheada em testes anteriores.
    """
    monkeypatch.setattr(pdf_generator, "SessionLocal", lambda: db_session)
    pdf_generator.get_storage_service.cache_clear()
    monkeypatch.setattr(pdf_generator, "get_storage_service", lambda: fake_storage)


def test_generate_process_visit_report_persists_document(db_session, monkeypatch):
    """Path feliz: logo não cadastrado (b""), nenhum warning, PDF gerado e persistido."""
    tenant_id, process_id = _seed_process(db_session)
    fake_storage = FakeStorageService()
    _patch_storage(monkeypatch, db_session, fake_storage)

    result = pdf_generator.generate_process_visit_report(tenant_id=tenant_id, process_id=process_id)

    assert result["status"] == "success"
    assert result["document_id"] > 0
    assert "warnings" not in result  # silêncio quando logo só não foi cadastrado
    assert len(fake_storage.upload_calls) == 1
    assert fake_storage.upload_calls[0]["filename"] == f"Relatorio_Visita_{process_id}.pdf"


def test_generate_process_visit_report_degrada_quando_logo_inacessivel(db_session, monkeypatch):
    """Radar-não-cancela: MinIO offline ao buscar logo → PDF é gerado mesmo assim,
    e o retorno carrega `warnings` para a UI sinalizar ao consultor (white-label)."""
    tenant_id, process_id = _seed_process(db_session)
    fake_storage = FakeStorageService(
        logo_raises=ConnectionError("Could not connect to the endpoint URL"),
    )
    _patch_storage(monkeypatch, db_session, fake_storage)

    result = pdf_generator.generate_process_visit_report(tenant_id=tenant_id, process_id=process_id)

    # PDF segue sendo gerado e persistido
    assert result["status"] == "success"
    assert result["document_id"] > 0
    assert len(fake_storage.upload_calls) == 1
    # Warning sobe ao caller (UI / log de auditoria)
    assert "warnings" in result
    assert len(result["warnings"]) == 1
    assert "logo do tenant indisponível" in result["warnings"][0]
    assert "ConnectionError" in result["warnings"][0]
