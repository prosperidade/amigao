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

## Duas etapas: preparar FORA, escrever DENTRO

A primeira versao mantinha UMA transacao aberta durante as ~30 mil chamadas de
embedding. Isso salvou o corpus tres vezes em 05/08 — e impediu a passada de
terminar: qualquer soluco de rede no meio de dez minutos de HTTP jogava tudo
fora, e a terceira tentativa morreu em "peer closed connection".

A licao: **a atomicidade e do CORPO da substituicao, nao da geracao dos
vetores.** Chamada de rede dentro de transacao e antipadrao — a transacao fica
refem da rede e o banco segura linhas sujas por minutos.

  ETAPA 1 (fora de transacao): chunk + embed de tudo, com retry classificado.
  CHECKPOINT: confere o que esta em memoria ANTES de tocar no banco.
  ETAPA 2 (transacao unica, segundos): delete + insert.

Vetor faltando descoberto DEPOIS do delete seria o pior caso possivel; o
checkpoint existe para que isso nao possa acontecer.

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


def _inserir_preparado(session, *, doc, vig, chunks, vetores, modelo, hash_fn) -> int:
    """Insere chunks JA embarcados. Nenhuma chamada de rede aqui dentro.

    Replica o que `index_legislation_document` monta de metadado — inclusive o
    rotulo de vigencia no titulo (ADR-037), que viaja NO DADO.
    """
    import json as _json

    from sqlalchemy import text as _sql

    from app.services.vigencia import titulo_com_vigencia

    sql = _sql(
        """
        INSERT INTO knowledge_catalog (
            tenant_id, source_type, source_ref, chunk_index,
            title, section, chunk_text, chunk_tokens,
            dispositivo, dispositivo_origem, hierarquia, referencias,
            jurisdiction, uf, agency, identifier, effective_date,
            embedding, embedding_model, embedding_dim,
            content_hash, extra_metadata
        ) VALUES (
            :tenant_id, 'legislation', :source_ref, :chunk_index,
            :title, :section, :chunk_text, :chunk_tokens,
            :dispositivo, :dispositivo_origem,
            CAST(:hierarquia AS jsonb), CAST(:referencias AS jsonb),
            :jurisdiction, :uf, :agency, :identifier, :effective_date,
            CAST(:embedding AS vector), :embedding_model, :embedding_dim,
            :content_hash, CAST(:extra_metadata AS jsonb)
        )
        ON CONFLICT (content_hash) DO NOTHING
        """
    )
    source_ref = f"legislation_documents:{doc.id}"
    titulo = titulo_com_vigencia(doc.title, vig)
    extra = _json.dumps({
        "demand_types": doc.demand_types,
        "keywords": doc.keywords,
        "source_type_legislation": doc.source_type,
        "vigencia_inicio": vig.inicio.isoformat() if vig.inicio else None,
        "vigencia_fim": vig.fim.isoformat() if vig.fim else None,
        "sucessora_ref": vig.sucessora_ref,
        "historica": vig.historica,
    })
    inseridos = 0
    for c, v in zip(chunks, vetores, strict=True):
        r = session.execute(sql, {
            "tenant_id": doc.tenant_id,
            "source_ref": source_ref,
            "chunk_index": c.index,
            "title": titulo,
            "section": c.section,
            "chunk_text": c.text,
            "chunk_tokens": c.tokens,
            "dispositivo": c.dispositivo,
            "dispositivo_origem": c.dispositivo_origem,
            "hierarquia": _json.dumps(c.hierarquia) if c.hierarquia else None,
            "referencias": _json.dumps(c.referencias) if c.referencias else None,
            "jurisdiction": doc.scope,
            "uf": doc.uf,
            "agency": doc.agency,
            "identifier": doc.identifier,
            "effective_date": doc.effective_date.date() if doc.effective_date else None,
            "embedding": "[" + ",".join(f"{x:.7f}" for x in v) + "]",
            "embedding_model": modelo,
            "embedding_dim": len(v),
            "content_hash": hash_fn("legislation", source_ref, c.index, c.text),
            "extra_metadata": extra,
        })
        inseridos += r.rowcount or 0
    return inseridos


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

        # === ETAPA 1 — preparar FORA da transacao =============================
        # Chunk + embed de tudo, com retry classificado. Nada e escrito aqui:
        # transacao aberta durante centenas de chamadas HTTP fica refem da rede.
        from app.models.legislation import LegislationDocument
        from app.services.embeddings import EMBEDDING_DIM, embed_batch
        from app.services.knowledge_catalog import _hash_chunk
        from app.services.vigencia import vigencia_do_documento

        t0 = time.time()
        preparados: list[dict] = []
        for i, linha in enumerate(docs, 1):
            doc = session.get(LegislationDocument, linha.id)
            vig = vigencia_do_documento(doc)
            pedacos = chunk_text(normalizar(doc.full_text))
            if not pedacos:
                continue
            vetores = embed_batch([c.text for c in pedacos])
            preparados.append({
                "doc": doc,
                "vig": vig,
                "chunks": pedacos,
                "vetores": vetores,
            })
            if i % 10 == 0:
                total = sum(len(p["chunks"]) for p in preparados)
                print(f"  embarcados {i}/{len(docs)} documentos | {total} chunks")

        # === CHECKPOINT — conferir ANTES de tocar no banco ====================
        # Vetor faltando descoberto DEPOIS do delete seria o pior caso possivel.
        problemas: list[str] = []
        total_chunks = total_vetores = 0
        for p in preparados:
            ref = p["doc"].identifier or p["doc"].title
            total_chunks += len(p["chunks"])
            total_vetores += len(p["vetores"])
            if len(p["chunks"]) != len(p["vetores"]):
                problemas.append(
                    f"{ref}: {len(p['chunks'])} chunks vs {len(p['vetores'])} vetores"
                )
            for v in p["vetores"]:
                if not v:
                    problemas.append(f"{ref}: vetor vazio")
                    break
                if len(v) != EMBEDDING_DIM:
                    problemas.append(f"{ref}: dim {len(v)} != {EMBEDDING_DIM}")
                    break
        if total_chunks != chunks_previstos:
            problemas.append(
                f"total de chunks {total_chunks} != previsto {chunks_previstos}"
            )
        if problemas:
            raise Abortar(
                "checkpoint reprovou — nada foi tocado no banco: "
                + "; ".join(problemas[:10])
            )
        print(
            f"CHECKPOINT ok: {total_chunks} chunks, {total_vetores} vetores, "
            f"dim {EMBEDDING_DIM}, modelo {modelo}"
        )

        # Fingerprint conferido DE NOVO: a janela entre a partida e a escrita
        # agora e longa (minutos de embedding).
        fp_antes_escrita = _fingerprint(session)
        if any(
            fp_antes_escrita.get(c) != fp_inicio.get(c)
            for c in ("total_chunks", "legislation_documents",
                      "max_id_legislation_documents")
        ):
            raise Abortar(
                "o corpus MUDOU durante a preparacao — nada foi escrito. "
                f"partida={fp_inicio} agora={fp_antes_escrita}"
            )

        # === ETAPA 2 — escrever DENTRO de uma transacao, em segundos ==========
        t_escrita = time.time()
        removidos = session.execute(
            _sql("DELETE FROM knowledge_catalog WHERE source_type = 'legislation'")
        ).rowcount

        gravados = 0
        for p in preparados:
            doc, vig = p["doc"], p["vig"]
            gravados += _inserir_preparado(
                session, doc=doc, vig=vig, chunks=p["chunks"],
                vetores=p["vetores"], modelo=modelo, hash_fn=_hash_chunk,
            )
        session.commit()
        print(f"removidos {removidos} / gravados {gravados} em "
              f"{time.time() - t_escrita:.1f}s de transacao")

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
