"""Percurso autenticado do Incremento 5 (ADR-074) em DEV: Rota → relatório → escopo → orçamento.

Casos do gate no tenant de dev 33: #23 = processo 65, #25 = processo 66, ambos com Rota validada
pelo motor jurídico (Incremento 4b). Só HTTP contra a API; nenhuma escrita direta no banco.

    INC5_API=http://127.0.0.1:8040 INC5_EMAIL=... INC5_SENHA=... \\
    INC5_EMAIL_OUTRO=... INC5_SENHA_OUTRO=... python scripts/provar_incremento5_comercial.py saida.json

``INC5_FASES`` (padrão: base, remocao, isolamento) escolhe as fases; ``regerar`` gera de novo
relatório, escopo e orçamento do #25 (depois de uma correção de código). ``INC5_CONCLUSAO``
(opcional) é o id de uma conclusão do diagnóstico em revisão no #25, só para o registro.

Os preços são de PROVA, não a tabela de uma consultoria. Credenciais só por ambiente.
"""

from __future__ import annotations

import json
import os
import sys
from decimal import Decimal

import httpx

API = os.environ.get("INC5_API", "http://127.0.0.1:8040") + "/api/v1"
CASOS = {"#23": 65, "#25": 66}
REGISTRO: list[dict] = []


def registrar(passo: str, **dados) -> None:
    REGISTRO.append({"passo": passo, **dados})
    print(json.dumps(REGISTRO[-1], ensure_ascii=False, default=str)[:400])


def sessao(email: str, senha: str) -> httpx.Client:
    c = httpx.Client(base_url=API, timeout=180)
    r = c.post("/auth/login", data={"username": email, "password": senha}, headers={"X-Auth-Profile": "internal"})
    r.raise_for_status()
    c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return c


def ok(r: httpx.Response, *esperados: int) -> dict:
    if r.status_code not in (esperados or (200, 201)):
        raise SystemExit(f"{r.request.method} {r.request.url} → {r.status_code}: {r.text[:500]}")
    return r.json() if r.content else {}


def resumo_redacao(doc: dict) -> dict:
    secoes = doc["conteudo"]["secoes"]
    afirmacoes = [a for s in secoes for a in s["afirmacoes"]]
    tipos: dict[str, int] = {}
    for a in afirmacoes:
        for e in a["evidencias"]:
            tipos[e["tipo"]] = tipos.get(e["tipo"], 0) + 1
    return {"id": doc["id"], "tipo": doc["tipo"], "versao": doc["versao"], "estado_revisao": doc["estado_revisao"],
            "atualidade": doc["atualidade"], "afirmacoes": len(afirmacoes),
            "afirmacoes_sem_evidencia": sum(1 for a in afirmacoes if not a["evidencias"]),
            "evidencias_por_tipo": tipos,
            "secoes": {s["chave"]: [a["texto"] for a in s["afirmacoes"]] for s in secoes}}


def resumo_orcamento(o: dict) -> dict:
    return {"id": o["id"], "versao": o["versao"], "total": o["total"], "estado_revisao": o["estado_revisao"],
            "atualidade": o["atualidade"], "ressalvas": o["ressalvas"], "fora": o["fora"],
            "itens": [{k: i[k] for k in ("rota_passo_id", "descricao", "escolha", "calculo", "total")}
                      | {"metodo": f"{i['metodo']['codigo']} v{i['metodo']['versao']}",
                         "dispositivo_id": i["fundamento"].get("dispositivo_id")} for i in o["itens"]]}


def conferir_soma(o: dict) -> None:
    soma = sum(Decimal(i["total"]) for i in o["itens"])
    assert soma == Decimal(o["total"]), (soma, o["total"])


FASES = set((os.environ.get("INC5_FASES") or "base,remocao,isolamento").split(","))


def main(saida: str) -> None:
    a = sessao(os.environ["INC5_EMAIL"], os.environ["INC5_SENHA"])
    registrar("login", sessao="A", usuario=os.environ["INC5_EMAIL"], fases=sorted(FASES))
    if "base" in FASES:
        fase_base(a)
    if "remocao" in FASES:
        fase_remocao(a)
    if "regerar" in FASES:
        fase_regerar(a)
    if "isolamento" in FASES:
        fase_isolamento()
    with open(saida, "w", encoding="utf-8") as f:
        json.dump(REGISTRO, f, ensure_ascii=False, indent=1, default=str)


