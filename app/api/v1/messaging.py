"""Webhooks de inbound de mensagens (PR 2.1).

Integra canal a um CASO JÁ ABERTO. Mensagens inbound **NÃO criam caso**
(decisão fechada 2026-05-28): o caso é identificado pelo número do remetente
já cadastrado em ``Client``. Sem caso aberto → thread órfão + alerta. Sem
``Client`` → ignora com log (não bloqueia o webhook).

E-mail inbound (Resend) não está implementado nesta PR — ver
``INTEGRACOES_GOVTECH``. A abstração fica pronta para plugar quando o domínio/
plano habilitar o Resend Inbound.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import mimetypes
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.models.client import Client
from app.models.communication import CommunicationThread, Message
from app.models.document import Document, DocumentSource
from app.models.process import Process, ProcessStatus
from app.services.messaging import get_whatsapp_provider
from app.services.messaging.whatsapp_provider import InboundMessage
from app.services.notifications import publish_realtime_event, register_notification_audit

logger = logging.getLogger(__name__)
router = APIRouter()

_CLOSED_STATUSES = {ProcessStatus.concluido, ProcessStatus.arquivado, ProcessStatus.cancelado}
_MEDIA_TIMEOUT = httpx.Timeout(20.0, connect=5.0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verify_hmac(secret: Optional[str], raw_body: bytes, signature: Optional[str]) -> bool:
    """HMAC-SHA256 do corpo cru. Sem secret configurado → não exige assinatura
    (webhook dormente / provider sem assinatura). Aceita ``sha256=<hex>`` ou ``<hex>``."""
    if not secret:
        return True
    if not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    provided = signature.split("=", 1)[-1].strip()
    return hmac.compare_digest(expected, provided)


def _norm_phone(value: Optional[str]) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _find_client_by_phone(db: Session, number: str) -> Optional[Client]:
    """Acha o Client pelo telefone (normalizado, casando pelos últimos 8 dígitos).

    O tenant é derivado do Client encontrado (o número identifica unicamente o
    cliente). Limitação conhecida: varredura em Python — aceitável no volume
    atual; otimizar quando o cofre de telefones crescer.
    """
    target = _norm_phone(number)
    if len(target) < 8:
        return None
    tail = target[-8:]
    candidates = db.query(Client).filter(Client.phone.isnot(None)).all()
    for client in candidates:
        for phone in (client.phone, client.secondary_phone):
            norm = _norm_phone(phone)
            if norm and norm[-8:] == tail:
                return client
    return None


def _get_or_create_thread(
    db: Session,
    *,
    tenant_id: int,
    client_id: int,
    process_id: Optional[int],
    provider_name: str,
    provider_account_id: Optional[str],
) -> CommunicationThread:
    query = db.query(CommunicationThread).filter(
        CommunicationThread.tenant_id == tenant_id,
        CommunicationThread.client_id == client_id,
        CommunicationThread.channel == "whatsapp",
    )
    query = (
        query.filter(CommunicationThread.process_id == process_id)
        if process_id is not None
        else query.filter(CommunicationThread.process_id.is_(None))
    )
    thread = query.order_by(CommunicationThread.id.desc()).first()
    if thread is not None:
        return thread
    thread = CommunicationThread(
        tenant_id=tenant_id,
        process_id=process_id,
        client_id=client_id,
        title="WhatsApp" if process_id is not None else "WhatsApp (sem caso aberto)",
        channel="whatsapp",
        provider=provider_name,
        provider_account_id=provider_account_id,
    )
    db.add(thread)
    db.flush()
    return thread


def _save_media_as_document(
    db: Session,
    inbound: InboundMessage,
    *,
    tenant_id: int,
    process: Process,
    client: Client,
) -> Optional[Document]:
    """Baixa a mídia e grava como Document do caso. Best-effort (URLs de mídia
    do WhatsApp podem ser efêmeras/cifradas — falha não derruba o webhook)."""
    try:
        resp = httpx.get(inbound.media_url, timeout=_MEDIA_TIMEOUT)
        if resp.status_code >= 400 or not resp.content:
            logger.warning("messaging.whatsapp: download de mídia falhou (status=%s)", resp.status_code)
            return None
        content = resp.content
        content_type = (resp.headers.get("content-type") or "application/octet-stream").split(";")[0].strip()
        ext = (mimetypes.guess_extension(content_type) or "").lstrip(".")
        filename = f"whatsapp_{inbound.external_msg_id or 'media'}{('.' + ext) if ext else ''}"
        from app.services.storage import get_storage_service  # noqa: PLC0415

        stored = get_storage_service().upload_bytes(content, filename, content_type, tenant_id, process.id)
        doc = Document(
            tenant_id=tenant_id,
            process_id=process.id,
            client_id=client.id,
            original_file_name=filename,
            filename=filename,
            content_type=content_type,
            mime_type=content_type,
            extension=ext or None,
            storage_key=stored["storage_key"],
            file_size_bytes=stored["file_size_bytes"],
            size=stored["file_size_bytes"],
            checksum_sha256=stored["checksum_sha256"],
            source=DocumentSource.whatsapp,
            document_category="whatsapp_inbound",
        )
        db.add(doc)
        db.flush()
        return doc
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning("messaging.whatsapp: erro ao salvar mídia como Document: %s", exc)
        return None


def _alert_orphan(db: Session, *, client: Client, inbound: InboundMessage) -> None:
    """Mensagem de cliente sem caso aberto: alerta interno + audit (não cria caso)."""
    payload = {
        "client_id": client.id,
        "from_number": inbound.from_number,
        "preview": (inbound.body or "")[:200],
    }
    try:
        publish_realtime_event(
            tenant_id=client.tenant_id,
            event_type="messaging.inbound_orphan",
            payload=payload,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("messaging.whatsapp: falha ao publicar alerta órfão: %s", exc)
    try:
        register_notification_audit(
            db=db,
            tenant_id=client.tenant_id,
            entity_type="client",
            entity_id=client.id,
            action="inbound_orphan",
            details=payload,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("messaging.whatsapp: falha ao auditar alerta órfão: %s", exc)


def _ingest_inbound(db: Session, inbound: InboundMessage, *, provider_name: str) -> dict:
    client = _find_client_by_phone(db, inbound.from_number)
    if client is None:
        logger.info("messaging.whatsapp: remetente desconhecido (%s) — ignorado", inbound.from_number)
        return {"status": "ignored", "reason": "unknown_sender"}

    tenant_id = client.tenant_id
    process = (
        db.query(Process)
        .filter(
            Process.tenant_id == tenant_id,
            Process.client_id == client.id,
            Process.deleted_at.is_(None),
            Process.status.notin_(_CLOSED_STATUSES),
        )
        .order_by(Process.created_at.desc())
        .first()
    )
    is_orphan = process is None

    thread = _get_or_create_thread(
        db,
        tenant_id=tenant_id,
        client_id=client.id,
        process_id=process.id if process else None,
        provider_name=provider_name,
        provider_account_id=inbound.provider_account_id,
    )
    message = Message(
        thread_id=thread.id,
        sender_id=None,
        content=inbound.body or "",
        is_internal=False,
        status="received",
        external_msg_id=inbound.external_msg_id,
    )
    db.add(message)
    db.flush()

    document_id: Optional[int] = None
    if inbound.media_url and process is not None:
        doc = _save_media_as_document(db, inbound, tenant_id=tenant_id, process=process, client=client)
        document_id = doc.id if doc else None

    if is_orphan:
        _alert_orphan(db, client=client, inbound=inbound)

    db.commit()
    return {
        "status": "ok",
        "thread_id": thread.id,
        "message_id": message.id,
        "orphan": is_orphan,
        "document_id": document_id,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/whatsapp/webhook")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_hub_signature_256: Optional[str] = Header(default=None),
) -> dict:
    """Recebe o inbound do provider de WhatsApp (Evolution agora; Z-API futuro).

    Sempre tenta responder 200 (provider faz retry em 5xx). Exceção: HMAC
    inválido → 401 (rejeição explícita de payload não autenticado).
    """
    # Canal WhatsApp desacoplado do boot (2026-06-01): sem EVOLUTION_API_URL/KEY
    # o webhook existe mas responde 503 — nunca quebra o startup do app.
    if not (settings.EVOLUTION_API_URL and settings.EVOLUTION_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp não configurado.",
        )

    raw = await request.body()
    if not _verify_hmac(settings.EVOLUTION_WEBHOOK_SECRET, raw, x_hub_signature_256):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Assinatura HMAC inválida.")

    try:
        payload = json.loads(raw or b"{}")
    except (json.JSONDecodeError, ValueError):
        logger.warning("messaging.whatsapp: corpo não-JSON ignorado")
        return {"status": "ignored", "reason": "invalid_json"}

    provider = get_whatsapp_provider()
    try:
        inbound = provider.parse_inbound_webhook(payload)
    except Exception as exc:  # noqa: BLE001 — payload imprevisível do provider
        logger.warning("messaging.whatsapp: payload não parseável: %s", exc)
        return {"status": "ignored", "reason": "unparseable"}

    if not inbound.from_number:
        return {"status": "ignored", "reason": "no_sender"}

    return _ingest_inbound(db, inbound, provider_name=provider.name)
