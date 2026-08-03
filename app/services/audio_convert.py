"""
audio_convert — o sistema resolve o tamanho do áudio, a consultora não (dívida #201).

O problema, medido: o provedor de transcrição recusa arquivos acima de 25 MB.
Uma reunião de uma hora gravada em WAV passa disso com folga, e a saída que
existia era uma mensagem pedindo para *"reenviar em qualidade menor (mono,
64 kbps)"*. Instrução acionável só para quem sabe o que é bitrate — e a
consultora não tem por que saber. **Isso é trabalho do sistema.**

Aqui ele faz esse trabalho: converte para mp3 mono ~64 kbps, que é de sobra para
fala (o Whisper reamostra tudo para 16 kHz mono internamente, então a perda é
nenhuma na prática) e derruba o tamanho em uma ordem de grandeza. A consultora só
é avisada se, **mesmo depois de comprimir**, a gravação ainda não couber — e aí a
instrução é sobre a gravação ("divida em duas partes"), não sobre codec.

Efeito colateral bem-vindo: a conversão também resolve **formato**. Um `.amr` de
gravador antigo ou um `.wma` eram áudio que o provedor não aceita, e viravam
"formato não suportado". Passando pelo ffmpeg, viram mp3 e são transcritos. O que
antes era recusa vira entrega.

Escopo desta rodada: **conversão apenas**. Segmentar em pedaços de 25 MB fica de
fora de propósito — é específico do Whisper e vira trabalho jogado fora se a
medição do #206 apontar outro provedor.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Perfil de saída. Mono e 16 kHz não são economia agressiva: é exatamente o que o
# Whisper usa internamente (ele reamostra tudo para 16 kHz mono antes de
# processar). Guardar mais que isso é guardar o que o modelo vai jogar fora.
MP3_SAMPLE_RATE = "16000"
MP3_CANAIS = "1"

# Bitrate ADAPTATIVO, e a medição de 03/08 é o motivo. A 64 kbps fixos, uma
# reunião de 1 hora sai com 27,6 MB — **ainda acima** do teto de 25 MB do
# provedor. Ou seja: converter a taxa fixa deixaria o caso-título da dívida #201
# ("reunião de uma hora em WAV") falhando do mesmo jeito, só que depois de gastar
# CPU. Escolher o bitrate pela DURAÇÃO faz o arquivo caber por construção.
BITRATE_MAX_KBPS = 64   # curto: qualidade folgada, nada a ganhar acima disso
BITRATE_MIN_KBPS = 24   # piso: abaixo daqui a fala começa a perder consoante
# Folga para cabeçalho/ID3 e variação do encoder — o alvo não é "exatamente o
# teto", é "seguramente abaixo dele".
FOLGA_TETO = 0.92

# Teto de tempo da conversão. ffmpeg é rápido (dezenas de vezes o tempo real),
# mas o worker é pool=solo — uma conversão pendurada bloqueia a fila.
CONVERSAO_TIMEOUT_SEGUNDOS = 300


@dataclass
class ConversaoResult:
    """Resultado da conversão. `audio` é None quando não deu (com `erro` dizendo)."""

    audio: Optional[bytes]
    bytes_antes: int
    bytes_depois: int
    formato_origem: str
    erro: Optional[str] = None
    # Bitrate efetivamente usado e duração lida — vão para o AIJob, porque é o
    # par que explica o tamanho final quando alguém for investigar.
    bitrate_kbps: int = BITRATE_MAX_KBPS
    duracao_segundos: float = 0.0

    @property
    def reducao_pct(self) -> float:
        """Quanto encolheu, em %. 0.0 quando não houve conversão."""
        if not self.bytes_antes or not self.bytes_depois:
            return 0.0
        return (1 - self.bytes_depois / self.bytes_antes) * 100


def ffmpeg_disponivel() -> bool:
    """O binário existe nesta máquina?

    Em produção existe (vai na imagem). No host de desenvolvimento em Windows
    pode não existir — e nesse caso a transcrição continua funcionando para os
    arquivos que já cabiam, em vez de quebrar por falta de uma ferramenta que só
    é necessária no caso grande.
    """
    return shutil.which("ffmpeg") is not None


def duracao_segundos(caminho: str) -> float:
    """Duração do áudio via ffprobe. 0.0 quando não dá para saber.

    Zero significa "desconhecida", e quem chama trata assim: sem duração não há
    como escolher bitrate por tamanho-alvo, então usa-se o máximo.
    """
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", caminho],
            capture_output=True, text=True, timeout=30, check=False,
        )
        return float((proc.stdout or "").strip() or 0.0)
    except (ValueError, subprocess.TimeoutExpired, OSError):
        return 0.0


def bitrate_para_caber(duracao: float, teto_bytes: Optional[int]) -> int:
    """Maior bitrate (kbps) que faz `duracao` caber em `teto_bytes`.

    Sem teto ou sem duração conhecida, devolve o máximo — não faz sentido
    degradar qualidade por precaução contra um limite que não se sabe qual é.

    Medido em 03/08: a 64 kbps, 1 hora = 27,6 MB e **não cabe** nos 25 MB do
    provedor. A 58 kbps cabe. Escolher pela duração transforma "quase sempre
    funciona" em "cabe por construção", até o piso de qualidade.
    """
    if not teto_bytes or duracao <= 0:
        return BITRATE_MAX_KBPS
    kbps = int((teto_bytes * FOLGA_TETO * 8) / duracao / 1000)
    return max(BITRATE_MIN_KBPS, min(BITRATE_MAX_KBPS, kbps))


def duracao_maxima_suportada(teto_bytes: int) -> float:
    """Quantas HORAS cabem no teto, já no piso de qualidade.

    É o número que a mensagem ao consultor usa quando nem a compressão resolve:
    ela precisa saber em que tamanho dividir a gravação, e "horas" é a unidade
    que ela tem como avaliar — não megabytes, não kbps.
    """
    return (teto_bytes * FOLGA_TETO * 8) / (BITRATE_MIN_KBPS * 1000) / 3600


def converter_para_mp3(
    audio_bytes: bytes,
    *,
    filename: str = "audio",
    teto_bytes: Optional[int] = None,
) -> ConversaoResult:
    """Converte qualquer áudio legível pelo ffmpeg em mp3 mono ~64 kbps.

    Usa arquivos temporários em vez de pipes de propósito: contêiner com índice no
    fim (`.m4a`/`.mp4`, cujo *moov atom* pode estar no final) não é decodificável
    a partir de stdin, e falharia justamente nos arquivos de celular — que são a
    maioria das gravações de reunião.
    """
    origem = (filename.rsplit(".", 1)[-1].lower() if "." in filename else "") or "desconhecido"
    antes = len(audio_bytes or b"")

    if not audio_bytes:
        return ConversaoResult(None, 0, 0, origem, erro="Áudio vazio — nada a converter.")

    if not ffmpeg_disponivel():
        return ConversaoResult(
            None, antes, 0, origem,
            erro="ffmpeg não está disponível nesta instalação.",
        )

    tmpdir = tempfile.mkdtemp(prefix="regente_audio_")
    entrada = os.path.join(tmpdir, f"entrada.{origem}" if origem != "desconhecido" else "entrada")
    saida = os.path.join(tmpdir, "saida.mp3")
    try:
        with open(entrada, "wb") as fh:
            fh.write(audio_bytes)

        dur = duracao_segundos(entrada)
        kbps = bitrate_para_caber(dur, teto_bytes)

        cmd = [
            "ffmpeg", "-nostdin", "-y",
            "-i", entrada,
            "-vn",                      # descarta vídeo (gravação de reunião com tela)
            "-ac", MP3_CANAIS,
            "-ar", MP3_SAMPLE_RATE,
            "-b:a", f"{kbps}k",
            "-f", "mp3",
            saida,
        ]
        proc = subprocess.run(
            cmd, capture_output=True, timeout=CONVERSAO_TIMEOUT_SEGUNDOS, check=False,
        )
        if proc.returncode != 0 or not os.path.exists(saida):
            # A última linha do stderr do ffmpeg é a causa real; o resto é banner.
            detalhe = (proc.stderr or b"").decode("utf-8", "replace").strip().splitlines()
            causa = detalhe[-1] if detalhe else f"código {proc.returncode}"
            logger.warning("audio_convert: ffmpeg falhou em '%s': %s", filename, causa)
            return ConversaoResult(
                None, antes, 0, origem,
                erro=f"Não foi possível converter o áudio ({causa}).",
            )

        with open(saida, "rb") as fh:
            convertido = fh.read()

        depois = len(convertido)
        if not depois:
            return ConversaoResult(
                None, antes, 0, origem,
                erro="A conversão produziu um arquivo vazio.",
            )

        logger.info(
            "audio_convert: '%s' %s %.1f MB → mp3 %dk mono %.1f MB (−%.0f%%, %.0fs)",
            filename, origem, antes / 1024 / 1024, kbps, depois / 1024 / 1024,
            (1 - depois / antes) * 100, dur,
        )
        return ConversaoResult(
            convertido, antes, depois, origem,
            bitrate_kbps=kbps, duracao_segundos=dur,
        )

    except subprocess.TimeoutExpired:
        logger.warning("audio_convert: ffmpeg estourou o tempo em '%s'", filename)
        return ConversaoResult(
            None, antes, 0, origem,
            erro="A conversão do áudio demorou demais e foi interrompida.",
        )
    except Exception as exc:  # noqa: BLE001 — conversão é meio, não fim
        logger.exception("audio_convert: erro inesperado em '%s'", filename)
        return ConversaoResult(
            None, antes, 0, origem, erro=f"Erro inesperado ao converter o áudio: {exc}",
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
