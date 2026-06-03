"""PR 2.1 — webhook de inbound WhatsApp.

Mensagem entra no thread do caso aberto; mídia vira Document; remetente
desconhecido é ignorado; cliente sem caso aberto vira thread órfão + alerta;
HMAC inválido → 401.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.models.client import Client, ClientType
from app.models.communication import CommunicationThread, Message
from app.models.document import Document
from app.models.process import Process, ProcessStatus
from app.models.tenant import Tenant

_WEBHOOK = "/api/v1/messaging/whatsapp/webhook"


@pytest.fixture(autouse=True)
def _whatsapp_configured(monkeypatch):
    """Canal WhatsApp ativo: sem EVOLUTION_API_URL/KEY o webhook responde 503
    ("WhatsApp não configurado") — desacoplado do boot em 2026-06-01. Estes
    testes exercitam o caminho com o canal configurado."""
    monkeypatch.setattr(settings, "EVOLUTION_API_URL", "https://evo.local")
    monkeypatch.setattr(settings, "EVOLUTION_API_KEY", "test-key")


def _setup(db_session, *, name: str, phone: str, with_open_process: bool = True, closed: bool = False):
    tenant = Tenant(name=f"T {name}")
    db_session.add(tenant)
    db_session.flush()
    client = Client(tenant_id=tenant.id, client_type=ClientType.pf, full_name=name, phone=phone)
    db_session.add(client)
    db_session.flush()
    process = None
    if with_open_process:
        process = Process(
            tenant_id=tenant.id,
            client_id=client.id,
            title=f"Caso {name}",
            process_type="car",
            status=ProcessStatus.arquivado if closed else ProcessStatus.diagnostico,
        )
        db_session.add(process)
        db_session.flush()
    db_session.commit()
    return tenant, client, process


def _payload(remote: str, *, text_body: str = "", media: str | None = None, msg_id: str = "MSG1") -> dict:
    message = (
        {"imageMessage": {"url": media, "caption": text_body}}
        if media
        else {"conversation": text_body}
    )
    return {
        "event": "messages.upsert",
        "instance": "amigao",
        "data": {
            "key": {"remoteJid": f"{remote}@s.whatsapp.net", "id": msg_id, "fromMe": False},
            "message": message,
            "messageTimestamp": 1717000000,
        },
    }


def test_inbound_text_lands_in_open_case_thread(client: TestClient, db_session):
    _, cli, proc = _setup(db_session, name="Romilton", phone="+55 11 99999-8888")

    r = client.post(_WEBHOOK, json=_payload("5511999998888", text_body="Olá, tudo certo?"))

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert body["orphan"] is False

    thread = db_session.query(CommunicationThread).filter_by(id=body["thread_id"]).one()
    assert thread.process_id == proc.id
    assert thread.channel == "whatsapp"
    assert thread.provider == "evolution"
    msg = db_session.query(Message).filter_by(thread_id=thread.id).one()
    assert msg.content == "Olá, tudo certo?"
    assert msg.status == "received"
    assert msg.external_msg_id == "MSG1"


def test_inbound_media_becomes_document(client: TestClient, db_session):
    _, cli, proc = _setup(db_session, name="Maria", phone="11988887777")

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.content = b"\x89PNG\r\n"
    fake_resp.headers = {"content-type": "image/png"}
    fake_storage = MagicMock()
    fake_storage.upload_bytes.return_value = {
        "storage_key": f"t/{proc.id}/whatsapp.png",
        "filename": "whatsapp.png",
        "content_type": "image/png",
        "file_size_bytes": 6,
        "checksum_sha256": "deadbeef",
    }

    with patch("app.api.v1.messaging.httpx.get", return_value=fake_resp), patch(
        "app.services.storage.get_storage_service", return_value=fake_storage
    ):
        r = client.post(
            _WEBHOOK,
            json=_payload("5511988887777", text_body="segue foto", media="https://evo/x.png", msg_id="MSG2"),
        )

    assert r.status_code == 200, r.text
    assert r.json()["document_id"] is not None
    doc = db_session.query(Document).filter_by(process_id=proc.id).one()
    assert doc.source.value == "whatsapp"
    assert doc.document_category == "whatsapp_inbound"
    assert doc.storage_key == f"t/{proc.id}/whatsapp.png"


def test_unknown_sender_is_ignored(client: TestClient, db_session):
    _setup(db_session, name="Joao", phone="11900000000")

    r = client.post(_WEBHOOK, json=_payload("5511111112222", text_body="quem sou eu"))

    assert r.status_code == 200
    assert r.json() == {"status": "ignored", "reason": "unknown_sender"}


def test_client_without_open_case_creates_orphan_thread_and_alert(client: TestClient, db_session):
    _, cli, _ = _setup(db_session, name="SemCaso", phone="11955554444", with_open_process=True, closed=True)

    r = client.post(_WEBHOOK, json=_payload("5511955554444", text_body="oi sem caso"))

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["orphan"] is True
    thread = db_session.query(CommunicationThread).filter_by(id=body["thread_id"]).one()
    assert thread.process_id is None
    assert thread.client_id == cli.id
    # alerta auditado
    audit = db_session.execute(
        text("SELECT action FROM audit_logs WHERE tenant_id = :t AND action = 'inbound_orphan'"),
        {"t": cli.tenant_id},
    ).first()
    assert audit is not None


def test_webhook_returns_503_when_whatsapp_not_configured(client: TestClient, monkeypatch):
    # Sem EVOLUTION_API_URL/KEY o canal está desligado (desacoplado do boot
    # em 2026-06-01): o webhook existe mas responde 503, nunca quebra o app.
    monkeypatch.setattr(settings, "EVOLUTION_API_URL", None)
    monkeypatch.setattr(settings, "EVOLUTION_API_KEY", None)

    r = client.post(_WEBHOOK, json=_payload("5511999998888", text_body="oi"))

    assert r.status_code == 503, r.text
    assert r.json()["detail"] == "WhatsApp não configurado."


def test_invalid_hmac_returns_401(client: TestClient, db_session, monkeypatch):
    _setup(db_session, name="HmacUser", phone="11933332222")
    monkeypatch.setattr(settings, "EVOLUTION_WEBHOOK_SECRET", "topsecret")

    r = client.post(
        _WEBHOOK,
        json=_payload("5511933332222", text_body="oi"),
        headers={"X-Hub-Signature-256": "sha256=deadbeefwrong"},
    )

    assert r.status_code == 401
