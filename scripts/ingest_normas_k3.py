"""scripts/ingest_normas_k3.py — Onda 1 da Fase 2 (gap K3 do mapa de gaps 2026-05-23).

Ingere as 9 normas citadas pela skill `diagnostico/situacao_ambiental_imovel_rural`
que estavam ausentes do `knowledge_catalog` com `identifier` próprio.

Origem dos PDFs: Andre baixou e curou em `<projeto>/normas_k3/` em 2026-05-23.
Manifesto canônico: `MANIFESTO_NORMAS.md` (raiz do projeto).

Tratamento especial:
- IN SEMAD 7/2024 está embutida no diário oficial de 10/05/2024 a partir da
  página 7. Extraímos apenas as páginas 7+ do PDF; não indexamos o diário inteiro.

Uso:
    python scripts/ingest_normas_k3.py --dry-run   # valida tudo sem persistir
    python scripts/ingest_normas_k3.py             # ingere de verdade
    python scripts/ingest_normas_k3.py --only conama  # filtra por substring no file

Após ingestão, rodar `python scripts/reindex_sync.py --only <ids>` para gerar
os chunks no `knowledge_catalog` (o que faz o `citation_evaluator` enxergar a norma).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import logging
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.ingest_legislation import (  # noqa: E402
    estimate_tokens,
    sanitize_text,
    save_preview,
)

logger = logging.getLogger("ingest_normas_k3")


# ---------------------------------------------------------------------------
# Metadata curada — espelha MANIFESTO_NORMAS.md (raiz do projeto)
# ---------------------------------------------------------------------------

CURATED: list[dict] = [
    {
        "file": "Lei Ordinaria 18.104.pdf",
        "title": "Lei GO 18.104/2013 — Política Florestal de Goiás",
        "identifier": "Lei GO 18.104/2013",
        "scope": "estadual",
        "source_type": "lei",
        "agency": "ALEGO",
        "uf": "GO",
        "effective_date": "2013-07-18",
        "demand_types": ["car", "retificacao_car", "regularizacao_fundiaria", "compensacao"],
    },
    {
        "file": "Lei Ordinaria 18.102.pdf",
        "title": "Lei GO 18.102/2013 — Infrações administrativas ambientais",
        "identifier": "Lei GO 18.102/2013",
        "scope": "estadual",
        "source_type": "lei",
        "agency": "ALEGO",
        "uf": "GO",
        "effective_date": "2013-07-18",
        "demand_types": ["defesa"],
    },
    {
        "file": "Lei Ordinaria 21.231.pdf",
        "title": "Lei GO 21.231/2022 — Compensação florestal e por danos ambientais",
        "identifier": "Lei GO 21.231/2022",
        "scope": "estadual",
        "source_type": "lei",
        "agency": "ALEGO",
        "uf": "GO",
        "effective_date": "2022-01-01",
        "demand_types": ["compensacao", "regularizacao_fundiaria"],
    },
    {
        "file": "Decreto Numerado 9.710.pdf",
        "title": "Decreto GO 9.710/2020 — Regime extraordinário de licenciamento",
        "identifier": "Decreto GO 9.710/2020",
        "scope": "estadual",
        "source_type": "decreto",
        "agency": "Casa Civil GO",
        "uf": "GO",
        "effective_date": "2020-06-30",
        "demand_types": ["licenciamento"],
    },
    {
        "file": "Instrucao Normativa 3.pdf",
        "title": "IN SEMAD 3/2025 — Procedimentos de compensação florestal e por danos (revoga IN 14/2018 e IN 7/2023)",
        "identifier": "IN SEMAD 3/2025",
        "scope": "estadual",
        "source_type": "instrucao_normativa",
        "agency": "SEMAD-GO",
        "uf": "GO",
        "effective_date": "2025-01-01",
        "demand_types": ["compensacao"],
    },
    {
        # O nome "pag.7" indica que o Andre já recortou a página 7 do diário (a IN começa ali).
        # O PDF entregue tem 1 página = página 7 do diário original. NÃO usar page_start.
        "file": "diario_oficial_2024_05_10_completo_pag.7.pdf",
        "title": "IN SEMAD 7/2024 — Análise prioritária da DAI (extraído do diário oficial 10/05/2024)",
        "identifier": "IN SEMAD 7/2024",
        "scope": "estadual",
        "source_type": "instrucao_normativa",
        "agency": "SEMAD-GO",
        "uf": "GO",
        "effective_date": "2024-05-10",
        "demand_types": ["licenciamento"],
    },
    {
        "file": "IN INCRA 131-2023.pdf",
        "title": "IN INCRA 131/2023 — Módulo/Lote de CAR em assentamento; parcelas de reforma agrária",
        "identifier": "IN INCRA 131/2023",
        "scope": "federal",
        "source_type": "instrucao_normativa",
        "agency": "INCRA",
        "uf": None,
        "effective_date": "2023-01-01",
        "demand_types": ["car", "regularizacao_fundiaria"],
    },
    {
        "file": "conama.mma428.gov.br.pdf",
        "title": "Resolução CONAMA 428/2010 — Licenciamento em UC e zona de amortecimento",
        "identifier": "Resolução CONAMA 428/2010",
        "scope": "federal",
        "source_type": "resolucao",
        "agency": "CONAMA",
        "uf": None,
        "effective_date": "2010-12-17",
        "demand_types": ["licenciamento", "defesa"],
    },
    {
        "file": "CONAMA429-02.pdf",
        "title": "Resolução CONAMA 429/2011 — Metodologia de recuperação de APP",
        "identifier": "Resolução CONAMA 429/2011",
        "scope": "federal",
        "source_type": "resolucao",
        "agency": "CONAMA",
        "uf": None,
        "effective_date": "2011-03-08",
        "demand_types": ["compensacao", "defesa"],
    },
]


# ---------------------------------------------------------------------------
# Extração de texto
# ---------------------------------------------------------------------------

_PYPDF_MIN_CHARS = 200  # abaixo disso, assume PDF escaneado e cai pro OCR


def _extract_pdf_text(pdf_path: Path, page_start: int | None = None) -> tuple[str, str]:
    """Extrai texto de PDF.

    Estratégia:
    1. pypdf (rápido, grátis) — funciona em PDFs digitais.
    2. Se pypdf entrega < 200 chars úteis, cai para `app.services.ocr_pdf.extract_text_from_pdf`
       que faz cascata pypdf → Gemini Vision → OpenAI Vision.

    `page_start` (1-indexed) só se aplica à etapa pypdf; para o fallback OCR,
    o PDF inteiro é processado pelo orquestrador upstream.

    Retorna (texto, método).
    """
    from pypdf import PdfReader  # noqa: PLC0415

    pdf_bytes = pdf_path.read_bytes()
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = reader.pages
    if page_start is not None:
        pages = pages[page_start - 1:]
    parts: list[str] = []
    for page in pages:
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text)
    text = "\n\n".join(parts)

    if len(text) >= _PYPDF_MIN_CHARS:
        return text, "pypdf"

    # Fallback OCR (PDF escaneado) — usa o pipeline já existente do projeto
    logger.info("pypdf entregou %d chars; fallback para OCR cascata...", len(text))
    from app.services.ocr_pdf import extract_text_from_pdf  # noqa: PLC0415
    result = extract_text_from_pdf(pdf_bytes)
    return result.text, result.method


# ---------------------------------------------------------------------------
# Orquestração (espelha ingest_pasta_socia.py)
# ---------------------------------------------------------------------------

def process_one(
    entry: dict,
    pasta: Path,
    preview_dir: Path,
    dry_run: bool,
) -> dict:
    pdf_path = pasta / entry["file"]
    if not pdf_path.exists():
        return {"file": entry["file"], "action": "skipped_missing", "error": "arquivo não encontrado"}

    page_start = entry.get("page_start")
    logger.info(
        "Lendo %s (%.1f MB)%s...",
        entry["file"],
        pdf_path.stat().st_size / 1024 / 1024,
        f" — só páginas {page_start}+" if page_start else "",
    )
    raw, method = _extract_pdf_text(pdf_path, page_start=page_start)
    text = sanitize_text(raw)

    if len(text) < 200:
        return {"file": entry["file"], "action": "failed_short", "chars": len(text), "method": method}

    tokens = estimate_tokens(text)
    preview_path = save_preview(entry["identifier"], text, preview_dir)

    info: dict = {
        "file": entry["file"],
        "identifier": entry["identifier"],
        "chars": len(text),
        "tokens": tokens,
        "method": method,
        "preview": str(preview_path),
    }

    if dry_run:
        info["action"] = "dry_run"
        return info

    from app.db.session import SessionLocal  # noqa: PLC0415
    from app.models.legislation import LegislationDocument  # noqa: PLC0415

    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    effective = None
    if entry.get("effective_date"):
        try:
            effective = datetime.strptime(entry["effective_date"], "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            logger.warning("effective_date inválido em %s: %r", entry["file"], entry["effective_date"])

    db = SessionLocal()
    try:
        existing = (
            db.query(LegislationDocument)
            .filter(LegislationDocument.identifier == entry["identifier"])
            .all()
        )

        for doc in existing:
            if doc.content_hash == content_hash and doc.status == "indexed":
                info["action"] = "skipped_duplicate"
                info["db_id"] = doc.id
                return info

        for doc in existing:
            if doc.status == "indexed":
                doc.status = "superseded"
                doc.revoked_at = datetime.now(UTC)

        new_doc = LegislationDocument(
            title=entry["title"],
            identifier=entry["identifier"],
            scope=entry["scope"],
            source_type=entry["source_type"],
            agency=entry.get("agency"),
            uf=entry.get("uf"),
            municipality=None,
            effective_date=effective,
            url=None,
            file_path=str(pdf_path),
            full_text=text,
            token_count=tokens,
            content_hash=content_hash,
            status="indexed",
            demand_types=entry.get("demand_types") or None,
        )
        db.add(new_doc)
        db.flush()
        db.commit()
        info["action"] = "inserted"
        info["db_id"] = new_doc.id
        return info
    finally:
        db.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--pasta", type=Path,
        default=Path(__file__).resolve().parent.parent / "normas_k3",
        help="Pasta com os 9 PDFs (default: ../normas_k3/ relativo ao worktree)",
    )
    p.add_argument("--preview-dir", type=Path, default=Path("ops/normas_k3_preview"))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only", help="Processa só o arquivo cujo nome contém esta substring")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not args.pasta.exists():
        logger.error("Pasta %s não existe.", args.pasta)
        return 1

    entries = CURATED
    if args.only:
        needle = args.only.lower()
        entries = [e for e in CURATED if needle in e["file"].lower() or needle in e["identifier"].lower()]
        if not entries:
            logger.error("Nenhum entry casou com --only %r", args.only)
            return 1

    results: list[dict] = []
    for entry in entries:
        try:
            result = process_one(entry, args.pasta, args.preview_dir, args.dry_run)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Erro processando %s", entry["file"])
            result = {"file": entry["file"], "action": "error", "error": str(exc)}
        results.append(result)
        logger.info("  → %s", result.get("action"))

    print("\n=== Resumo ===")
    for r in results:
        line = f"  {r.get('action','?'):20} | {r.get('file',''):50}"
        if r.get("chars"):
            line += f" | {r['chars']:>7} chars | {r.get('tokens',0):>6} tokens"
        if r.get("method"):
            line += f" | via {r['method']}"
        if r.get("db_id"):
            line += f" | db_id={r['db_id']}"
        if r.get("error"):
            line += f" | err={r['error']}"
        print(line)

    failed = [r for r in results if r.get("action") in {"failed_short", "error", "skipped_missing"}]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
