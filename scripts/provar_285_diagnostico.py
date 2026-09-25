"""Prova do #285 (ADR-080) em DEV: diagnóstico REAL por afirmação no #23 e no #25, entrando em
revisão e virando ressalva do orçamento (ADR-074). Só HTTP contra a API.

    INC285_API=http://127.0.0.1:8040 INC285_EMAIL=... INC285_SENHA=... \\
    INC285_SINTETICA=<object_id da conclusão sintética da prova do Inc. 5> \\
    python scripts/provar_285_diagnostico.py saida.json

O diagnóstico chama o modelo configurado pelo gateway (cadeia do projeto). Nada é simulado.
"""

from __future__ import annotations

import json
import os
import sys
import time

import httpx

API = os.environ.get("INC285_API", "http://127.0.0.1:8040") + "/api/v1"
CASOS = {"#23": 65, "#25": 66}
# INC285_CASOS=#23 roda o diagnóstico só nesse caso (retomada sem duplicar o do outro).
DIAGNOSTICAR = set((os.environ.get("INC285_CASOS") or "#23,#25").split(","))
REGISTRO: list[dict] = []


def registrar(passo: str, /, **dados) -> None:
    REGISTRO.append({"passo": passo, **dados})
    print(json.dumps(REGISTRO[-1], ensure_ascii=False, default=str)[:600])


def sessao() -> httpx.Client:
    c = httpx.Client(base_url=API, timeout=900)
    r = c.post("/auth/login", data={"username": os.environ["INC285_EMAIL"], "password": os.environ["INC285_SENHA"]},
               headers={"X-Auth-Profile": "internal"})
    r.raise_for_status()
    c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return c


def ok(r: httpx.Response, *esperados: int) -> dict:
    if r.status_code not in (esperados or (200, 201)):
        raise SystemExit(f"{r.request.method} {r.request.url} → {r.status_code}: {r.text[:800]}")
    return r.json() if r.content else {}


def estado(c: httpx.Client, pid: int) -> dict:
    return ok(c.get(f"/evidence/cases/{pid}"))


def retirar_sintetica(c: httpx.Client) -> None:
    """A conclusão sintética da prova do Inc. 5 sai de cena por revisão, não por apagamento."""
    alvo = os.environ.get("INC285_SINTETICA")
    if not alvo:
        return
    linhas = [r for r in estado(c, CASOS["#25"])["objects"] if r["object"]["id"] == alvo]
    if not linhas:
        raise SystemExit(f"conclusão sintética {alvo} não encontrada no #25")
    linha = max(linhas, key=lambda r: r["object"]["version"])
    if linha["review"] and linha["review"]["action"] == "rejeitar":
        registrar("sintetica_ja_rejeitada", objeto=alvo)
        return
    ok(c.post(f"/evidence/cases/{CASOS['#25']}/objects/{alvo}/review", json={
        "expected_version": linha["object"]["version"], "expected_revision": linha["revision"],
        "action": "rejeitar",
        "justification": "Conclusão sintética da prova do Inc. 5 (roteamento); substituída pelo diagnóstico real (#285)"}))
    registrar("sintetica_rejeitada", caso="#25", objeto=alvo)


def rejeitar_pendentes(c: httpx.Client, caso: str, pid: int, motivo: str) -> None:
    """Conclusões do diagnóstico ainda em revisão saem por rejeição justificada (nada se apaga)."""
    for row in estado(c, pid)["objects"]:
        obj = row["object"]
        if obj.get("origin") == "diagnostico" and row["review"] is None and not row["stale"]:
            ok(c.post(f"/evidence/cases/{pid}/objects/{obj['id']}/review", json={
                "expected_version": obj["version"], "expected_revision": row["revision"],
                "action": "rejeitar", "justification": motivo}))
            registrar("conclusao_rejeitada", caso=caso, objeto=obj["id"], motivo=motivo)


