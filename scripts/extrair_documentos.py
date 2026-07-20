"""Extração em lote com ESCOPO explícito — dívida #78.

A rota `POST /processes/{id}/extract` processa **todos** os documentos do
processo. Para o caso 15 isso significaria pagar LLM em 42 documentos, sendo que
10 já estão lidos. Este script roda só nos documentos escolhidos.

  DRY-RUN É O DEFAULT. Sem ``--execute`` nada roda — só lista o escopo e o
  volume de texto que seria enviado ao provider.

Execução **síncrona** (não enfileira no Celery): um documento por vez, com o
custo real de cada AIJob impresso ao fim. É mais lento e é de propósito — o
objetivo é ver o gasto acontecendo, não disparar 20 tasks no escuro.

Uso (dentro do container api):

    # Dry-run com escopo explícito
    python scripts/extrair_documentos.py --document-id 322 --document-id 324

    # Todos os do processo que ainda não têm staging
    python scripts/extrair_documentos.py --process-id 15 --sem-staging

    # Execução real
    python scripts/extrair_documentos.py --document-id 322 --execute

    # Teto de custo: aborta o lote se o acumulado passar do limite
    python scripts/extrair_documentos.py --process-id 15 --sem-staging --execute \\
        --teto-usd 1.00
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal  # noqa: E402
from app.models.extracted_field_staging import ExtractedFieldStaging  # noqa: E402
from app.services.extracao_lote import coletar_escopo  # noqa: E402


def _print_escopo(docs) -> int:
    print(f"\n== Extração em lote · {len(docs)} documento(s) no escopo ==")
    total_chars = 0
    por_tipo: dict[str, list[int]] = {}
    for d in docs:
        n = len(d.extracted_text or "")
        total_chars += n
        por_tipo.setdefault(d.document_type or "(sem tipo)", []).append(n)

    for tipo, tamanhos in sorted(por_tipo.items(), key=lambda kv: -sum(kv[1])):
        print(f"  {tipo:<22} {len(tamanhos):>3} doc(s)  {sum(tamanhos):>8} chars "
              f"(~{sum(tamanhos)//4} tokens)")
    print(f"  {'TOTAL':<22} {len(docs):>3} doc(s)  {total_chars:>8} chars "
          f"(~{total_chars//4} tokens de entrada)")
    return total_chars


def main() -> int:
    parser = argparse.ArgumentParser(description="Extração em lote com escopo (#78).")
    parser.add_argument("--document-id", type=int, action="append", dest="document_ids")
    parser.add_argument("--process-id", type=int, action="append", dest="process_ids")
    parser.add_argument("--sem-staging", action="store_true",
                        help="Só documentos que ainda não têm nenhuma linha de staging.")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--teto-usd", type=float, default=None,
                        help="Aborta o lote se o custo acumulado passar deste valor.")
    parser.add_argument("--confirm", type=str, default=None)
    args = parser.parse_args()

    if not args.document_ids and not args.process_ids:
        parser.error("informe --document-id e/ou --process-id")

    db = SessionLocal()
    try:
        escopo = coletar_escopo(db, document_ids=args.document_ids,
                                process_ids=args.process_ids,
                                sem_staging=args.sem_staging)
        docs = escopo.documentos
        if not docs:
            print("\nNenhum documento no escopo — nada a fazer.")
            return 0

        _print_escopo(docs)
        if escopo.sem_texto:
            print(f"  AVISO: sem texto (serão pulados): {escopo.sem_texto}")
        if escopo.sem_tipo:
            print(f"  AVISO: sem document_type (extração genérica): {escopo.sem_tipo}")

        if not args.execute:
            print("\n  DRY-RUN — nada foi enviado ao provider. Repita com --execute.")
            return 0

        frase = f"extrair {len(docs)} documento(s)"
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
            print("ERRO: frase não confere. Nada foi executado.", file=sys.stderr)
            return 2

        from app.agents import AgentContext, AgentRegistry  # noqa: PLC0415
        from app.models.ai_job import AIJob  # noqa: PLC0415

        custo_total = 0.0
        print()
        for i, doc in enumerate(docs, 1):
            if not (doc.extracted_text or "").strip():
                print(f"  [{i}/{len(docs)}] doc {doc.id}: sem texto — pulado")
                continue

            ctx = AgentContext(
                tenant_id=doc.tenant_id,
                user_id=None,
                process_id=doc.process_id,
                session=db,
                metadata={"document_id": doc.id},
            )
            agent = AgentRegistry.create("extrator", ctx)
            resultado = agent.run()
            db.commit()

            custo = 0.0
            job_id = getattr(resultado, "ai_job_id", None)
            if job_id:
                job = db.query(AIJob).filter(AIJob.id == job_id).first()
                custo = float(getattr(job, "cost_usd", 0) or 0)
            custo_total += custo

            n_staging = (
                db.query(ExtractedFieldStaging)
                .filter(ExtractedFieldStaging.document_id == doc.id)
                .count()
            )
            status = "ok" if getattr(resultado, "success", False) else "FALHOU"
            # Auto de infração não vai para o staging: é FATO DE PASSIVO e sai no
            # `AIJob.result["auto_infracao_fato"]`. Reportar "staging: 0" para eles
            # pareceria falha quando é o caminho correto.
            dados = getattr(resultado, "data", None) or {}
            fato = dados.get("auto_infracao_fato") if isinstance(dados, dict) else None
            if fato:
                numero = fato.get("numero_auto") or fato.get("numero") or "s/nº"
                efeito = f"FATO auto {numero}"
            else:
                efeito = f"staging agora: {n_staging}"
            print(f"  [{i}/{len(docs)}] doc {doc.id} ({doc.document_type}): {status} · "
                  f"job {job_id} · ${custo:.4f} · {efeito}")

            if args.teto_usd is not None and custo_total > args.teto_usd:
                print(f"\n  TETO DE CUSTO ATINGIDO (${custo_total:.4f} > "
                      f"${args.teto_usd:.2f}) — lote interrompido.")
                break

        print(f"\n  Custo real do lote: ${custo_total:.4f}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
