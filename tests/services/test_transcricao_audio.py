"""transcricao_audio — a camada que transforma áudio em texto (dívida #103).

Regra que estes testes fixam: **falha nunca é silêncio**. Toda saída sem texto
traz um `error` legível, escrito para o consultor e não para o log — porque é ele
quem vai ler na tela e decidir o que fazer.
"""

from __future__ import annotations

import pytest

from app.core.ai_gateway import AIGatewayError, AITranscriptionResponse
from app.services.audio_files import TRANSCRICAO_ORIGEM_LABEL
from app.services.transcricao_audio import RESUMO_CABECALHO, resumir_reuniao, transcrever_audio


def _resposta(texto: str, *, segundos: float = 120.0, custo: float = 0.012):
    return AITranscriptionResponse(
        text=texto,
        model_used="whisper-1",
        provider="openai",
        cost_usd=custo,
        duration_ms=3400,
        audio_seconds=segundos,
        duracao_fonte="provedor",
    )


def test_transcricao_bem_sucedida_sai_marcada_com_a_origem(monkeypatch):
    """O texto herda tudo de documento — então a procedência viaja NELE.

    Quem lê a transcrição depois (diagnóstico, busca, consultor) tem que saber que
    aquilo foi DITO numa reunião, não escrito num documento oficial: peso
    probatório diferente.
    """
    monkeypatch.setattr(
        "app.core.ai_gateway.transcribe",
        lambda *a, **kw: _resposta("O CAR do lote 1-C está pendente de retificação."),
    )

    r = transcrever_audio(b"fake-audio-bytes", filename="reuniao.m4a", mime_type="audio/mp4")

    assert r.error is None
    assert r.method == "whisper"
    assert TRANSCRICAO_ORIGEM_LABEL in r.text
    assert "reuniao.m4a" in r.text
    assert "CAR do lote 1-C" in r.text
    assert r.cost_usd == pytest.approx(0.012)
    assert r.audio_seconds == pytest.approx(120.0)
    assert r.duracao_fonte == "provedor"


def test_vocabulario_do_dominio_vai_no_prompt_do_whisper(monkeypatch):
    """Medido em 03/08: sem o vocabulário, "auto de infração" saiu "ALTO de
    infração" — justo o termo que dispara prazo de defesa, esfera e rota.

    O `prompt` do Whisper é o mecanismo oficial de enviesar termos técnicos, e não
    custa nada: a cobrança é por duração do áudio, não por tokens.
    """
    capturado = {}

    def _captura(audio, **kw):
        capturado.update(kw)
        return _resposta("Aí veio o auto de infração.")

    monkeypatch.setattr("app.core.ai_gateway.transcribe", _captura)

    transcrever_audio(b"bytes", filename="reuniao.mp3", mime_type="audio/mpeg")

    assert "auto de infração" in capturado["prompt"]
    assert "CAR" in capturado["prompt"]
    assert "reserva legal" in capturado["prompt"]


def test_formato_nao_suportado_falha_antes_de_gastar_a_chamada(monkeypatch):
    chamou = []
    monkeypatch.setattr(
        "app.core.ai_gateway.transcribe",
        lambda *a, **kw: chamou.append(1),
    )

    r = transcrever_audio(b"bytes", filename="gravacao.amr", mime_type="audio/amr")

    assert chamou == []          # não pagou por uma chamada que ia ser recusada
    assert r.text == ""
    assert "não suportado" in r.error
    assert "amr" in r.error
    assert r.cost_usd == 0.0     # zero CONHECIDO, não desconhecido


def test_arquivo_acima_do_teto_do_provedor_diz_o_que_fazer(monkeypatch):
    """Reunião longa em WAV estoura os 25 MB da OpenAI.

    O consultor não pode receber "erro" — tem que receber a saída: dividir ou
    reenviar em qualidade menor.
    """
    from app.core.config import settings
    monkeypatch.setattr(settings, "AUDIO_TRANSCRIPTION_MAX_BYTES", 1024)
    chamou = []
    monkeypatch.setattr("app.core.ai_gateway.transcribe", lambda *a, **kw: chamou.append(1))

    r = transcrever_audio(b"x" * 5000, filename="reuniao.wav", mime_type="audio/wav")

    assert chamou == []
    assert "passa do limite" in r.error
    assert "Divida a gravação" in r.error


def test_falha_do_gateway_vira_motivo_legivel(monkeypatch):
    def _explode(*_a, **_kw):
        raise AIGatewayError(message="Transcrição de áudio exige chave OpenAI.")

    monkeypatch.setattr("app.core.ai_gateway.transcribe", _explode)

    r = transcrever_audio(b"bytes", filename="reuniao.mp3", mime_type="audio/mpeg")

    assert r.text == ""
    assert "chave OpenAI" in r.error


def test_erro_inesperado_nao_escapa_como_stack(monkeypatch):
    """Radar não cancela voo: exceção crua da lib não pode subir e deixar o
    documento preso em 'processing' — ela vira motivo."""
    def _explode(*_a, **_kw):
        raise RuntimeError("connection reset by peer")

    monkeypatch.setattr("app.core.ai_gateway.transcribe", _explode)

    r = transcrever_audio(b"bytes", filename="reuniao.mp3", mime_type="audio/mpeg")

    assert r.text == ""
    assert "connection reset by peer" in r.error


def test_audio_mudo_e_resultado_vazio_nao_erro_tecnico(monkeypatch):
    """Distinção que importa na tela: 'falhou' ≠ 'não tinha fala'.

    O custo foi pago dos dois jeitos e precisa ser registrado.
    """
    monkeypatch.setattr(
        "app.core.ai_gateway.transcribe", lambda *a, **kw: _resposta("", custo=0.004)
    )

    r = transcrever_audio(b"bytes", filename="reuniao.mp3", mime_type="audio/mpeg")

    assert r.text == ""
    assert "vazia" in r.error
    assert r.cost_usd == pytest.approx(0.004)  # gastou; a auditoria tem que saber


# ---------------------------------------------------------------------------
# GANCHO do resumo (decisão 3a da Isis — pendente, desligado por default)
# ---------------------------------------------------------------------------


def test_resumo_estruturado_devolve_bloco_rotulado(monkeypatch):
    class _Resp:
        content = "## O que o cliente pediu\nRegularizar o CAR."
        cost_usd = 0.002

    monkeypatch.setattr("app.core.ai_gateway.complete", lambda *a, **kw: _Resp())

    bloco, custo = resumir_reuniao("transcrição qualquer")

    assert bloco.startswith(f"[{RESUMO_CABECALHO}]")
    assert "Regularizar o CAR." in bloco
    assert custo == pytest.approx(0.002)


def test_falha_no_resumo_nao_derruba_a_transcricao(monkeypatch):
    """O resumo é ACRÉSCIMO. Quebrar nele não pode custar a entrega principal."""
    def _explode(*_a, **_kw):
        raise RuntimeError("LLM fora do ar")

    monkeypatch.setattr("app.core.ai_gateway.complete", _explode)

    bloco, custo = resumir_reuniao("transcrição qualquer")

    assert bloco == ""
    assert custo == 0.0
