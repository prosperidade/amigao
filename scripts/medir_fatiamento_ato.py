"""Prova do ADR-077 (#271) em DEV: extrai um caso pelo caminho de produção e mede.

Roda a execução persistida do ADR-069 (``start_execution`` + ``resume_execution``,
o mesmo código que o worker executa — só sem Celery) e depois confere tudo a
partir do que ficou GRAVADO, nunca do que o script supõe:

  - por fatia: modelo que respondeu, tokens, custo, tempo, ``finish_reason``;
  - se alguma chamada caiu no fallback (critério: nenhuma);
  - âncoras: toda observação da extração com versão e fragmento, e o fragmento
    igual ao texto da versão naquela posição (critério: 100%);
  - matrículas independentes: número e área por documento.

Só em DEV. O alvo é conferido antes de abrir qualquer transação:
``127.0.0.1:15432/amigao_db``. Qualquer outro alvo aborta.

Uso:
    python scripts/medir_fatiamento_ato.py --tenant 34 --processo 67 --usuario 37
    python scripts/medir_fatiamento_ato.py --tenant 34 --processo 67 --usuario 37 --so-medir
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("LOG_LEVEL", "WARNING")

ALVO_DEV = ("127.0.0.1", 15432, "amigao_db")


def conferir_alvo():
    from sqlalchemy.engine import make_url

    from app.core.config import settings

    url = make_url(settings.SQLALCHEMY_DATABASE_URI)
    efetivo = (url.host, url.port, url.database)
    print(f"alvo: host={url.host} porta={url.port} banco={url.database} usuario={url.username}")
    if efetivo != ALVO_DEV:
        raise SystemExit(f"ABORTADO: alvo {efetivo} não é o dev {ALVO_DEV}")


def extrair(tenant, processo, usuario):
    from app.db.session import SessionLocal
    from app.services.connected_agents import execution_data, resume_execution, start_execution

    inicio = time.monotonic()
    with SessionLocal() as db:
        execucao = start_execution(db, tenant, usuario, processo, "extrator")
        db.commit()
        resultado = execution_data(resume_execution(db, tenant, usuario, execucao.id))
        db.commit()
    return resultado, time.monotonic() - inicio


def medir(tenant, processo):
    from sqlalchemy import text

    from app.db.session import SessionLocal

    saida = {"documentos": [], "chamadas": [], "ancoras": {}, "matriculas": []}
    with SessionLocal() as db:
        docs = db.execute(text(
            "select id, document_type, length(extracted_text) from documents "
            "where tenant_id=:t and process_id=:p and deleted_at is null order by id"),
            {"t": tenant, "p": processo}).all()
        total, ancoradas, conferidas = 0, 0, 0
        for doc_id, tipo, chars in docs:
            rel = db.execute(text(
                "select content->'attributes'->'normalized' from evidence_versions "
                "where tenant_id=:t and process_id=:p and object_id=:o order by version desc limit 1"),
                {"t": tenant, "p": processo, "o": f"extracao:rejeicoes:{doc_id}"}).scalar()
            if not rel:
                saida["documentos"].append({"doc": doc_id, "tipo": tipo, "chars": chars, "extraido": False})
                continue
            fat = rel.get("fatiamento") or {}
            ids = [o["id"] for o in rel.get("observacoes", [])]
            saida["documentos"].append({"doc": doc_id, "tipo": tipo, "chars": chars, "extraido": True,
                "metodo": fat.get("metodo"), "fatias": len(fat.get("fatias", [])),
                "observacoes": len(ids), "rejeicoes": len(rel.get("rejeicoes", []))})
            for c in fat.get("chamadas", []):
                saida["chamadas"].append({"doc": doc_id, **c})
            if not ids:
                continue
            linhas = db.execute(text(
                "select ev.documento_versao_id, ev.fragmento_id, f.inicio, f.fim, f.trecho, "
                "substr(dv.texto, f.inicio + 1, f.fim - f.inicio) as no_texto "
                "from evidence_versions ev "
                "left join fragmento f on f.id = ev.fragmento_id "
                "left join documento_versao dv on dv.id = ev.documento_versao_id "
                "where ev.tenant_id=:t and ev.process_id=:p and ev.object_id = any(:ids) "
                "and ev.version = (select max(version) from evidence_versions x "
                "  where x.tenant_id=ev.tenant_id and x.process_id=ev.process_id and x.object_id=ev.object_id)"),
                {"t": tenant, "p": processo, "ids": ids}).all()
            for versao, frag, _i, _f, trecho, no_texto in linhas:
                total += 1
                if versao and frag:
                    ancoradas += 1
                    if trecho == no_texto:
                        conferidas += 1
            if tipo == "matricula":
                numeros = db.execute(text(
                    "select distinct coalesce(content->'attributes'->>'literal','') from evidence_versions "
                    "where tenant_id=:t and process_id=:p and object_id = any(:ids) "
                    "and content->'attributes'->>'predicate' in ('matricula','codigo_nacional_de_matricula') "
                    "limit 3"), {"t": tenant, "p": processo, "ids": ids}).scalars().all()
                areas = db.execute(text(
                    "select distinct coalesce(content->'attributes'->>'literal','') from evidence_versions "
                    "where tenant_id=:t and process_id=:p and object_id = any(:ids) "
                    "and content->'attributes'->>'predicate' = 'area_imovel' limit 2"),
                    {"t": tenant, "p": processo, "ids": ids}).scalars().all()
                saida["matriculas"].append({"doc": doc_id,
                    "numero": [n[:80] for n in numeros], "area": [a[:80] for a in areas]})
        saida["ancoras"] = {"observacoes": total, "com_versao_e_fragmento": ancoradas,
                            "fragmento_igual_ao_texto": conferidas}
        # Tentativas ao provedor, inclusive as que falharam (timeout, truncagem refeita):
        # o relatório só guarda a resposta final de cada fatia; o job guarda todas.
        job = db.execute(text(
            "select id, cost_usd, input_payload->'attempts', input_payload->'orcamento' from ai_jobs "
            "where tenant_id=:t and entity_id=:p and agent_name='extrator' order by id desc limit 1"),
            {"t": tenant, "p": processo}).first()
        if job:
            tentativas = job[2] or []
            falhas = {}
            for a in tentativas:
                if a.get("status") == "failed":
                    chave = f"{a.get('model')}:{a.get('error_type')}"
                    falhas[chave] = falhas.get(chave, 0) + 1
            saida["job"] = {"id": job[0], "custo_registrado_usd": job[1], "tentativas": len(tentativas),
                "falhas": falhas, "modelos": sorted({a.get("model") for a in tentativas}),
                "custo_pago_usd": round(sum(a.get("cost_usd") or 0 for a in tentativas), 4),
                "orcamento": job[3]}
    return saida


def resumir(med):
    chamadas = med["chamadas"]
    primario = [c for c in chamadas if c.get("modelo") == "gpt-5.6-luna"]
    fallback = [c for c in chamadas if c.get("modelo") != "gpt-5.6-luna"]
    truncadas = [c for c in chamadas if c.get("finish_reason") == "length"]
    ms = sorted(c.get("ms") or 0 for c in chamadas)
    out = sorted(c.get("tokens_out") or 0 for c in chamadas)
    return {
        "chamadas": len(chamadas), "no_primario": len(primario), "no_fallback": len(fallback),
        "truncadas": len(truncadas),
        "custo_total_usd": round(sum(c.get("custo_usd") or 0 for c in chamadas), 4),
        "custo_max_por_chamada_usd": round(max((c.get("custo_usd") or 0 for c in chamadas), default=0), 4),
        "ms_mediana": ms[len(ms) // 2] if ms else None, "ms_max": ms[-1] if ms else None,
        "tokens_out_mediana": out[len(out) // 2] if out else None, "tokens_out_max": out[-1] if out else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", type=int, required=True)
    ap.add_argument("--processo", type=int, required=True)
    ap.add_argument("--usuario", type=int, required=True)
    ap.add_argument("--so-medir", action="store_true", help="não extrai; só mede o que está gravado")
    ap.add_argument("--json", help="grava a medição completa neste arquivo")
    args = ap.parse_args()

    conferir_alvo()
    if not args.so_medir:
        resultado, segundos = extrair(args.tenant, args.processo, args.usuario)
        print(f"execução: status={resultado.get('status')} em {segundos:.0f} s")
        for passo in resultado.get("steps", []):
            print(f"  passo {passo.get('agent')}: {passo.get('status')} {passo.get('error') or ''}")
    med = medir(args.tenant, args.processo)
    med["resumo"] = resumir(med)
    for d in med["documentos"]:
        print("doc", d)
    for m in med["matriculas"]:
        print("matrícula", m)
    print("âncoras", med["ancoras"])
    print("resumo", med["resumo"])
    print("job", med.get("job"))
    if args.json:
        Path(args.json).write_text(json.dumps(med, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
