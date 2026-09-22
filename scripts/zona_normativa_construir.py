"""Constrói o catálogo normativo (ADR-075) a partir do corpus legado — DRY-RUN por padrão.

    python scripts/zona_normativa_construir.py                       # só relatório
    python scripts/zona_normativa_construir.py --relatorio saida.json
    python scripts/zona_normativa_construir.py --aplicar --originais ../legislacao ...

O dry-run é o que a revisão humana das fronteiras lê: por coletânea, cada ato
cortado, com sinal, páginas, cabeçalho, identidade e motivos de revisão. Não
contém texto de norma — só contagens e cabeçalhos.

`--aplicar` grava no banco apontado pelo `.env` e embarca os trechos. Recusa
banco de produção e catálogo com validação registrada. Imprime o alvo antes.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.zona_normativa import catalogo  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aplicar", action="store_true", help="grava no banco (padrão: dry-run)")
    ap.add_argument("--reconstruir", action="store_true",
                    help="apaga o catálogo antes (recusado se houver validação registrada)")
    ap.add_argument("--originais", nargs="*", default=[], help="pastas com os arquivos originais (A5)")
    ap.add_argument("--relatorio", help="grava o relatório de dry-run em JSON")
    ap.add_argument("--documentos", nargs="*", type=int, help="restringe a estes legislation_documents.id")
    ap.add_argument("--dev-descartar-validacoes", action="store_true",
                    help="SÓ DEV: apaga validacao_norma (desligando o gatilho append-only) para "
                         "reconstruir o catálogo. Em produção a trilha não se apaga — nova "
                         "ingestão entra como versão nova")
    ap.add_argument("--ligar-originais-por-nome", nargs="*", metavar="PASTA",
                    help="só liga originais (A5) às fontes SEMAD pelo nome do arquivo e sai")
    args = ap.parse_args()

    url = make_url(str(settings.SQLALCHEMY_DATABASE_URI))
    print(f"alvo: host={url.host} porta={url.port} banco={url.database} usuario={url.username} "
          f"ENVIRONMENT={settings.ENVIRONMENT}")
    escreve = args.aplicar or args.ligar_originais_por_nome is not None
    if escreve and (settings.ENVIRONMENT == "production" or url.host not in ("127.0.0.1", "localhost", "db")):
        print("RECUSADO: escrita do catálogo só em banco de desenvolvimento.")
        return 2

    session = SessionLocal()
    if args.ligar_originais_por_nome is not None:
        from app.services.storage import get_storage_service  # noqa: PLC0415
        from app.services.zona_normativa.integridade import guardar_original  # noqa: PLC0415

        storage = get_storage_service()
        try:
            out = catalogo.ligar_originais_por_nome(
                session, raizes=[pathlib.Path(p) for p in args.ligar_originais_por_nome],
                guardar=lambda caminho, sha: guardar_original(storage, caminho, sha),
            )
            session.commit()
            print("originais ligados:", out)
            return 0
        finally:
            session.close()
    try:
        t0 = time.time()
        plano = catalogo.planejar(
            session, raizes_originais=[pathlib.Path(p) for p in args.originais],
            apenas_documentos=args.documentos,
        )
        for linha in catalogo.resumo_relatorio(plano):
            print(linha)
        custo = catalogo.estimar_embedding(plano)
        print("embedding:", custo)
        print(f"planejamento: {time.time() - t0:.1f}s")
        if args.relatorio:
            pathlib.Path(args.relatorio).write_text(json.dumps({
                "resumo": plano.resumo(), "embedding": custo,
                "originais": {str(k): v[0] for k, v in plano.originais.items()},
                "coletaneas": plano.relatorio_coletaneas,
            }, ensure_ascii=False, indent=1), encoding="utf-8")
            print("relatório:", args.relatorio)
        if not args.aplicar:
            print("DRY-RUN — nada gravado.")
            return 0

        from app.services.embeddings import current_model, embed_batch  # noqa: PLC0415
        from app.services.storage import get_storage_service  # noqa: PLC0415
        from app.services.zona_normativa.integridade import guardar_original  # noqa: PLC0415

        if args.dev_descartar_validacoes:
            from sqlalchemy import text as _sql  # noqa: PLC0415

            n = session.execute(_sql("SELECT count(*) FROM validacao_norma")).scalar_one()
            print(f"SÓ DEV: descartando {n} validações de prova (gatilho desligado e religado).")
            session.execute(_sql("ALTER TABLE validacao_norma DISABLE TRIGGER USER"))
            session.execute(_sql("DELETE FROM validacao_norma"))
            session.execute(_sql("ALTER TABLE validacao_norma ENABLE TRIGGER USER"))
        if args.reconstruir:
            catalogo.limpar_catalogo(session)
        storage = get_storage_service()
        chaves = {
            doc_id: guardar_original(storage, pathlib.Path(caminho), sha)
            for doc_id, (sha, caminho) in plano.originais.items()
        }
        print(f"originais guardados: {len(chaves)}")
        contagem = catalogo.aplicar(
            session, plano, embed=embed_batch, modelo_embedding=current_model(),
            originais_storage=chaves, progresso=print,
        )
        session.commit()
        print("aplicado:", contagem)
        return 0
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
