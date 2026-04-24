"""
scripts/inspect_legislation_pdfs.py — utilitário one-shot da Sprint 0.

Varre `legislacao/` e tenta inferir, via primeira(s) página(s) de cada PDF:
  - título
  - identifier (Lei X/YYYY, IN MMA Y/YYYY, etc.)
  - scope (federal / estadual)
  - source_type (lei, decreto, resolucao, instrucao_normativa, portaria, nota_tecnica, manual)
  - agency (MMA, IBAMA, SEMAD, CEMAm, ...)
  - UF (GO, MT, ...)
  - effective_date

Gera um JSON em `ops/legislation_metadata.json` com a lista curada para
confirmação humana antes de rodar `ingest_legislation.py` em massa.

Uso:
    python scripts/inspect_legislation_pdfs.py [--dir legislacao]
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger("inspect")


# ---------------------------------------------------------------------------
# Extração por regex
# ---------------------------------------------------------------------------

_MONTHS_PT = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
    "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}

_SOURCE_TYPE_PATTERNS = [
    (re.compile(r"\binstru[çc][aã]o\s+normativa\b", re.I), "instrucao_normativa"),
    (re.compile(r"\bresolu[çc][aã]o\b", re.I), "resolucao"),
    (re.compile(r"\bportaria\b", re.I), "portaria"),
    (re.compile(r"\bnota\s+t[eé]cnica\b", re.I), "nota_tecnica"),
    (re.compile(r"\bdecreto\b", re.I), "decreto"),
    (re.compile(r"\blei\s+complementar\b", re.I), "lei"),
    (re.compile(r"\blei\b", re.I), "lei"),
    (re.compile(r"\bmanual\b", re.I), "manual"),
]

_AGENCY_PATTERNS = [
    (re.compile(r"\bMINIST[EÉ]RIO\s+DO\s+MEIO\s+AMBIENTE\b", re.I), "MMA"),
    (re.compile(r"\bIBAMA\b", re.I), "IBAMA"),
    (re.compile(r"\bICMBIO\b", re.I), "ICMBio"),
    (re.compile(r"\bSEMAD[- ]?GO\b", re.I), "SEMAD-GO"),
    (re.compile(r"\bSEMAD\b", re.I), "SEMAD"),
    (re.compile(r"\bSEMA[- ]?MT\b", re.I), "SEMA-MT"),
    (re.compile(r"\bSEMA[- ]?MS\b", re.I), "SEMA-MS"),
    (re.compile(r"\bSEMA\b", re.I), "SEMA"),
    (re.compile(r"\bCEMA[Mm]\b"), "CEMAm"),
    (re.compile(r"\bCONAMA\b"), "CONAMA"),
    (re.compile(r"\bANA\b"), "ANA"),
]

# "Lei nº 12.651, de 25 de maio de 2012" / "INSTRUÇÃO NORMATIVA No 2/MMA, DE 06 DE MAIO DE 2014"
_IDENTIFIER_RE = re.compile(
    r"(lei(?:\s+complementar)?|decreto|instru[çc][aã]o\s+normativa|resolu[çc][aã]o|portaria|nota\s+t[eé]cnica)"
    r"[\s\w/]*?"
    r"(?:n[oº\.]*\s*)?"
    r"([\d\.]+(?:/\s*[A-Z]+)?(?:/\d{2,4})?)",
    re.I,
)

# "de 06 de maio de 2014"
_DATE_PT_RE = re.compile(
    r"(\d{1,2})\s+de\s+(janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+(\d{4})",
    re.I,
)

_UF_RE = re.compile(
    r"\b(ESTADO\s+DE\s+|GOVERNO\s+DO\s+ESTADO\s+DE\s+|SECRETARIA\s+DE\s+ESTADO\s+DO\s+MEIO\s+AMBIENTE\s+DE\s+)"
    r"(GOI[AÁ]S|MATO\s+GROSSO|MATO\s+GROSSO\s+DO\s+SUL|TOCANTINS|MINAS\s+GERAIS|S[AÃ]O\s+PAULO|PARAN[AÁ]|BAHIA)",
    re.I,
)

_UF_MAP = {
    "goiás": "GO", "goias": "GO",
    "mato grosso": "MT",
    "mato grosso do sul": "MS",
    "tocantins": "TO",
    "minas gerais": "MG",
    "são paulo": "SP", "sao paulo": "SP",
    "paraná": "PR", "parana": "PR",
    "bahia": "BA",
}


def _infer_source_type(text: str) -> str | None:
    # "manual" só vence se nenhum dos outros bateu (tende a ser ambíguo)
    for pattern, tag in _SOURCE_TYPE_PATTERNS[:-1]:
        if pattern.search(text):
            return tag
    if _SOURCE_TYPE_PATTERNS[-1][0].search(text):
        return "manual"
    return None


def _infer_agency(text: str) -> str | None:
    for pattern, agency in _AGENCY_PATTERNS:
        if pattern.search(text):
            return agency
    return None


def _infer_uf(text: str) -> str | None:
    m = _UF_RE.search(text)
    if m:
        raw = m.group(2).lower().replace("  ", " ").strip()
        return _UF_MAP.get(raw)
    # Também aceita "SEMAD-GO" etc já pegos pelo agency
    for state_key, uf in _UF_MAP.items():
        if re.search(rf"\b{re.escape(uf)}\b", text[:3000]):
            return uf
    return None


def _infer_identifier(text: str) -> str | None:
    m = _IDENTIFIER_RE.search(text)
    if not m:
        return None
    kind = m.group(1).strip().lower()
    num = m.group(2).strip()
    # Limpa número: "12.651" ou "02/2014" ou "259" etc.
    num = re.sub(r"\s+", "", num)
    kind_map = {
        "lei": "Lei",
        "lei complementar": "LC",
        "decreto": "Decreto",
        "instrução normativa": "IN",
        "instrucao normativa": "IN",
        "resolução": "Res.",
        "resolucao": "Res.",
        "portaria": "Portaria",
        "nota técnica": "Nota Técnica",
        "nota tecnica": "Nota Técnica",
    }
    prefix = kind_map.get(kind, kind.title())
    return f"{prefix} {num}"


def _infer_date(text: str) -> str | None:
    m = _DATE_PT_RE.search(text)
    if not m:
        return None
    day, month_pt, year = m.groups()
    month_key = month_pt.lower().replace("ç", "c")
    month_pt_clean = month_pt.lower().replace("ç", "ç")  # preservar para lookup
    month = _MONTHS_PT.get(month_pt.lower()) or _MONTHS_PT.get(month_key)
    if not month:
        return None
    return f"{year}-{month:02d}-{int(day):02d}"


def _infer_scope(agency: str | None, uf: str | None, text: str) -> str:
    if uf:
        return "estadual"
    if agency in {"MMA", "IBAMA", "ICMBio", "CONAMA", "ANA"}:
        return "federal"
    # Heurística final: "Presidente da República", "Congresso Nacional"
    if re.search(r"\bPresidente\s+da\s+Rep[úu]blica\b|\bCongresso\s+Nacional\b", text, re.I):
        return "federal"
    return "federal"  # default


def _demand_hint(filename: str) -> list[str]:
    """Heurística simples a partir do nome do arquivo."""
    name = filename.lower()
    tags: list[str] = []
    if "car" in name or "cadastro_ambiental" in name or "cadastro ambiental" in name:
        tags.extend(["car", "retificacao_car"])
    if "licenciamento" in name:
        tags.append("licenciamento")
    if "outorga" in name or "recursos_hidricos" in name or "hidricos" in name:
        tags.append("outorga")
    if "compensacao" in name or "prad" in name:
        tags.append("compensacao")
    if "autocomposicao" in name or "desembargo" in name or "auto" in name:
        tags.append("defesa")
    if "regularizacao" in name:
        tags.append("regularizacao_fundiaria")
    if "fiscalizacao" in name:
        tags.append("defesa")
    return sorted(set(tags))


# ---------------------------------------------------------------------------
# Varredura
# ---------------------------------------------------------------------------

def inspect_pdf(path: Path, head_chars: int = 4000) -> dict:
    """Extrai as primeiras páginas e infere metadados."""
    import io

    from pypdf import PdfReader

    meta: dict = {
        "file": str(path),
        "size_bytes": path.stat().st_size,
    }
    try:
        reader = PdfReader(io.BytesIO(path.read_bytes()))
        pages_sample = []
        for i, page in enumerate(reader.pages):
            if i >= 3:  # só as 3 primeiras páginas
                break
            t = page.extract_text() or ""
            pages_sample.append(t)
        meta["num_pages"] = len(reader.pages)
    except Exception as exc:
        meta["error"] = f"pdf read failed: {exc}"
        return meta

    head = ("\n".join(pages_sample))[:head_chars]
    meta["head_preview"] = head[:400].replace("\n", " ").strip()

    agency = _infer_agency(head)
    uf = _infer_uf(head)
    source_type = _infer_source_type(head)
    identifier = _infer_identifier(head)
    effective_date = _infer_date(head)
    scope = _infer_scope(agency, uf, head)

    meta.update(
        agency=agency,
        uf=uf,
        source_type=source_type,
        identifier=identifier,
        effective_date=effective_date,
        scope=scope,
        demand_hints=_demand_hint(path.name),
    )
    return meta


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dir", type=Path, default=Path("legislacao"))
    p.add_argument("--out", type=Path, default=Path("ops/legislation_metadata.json"))
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not args.dir.exists():
        logger.error("Diretorio nao existe: %s", args.dir)
        return 1

    # Só PDFs da raiz (sem recurse — os manuais de outorga ficam em subpasta dedicada)
    pdfs = sorted(args.dir.glob("*.pdf"))
    if not pdfs:
        logger.error("Nenhum PDF encontrado em %s", args.dir)
        return 2

    results = []
    for pdf in pdfs:
        logger.info("Inspecionando %s (%.1f KB)", pdf.name, pdf.stat().st_size / 1024)
        meta = inspect_pdf(pdf)
        results.append(meta)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Metadata salvo em %s (%d arquivos)", args.out, len(results))

    # Tabela resumida no stdout
    print("\n=== RESUMO INFERIDO ===\n")
    print(f"{'arquivo':<55} {'scope':<9} {'tipo':<20} {'órgão':<8} {'UF':<3} {'identifier':<30}")
    print("-" * 140)
    for m in results:
        name = Path(m["file"]).name[:54]
        print(
            f"{name:<55} {m.get('scope','?'):<9} {m.get('source_type') or '?':<20} "
            f"{m.get('agency') or '-':<8} {m.get('uf') or '-':<3} {m.get('identifier') or '?':<30}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