def fase_base(a: httpx.Client) -> None:

    # Métodos e preços do tenant (versão 1 de cada; valores de prova).
    atuais = {m["codigo"] for m in ok(a.get("/comercial/metodos"))["correntes"]}
    for corpo in (
        {"codigo": "hora_tecnica", "nome": "Hora técnica", "unidade": "hora", "valor_unitario": "250.00",
         "quantidade_padrao": "8", "padrao": True},
        {"codigo": "ccir", "nome": "Emissão/regularização de CCIR", "unidade": "fixo", "valor_unitario": "900.00",
         "rule_ids": ["REG-FUN-002"]},
        {"codigo": "inscricao_car", "nome": "Inscrição no CAR", "unidade": "fixo", "valor_unitario": "1800.00",
         "rule_ids": ["REG-BR-CAR-001"]},
    ):
        if corpo["codigo"] not in atuais:
            m = ok(a.post("/comercial/metodos", json=corpo), 201)
            registrar("metodo_criado", codigo=m["codigo"], versao=m["versao"], valor=m["valor_unitario"],
                      unidade=m["unidade"], rule_ids=m["rule_ids"], padrao=m["padrao"])

    # #25 pela CADEIA (ADR-069): diagnóstico em revisão não impede; retomada até o fim.
    pid = CASOS["#25"]
    if os.environ.get("INC5_DIAGNOSTICO") == "1":
        # Diagnóstico REAL (gateway, cadeia de modelos do projeto) deixado em revisão de propósito.
        d = ok(a.post("/agents/run", json={"agent_name": "diagnostico", "process_id": pid}))
        registrar("diagnostico_rodado", caso="#25", execucao=d.get("id"), status=d.get("status"),
                  passos=[(s["agent"], s["status"], s.get("error")) for s in d.get("steps", [])],
                  conclusoes_em_revisao=[o["id"] for s in d.get("steps", []) for o in s.get("outputs", [])])
    ex = ok(a.post("/agents/chain", json={"chain_name": "gerar_proposta", "process_id": pid}))
    registrar("cadeia_iniciada", caso="#25", execucao=ex["id"], passos=[(s["agent"], s["status"]) for s in ex["steps"]])
    red = ok(a.get(f"/processes/{pid}/comercial/redacao"))
    for tipo in ("relatorio_preliminar", "especificacao_escopo"):
        registrar("redacao_gerada", caso="#25", **resumo_redacao(red[tipo]))
    esc = red["especificacao_escopo"]
    ok(a.post(f"/processes/{pid}/comercial/redacao/{esc['id']}/revisar",
              json={"acao": "aprovar", "justificativa": "PROVA INC5 — escopo confere com a Rota validada"}))
    ex = ok(a.post(f"/evidence/executions/{ex['id']}/resume", json={"expected_revision": ex["revision"]}))
    registrar("cadeia_retomada", caso="#25", passos=[(s["agent"], s["status"]) for s in ex["steps"]],
              completa=ex["completed"])
    o = ok(a.get(f"/processes/{pid}/comercial/orcamento"))["orcamento"]
    conferir_soma(o)
    registrar("orcamento_gerado", caso="#25", **resumo_orcamento(o))
    ok(a.post(f"/processes/{pid}/comercial/orcamento/{o['id']}/revisar",
              json={"acao": "aprovar", "justificativa": "PROVA INC5 — preços de prova conferidos"}))
    ex = ok(a.post(f"/evidence/executions/{ex['id']}/resume", json={"expected_revision": ex["revision"]}))
    registrar("cadeia_concluida", caso="#25", status=ex["status"], completa=ex["completed"])

    # #23 pela API direta.
    pid = CASOS["#23"]
    r = ok(a.post(f"/processes/{pid}/comercial/redacao"), 201)
    for tipo in ("relatorio_preliminar", "especificacao_escopo"):
        registrar("redacao_gerada", caso="#23", **resumo_redacao(r[tipo]))
    ok(a.post(f"/processes/{pid}/comercial/redacao/{r['especificacao_escopo']['id']}/revisar",
              json={"acao": "aprovar", "justificativa": "PROVA INC5 — escopo confere com a Rota validada"}))
    o = ok(a.post(f"/processes/{pid}/comercial/orcamento"), 201)
    conferir_soma(o)
    registrar("orcamento_gerado", caso="#23", **resumo_orcamento(o))
    ok(a.post(f"/processes/{pid}/comercial/orcamento/{o['id']}/revisar",
              json={"acao": "aprovar", "justificativa": "PROVA INC5 — preços de prova conferidos"}))
    draft = ok(a.get("/proposals/generate-draft", params={"process_id": pid}))
    registrar("proposta_rascunho", caso="#23", orcamento_id=draft["orcamento_id"], valor=draft["suggested_value"],
              itens=[(i["description"], i["rota_passo_id"], i["orcamento_item_id"], i["total"])
                     for i in draft["scope_items"]])

    # Recarga (mesma sessão) e NOVA sessão: o mesmo estado volta do banco.
    for rotulo, cli in (("recarga", a), ("nova_sessao", sessao(os.environ["INC5_EMAIL"], os.environ["INC5_SENHA"]))):
        for caso, pid in CASOS.items():
            red = ok(cli.get(f"/processes/{pid}/comercial/redacao"))
            o = ok(cli.get(f"/processes/{pid}/comercial/orcamento"))["orcamento"]
            registrar(rotulo, caso=caso, escopo=(red["especificacao_escopo"]["id"],
                                                 red["especificacao_escopo"]["estado_revisao"],
                                                 red["especificacao_escopo"]["atualidade"]["estado"]),
                      orcamento=(o["id"], o["versao"], o["total"], o["estado_revisao"], o["atualidade"]["estado"]))


