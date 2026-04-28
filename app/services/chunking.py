"""Chunking hibrido para o knowledge_catalog.

Estrategia:
1. Tenta cortar por marcadores estruturais de texto legislativo brasileiro
   ("Art. N", "CAPITULO X", "SECAO Y", "TITULO Z").
2. Se o chunk resultante exceder MAX_TOKENS, sub-divide em janelas de
   tamanho TARGET_TOKENS com OVERLAP_TOKENS de superposicao.
3. Se nenhuma marcacao for encontrada (ex: doutrina, oficio, manual),
   cai direto na janela deslizante.

Estimativa de tokens via heuristica de 4 chars/token (boa aproximacao
para portugues juridico — confirmado contra Gemini tokenizer no Sprint 0).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Marcadores estruturais. Ordem importa: do mais externo para o mais interno.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("titulo", re.compile(r"^\s*T[ÍI]TULO\s+[IVXLCDM]+", re.MULTILINE | re.IGNORECASE)),
    ("capitulo", re.compile(r"^\s*CAP[ÍI]TULO\s+[IVXLCDM]+", re.MULTILINE | re.IGNORECASE)),
    ("secao", re.compile(r"^\s*SE[ÇC][ÃA]O\s+[IVXLCDM]+", re.MULTILINE | re.IGNORECASE)),
    ("artigo", re.compile(r"^\s*Art\.\s*\d+", re.MULTILINE)),
]

TARGET_TOKENS = 800
MAX_TOKENS = 1500
OVERLAP_TOKENS = 100
_CHARS_PER_TOKEN = 4


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


@dataclass
class TextChunk:
    """Pedaco de texto resultante do chunking."""

    text: str
    section: str | None
    index: int
    tokens: int


def _split_by_pattern(text: str, pattern: re.Pattern[str]) -> list[tuple[int, str]]:
    """Quebra texto pelos matches de `pattern`. Retorna [(start_offset, slice), ...]."""
    matches = list(pattern.finditer(text))
    if not matches:
        return [(0, text)]
    out: list[tuple[int, str]] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((start, text[start:end]))
    # Conteudo antes do primeiro match — ex: ementa, preambulo.
    if matches[0].start() > 0:
        prelude = text[: matches[0].start()].strip()
        if prelude:
            out.insert(0, (0, prelude))
    return out


def _label_section(slice_text: str) -> str | None:
    """Extrai um label curto do inicio do slice (ex: 'Art. 12', 'Capitulo III')."""
    head = slice_text.lstrip()[:120]
    first_line = head.splitlines()[0] if head else ""
    return first_line.strip() or None


def _sliding_window(
    text: str,
    base_section: str | None,
    base_index: int,
) -> list[TextChunk]:
    """Janela deslizante por tokens aproximados, com overlap."""
    chunks: list[TextChunk] = []
    target_chars = TARGET_TOKENS * _CHARS_PER_TOKEN
    overlap_chars = OVERLAP_TOKENS * _CHARS_PER_TOKEN
    step = max(1, target_chars - overlap_chars)

    pos = 0
    sub_idx = 0
    while pos < len(text):
        window = text[pos : pos + target_chars]
        if not window.strip():
            break
        chunks.append(
            TextChunk(
                text=window.strip(),
                section=f"{base_section} (parte {sub_idx + 1})" if base_section else None,
                index=base_index + sub_idx,
                tokens=_approx_tokens(window),
            )
        )
        sub_idx += 1
        pos += step
    return chunks


def chunk_text(text: str) -> list[TextChunk]:
    """Aplica chunking hibrido sobre o texto. Retorna lista ordenada."""
    text = (text or "").strip()
    if not text:
        return []

    # 1. Tenta marcadores estruturais. Usa o mais granular que retorna >1 split.
    structural: list[tuple[str, str]] = []  # (section_label, text)
    for label, pattern in reversed(_PATTERNS):
        slices = _split_by_pattern(text, pattern)
        if len(slices) > 1:
            for _, slice_text in slices:
                structural.append((label, slice_text))
            break

    # 2. Se nenhum padrao quebrou — janela deslizante direta.
    if not structural:
        return _sliding_window(text, base_section=None, base_index=0)

    # 3. Para cada slice estrutural: aceita inteiro se cabe; senao sub-divide.
    chunks: list[TextChunk] = []
    next_index = 0
    for _label, slice_text in structural:
        slice_text = slice_text.strip()
        if not slice_text:
            continue
        section = _label_section(slice_text)
        tokens = _approx_tokens(slice_text)
        if tokens <= MAX_TOKENS:
            chunks.append(
                TextChunk(
                    text=slice_text,
                    section=section,
                    index=next_index,
                    tokens=tokens,
                )
            )
            next_index += 1
        else:
            sub_chunks = _sliding_window(slice_text, section, next_index)
            chunks.extend(sub_chunks)
            next_index += len(sub_chunks)

    return chunks
