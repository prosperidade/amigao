"""Fatiamento da matrícula por ato registral, antes do extrator (ADR-077, dívida #271).

Motivo medido em produção (22–23/09/2026): a matrícula 3.181 (doc 547, 82.117
caracteres) ia ao extrator em duas fatias de ~45 mil caracteres. Cada uma pedia
milhares de tokens de SAÍDA; o Luna estourava o timeout de 30 s, o fallback
Gemini truncava em 11.996/12.000 e a repetição custava US$ 0,078 numa chamada.
A 3.313 (57 mil) fez o mesmo. O gargalo é o tamanho da resposta, e o tamanho da
resposta segue o número de atos na fatia — então a fatia passa a ser o ato.

Regras (ADR-077):

1. **O ato é a unidade.** Um ato começa no seu cabeçalho (`R-09 MAT. 3.181`,
   `AV.05 Mat.`, `R.06-`) logo depois da linha de traços que a serventia usa
   como separador, e vai até o próximo ato. Tudo antes do primeiro ato é a
   ``abertura`` (cabeçalho da certidão, descrição do imóvel, memorial). O
   encerramento da certidão fica com o último ato.
2. **Ato inteiro nunca é partido**, e atos pequenos consecutivos podem dividir
   uma chamada, até ``max_chars``.
3. **Máximos declarados** (``EXTRACTOR_ATO_MAX_CHARS``, ``EXTRACTOR_ABERTURA_MAX_CHARS``):
   a abertura tem o seu, porque o memorial gera uns 0,2 token de saída por
   caractere e o ato, de 0,9 a 1,6.
4. **Ato maior que o máximo** é cortado em fronteira estrutural — linha em
   branco, ou fim de linha terminado em ``;`` ou ``.`` —, o mais tarde possível
   antes do máximo; sem fronteira, em qualquer fim de linha; sem fim de linha,
   no máximo. **Sem sobreposição:** a identidade da observação inclui a chave
   da parte, prefixada por fatia, e sobreposição duplicaria observação. O que
   cruzar um corte vira rejeição de âncora — visível, nunca silêncio.
5. **As fatias ladrilham o texto inteiro**, sem lacuna nem sobreposição: a
   cobertura é conferível por soma.
6. **Sem ato reconhecível**, devolve ``None`` e quem chama usa o fatiamento por
   tamanho (``extraction_window.fatiar``) — declarado, não silencioso.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Cabeçalho de ato logo após a linha de traços que separa os atos na certidão.
# Menções internas ("registrada no R-10", "objeto do R-12 acima") não vêm depois
# de traços, então não abrem ato.
_ATO = re.compile(
    r"(?m)^[ \t]*-{5,}[ \t]*\r?\n[ \t]*(?P<ato>(?P<tipo>R|AV)[ \t]*[-–.][ \t]*0*(?P<num>\d{1,3}))(?!\d)"
)
# Fronteiras para cortar ato grande, da mais forte para a mais fraca.
_FRONTEIRA_FORTE = re.compile(r"(?:\n[ \t]*\n|[;.][ \t]*\n)")
_FIM_DE_LINHA = re.compile(r"\n")


@dataclass(frozen=True)
class FatiaAto:
    """Um pedaço do documento, onde ele está e qual ato (ou atos) ele cobre."""

    indice: int
    inicio: int
    fim: int
    atos: tuple[str, ...]
    parte: int = 1
    partes: int = 1

    @property
    def rotulo(self) -> str:
        nome = "+".join(self.atos)
        if self.partes > 1:
            nome += f"#{self.parte}/{self.partes}"
        return f"{nome}[{self.inicio}:{self.fim}]"

    @property
    def tamanho(self) -> int:
        return self.fim - self.inicio


def localizar_atos(texto: str) -> list[tuple[str, int, int]]:
    """``[(rótulo, início, fim)]`` cobrindo o texto inteiro, abertura incluída."""
    marcas = [(f"{m['tipo']}-{int(m['num']):02d}", m.start("ato")) for m in _ATO.finditer(texto)]
    if not marcas:
        return []
    blocos = []
    if marcas[0][1] > 0:
        blocos.append(("abertura", 0, marcas[0][1]))
    for i, (rotulo, inicio) in enumerate(marcas):
        fim = marcas[i + 1][1] if i + 1 < len(marcas) else len(texto)
        blocos.append((rotulo, inicio, fim))
    return blocos


def _cortar(texto: str, inicio: int, fim: int, max_chars: int) -> list[tuple[int, int]]:
    """Corta [inicio, fim) em pedaços de até ``max_chars``, em fronteira estrutural."""
    pedacos = []
    atual = inicio
    while fim - atual > max_chars:
        limite = atual + max_chars
        janela = texto[atual:limite]
        corte = None
        for padrao in (_FRONTEIRA_FORTE, _FIM_DE_LINHA):
            ultimas = [m.end() for m in padrao.finditer(janela)]
            # Metade do máximo no mínimo: corte cedo demais multiplica chamadas.
            ultimas = [p for p in ultimas if p >= max_chars // 2]
            if ultimas:
                corte = atual + ultimas[-1]
                break
        if corte is None:
            corte = limite
        pedacos.append((atual, corte))
        atual = corte
    pedacos.append((atual, fim))
    return pedacos


def fatiar_por_ato(texto: str, *, max_chars: int, max_chars_abertura: int | None = None) -> list[FatiaAto] | None:
    """Fatias por ato registral, ou ``None`` quando o texto não tem ato reconhecível.

    ``max_chars_abertura`` vale só para a abertura (memorial descritivo), que gera
    muito menos saída por caractere que um ato; sem ele, vale ``max_chars``.
    """
    max_chars_abertura = max_chars_abertura or max_chars
    if max_chars < 1 or max_chars_abertura < 1:
        raise ValueError("max_chars precisa ser positivo")
    blocos = localizar_atos(texto)
    if not blocos:
        return None

    fatias: list[FatiaAto] = []
    grupo: list[tuple[str, int, int]] = []

    def fechar_grupo():
        if grupo:
            fatias.append(FatiaAto(len(fatias), grupo[0][1], grupo[-1][2], tuple(r for r, _, _ in grupo)))
            grupo.clear()

    for rotulo, inicio, fim in blocos:
        limite = max_chars_abertura if rotulo == "abertura" else max_chars
        if fim - inicio > limite:
            fechar_grupo()
            pedacos = _cortar(texto, inicio, fim, limite)
            for n, (a, b) in enumerate(pedacos, start=1):
                fatias.append(FatiaAto(len(fatias), a, b, (rotulo,), parte=n, partes=len(pedacos)))
            continue
        if grupo and fim - grupo[0][1] > max_chars:
            fechar_grupo()
        grupo.append((rotulo, inicio, fim))
    fechar_grupo()
    return fatias
