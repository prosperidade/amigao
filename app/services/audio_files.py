"""
audio_files — detecção e roteamento de arquivos de ÁUDIO (dívida #103).

Contexto: a consultora sobe a gravação da reunião com o cliente achando que o
sistema ouve. Até aqui o arquivo era guardado e mais nada — `IntakeDraft.audio_url`
era gravado e não lido por serviço algum, e a menção a Whisper em
`app/schemas/intake.py` era comentário, não código.

A reunião é **fonte primária** do caso (o que o cliente contou, o que prometeu
enviar, o que foi combinado). Por isso a modelagem escolhida (ADR-060) é: o áudio
é um **documento cujo texto é a transcrição**. Ele não ganha pipeline paralelo —
entra no mesmo `Document`, com o mesmo `ocr_status`, e o texto pousa no mesmo
`Document.extracted_text` que o diagnóstico já lê.

Este módulo só **detecta e roteia**, espelhando `geo_files.is_geospatial`: a
decisão "este arquivo entra em qual pipeline de leitura?" mora num lugar só e é
consultada pelas três portas de upload (documento do caso, rascunho de intake e
extração em lote). Quem transcreve é `app/services/transcricao_audio.py`; quem
orquestra (storage, cache, AIJob, estado na tela) é `app/workers/audio_tasks.py`.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# document_type canônico do áudio de reunião/entrevista. Já era o valor emitido
# pelo `DocumentUploadZone` e pelo wizard de intake — aqui ele vira constante
# para as três portas concordarem.
AUDIO_DOCUMENT_TYPE = "audio_entrevista"

# Rótulo de ORIGEM que viaja com a transcrição (decisão 3b — default conservador:
# o áudio entra como documento normal do caso, mas quem lê sabe de onde o texto
# veio). Prefixado ao texto transcrito, então aparece de graça em toda superfície
# que já mostra `extracted_text` (diagnóstico, busca, fonte clicável).
TRANSCRICAO_ORIGEM_LABEL = "TRANSCRIÇÃO DE ÁUDIO — REUNIÃO"

# Extensões de áudio/vídeo-com-fala reconhecidas no upload. Detectar é mais amplo
# que conseguir transcrever de propósito: um `.amr` de gravador antigo É áudio, e
# o consultor merece a mensagem "formato não suportado pela transcrição" em vez do
# silêncio de um arquivo que ninguém roteou.
AUDIO_EXTENSIONS: frozenset[str] = frozenset({
    "mp3", "m4a", "wav", "ogg", "oga", "opus", "webm", "flac", "aac",
    "mpga", "mpeg", "mp4", "amr", "wma", "3gp", "aiff", "caf",
})

# Subconjunto que o provedor de transcrição aceita (Whisper/OpenAI). Fora daqui a
# task falha com motivo legível ANTES de gastar a chamada.
TRANSCRIBABLE_EXTENSIONS: frozenset[str] = frozenset({
    "mp3", "m4a", "wav", "ogg", "oga", "webm", "flac", "mpga", "mpeg", "mp4",
})

# MIME types de áudio conhecidos. Na prática o navegador manda o MIME certo para
# áudio (diferente do caso geoespacial, onde vinha `application/octet-stream`),
# mas a detecção por extensão continua sendo a fonte primária.
AUDIO_MIME_PREFIXES: tuple[str, ...] = ("audio/",)
AUDIO_MIME_TYPES: frozenset[str] = frozenset({
    "video/mp4",     # gravação de reunião com faixa de vídeo — a fala está lá
    "video/webm",
    "application/ogg",
})


def extension_of(filename: Optional[str]) -> str:
    """Extensão normalizada (minúscula, sem ponto). '' quando não há extensão."""
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower().strip()


def is_audio(
    filename: Optional[str],
    mime_type: Optional[str] = None,
    document_type: Optional[str] = None,
) -> bool:
    """True se o arquivo é áudio pela extensão, pelo MIME **ou** pelo tipo declarado.

    O `document_type` entra na conta porque as duas portas de upload já declaram
    `audio_entrevista` explicitamente; um arquivo assim marcado é áudio mesmo que
    chegue sem extensão reconhecível (upload de app de gravação, nome tipo
    `REC0001`). O contrário não vale: nome de arquivo sozinho não prova nada —
    "reuniao.pdf" não é áudio.
    """
    if (document_type or "").strip() == AUDIO_DOCUMENT_TYPE:
        return True

    mime = (mime_type or "").strip().lower()
    if mime.startswith(AUDIO_MIME_PREFIXES) or mime in AUDIO_MIME_TYPES:
        return True

    return extension_of(filename) in AUDIO_EXTENSIONS


def formato_suportado(filename: Optional[str], mime_type: Optional[str] = None) -> bool:
    """True quando o formato é aceito pelo provedor de transcrição.

    Arquivo sem extensão mas com MIME de áudio é tratado como suportado — o
    provedor decide; falhar aqui seria adivinhar contra o consultor.
    """
    ext = extension_of(filename)
    if ext:
        return ext in TRANSCRIBABLE_EXTENSIONS
    return (mime_type or "").strip().lower().startswith(AUDIO_MIME_PREFIXES)


def motivo_formato_nao_suportado(filename: Optional[str]) -> str:
    """Mensagem legível (sem stack técnico) para formato de áudio não transcritível."""
    ext = extension_of(filename) or "sem extensão"
    aceitos = ", ".join(sorted(TRANSCRIBABLE_EXTENSIONS))
    return (
        f"Formato de áudio não suportado pela transcrição ({ext}). "
        f"Converta para um destes e reenvie: {aceitos}."
    )


def marcar_origem(texto: str, *, nome_arquivo: Optional[str] = None) -> str:
    """Prefixa a transcrição com o rótulo de ORIGEM.

    Princípio 11 (nenhuma afirmação sem fonte) aplicado ao texto bruto: quando o
    diagnóstico citar um trecho desta transcrição, o LLM e o consultor enxergam
    que aquilo foi **dito numa reunião**, não escrito num documento oficial. Peso
    probatório diferente, e a tela não precisa saber disso — vem no próprio texto.
    """
    texto = (texto or "").strip()
    if not texto:
        return ""
    cabecalho = f"[{TRANSCRICAO_ORIGEM_LABEL}"
    if nome_arquivo:
        cabecalho += f" · arquivo: {nome_arquivo}"
    cabecalho += "]"
    return f"{cabecalho}\n\n{texto}"
