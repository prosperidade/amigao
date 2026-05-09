"""Evaluator de citações legais — Sprint A1 (Tarefa B).

Mitigador de alucinação no ``RedatorAgent``: depois do LLM responder, este
módulo extrai todas as citações de norma do texto, cruza com o contexto
legislativo já carregado pelo agente (sem fazer nova busca RAG) e, quando
houver citação inválida, força ``requires_review=True`` no output.

Não bloqueia o output — só **marca**. A peça gerada continua sendo entregue
ao consultor; o badge de revisão obrigatória deixa explícito que tem citação
não confirmada.

Decisões da Fase 0 aplicadas:
* `CitationRef` (Tarefa C) é o tipo canônico — não há `Citation` paralelo.
* Validação só contra contexto in-memory; nenhuma chamada para
  ``knowledge_catalog.search`` aqui.
* Acórdãos STF/STJ ficam fora de escopo (regra explícita do prompt).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from app.schemas.stage_output import CitationJurisdicao, CitationKind, CitationRef

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Resultado da validação
# ---------------------------------------------------------------------------

@dataclass
class CitationValidationResult:
    """Saída do ``validate_citations``.

    Attributes:
        valid: ``True`` quando todas as citações foram confirmadas no
            contexto (ou quando não há citações no texto).
        total: número total de citações detectadas no texto.
        invalid: lista de ``CitationRef`` não confirmadas.
        coverage_ratio: fração validada (1.0 quando não há citações ou
            quando todas casaram).
    """

    valid: bool
    total: int
    invalid: list[CitationRef] = field(default_factory=list)
    coverage_ratio: float = 1.0


# ---------------------------------------------------------------------------
# Regex multi-formato (preferência por capturas mais específicas primeiro)
# ---------------------------------------------------------------------------

# Variantes do "nº": [Nn]º? · [Nn]\.?º? · [Nn][o0]?\.? · °/º · com ou sem espaço
_NUM = r"(?:n[º°ºo]?\.?\s*)?"
# Número aceitando . (12.651), - (12-651), / (001/2026), letras finais (12651-A)
_NUMBER = r"(\d+(?:[.-]\d+)*[A-Z]?)"
# 4 dígitos ANTES de 2 — re alternation é leftmost; sem isso, "2012" vira "20".
_YEAR = r"(\d{4}|\d{2})"
# Aceita "/AAAA", ", de DD de MES de AAAA" ou ", AAAA"
_MES = r"(?:janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
_DATE_OR_YEAR = (
    rf"(?:\s*[/,]\s*(?:de\s+\d{{1,2}}\s+de\s+{_MES}\s+de\s+)?{_YEAR})"
)

# Pré-prefixo opcional "art. X[, § Y[º]] da/do"
_ARTIGO_PREFIX = (
    r"(?:art(?:\.|igo)?\s*(?P<artigo>\d+[º°ºo]?(?:\s*,\s*[§]+\s*\d+[º°ºo]?)?)"
    r"\s*(?:d[ao]s?\s+)?)?"
)

_PATTERNS: list[tuple[str, re.Pattern[str], CitationKind]] = [
    # Lei Complementar — DEVE vir antes de "Lei" para não ser engolida
    (
        "lei_complementar",
        re.compile(
            rf"{_ARTIGO_PREFIX}Lei\s+Complementar\s+{_NUM}{_NUMBER}{_DATE_OR_YEAR}",
            re.IGNORECASE,
        ),
        "lei_complementar",
    ),
    # Decreto-Lei — antes de "Decreto"
    (
        "decreto_lei",
        re.compile(
            rf"{_ARTIGO_PREFIX}Decreto[\s \-]Lei\s+{_NUM}{_NUMBER}{_DATE_OR_YEAR}",
            re.IGNORECASE,
        ),
        "decreto_lei",
    ),
    (
        "decreto",
        re.compile(
            rf"{_ARTIGO_PREFIX}Decreto\s+{_NUM}{_NUMBER}{_DATE_OR_YEAR}",
            re.IGNORECASE,
        ),
        "decreto",
    ),
    (
        "lei",
        re.compile(
            rf"{_ARTIGO_PREFIX}Lei\s+{_NUM}{_NUMBER}{_DATE_OR_YEAR}",
            re.IGNORECASE,
        ),
        "lei",
    ),
    # Resolução genérica: captura a sigla — "CONAMA" vira resolucao_conama, demais vira "outro"
    (
        "resolucao_generica",
        re.compile(
            rf"{_ARTIGO_PREFIX}Resoluç[ãa]o\s+(?P<sigla>[A-Z]{{2,12}})\s+{_NUM}{_NUMBER}{_DATE_OR_YEAR}",
            re.IGNORECASE,
        ),
        "outro",
    ),
    # IN <ÓRGÃO> X/AAAA  ou  Instrução Normativa <ÓRGÃO> X/AAAA
    (
        "instrucao_normativa",
        re.compile(
            rf"{_ARTIGO_PREFIX}(?:IN|Instruç[ãa]o\s+Normativa)\s+(?P<sigla>[A-Z]{{2,12}})?\s*{_NUM}{_NUMBER}{_DATE_OR_YEAR}",
            re.IGNORECASE,
        ),
        "instrucao_normativa",
    ),
    (
        "portaria",
        re.compile(
            rf"{_ARTIGO_PREFIX}Portaria\s+(?:[A-Z]{{2,12}}\s+)?{_NUM}{_NUMBER}{_DATE_OR_YEAR}",
            re.IGNORECASE,
        ),
        "portaria",
    ),
    (
        "medida_provisoria",
        re.compile(
            rf"{_ARTIGO_PREFIX}(?:MP|Medida\s+Provis[óo]ria)\s+{_NUM}{_NUMBER}{_DATE_OR_YEAR}",
            re.IGNORECASE,
        ),
        "medida_provisoria",
    ),
]


# ---------------------------------------------------------------------------
# Helpers de normalização
# ---------------------------------------------------------------------------

def _normalize_year(year_text: str) -> int:
    """'12' → 2012; '1998' → 1998. (Heurística simples para 2 dígitos.)"""
    y = int(year_text)
    if y < 100:
        # convenção: <50 = 20xx, ≥50 = 19xx
        return 2000 + y if y < 50 else 1900 + y
    return y


def _normalize_numero(numero_text: str) -> str:
    """Mantém forma original (preserva pontos: '12.651') — caller compara depois pela versão dígito-only."""
    return numero_text.strip()


def _digits_only(numero: str) -> str:
    """Para comparação: '12.651' == '12651' == '12-651'. Letras (sufixos) preservadas."""
    return re.sub(r"[^0-9A-Za-z]", "", numero).upper()


def _key(kind: str, numero: str, ano: int) -> tuple[str, str, int]:
    return (kind, _digits_only(numero), ano)


# ---------------------------------------------------------------------------
# extract_citations
# ---------------------------------------------------------------------------

def extract_citations(text: str) -> list[CitationRef]:
    """Varre o texto e devolve as citações encontradas, sem duplicatas.

    Regras:
    * ordem dos patterns importa — Lei Complementar / Decreto-Lei vêm antes
      dos seus "primos" mais curtos para evitar match parcial.
    * intervalos já casados são removidos do texto antes do próximo pattern,
      garantindo que "Lei Complementar 140/2011" não seja recapturada como
      "Lei 140/2011".
    * deduplicação por ``(kind, numero_normalizado, ano)``.
    """
    if not text:
        return []

    citations: list[CitationRef] = []
    seen: set[tuple[str, str, int]] = set()
    consumed = bytearray(b"\x00" * len(text))  # marcador de offsets já consumidos

    def _is_overlapping(span: tuple[int, int]) -> bool:
        start, end = span
        return any(consumed[i] for i in range(start, end))

    def _mark(span: tuple[int, int]) -> None:
        start, end = span
        for i in range(start, end):
            consumed[i] = 1

    for _name, pattern, default_kind in _PATTERNS:
        for match in pattern.finditer(text):
            if _is_overlapping(match.span()):
                continue

            num_text = match.group(match.lastindex)
            ano_text = match.group(match.lastindex - 1) if match.lastindex >= 2 else ""
            # ajustar quando há groups nomeados (sigla, artigo)
            # ano e número vêm sempre como os 2 últimos grupos não-nomeados
            groups = match.groups()
            # filtra apenas grupos posicionais (descartando "artigo" e "sigla" se quisermos)
            # Como _NUMBER e _YEAR são os últimos grupos posicionais, pegamos os 2 últimos:
            year_text = groups[-1]
            number_text = groups[-2]

            try:
                ano = _normalize_year(year_text)
            except ValueError:
                continue

            kind: CitationKind = default_kind
            artigo = match.groupdict().get("artigo")
            sigla = match.groupdict().get("sigla")

            if default_kind == "outro" and sigla and sigla.upper() == "CONAMA":
                kind = "resolucao_conama"

            citation = CitationRef(
                kind=kind,
                numero=_normalize_numero(number_text),
                ano=ano,
                raw=match.group(0).strip(),
                artigo=artigo.strip() if artigo else None,
            )
            key = _key(kind, citation.numero, ano)
            if key in seen:
                _mark(match.span())
                continue
            seen.add(key)
            citations.append(citation)
            _mark(match.span())

    return citations


# ---------------------------------------------------------------------------
# validate_citations
# ---------------------------------------------------------------------------

def _resolve_known(item: Any) -> tuple[CitationRef, int | None, CitationJurisdicao | None] | None:
    """Normaliza um elemento do legislation_context.

    Aceita (em ordem de preferência):
    * ``CitationRef`` puro
    * ``SearchResult`` do ``knowledge_catalog`` (usa ``identifier`` como base
      e populamos ``chunk_id`` + ``jurisdicao`` a partir dele).
    * ``str`` no formato livre tipo "Lei 12.651/2012" — extraímos.

    Retorna tupla (CitationRef, chunk_id, jurisdicao) ou ``None`` quando não foi possível
    interpretar o item. Nunca lança.
    """
    if isinstance(item, CitationRef):
        return item, item.chunk_id, item.jurisdicao

    text: str | None = None
    chunk_id: int | None = None
    jurisdicao: CitationJurisdicao | None = None

    # SearchResult: aceitar duck-type (precisa de identifier, id, jurisdiction opcional)
    identifier = getattr(item, "identifier", None)
    if identifier:
        text = str(identifier)
        chunk_id = getattr(item, "id", None)
        jur_raw = getattr(item, "jurisdiction", None)
        if isinstance(jur_raw, str) and jur_raw.lower() in {"federal", "estadual", "municipal", "outro"}:
            jurisdicao = jur_raw.lower()  # type: ignore[assignment]
    elif isinstance(item, str):
        text = item

    if not text:
        return None

    extracted = extract_citations(text)
    if not extracted:
        return None
    cit = extracted[0]
    return cit, chunk_id, jurisdicao


def validate_citations(
    citations: list[CitationRef],
    legislation_context: Iterable[Any],
) -> CitationValidationResult:
    """Cruza citações detectadas no texto contra o contexto legislativo carregado.

    O ``legislation_context`` aceita lista heterogênea de:
    * ``CitationRef``
    * ``SearchResult`` (``knowledge_catalog``)
    * strings tipo ``"Lei 12.651/2012"``

    Quando houver match, o ``CitationRef`` original é mutado (campos
    ``chunk_id`` e ``jurisdicao`` populados a partir do contexto). Citações
    sem match vão para ``invalid``.
    """
    total = len(citations)
    if total == 0:
        return CitationValidationResult(valid=True, total=0, invalid=[], coverage_ratio=1.0)

    # Indexar conhecidos por chave (kind, numero_dígito, ano)
    index: dict[tuple[str, str, int], tuple[int | None, CitationJurisdicao | None]] = {}
    for raw in legislation_context:
        resolved = _resolve_known(raw)
        if resolved is None:
            continue
        ref, chunk_id, jurisdicao = resolved
        key = _key(ref.kind, ref.numero, ref.ano)
        prev = index.get(key)
        # mantém quando já tinha info; substitui só se a nova info for mais rica
        if prev is None or (prev[0] is None and chunk_id is not None):
            index[key] = (chunk_id, jurisdicao)

    invalid: list[CitationRef] = []
    matched = 0
    enriched: list[CitationRef] = []

    for cit in citations:
        key = _key(cit.kind, cit.numero, cit.ano)
        if key in index:
            matched += 1
            chunk_id, jurisdicao = index[key]
            # Recria CitationRef preservando frozen=True não está em uso;
            # _StrictModel é Pydantic mutable, OK mutar.
            updated = cit.model_copy(update={
                "chunk_id": chunk_id if cit.chunk_id is None else cit.chunk_id,
                "jurisdicao": jurisdicao if cit.jurisdicao is None else cit.jurisdicao,
            })
            enriched.append(updated)
        else:
            invalid.append(cit)
            enriched.append(cit)

    # Mutação no lugar — devolvemos a lista atualizada via citations[:]
    citations[:] = enriched

    coverage = matched / total if total else 1.0
    return CitationValidationResult(
        valid=len(invalid) == 0,
        total=total,
        invalid=invalid,
        coverage_ratio=coverage,
    )
