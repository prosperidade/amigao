"""scripts/reindex_legislation_by_uf.py — indexa (chunk + embed) no knowledge_catalog
todos os LegislationDocument já persistidos (status=indexed) de uma UF, chamando
`index_legislation_document` SÍNCRONO (sem depender de um worker Celery consumindo
a fila) — mais simples de observar resultado numa rodada ad-hoc (ex.: prod).

Idempotente: `index_legislation_document` pula chunks com content_hash repetido.

Uso (após `ingest_legislacao_acre.py` ter criado os LegislationDocument):
    python scripts/reindex_legislation_by_uf.py --uf AC
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

# Rodado como `python scripts/reindex_legislation_by_uf.py`, sys.path[0] é a pasta
# do script; adiciona a raiz para que `from app.X import Y` funcione (mesmo padrão
# de sanear_staging.py). Sem isto, ModuleNotFoundError: No module named 'app'.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("reindex_legislation_by_uf")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--uf", required=True, help="UF a reindexar (ex.: AC)")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    from app.db.session import SessionLocal
    from app.models.legislation import LegislationDocument, LegislationStatus
    from app.services.knowledge_catalog import index_legislation_document

    db = SessionLocal()
    try:
        rows = (
            db.query(LegislationDocument)
            .filter(
                LegislationDocument.uf == args.uf,
                LegislationDocument.status == LegislationStatus.indexed.value,
                LegislationDocument.full_text.isnot(None),
            )
            .all()
        )
        if not rows:
            logger.error("Nenhum LegislationDocument indexed encontrado para uf=%s", args.uf)
            return 1

        total_chunks = 0
        for doc in rows:
            inserted = index_legislation_document(db, doc.id)
            db.commit()
            total_chunks += inserted
            logger.info("doc_id=%d identifier=%s chunks_inseridos=%d", doc.id, doc.identifier, inserted)

        print(f"\n=== RESUMO uf={args.uf} ===")
        print(f"  documentos processados: {len(rows)}")
        print(f"  chunks inseridos (novos): {total_chunks}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
