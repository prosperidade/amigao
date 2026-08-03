"""
transcricao_audio — transcrição de áudio de reunião (dívida #103 · ADR-060).

Camada pura, espelhando `ocr_pdf`: recebe bytes, devolve texto e o que a auditoria
precisa saber (modelo, duração, custo, erro). **Não lê do storage nem persiste** —
orquestração, cache, AIJob e estado na tela ficam em `app/workers/audio_tasks.py`.

O texto produzido aqui já sai marcado com a origem ("transcrição de áudio —
reunião"), porque ele vai pousar em `Document.extracted_text` e será lido por
superfícies que não sabem que aquilo veio de uma gravação: diagnóstico, busca,
fonte clicável. A marcação viaja junto do texto, não ao lado dele.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.services.audio_files import (
    formato_suportado,
    marcar_origem,
    motivo_formato_nao_suportado,
)

logger = logging.getLogger(__name__)

# Prompt do GANCHO de resumo estruturado (decisão 3a da Isis, pendente). Fica
# pronto e desligado: quando ela responder "transcrição + resumo", é
# AUDIO_TRANSCRICAO_RESUMO_ENABLED=true, não sprint nova.
RESUMO_PROMPT = """Você recebeu a transcrição de uma reunião entre um consultor ambiental e seu cliente (produtor rural brasileiro).

Extraia APENAS o que foi efetivamente dito. Não infira, não complete, não sugira.
Se uma seção não tiver conteúdo na transcrição, escreva "nada registrado".

Responda em texto corrido, em português, nesta estrutura exata:

## O que o cliente pediu
## O que o cliente prometeu enviar
## Prazos mencionados
## Decisões tomadas na reunião

