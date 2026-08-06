"""
scripts/medir_chunking_estrutural.py — métrica ESTRUTURAL do chunker (#117).

Roda o chunker sobre o `full_text` dos documentos e conta o que o chunker faz
com o texto. **Não toca no índice** e não depende dele: por isso pode ser medida
a cada fase da remediação, enquanto a métrica de recuperação só faz sentido
depois da reindexação única da Fase 4.

O que separa — e a separação é o ponto:

  · **artigo grande legítimo** — dispositivo extenso de verdade (o `Art. 61-A`
    do Código Florestal tem 4.644 tokens). Cortá-lo por tamanho é a estratégia
    funcionando, não defeito.

  · **fatia absorvedora** — fatia rotulada como artigo que engoliu material que
    não é daquele artigo. Medido em 04/08: o `Art. 51.` do MT-NUC01 tem
    1.045.121 chars e **nenhum outro cabeçalho de artigo dentro**; o texto
    simplesmente deixou de ser articulado (sumário paginado, rodapé de captura
    web, listas de diretrizes). **Isto é o defeito, e deve ir a zero.**

Medir sobre a mistura mediria o defeito e chamaria de estratégia.

Uso:
    python scripts/medir_chunking_estrutural.py --rotulo antes_fase1
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Artigo de vigência ("Esta Lei entra em vigor...") é sempre uma frase. Quando
# aparece gigante, é porque absorveu tudo que vinha depois — é o último artigo
# da norma, e no compêndio o que vem depois é anexo ou outra norma.
_RE_VIGENCIA = re.compile(
    r"entrar?[áa]?\s+em\s+vigor|revogam-se|produz\s+efeitos", re.IGNORECASE
)


def _percentis(valores: list[int]) -> dict:
    if not valores:
        return {}
    v = sorted(valores)

    def p(q: float) -> int:
        return v[min(len(v) - 1, int(len(v) * q))]

    return {
        "p50": p(0.50), "p90": p(0.90), "p95": p(0.95),
        "p99": p(0.99), "p999": p(0.999), "max": v[-1],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--rotulo", required=True)
    p.add_argument("--out-dir", type=Path, default=Path("ops/medicao_chunking"))
    p.add_argument(
        "--sem-guarda",
        action="store_true",
        help="desliga a guarda de sanidade no chunker (mede o comportamento ANTERIOR)",
    )
    p.add_argument(
        "--max-artigo",
        type=int,
        default=None,
        help="sobrescreve MAX_ARTIGO_TOKENS (para medir o teto anterior)",
    )
    args = p.parse_args()

    from sqlalchemy import text as _sql

    from app.db.session import SessionLocal
    from app.services.chunking import (
        _PATTERNS,
        LIMITE_ARTIGO_TOKENS,
        MAX_TOKENS,
        ROTULO_NAO_ARTICULADO,
        _approx_tokens,
        _split_by_pattern,
        chunk_text,
    )

    # A DEFINIÇÃO do defeito é fixa e vem do texto, não da versão do chunker.
    # Capturada antes de qualquer monkeypatch: sem isso, desligar a guarda
    # zeraria o defeito por construção — mediria o instrumento, não o conserto.
    LIMITE = LIMITE_ARTIGO_TOKENS

    import app.services.chunking as _ch

    if args.sem_guarda:
        _ch.LIMITE_ARTIGO_TOKENS = 10**9
    if args.max_artigo is not None:
        # Permite medir o teto ANTERIOR sem reverter codigo. A classificacao do
        # defeito continua vindo de LIMITE, capturado acima.
        _ch.MAX_ARTIGO_TOKENS = args.max_artigo

    art = dict(_PATTERNS)["artigo"]
    session = SessionLocal()
    try:
        docs = session.execute(
            _sql(
                "SELECT coalesce(identifier, title) AS ident, full_text "
                "FROM legislation_documents WHERE full_text IS NOT NULL "
                "AND length(full_text) > 0 ORDER BY id"
            )
        ).all()

        tamanhos: list[int] = []
        legitimos: list[dict] = []   # MAX_TOKENS < n <= LIMITE  → corte por tamanho, ok
        absorvedoras: list[dict] = []  # n > LIMITE → defeito
        chunks_totais = 0
        chunks_rotulo_artigo = 0
        chunks_rotulo_honesto = 0
        chunks_artigo_partido = 0
        tam_chunks: list[int] = []

        for d in docs:
            fatias = _split_by_pattern(d.full_text, art)
            if len(fatias) > 1:
                for _off, corpo in fatias:
                    if not art.match(corpo):
                        continue
                    corpo = corpo.strip()
                    n = _approx_tokens(corpo)
                    tamanhos.append(n)
                    if n > LIMITE:
                        absorvedoras.append({
                            "documento": d.ident,
                            "rotulo": " ".join(corpo[:60].split()),
                            "tokens": n,
                            "e_artigo_de_vigencia": bool(_RE_VIGENCIA.search(corpo[:300])),
                        })
                    elif n > MAX_TOKENS:
                        legitimos.append({
                            "documento": d.ident,
                            "rotulo": " ".join(corpo[:60].split()),
                            "tokens": n,
                        })

            # O que sai de fato: quantos chunks carregam rótulo de artigo falso.
            for c in chunk_text(d.full_text):
                chunks_totais += 1
                tam_chunks.append(c.tokens)
                if c.section and art.match(c.section):
                    chunks_rotulo_artigo += 1
                    if "(parte" in c.section:
                        chunks_artigo_partido += 1
                elif c.section and c.section.startswith(ROTULO_NAO_ARTICULADO):
                    chunks_rotulo_honesto += 1

        # BASE DA MEDIÇÃO — declarada ao lado do resultado.
        #
        # O baseline de recuperação (2e78917) usa 31.298 = `knowledge_catalog`
        # INTEIRO. Esta métrica usa 30.104 = só o que vem de
        # `legislation_documents`. Números de bases diferentes não se comparam,
        # e o antes/depois inteiro se apoia nisso.
        por_source = {
            r.st: int(r.n)
            for r in session.execute(
                _sql(
                    "SELECT coalesce(source_type,'(null)') st, count(*) n "
                    "FROM knowledge_catalog GROUP BY 1 ORDER BY 2 DESC"
                )
            ).all()
        }

        resultado = {
            "rotulo": args.rotulo,
            "base_da_medicao": {
                "o_que_e_medido": (
                    "re-chunking do full_text de legislation_documents — "
                    "NAO e o knowledge_catalog inteiro"
                ),
                "equivalente_no_indice": (
                    "knowledge_catalog WHERE source_type='legislation'"
                ),
                "chunks_no_indice_por_source_type": por_source,
                "total_knowledge_catalog": sum(por_source.values()),
                "query_total": "SELECT count(*) FROM knowledge_catalog",
                "query_recorte": (
                    "SELECT count(*) FROM knowledge_catalog "
                    "WHERE source_type='legislation'"
                ),
            },
            "documentos": len(docs),
            "limite_artigo_tokens": LIMITE,
            "guarda_ativa": not args.sem_guarda,
            "max_tokens": MAX_TOKENS,
            "max_artigo_tokens": _ch.MAX_ARTIGO_TOKENS,
            "fatias_de_artigo": len(tamanhos),
            "distribuicao_tokens": _percentis(tamanhos),
            "artigos_grandes_legitimos": {
                "definicao": f"{MAX_TOKENS} < tokens <= {LIMITE} — corte por tamanho é a estratégia",
                "quantidade": len(legitimos),
                "exemplos": sorted(legitimos, key=lambda x: -x["tokens"])[:10],
            },
            "fatias_absorvedoras": {
                "definicao": f"tokens > {LIMITE} — DEFEITO, deve ir a zero",
                "quantidade": len(absorvedoras),
                "das_quais_artigo_de_vigencia": sum(
                    1 for a in absorvedoras if a["e_artigo_de_vigencia"]
                ),
                "exemplos": sorted(absorvedoras, key=lambda x: -x["tokens"])[:15],
            },
            "chunks": {
                "total": chunks_totais,
                "com_rotulo_de_artigo": chunks_rotulo_artigo,
                "com_rotulo_honesto_nao_articulado": chunks_rotulo_honesto,
                "de_artigo_PARTIDO_por_tamanho": chunks_artigo_partido,
                "distribuicao_tokens": _percentis(tam_chunks),
            },
        }

        args.out_dir.mkdir(parents=True, exist_ok=True)
        destino = args.out_dir / f"{args.rotulo}.json"
        destino.write_text(
            json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"escrito: {destino}")
        print(
            f"  fatias de artigo: {len(tamanhos)} | "
            f"legítimas grandes: {len(legitimos)} | "
            f"ABSORVEDORAS: {len(absorvedoras)}"
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
