"""Reset de casos de teste — CLI (FASE 2).

Apaga TODO o rastro de casos de teste EXPLÍCITOS de um tenant (staging, ações,
rotas, diagnóstico, issues, checklists, propostas, contratos, documentos +
objetos R2, AIJobs, drafts órfãos, e imóvel/matrículas/cliente quando ficam
órfãos). A lógica vive em ``app/services/reset_casos_teste.py``.

  DRY-RUN É O DEFAULT. Sem ``--execute`` nada é escrito — só lista as contagens.

Uso (dentro do container api, ou no venv host apontando o .env do ambiente):

    # Dry-run (default): só relata a lista que será apagada
    python scripts/reset_casos_teste.py --process-id 13

    # Vários casos de uma vez
    python scripts/reset_casos_teste.py --process-id 13 --process-id 14

    # Execução real — EXIGE backup confirmado + frase digitada
    python scripts/reset_casos_teste.py --process-id 13 --execute --backup-confirmada
    #  → o script imprime a frase exata e pede que você a digite

    # Execução não-interativa (CI/automação): a frase vai em --confirm
    python scripts/reset_casos_teste.py --process-id 13 --execute \\
        --backup-confirmada --confirm "apagar 1 caso(s) do tenant 1"

PRÉ-REQUISITO OBRIGATÓRIO do --execute: dump/PITR feito. Ver a seção
"Reset de casos de teste" em docs/operacao/RUNBOOK_OPS.md.
"""

from __future__ import annotations

import argparse
import os
import sys

# Rodado como `python scripts/reset_casos_teste.py`: adiciona a raiz ao path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal  # noqa: E402
from app.services.reset_casos_teste import (  # noqa: E402
    ResetReport,
    ResetScopeError,
    collect_scope,
    dry_run,
    execute_reset,
)


def _confirmation_phrase(tenant_id: int, n_casos: int) -> str:
    """Frase exata que o operador precisa digitar para o --execute."""
    return f"apagar {n_casos} caso(s) do tenant {tenant_id}"


def _print_report(report: ResetReport, *, verbose: bool) -> None:
    modo = "EXECUTADO (gravado)" if report.executed else "DRY-RUN (nada gravado)"
    print(f"\n== Reset de casos · tenant {report.tenant_id} · {modo} ==")
    print(f"  processos no escopo: {report.process_ids}")
    print(f"  imóveis a apagar (órfãos):   {report.property_ids or '—'}")
    if report.property_ids_preserved:
        print(f"  imóveis preservados (compartilhados): {report.property_ids_preserved}")
    print(f"  clientes a apagar (órfãos):  {report.client_ids or '—'}")
    if report.client_ids_preserved:
        print(f"  clientes preservados (compartilhados): {report.client_ids_preserved}")
    print("  ---------------------------------------------")
    print("  linhas por tabela:")
    for label, n in report.counts.items():
        if n or verbose:
            print(f"    {label:<32} {n:>6}")
    print("  ---------------------------------------------")
    print(f"  TOTAL de linhas:             {report.total_rows():>6}")
    verbo = "apagados" if report.executed else "a apagar"
    print(f"  objetos R2 {verbo}:          {report.r2_objects:>6}")
    detach = "desvinculados" if report.executed else "a desvincular"
    print(f"  legislation_alerts {detach}: {report.legislation_alerts_detached:>6} (preservados)")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reset de casos de teste (dry-run é o default).",
    )
    parser.add_argument(
        "--process-id", type=int, action="append", required=True, dest="process_ids",
        help="ID de um processo a resetar. Repita para vários casos.",
    )
    parser.add_argument(
        "--tenant-id", type=int, default=None,
        help="Tenant esperado (cross-check; derivado dos processos se omitido).",
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="Executa de verdade. Sem esta flag, é dry-run (nada é escrito).",
    )
    parser.add_argument(
        "--backup-confirmada", action="store_true",
        help="Asserção de que o dump/PITR foi feito (obrigatório com --execute).",
    )
    parser.add_argument(
        "--confirm", type=str, default=None,
        help="Frase de confirmação (não-interativo). Precisa bater exatamente.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Mostra tabelas com contagem zero.")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        try:
            scope = collect_scope(session, args.process_ids, tenant_id=args.tenant_id)
        except ResetScopeError as exc:
            print(f"ERRO de escopo: {exc}", file=sys.stderr)
            return 2

        # Sempre mostra o dry-run primeiro — é a lista que fundamenta a decisão.
        report = dry_run(session, scope)
        _print_report(report, verbose=args.verbose)

        if not args.execute:
            print("Dry-run: nada foi alterado. Adicione --execute para gravar.\n")
            return 0

        # --- Gates do --execute ---
        if not args.backup_confirmada:
            print(
                "RECUSADO: --execute exige --backup-confirmada.\n"
                "Faça o dump/PITR primeiro (docs/operacao/RUNBOOK_OPS.md → "
                "'Reset de casos de teste') e rode de novo com --backup-confirmada.",
                file=sys.stderr,
            )
            return 3

        phrase = _confirmation_phrase(scope.tenant_id, len(scope.process_ids))
        if args.confirm is not None:
            typed = args.confirm
        else:
            print(f"Para confirmar a EXCLUSÃO IRREVERSÍVEL, digite exatamente:\n  {phrase}")
            try:
                typed = input("> ").strip()
            except EOFError:
                typed = ""
        if typed != phrase:
            print(
                f"RECUSADO: confirmação não confere.\n  esperado: {phrase!r}\n  recebido: {typed!r}\n"
                "Nada foi alterado.",
                file=sys.stderr,
            )
            return 4

        # --- Execução real ---
        from app.services.storage import BUCKET_NAME, get_storage_service  # noqa: PLC0415

        s3_client = get_storage_service().s3_client
        result = execute_reset(
            session,
            scope,
            user_id=None,  # operação de sistema (script), sem usuário logado
            s3_client=s3_client,
            bucket=BUCKET_NAME,
        )
        session.commit()
        _print_report(result, verbose=args.verbose)
        print("Reset EXECUTADO e commitado. Registro em audit_logs (action=reset_casos_teste).\n")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
