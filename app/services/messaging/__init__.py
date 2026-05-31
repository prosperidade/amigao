"""Camada de mensageria multi-canal (PR 2.1).

Abstração de provider de WhatsApp (Evolution agora, Z-API em stub) para
integrar canais a um CASO JÁ ABERTO. Mensagens inbound NÃO criam caso
(decisão fechada 2026-05-28) — entram no CommunicationThread do processo
identificado pelo número/e-mail do remetente já cadastrado em Client.
"""

from app.services.messaging.registry import get_whatsapp_provider
from app.services.messaging.whatsapp_provider import InboundMessage, WhatsAppProvider

__all__ = ["get_whatsapp_provider", "InboundMessage", "WhatsAppProvider"]
