"""
scripts/ingest_pasta_socia.py — Sprint 0 / orquestrador one-shot

Ingere os 15 PDFs da pasta `legislacao/` (fornecida pela sócia em 2026-04-23)
usando a metadata curada manualmente após inspeção.

Uso:
    python scripts/ingest_pasta_socia.py --dry-run   # valida tudo sem escrever
    python scripts/ingest_pasta_socia.py             # ingere de verdade
    python scripts/ingest_pasta_socia.py --only IN_CAR.pdf  # filtra um único arquivo
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
    load_from_pdf_path,
    sanitize_text,
    save_preview,
)

logger = logging.getLogger("ingest_pasta_socia")


# ---------------------------------------------------------------------------
# Metadata curada — decisões da Sprint 0 (confirmadas 2026-04-23)
# ---------------------------------------------------------------------------

CURATED: list[dict] = [
    # Tier 1 — Diplomas limpos
    {
        "file": "IN_CAR.pdf",
        "title": "Instrução Normativa MMA 02/2014 — Procedimentos do CAR/SICAR",
        "identifier": "IN MMA 02/2014",
        "scope": "federal",
        "source_type": "instrucao_normativa",
        "agency": "MMA",
        "uf": None,
        "effective_date": "2014-05-06",
        "demand_types": ["car", "retificacao_car"],
    },
    {
        "file": "N nº 14_2024 IBAMA - Sobre PRAD .pdf",
        "title": "Instrução Normativa IBAMA 14/2024 — Projeto de Recuperação de Áreas Degradadas (PRAD)",
        "identifier": "IN IBAMA 14/2024",
        "scope": "federal",
        "source_type": "instrucao_normativa",
        "agency": "IBAMA",
        "uf": None,
        "effective_date": "2024-07-01",
        "demand_types": ["compensacao", "defesa"],
    },
    {
        "file": "Resolução CEMAm 259 de 29 de maio de 2024 (1).pdf",
        "title": "Resolução CEMAm 259/2024 — Atividades de impacto local (competência municipal)",
        "identifier": "Res. CEMAm 259/2024",
        "scope": "estadual",
        "source_type": "resolucao",
        "agency": "CEMAm",
        "uf": "GO",
        "effective_date": "2024-05-29",
        "demand_types": ["licenciamento"],
    },
    {
        "file": "02_LEGISLACAO_AUTOCOMPOSICAO.pdf",
        "title": "IN SEMAD 01/2024 — Recursos de ofício em processos de autos de infração",
        "identifier": "IN SEMAD-GO 01/2024",
        "scope": "estadual",
        "source_type": "instrucao_normativa",
        "agency": "SEMAD-GO",
        "uf": "GO",
        "effective_date": None,  # texto não tem dia/mês explícito na primeira página
        "demand_types": ["defesa"],
    },
    {
        "file": "03_LEGISLACAO_CADASTRO_AMBIENTAL_RURAL.pdf",
        "title": "IN SEMAD 09/2024 — Cancelamento de CAR no SICAR",
        "identifier": "IN SEMAD-GO 09/2024",
        "scope": "estadual",
        "source_type": "instrucao_normativa",
        "agency": "SEMAD-GO",
        "uf": "GO",
        "effective_date": None,
        "demand_types": ["car", "retificacao_car"],
    },
    {
        "file": "04_LEGISLACAO_COMPENSACAO_AMBIENTAL.pdf",
        "title": "Decreto GO 9.308/2018 — Metodologia de definição do grau de impacto ambiental e compensação",
        "identifier": "Decreto GO 9.308/2018",
        "scope": "estadual",
        "source_type": "decreto",
        "agency": "SEMAD-GO",
        "uf": "GO",
        "effective_date": "2018-09-12",
        "demand_types": ["compensacao"],
    },
    {
        "file": "09_LEGISLAÇÃO_ FISCALIZAÇÃO_AMBIENTAL.pdf",
        "title": "Portaria SEMAD 501/2024 — Procedimentos de fiscalização ambiental",
        "identifier": "Portaria SEMAD-GO 501/2024",
        "scope": "estadual",
        "source_type": "portaria",
        "agency": "SEMAD-GO",
        "uf": "GO",
        "effective_date": "2024-06-27",
        "demand_types": ["defesa"],
    },
    # Tier 2 — Manuais/anexos técnicos
    {
        "file": "06_MANUAIS_CADASTRO_AMBIENTAL.pdf",
        "title": "Manual SFB — Retificação Dinamizada do SICAR (2023)",
        "identifier": "Manual SFB SICAR 2023",
        "scope": "federal",
        "source_type": "manual",
        "agency": "MMA",
        "uf": None,
        "effective_date": "2023-01-01",
        "demand_types": ["car", "retificacao_car"],
    },
    {
        "file": "07_SISTEMA_IPÊ.pdf",
        "title": "Matriz IPÊ — Licenciamento ambiental de atividades rurais (SEMAD GO)",
        "identifier": "Matriz IPÊ SEMAD-GO",
        "scope": "estadual",
        "source_type": "manual",
        "agency": "SEMAD-GO",
        "uf": "GO",
        "effective_date": None,
        "demand_types": ["licenciamento"],
    },
    {
        "file": "08_ATIVIDADES_LICENCIAMENTO_E_INEXIBILIDADE_MUNICIPIOS_APTOS_A_LICENCIAS.pdf",
        "title": "Lista de atividades de licenciamento e inexigibilidade — municípios aptos GO (308p)",
        "identifier": "Anexo ATIV-INEX GO 308p",
        "scope": "estadual",
        "source_type": "manual",
        "agency": "SEMAD-GO",
        "uf": "GO",
        "effective_date": None,
        "demand_types": ["licenciamento"],
    },
    {
        "file": "atividades_inexigiveis (10) (1).pdf",
        "title": "Lista de atividades inexigíveis — GO (versão curta 7p)",
        "identifier": "Anexo ATIV-INEX GO 7p",
        "scope": "estadual",
        "source_type": "manual",
        "agency": "SEMAD-GO",
        "uf": "GO",
        "effective_date": None,
        "demand_types": ["licenciamento"],
    },
    # Tier 3 — Coletâneas grandes (ingerir inteiro — Gemini Pro cobre via roteamento dinâmico)
    {
        "file": "01_LEGISLACAO_REGULARIZACAO_AMBIENTAL.pdf",
        "title": "Coletânea Regularização Ambiental GO (convênios/atos 2024)",
        "identifier": "Coletânea Regularização Ambiental GO 2024",
        "scope": "estadual",
        "source_type": "manual",
        "agency": "SEMAD-GO",
        "uf": "GO",
        "effective_date": None,
        "demand_types": ["regularizacao_fundiaria"],
    },
    {
        "file": "05_LEGISLACAO_LICENCIAMENTO_AMBIENTAL.pdf",
        "title": "Coletânea Licenciamento Ambiental GO (Portaria SEMAD 183/2020 e correlatas, 796p)",
        "identifier": "Coletânea Licenciamento GO 2020+",
        "scope": "estadual",
        "source_type": "manual",
        "agency": "SEMAD-GO",
        "uf": "GO",
        "effective_date": "2020-01-01",
        "demand_types": ["licenciamento"],
    },
    {
        "file": "10.PLANO DE MANEJO POUSO ALTO.pdf",
        "title": "Plano de Manejo — Estação Ecológica de Pouso Alto (GO, 2016)",
        "identifier": "Plano de Manejo EE Pouso Alto 2016",
        "scope": "estadual",
        "source_type": "manual",
        "agency": "SEMAD-GO",
        "uf": "GO",
        "effective_date": "2016-06-23",
        "demand_types": [],  # documento territorial específico — aparece só em busca direta
    },
    {
        "file": "10_LEGILACAO_RECURSOS_HIDRICOS_OUTORGA.pdf",
        "title": "Coletânea Recursos Hídricos / Outorga GO (Lei 13.123/1997 + atos correlatos)",
        "identifier": "Coletânea Outorga GO 1997+",
        "scope": "estadual",
        "source_type": "manual",
        "agency": "SEMAD-GO",
        "uf": "GO",
        "effective_date": "1997-07-16",
        "demand_types": ["outorga"],
    },
]


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------

def process_one(
    entry: dict,
    pasta: Path,
    preview_dir: Path,
    dry_run: bool,
) -> dict:
    """Processa um PDF e opcionalmente persiste no banco."""
    pdf_path = pasta / entry["file"]
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
        "chars": len(text),
        "tokens": tokens,
        "preview": str(preview_path),
    }

    if dry_run:
        info["action"] = "dry_run"
        return info

    # Persistir no banco
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

        # Skip se já indexado com mesmo hash
        for doc in existing:
            if doc.content_hash == content_hash and doc.status == "indexed":
                info["action"] = "skipped_duplicate"
                info["db_id"] = doc.id
                return info

        # Supersede antigos
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
    p.add_argument("--pasta", type=Path, default=Path("legislacao"))
    p.add_argument("--preview-dir", type=Path, default=Path("ops/legislation_preview"))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only", help="Processa só o arquivo cujo nome contém esta substring")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not args.pasta.exists():
        logger.error("Pasta não encontrada: %s", args.pasta)
        return 1

    entries = CURATED
    if args.only:
        entries = [e for e in CURATED if args.only.lower() in e["file"].lower()]
        if not entries:
            logger.error("Nenhuma entrada curada bate com --only=%s", args.only)
            return 2

    results = []
    for entry in entries:
        try:
            r = process_one(entry, args.pasta, args.preview_dir, args.dry_run)
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
