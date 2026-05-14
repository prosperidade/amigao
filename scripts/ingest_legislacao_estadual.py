"""scripts/ingest_legislacao_estadual.py — ingere compêndios estaduais (MS/MT/...).

Diferente do `ingest_pasta_socia.py` (que trata cada arquivo como um diploma
individual com metadata curada), este script processa **compêndios temáticos
por UF**: cada PDF é um agregado de várias normas organizadas por núcleo
(01_Constitucional, 02_Territorial, 03_Florestal_CAR_PRA, etc.).

O nome do arquivo carrega o núcleo + tema, então a metadata é derivada
mecanicamente — não precisa CURATED manual.

Uso:
    # Dry-run para validar antes de gravar
    python scripts/ingest_legislacao_estadual.py --uf MS --pasta /app/legislacao_estadual/MS --dry-run

    # Ingestão real
    python scripts/ingest_legislacao_estadual.py --uf MS --pasta /app/legislacao_estadual/MS
    python scripts/ingest_legislacao_estadual.py --uf MT --pasta /app/legislacao_estadual/MT

    # Filtrar 1 arquivo
    python scripts/ingest_legislacao_estadual.py --uf MS --pasta /app/legislacao_estadual/MS --only Constitucional
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import re
import sys
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.ingest_legislation import (  # noqa: E402
    estimate_tokens,
    load_from_pdf_path,
    sanitize_text,
    save_preview,
)

logger = logging.getLogger("ingest_legislacao_estadual")


# Mapa de tema (slug normalizado) → (rótulo legível, demand_types).
# Cobre os núcleos do mapa Regente da sócia (MS/MT/GO seguem nomenclatura
# semelhante). Quando um tema novo aparecer, cai pro fallback genérico.
TEMA_MAP: dict[str, tuple[str, list[str]]] = {
    "constitucional":          ("Núcleo Constitucional e Institucional", ["geral"]),
    "constitucional_institucional_competencial": ("Núcleo Constitucional e Institucional", ["geral"]),
    "territorial":             ("Núcleo Territorial e Cadastro", ["car", "cadastro"]),
    "territorial_cadastro":    ("Núcleo Territorial e Cadastro", ["car", "cadastro"]),
    "florestal_car":           ("Núcleo Florestal — CAR e PRA", ["car", "prad", "reserva_legal"]),
    "florestal_car_pra":       ("Núcleo Florestal — CAR e PRA", ["car", "prad", "reserva_legal"]),
    "licenciamento":           ("Núcleo de Licenciamento Ambiental", ["licenciamento"]),
    "hidrico":                 ("Núcleo Hídrico e Outorgas", ["outorga"]),
    "hidrico_saneamento":      ("Núcleo Hídrico e Saneamento", ["outorga", "saneamento"]),
    "infracoes":               ("Núcleo de Infrações e Defesa", ["defesa", "auto_infracao"]),
    "credito":                 ("Núcleo de Crédito Rural Ambiental", ["credito_rural"]),
    "credito_pd":              ("Núcleo de Crédito Rural Ambiental", ["credito_rural"]),
    "biomas":                  ("Núcleo de Biomas e Conservação", ["biodiversidade"]),
    "fogo":                    ("Núcleo de Fogo e Queimadas", ["queimada"]),
    "fogo_queimadas":          ("Núcleo de Fogo e Queimadas", ["queimada"]),
    "fauna":                   ("Núcleo de Fauna e Biodiversidade", ["fauna"]),
    "fauna_biodiversidade":    ("Núcleo de Fauna e Biodiversidade", ["fauna"]),
    "ativos":                  ("Núcleo de Ativos de Carbono", ["carbono"]),
    "ativos_carbono":          ("Núcleo de Ativos de Carbono", ["carbono"]),
}


AGENCY_BY_UF = {
    "MS": "SEMADESC-MS",
    "MT": "SEMA-MT",
    "GO": "SEMAD-GO",
}


def normalize_slug(s: str) -> str:
    """Remove acentos, baixa caixa, troca espaço/hífen por underscore."""
    nfkd = unicodedata.normalize("NFKD", s)
    only_ascii = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9_]+", "_", only_ascii.lower()).strip("_")


def parse_filename(filename: str) -> tuple[str | None, str]:
    """Extrai (núcleo, tema_slug) do nome do arquivo.

    Exemplos:
      "01_Constitucional.pdf"                         -> ("01", "constitucional")
      "03_Florestal_CAR_PRA.pdf"                      -> ("03", "florestal_car_pra")
      "01_Núcleo Constitucional, Institucional...pdf" -> ("01", "nucleo_constitucional_institucional_e_competencial")
      "07_Credito.pd.pdf"                             -> ("07", "credito_pd")
    """
    stem = Path(filename).stem
    m = re.match(r"^(\d{1,2})[_\s\-]+(.+)$", stem)
    if m:
        nucleo = m.group(1).zfill(2)
        tema = normalize_slug(m.group(2))
    else:
        nucleo = None
        tema = normalize_slug(stem)
    # Remove prefixo "nucleo_" se vier no tema.
    tema = re.sub(r"^nucleo_", "", tema)
    return nucleo, tema


def build_entry(pdf_path: Path, uf: str) -> dict:
    nucleo, tema_slug = parse_filename(pdf_path.name)

    # Mapeia tema → rótulo + demand_types. Busca matches mais específicos primeiro.
    label = None
    demand_types: list[str] = []
    for key, (lbl, dts) in TEMA_MAP.items():
        if key in tema_slug:
            label, demand_types = lbl, dts
            break
    if not label:
        # Fallback: capitaliza o tema bruto.
        label = tema_slug.replace("_", " ").title()
        demand_types = ["geral"]

    nucleo_part = f"NUC{nucleo}" if nucleo else "GERAL"
    identifier = f"{uf}-{nucleo_part}-{tema_slug}"
    title = f"{uf} — Compêndio Regente {nucleo_part}: {label}"

    return {
        "file": pdf_path.name,
        "title": title,
        "identifier": identifier,
        "scope": "estadual",
        "source_type": "compendio_regente",
        "agency": AGENCY_BY_UF.get(uf),
        "uf": uf,
        "effective_date": None,  # compêndio agrega normas com datas diversas
        "demand_types": demand_types,
        "nucleo": nucleo,
        "tema_slug": tema_slug,
    }


def discover_pdfs(pasta: Path) -> list[Path]:
    """Lista PDFs ignorando arquivos temporários (~$...) e ocultos."""
    out: list[Path] = []
    for p in sorted(pasta.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() != ".pdf":
            continue
        if p.name.startswith("~$") or p.name.startswith("."):
            continue
        out.append(p)
    return out


def process_one(
    entry: dict,
    pdf_path: Path,
    preview_dir: Path,
    dry_run: bool,
) -> dict:
    if not pdf_path.exists():
        return {"file": entry["file"], "action": "skipped_missing", "error": "arquivo não encontrado"}

    logger.info("Lendo %s (%.1f MB)...", entry["file"], pdf_path.stat().st_size / 1024 / 1024)
    raw = load_from_pdf_path(pdf_path)
    text = sanitize_text(raw)

    if len(text) < 200:
        return {"file": entry["file"], "action": "failed_short", "chars": len(text)}

    tokens = estimate_tokens(text)
    preview_path = save_preview(entry["identifier"], text, preview_dir)

    info = {
        "file": entry["file"],
        "identifier": entry["identifier"],
        "title": entry["title"],
        "chars": len(text),
        "tokens": tokens,
        "preview": str(preview_path),
    }

    if dry_run:
        info["action"] = "dry_run"
        return info

    from app.db.session import SessionLocal  # noqa: PLC0415
    from app.models.legislation import LegislationDocument  # noqa: PLC0415

    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    db = SessionLocal()
    try:
        existing = (
            db.query(LegislationDocument)
            .filter(LegislationDocument.identifier == entry["identifier"])
            .all()
        )

        # Mesmo hash já indexado → skip.
        for doc in existing:
            if doc.content_hash == content_hash and doc.status == "indexed":
                info["action"] = "skipped_duplicate"
                info["db_id"] = doc.id
                return info

        # Supersede versões anteriores com mesmo identifier.
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
            effective_date=None,
            url=None,
            file_path=str(pdf_path),
            full_text=text,
            token_count=tokens,
            content_hash=content_hash,
            status="indexed",
            demand_types=entry.get("demand_types") or None,
            extra_metadata={"nucleo": entry.get("nucleo"), "tema_slug": entry.get("tema_slug")},
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
    p.add_argument("--uf", required=True, help="Sigla da UF (MS, MT, GO, ...)")
    p.add_argument("--pasta", type=Path, required=True, help="Pasta com os PDFs")
    p.add_argument("--preview-dir", type=Path, default=Path("ops/legislation_preview"))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only", help="Processa apenas arquivos cujo nome contém esta substring")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not args.pasta.exists():
        logger.error("Pasta não encontrada: %s", args.pasta)
        return 1

    args.preview_dir.mkdir(parents=True, exist_ok=True)

    pdfs = discover_pdfs(args.pasta)
    if args.only:
        pdfs = [p for p in pdfs if args.only.lower() in p.name.lower()]
    if not pdfs:
        logger.error("Nenhum PDF encontrado em %s", args.pasta)
        return 2

    uf = args.uf.upper()
    entries = [build_entry(p, uf) for p in pdfs]

    logger.info("Arquivos encontrados (%d):", len(entries))
    for e in entries:
        logger.info("  • %s → %s", e["file"], e["identifier"])

    results = []
    for entry, pdf_path in zip(entries, pdfs):
        try:
            r = process_one(entry, pdf_path, args.preview_dir, args.dry_run)
        except Exception as exc:
            logger.exception("Falha ao processar %s", entry["file"])
            r = {"file": entry["file"], "action": "failed_exception", "error": str(exc)}
        results.append(r)
        logger.info(
            "→ %s | action=%s chars=%s tokens=%s db_id=%s",
            r.get("file"),
            r.get("action"),
            r.get("chars"),
            r.get("tokens"),
            r.get("db_id"),
        )

    # Resumo
    print("\n=== RESUMO ===")
    summary: dict[str, int] = {}
    total_tokens = 0
    for r in results:
        summary[r["action"]] = summary.get(r["action"], 0) + 1
        total_tokens += r.get("tokens") or 0
    for action, count in sorted(summary.items()):
        print(f"  {action}: {count}")
    print(f"  total_tokens (soma): {total_tokens:,}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
