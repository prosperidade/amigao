"""ADR-079 — rodada de N leituras × leitura única, sobre leituras já medidas.

Entrada: os JSON de ``scripts/medir_releitura.py`` (várias leituras independentes
dos mesmos documentos, por modelo, sem gravar). Nada é chamado de novo: as rodadas
são combinações dessas leituras, e o "mesmo fato" é a regra do produto
(``app.services.leitura_multipla.mesmo_fato``, a do ADR-078).

Sem gabarito, a referência de cobertura é o que o modelo viu em TODAS as leituras
disponíveis (o conjunto agrupado das M leituras) e o subconjunto visto por pelo
menos duas delas (menos sujeito a leitura espúria). Mede, para rodadas de k = 1..3:

- cobertura: fração dessa referência que a união da rodada contém;
- marcadas entre rodadas: fração da união de uma rodada que uma rodada seguinte,
  com leituras disjuntas, não reencontra — o que o ADR-078 poria na tela;
- custo e tempo: por leitura medidos, multiplicados por k.

Uso:
    python scripts/medir_rodada.py rl_gpt-5.6-luna_*.json rl_gpt-6-luna_*.json
"""

from __future__ import annotations

import json
import sys
from itertools import combinations
from pathlib import Path
from statistics import mean

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.services.leitura_multipla import agrupar, mesmo_fato  # noqa: E402


def _itens(documento):
    """Os itens salvos pela medição, no formato do schema: coleção → dicts com posição."""
    por_colecao = {}
    for it in documento.get("itens", []):
        colecao = it["assinatura"][0]
        por_colecao.setdefault(colecao, []).append(
            {**it["valor"], "posicao_inicio": it["inicio"], "posicao_fim": it["fim"]})
    return por_colecao


def _medir_documento(leituras):
    """``leituras``: um registro de documento por leitura (mesmo documento)."""
    # Leitura que falhou neste documento fica fora, como na rodada (ADR-079, regra 7).
    falhas = sum(1 for d in leituras if d.get("erro"))
    leituras = [d for d in leituras if not d.get("erro")]
    m = len(leituras)
    itens = [_itens(d) for d in leituras]
    colecoes = sorted({c for i in itens for c in i})
    # Referência: o agrupamento das M leituras; de cada grupo, as leituras que o viram.
    referencia = []
    for colecao in colecoes:
        for grupo in agrupar(colecao, [i.get(colecao, []) for i in itens]):
            referencia.append({n for n, _, _ in grupo})
    robusta = [g for g in referencia if len(g) >= 2]
    saida = {"leituras_validas": m, "leituras_falhas": falhas, "referencia": len(referencia),
             "referencia_vista_2+": len(robusta), "por_k": {}}
    for k in (1, 2, 3):
        if k > m:
            continue
        rodadas = list(combinations(range(m), k))
        cobertura = [sum(1 for g in referencia if g & set(r)) / len(referencia) for r in rodadas] if referencia else []
        cobertura_2 = [sum(1 for g in robusta if g & set(r)) / len(robusta) for r in rodadas] if robusta else []
        uniao = []
        marcadas = []
        # Marcadas separadas pelo apoio do item na rodada de origem: vista por 1 leitura × por 2+.
        por_apoio = {"1": [0, 0], "2+": [0, 0]}
        for r in rodadas:
            grupos = {c: agrupar(c, [itens[n].get(c, []) for n in r]) for c in colecoes}
            reps = {c: [g[0][2] for g in gs] for c, gs in grupos.items()}
            apoio = {c: [len({n for n, _, _ in g}) for g in gs] for c, gs in grupos.items()}
            uniao.append(sum(len(v) for v in reps.values()))
            # Rodadas seguintes com leituras disjuntas: o que não reencontram fica marcado.
            for s in rodadas:
                if set(s) & set(r):
                    continue
                total = sum(len(v) for v in reps.values())
                sem = 0
                for c, v in reps.items():
                    for rep, k_apoio in zip(v, apoio[c], strict=True):
                        faixa = por_apoio["1" if k_apoio == 1 else "2+"]
                        faixa[1] += 1
                        if not any(mesmo_fato(c, rep, o) for n in s for o in itens[n].get(c, [])):
                            sem += 1
                            faixa[0] += 1
                if total:
                    marcadas.append(sem / total)
        saida["por_k"][k] = {
            "rodadas": len(rodadas), "uniao_media": round(mean(uniao), 1),
            "cobertura": round(mean(cobertura), 3) if cobertura else None,
            "cobertura_vistos_2+": round(mean(cobertura_2), 3) if cobertura_2 else None,
            "marcadas_entre_rodadas": round(mean(marcadas), 3) if marcadas else None,
            "pares_de_rodadas": len(marcadas),
            "marcadas_por_apoio": {f: (round(a / b, 3) if b else None) for f, (a, b) in por_apoio.items()},
            "marcadas_contagem": por_apoio,
        }
    return saida


