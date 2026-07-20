"""Backfill de `Document.document_type` por conteúdo — dívida #70.

Reclassifica documentos que estão SEM tipo (`document_type` NULL/vazio) usando o
texto já salvo em `extracted_text`, grava o tipo e re-dispara o vínculo com o
item do checklist.

  DRY-RUN É O DEFAULT. Sem ``--execute`` nada é escrito — só lista o que faria.

**Custo zero de IA.** `classify_doc_type` é rule-based (palavras-chave sobre o
texto). Não há re-OCR nem chamada a provider. A extração de campos, essa sim
paga, NÃO é disparada por este script.

**Só preenche NULL** (decisão do André, 2026-07-20): documento que já tem
`document_type` é preservado mesmo quando o conteúdo discorda. Essas divergências
aparecem no relatório como achado para revisão humana — nunca são escritas.

Uso (dentro do container api, ou no venv host apontando o .env do ambiente):

    # Dry-run (default): relata doc_id → tipo proposto
    python scripts/backfill_document_type.py --process-id 15

    # Escopo por tenant
    python scripts/backfill_document_type.py --tenant-id 1

    # Execução real — exige a frase de confirmação
    python scripts/backfill_document_type.py --process-id 15 --execute
    #  → o script imprime a frase exata e pede que você a digite

    # Não-interativo (CI/automação)
    python scripts/backfill_document_type.py --process-id 15 --execute \\
        --confirm "gravar tipo em 30 documento(s)"

Diferente do reset-tool, este backfill é ADITIVO: só preenche campo vazio, não
apaga nem sobrescreve nada. Por isso não exige backup confirmado — mas continua
pedindo confirmação explícita, porque escreve em produção.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal  # noqa: E402
from app.services.document_classification import (  # noqa: E402
    RelatorioBackfill,
    planejar_backfill,
)


def _confirmation_phrase(n: int) -> str:
    return f"gravar tipo em {n} documento(s)"


def _print_report(rel: RelatorioBackfill, *, verbose: bool) -> None:
    modo = "EXECUTADO (gravado)" if rel.executado else "DRY-RUN (nada gravado)"
    print(f"\n== Backfill de document_type · {rel.escopo} · {modo} ==")
    print(f"  sem tipo, COM texto salvo (classificáveis): {rel.candidatos}")
    print(f"  sem tipo e SEM texto (precisam de OCR antes): {rel.sem_texto}")
    lista = rel.gravados if rel.executado else rel.a_gravar
    print(f"  {'gravados' if rel.executado else 'seriam gravados'}: {len(lista)}")
    print(f"  vinculados a item de checklist: {len(rel.vinculados)}")
    print(f"  texto lido mas sem tipo específico: {len(rel.sem_tipo_definido)}")

    por_tipo: dict[str, int] = {}
    for r in rel.resultados:
        if r.tipo_proposto and r.tipo_proposto != "outro":
            por_tipo[r.tipo_proposto] = por_tipo.get(r.tipo_proposto, 0) + 1
    if por_tipo:
        print("\n  Distribuição por tipo proposto:")
        for tipo, n in sorted(por_tipo.items(), key=lambda kv: -kv[1]):
            print(f"    {tipo:<22} {n}")

    divergentes = [r for r in rel.resultados if r.divergente]
    if divergentes:
        print(f"\n  ACHADO — conteúdo diverge do tipo já gravado ({len(divergentes)}):")
        print("  (preservados por decisão; candidatos a alerta futuro)")
        for r in divergentes:
            print(f"    doc {r.document_id}: gravado={r.tipo_anterior} conteúdo={r.tipo_proposto}")

    if verbose:
        print("\n  Detalhe por documento:")
        for r in rel.resultados:
            alvo = r.tipo_proposto or "—"
            marca = "*" if r.gravado else " "
            vinc = f" → item {r.item_vinculado}" if r.item_vinculado else ""
            print(f"   {marca} doc {r.document_id:<6} {alvo:<22} {r.motivo}{vinc}")

    if not rel.executado and rel.candidatos:
        print("\n  Nada foi gravado. Para aplicar, repita com --execute.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill de document_type por conteúdo (#70).")
    parser.add_argument("--process-id", type=int, action="append", dest="process_ids",
                        help="Escopo por processo (repetível).")
    parser.add_argument("--tenant-id", type=int, default=None,
                        help="Escopo por tenant (todos os processos).")
    parser.add_argument("--execute", action="store_true",
                        help="Grava de verdade. Sem esta flag é dry-run.")
    parser.add_argument("--confirm", type=str, default=None,
                        help="Frase de confirmação para uso não-interativo.")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Lista documento por documento.")
    args = parser.parse_args()

    if not args.process_ids and args.tenant_id is None:
        parser.error("informe --process-id (repetível) ou --tenant-id")

    db = SessionLocal()
    try:
        # Sempre planeja primeiro: o dry-run é a base da confirmação, para a
        # frase digitada refletir o número real de gravações.
        previa = planejar_backfill(
            db, process_ids=args.process_ids, tenant_id=args.tenant_id, executar=False
        )

        if not args.execute:
            _print_report(previa, verbose=args.verbose)
            return 0

        n = len(previa.a_gravar)   # mesma contagem do relatório — uma fonte só
        if n == 0:
            _print_report(previa, verbose=args.verbose)
            print("\n  Nada a gravar — encerrando sem escrever.")
            return 0

        frase = _confirmation_phrase(n)
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

        rel = planejar_backfill(
            db, process_ids=args.process_ids, tenant_id=args.tenant_id, executar=True
        )
        db.commit()
        _print_report(rel, verbose=args.verbose)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
