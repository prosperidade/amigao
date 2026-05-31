"""Seleção do WhatsAppProvider por configuração (PR 2.1)."""

from __future__ import annotations

from app.core.config import settings
from app.services.messaging.whatsapp_provider import WhatsAppProvider


def get_whatsapp_provider() -> WhatsAppProvider:
    """Retorna a instância do provider conforme ``settings.WHATSAPP_PROVIDER``.

    Default ``"evolution"``. ``"zapi"`` retorna o stub (levanta
    ``NotImplementedError`` ao ser usado). Valor desconhecido → ``ValueError``.
    """
    provider = (settings.WHATSAPP_PROVIDER or "evolution").strip().lower()
    if provider == "evolution":
        from app.services.messaging.evolution_provider import EvolutionProvider  # noqa: PLC0415

        return EvolutionProvider()
    if provider == "zapi":
        from app.services.messaging.zapi_provider import ZAPIProvider  # noqa: PLC0415

        return ZAPIProvider()
    raise ValueError(
        f"WHATSAPP_PROVIDER desconhecido: {provider!r} (use 'evolution' ou 'zapi')."
    )
