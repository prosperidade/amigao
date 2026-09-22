"""Roda as sondas de recuperação (ADR-075 §9) contra o catálogo do banco do `.env`.

    python scripts/sondas_recuperacao.py                 # usa o cache de vetores
    python scripts/sondas_recuperacao.py --embarcar      # embarca perguntas fora do cache
    python scripts/sondas_recuperacao.py --saida r.json  # grava o relatório

Onde roda (decisão 4 do André, 18/09): PR que toque recuperação, corpus, chunking
ou embedding + rodada noturna completa, sobre corpus de homologação. O contrato
(filtro, vazio com razão, vaga por dispositivo, citação por ID) roda em todo PR
em `tests/recuperacao/` com vetores sintéticos.

Sai com código 1 se o portão não passar (recall@5 ≥ 0,9; controle negativo 100%;
zero citação órfã). Sondas verdes são condição para religar a Legislação (decisão 6).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal  # noqa: E402
from app.services.zona_normativa import sondas  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--embarcar", action="store_true", help="embarca perguntas fora do cache (chamada paga)")
    ap.add_argument("--saida", help="relatório JSON")
    args = ap.parse_args()

    from app.services.embeddings import current_model  # noqa: PLC0415

    modelo = current_model()
    lista = sondas.carregar_sondas()
    erros = sondas.validar_formato(lista)
    if erros:
        print("formato inválido:", *erros, sep="\n  ")
        return 2
    vetores = sondas.carregar_vetores()
    faltam = [s for s in lista if s.get("pergunta") and sondas.chave_vetor(modelo, s["pergunta"]) not in vetores]
    if faltam and args.embarcar:
        from app.services.embeddings import embed_text  # noqa: PLC0415

        for s in faltam:
            vetores[sondas.chave_vetor(modelo, s["pergunta"])] = embed_text(s["pergunta"], task_type="RETRIEVAL_QUERY")
        sondas.salvar_vetores(vetores)
        print(f"embarcadas {len(faltam)} perguntas; cache em {sondas.ARQUIVO_VETORES}")
    elif faltam:
        print(f"{len(faltam)} perguntas fora do cache; rode com --embarcar")

    session = SessionLocal()
    try:
        rel = sondas.rodar(session, lista, vetores=vetores, modelo=modelo)
    finally:
        session.rollback()
        session.close()
    for r in rel["resultados"]:
        print(f"{'OK ' if r['ok'] else 'XX '} {r['grupo']:<22} {r['id']:<34} {r['detalhe']}")
    print(json.dumps({k: v for k, v in rel.items() if k != "resultados"}, ensure_ascii=False))
    if args.saida:
        pathlib.Path(args.saida).write_text(json.dumps(rel, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if rel["portao"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
