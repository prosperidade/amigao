"""transcribe_audio_document — o pipeline que faz o sistema OUVIR (dívida #103).

Cenários cobertos:
1. Áudio → transcrição → `extracted_text` populado, `ocr_status=done`, AIJob com
   custo e duração persistidos.
2. O extrator NÃO é despachado (ADR-060): conversa de reunião não vira campo
   cadastral.
3. Falha de transcrição → `ocr_status=failed` com MOTIVO em `ocr_error` e evento
   `document.ocr.failed` — nunca preso em 'processing', nunca silêncio.
4. Mesmo áudio subido duas vezes → cache twin, sem pagar de novo.
5. Orçamento do tenant esgotado → não transcreve e diz por quê.

Mocks evitam MinIO/LiteLLM/WebSocket reais. O AIJob é gravado de verdade no banco
de teste, porque é ele que sustenta a auditoria de custo.
"""

from __future__ import annotations

from typing import Any

import pytest

import app.workers.audio_tasks as audio_tasks
from app.models.ai_job import AIJob
from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.process import Process, ProcessStatus
from app.models.tenant import Tenant
from app.models.user import User
from app.services.transcricao_audio import TranscricaoResult


@pytest.fixture
def seeded(db_session):
    tenant = Tenant(name="Audio Tenant")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        email="audio@example.com",
        full_name="Audio User",
        hashed_password="x" * 60,
        tenant_id=tenant.id,
        is_active=True,
    )
    cli = Client(
        tenant_id=tenant.id,
        full_name="Cliente Áudio",
        email="cli.audio@example.com",
        client_type=ClientType.pf,
        status=ClientStatus.active,
    )
    db_session.add_all([user, cli])
    db_session.flush()

    process = Process(
        tenant_id=tenant.id,
        client_id=cli.id,
        title="Processo Áudio",
        process_type="car",
        status=ProcessStatus.triagem,
    )
    db_session.add(process)
    db_session.flush()

    return tenant, user, cli, process


def _make_audio_doc(
    db_session,
    *,
    tenant_id: int,
    client_id: int,
    process_id: int,
    filename: str = "reuniao.m4a",
    extracted_text: str | None = None,
    checksum: str | None = None,
) -> Document:
    doc = Document(
        tenant_id=tenant_id,
        process_id=process_id,
        client_id=client_id,
        original_file_name=filename,
        filename=filename,
        content_type="audio/mp4",
        mime_type="audio/mp4",
        storage_key=f"tenant-{tenant_id}/{filename}-{checksum or 'novo'}",
        document_type="audio_entrevista",
        document_category="audio",
        ocr_status=OcrStatus.pending,
        extracted_text=extracted_text,
        checksum_sha256=checksum,
    )
    db_session.add(doc)
    db_session.flush()
    return doc


@pytest.fixture
def mock_boundaries(monkeypatch, db_session):
    bag: dict[str, Any] = {
        "extrator_calls": [],
        "events": [],
        "downloaded": b"fake-audio-bytes-for-test",
    }

    class _NoCloseSession:
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def close(self) -> None:
            pass

        def rollback(self) -> None:
            pass

    monkeypatch.setattr(audio_tasks, "SessionLocal", lambda: _NoCloseSession(db_session))

    class _FakeStorage:
        def download_bytes(self, _key: str) -> bytes:
            return bag["downloaded"]

    monkeypatch.setattr("app.services.storage.get_storage_service", lambda: _FakeStorage())

    class _FakeRunAgent:
        @staticmethod
        def delay(**kwargs):
            bag["extrator_calls"].append(kwargs)

    import app.workers.agent_tasks as agent_tasks_mod
    monkeypatch.setattr(agent_tasks_mod, "run_agent", _FakeRunAgent)

    def _fake_publish(*, tenant_id, event_type, payload, client_id=None):
        bag["events"].append({"event_type": event_type, "payload": payload})
        return True

    monkeypatch.setattr("app.services.notifications.publish_realtime_event", _fake_publish)
    monkeypatch.setattr("app.core.ai_gateway.check_tenant_monthly_budget", lambda *a, **kw: None)

    return bag


def _ok(texto: str = "[TRANSCRIÇÃO DE ÁUDIO — REUNIÃO]\n\nO CAR está pendente.") -> TranscricaoResult:
    return TranscricaoResult(
        text=texto, method="whisper", chars=len(texto), cost_usd=0.18,
        audio_seconds=1800.0, duracao_fonte="provedor", duration_ms=52_000,
        model_used="whisper-1", provider="openai",
    )


