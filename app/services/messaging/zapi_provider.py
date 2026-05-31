"""ZAPIProvider — STUB (PR 2.1).

Mantém o contrato ``WhatsAppProvider`` pronto para uma futura implementação
Z-API. NÃO implementado nesta PR (decisão fechada). Ver dívida no
``REGISTRO_DIVIDAS`` ("Implementar Z-API provider quando demandar").
"""

from __future__ import annotations

from typing import Optional

from app.services.messaging.whatsapp_provider import InboundMessage, WhatsAppProvider

_NOT_IMPL = "Z-API ainda não implementado (provider em stub — ver REGISTRO_DIVIDAS)."


class ZAPIProvider(WhatsAppProvider):
    name = "zapi"

    def send_message(self, to: str, body: str, media_url: Optional[str] = None) -> dict:
        raise NotImplementedError(_NOT_IMPL)

    def parse_inbound_webhook(self, payload: dict) -> InboundMessage:
        raise NotImplementedError(_NOT_IMPL)
