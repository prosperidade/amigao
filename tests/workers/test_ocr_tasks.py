"""ocr_then_extract — testes do pipeline de OCR + dispatch do extrator.

Cenários cobertos:
1. PDF digital → pypdf extrai → extracted_text populado, extrator despachado
2. PDF escaneado → Gemini Vision extrai → extracted_text populado
3. Upload duplicado (mesmo SHA-256) → cache twin hit, nenhum AIJob criado
4. Tenant com orçamento esgotado → status=skipped_budget, alerta emitido
5. OCR falha em todas as 3 tentativas → status=failed, error preservado
6. force=True em document com texto → re-OCR forçado (bypassa cache_self)

Mocks evitam chamadas reais a MinIO / LiteLLM / WebSocket. AIJob persistido
de verdade no banco de teste pra validar audit trail.
"""

from __future__ import annotations

from typing import Any

import pytest

import app.workers.ocr_tasks as ocr_tasks
from app.models.ai_job import AIJob
from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.process import Process, ProcessStatus
from app.models.tenant import Tenant
from app.models.user import User
from app.services.ocr_pdf import OcrResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded(db_session):
    tenant = Tenant(name="OCR Tenant")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        email="ocr@example.com",
        full_name="OCR User",
        hashed_password="x" * 60,
        tenant_id=tenant.id,
        is_active=True,
    )
    process_client = Client(
        tenant_id=tenant.id,
        full_name="Cliente OCR",
        email="cli.ocr@example.com",
        client_type=ClientType.pf,
        status=ClientStatus.active,
    )
    db_session.add_all([user, process_client])
    db_session.flush()

    process = Process(
        tenant_id=tenant.id,
        client_id=process_client.id,
        title="Processo OCR",
        process_type="car",
        status=ProcessStatus.triagem,
    )
    db_session.add(process)
    db_session.flush()

    return tenant, user, process_client, process


def _make_document(
    db_session,
    *,
    tenant_id: int,
    client_id: int,
    process_id: int,
    filename: str = "doc.pdf",
    storage_key: str | None = None,
    extracted_text: str | None = None,
    checksum: str | None = None,
) -> Document:
    doc = Document(
        tenant_id=tenant_id,
        process_id=process_id,
        client_id=client_id,
        original_file_name=filename,
        filename=filename,
        content_type="application/pdf",
        storage_key=storage_key or f"tenant-{tenant_id}/{filename}",
        document_type="matricula",
        ocr_status=OcrStatus.pending,
        extracted_text=extracted_text,
        checksum_sha256=checksum,
    )
    db_session.add(doc)
    db_session.flush()
    return doc


@pytest.fixture
def mock_boundaries(monkeypatch, db_session):
    """Mocks comuns: SessionLocal, storage, run_agent, publish_realtime_event,
    budget_guard. Retorna um bag pra testes inspecionarem chamadas."""
    bag: dict[str, Any] = {
        "extrator_calls": [],
        "events": [],
        "downloaded": b"%PDF-1.4 fake bytes for test",
    }

    # SessionLocal devolve a sessão transacional do teste sem fechar
    class _NoCloseSession:
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def close(self) -> None:
            pass

        def rollback(self) -> None:
            # Não rolar back a transação externa do teste em caso de erro
            pass

    monkeypatch.setattr(
        ocr_tasks, "SessionLocal", lambda: _NoCloseSession(db_session)
    )

    # Storage
    class _FakeStorage:
        def download_bytes(self, _key: str) -> bytes:
            return bag["downloaded"]

    monkeypatch.setattr(
        "app.services.storage.get_storage_service",
        lambda: _FakeStorage(),
    )

    # run_agent.delay → captura
    class _FakeRunAgent:
        @staticmethod
        def delay(**kwargs):
            bag["extrator_calls"].append(kwargs)

    import app.workers.agent_tasks as agent_tasks_mod
    monkeypatch.setattr(agent_tasks_mod, "run_agent", _FakeRunAgent)

    # publish_realtime_event → captura
    def _fake_publish(*, tenant_id, event_type, payload, client_id=None):
        bag["events"].append({
            "tenant_id": tenant_id,
            "event_type": event_type,
            "payload": payload,
        })
        return True

    monkeypatch.setattr(
        "app.services.notifications.publish_realtime_event",
        _fake_publish,
    )

    # Budget guard — default no-op (pode ser sobrescrito por teste)
    monkeypatch.setattr(
        "app.core.ai_gateway.check_tenant_monthly_budget",
        lambda *a, **kw: None,
    )

    return bag


