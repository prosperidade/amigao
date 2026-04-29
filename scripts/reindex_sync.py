"""Re-indexa legislacao pendente sincronamente (bypass do Celery).

Util quando o worker esta afogado em retries de outras tasks. Itera
LegislationDocument que nao tem chunks no knowledge_catalog e indexa
um por um, commitando depois de cada doc para que progresso seja
visivel ao vivo via SELECT count(*) FROM knowledge_catalog.

Uso (dentro do container api):
    python scripts/reindex_sync.py
    python scripts/reindex_sync.py --only 3,4,5      # apenas docs especificos
    python scripts/reindex_sync.py --skip-large      # pula docs > 100k tokens
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import traceback

# Quando rodado como `python scripts/reindex_sync.py`, sys.path[0] é a pasta
# do script — nao a raiz. Adicionamos a raiz para que `from app.X import Y` funcione.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.services.knowledge_catalog import index_legislation_document  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="lista de doc_ids separados por virgula")
    parser.add_argument(
        "--skip-large",
        action="store_true",
        help="pula docs com token_count > 100000",
    )
    args = parser.parse_args()

    session = SessionLocal()

    if args.only:
        wanted = [int(x.strip()) for x in args.only.split(",") if x.strip()]
        rows = session.execute(
            text(
                "SELECT id, title, token_count FROM legislation_documents "
                "WHERE id = ANY(:ids) ORDER BY token_count"
            ),
            {"ids": wanted},
        ).all()
    else:
        rows = session.execute(
            text(
                """
                SELECT ld.id, ld.title, ld.token_count
                FROM legislation_documents ld
                LEFT JOIN (
                    SELECT split_part(source_ref,':',2)::int AS doc_id
                    FROM knowledge_catalog
                    WHERE source_type='legislation'
                    GROUP BY 1
                ) kc ON kc.doc_id = ld.id
                WHERE kc.doc_id IS NULL AND ld.full_text IS NOT NULL
                ORDER BY ld.token_count
                """
            )
        ).all()

    if not rows:
        print("Nada a fazer: todos os docs com full_text ja tem chunks.")
        return 0

    if args.skip_large:
        rows = [r for r in rows if r.token_count <= 100_000]

    total_tokens = sum(r.token_count for r in rows)
    est_chunks = total_tokens // 800
    est_seconds = int(est_chunks * 1.05)
    print(f"==> {len(rows)} docs a indexar, ~{total_tokens:,} tokens, "
          f"~{est_chunks} chunks, ~{est_seconds//60} min estimados.")
    for r in rows:
        print(f"    doc {r.id:>2}: {r.token_count:>7,} tokens — {r.title[:60]}")
    print()

    grand_total = 0
    for i, r in enumerate(rows, 1):
        print(f"[{i}/{len(rows)}] doc {r.id} ({r.token_count:,} tokens)...", flush=True)
        t0 = time.monotonic()
        try:
            inserted = index_legislation_document(session, r.id)
            session.commit()
            dt = time.monotonic() - t0
            grand_total += inserted
            print(f"    OK inserted={inserted} em {dt:.1f}s", flush=True)
        except Exception as exc:
            session.rollback()
            print(f"    FAIL: {type(exc).__name__}: {exc}", flush=True)
            traceback.print_exc()

    print(f"\n=== TOTAL inserido: {grand_total} chunks ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
