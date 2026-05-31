"""Abstração de provider de WhatsApp (PR 2.1).

Contrato único para envio e parsing de inbound, independente do provider
concreto. O webhook e o serviço de mensagens falam só com esta interface —
trocar de provider é configuração (`settings.WHATSAPP_PROVIDER`), não código.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel


class InboundMessage(BaseModel):
    """Mensagem inbound normalizada — qualquer provider converge para este schema.

    `from_number`: número do remetente (só dígitos, sem sufixo de JID).
    `provider_account_id`: instância/conta que recebeu (ex.: nome da instância
    Evolution) — espelha `CommunicationThread.provider_account_id`.
    """

    from_number: str
    body: str = ""
    media_url: Optional[str] = None
    external_msg_id: Optional[str] = None
    timestamp: Optional[str] = None
    provider_account_id: Optional[str] = None


class WhatsAppProvider(ABC):
    """Interface comum a todos os providers de WhatsApp."""

    name: str = "abstract"

    @abstractmethod
    def send_message(self, to: str, body: str, media_url: Optional[str] = None) -> dict:
        """Envia uma mensagem. Retorna ``{"external_msg_id": str|None, "status": str}``."""
        raise NotImplementedError

    @abstractmethod
    def parse_inbound_webhook(self, payload: dict) -> InboundMessage:
        """Normaliza o payload bruto do provider para ``InboundMessage``."""
        raise NotImplementedError
