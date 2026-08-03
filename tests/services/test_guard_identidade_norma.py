"""A fresta do guard de identidade — número de norma é TOKEN, não substring.

O ADR-036 fechou a porta grande: similaridade responde "parece com", e a
afirmação `localizada` promete "é". O guard passou a exigir que o número da
norma aparecesse no trecho.

Só que ele exigia isso da forma errada. `_digitos()` juntava os dígitos de
`identifier + title + chunk_text` numa string única e a busca era por substring.
Para o trecho `Decreto 6.514/2008 · "Art. 18. O descumprimento..."` isso produzia
`6514200818`, e então três coisas passavam:

    "65142"  — atravessa "6514" + o "2" de 2008
    "142"    — atravessa "…14" + "20…"
    "18"     — é o número do ARTIGO, não da norma

Fresta mais estreita que o bug original, e da mesma família: fonte falsa com
aparência de rigor, numa peça que a consultora assina. Medida em 31/07.
"""

import pytest

from app.services.auto_infracao_extraction import (
    _numeros_de_norma,
    chunk_confere_com_a_norma,
)

NBSP = " "


class _Chunk:
    def __init__(self, identifier=None, title=None, chunk_text=""):
        self.identifier = identifier
        self.title = title
        self.chunk_text = chunk_text


@pytest.fixture
def chunk_6514():
    """O trecho real que revelou a fresta (Decreto 6.514/2008, art. 18)."""
    return _Chunk(
        identifier="Decreto 6.514/2008",
        title="Infrações e sanções administrativas ao meio ambiente",
        chunk_text="Art. 18. O descumprimento total ou parcial de embargo...",
    )


# --------------------------------------------------------------------------
# Os três falsos positivos medidos — todos devem REJEITAR agora
# --------------------------------------------------------------------------

@pytest.mark.parametrize("numero_falso", ["65142", "142", "18"])
def test_numero_que_atravessa_fronteira_nao_confirma(chunk_6514, numero_falso):
    assert chunk_confere_com_a_norma(chunk_6514, numero_falso, 2008) is False


def test_numero_do_artigo_nunca_identifica_a_norma(chunk_6514):
    """"Art. 18" não faz deste trecho a "norma 18" — nem com o ano batendo."""
    assert chunk_confere_com_a_norma(chunk_6514, "18", 2008) is False


# --------------------------------------------------------------------------
# O que tem de continuar aceitando
# --------------------------------------------------------------------------

def test_norma_legitima_continua_confirmando(chunk_6514):
    assert chunk_confere_com_a_norma(chunk_6514, "6.514", 2008) is True


def test_confirma_pelo_texto_quando_nao_ha_identifier():
    """O corpus nem sempre traz `identifier` — o texto do trecho basta."""
    chunk = _Chunk(chunk_text="aplica-se o Decreto 6.514, de 22 de julho de 2008")
    assert chunk_confere_com_a_norma(chunk, "6.514", 2008) is True


def test_numero_sem_digito_nao_confirma_nada(chunk_6514):
    assert chunk_confere_com_a_norma(chunk_6514, "", 2008) is False
    assert chunk_confere_com_a_norma(chunk_6514, "s/n", 2008) is False


# --------------------------------------------------------------------------
# Espaço não-quebrável na CONSULTA (a outra ponta da #96)
# --------------------------------------------------------------------------

def test_nbsp_no_separador_de_milhar_nao_impede_a_confirmacao():
    """O Planalto separa milhar e "Art." do número com U+00A0.

    O guard antigo era imune por acidente (jogava fora todo não-dígito); o novo
    compara token, então precisa tolerar o separador de propósito.
    """
    chunk = _Chunk(
        identifier=f"Decreto{NBSP}6.514/2008",
        chunk_text=f"Art.{NBSP}18.{NBSP}O descumprimento total ou parcial de embargo",
    )
    assert chunk_confere_com_a_norma(chunk, "6.514", 2008) is True
    assert chunk_confere_com_a_norma(chunk, "18", 2008) is False


# --------------------------------------------------------------------------
# Regressão do ADR-036 — a porta grande continua fechada
# --------------------------------------------------------------------------

def test_compendio_estadual_nao_confirma_lei_federal():
    """O caso que originou o ADR-036: "Art. 70 da Lei 9.605/98" foi "localizada"
    no compêndio do MT, seção "Art. 70.", por casamento de string."""
    chunk = _Chunk(
        identifier="MT-NUC04-licenciamento",
        title="MT — Compêndio Regente NUC04: Núcleo de Licenciamento Ambiental",
        chunk_text="Art. 70. O licenciamento estadual observará...",
    )
    assert chunk_confere_com_a_norma(chunk, "9.605", 1998) is False


# --------------------------------------------------------------------------
# A extração de números, isolada
# --------------------------------------------------------------------------

def test_extrai_norma_e_ignora_dispositivo():
    achados = _numeros_de_norma("Art. 18 do Decreto 6.514, de 2008; § 1º e inciso II")
    assert "6514" in achados
    assert "2008" in achados
    assert "18" not in achados, "número de artigo não é número de norma"
    assert "1" not in achados, "número de parágrafo não é número de norma"


def test_nao_inventa_numero_atravessando_fronteira():
    achados = _numeros_de_norma("Decreto 6.514/2008")
    assert achados == {"6514", "2008"}
    assert "65142" not in achados
