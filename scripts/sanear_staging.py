"""Saneamento RETROATIVO do staging de um processo (regra de limpeza do #81).

A limpeza-na-origem (ficha01_extraction.build_staging_fields) só vale para
extrações NOVAS. Processos cujo staging entrou ANTES do #81 podem ter:
  - duplicata de formato ("349.9022" e "349,9022" como 2 linhas);
  - lixo em campo de código ("Certidão de Embargo" num numero_car);
  - lista repetida (pendencias_rat / onus duplicados).

Este comando aplica a MESMA regra ao staging já gravado. Idempotente — rodar
duas vezes não remove nada na segunda passada. NÃO apaga decisões do consultor
(aceito/rejeitado): lixo decidido é preservado; numa duplicata decidida mantém-se
a linha que carrega a decisão.

Uso (dentro do container api, ou no venv host apontando o .env de prod):
    python scripts/sanear_staging.py --process-id 13
    python scripts/sanear_staging.py --process-id 13 --dry-run     # só relata, não grava
    python scripts/sanear_staging.py --process-id 13 --tenant-id 1 # força o tenant
    python scripts/sanear_staging.py --process-id 13 -v            # lista cada linha tocada

Sem --tenant-id, o tenant é derivado do próprio processo.
"""

from __future__ import annotations

import argparse
import os
import sys

# Rodado como `python scripts/sanear_staging.py`, sys.path[0] é a pasta do script;
# adiciona a raiz para que `from app.X import Y` funcione.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal  # noqa: E402
from app.services.ficha01_extraction import sanear_staging_process  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Saneamento retroativo do staging.")
    parser.add_argument("--process-id", type=int, required=True, help="ID do processo a sanear.")
    parser.add_argument(
        "--tenant-id", type=int, default=None,
        help="Tenant do processo (derivado do processo se omitido).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Só relata o que seria removido; não grava.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Lista cada linha tocada.")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        tenant_id = args.tenant_id
        if tenant_id is None:
            from app.models.process import Process  # noqa: PLC0415

            proc = session.query(Process).filter(Process.id == args.process_id).first()
            if proc is None:
                print(f"ERRO: processo {args.process_id} não encontrado.", file=sys.stderr)
                return 2
            tenant_id = proc.tenant_id

        result = sanear_staging_process(
            session,
            tenant_id=tenant_id,
            process_id=args.process_id,
            dry_run=args.dry_run,
        )
        if not args.dry_run:
            session.commit()

        modo = "DRY-RUN (nada gravado)" if args.dry_run else "APLICADO"
        print(f"== Saneamento staging · processo {args.process_id} · tenant {tenant_id} · {modo} ==")
        print(f"  linhas antes:  {result.rows_before}")
        print(f"  linhas depois: {result.rows_after}")
        print(f"  removidas:     {result.total_removed} "
              f"(lixo={result.garbage_removed}, formato={result.duplicates_removed}, "
              f"lista={result.lists_collapsed})")
        if result.decisions_preserved:
            print(f"  decisões do consultor preservadas: {result.decisions_preserved}")
        if args.verbose and result.details:
            print("  detalhes:")
            for d in result.details:
                print(f"    - {d}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
