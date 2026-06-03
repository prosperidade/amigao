"""PR 2.1 — EvolutionProvider (parsing de inbound + construção do envio).

Unitários puros (sem DB, sem rede real — httpx mockado).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.messaging.evolution_provider import EvolutionProvider, EvolutionProviderError


def _provider() -> EvolutionProvider:
    return EvolutionProvider(api_url="https://evo.example.com/", api_key="KEY123", instance="amigao")


# ---------------------------------------------------------------------------
# parse_inbound_webhook
# ---------------------------------------------------------------------------

def test_parse_inbound_text_message() -> None:
    payload = {
        "event": "messages.upsert",
        "instance": "amigao",
        "data": {
            "key": {"remoteJid": "5511999998888@s.whatsapp.net", "id": "MSG1", "fromMe": False},
            "message": {"conversation": "Olá, segue o documento"},
            "messageTimestamp": 1717000000,
        },
    }
    inbound = _provider().parse_inbound_webhook(payload)
    assert inbound.from_number == "5511999998888"
    assert inbound.body == "Olá, segue o documento"
    assert inbound.media_url is None
    assert inbound.external_msg_id == "MSG1"
    assert inbound.provider_account_id == "amigao"
    assert inbound.timestamp == "1717000000"


def test_parse_inbound_media_message() -> None:
    payload = {
        "instance": "amigao",
        "data": {
            "key": {"remoteJid": "5511999998888@s.whatsapp.net", "id": "MSG2"},
            "message": {"imageMessage": {"url": "https://evo.example.com/file.jpg", "caption": "foto da matrícula"}},
        },
    }
    inbound = _provider().parse_inbound_webhook(payload)
    assert inbound.media_url == "https://evo.example.com/file.jpg"
    assert inbound.body == "foto da matrícula"


def test_parse_inbound_empty_payload_is_safe() -> None:
    inbound = _provider().parse_inbound_webhook({})
    assert inbound.from_number == ""
    assert inbound.body == ""


# ---------------------------------------------------------------------------
# send_message
# ---------------------------------------------------------------------------

def test_send_message_builds_request_and_parses_response() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"key": {"id": "SENT-ID-9"}}

    with patch("app.services.messaging.evolution_provider.httpx.post", return_value=mock_resp) as mock_post:
        result = _provider().send_message("5511999998888", "olá")

    mock_post.assert_called_once()
    called_url = mock_post.call_args.args[0] if mock_post.call_args.args else mock_post.call_args.kwargs.get("url")
    assert called_url == "https://evo.example.com/message/sendText/amigao"
    assert mock_post.call_args.kwargs["json"] == {"number": "5511999998888", "text": "olá"}
    assert mock_post.call_args.kwargs["headers"]["apikey"] == "KEY123"
    assert result == {"external_msg_id": "SENT-ID-9", "status": "sent"}


def test_send_media_uses_send_media_endpoint() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"id": "M-1"}

    with patch("app.services.messaging.evolution_provider.httpx.post", return_value=mock_resp) as mock_post:
        result = _provider().send_message("5511999998888", "doc", media_url="https://x/y.pdf")

    called_url = mock_post.call_args.args[0] if mock_post.call_args.args else mock_post.call_args.kwargs.get("url")
    assert called_url == "https://evo.example.com/message/sendMedia/amigao"
    assert mock_post.call_args.kwargs["json"]["media"] == "https://x/y.pdf"
    assert result["status"] == "sent"


def test_send_message_raises_when_not_configured() -> None:
    provider = EvolutionProvider(api_url=None, api_key=None)
    assert provider.is_configured is False
    with pytest.raises(EvolutionProviderError):
        provider.send_message("5511999998888", "oi")


def test_send_message_raises_on_http_error_status() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.json.return_value = {"error": "boom"}
    with (
        patch("app.services.messaging.evolution_provider.httpx.post", return_value=mock_resp),
        pytest.raises(EvolutionProviderError),
    ):
        _provider().send_message("5511999998888", "oi")


def test_send_message_wraps_network_error() -> None:
    with (
        patch("app.services.messaging.evolution_provider.httpx.post", side_effect=httpx.ConnectError("down")),
        pytest.raises(EvolutionProviderError),
    ):
        _provider().send_message("5511999998888", "oi")
