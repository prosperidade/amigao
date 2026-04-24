"""
scripts/ingest_federais_canonicos.py — Sprint 0 / 2º round

Baixa e ingere os diplomas federais canônicos que faltam na pasta da sócia.
Usa httpx + BeautifulSoup do script `ingest_legislation.py`.

Lista curada (2026-04-23, confirmada):
  - Lei 12.651/2012 (Código Florestal)
  - Lei 9.605/1998 (Crimes Ambientais)
  - Lei 9.985/2000 (SNUC)
  - Lei 6.938/1981 (PNMA)
  - LC 140/2011 (competências)
  - Res. CONAMA 001/1986 (EIA/RIMA)
  - Res. CONAMA 237/1997 (Licenciamento)
  - Res. CONAMA 369/2006 (APP)
  - Decreto 7.830/2012 (SICAR)
  - Decreto 8.235/2014 (PRA)

Uso:
    python scripts/ingest_federais_canonicos.py --dry-run
    python scripts/ingest_federais_canonicos.py --only 12.651
    python scripts/ingest_federais_canonicos.py
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.ingest_legislation import (  # noqa: E402
    estimate_tokens,
    load_from_url,
    sanitize_text,
    save_preview,
)

logger = logging.getLogger("ingest_federais")


CURATED_FEDERAIS: list[dict] = [
    {
        "url": "https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2012/lei/l12651.htm",
        "title": "Código Florestal (Lei 12.651/2012)",
        "identifier": "Lei 12.651/2012",
        "source_type": "lei",
        "agency": "Congresso Nacional",
        "effective_date": "2012-05-25",
        "demand_types": ["car", "retificacao_car", "compensacao", "regularizacao_fundiaria"],
    },
    {
        "url": "https://www.planalto.gov.br/ccivil_03/leis/l9605.htm",
        "title": "Lei de Crimes Ambientais (Lei 9.605/1998)",
        "identifier": "Lei 9.605/1998",
        "source_type": "lei",
        "agency": "Congresso Nacional",
        "effective_date": "1998-02-12",
        "demand_types": ["defesa"],
    },
    {
        "url": "https://www.planalto.gov.br/ccivil_03/leis/l9985.htm",
        "title": "Sistema Nacional de Unidades de Conservação — SNUC (Lei 9.985/2000)",
        "identifier": "Lei 9.985/2000",
        "source_type": "lei",
        "agency": "Congresso Nacional",
        "effective_date": "2000-07-18",
        "demand_types": ["licenciamento", "compensacao"],
    },
    {
        "url": "https://www.planalto.gov.br/ccivil_03/leis/l6938.htm",
        "title": "Política Nacional do Meio Ambiente (Lei 6.938/1981)",
        "identifier": "Lei 6.938/1981",
        "source_type": "lei",
        "agency": "Congresso Nacional",
        "effective_date": "1981-08-31",
        "demand_types": ["licenciamento"],
    },
    {
        "url": "https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp140.htm",
        "title": "Competências comuns em meio ambiente (LC 140/2011)",
        "identifier": "LC 140/2011",
        "source_type": "lei",
        "agency": "Congresso Nacional",
        "effective_date": "2011-12-08",
        "demand_types": ["licenciamento"],
    },
    {
        "url": "https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2012/decreto/d7830.htm",
        "title": "Regulamento do SICAR (Decreto 7.830/2012)",
        "identifier": "Decreto 7.830/2012",
        "source_type": "decreto",
        "agency": "Presidência da República",
        "effective_date": "2012-10-17",
        "demand_types": ["car", "retificacao_car"],
    },
    {
        "url": "https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2014/decreto/d8235.htm",
        "title": "Programa de Regularização Ambiental — PRA (Decreto 8.235/2014)",
        "identifier": "Decreto 8.235/2014",
        "source_type": "decreto",
        "agency": "Presidência da República",
        "effective_date": "2014-05-05",
        "demand_types": ["car", "retificacao_car", "compensacao"],
    },
    # CONAMA — o portal Sisconama serve múltiplos IDs com conteúdo desalinhado.
    # Validação 2026-04-23: apenas id=23 retorna CONAMA 001/1986 corretamente;
    # id=745 retornou texto da 001 (não 237); id=489 retornou texto da 372 (não 369).
    # Ver TODO ingest_federais_canonicos.py:CONAMA_TODO para URLs corretas.
    {
        "url": "https://conama.mma.gov.br/?option=com_sisconama&task=arquivo.download&id=23",
        "title": "Resolução CONAMA 001/1986 — EIA/RIMA",
        "identifier": "Res. CONAMA 001/1986",
        "source_type": "resolucao",
        "agency": "CONAMA",
        "effective_date": "1986-01-23",
        "demand_types": ["licenciamento"],
        # Palavra-chave que precisa aparecer no texto para confirmar que bateu com o diploma certo
        "validation_keyword": "Resolução CONAMA nº 1",
    },
    # CONAMA_TODO — próximo round (URLs verificadas):
    #   Res. CONAMA 237/1997 (licenciamento) — achar URL correta no MMA/in.gov.br
    #   Res. CONAMA 369/2006 (APP) — achar URL correta no MMA/in.gov.br
]


def process_one(entry: dict, preview_dir: Path, dry_run: bool) -> dict:
    import httpx

    info: dict = {
        "identifier": entry["identifier"],
        "url": entry["url"],
    }
    try:
        logger.info("Baixando %s ...", entry["identifier"])
        ctype, raw = load_from_url(entry["url"])
        info["content_type"] = ctype
    except httpx.HTTPError as exc:
        info["action"] = "failed_download"
        info["error"] = str(exc)
        return info

    text = sanitize_text(raw)
    if len(text) < 500:
        info["action"] = "failed_short"
        info["chars"] = len(text)
        return info

    # Validação de conteúdo: se passou keyword, verificar que aparece no texto
    keyword = entry.get("validation_keyword")
    if keyword and keyword.lower() not in text.lower():
        info["action"] = "failed_validation"
        info["error"] = f"keyword {keyword!r} nao encontrada no texto baixado"
        info["chars"] = len(text)
        return info

    info["chars"] = len(text)
    info["tokens"] = estimate_tokens(text)
    preview_path = save_preview(entry["identifier"], text, preview_dir)
    info["preview"] = str(preview_path)

    if dry_run:
        info["action"] = "dry_run"
        return info

    from app.db.session import SessionLocal  # noqa: PLC0415
    from app.models.legislation import LegislationDocument  # noqa: PLC0415

    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    effective = datetime.strptime(entry["effective_date"], "%Y-%m-%d").replace(tzinfo=UTC)

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
            scope="federal",
            source_type=entry["source_type"],
            agency=entry.get("agency"),
            uf=None,
            municipality=None,
            effective_date=effective,
            url=entry["url"],
            file_path=None,
            full_text=text,
            token_count=info["tokens"],
            content_hash=content_hash,
            status="indexed",
            demand_types=entry["demand_types"],
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
    p.add_argument("--preview-dir", type=Path, default=Path("ops/legislation_preview"))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only", help="Substring do identifier (ex: 12.651)")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    entries = CURATED_FEDERAIS
    if args.only:
        entries = [e for e in entries if args.only.lower() in e["identifier"].lower()]

    results = []
    for entry in entries:
        try:
            r = process_one(entry, args.preview_dir, args.dry_run)
        except Exception as exc:
            logger.exception("Falha ao processar %s", entry["identifier"])
            r = {"identifier": entry["identifier"], "action": "failed_exception", "error": str(exc)}
        results.append(r)
        logger.info(
            "→ %s | action=%s chars=%s tokens=%s db_id=%s",
            r.get("identifier"), r.get("action"), r.get("chars"), r.get("tokens"), r.get("db_id"),
        )

    print("\n=== RESUMO FEDERAIS ===")
    summary: dict[str, int] = {}
    total_tokens = 0
    for r in results:
        summary[r["action"]] = summary.get(r["action"], 0) + 1
        total_tokens += r.get("tokens") or 0
    for action, count in sorted(summary.items()):
        print(f"  {action}: {count}")
    print(f"  total_tokens: {total_tokens:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
