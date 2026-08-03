"""
scripts/sanear_corpus.py — reparo do corpus já gravado (dívidas #95 e #96).

Dois defeitos de fidelidade de texto entraram em abril e ficaram três meses
invisíveis, porque texto corrompido não levanta exceção. O canário e o saneador
do PR #127 fecharam a porta para ingestões NOVAS; esta ferramenta trata o
passivo.

    --mojibake    #95 — documento cujo texto veio com U+FFFD (charset errado).
                  Rebaixa da URL de origem, confere que saiu limpo e reindexa.
                  Só age em documento que TEM url: o que veio de disco precisa
                  do arquivo original, não de rede.

    --invisiveis  #96 — U+00A0 / U+200B / U+FEFF no texto já gravado.
                  Normaliza IN PLACE, sem reembedar: o caractere é
                  semanticamente invisível, o vetor não muda de forma relevante,
                  e o que se recupera é a busca LITERAL — a nossa, a de operação
                  e o Ctrl+F de quem lê a peça pronta.

Dry-run é o padrão. Nada é gravado sem `--executar`.

Uso:
    python scripts/sanear_corpus.py --invisiveis
    python scripts/sanear_corpus.py --invisiveis --executar
    python scripts/sanear_corpus.py --mojibake
    python scripts/sanear_corpus.py --mojibake --executar
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger("sanear_corpus")

# Acima disto, o texto é lixo e não deve ficar no corpus (mesmo limiar do
# canário de ingestão em `scripts/ingest_federais_canonicos.py`).
LIMIAR_MOJIBAKE = 0.0005

# Invisíveis que quebram busca literal sem aparecer na tela.
INVISIVEIS = {
    "\u00a0": " ",  # espaco nao-quebravel — o do Planalto entre "Art." e o numero
    "\u2007": " ",  # espaco de figura
    "\u202f": " ",  # espaco estreito nao-quebravel
    "\u200b": "",   # zero-width space
    "\ufeff": "",   # BOM no meio do texto
}
_TRADUCAO = str.maketrans({k: v for k, v in INVISIVEIS.items()})


def normalizar_invisiveis(texto: str | None) -> str | None:
    """Idempotente: aplicar duas vezes dá o mesmo resultado da primeira."""
    if texto is None:
        return None
    return texto.translate(_TRADUCAO)


def _hash_chunk(source_type: str, source_ref: str, chunk_index: int, body: str) -> str:
    """Réplica exata de `app.services.knowledge_catalog._hash_chunk`.

    Precisa ser idêntica: normalizar o texto sem recalcular o hash deixaria o
    `content_hash` descrito de um conteúdo que já não existe — e a PRÓXIMA
    reindexação, que pula por hash, inseriria tudo de novo, duplicado.
    """
    h = hashlib.sha256()
    h.update(source_type.encode("utf-8"))
    h.update(b"\x00")
    h.update(source_ref.encode("utf-8"))
    h.update(b"\x00")
    h.update(str(chunk_index).encode("ascii"))
    h.update(b"\x00")
    h.update(body.encode("utf-8"))
    return h.hexdigest()


# ---------------------------------------------------------------------------
# #96 — invisíveis
# ---------------------------------------------------------------------------

def sanear_invisiveis(session, executar: bool) -> dict:
    from sqlalchemy import text as _sql

    padrao = "%" + "%|%".join(INVISIVEIS) + "%"  # só para log; a seleção é abaixo
    del padrao

    condicao = " OR ".join(
        f"coalesce({campo},'') LIKE :p{i}"
        for campo in ("chunk_text", "title", "section")
        for i in range(len(INVISIVEIS))
    )
    params = {f"p{i}": f"%{c}%" for i, c in enumerate(INVISIVEIS)}

    linhas = session.execute(
        _sql(
            f"""
            SELECT id, source_type, source_ref, chunk_index, chunk_text, title, section
            FROM knowledge_catalog
            WHERE {condicao}
            ORDER BY id
            """
        ),
        params,
    ).all()

    docs = session.execute(
        _sql(
            "SELECT id, identifier, full_text FROM legislation_documents "
            "WHERE " + " OR ".join(f"full_text LIKE :p{i}" for i in range(len(INVISIVEIS))) +
            " ORDER BY id"
        ),
        params,
    ).all()

    relatorio = {
        "chunks_afetados": len(linhas),
        "documentos_afetados": len(docs),
        "chunks_por_documento": {},
        "hashes_recalculados": 0,
    }
    for linha in linhas:
        relatorio["chunks_por_documento"].setdefault(linha.source_ref, 0)
        relatorio["chunks_por_documento"][linha.source_ref] += 1

    if not executar:
        return relatorio

    for linha in linhas:
        novo_texto = normalizar_invisiveis(linha.chunk_text)
        novo_hash = _hash_chunk(
            linha.source_type, linha.source_ref, linha.chunk_index, novo_texto
        )
        session.execute(
            _sql(
                """
                UPDATE knowledge_catalog
                   SET chunk_text = :t, title = :ti, section = :se, content_hash = :h
                 WHERE id = :id
                """
            ),
            {
                "t": novo_texto,
                "ti": normalizar_invisiveis(linha.title),
                "se": normalizar_invisiveis(linha.section),
                "h": novo_hash,
                "id": linha.id,
            },
        )
        relatorio["hashes_recalculados"] += 1

    for doc in docs:
        session.execute(
            _sql("UPDATE legislation_documents SET full_text = :t WHERE id = :id"),
            {"t": normalizar_invisiveis(doc.full_text), "id": doc.id},
        )

    session.commit()
    return relatorio


# ---------------------------------------------------------------------------
# #95 — mojibake
# ---------------------------------------------------------------------------

def sanear_mojibake(session, executar: bool) -> dict:
    from scripts.ingest_legislation import (
        estimate_tokens,
        load_from_url,
        sanitize_text,
        verificar_mojibake,
    )
    from sqlalchemy import text as _sql

    from app.services.knowledge_catalog import index_legislation_document

    candidatos = session.execute(
        _sql(
            """
            SELECT id, identifier, url, full_text,
                   (length(full_text) - length(replace(full_text, '�', '')))::float
                     / nullif(length(full_text),0) AS sujeira
            FROM legislation_documents
            WHERE full_text LIKE '%�%'
            ORDER BY id
            """
        )
    ).all()

    relatorio: dict = {"documentos": [], "sem_url": [], "chunks_refeitos": 0}

    for doc in candidatos:
        item = {
            "id": doc.id,
            "identifier": doc.identifier,
            "sujeira_antes": round(doc.sujeira * 100, 3),
            "url": doc.url,
        }
        if not doc.url:
            # Veio de disco: rede não resolve. Precisa do arquivo original.
            relatorio["sem_url"].append(item)
            continue

        try:
            _ctype, bruto = load_from_url(doc.url)
            texto = sanitize_text(bruto)
        except Exception as exc:  # noqa: BLE001
            item["erro"] = f"{type(exc).__name__}: {exc}"
            relatorio["documentos"].append(item)
            continue

        sujeira = verificar_mojibake(texto)
        item["sujeira_depois"] = round(sujeira * 100, 3)
        item["chars_antes"] = len(doc.full_text or "")
        item["chars_depois"] = len(texto)

        if sujeira > LIMIAR_MOJIBAKE:
            # Rebaixar não resolveu — não troca lixo por lixo.
            item["acao"] = "recusado_ainda_sujo"
            relatorio["documentos"].append(item)
            continue

        item["acao"] = "reingerir" if not executar else "reingerido"
        relatorio["documentos"].append(item)

        if not executar:
            continue

        # UPDATE no MESMO id (não supersede): preserva `sucessora_id` de quem
        # aponta para este documento e não deixa órfão o histórico.
        session.execute(
            _sql(
                """
                UPDATE legislation_documents
                   SET full_text = :t, token_count = :tk, content_hash = :h
                 WHERE id = :id
                """
            ),
            {
                "t": texto,
                "tk": estimate_tokens(texto),
                "h": hashlib.sha256(texto.encode("utf-8")).hexdigest(),
                "id": doc.id,
            },
        )
        # Os chunks antigos carregam o texto sujo e hashes do texto sujo — saem.
        session.execute(
            _sql("DELETE FROM knowledge_catalog WHERE source_ref = :ref"),
            {"ref": f"legislation_documents:{doc.id}"},
        )
        session.commit()

        inseridos = index_legislation_document(session, doc.id)
        session.commit()
        item["chunks"] = inseridos
        relatorio["chunks_refeitos"] += inseridos

    return relatorio


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--invisiveis", action="store_true", help="#96 — U+00A0/ZWSP/BOM")
    p.add_argument("--mojibake", action="store_true", help="#95 — U+FFFD")
    p.add_argument("--executar", action="store_true", help="grava (padrão: dry-run)")
    args = p.parse_args()

    if not (args.invisiveis or args.mojibake):
        p.error("escolha --invisiveis e/ou --mojibake")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    modo = "EXECUÇÃO" if args.executar else "DRY-RUN (nada será gravado)"
    print(f"=== SANEAMENTO DO CORPUS — {modo} ===\n")

    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        if args.invisiveis:
            r = sanear_invisiveis(session, args.executar)
            print("--- #96 invisíveis (U+00A0 / U+200B / U+FEFF) ---")
            print(f"  chunks afetados     : {r['chunks_afetados']}")
            print(f"  documentos afetados : {r['documentos_afetados']}")
            print(f"  hashes recalculados : {r['hashes_recalculados']}")
            print("  custo de embedding  : US$ 0,00 (normalização in-place)")
            piores = sorted(
                r["chunks_por_documento"].items(), key=lambda kv: -kv[1]
            )[:8]
            for ref, n in piores:
                print(f"    {ref:<34} {n} chunks")
            print()

        if args.mojibake:
            r = sanear_mojibake(session, args.executar)
            print("--- #95 mojibake (U+FFFD) ---")
            for d in r["documentos"]:
                print(
                    f"  {d['identifier']:<22} {d['sujeira_antes']:>6}% → "
                    f"{d.get('sujeira_depois', '?')}%  {d.get('acao', d.get('erro',''))}"
                    f"  chunks={d.get('chunks','-')}"
                )
            if r["sem_url"]:
                print("\n  SEM URL (precisam do arquivo original — pedido à Isis):")
                for d in r["sem_url"]:
                    print(f"    {d['identifier']:<40} {d['sujeira_antes']}%")
            print(f"\n  chunks refeitos: {r['chunks_refeitos']}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