Transcrição:
---
{transcricao}
---"""

RESUMO_CABECALHO = "RESUMO ESTRUTURADO DA REUNIÃO (gerado por IA a partir da transcrição)"

# Vocabulário do domínio passado ao Whisper como `prompt`. O modelo usa esse texto
# para enviesar a transcrição — é o mecanismo oficial para termos técnicos, siglas
# e nomes próprios que o áudio comum não ensina.
#
# Não é otimização especulativa: na medição de 03/08, "auto de infração" saiu
# **"alto de infração"**. Justo o termo que decide o caso — é o auto que dispara
# prazo de defesa, esfera e rota. Termo errado quebra a busca do consultor e
# empurra o diagnóstico para a leitura errada.
#
# Teto do provedor: ~224 tokens. Mantido curto e denso, sem frases.
VOCABULARIO_DOMINIO = (
    "Vocabulário de consultoria ambiental rural brasileira: auto de infração, "
    "notificação, embargo, termo de embargo, CAR, Cadastro Ambiental Rural, "
    "SICAR, recibo do CAR, RAT, retificação, matrícula, cartório, averbação, "
    "reserva legal, APP, área de preservação permanente, ITR, NIRF, CCIR, INCRA, "
    "SIGEF, SNCR, georreferenciamento, shapefile, módulo fiscal, VTN, "
    "supressão de vegetação, PRAD, licenciamento, outorga, IBAMA, SEMAD, SEMA, "
    "ICMBio, defesa administrativa, recurso, prazo, protocolo, hectares."
)


@dataclass
class TranscricaoResult:
    text: str
    method: str  # "whisper" | "none"
    chars: int
    cost_usd: float
    audio_seconds: float
    duracao_fonte: str
    duration_ms: int
    model_used: str
    provider: str
    error: Optional[str] = None


def _falha(motivo: str, method: str = "none") -> TranscricaoResult:
    """Resultado de falha com custo CONHECIDO e zero — não `None`, não omitido.

    0.0 aqui é informação ("não gastou"), diferente de desconhecido. Colapsar os
    dois quebra a agregação de custo do tenant.
    """
    return TranscricaoResult(
        text="", method=method, chars=0, cost_usd=0.0, audio_seconds=0.0,
        duracao_fonte="nao_aplicavel", duration_ms=0, model_used="", provider="",
        error=motivo,
    )


def transcrever_audio(
    audio_bytes: bytes,
    *,
    filename: str,
    mime_type: Optional[str] = None,
    user_preferences: Optional[dict] = None,
) -> TranscricaoResult:
    """Transcreve o áudio e devolve o texto já marcado com a origem.

    Guardas ANTES de gastar a chamada, cada uma com motivo legível para a tela:
    arquivo vazio, arquivo que nem depois de comprimido cabe no provedor, formato
    que ninguém consegue ler. Falha nunca é silêncio — sempre volta em `error`.

    Dívida #201: tamanho e formato deixaram de ser problema da consultora. Quando
    o arquivo não cabe **ou** o provedor não lê aquele formato, o sistema converte
    sozinho (mp3 mono ~64 kbps, de sobra para fala) e segue. Ela só ouve falar
    disso se, mesmo comprimido, ainda não couber — e aí a instrução é sobre a
    gravação, não sobre codec.
    """
    from app.core.ai_gateway import AIGatewayError, transcribe  # noqa: PLC0415
    from app.core.config import settings  # noqa: PLC0415
    from app.services.audio_convert import converter_para_mp3, ffmpeg_disponivel  # noqa: PLC0415

    if not audio_bytes:
        return _falha("Arquivo de áudio vazio ou não recuperado do storage.")

    teto = int(settings.AUDIO_TRANSCRIPTION_MAX_BYTES)
    grande_demais = len(audio_bytes) > teto
    formato_ilegivel = not formato_suportado(filename, mime_type)

    if grande_demais or formato_ilegivel:
        if not ffmpeg_disponivel():
            # Sem a ferramenta, volta ao comportamento anterior — mas dizendo o
            # que é: limitação da instalação, não erro do arquivo dela.
            if formato_ilegivel:
                return _falha(motivo_formato_nao_suportado(filename))
            return _falha(
                f"A gravação tem {len(audio_bytes) / 1024 / 1024:.1f} MB e passa do "
                f"limite de {teto / 1024 / 1024:.1f} MB do serviço de transcrição. "
                "A compressão automática não está disponível nesta instalação — "
                "divida a gravação em duas partes e reenvie."
            )

        # O teto viaja junto: é ele que define o bitrate. Sem isso a conversão
        # sairia a 64 kbps fixos e uma reunião de 1 hora ainda estouraria
        # (27,6 MB contra 25 MB — medido em 03/08).
        conv = converter_para_mp3(audio_bytes, filename=filename, teto_bytes=teto)
        if conv.audio is None:
            return _falha(
                f"{conv.erro} Se o arquivo abrir normalmente no seu computador, "
                "reenvie-o; se não abrir, a gravação pode ter vindo corrompida."
            )

        logger.info(
            "transcricao_audio: '%s' convertido %.1f MB → %.1f MB (−%.0f%%) antes de transcrever",
            filename, conv.bytes_antes / 1024 / 1024,
            conv.bytes_depois / 1024 / 1024, conv.reducao_pct,
        )
        audio_bytes = conv.audio
        filename = f"{filename.rsplit('.', 1)[0] if '.' in filename else filename}.mp3"

        if len(audio_bytes) > teto:
            # Só AQUI ela é incomodada, e só quando a gravação passa do que cabe
            # no piso de qualidade (~2h20 medidas). A conta é em HORAS — unidade
            # que ela tem como avaliar olhando a própria gravação — e o limite
            # sugerido vem do teto real, não de um número escolhido a dedo.
            from app.services.audio_convert import duracao_maxima_suportada  # noqa: PLC0415
            limite_h = duracao_maxima_suportada(teto)
            duracao_txt = (
                f"cerca de {conv.duracao_segundos / 3600:.1f} horas de gravação"
                if conv.duracao_segundos > 0
                else f"{len(audio_bytes) / 1024 / 1024:.0f} MB"
            )
            return _falha(
                f"Mesmo depois de comprimida, a gravação ({duracao_txt}) passa do "
                f"limite do serviço de transcrição. Divida-a em partes de até "
                f"{limite_h:.0f} horas e envie cada uma separadamente."
            )

    try:
        resp = transcribe(
            audio_bytes,
            filename=filename,
            prompt=VOCABULARIO_DOMINIO,
            user_preferences=user_preferences,
            max_cost_override_usd=settings.AI_MAX_COST_PER_JOB_USD_TRANSCRICAO,
        )
    except AIGatewayError as exc:
        logger.warning("transcricao_audio: gateway recusou '%s': %s", filename, exc.message)
        return _falha(exc.message)
    except Exception as exc:  # noqa: BLE001 — o motivo tem que chegar na tela
        logger.exception("transcricao_audio: erro inesperado em '%s'", filename)
        return _falha(f"Erro inesperado na transcrição: {exc}")

    if not resp.text:
        # Áudio mudo, ruído puro ou gravação que não capturou nada. Não é erro
        # técnico — é resultado vazio, e o consultor precisa saber a diferença.
        return TranscricaoResult(
            text="", method="whisper", chars=0, cost_usd=resp.cost_usd,
            audio_seconds=resp.audio_seconds, duracao_fonte=resp.duracao_fonte,
            duration_ms=resp.duration_ms, model_used=resp.model_used,
            provider=resp.provider,
            error=(
                "A transcrição voltou vazia — o áudio pode estar mudo, com ruído "
                "demais ou sem fala audível."
            ),
        )

    texto = marcar_origem(resp.text, nome_arquivo=filename)

    return TranscricaoResult(
        text=texto,
        method="whisper",
        chars=len(texto),
        cost_usd=resp.cost_usd,
        audio_seconds=resp.audio_seconds,
        duracao_fonte=resp.duracao_fonte,
        duration_ms=resp.duration_ms,
        model_used=resp.model_used,
        provider=resp.provider,
    )


def resumir_reuniao(
    transcricao: str,
    *,
    user_preferences: Optional[dict] = None,
) -> tuple[str, float]:
    """GANCHO (decisão 3a pendente): resumo estruturado da reunião.

    Devolve ``(bloco_de_resumo, custo_usd)``. Bloco vazio quando não foi possível
    resumir — o resumo é ACRÉSCIMO; falhar nele nunca pode custar a transcrição,
    que é a entrega principal (radar não cancela voo).

    Só é chamado quando ``AUDIO_TRANSCRICAO_RESUMO_ENABLED`` está ligado.
    """
    from app.core.ai_gateway import complete  # noqa: PLC0415

    texto = (transcricao or "").strip()
    if not texto:
        return "", 0.0

    try:
        resp = complete(
            RESUMO_PROMPT.format(transcricao=texto),
            system=(
                "Você é assistente de um consultor ambiental brasileiro. "
                "Fidelidade ao que foi dito acima de completude."
            ),
            user_preferences=user_preferences,
            agent_name="atendimento",
        )
    except Exception as exc:  # noqa: BLE001 — acréscimo não derruba a entrega
        logger.warning("transcricao_audio.resumir_reuniao falhou: %s", exc)
        return "", 0.0

    corpo = (resp.content or "").strip()
    if not corpo:
        return "", resp.cost_usd
    return f"[{RESUMO_CABECALHO}]\n\n{corpo}", resp.cost_usd
