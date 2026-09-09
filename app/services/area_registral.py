"""Notação registral de área — `hectares,ares.centiares` (ADR-064, contenção 3).

Motivador REAL, medido na confirmação da entrada de 09/09 (ELODI, docs 547/548):

    "com área de 926,36.54ha(novecentos e vinte e seis hectares, trinta e seis
     ares e cinquenta e quatro centiares)"

O OCR foi FIEL: o documento diz `926,36.54`. Não é erro de leitura — é a notação
registral antiga em que a vírgula separa hectares de ares e o ponto separa ares
de centiares. O valor real é **926,3654 ha**.

O que o sistema fazia: `_normalize_number_str` resolve separadores pelo ÚLTIMO
separador presente ("o mais à direita é o decimal"). Em `926,36.54` o último é o
ponto ⇒ a vírgula vira milhar ⇒ **92.636,54 ha**, cem vezes o real. E
`check_format` aprovava, porque 92.636,54 é um número positivo plausível. A
matriz compararia o CAR (2.180,8267 ha) contra uma soma de matrículas de
165.711,73 ha.

Por que REGRA e não LLM (ADR-064): a decodificação é determinística e o próprio
documento traz o extenso que a confirma, a duas linhas do número. Pedir isso ao
modelo é trocar uma conversão exata por uma que varia entre execuções — a mesma
areia que a contenção da entrada existe para tirar do caminho.

Este módulo é PURO (regex + texto) e não importa nada do domínio: é dependência
de `inconsistency_matrix.parse_area_ha`, a porta única de área, e não pode
fechar ciclo com ela.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# A notação
# ---------------------------------------------------------------------------

# `<hectares>,<ares 2 dígitos>.<centiares 2 dígitos>` — ex.: "926,36.54",
# "725,46.63", "1.234,05.09". A parte de hectares aceita ponto de milhar.
#
# Por que EXATAMENTE 2 dígitos em cada lado: é o que separa a notação registral
# de um número comum. `2.180,8267` (vírgula + 4 casas, sem ponto depois) e
# `212,3553` não casam — e devem continuar não casando, senão a regra
# reescreveria áreas corretas. `1,234.56` (milhar à americana) tem 3 dígitos
# após a vírgula e também não casa.
_NOTACAO_RE = re.compile(r"^(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})\.(\d{2})$")


@dataclass(frozen=True)
class AreaRegistral:
    """Uma área decodificada da notação registral, com o método usado."""

    bruto: str
    """O literal como saiu do documento — NUNCA reescrito."""

    valor_ha: float
    """O valor em hectares depois da regra."""

    hectares: int
    ares: int
    centiares: int

    metodo: str
    """`notacao_ha_a_ca` ou `notacao_ha_a_ca+extenso` (quando o extenso confirma)."""

    extenso_ha: Optional[float] = None
    """Valor lido do extenso no entorno, quando havia extenso."""

    extenso_confere: Optional[bool] = None
    """True/False quando houve extenso; None quando não havia o que conferir."""


def _limpar(bruto: object) -> str:
    """Deixa só dígitos e separadores — 'ha', espaços e unidade saem."""
    s = str(bruto).strip().lower()
    return re.sub(r"[^0-9.,]", "", s)


def parece_notacao_registral(bruto: object) -> bool:
    """True se o literal está na notação `hectares,ares.centiares`."""
    return bool(_NOTACAO_RE.fullmatch(_limpar(bruto)))


def normalizar_area_registral(
    bruto: object, entorno: Optional[str] = None
) -> Optional[AreaRegistral]:
    """Decodifica `N,NN.NN` → hectares. None quando o literal não é a notação.

    ``entorno`` (opcional) é o trecho do documento ao redor do número — quando
    ele traz o extenso ("novecentos e vinte e seis hectares, trinta e seis ares
    e cinquenta e quatro centiares"), o extenso é usado como VERIFICAÇÃO: bate
    ⇒ método vira `notacao_ha_a_ca+extenso`; não bate ⇒ `extenso_confere=False`
    e quem chama rebaixa a confiança. O extenso nunca SUBSTITUI a regra — ele
    confirma ou levanta a mão.
    """
    m = _NOTACAO_RE.fullmatch(_limpar(bruto))
    if m is None:
        return None

    hectares = int(m.group(1).replace(".", ""))
    ares = int(m.group(2))
    centiares = int(m.group(3))
    valor = hectares + ares / 100.0 + centiares / 10000.0

    extenso_ha = parse_extenso_area(entorno) if entorno else None
    if extenso_ha is None:
        return AreaRegistral(
            bruto=str(bruto), valor_ha=valor, hectares=hectares, ares=ares,
            centiares=centiares, metodo="notacao_ha_a_ca",
        )

    confere = abs(extenso_ha - valor) < 1e-6
    return AreaRegistral(
        bruto=str(bruto), valor_ha=valor, hectares=hectares, ares=ares,
        centiares=centiares,
        metodo="notacao_ha_a_ca+extenso" if confere else "notacao_ha_a_ca",
        extenso_ha=extenso_ha, extenso_confere=confere,
    )


# ---------------------------------------------------------------------------
# O extenso — a verificação que estava a duas linhas e ninguém lia
# ---------------------------------------------------------------------------

_UNIDADES: dict[str, int] = {
    "zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4,
    "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9,
    "dez": 10, "onze": 11, "doze": 12, "treze": 13, "quatorze": 14,
    "catorze": 14, "quinze": 15, "dezesseis": 16, "dezessete": 17,
    "dezoito": 18, "dezenove": 19,
    "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60,
    "setenta": 70, "oitenta": 80, "noventa": 90,
    "cem": 100, "cento": 100, "duzentos": 200, "duzentas": 200,
    "trezentos": 300, "trezentas": 300, "quatrocentos": 400, "quatrocentas": 400,
    "quinhentos": 500, "quinhentas": 500, "seiscentos": 600, "seiscentas": 600,
    "setecentos": 700, "setecentas": 700, "oitocentos": 800, "oitocentas": 800,
    "novecentos": 900, "novecentas": 900,
}

# Rótulos de unidade que FECHAM um número por extenso.
_ROTULO_HA = {"hectare", "hectares"}
_ROTULO_ARE = {"are", "ares"}
_ROTULO_CA = {"centiare", "centiares"}


def _tokens(texto: str) -> list[str]:
    """Palavras minúsculas sem acento — 'trinta e seis' → ['trinta','e','seis']."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return re.findall(r"[a-z]+", sem_acento.lower())


def _valor_do_buffer(buffer: list[str]) -> Optional[int]:
    """Soma as palavras-número acumuladas. None se o buffer não tem número."""
    total = 0
    corrente = 0
    viu_numero = False
    for palavra in buffer:
        if palavra == "mil":
            corrente = (corrente or 1) * 1000
            total += corrente
            corrente = 0
            viu_numero = True
        elif palavra in _UNIDADES:
            corrente += _UNIDADES[palavra]
            viu_numero = True
    return (total + corrente) if viu_numero else None


def parse_extenso_area(trecho: Optional[str]) -> Optional[float]:
    """Lê 'X hectares, Y ares e Z centiares' → área em ha. None se não houver.

    Exige o rótulo de HECTARES: sem ele não há como afirmar que o extenso fala
    de área (o entorno de uma matrícula é cheio de números por extenso — valor
    de hipoteca, prazo de arrendamento, número de ordem). ``ares``/``centiares``
    são opcionais.
    """
    if not trecho:
        return None

    hectares: Optional[int] = None
    ares = 0
    centiares = 0
    buffer: list[str] = []

    for palavra in _tokens(trecho):
        if palavra in _ROTULO_HA:
            hectares = _valor_do_buffer(buffer) or 0
            buffer = []
        elif palavra in _ROTULO_CA:
            centiares = _valor_do_buffer(buffer) or 0
            buffer = []
        elif palavra in _ROTULO_ARE:
            ares = _valor_do_buffer(buffer) or 0
            buffer = []
        elif palavra in _UNIDADES or palavra == "mil":
            buffer.append(palavra)
        elif palavra == "e":
            continue
        else:
            # Palavra fora do vocabulário numérico corta a sequência: evita que
            # um número de outra frase escorregue para dentro do extenso da área.
            buffer = []

    if hectares is None:
        return None
    return hectares + ares / 100.0 + centiares / 10000.0


# ---------------------------------------------------------------------------
# Entorno do número no documento
# ---------------------------------------------------------------------------

# O extenso vem logo DEPOIS do número, entre parênteses. 240 chars cobrem o
# caso real ("...cinquenta e quatro centiares)" = 101 chars) com folga, sem
# varrer o parágrafo seguinte.
ENTORNO_CHARS = 240


def entorno_do_valor(texto: Optional[str], pos: Optional[int]) -> Optional[str]:
    """Trecho do documento a partir da posição do número, para achar o extenso."""
    if not texto or pos is None or pos < 0 or pos >= len(texto):
        return None
    return texto[pos: pos + ENTORNO_CHARS]
