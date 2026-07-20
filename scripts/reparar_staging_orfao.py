"""Reparo do staging órfão (`process_id` NULL) — CLI.

  DRY-RUN É O DEFAULT. Sem ``--execute`` nada é escrito — lista linha a linha
  o que seria adotado e o que seria apagado.

Decisão híbrida (André, 2026-07-20): órfã redundante com a leva vinculada é
APAGADA; órfã que é a única leitura do campo é ADOTADA (ganha `process_id`).
`field_value` nunca é tocado.

Uso (dentro do container api):

    # Dry-run nominal, id a id
    python scripts/reparar_staging_orfao.py --process-id 15 --verbose

    # Execução real — exige a frase de confirmação
    python scripts/reparar_staging_orfao.py --process-id 15 --execute

    # Não-interativo
    python scripts/reparar_staging_orfao.py --process-id 15 --execute \\
        --confirm "adotar 2 e apagar 44 linha(s) de staging"

Sem --process-id, o escopo é o banco inteiro (todos os documentos com dono).
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal  # noqa: E402
from app.services.reparo_staging_orfao import (  # noqa: E402
    RelatorioReparo,
    planejar_reparo,
)


def _confirmation_phrase(n_adotar: int, n_apagar: int) -> str:
    return f"adotar {n_adotar} e apagar {n_apagar} linha(s) de staging"


def _print_report(rel: RelatorioReparo, *, verbose: bool) -> None:
    modo = "EXECUTADO (gravado)" if rel.executado else "DRY-RUN (nada gravado)"
    print(f"\n== Reparo de staging órfão · {modo} ==")
    print(f"  {'adotadas' if rel.executado else 'a adotar'} (única leitura): {len(rel.adotar)}")
    print(f"  {'apagadas' if rel.executado else 'a apagar'} (redundantes):   {len(rel.apagar)}")
    if rel.sem_dono:
        print(f"  ignoradas (documento ainda sem processo): {rel.sem_dono}")

    if rel.adotar:
        print("\n  ADOTAR — preenche process_id, valor intocado:")
        for item in rel.adotar:
            print(f"    staging {item.staging_id:<7} doc {item.document_id:<6} "
                  f"{item.field_name:<26} → processo {item.process_id_alvo}")

    if rel.apagar:
        if verbose:
            print("\n  APAGAR — redundantes com a leva já vinculada:")
            for item in rel.apagar:
                print(f"    staging {item.staging_id:<7} doc {item.document_id:<6} {item.field_name}")
        else:
            por_doc: dict[int, int] = {}
            for item in rel.apagar:
                por_doc[item.document_id] = por_doc.get(item.document_id, 0) + 1
            print("\n  APAGAR — redundantes, por documento:")
            for doc_id, n in sorted(por_doc.items()):
                print(f"    doc {doc_id}: {n}")
            print("    (use --verbose para a lista id a id)")

    if not rel.executado and (rel.adotar or rel.apagar):
        print("\n  Nada foi gravado. Para aplicar, repita com --execute.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Reparo de staging órfão (process_id NULL).")
    parser.add_argument("--process-id", type=int, action="append", dest="process_ids",
                        help="Escopo por processo (repetível). Sem isto, o banco inteiro.")
    parser.add_argument("--execute", action="store_true", help="Grava de verdade.")
    parser.add_argument("--confirm", type=str, default=None, help="Frase para uso não-interativo.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Lista as apagadas id a id.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        previa = planejar_reparo(db, process_ids=args.process_ids, executar=False)

        if not args.execute:
            _print_report(previa, verbose=args.verbose)
            return 0

        if not previa.adotar and not previa.apagar:
            _print_report(previa, verbose=args.verbose)
            print("\n  Nada a reparar — encerrando sem escrever.")
            return 0

        frase = _confirmation_phrase(len(previa.adotar), len(previa.apagar))
        if args.confirm is None:
            print(f"\nPara confirmar, digite exatamente:\n  {frase}")
            try:
                digitado = input("> ").strip()
            except EOFError:
                print("ERRO: sem terminal interativo. Use --confirm.", file=sys.stderr)
                return 2
        else:
            digitado = args.confirm.strip()

        if digitado != frase:
            print("ERRO: frase de confirmação não confere. Nada foi gravado.", file=sys.stderr)
            return 2

        rel = planejar_reparo(db, process_ids=args.process_ids, executar=True)
        db.commit()
        _print_report(rel, verbose=args.verbose)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
