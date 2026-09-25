"""As seis provas de leitura do Incremento 2, recalculadas do que está gravado.

Mesma régua para qualquer modelo: lê a leitura corrente do caso (a última
extração de cada documento) e as entidades do tenant, e diz, prova a prova,
passou/não passou com a evidência. Feito para tenants limpos, um por modelo
(`clonar_casos_dev.py`), onde pessoa e participação não se misturam com leituras
de outro modelo. Só leitura; só DEV.

Uso:
    python scripts/provas_leitura.py --tenant 36 --caso23 72 --caso25 73
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ALVO_DEV = ("127.0.0.1", 15432, "amigao_db")
MATRICULAS = {"3181", "3313", "3673", "4387"}


def _dig(v):
    return re.sub(r"\D", "", str(v or ""))


def provas(db, tenant, caso23, caso25):
    from sqlalchemy import text

    from app.services.entrada_semantica import observacoes_correntes_do_caso

    def obs(caso):
        return [r for r in observacoes_correntes_do_caso(db, tenant, caso) if r.kind == "observacao"]

    def attr(r, k):
        return (r.content.get("attributes") or {}).get(k)

    docs = {d: (t, f) for d, t, f in db.execute(text(
        "select id, document_type, filename from documents where tenant_id=:t and process_id in (:a,:b)"),
        {"t": tenant, "a": caso23, "b": caso25})}
    o23, o25 = obs(caso23), obs(caso25)
    res = {}

    # 1. Escritura não prova estado atual.
    escritura = [d for d, (_, f) in docs.items() if "ESCRITURA" in f.upper()]
    oe = [r for r in o25 if r.source_document_id in escritura]
    fora = [attr(r, "predicate") for r in oe if r.knowledge_state not in (None, "nao_determinado")]
    posse = [attr(r, "predicate") for r in oe if "posse" in str(attr(r, "predicate") or "")
             or "possuidor" in str(attr(r, "literal") or "").lower()]
    res["escritura_nao_prova_estado_atual"] = {
        "passou": bool(oe) and not fora,
        "evidencia": {"observacoes_da_escritura": len(oe), "fora_de_nao_determinado": fora, "posse_declarada": posse[:3]}}

    # 2. Transmitente não vira cliente nem titular.
    cliente = db.execute(text("select c.full_name, c.cpf_cnpj from processes p join clients c on c.id=p.client_id "
                              "where p.id=:p"), {"p": caso25}).one()
    transm = db.execute(text(
        "select distinct pe.nome from participacao pa join pessoa pe on pe.id=pa.pessoa_id "
        "where pa.tenant_id=:t and pa.process_id=:p and pa.papel='transmitente'"), {"t": tenant, "p": caso25}).scalars().all()
    virou = [n for n in transm if n.upper()[:12] in (cliente.full_name or "").upper()]
    res["transmitente_nao_vira_cliente"] = {
        "passou": bool(transm) and not virou,
        "evidencia": {"cliente": cliente.full_name, "transmitentes": transm, "transmitente_como_cliente": virou}}

    # 3. Quatro matrículas independentes: cada uma cita o próprio número; cruzadas são vizinhas.
    mats = [d for d, (t, _) in docs.items() if t == "matricula" and d in {r.source_document_id for r in o23}]
    matriz, proprio = {}, {}
    for d in mats:
        cont = {m: 0 for m in MATRICULAS}
        for r in o23:
            if r.source_document_id != d:
                continue
            dig = _dig(attr(r, "literal"))
            for m in MATRICULAS:
                cont[m] += m in dig
        matriz[d] = cont
        proprio[d] = max(cont, key=cont.get)
    res["quatro_matriculas_independentes"] = {
        "passou": len(mats) == 4 and len(set(proprio.values())) == 4,
        "evidencia": {"numero_dominante_por_documento": proprio, "citacoes": matriz}}

    # 4. PJ preserva CNPJ.
    pj = db.execute(text(
        "select pe.nome, pi.valor from pessoa pe join pessoa_identificador pi on pi.pessoa_id=pe.id "
        "where pe.tenant_id=:t and pe.natureza='pj' and pi.tipo='cnpj'"), {"t": tenant}).all()
    cnpjs = {_dig(v) for _, v in pj}
    res["pj_preserva_cnpj"] = {
        "passou": {"29091958000117", "59508731000195"} <= cnpjs,
        "evidencia": {"pj_com_cnpj": [f"{n} | {v}" for n, v in pj]}}

    # 5. Falecimento, espólio, inventariante, referência a processo.
    preds25 = [attr(r, "predicate") for r in o25]
    espolios = db.execute(text("select count(*) from espolio where tenant_id=:t"), {"t": tenant}).scalar()
    inventariante = db.execute(text(
        "select count(*) from participacao where tenant_id=:t and process_id=:p and papel='inventariante'"),
        {"t": tenant, "p": caso25}).scalar()
    refs = [attr(r, "literal") for r in o25 if attr(r, "predicate") == "referencia_processo"]
    tem_numero = any("5286960" in _dig(x) for x in refs)
    res["falecimento_espolio_inventariante_referencia"] = {
        "passou": "falecimento_declarado" in preds25 and espolios > 0 and inventariante > 0 and tem_numero,
        "evidencia": {"falecimento_declarado": "falecimento_declarado" in preds25, "espolios": espolios,
                      "inventariantes": inventariante, "referencia_com_numero_do_inventario": tem_numero}}

    # 6. Inventariante confirmado só com fundamento.
    sem_fund = db.execute(text(
        "select count(*) from participacao where tenant_id=:t and papel='inventariante' "
        "and estado_confirmacao='confirmado' and documento_id is null"), {"t": tenant}).scalar()
    ids = db.execute(text("select estado_confirmacao, count(*) from pessoa_identificador where tenant_id=:t "
                          "group by 1"), {"t": tenant}).all()
    res["inventariante_so_com_fundamento"] = {
        "passou": sem_fund == 0 and inventariante > 0,
        "evidencia": {"inventariante_confirmado_sem_documento": sem_fund,
                      "identificadores_por_estado": {e: n for e, n in ids}}}

    res["_resumo"] = {"passaram": sum(1 for k, v in res.items() if not k.startswith("_") and v["passou"]),
                      "observacoes_23": len(o23), "observacoes_25": len(o25)}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", type=int, required=True)
    ap.add_argument("--caso23", type=int, required=True)
    ap.add_argument("--caso25", type=int, required=True)
    args = ap.parse_args()
    from sqlalchemy.engine import make_url

    from app.core.config import settings
    from app.db.session import SessionLocal
    url = make_url(settings.SQLALCHEMY_DATABASE_URI)
    if (url.host, url.port, url.database) != ALVO_DEV:
        raise SystemExit(f"ABORTADO: alvo {(url.host, url.port, url.database)} não é o dev {ALVO_DEV}")
    with SessionLocal() as db:
        print(json.dumps(provas(db, args.tenant, args.caso23, args.caso25), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