def main(arquivos):
    leituras = [json.loads(Path(a).read_text(encoding="utf-8")) for a in arquivos]
    por_modelo = {}
    for lt in leituras:
        por_modelo.setdefault(lt["modelo_pedido"], []).append(lt)
    relatorio = {}
    for modelo, lts in por_modelo.items():
        lts.sort(key=lambda x: x.get("leitura", 0))
        docs = [d["doc"] for d in lts[0]["documentos"]]
        por_doc = {}
        for doc in docs:
            registros = [next(d for d in lt["documentos"] if d["doc"] == doc) for lt in lts]
            por_doc[doc] = {"tipo": registros[0]["tipo"], **_medir_documento(registros)}
        # Custo e tempo por leitura (todas as chamadas, reparo incluído).
        custos = [sum(c.get("custo_usd") or 0 for d in lt["documentos"] for c in d.get("chamadas", [])) for lt in lts]
        tempos = [sum(d["segundos"] for d in lt["documentos"]) for lt in lts]
        maior = [max(d["segundos"] for d in lt["documentos"]) for lt in lts]
        chamadas = [c for lt in lts for d in lt["documentos"] for c in d.get("chamadas", [])]
        total = {}
        for k in (1, 2, 3):
            linhas = [v["por_k"].get(k) for v in por_doc.values() if v["por_k"].get(k)]
            if not linhas:
                continue
            ref = sum(v["referencia"] for v in por_doc.values())
            ref2 = sum(v["referencia_vista_2+"] for v in por_doc.values())
            com_par = [v for v in por_doc.values() if v["por_k"][k]["marcadas_entre_rodadas"] is not None]
            # Ponderado pelo tamanho da referência de cada documento.
            total[k] = {
                "uniao_media": round(sum(v["por_k"][k]["uniao_media"] for v in por_doc.values()), 1),
                "cobertura": round(sum(v["por_k"][k]["cobertura"] * v["referencia"] for v in por_doc.values()) / ref, 3),
                "cobertura_vistos_2+": round(sum((v["por_k"][k]["cobertura_vistos_2+"] or 0) * v["referencia_vista_2+"]
                                                 for v in por_doc.values()) / ref2, 3),
                # Só documentos com rodadas disjuntas (leituras falhas podem deixar um documento sem par).
                "marcadas_entre_rodadas": round(sum(v["por_k"][k]["marcadas_entre_rodadas"] * v["por_k"][k]["uniao_media"]
                                                    for v in com_par) / sum(v["por_k"][k]["uniao_media"] for v in com_par), 3),
                "marcadas_por_releitura": round(sum(v["por_k"][k]["marcadas_entre_rodadas"] * v["por_k"][k]["uniao_media"]
                                                    for v in com_par), 1),
                "documentos_sem_par": [d for d, v in por_doc.items() if v["por_k"][k]["marcadas_entre_rodadas"] is None],
                "marcadas_por_apoio": {f: round(sum(v["por_k"][k]["marcadas_contagem"][f][0] for v in por_doc.values())
                                                / max(1, sum(v["por_k"][k]["marcadas_contagem"][f][1] for v in por_doc.values())), 3)
                                       for f in ("1", "2+")} if k > 1 else None,
                "custo_usd": round(k * mean(custos), 4),
                "tempo_sequencial_s": round(k * mean(tempos)),
                "maior_documento_sequencial_s": round(k * mean(maior)),
            }
        relatorio[modelo] = {
            "leituras": len(lts), "referencia": sum(v["referencia"] for v in por_doc.values()),
            "referencia_vista_2+": sum(v["referencia_vista_2+"] for v in por_doc.values()),
            "custo_por_leitura_usd": [round(c, 4) for c in custos], "tempo_por_leitura_s": [round(t) for t in tempos],
            "chamadas": len(chamadas), "fallback": sum(1 for c in chamadas if c.get("modelo") != modelo),
            "truncadas": sum(1 for c in chamadas if c.get("finish_reason") == "length"),
            "erros": [d["erro"] for lt in lts for d in lt["documentos"] if d.get("erro")],
            "total": total, "por_documento": por_doc,
        }
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
