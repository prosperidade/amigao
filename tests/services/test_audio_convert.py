"""Conversão automática de áudio (dívida #201).

A regra que estes testes fixam é de PRODUTO, não de codec: **a consultora nunca
ouve falar de bitrate.** Arquivo grande demais ou em formato que o provedor não
lê é problema do sistema; ela só é incomodada quando nem a compressão resolve —
e aí a instrução é sobre a gravação ("divida em partes de até uma hora"), numa
unidade que ela tem como avaliar.

Os testes não dependem de ffmpeg instalado: eles verificam a DECISÃO (converteu?
avisou? com que texto?), com a conversão mockada. O ffmpeg de verdade é exercido
na medição registrada no pulso.
"""

from __future__ import annotations

import pytest

from app.core.ai_gateway import AITranscriptionResponse
from app.services.audio_convert import (
    BITRATE_MAX_KBPS,
    BITRATE_MIN_KBPS,
    ConversaoResult,
    bitrate_para_caber,
    duracao_maxima_suportada,
)
from app.services.transcricao_audio import transcrever_audio

TETO = 25 * 1024 * 1024


# ---------------------------------------------------------------------------
# Bitrate adaptativo — o que a medição de 03/08 obrigou a existir
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("horas", [0.5, 1.0, 1.5, 2.0])
def test_reuniao_ate_duas_horas_cabe_por_construcao(horas):
    """A 64 kbps FIXOS, 1 hora dá 27,6 MB e **não cabe** nos 25 MB (medido).

    Ou seja: converter a taxa fixa deixaria o caso-título da #201 — "reunião de
    uma hora em WAV" — falhando do mesmo jeito, só que depois de gastar CPU.
    Escolher o bitrate pela duração faz caber por construção.
    """
    segundos = horas * 3600
    kbps = bitrate_para_caber(segundos, TETO)
    tamanho = kbps * 1000 * segundos / 8
    assert tamanho <= TETO, f"{horas}h a {kbps} kbps daria {tamanho / 1024 / 1024:.1f} MB"


def test_audio_curto_nao_perde_qualidade_a_toa():
    """Meia hora cabe folgada: não há por que degradar."""
    assert bitrate_para_caber(30 * 60, TETO) == BITRATE_MAX_KBPS


def test_bitrate_nunca_desce_abaixo_do_piso():
    """Abaixo do piso a fala perde consoante. Melhor recusar e pedir divisão do
    que devolver uma transcrição ruim que ninguém sabe que é ruim."""
    assert bitrate_para_caber(10 * 3600, TETO) == BITRATE_MIN_KBPS


def test_sem_duracao_ou_sem_teto_usa_o_maximo():
    """Zero = duração desconhecida. Degradar por precaução contra um limite que
    não se sabe qual é seria perder qualidade à toa."""
    assert bitrate_para_caber(0, TETO) == BITRATE_MAX_KBPS
    assert bitrate_para_caber(3600, None) == BITRATE_MAX_KBPS


def test_limite_em_horas_bate_com_o_piso():
    """O número que vai para a mensagem da consultora vem do teto real, não de um
    palpite: ~2,2 h a 24 kbps dentro de 25 MB."""
    limite = duracao_maxima_suportada(TETO)
    assert 2.0 < limite < 2.5
    # E o que está DENTRO do limite realmente cabe.
    seg = (limite - 0.1) * 3600
    assert bitrate_para_caber(seg, TETO) * 1000 * seg / 8 <= TETO


def _resposta(texto="Bom dia, o CAR está pendente."):
    return AITranscriptionResponse(
        text=texto, model_used="whisper-1", provider="openai", cost_usd=0.01,
        duration_ms=1000, audio_seconds=60.0, duracao_fonte="provedor",
    )


