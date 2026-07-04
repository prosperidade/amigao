"""scripts/ingest_legislacao_acre.py — ingere o corpus legislativo do Acre (AC).

Diferente dos compêndios MS/MT (PDFs com núcleo no nome do arquivo), o corpus
do Acre veio da pasta "Legislações Regente" como arquivos **Markdown** já
textuais (ACRE_N1.md .. ACRE_N12.md), exportados do portal LEGIS/LegisWeb.

A numeração N# NÃO segue fielmente a ordem dos núcleos Regente de MS/MT
(medido por frequência de palavras-chave em 2026-07-04), então a metadata é
CURADA por arquivo — tema e demand_types refletem o conteúdo dominante medido,
não o número.

Particularidades do corpus (verificadas por SHA-256):
- ACRE_N11.md é byte-idêntico a ACRE_N10.md → só N10 é ingerido.
- ACRE_LEG_RURAL.md é a compilação dos N# (soma dos tamanhos bate) → pulado
  para não duplicar chunks no RAG. Único conteúdo exclusivo dele é o N7
  (~28 KB, sem arquivo avulso) — pendente de export separado.
- LEG-Consultada-OE-2025.md é a bibliografia CPI/PUC-Rio "Onde Estamos na
  Implementação do Código Florestal?" (ed. 2025) — lista as normas de CAR/PRA
  de todas as UFs. Ingerida com uf=None (aplicável a qualquer UF).

Uso (dentro do container api, pasta montada em /app/legislacao_estadual/AC):
    python scripts/ingest_legislacao_acre.py --pasta /app/legislacao_estadual/AC --dry-run
    python scripts/ingest_legislacao_acre.py --pasta /app/legislacao_estadual/AC
    python scripts/ingest_legislacao_acre.py --pasta /app/legislacao_estadual/AC --only N5
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
    sanitize_text,
    save_preview,
)

logger = logging.getLogger("ingest_legislacao_acre")


# Metadata curada por arquivo. Chave = nome do arquivo.
# (identifier, title, scope, uf, agency, demand_types, extra)
CURATED: dict[str, dict] = {
    "ACRE_N1.md": {
        "identifier": "AC-N01-constitucional",
        "title": "AC — Compêndio Regente N01: Núcleo Constitucional e Institucional",
        "demand_types": ["geral"],
        "tema_slug": "constitucional",
    },
    "ACRE_N2.md": {
        "identifier": "AC-N02-territorial_cadastro",
        "title": "AC — Compêndio Regente N02: Núcleo Territorial e Cadastro (ZEE, CIGMA)",
        "demand_types": ["car", "cadastro"],
        "tema_slug": "territorial_cadastro",
    },
    "ACRE_N3.md": {
        "identifier": "AC-N03-florestal_car_pra",
        "title": "AC — Compêndio Regente N03: Núcleo Florestal — CAR e PRA (vol. 1)",
        "demand_types": ["car", "prad", "reserva_legal"],
        "tema_slug": "florestal_car_pra",
    },
    "ACRE_N4.md": {
        "identifier": "AC-N04-licenciamento",
        "title": "AC — Compêndio Regente N04: Núcleo de Licenciamento Ambiental e Agrotóxicos",
        "demand_types": ["licenciamento"],
        "tema_slug": "licenciamento",
    },
    "ACRE_N5.md": {
        "identifier": "AC-N05-hidrico",
        "title": "AC — Compêndio Regente N05: Núcleo Hídrico e Outorgas",
        "demand_types": ["outorga"],
        "tema_slug": "hidrico",
    },
    "ACRE_N6.md": {
        "identifier": "AC-N06-florestal_car_pra_2",
        "title": "AC — Compêndio Regente N06: Núcleo Florestal — CAR e PRA (vol. 2, Lei 3.349/2017)",
        "demand_types": ["car", "prad", "reserva_legal"],
        "tema_slug": "florestal_car_pra",
    },
    "ACRE_N8.md": {
        "identifier": "AC-N08-biomas_ucs",
        "title": "AC — Compêndio Regente N08: Núcleo de Biomas e Unidades de Conservação",
        "demand_types": ["biodiversidade"],
        "tema_slug": "biomas",
    },
    "ACRE_N9.md": {
        "identifier": "AC-N09-infracoes_sanidade",
        "title": "AC — Compêndio Regente N09: Infrações, Fiscalização e Sanidade Agropecuária",
        "demand_types": ["defesa", "auto_infracao", "fauna"],
        "tema_slug": "infracoes",
    },
    "ACRE_N10.md": {
        "identifier": "AC-N10-politica_ambiental_sisa",
        "title": "AC — Compêndio Regente N10: Política Ambiental Estadual e Serviços Ambientais (SISA)",
        "demand_types": ["geral", "carbono"],
        "tema_slug": "politica_ambiental",
    },
    "ACRE_N12.md": {
        "identifier": "AC-N12-regularizacao_servicos_ambientais",
        "title": "AC — Compêndio Regente N12: Regularização Ambiental e Serviços Ambientais",
        "demand_types": ["car", "prad", "carbono"],
        "tema_slug": "regularizacao",
    },
    "LEG-Consultada-OE-2025.md": {
        "identifier": "CPI-LEG-CONSULTADA-OE-2025",
        "title": "CPI/PUC-Rio — Legislação Consultada: Radiografia do CAR e do PRA nos Estados (ed. 2025)",
        "scope": "nacional",
        "uf": None,
        "agency": None,
        "source_type": "referencia_bibliografica",
        "demand_types": ["car", "prad"],
        "tema_slug": "referencia_car_pra_ufs",
    },
}

# Ignorados de propósito (duplicatas verificadas por hash — ver docstring).
SKIPPED = {"ACRE_N11.md", "ACRE_LEG_RURAL.md"}

DEFAULTS = {
    "scope": "estadual",
    "uf": "AC",
    "agency": "SEMAPI-AC",
    "source_type": "compendio_regente",
}


def process_one(md_path: Path, meta: dict, preview_dir: Path, dry_run: bool) -> dict:
    raw = md_path.read_text(encoding="utf-8", errors="replace")
    text = sanitize_text(raw)

    if len(text) < 200:
        return {"file": md_path.name, "action": "failed_short", "chars": len(text)}

    tokens = estimate_tokens(text)
    preview_path = save_preview(meta["identifier"], text, preview_dir)

    info = {
        "file": md_path.name,
        "identifier": meta["identifier"],
        "title": meta["title"],
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
            .filter(LegislationDocument.identifier == meta["identifier"])
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
            title=meta["title"],
            identifier=meta["identifier"],
            scope=meta.get("scope", DEFAULTS["scope"]),
            source_type=meta.get("source_type", DEFAULTS["source_type"]),
            agency=meta.get("agency", DEFAULTS["agency"]),
            uf=meta.get("uf", DEFAULTS["uf"]),
            municipality=None,
            effective_date=None,
            url=None,
            file_path=str(md_path),
            full_text=text,
            token_count=tokens,
            content_hash=content_hash,
            status="indexed",
            demand_types=meta.get("demand_types") or None,
            extra_metadata={"tema_slug": meta.get("tema_slug"), "origem": "pasta_legislacoes_regente"},
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
    p.add_argument("--pasta", type=Path, required=True, help="Pasta com os .md do Acre")
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

    presentes = {f.name for f in args.pasta.iterdir() if f.is_file()}
    ignorados = presentes & SKIPPED
    desconhecidos = presentes - set(CURATED) - SKIPPED
    faltando = set(CURATED) - presentes

    for name in sorted(ignorados):
        logger.info("Ignorando %s (duplicata/compilação — ver docstring)", name)
    for name in sorted(desconhecidos):
        logger.warning("Arquivo sem metadata curada (pulado): %s", name)
    for name in sorted(faltando):
        logger.warning("Arquivo curado ausente na pasta: %s", name)

    alvos = sorted(set(CURATED) & presentes)
    if args.only:
        alvos = [n for n in alvos if args.only.lower() in n.lower()]
    if not alvos:
        logger.error("Nenhum arquivo a processar em %s", args.pasta)
        return 2

    results = []
    for name in alvos:
        meta = CURATED[name]
        try:
            r = process_one(args.pasta / name, meta, args.preview_dir, args.dry_run)
        except Exception as exc:
            logger.exception("Falha ao processar %s", name)
            r = {"file": name, "action": "failed_exception", "error": str(exc)}
        results.append(r)
        logger.info(
            "→ %s | action=%s chars=%s tokens=%s db_id=%s",
            r.get("file"), r.get("action"), r.get("chars"), r.get("tokens"), r.get("db_id"),
        )

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