def fase_remocao(a: httpx.Client) -> None:
    """Remover um passo com motivo (#25): o orçamento marca desatualizado, não retrocede; a versão nova reflete."""
    pid = CASOS["#25"]
    antes = ok(a.get(f"/processes/{pid}/comercial/orcamento"))["orcamento"]
    rota = ok(a.get(f"/processes/{pid}/rota"))
    motivo = "PROVA INC5 — cliente apresentará o CCIR vigente; emissão fica fora do serviço"
    ja_removido = os.environ.get("INC5_PASSO_REMOVIDO")
    if ja_removido:
        # Retomada: o DELETE (204) já foi aplicado numa execução anterior deste script.
        alvo = {"id": int(ja_removido), "titulo": "Emitir ou regularizar o CCIR do imóvel"}
        registrar("passo_removido_em_execucao_anterior", caso="#25", rota=rota["id"], passo_id=alvo["id"],
                  motivo=motivo, vivos=[p["id"] for p in rota["passos"]])
    else:
        alvo = next(p for p in rota["passos"] if p["titulo"].startswith("Emitir ou regularizar o CCIR"))
        ok(a.delete(f"/rotas/{rota['id']}/passos/{alvo['id']}", params={"motivo": motivo}), 204)
        registrar("passo_removido", caso="#25", rota=rota["id"], passo_id=alvo["id"], titulo=alvo["titulo"],
                  motivo=motivo)
    depois = ok(a.get(f"/processes/{pid}/comercial/orcamento"))["orcamento"]
    rota_depois = ok(a.get(f"/processes/{pid}/rota"))
    registrar("orcamento_apos_remocao", caso="#25", id=depois["id"], versao=depois["versao"],
              estado_revisao=depois["estado_revisao"], atualidade=depois["atualidade"],
              rota_status=rota_depois["status"])
    assert depois["id"] == antes["id"] and depois["atualidade"]["estado"] == "desatualizado"
    rec = a.post(f"/processes/{pid}/comercial/orcamento")
    registrar("orcamento_sobre_escopo_desatualizado", caso="#25", http=rec.status_code, detalhe=rec.json()["detail"])
    r = ok(a.post(f"/processes/{pid}/comercial/redacao"), 201)
    registrar("redacao_regerada", caso="#25", **resumo_redacao(r["especificacao_escopo"]))
    ok(a.post(f"/processes/{pid}/comercial/redacao/{r['especificacao_escopo']['id']}/revisar",
              json={"acao": "aprovar", "justificativa": "PROVA INC5 — escopo sem o CCIR"}))
    novo = ok(a.post(f"/processes/{pid}/comercial/orcamento"), 201)
    conferir_soma(novo)
    registrar("orcamento_regerado", caso="#25", **resumo_orcamento(novo))
    assert alvo["id"] not in {i["rota_passo_id"] for i in novo["itens"]}
    assert any(f["rota_passo_id"] == alvo["id"] and motivo in f["motivo"] for f in novo["fora"])

    b = sessao(os.environ["INC5_EMAIL"], os.environ["INC5_SENHA"])
    lido = ok(b.get(f"/processes/{pid}/comercial/orcamento"))
    registrar("nova_sessao_apos_remocao", caso="#25",
              versoes=[(v["versao"], v["total"], v["estado_revisao"], v["superada_em"] is not None)
                       for v in lido["versoes"]], atual=lido["orcamento"]["atualidade"])
    ok(b.post(f"/processes/{pid}/comercial/orcamento/{novo['id']}/revisar",
              json={"acao": "aprovar", "justificativa": "PROVA INC5 — orçamento sem o CCIR"}))
    draft = ok(b.get("/proposals/generate-draft", params={"process_id": pid}))
    registrar("proposta_rascunho", caso="#25", orcamento_id=draft["orcamento_id"], valor=draft["suggested_value"],
              conclusao_em_revisao=os.environ.get("INC5_CONCLUSAO"),
              itens=[(i["description"], i["rota_passo_id"], i["orcamento_item_id"], i["total"])
                     for i in draft["scope_items"]])