def diagnosticar(c: httpx.Client, caso: str, pid: int) -> list[str]:
    inicio = time.monotonic()
    r = ok(c.post("/agents/run", json={"agent_name": "diagnostico", "process_id": pid}))
    passo = r["steps"][0]
    saidas = [o["id"] for o in passo.get("outputs", [])]
    registrar("diagnostico_real", caso=caso, execucao=r["id"], status=r["status"], passo_status=passo["status"],
              erro=passo.get("error"), job=passo.get("job_id"), conclusoes=len(saidas),
              segundos=round(time.monotonic() - inicio, 1))
    if passo["status"] != "completed":
        return []
    objetos = {row["object"]["id"]: row for row in estado(c, pid)["objects"]}
    permitidas = {(o["id"], o["version"]) for g in ("sources", "observations", "derivations", "conclusions")
                  for o in estado(c, pid)["envelope"][g]}
    for oid in saidas:
        row = objetos[oid]
        obj = row["object"]
        registrar("afirmacao", caso=caso, objeto=oid, classe=obj["conclusion_class"], texto=obj["statement"],
                  certeza=obj["attributes"].get("certainty"), impacto=obj["attributes"].get("impact"),
                  urgencia=obj["attributes"].get("urgency"), aplicabilidade=obj.get("applicability"),
                  premissas=[(p["id"], p["version"]) for p in obj["premises"]],
                  premissas_fora_do_envelope=[p for p in obj["premises"] if (p["id"], p["version"]) not in permitidas],
                  revisao=row["review"])
    return saidas


def comercial(c: httpx.Client, caso: str, pid: int) -> None:
    antes = ok(c.get(f"/processes/{pid}/comercial/orcamento"))["orcamento"]
    registrar("orcamento_depois_do_diagnostico", caso=caso, id=antes["id"], versao=antes["versao"],
              estado_revisao=antes["estado_revisao"], atualidade=antes["atualidade"])
    r = ok(c.post(f"/processes/{pid}/comercial/redacao"), 201)
    esc = r["especificacao_escopo"]
    premissas = next(s for s in esc["conteudo"]["secoes"] if s["chave"] == "premissas")["afirmacoes"]
    registrar("escopo_regerado", caso=caso, id=esc["id"], versao=esc["versao"],
              premissa_diagnostico=[a for a in premissas if a["id"] == "premissa:diagnostico"])
    ok(c.post(f"/processes/{pid}/comercial/redacao/{esc['id']}/revisar",
              json={"acao": "aprovar", "justificativa": "PROVA #285 — escopo sobre a Rota; diagnóstico como ressalva"}))
    o = ok(c.post(f"/processes/{pid}/comercial/orcamento"), 201)
    registrar("orcamento_com_ressalva", caso=caso, id=o["id"], versao=o["versao"], total=o["total"],
              ressalvas=o["ressalvas"], atualidade=o["atualidade"])
    ok(c.post(f"/processes/{pid}/comercial/orcamento/{o['id']}/revisar",
              json={"acao": "aprovar", "justificativa": "PROVA #285 — diagnóstico em revisão é ressalva, não bloqueio"}))
    draft = ok(c.get("/proposals/generate-draft", params={"process_id": pid}))
    registrar("proposta_rascunho", caso=caso, orcamento_id=draft["orcamento_id"], valor=draft["suggested_value"])


def main(saida: str) -> None:
    try:
        percurso()
    finally:
        # Grava o que houve, inclusive se o percurso parar no meio.
        with open(saida, "w", encoding="utf-8") as f:
            json.dump(REGISTRO, f, ensure_ascii=False, indent=1, default=str)


def percurso() -> None:
    a = sessao()
    registrar("login", sessao="A")
    retirar_sintetica(a)
    for caso in filter(None, (os.environ.get("INC285_REJEITAR_PENDENTES") or "").split(",")):
        rejeitar_pendentes(a, caso, CASOS[caso], "PROVA #285 — rodada do prompt 080.2 substituída pela 080.3 "
                                                 "(código final do PR)")
    for caso, pid in CASOS.items():
        if caso in DIAGNOSTICAR and diagnosticar(a, caso, pid):
            comercial(a, caso, pid)
    b = sessao()
    for caso, pid in CASOS.items():
        o = ok(b.get(f"/processes/{pid}/comercial/orcamento"))["orcamento"]
        pendentes = [r["object"]["id"] for r in estado(b, pid)["objects"]
                     if r["object"].get("origin") == "diagnostico" and r["review"] is None]
        registrar("nova_sessao", caso=caso, orcamento=(o["id"], o["versao"], o["estado_revisao"],
                  o["atualidade"]["estado"]), ressalvas=[x["tipo"] for x in o["ressalvas"]],
                  conclusoes_em_revisao=pendentes)


if __name__ == "__main__":
    main(sys.argv[1])
