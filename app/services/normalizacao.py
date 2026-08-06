"""Normalizacao Unicode do texto que ENTRA no pipeline (#122).

O extrator de PDF copia o glifo composto que a fonte usa: `ﬁ` (U+FB01) e `ﬂ`
(U+FB02) chegam como UM caractere onde deveriam estar dois. Medido em 04/08:
**2.091 chunks em 19 normas** carregam ligadura.

O que a ligadura atrapalha e COMPARACAO LITERAL e busca por termo: um trecho
gravado com `ﬁns` nao casa com quem procura `fins`, nem no nosso match de
citacao nem no Ctrl+F de quem le.

**O que ela NAO faz** (medido em 05/08, corrigindo afirmacao anterior deste
mesmo modulo): ela nao mascarava a duplicacao do `content_hash`. As duplicatas
ja eram byte-identicas — 4.530 grupos antes da normalizacao, 4.529 depois. O que
as esconde e o DESENHO do hash: `_hash_chunk` inclui `source_ref`, entao dois
documentos diferentes nunca colidem, com ou sem ligadura. Ver #122 e #123.

**O lugar e a ENTRADA, nao o consumo.** Normalizar no consumo obriga cada
consumidor a lembrar, e basta um esquecer para a comparacao mentir de novo.
Aqui o texto entra normalizado uma vez, e todo mundo depois compara maca com
maca.

## Por que NAO usamos NFKC

Foi a primeira escolha, e MEDIR antes de escrever no corpus a derrubou. O NFKC
trata `º` (U+00BA, indicador ordinal) como equivalente de COMPATIBILIDADE de
`o` — e converte:

    Lei nº 12.651   ->  Lei no 12.651
    art. 5º, §1º    ->  art. 5o, §1o
    1ª via          ->  1a via

Em texto juridico isso e destruicao, nao normalizacao: `"Lei no 1/2021"` alem de
errado fica ambiguo com a preposicao, e toda busca por `art. 5º` deixa de casar.
Medido: o NFKC mudaria **18.362 chunks (63%)**, quase todos por causa do `º` —
nao por ligadura. Seria a #122 ao contrario: a normalizacao criada para fazer
comparacao de string funcionar passaria a QUEBRAR a comparacao que sustenta o
produto.

Por isso a troca e CIRURGICA: so as ligaduras, preservando `º`, `ª` e `§`.
"""

from __future__ import annotations

# Ligaduras latinas do bloco Alphabetic Presentation Forms (U+FB00..U+FB06).
# Trocadas UMA a UMA, de proposito: qualquer forma "esperta" de normalizacao
# (NFKC, NFKD) leva junto o `º` e o `ª`, que sao significado, nao apresentacao.
LIGADURAS: dict[str, str] = {
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "ﬅ": "st",
    "ﬆ": "st",
}

_TABELA = str.maketrans(LIGADURAS)


def normalizar(texto: str) -> str:
    """Desfaz ligaduras tipograficas. Idempotente.

    NAO toca em `º`, `ª`, `§` nem em acentuacao — ver a nota do modulo sobre o
    NFKC descartado.
    """
    if not texto:
        return texto
    return texto.translate(_TABELA)


def tem_ligadura(texto: str) -> bool:
    return any(c in LIGADURAS for c in (texto or ""))


def conta_ligaduras(texto: str) -> int:
    return sum(1 for c in (texto or "") if c in LIGADURAS)