def _run(**kwargs) -> dict[str, Any]:
    return audio_tasks.transcribe_audio_document.apply(kwargs=kwargs).get()


# ---------------------------------------------------------------------------
# 1) Caminho feliz — o sistema ouve
# ---------------------------------------------------------------------------


def test_audio_vira_documento_com_texto(seeded, db_session, monkeypatch, mock_boundaries):
    tenant, user, cli, proc = seeded
    doc = _make_audio_doc(
        db_session, tenant_id=tenant.id, client_id=cli.id, process_id=proc.id
    )

    monkeypatch.setattr(
        "app.services.transcricao_audio.transcrever_audio",
        lambda *a, **kw: _ok(),
    )

    result = _run(doc_id=doc.id, tenant_id=tenant.id, user_id=user.id)

    assert result["status"] == "transcricao_ok"
    assert result["audio_seconds"] == 1800.0

    refreshed = db_session.get(Document, doc.id)
    assert refreshed.ocr_status == OcrStatus.done
    assert refreshed.ocr_error is None
    assert "O CAR está pendente." in refreshed.extracted_text
    # Fala espontânea erra nome/número mais que PDF digital — confiança menor.
    assert refreshed.confidence_score == 0.70


def test_auditoria_registra_custo_e_duracao(seeded, db_session, monkeypatch, mock_boundaries):
    """Princípio 2: custo por reunião tem que ser reconstruível depois."""
    tenant, user, cli, proc = seeded
    doc = _make_audio_doc(db_session, tenant_id=tenant.id, client_id=cli.id, process_id=proc.id)

    monkeypatch.setattr(
        "app.services.transcricao_audio.transcrever_audio", lambda *a, **kw: _ok()
    )

    result = _run(doc_id=doc.id, tenant_id=tenant.id, user_id=user.id)

    job = db_session.get(AIJob, result["ai_job_id"])
    assert job.agent_name == "transcricao_audio"
    assert job.model_used == "whisper-1"
    assert job.cost_usd == pytest.approx(0.18)
    assert job.input_payload["audio_seconds"] == 1800.0
    assert job.input_payload["duracao_fonte"] == "provedor"


def test_transcricao_nao_dispara_o_extrator(seeded, db_session, monkeypatch, mock_boundaries):
    """ADR-060: conversa de reunião NÃO é documento cadastral.

    Deixar o extrator garimpar matrícula e área numa fala espontânea encheria o
    staging de campo inventado a partir de "acho que é uns quatrocentos hectares".
    """
    tenant, user, cli, proc = seeded
    doc = _make_audio_doc(db_session, tenant_id=tenant.id, client_id=cli.id, process_id=proc.id)

    monkeypatch.setattr(
        "app.services.transcricao_audio.transcrever_audio", lambda *a, **kw: _ok()
    )

    _run(doc_id=doc.id, tenant_id=tenant.id, user_id=user.id)

    assert mock_boundaries["extrator_calls"] == []


# ---------------------------------------------------------------------------
# 2) Falha visível — nunca preso, nunca mudo
# ---------------------------------------------------------------------------


def test_falha_de_transcricao_aparece_com_motivo(seeded, db_session, monkeypatch, mock_boundaries):
    tenant, user, cli, proc = seeded
    doc = _make_audio_doc(db_session, tenant_id=tenant.id, client_id=cli.id, process_id=proc.id)

    falha = TranscricaoResult(
        text="", method="none", chars=0, cost_usd=0.0, audio_seconds=0.0,
        duracao_fonte="nao_aplicavel", duration_ms=0, model_used="", provider="",
        error="Formato de áudio não suportado pela transcrição (amr).",
    )
    monkeypatch.setattr(
        "app.services.transcricao_audio.transcrever_audio", lambda *a, **kw: falha
    )

    result = _run(doc_id=doc.id, tenant_id=tenant.id, user_id=user.id)

    assert result["status"] == "transcricao_falhou"

    refreshed = db_session.get(Document, doc.id)
    assert refreshed.ocr_status == OcrStatus.failed          # não fica em 'processing'
    assert "não suportado" in refreshed.ocr_error            # e o motivo chega na tela

    falhas = [e for e in mock_boundaries["events"] if e["event_type"] == "document.ocr.failed"]
    assert len(falhas) == 1


