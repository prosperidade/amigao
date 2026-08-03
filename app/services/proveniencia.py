"""proveniencia — de onde veio o texto de uma norma do corpus (dívida #97).

O sistema cita norma em peça que a consultora assina. "De onde veio esse texto"
precisa ter resposta, e a resposta precisa distinguir três coisas que não são a
mesma:

- **oficial deduzido**: a URL é de domínio oficial (Planalto, DOU, `.gov.br`).
  Ninguém conferiu; o domínio é que garante.
- **oficial conferido**: uma pessoa afirmou a origem. Carrega data
  (`fonte_conferida_em`) — é o que separa "alguém olhou" de "o robô deduziu".
- **não conferido**: agregador, ou origem desconhecida. Não se apresenta como
  oficial enquanto ninguém conferir.

A classificação é DERIVADA, nunca digitada documento a documento, para que não
exista documento novo sem origem: fonte não reconhecida cai num rótulo explícito
de desconhecida, jamais em branco.

Espelha o backfill da migration `b5c92fa4d7e1`. Mudou aqui, mudar lá.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# Confirmação do André em 01/08/2026: TODAS as pastas de legislação (GO, MT, MS,
# AC) vieram da Isis, de fontes oficiais estaduais. Não há material de origem
# duvidosa na base.
CURADORIA_ISIS = (
    "curadoria Isis Terra — fontes oficiais estaduais (SEMAD/Casa Civil/DOE)"
)
CONFERIDA_EM = date(2026, 8, 1)

DESCONHECIDA = "origem não identificada — conferir antes de citar"

# domínio → rótulo. Ordem importa: o mais específico primeiro.
_DOMINIOS_OFICIAIS: tuple[tuple[str, str], ...] = (
    ("planalto.gov.br", "Planalto — Presidência da República (oficial)"),
    ("in.gov.br", "DOU — Imprensa Nacional (oficial)"),
    ("conama.mma.gov.br", "CONAMA/MMA (oficial)"),
    (".gov.br", "portal .gov.br (oficial)"),
)


@dataclass(frozen=True)
class Proveniencia:
    origem: str
    oficial: bool
    conferida_em: date | None = None


def classificar_fonte(
    url: str | None = None,
    file_path: str | None = None,
) -> Proveniencia:
    """De onde veio o texto, e se a fonte é oficial.

    A ordem das perguntas é a ordem da confiança: URL oficial primeiro (o
    domínio prova), disco depois (uma pessoa afirmou), agregador em seguida
    (não prova nada), e desconhecida por último — declarada, nunca vazia.
    """
    alvo = (url or "").lower()
    if alvo:
        for agulha, rotulo in _DOMINIOS_OFICIAIS:
            if agulha in alvo:
                return Proveniencia(origem=rotulo, oficial=True)
        # URL que não é de domínio oficial: agregador. Não vira oficial só por
        # ter link — foi assim que a IN IBAMA 10/2012 entrou, e ela aguarda o
        # PDF oficial (dívida #98).
        return Proveniencia(
            origem=f"fonte não-oficial (agregador) — {url}", oficial=False
        )

    if file_path:
        return Proveniencia(
            origem=f"{CURADORIA_ISIS} [arquivo: {file_path}]",
            oficial=True,
            conferida_em=CONFERIDA_EM,
        )

    return Proveniencia(origem=DESCONHECIDA, oficial=False)
