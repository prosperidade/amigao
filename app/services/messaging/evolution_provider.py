"""EvolutionProvider — implementação concreta sobre a Evolution API (PR 2.1).

Usa ``httpx`` síncrono (mesmo padrão do ``ResendClient``). Dormente por
default: sem ``EVOLUTION_API_URL``/``EVOLUTION_API_KEY`` configurados,
``send_message`` levanta erro explícito (o parsing de inbound não depende de
config e roda sempre).
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.core.config import settings
from app.services.messaging.whatsapp_provider import InboundMessage, WhatsAppProvider

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class EvolutionProviderError(Exception):
    """Falha na comunicação com a Evolution API."""

    def __init__(self, message: str, *, status_code: Optional[int] = None, body: Optional[dict] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body or {}


def _safe_json(resp: httpx.Response) -> dict:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {"data": data}
    except Exception:  # noqa: BLE001 — resposta não-JSON
        return {}


def _extract_media_url(message: dict) -> Optional[str]:
    """Extrai a URL de mídia das formas comuns do payload Evolution v2."""
    for key in ("imageMessage", "documentMessage", "videoMessage", "audioMessage"):
        node = message.get(key)
        if isinstance(node, dict) and node.get("url"):
            return node["url"]
    return message.get("mediaUrl") or None


class EvolutionProvider(WhatsAppProvider):
    """Provider concreto da Evolution API (self-hosted/hostado)."""

    name = "evolution"

    def __init__(
        self,
        *,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        instance: Optional[str] = None,
        timeout: httpx.Timeout = _DEFAULT_TIMEOUT,
    ) -> None:
        raw_url = api_url if api_url is not None else settings.EVOLUTION_API_URL
        self.api_url = (raw_url or "").rstrip("/")
        self.api_key = api_key if api_key is not None else settings.EVOLUTION_API_KEY
        self.instance = instance  # nome da instância Evolution (provider_account_id)
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.api_url and self.api_key)

    def _headers(self) -> dict[str, str]:
        return {"apikey": self.api_key or "", "Content-Type": "application/json"}

    def send_message(self, to: str, body: str, media_url: Optional[str] = None) -> dict:
        if not self.is_configured:
            raise EvolutionProviderError(
                "Evolution não configurada (EVOLUTION_API_URL/EVOLUTION_API_KEY ausentes)."
            )
        instance = self.instance or "default"
        if media_url:
            path = f"/message/sendMedia/{instance}"
            payload: dict = {"number": to, "mediatype": "document", "media": media_url, "caption": body}
        else:
            path = f"/message/sendText/{instance}"
            payload = {"number": to, "text": body}
        url = f"{self.api_url}{path}"
        try:
            resp = httpx.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
        except httpx.HTTPError as exc:
            raise EvolutionProviderError(f"Falha de rede com a Evolution: {exc}") from exc
        if resp.status_code >= 400:
            raise EvolutionProviderError(
                "Evolution retornou erro no envio.",
                status_code=resp.status_code,
                body=_safe_json(resp),
            )
        data = _safe_json(resp)
        external_id = (data.get("key") or {}).get("id") or data.get("id")
        return {"external_msg_id": external_id, "status": "sent"}

    def parse_inbound_webhook(self, payload: dict) -> InboundMessage:
        """Normaliza o webhook ``messages.upsert`` da Evolution v2.

        Forma esperada:
        ``{event, instance, data: {key:{remoteJid,id}, message:{...}, messageTimestamp}}``
        """
        data = payload.get("data") or {}
        key = data.get("key") or {}
        remote_jid = key.get("remoteJid") or ""
        from_number = remote_jid.split("@")[0] if remote_jid else ""
        message = data.get("message") or {}
        body = (
            message.get("conversation")
            or (message.get("extendedTextMessage") or {}).get("text")
            or (message.get("imageMessage") or {}).get("caption")
            or (message.get("documentMessage") or {}).get("caption")
            or ""
        )
        ts = data.get("messageTimestamp")
        return InboundMessage(
            from_number=from_number,
            body=body,
            media_url=_extract_media_url(message),
            external_msg_id=key.get("id"),
            timestamp=str(ts) if ts is not None else None,
            provider_account_id=payload.get("instance"),
        )