@pytest.fixture
def com_ffmpeg(monkeypatch):
    """ffmpeg presente e funcionando: comprime 10× (fator realista de WAV→mp3)."""
    monkeypatch.setattr("app.services.audio_convert.ffmpeg_disponivel", lambda: True)

    def _converte(audio, *, filename="audio", teto_bytes=None):
        return ConversaoResult(
            audio=b"m" * max(1, len(audio) // 10),
            bytes_antes=len(audio),
            bytes_depois=max(1, len(audio) // 10),
            formato_origem=(filename.rsplit(".", 1)[-1] if "." in filename else "?"),
            duracao_segundos=1800.0,
        )

    monkeypatch.setattr("app.services.audio_convert.converter_para_mp3", _converte)


# ---------------------------------------------------------------------------
# O sistema resolve
# ---------------------------------------------------------------------------


def test_wav_grande_e_convertido_e_transcrito_sem_incomodar_ninguem(
    monkeypatch, com_ffmpeg
):
    """Reunião de uma hora em WAV: antes falhava pedindo 'mono, 64 kbps'."""
    recebido = {}

    def _transcribe(audio, **kw):
        recebido["bytes"] = len(audio)
        recebido["filename"] = kw.get("filename")
        return _resposta()

    monkeypatch.setattr("app.core.ai_gateway.transcribe", _transcribe)

    r = transcrever_audio(b"w" * (TETO + 5_000_000),
                          filename="reuniao.wav", mime_type="audio/wav")

    assert r.error is None, "arquivo grande deveria ter sido comprimido, não recusado"
    assert recebido["bytes"] < TETO
    # O provedor recebe o nome já com a extensão convertida — é por ele que o SDK
    # identifica o formato.
    assert recebido["filename"].endswith(".mp3")


def test_formato_que_o_provedor_nao_le_passa_a_ser_transcrito(monkeypatch, com_ffmpeg):
    """Ganho colateral do #201: `.amr` de gravador antigo era recusado.

    Antes: "formato não suportado — converta e reenvie". Agora o sistema
    converte. Recusa virou entrega.
    """
    monkeypatch.setattr("app.core.ai_gateway.transcribe", lambda a, **kw: _resposta())

    r = transcrever_audio(b"amr-pequeno", filename="gravacao.amr", mime_type="audio/amr")

    assert r.error is None
    assert "não suportado" not in (r.error or "")


def test_arquivo_pequeno_e_legivel_nao_passa_por_conversao(monkeypatch):
    """Não re-codificar à toa: mp3 que já cabe vai direto (perda zero, CPU zero)."""
    chamou = []
    monkeypatch.setattr("app.services.audio_convert.ffmpeg_disponivel", lambda: True)
    monkeypatch.setattr(
        "app.services.audio_convert.converter_para_mp3",
        lambda a, **kw: chamou.append(1),
    )
    monkeypatch.setattr("app.core.ai_gateway.transcribe", lambda a, **kw: _resposta())

    r = transcrever_audio(b"mp3-pequeno", filename="reuniao.mp3", mime_type="audio/mpeg")

    assert r.error is None
    assert chamou == [], "arquivo que já cabe não deve ser re-codificado"


# ---------------------------------------------------------------------------
# Quando o sistema NÃO resolve, a instrução é humana
# ---------------------------------------------------------------------------


def test_se_nem_comprimido_couber_a_instrucao_e_em_horas_nao_em_kbps(monkeypatch):
    """O único caso em que ela é incomodada. E a conta é dela de avaliar."""
    monkeypatch.setattr("app.services.audio_convert.ffmpeg_disponivel", lambda: True)
    # Comprime pouco (áudio já era mp3 de 3 horas): continua acima do teto.
    monkeypatch.setattr(
        "app.services.audio_convert.converter_para_mp3",
        lambda a, **kw: ConversaoResult(
            audio=b"m" * (TETO + 1000), bytes_antes=len(a),
            bytes_depois=TETO + 1000, formato_origem="wav",
            bitrate_kbps=BITRATE_MIN_KBPS, duracao_segundos=4 * 3600,
        ),
    )
    chamou = []
    monkeypatch.setattr("app.core.ai_gateway.transcribe", lambda a, **kw: chamou.append(1))

    r = transcrever_audio(b"x" * (TETO * 3), filename="reuniao.wav", mime_type="audio/wav")

    assert chamou == []
    assert "horas" in r.error
    assert "divida" in r.error.lower()
    # A palavra proibida: ela não tem por que saber o que é isso.
    for jargao in ("kbps", "bitrate", "mono", "codec", "MB/s"):
        assert jargao not in r.error, f"'{jargao}' vazou para a consultora"


def test_falha_da_conversao_sugere_o_que_verificar(monkeypatch):
    """Arquivo corrompido no upload é a causa provável — e é verificável por ela."""
    monkeypatch.setattr("app.services.audio_convert.ffmpeg_disponivel", lambda: True)
    monkeypatch.setattr(
        "app.services.audio_convert.converter_para_mp3",
        lambda a, **kw: ConversaoResult(
            audio=None, bytes_antes=len(a), bytes_depois=0, formato_origem="m4a",
            erro="Não foi possível converter o áudio (Invalid data found).",
        ),
    )

    r = transcrever_audio(b"x" * (TETO + 1), filename="reuniao.m4a", mime_type="audio/mp4")

    assert "não foi possível converter" in r.error.lower()
    assert "abrir normalmente no seu computador" in r.error


def test_sem_ffmpeg_a_mensagem_diz_que_e_limitacao_da_instalacao(monkeypatch):
    """Degradar com honestidade: sem a ferramenta, o arquivo grande volta a
    falhar — mas dizendo que é limitação daqui, não defeito do arquivo dela."""
    monkeypatch.setattr("app.services.audio_convert.ffmpeg_disponivel", lambda: False)

    r = transcrever_audio(b"x" * (TETO + 1), filename="reuniao.wav", mime_type="audio/wav")

    assert "compressão automática não está disponível" in r.error
    assert "divida a gravação em duas partes" in r.error.lower()
    for jargao in ("kbps", "bitrate", "codec"):
        assert jargao not in r.error