def _run_task(**kwargs) -> dict[str, Any]:
    """Executa ocr_then_extract sincronamente e devolve o dict de resultado."""
    return ocr_tasks.ocr_then_extract.apply(kwargs=kwargs).get()


# ---------------------------------------------------------------------------
# 1) PDF digital → pypdf extrai → extracted_text populado
# ---------------------------------------------------------------------------


def test_pdf_digital_pypdf_extrai_e_dispatcha_extrator(
    seeded, db_session, monkeypatch, mock_boundaries
):
    tenant, user, client, process = seeded
    doc = _make_document(
        db_session,
        tenant_id=tenant.id,
        client_id=client.id,
        process_id=process.id,
        filename="matricula-digital.pdf",
    )

    monkeypatch.setattr(
        "app.services.ocr_pdf.extract_text_from_pdf",
        lambda pdf_bytes, mime_type="application/pdf": OcrResult(
            text="MATRÍCULA 12345 — área 50ha",
            method="pypdf",
            chars=28,
            cost_usd=0.0,
            tokens_in=0,
            tokens_out=0,
            duration_ms=42,
            model_used="pypdf",
            provider="pypdf",
        ),
    )

    result = _run_task(doc_id=doc.id, tenant_id=tenant.id, user_id=user.id)

    assert result["status"] == "ocr_ok"
    assert result["method"] == "pypdf"
    assert result["cost_usd"] == 0.0

    db_session.expire(doc)
    refreshed = db_session.get(Document, doc.id)
    assert refreshed.extracted_text == "MATRÍCULA 12345 — área 50ha"
    assert refreshed.ocr_status == OcrStatus.done
    assert refreshed.confidence_score == 0.95  # pypdf é determinístico

    # AIJob persistido pra audit
    ai_jobs = db_session.query(AIJob).filter(AIJob.entity_id == doc.id).all()
    assert len(ai_jobs) == 1
    assert ai_jobs[0].agent_name == "ocr_pdf"
    assert ai_jobs[0].cost_usd == 0.0

    # Extrator despachado uma vez
    assert len(mock_boundaries["extrator_calls"]) == 1
    assert mock_boundaries["extrator_calls"][0]["agent_name"] == "extrator"
    assert mock_boundaries["extrator_calls"][0]["metadata"]["document_id"] == doc.id

    # WebSocket event de sucesso
    completed = [e for e in mock_boundaries["events"] if e["event_type"] == "document.ocr.completed"]
    assert len(completed) == 1
    assert completed[0]["payload"]["method"] == "pypdf"
    assert completed[0]["payload"]["status"] == "completed"


# ---------------------------------------------------------------------------
# 2) PDF escaneado → Gemini Vision extrai
# ---------------------------------------------------------------------------


def test_pdf_escaneado_gemini_extrai(
    seeded, db_session, monkeypatch, mock_boundaries
):
    tenant, user, client, process = seeded
    doc = _make_document(
        db_session,
        tenant_id=tenant.id,
        client_id=client.id,
        process_id=process.id,
        filename="ccir-escaneado.pdf",
    )

    monkeypatch.setattr(
        "app.services.ocr_pdf.extract_text_from_pdf",
        lambda pdf_bytes, mime_type="application/pdf": OcrResult(
            text="CCIR 2026 — código do imóvel 901.234.567.890-1",
            method="gemini",
            chars=48,
            cost_usd=0.00063,
            tokens_in=1024,
            tokens_out=128,
            duration_ms=2100,
            model_used="gemini/gemini-2.0-flash",
            provider="gemini",
        ),
    )

    result = _run_task(doc_id=doc.id, tenant_id=tenant.id, user_id=user.id)

    assert result["status"] == "ocr_ok"
    assert result["method"] == "gemini"
    assert result["cost_usd"] == pytest.approx(0.00063)

    refreshed = db_session.get(Document, doc.id)
    assert "CCIR" in refreshed.extracted_text
    assert refreshed.ocr_status == OcrStatus.done
    assert refreshed.confidence_score == 0.70  # Vision tem confidence menor

    ai_job = db_session.query(AIJob).filter(AIJob.entity_id == doc.id).one()
    assert ai_job.model_used == "gemini/gemini-2.0-flash"
    assert ai_job.tokens_in == 1024
    assert ai_job.cost_usd == pytest.approx(0.00063)


