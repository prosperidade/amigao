"""Dívida #281 — variância entre leituras do mesmo documento, em DEV, sem gravar.

Lê os documentos de um caso com o extrator (`ler_documento`: fatiar, chamar,
ancorar, validar) e NÃO persiste — persistir dispararia a superação da leitura
anterior, que é justamente o que se mede. Cada item validado sai com uma
identidade que não depende das chaves que o modelo inventa ("elodi" numa
leitura, "p1" na outra): coleção, predicado/rótulo/papel e o trecho ancorado.

O modelo é escolhido só neste processo (`--modelo`); o padrão do sistema não muda.

Uso:
    python scripts/medir_releitura.py --tenant 34 --processo 67 --modelo gpt-6-luna --leitura 1 --json saida.json
    python scripts/medir_releitura.py --comparar a.json b.json c.json ...
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
ALVO_DEV = ("127.0.0.1", 15432, "amigao_db")
# Chaves que o modelo inventa e que ligam itens entre si: não são o valor lido.
_REFERENCIAS = {"trecho", "posicao_inicio", "posicao_fim", "chave", "parte_chave", "representado_chave",
                "falecido_chave", "sujeito", "contratante", "contratado", "confianca"}


def _so_digitos(v):
    return re.sub(r"\D", "", str(v or ""))


def _normal(v):
    return re.sub(r"\s+", " ", str(v or "")).strip().upper()


def assinatura(colecao, item):
    """O que torna dois itens de leituras diferentes 'o mesmo fato' (além do trecho)."""
    d = item if isinstance(item, dict) else item.model_dump(mode="json")
    if colecao == "observacoes":
        return (colecao, d.get("predicado"))
    if colecao == "atos":
        return (colecao, _normal(d.get("rotulo")).replace(" ", "").replace(".", "-"))
    if colecao == "partes":
        return (colecao, _so_digitos(d.get("identificador")) or _normal(d.get("nome")))
    if colecao in ("participacoes", "todas_participacoes"):
        return ("participacoes", d.get("papel"))
    if colecao == "referencias_processo":
        return (colecao, _so_digitos(d.get("numero")))
    return (colecao,)


# As coleções que a persistência grava como observação (``_persistir_entrada``).
# ``limites`` é texto livre sem âncora; participações vêm de ``todas_participacoes``,
# que junta também as aninhadas nos atos.
_COLECOES = ("partes", "todas_participacoes", "atos", "observacoes", "contratos",
             "falecimentos_declarados", "referencias_processo")


def itens_da_leitura(entrada):
    saida = []
    for colecao in _COLECOES:
        for item in getattr(entrada, colecao) or []:
            d = item.model_dump(mode="json")
            saida.append({"assinatura": list(assinatura(colecao, d)),
                          "inicio": d.get("posicao_inicio"), "fim": d.get("posicao_fim"),
                          "valor": {k: v for k, v in d.items() if k not in _REFERENCIAS}})
    return saida


def ler(tenant, processo, docs):
    from sqlalchemy.engine import make_url

    from app.core.config import settings
    from app.db.session import SessionLocal
    from app.models.document import Document
    from app.services.agent_capabilities import capability_manifest
    from app.services.entrada_semantica import ler_documento

    url = make_url(settings.SQLALCHEMY_DATABASE_URI)
    if (url.host, url.port, url.database) != ALVO_DEV:
        raise SystemExit(f"ABORTADO: alvo {(url.host, url.port, url.database)} não é o dev {ALVO_DEV}")
    manifest = capability_manifest("extrator", {})
    resultado = {"modelo_pedido": settings.AI_EXTRATOR_MODEL, "documentos": []}
    with SessionLocal() as db:
        for doc_id in docs:
            doc = db.query(Document).filter_by(id=doc_id, tenant_id=tenant, process_id=processo).one()
            t0 = time.monotonic()
            erro = None
            try:
                leitura = ler_documento(db, doc, manifest=manifest)
            except Exception as exc:  # a falha da leitura é dado da medição, não aborta as outras
                leitura, erro = None, f"{type(exc).__name__}: {getattr(exc, 'detail', None) or exc}"
            db.rollback()  # nada desta leitura é gravado
            registro = {"doc": doc_id, "tipo": doc.document_type, "chars": len(doc.extracted_text or ""),
                        "segundos": round(time.monotonic() - t0, 1), "erro": erro}
            if leitura:
                registro.update(itens=itens_da_leitura(leitura["entrada"]), chamadas=leitura["chamadas"],
                                fatias=len(leitura["fatias"]), rejeicoes=len(leitura["rejeicoes"]))
            resultado["documentos"].append(registro)
            print(f"doc {doc_id}: itens={len(registro.get('itens', []))} chamadas={len(registro.get('chamadas', []))} "
                  f"{registro['segundos']} s {erro or ''}", flush=True)
    return resultado


def _valor(it):
    return re.sub(r"\s+", "", str(it["valor"].get("valor") or "")).upper()


def _casa(a, b):
    """A mesma regra de ``entrada_semantica._mesmo_fato``: trecho sobreposto, mesmo tipo e
    discriminante, e — para observação — mesmo predicado OU mesmo valor lido."""
    if a["assinatura"][0] != b["assinatura"][0]:
        return False
    if a["inicio"] is None or b["inicio"] is None or not (a["inicio"] < b["fim"] and b["inicio"] < a["fim"]):
        return False
    if a["assinatura"] == b["assinatura"]:
        return True
    return a["assinatura"][0] == "observacoes" and _valor(a) != "" and _valor(a) == _valor(b)


def comparar(arquivos):
    """Por modelo e documento: itens por leitura, interseção (nas 3), união, custo, tempo."""
    leituras = [json.loads(Path(a).read_text(encoding="utf-8")) for a in arquivos]
    por_modelo = {}
    for lt in leituras:
        por_modelo.setdefault(lt["modelo_pedido"], []).append(lt)
    relatorio = {}
    for modelo, lts in por_modelo.items():
        docs = [d["doc"] for d in lts[0]["documentos"]]
        linhas = []
        for doc in docs:
            conjuntos = [next(d for d in lt["documentos"] if d["doc"] == doc) for lt in lts]
            itens = [c.get("itens", []) for c in conjuntos]
            # União: agrupa itens de todas as leituras que casam entre si.
            grupos = []
            for n, lista in enumerate(itens):
                for it in lista:
                    alvo = next((g for g in grupos if any(_casa(it, o) for _, o in g)), None)
                    (alvo.append((n, it)) if alvo is not None else grupos.append([(n, it)]))
            em_todas = [g for g in grupos if len({n for n, _ in g}) == len(itens)]
            em_uma = [g for g in grupos if len({n for n, _ in g}) == 1]
            valor_diferente = sum(1 for g in em_todas if len({json.dumps(o["valor"], sort_keys=True) for _, o in g}) > 1)
            chamadas = [c for cj in conjuntos for c in cj.get("chamadas", [])]
            linhas.append({
                "doc": doc, "tipo": conjuntos[0]["tipo"],
                "itens_por_leitura": [len(i) for i in itens],
                "intersecao": len(em_todas), "uniao": len(grupos), "so_em_uma_leitura": len(em_uma),
                "reencontrados_com_valor_diferente": valor_diferente,
                "jaccard": round(len(em_todas) / len(grupos), 3) if grupos else None,
                "custo_usd": round(sum(c.get("custo_usd") or 0 for c in chamadas), 4),
                "segundos": round(sum(cj["segundos"] for cj in conjuntos)),
                "chamadas": len(chamadas),
                "fallback": sum(1 for c in chamadas if c.get("modelo") != modelo),
                "truncadas": sum(1 for c in chamadas if c.get("finish_reason") == "length"),
                "erros": [cj["erro"] for cj in conjuntos if cj.get("erro")],
            })
        relatorio[modelo] = linhas
    return relatorio


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", type=int)
    ap.add_argument("--processo", type=int)
    ap.add_argument("--modelo")
    ap.add_argument("--leitura", type=int, default=1)
    ap.add_argument("--docs", default="154,155,156,157,159", help="CAR e matrículas do #23 no tenant 34")
    ap.add_argument("--json")
    ap.add_argument("--comparar", nargs="+")
    args = ap.parse_args()
    if args.comparar:
        print(json.dumps(comparar(args.comparar), ensure_ascii=False, indent=2))
        return
    # O modelo vale só neste processo; precisa estar no ambiente antes das settings.
    os.environ["AI_EXTRATOR_MODEL"] = args.modelo
    os.environ.setdefault("LOG_LEVEL", "WARNING")
    resultado = ler(args.tenant, args.processo, [int(x) for x in args.docs.split(",")])
    resultado["leitura"] = args.leitura
    Path(args.json).write_text(json.dumps(resultado, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
