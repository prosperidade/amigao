"""
scripts/reindexar_chunking.py — a reindexacao UNICA da remediacao do chunking.

As Fases 1-3 mudaram o CHUNKER e nao tocaram no indice. Este script e a unica
passada de escrita: reprocessa os `legislation_documents` com o chunker novo e a
normalizacao de ligaduras (#122), tudo de uma vez.

## Por que nao serve `reindex_legislation_by_uf.py`

Aquele script e **idempotente por `content_hash`**: pula chunk cujo hash ja
existe. Aqui o texto de TODO chunk mudou (fronteira, teto, ligadura), entao todo
hash e novo — ele nao pularia nada e tambem nao apagaria nada. O resultado seria
o corpus **somado**: ~30 mil chunks velhos convivendo com ~30 mil novos, duas
estrategias de chunking misturadas no mesmo indice. Pior que nao reindexar.

Por isso aqui a passada e **apagar e reescrever**, e por isso ela exige backup.

## Travas

- **Fingerprint de partida por IGUALDADE** (nao piso): corpus fora do estado
  esperado nao reindexa. Mesma regra que salvou o baseline.
- **Espaco vetorial travado**: provider e modelo conferidos ANTES; divergencia
  aborta alto. Nunca ha fallback — reindexar metade num espaco e metade noutro
  produz um indice que responde e mente (ADR-040).
- **Teto de custo**: aborta acima de `--custo-maximo` (padrao US$ 2,00).
- **Dry-run e o padrao.** Escrever exige `--executar`.
- **Nao deduplica.** Duplicata que fique visivel e achado para a #121, nao
  material para apagar: remover copia sem antes resolver a atribuicao destruiria
  a evidencia de qual identidade e a legitima.

Uso:
    python scripts/reindexar_chunking.py                 # dry-run
    python scripts/reindexar_chunking.py --executar
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Estado exigido na partida (mesmo do baseline 2e78917).
ESTADO_ESPERADO = {"total_chunks": 31_298, "legislation_documents": 102}

# Espaco vetorial da casa. Travado, nao inferido.
MODELO_ESPERADO = "text-embedding-3-small"
DIM_ESPERADA = 768

# text-embedding-3-small: US$ 0,020 por 1M de tokens (tabela OpenAI).
USD_POR_MILHAO_TOKENS = 0.020


class Abortar(RuntimeError):
    """Condicao de seguranca nao satisfeita. Nada foi escrito."""


def _fingerprint(session) -> dict:
    from sqlalchemy import text as _sql

    linhas = session.execute(
        _sql(
            "SELECT coalesce(source_type,'?') st, count(*) n "
            "FROM knowledge_catalog GROUP BY 1 ORDER BY 2 DESC"
        )
    ).all()
    por_source = {r.st: int(r.n) for r in linhas}
    espacos = [
        {"modelo": r.m, "dim": r.d, "chunks": int(r.n)}
        for r in session.execute(
            _sql(
                "SELECT coalesce(embedding_model,'?') m, embedding_dim d, count(*) n "
                "FROM knowledge_catalog GROUP BY 1,2 ORDER BY 3 DESC"
            )
        ).all()
    ]
    return {
        "total_chunks": sum(por_source.values()),
        "por_source_type": por_source,
        "legislation_documents": int(
            session.execute(_sql("SELECT count(*) FROM legislation_documents")).scalar() or 0
        ),
        "max_id_legislation_documents": int(
            session.execute(_sql("SELECT max(id) FROM legislation_documents")).scalar() or 0
        ),
        "espacos_no_indice": espacos,
    }


def _exigir_espaco_vetorial() -> str:
    """Provider e modelo conferidos ANTES de qualquer escrita."""
    from app.services import embeddings as emb

    modelo = emb.current_model()
    if MODELO_ESPERADO not in modelo:
        raise Abortar(
            f"espaco vetorial divergente: configurado {modelo!r}, esperado "
            f"{MODELO_ESPERADO!r}. Reindexar noutro espaco produz indice que "
            "responde e mente (ADR-040). Nada foi escrito."
        )
    return modelo


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--executar", action="store_true", help="escreve (padrao: dry-run)")
    p.add_argument("--custo-maximo", type=float, default=2.00)
    p.add_argument("--out-dir", type=Path, default=Path("ops/medicao_chunking"))
    args = p.parse_args()

    from sqlalchemy import text as _sql

    from app.db.session import SessionLocal
    from app.services.chunking import chunk_text
    from app.services.normalizacao import conta_ligaduras, normalizar

    session = SessionLocal()
    try:
        modelo = _exigir_espaco_vetorial()

        fp_inicio = _fingerprint(session)
        divergencias = [
            f"{c}: encontrado {fp_inicio.get(c)}, esperado {e}"
            for c, e in ESTADO_ESPERADO.items()
            if fp_inicio.get(c) != e
        ]
        if divergencias:
            raise Abortar(
                "corpus fora do estado esperado: " + "; ".join(divergencias)
                + ". Nada foi escrito."
            )

        docs = session.execute(
            _sql(
                "SELECT id, coalesce(identifier, title) AS ident, full_text "
                "FROM legislation_documents WHERE full_text IS NOT NULL "
                "AND length(full_text) > 0 ORDER BY id"
            )
        ).all()

        # --- dry-run: quanto vai custar, sem gastar nada -----------------------
        chunks_previstos = 0
        tokens_previstos = 0
        ligaduras = 0
        for d in docs:
            texto = normalizar(d.full_text)
            ligaduras += conta_ligaduras(d.full_text)
            for c in chunk_text(texto):
                chunks_previstos += 1
                tokens_previstos += c.tokens

        custo = tokens_previstos / 1_000_000 * USD_POR_MILHAO_TOKENS
        a_remover = fp_inicio["por_source_type"].get("legislation", 0)

        print("=" * 66)
        print(f"REINDEXACAO DO CHUNKING — {'EXECUCAO' if args.executar else 'DRY-RUN'}")
        print("=" * 66)
        print(f"espaco vetorial      : {modelo} ({DIM_ESPERADA}d) — conferido")
        print(
            f"fingerprint partida  : {fp_inicio['total_chunks']} chunks / "
            f"{fp_inicio['legislation_documents']} docs / "
            f"max id {fp_inicio['max_id_legislation_documents']}"
        )
        print(f"documentos a reprocessar : {len(docs)}")
        print(f"chunks a REMOVER         : {a_remover}  (source_type='legislation')")
        print(f"chunks a GRAVAR          : {chunks_previstos}")
        print(f"tokens a embarcar        : {tokens_previstos}")
        print(f"CUSTO ESTIMADO           : US$ {custo:.4f}   (teto US$ {args.custo_maximo:.2f})")
        print(f"ligaduras normalizadas   : {ligaduras} ocorrencias")
        print("=" * 66)

        if custo > args.custo_maximo:
            raise Abortar(
                f"custo estimado US$ {custo:.4f} acima do teto US$ "
                f"{args.custo_maximo:.2f}. Nada foi escrito."
            )

        if not args.executar:
            print("DRY-RUN — nada foi escrito. Use --executar para valer.")
            return 0

        # --- escrita ----------------------------------------------------------
        from app.services.knowledge_catalog import index_legislation_document

        t0 = time.time()
        removidos = session.execute(
            _sql("DELETE FROM knowledge_catalog WHERE source_type = 'legislation'")
        ).rowcount
        session.flush()
        print(f"removidos: {removidos} chunks")

        gravados = 0
        for i, d in enumerate(docs, 1):
            gravados += index_legislation_document(session, d.id)
            if i % 10 == 0:
                print(f"  {i}/{len(docs)} documentos | {gravados} chunks gravados")
        session.commit()

        fp_fim = _fingerprint(session)
        resultado = {
            "modelo": modelo,
            "documentos": len(docs),
            "chunks_removidos": removidos,
            "chunks_gravados": gravados,
            "tokens_embarcados": tokens_previstos,
            "custo_estimado_usd": round(custo, 4),
            "duracao_s": round(time.time() - t0, 1),
            "ligaduras_normalizadas": ligaduras,
            "fingerprint_inicio": fp_inicio,
            "fingerprint_fim": fp_fim,
        }
        args.out_dir.mkdir(parents=True, exist_ok=True)
        destino = args.out_dir / "reindexacao_fase4.json"
        destino.write_text(
            json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        print("=" * 66)
        print(f"gravados: {gravados} chunks em {resultado['duracao_s']}s")
        print(
            f"fingerprint fim: {fp_fim['total_chunks']} chunks / "
            f"{fp_fim['legislation_documents']} docs"
        )
        # Variacao de contagem e ACHADO, nao ajuste: reportar, nunca "corrigir".
        delta = fp_fim["total_chunks"] - fp_inicio["total_chunks"]
        print(f"variacao total: {delta:+d} chunks  (achado, nao ajuste)")
        print(f"escrito: {destino}")
        return 0
    except Abortar as e:
        session.rollback()
        print(f"ABORTADO: {e}")
        return 2
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