# ---------------------------------------------------------------------------
# 3) Upload duplicado (mesmo SHA-256) → cache twin hit
# ---------------------------------------------------------------------------


def test_cache_twin_hit_evita_ocr(
    seeded, db_session, monkeypatch, mock_boundaries
):
    tenant, user, client, process = seeded

    # Twin: documento já processado anteriormente com o mesmo checksum
    twin_text = "TEXTO JÁ EXTRAÍDO ANTES — twin hit"
    expected_checksum = ocr_tasks.__dict__  # placeholder
    from app.services.ocr_pdf import compute_sha256
    expected_checksum = compute_sha256(mock_boundaries["downloaded"])

    twin = _make_document(
        db_session,
        tenant_id=tenant.id,
        client_id=client.id,
        process_id=process.id,
        filename="twin.pdf",
        extracted_text=twin_text,
        checksum=expected_checksum,
    )
    twin.ocr_status = OcrStatus.done
    twin.confidence_score = 0.95
    db_session.flush()

    # Novo doc (sem texto, sem checksum). Vai bater no twin.
    new_doc = _make_document(
        db_session,
        tenant_id=tenant.id,
        client_id=client.id,
        process_id=process.id,
        filename="reupload.pdf",
        storage_key=f"tenant-{tenant.id}/reupload.pdf",
    )

    # Se extract_text_from_pdf for chamado, o teste falha — twin deve curto-circuitar
    def _should_not_be_called(*a, **kw):
        raise AssertionError("OCR não devia rodar — twin cache hit esperado")

    monkeypatch.setattr(
        "app.services.ocr_pdf.extract_text_from_pdf", _should_not_be_called
    )

    result = _run_task(doc_id=new_doc.id, tenant_id=tenant.id, user_id=user.id)

    assert result["status"] == "cache_hit_twin"
    assert result["twin_id"] == twin.id

    refreshed = db_session.get(Document, new_doc.id)
    assert refreshed.extracted_text == twin_text
    assert refreshed.ocr_status == OcrStatus.done
    assert refreshed.checksum_sha256 == expected_checksum

    # Nenhum AIJob criado (não houve chamada LLM)
    ai_jobs = db_session.query(AIJob).filter(AIJob.entity_id == new_doc.id).count()
    assert ai_jobs == 0

    # Evento emitido com method=cache_twin
    completed = [e for e in mock_boundaries["events"] if e["event_type"] == "document.ocr.completed"]
    assert len(completed) == 1
    assert completed[0]["payload"]["method"] == "cache_twin"
    assert completed[0]["payload"]["twin_id"] == twin.id


# ---------------------------------------------------------------------------
# 4) Tenant com orçamento esgotado → skipped_budget + alerta
# ---------------------------------------------------------------------------


def test_budget_esgotado_skipped_e_alerta_emitido(
    seeded, db_session, monkeypatch, mock_boundaries
):
    tenant, user, client, process = seeded
    doc = _make_document(
        db_session,
        tenant_id=tenant.id,
        client_id=client.id,
        process_id=process.id,
        filename="caro.pdf",
    )

    # Budget guard rejeita
    def _budget_blown(*a, **kw):
        raise RuntimeError("monthly budget exceeded for tenant")

    monkeypatch.setattr(
        "app.core.ai_gateway.check_tenant_monthly_budget", _budget_blown
    )

    # OCR não deve ser chamado quando o budget guard barra
    def _should_not_be_called(*a, **kw):
        raise AssertionError("OCR não devia rodar com budget esgotado")

    monkeypatch.setattr(
        "app.services.ocr_pdf.extract_text_from_pdf", _should_not_be_called
    )

    result = _run_task(doc_id=doc.id, tenant_id=tenant.id, user_id=user.id)

    assert result["status"] == "budget_exceeded"
    assert "monthly budget" in result["error"]

    refreshed = db_session.get(Document, doc.id)
    assert refreshed.ocr_status == OcrStatus.failed
    assert refreshed.extracted_text is None

    failed_events = [
        e for e in mock_boundaries["events"]
        if e["event_type"] == "document.ocr.failed"
    ]
    assert len(failed_events) == 1
    assert failed_events[0]["payload"]["status"] == "skipped_budget"


