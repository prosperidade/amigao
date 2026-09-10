"""ADR-064, contenção 2 — cobertura declarada da janela reflete só o que foi lido.

Achado Codex 10/09: `_extract_structured` gravava `cobertura_chars =
fatias[-1].fim` — a última fatia PLANEJADA, não a última PROCESSADA com
sucesso. Se a fatia final falhasse no gateway (ou no parse do JSON), a janela
declarava cobertura completa (`truncado=False`) sem ter lido o trecho.
"""

from unittest.mock import PropertyMock, patch

from app.core.ai_gateway import AIGatewayError, AIResponse
from app.core.config import Settings
from app.services import ficha01_extraction as mod
from app.services.extraction_window import Fatia


def _resposta(content: str) -> AIResponse:
    return AIResponse(
        content=content, model_used="gpt-4o-mini", tokens_in=1, tokens_out=1,
        cost_usd=0.0, duration_ms=1, provider="gpt",
    )


def test_falha_na_ultima_fatia_nao_declara_cobertura_completa(monkeypatch):
    """Doc de 2 fatias, a última falha no LLM — cobertura para na fatia 0."""
    fatia0 = Fatia(indice=0, inicio=0, fim=100)
    fatia1 = Fatia(indice=1, inicio=80, fim=200)
    monkeypatch.setattr(mod, "fatiar", lambda *a, **kw: [fatia0, fatia1])

    chamadas = {"n": 0}

    def fake_complete(prompt, system=None):
        chamadas["n"] += 1
        if chamadas["n"] == 2:
            raise AIGatewayError("timeout no gateway")
        return _resposta('{"numero_car": "GO-123", "confidence": {}}')

    monkeypatch.setattr("app.core.ai_gateway.complete", fake_complete)

    with patch.object(Settings, "ai_configured", new_callable=PropertyMock, return_value=True):
        parsed, janela = mod._extract_structured("x" * 200, "car")

    assert parsed is not None
    assert janela is not None
    # cobertura para no fim da fatia 0 — NÃO no fim do documento (fatia 1).
    assert janela.cobertura_chars == fatia0.fim
    assert janela.total_chars == 200
    assert janela.completa is False
    assert janela.truncado is True
    assert len(janela.falhas) == 1
    falha = janela.falhas[0]
    assert falha["indice"] == fatia1.indice
    assert falha["inicio"] == fatia1.inicio
    assert falha["fim"] == fatia1.fim
    assert "timeout no gateway" in falha["erro"]


def test_todas_fatias_ok_declara_cobertura_completa(monkeypatch):
    """Controle: sem falhas, cobertura = fim do documento e completa=True."""
    fatia0 = Fatia(indice=0, inicio=0, fim=100)
    fatia1 = Fatia(indice=1, inicio=80, fim=200)
    monkeypatch.setattr(mod, "fatiar", lambda *a, **kw: [fatia0, fatia1])

    monkeypatch.setattr(
        "app.core.ai_gateway.complete",
        lambda prompt, system=None: _resposta('{"numero_car": "GO-123", "confidence": {}}'),
    )

    with patch.object(Settings, "ai_configured", new_callable=PropertyMock, return_value=True):
        parsed, janela = mod._extract_structured("x" * 200, "car")

    assert parsed is not None
    assert janela is not None
    assert janela.cobertura_chars == fatia1.fim == 200
    assert janela.total_chars == 200
    assert janela.completa is True
    assert janela.truncado is False
    assert janela.falhas == []


def test_falha_de_parse_json_tambem_e_registrada(monkeypatch):
    """Resposta que não é JSON válido conta como fatia falha, não silêncio."""
    fatia0 = Fatia(indice=0, inicio=0, fim=100)
    monkeypatch.setattr(mod, "fatiar", lambda *a, **kw: [fatia0])
    monkeypatch.setattr(
        "app.core.ai_gateway.complete",
        lambda prompt, system=None: _resposta("isto não é JSON"),
    )

    with patch.object(Settings, "ai_configured", new_callable=PropertyMock, return_value=True):
        parsed, janela = mod._extract_structured("x" * 100, "car")

    # Nenhuma fatia processada com sucesso — sem candidato para mesclar.
    assert parsed is None
    assert janela is None


def test_resumo_so_expoe_falhas_quando_incompleta():
    """`resumo()` não muda de shape quando não houve falha (compatibilidade)."""
    from app.services.extraction_window import JanelaResultado

    completa = JanelaResultado(parsed={}, total_chars=10, cobertura_chars=10)
    assert "falhas" not in completa.resumo()
    assert "completa" not in completa.resumo()

    incompleta = JanelaResultado(
        parsed={}, total_chars=10, cobertura_chars=5, completa=False,
        falhas=[{"indice": 1, "inicio": 5, "fim": 10, "erro": "boom"}],
    )
    resumo = incompleta.resumo()
    assert resumo["completa"] is False
    assert resumo["falhas"] == [{"indice": 1, "inicio": 5, "fim": 10, "erro": "boom"}]