def fase_regerar(a: httpx.Client) -> None:
    """Versão nova de relatório, escopo e orçamento do #25; a anterior fica superada."""
    pid = CASOS["#25"]
    antes = ok(a.get(f"/processes/{pid}/comercial/orcamento"))["orcamento"]
    r = ok(a.post(f"/processes/{pid}/comercial/redacao"), 201)
    registrar("relatorio_regerado", caso="#25", **resumo_redacao(r["relatorio_preliminar"]))
    registrar("escopo_regerado", caso="#25", **resumo_redacao(r["especificacao_escopo"]))
    lido = ok(a.get(f"/processes/{pid}/comercial/orcamento"))["orcamento"]
    registrar("orcamento_apos_escopo_novo", caso="#25", id=lido["id"], versao=lido["versao"],
              estado_revisao=lido["estado_revisao"], atualidade=lido["atualidade"], era=antes["atualidade"])
    ok(a.post(f"/processes/{pid}/comercial/redacao/{r['especificacao_escopo']['id']}/revisar",
              json={"acao": "aprovar", "justificativa": "PROVA INC5 — escopo regerado após correção"}))
    o = ok(a.post(f"/processes/{pid}/comercial/orcamento"), 201)
    conferir_soma(o)
    registrar("orcamento_regerado", caso="#25", **resumo_orcamento(o))
    ok(a.post(f"/processes/{pid}/comercial/orcamento/{o['id']}/revisar",
              json={"acao": "aprovar", "justificativa": "PROVA INC5 — orçamento conferido"}))
    b = sessao(os.environ["INC5_EMAIL"], os.environ["INC5_SENHA"])
    for caso, p in CASOS.items():
        lido = ok(b.get(f"/processes/{p}/comercial/orcamento"))
        red = ok(b.get(f"/processes/{p}/comercial/redacao"))
        registrar("nova_sessao_final", caso=caso,
                  relatorio=(red["relatorio_preliminar"]["id"], red["relatorio_preliminar"]["versao"],
                             red["relatorio_preliminar"]["atualidade"]["estado"]),
                  escopo=(red["especificacao_escopo"]["id"], red["especificacao_escopo"]["versao"],
                          red["especificacao_escopo"]["estado_revisao"], red["especificacao_escopo"]["atualidade"]["estado"]),
                  orcamento=(lido["orcamento"]["id"], lido["orcamento"]["versao"], lido["orcamento"]["total"],
                             lido["orcamento"]["estado_revisao"], lido["orcamento"]["atualidade"]["estado"]),
                  versoes=[(v["versao"], v["total"], v["estado_revisao"], v["superada_em"] is not None)
                           for v in lido["versoes"]])
    draft = ok(b.get("/proposals/generate-draft", params={"process_id": pid}))
    registrar("proposta_rascunho", caso="#25", orcamento_id=draft["orcamento_id"], valor=draft["suggested_value"],
              itens=[(i["description"], i["rota_passo_id"], i["orcamento_item_id"], i["total"])
                     for i in draft["scope_items"]])


def fase_isolamento() -> None:
    """Usuário de outro tenant."""
    x = sessao(os.environ["INC5_EMAIL_OUTRO"], os.environ["INC5_SENHA_OUTRO"])
    registrar("isolamento", orcamento_23=x.get(f"/processes/{CASOS['#23']}/comercial/orcamento").status_code,
              redacao_25=x.get(f"/processes/{CASOS['#25']}/comercial/redacao").status_code,
              metodos=ok(x.get("/comercial/metodos")))


if __name__ == "__main__":
    main(sys.argv[1])
