"""audio_files — reconhecimento e roteamento de áudio (dívida #103 · ADR-060).

O que estes testes protegem: a decisão "este arquivo entra em qual pipeline de
leitura?". Errar para MENOS devolve o silêncio que a dívida #103 descreve (o
arquivo chega, ninguém lê); errar para MAIS manda PDF para a transcrição.
"""

from __future__ import annotations

import pytest

from app.services.audio_files import (
    AUDIO_DOCUMENT_TYPE,
    TRANSCRICAO_ORIGEM_LABEL,
    formato_suportado,
    is_audio,
    marcar_origem,
    motivo_formato_nao_suportado,
)


@pytest.mark.parametrize(
    "filename",
    ["reuniao.mp3", "REUNIAO.M4A", "conversa.ogg", "gravacao.wav", "call.webm"],
)
def test_reconhece_audio_por_extensao(filename):
    assert is_audio(filename) is True


@pytest.mark.parametrize(
    "mime",
    ["audio/mpeg", "audio/mp4", "audio/x-m4a", "audio/ogg", "video/mp4"],
)
def test_reconhece_audio_por_mime(mime):
    # Nome sem extensão reconhecível — quem decide é o MIME.
    assert is_audio("REC0001", mime) is True


def test_reconhece_audio_pelo_tipo_declarado_mesmo_sem_extensao():
    """As duas portas de upload já declaram `audio_entrevista`.

    Gravador de celular exporta arquivo com nome tipo `REC0001` sem extensão; o
    tipo declarado pelo consultor é prova suficiente.
    """
    assert is_audio("REC0001", None, AUDIO_DOCUMENT_TYPE) is True


@pytest.mark.parametrize(
    "filename,mime",
    [
        ("matricula.pdf", "application/pdf"),
        ("mapa.kml", "application/vnd.google-earth.kml+xml"),
        ("relatorio.docx", None),
        # O NOME não prova nada: um "reuniao.pdf" é PDF.
        ("reuniao.pdf", "application/pdf"),
    ],
)
def test_nao_confunde_documento_com_audio(filename, mime):
    assert is_audio(filename, mime) is False


def test_amr_e_audio_mas_nao_e_transcritivel():
    """Detectar é mais amplo que conseguir transcrever, de propósito.

    Um `.amr` de gravador antigo É áudio — e o consultor merece a mensagem
    "formato não suportado" em vez do silêncio de um arquivo que ninguém roteou.
    """
    assert is_audio("gravacao.amr") is True
    assert formato_suportado("gravacao.amr") is False
    motivo = motivo_formato_nao_suportado("gravacao.amr")
    assert "amr" in motivo
    assert "mp3" in motivo  # diz o que fazer, não só o que deu errado


def test_marcar_origem_prefixa_a_transcricao():
    texto = marcar_origem("Bom dia, o CAR está pendente.", nome_arquivo="reuniao.m4a")
    assert texto.startswith(f"[{TRANSCRICAO_ORIGEM_LABEL}")
    assert "reuniao.m4a" in texto
    assert "Bom dia, o CAR está pendente." in texto


def test_marcar_origem_de_texto_vazio_nao_inventa_cabecalho():
    """Transcrição vazia não pode virar um documento que só tem carimbo."""
    assert marcar_origem("") == ""
    assert marcar_origem("   ") == ""
