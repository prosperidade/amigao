"""Recorta os dispositivos do catálogo com a regra atual, preservando IDs (dívida #274).

    python scripts/zona_normativa_recortar.py                     # só mede (padrão)
    python scripts/zona_normativa_recortar.py --aplicar           # grava e embarca os trechos novos
    python scripts/zona_normativa_recortar.py --saida relatorio.json

Varre toda versão articulada do banco do `.env`. Dispositivo com o mesmo caminho e hash
mantém o ID; o que sai é apagado com seus trechos; o que entra é criado e embarcado.
Para, sem gravar nada daquela versão, se um dispositivo que sairia estiver citado pelo
motor jurídico ou pela Rota. Cada versão é uma transação.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.services.zona_normativa import catalogo  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aplicar", action="store_true", help="grava (padrão: só mede)")
    ap.add_argument("--saida", help="relatório JSON")
    args = ap.parse_args()

    embed = modelo = None
    if args.aplicar:
        from app.services.embeddings import current_model, embed_batch  # noqa: PLC0415

        embed, modelo = embed_batch, current_model()

    session = SessionLocal()
    alvo = session.execute(text("SELECT current_database(), inet_server_addr(), inet_server_port()")).one()
    print(f"banco: {alvo[0]} em {alvo[1]}:{alvo[2]} · {'APLICAR' if args.aplicar else 'medir'}")
    versoes = session.execute(text(
        "SELECT v.id, f.rotulo, v.texto FROM fonte_normativa_versao v JOIN fonte_normativa f ON f.id = v.fonte_id "
        "WHERE EXISTS (SELECT 1 FROM dispositivo d WHERE d.fonte_versao_id = v.id AND d.tipo = 'artigo') "
        "ORDER BY v.id"
    )).all()
    afetadas, recusadas = [], []
    for vid, rotulo, texto in versoes:
        try:
            rec = catalogo.reaplicar_dispositivos(
                session, vid, rotulo=rotulo, texto=texto, embed=embed, modelo_embedding=modelo,
                aplicar=args.aplicar,
            )
        except catalogo.DispositivoCitado as exc:
            session.rollback()
            recusadas.append({"versao": vid, "fonte": rotulo, "motivo": str(exc)})
            continue
        if args.aplicar:
            session.commit()
        if rec.saem or rec.entram:
            afetadas.append({"versao": vid, "fonte": rotulo, "mantidos": rec.mantidos, "saem": len(rec.saem),
                             "entram": len(rec.entram), "trechos_removidos": rec.trechos_removidos,
                             "trechos_novos": rec.trechos_novos, "entram_caminhos": rec.entram})
    if not args.aplicar:
        session.rollback()
    session.close()
    rel = {
        "aplicado": args.aplicar, "versoes_articuladas": len(versoes), "versoes_afetadas": len(afetadas),
        "dispositivos_mantidos_nas_afetadas": sum(a["mantidos"] for a in afetadas),
        "dispositivos_saem": sum(a["saem"] for a in afetadas),
        "dispositivos_entram": sum(a["entram"] for a in afetadas),
        "trechos_removidos": sum(a["trechos_removidos"] for a in afetadas),
        "trechos_novos": sum(a["trechos_novos"] for a in afetadas),
        "recusadas": recusadas, "afetadas": afetadas,
    }
    print(json.dumps({k: v for k, v in rel.items() if k != "afetadas"}, ensure_ascii=False, indent=1))
    if args.saida:
        pathlib.Path(args.saida).write_text(json.dumps(rel, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if recusadas else 0


if __name__ == "__main__":
    raise SystemExit(main())