def test_storage_indisponivel_nao_vira_no_bytes_generico(
    seeded, db_session, monkeypatch, mock_boundaries
):
    """Erro REAL de storage (região errada no R2, credencial) tem causa própria —
    mascarar como 'arquivo não encontrado' manda o consultor reenviar em vão."""
    from app.services.storage import StorageDownloadError

    tenant, user, cli, proc = seeded
    doc = _make_audio_doc(db_session, tenant_id=tenant.id, client_id=cli.id, process_id=proc.id)

    class _BrokenStorage:
        def download_bytes(self, _key):
            raise StorageDownloadError(_key, "SignatureDoesNotMatch", "assinatura inválida")

    monkeypatch.setattr("app.services.storage.get_storage_service", lambda: _BrokenStorage())

    result = _run(doc_id=doc.id, tenant_id=tenant.id, user_id=user.id)

    assert result["status"] == "storage_error"
    refreshed = db_session.get(Document, doc.id)
    assert refreshed.ocr_status == OcrStatus.failed
    assert "storage" in refreshed.ocr_error.lower()


def test_orcamento_esgotado_nao_transcreve_e_diz_por_que(
    seeded, db_session, monkeypatch, mock_boundaries
):
    tenant, user, cli, proc = seeded
    doc = _make_audio_doc(db_session, tenant_id=tenant.id, client_id=cli.id, process_id=proc.id)

    def _estourou(*_a, **_kw):
        raise RuntimeError("Orçamento mensal de IA excedido")

    monkeypatch.setattr("app.core.ai_gateway.check_tenant_monthly_budget", _estourou)
    chamou = []
    monkeypatch.setattr(
        "app.services.transcricao_audio.transcrever_audio",
        lambda *a, **kw: chamou.append(1),
    )

    result = _run(doc_id=doc.id, tenant_id=tenant.id, user_id=user.id)

    assert result["status"] == "budget_exceeded"
    assert chamou == []
    refreshed = db_session.get(Document, doc.id)
    assert "Orçamento" in refreshed.ocr_error


# ---------------------------------------------------------------------------
# 3) Cache — o mesmo áudio não paga duas vezes
# ---------------------------------------------------------------------------


def test_mesmo_audio_no_rascunho_e_no_caso_usa_cache_twin(
    seeded, db_session, monkeypatch, mock_boundaries
):
    tenant, user, cli, proc = seeded
    from app.services.ocr_pdf import compute_sha256
    checksum = compute_sha256(mock_boundaries["downloaded"])

    gemeo = _make_audio_doc(
        db_session, tenant_id=tenant.id, client_id=cli.id, process_id=proc.id,
        filename="reuniao-rascunho.m4a",
        extracted_text="[TRANSCRIÇÃO DE ÁUDIO — REUNIÃO]\n\njá transcrito",
        checksum=checksum,
    )
    novo = _make_audio_doc(
        db_session, tenant_id=tenant.id, client_id=cli.id, process_id=proc.id,
        filename="reuniao-caso.m4a",
    )

    chamou = []
    monkeypatch.setattr(
        "app.services.transcricao_audio.transcrever_audio",
        lambda *a, **kw: chamou.append(1),
    )

    result = _run(doc_id=novo.id, tenant_id=tenant.id, user_id=user.id)

    assert result["status"] == "cache_hit_twin"
    assert result["twin_id"] == gemeo.id
    assert chamou == []  # não pagou de novo

    refreshed = db_session.get(Document, novo.id)
    assert refreshed.ocr_status == OcrStatus.done
    assert "já transcrito" in refreshed.extracted_text


def test_force_reprocessa_mesmo_com_texto(seeded, db_session, monkeypatch, mock_boundaries):
    """O botão 'tentar de novo' tem que re-transcrever de fato — senão o cache
    mascara o reprocesso e o consultor fica com a leitura ruim para sempre."""
    tenant, user, cli, proc = seeded
    doc = _make_audio_doc(
        db_session, tenant_id=tenant.id, client_id=cli.id, process_id=proc.id,
        extracted_text="transcrição antiga e truncada",
    )

    monkeypatch.setattr(
        "app.services.transcricao_audio.transcrever_audio",
        lambda *a, **kw: _ok("[TRANSCRIÇÃO DE ÁUDIO — REUNIÃO]\n\nversão completa"),
    )

    result = _run(doc_id=doc.id, tenant_id=tenant.id, user_id=user.id, force=True)

    assert result["status"] == "transcricao_ok"
    refreshed = db_session.get(Document, doc.id)
    assert "versão completa" in refreshed.extracted_text
