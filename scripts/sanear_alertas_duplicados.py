"""Saneamento RETROATIVO de alertas regulatórios duplicados (origem do caso 13).

O guard de idempotência em ``auditor_imovel._persist_issues`` impede NOVAS
duplicatas. Este comando limpa as que já existem: colapsa grupos de
``RegulatoryIssue`` não resolvidos que são duplicatas exatas (mesma
``issue_dedupe_key``), preservando o sinal humano.

Regra (ver ``app/services/regulatory_dedupe.py``):
  - linhas DECIDIDAS pelo consultor (status_achado ≠ suspeita, status_saneamento
    ≠ pendente, ou com ProcessIssueDecision) são SEMPRE preservadas;
  - havendo ≥1 decidida, as não decididas do grupo são removidas (ruído);
  - sem decisão, mantém-se a mais recente;
  - grupos com ≥2 decididas CONFLITANTES são reportados e NÃO são tocados entre
    si — resolução é humana.

Idempotente — rodar duas vezes não remove nada na segunda passada.

Uso (dentro do container api, ou no venv host apontando o .env de prod):
    python scripts/sanear_alertas_duplicados.py --tenant-id 1
    python scripts/sanear_alertas_duplicados.py --property-id 10
    python scripts/sanear_alertas_duplicados.py --process-id 13           # deriva property/tenant
    python scripts/sanear_alertas_duplicados.py --process-id 13 --dry-run # só relata
    python scripts/sanear_alertas_duplicados.py --process-id 13 -v        # lista cada grupo

Caso 13 (decisão do André = opção A; 22/23 eram cliques de teste):
    python scripts/sanear_alertas_duplicados.py --process-id 13 --reset-conflicting --dry-run
    python scripts/sanear_alertas_duplicados.py --process-id 13 --reset-conflicting
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal  # noqa: E402
from app.services.regulatory_dedupe import sanear_alertas_duplicados  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Saneamento retroativo de alertas duplicados.")
    parser.add_argument("--process-id", type=int, default=None, help="Deriva tenant + property.")
    parser.add_argument("--property-id", type=int, default=None, help="Limita ao imóvel.")
    parser.add_argument("--tenant-id", type=int, default=None, help="Tenant (derivado se omitido).")
    parser.add_argument("--dry-run", action="store_true", help="Só relata; não grava.")
    parser.add_argument(
        "--reset-conflicting", action="store_true",
        help="Opção A: reseta decisões conflitantes (sem ProcessIssueDecision) "
             "para suspeita e colapsa o grupo. Use quando as decisões eram cliques "
             "de teste sobre duplicatas (ex.: caso 13).",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Lista cada grupo tocado.")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        tenant_id = args.tenant_id
        property_id = args.property_id

        if args.process_id is not None:
            from app.models.process import Process  # noqa: PLC0415

            proc = session.query(Process).filter(Process.id == args.process_id).first()
            if proc is None:
                print(f"ERRO: processo {args.process_id} não encontrado.", file=sys.stderr)
                return 2
            if tenant_id is None:
                tenant_id = proc.tenant_id
            if property_id is None:
                property_id = proc.property_id

        if tenant_id is None:
            print("ERRO: informe --tenant-id (ou --process-id para derivá-lo).", file=sys.stderr)
            return 2

        result = sanear_alertas_duplicados(
            session,
            tenant_id=tenant_id,
            property_id=property_id,
            dry_run=args.dry_run,
            reset_conflicting=args.reset_conflicting,
        )
        if not args.dry_run:
            session.commit()

        modo = "DRY-RUN (nada gravado)" if args.dry_run else "APLICADO"
        escopo = f"property {property_id}" if property_id is not None else "todos os imóveis"
        print(f"== Saneamento alertas · tenant {tenant_id} · {escopo} · {modo} ==")
        print(f"  linhas antes:  {result.rows_before}")
        print(f"  linhas depois: {result.rows_after}")
        print(f"  removidas:     {result.duplicates_removed} "
              f"(grupos colapsados={result.groups_collapsed})")
        if result.decisions_preserved:
            print(f"  decisões do consultor preservadas: {result.decisions_preserved}")
        if result.decisions_reset:
            print(f"  decisões conflitantes resetadas p/ suspeita (opção A): {result.decisions_reset}")
        if result.conflicts:
            print(f"  ⚠ grupos com decisões CONFLITANTES (resolução humana): {len(result.conflicts)}")
            for c in result.conflicts:
                print(f"    - {c}")
        if args.verbose and result.details:
            print("  detalhes:")
            for d in result.details:
                print(f"    - {d}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