# ---------------------------------------------------------------------------
# 5) OCR falha em toda a cascata → status=failed, erro preservado
# ---------------------------------------------------------------------------


def test_ocr_falha_em_toda_cascata_status_failed(
    seeded, db_session, monkeypatch, mock_boundaries
):
    tenant, user, client, process = seeded
    doc = _make_document(
        db_session,
        tenant_id=tenant.id,
        client_id=client.id,
        process_id=process.id,
        filename="ilegivel.pdf",
    )

    monkeypatch.setattr(
        "app.services.ocr_pdf.extract_text_from_pdf",
        lambda pdf_bytes, mime_type="application/pdf": OcrResult(
            text="",
            method="openai_vision",
            chars=0,
            cost_usd=0.0,
            tokens_in=0,
            tokens_out=0,
            duration_ms=5000,
            model_used="gpt-4o-mini",
            provider="openai",
            error="pypdf:0chars; gemini:rate_limit; openai:rate_limit",
        ),
    )

    result = _run_task(doc_id=doc.id, tenant_id=tenant.id, user_id=user.id)

    assert result["status"] == "ocr_failed"
    refreshed = db_session.get(Document, doc.id)
    assert refreshed.ocr_status == OcrStatus.failed
    assert refreshed.extracted_text is None

    # AIJob registra a falha com erro detalhado
    ai_job = db_session.query(AIJob).filter(AIJob.entity_id == doc.id).one()
    assert "rate_limit" in ai_job.error

    # Extrator NÃO foi despachado (sem texto pra extrair)
    assert len(mock_boundaries["extrator_calls"]) == 0

    failed_events = [
        e for e in mock_boundaries["events"]
        if e["event_type"] == "document.ocr.failed"
    ]
    assert len(failed_events) == 1


# ---------------------------------------------------------------------------
# 6) force=True em document com texto → re-OCR forçado (bypassa cache_self)
# ---------------------------------------------------------------------------


def test_force_true_reocr_bypass_cache_self(
    seeded, db_session, monkeypatch, mock_boundaries
):
    tenant, user, client, process = seeded
    doc = _make_document(
        db_session,
        tenant_id=tenant.id,
        client_id=client.id,
        process_id=process.id,
        filename="re-ocr.pdf",
        extracted_text="texto antigo (baixa qualidade)",
    )
    doc.ocr_status = OcrStatus.done
    db_session.flush()

    calls: dict[str, int] = {"n": 0}

    def _fake_extract(pdf_bytes, mime_type="application/pdf"):
        calls["n"] += 1
        return OcrResult(
            text="texto novo (re-extraido)",
            method="gemini",
            chars=25,
            cost_usd=0.0004,
            tokens_in=500,
            tokens_out=100,
            duration_ms=1500,
            model_used="gemini/gemini-2.0-flash",
            provider="gemini",
        )

    monkeypatch.setattr("app.services.ocr_pdf.extract_text_from_pdf", _fake_extract)

    # Primeira chamada sem force → cache_hit_self
    r_cached = _run_task(doc_id=doc.id, tenant_id=tenant.id, user_id=user.id)
    assert r_cached["status"] == "cache_hit_self"
    assert calls["n"] == 0

    # Segunda chamada com force=True → re-OCR
    r_forced = _run_task(
        doc_id=doc.id, tenant_id=tenant.id, user_id=user.id, force=True
    )
    assert r_forced["status"] == "ocr_ok"
    assert r_forced["method"] == "gemini"
    assert calls["n"] == 1

    refreshed = db_session.get(Document, doc.id)
    assert refreshed.extracted_text == "texto novo (re-extraido)"
