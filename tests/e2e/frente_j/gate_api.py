"""Gate E2E da Frente J — a sequência inteira contra a API REAL, autenticada.

Não é teste unitário: exige API + worker Celery + Redis + MinIO + Postgres
descartável de pé (`setup_db.py`) e uma chave de LLM válida no ambiente do
worker (a extração é real, como em produção). O que ele prova, na ordem
exigida pela reauditoria Codex de 11/09:

  1. subir os 6 docs da ELODI (texto REAL de produção, docs 546-551, em PDF
     de texto) → OCR (pypdf) → extração (LLM) → staging;
  2. abrir a Conferência (GET /staging-decisions) → decisões existem;
  3. decidir 3 — uma delas com EDIÇÃO DE TIPO (`reclassificar`);
  4. consolidar (POST /consolidar);
  5. "recarregar" (GET de novo, mesma sessão) e depois LOGOUT/LOGIN (sessão
     nova) → as mesmas decisões, mesmos estados, mesmos números nas seis
     telas (payload de cada aba, comparado campo a campo);
  6. subir documento novo → diagnóstico, rota e proposta marcados
     desatualizados; tentar aceitar a proposta → 422 com a razão.

Tudo o que a API devolveu vai para `--out` (JSON), para ser colado no
relatório. Nenhum valor é inventado: o script só compara o que leu.

Uso:
    python tests/e2e/frente_j/gate_api.py --base http://127.0.0.1:8000 \
        --seed <json impresso por setup_db.py> --pdfs <pasta com os 6 PDFs> \
        --out docs/trabalhos/fechamento_contrato/gate_api
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

DOCS = [
    # (arquivo, document_type, document_category) — mesma taxonomia do #23 real
    ("CAR FAZ B1 B2 B3 E BA - ELODI 2016.pdf", "car", "ambientais"),
    ("B1 - M3.181 - FAZ. R. Olhos d'agua - Elodi 2013 926ha.pdf", "matricula", "fundiarios"),
    ("B2 - M3.313 - FAZ. NH 2 - Elodi 2014 725ha.pdf", "matricula", "fundiarios"),
    ("B3 - M3.673 - FAZ Posse G4 - Elodi 2016 212ha.pdf", "matricula", "fundiarios"),
    ("B4 - M4.387 - FAZ Posse G3 - Elodi 2020 316ha.pdf", "matricula", "fundiarios"),
    ("CNH-e.pdf.pdf", "doc_pessoal", "societarios"),
]

# As seis abas do processo (ProcessDetailTypes.TABS) e o que cada uma lê.
SCREENS = {
    "visao_geral": ["/processes/{pid}", "/processes/{pid}/diagnoses", "/properties/{prop}/issues",
                    "/properties/{prop}/diagnosis-notes", "/processes/{pid}/rota"],
    "documentos": ["/documents/?process_id={pid}"],
    "conferencia": ["/processes/{pid}/staging-decisions", "/processes/{pid}/staging-fields",
                    "/processes/{pid}/progresso", "/processes/{pid}/requisitos",
                    "/processes/{pid}/confronto-identidade", "/processes/{pid}/matriculas-vigentes"],
    "dados": ["/processes/{pid}/dossier"],
    "acoes": ["/processes/{pid}/acoes"],
    "saidas": ["/processes/{pid}/artifacts"],
}

VOLATEIS = {"updated_at", "ai_job_id", "token", "access_token", "expires_at", "desde", "generated_at",
            "created_at", "ultima_atualizacao", "timestamp", "download_url", "upload_url"}


class Gate:
    def __init__(self, base: str, seed: dict[str, Any], pdfs: Path, out: Path):
        self.base = base.rstrip("/") + "/api/v1"
        self.seed = seed
        self.pdfs = pdfs
        self.out = out
        self.out.mkdir(parents=True, exist_ok=True)
        self.log: list[dict[str, Any]] = []
        self.cli = httpx.Client(timeout=120)
        self.token: str | None = None

    # ── infra ────────────────────────────────────────────────────────────
    def _rec(self, passo: str, **dados: Any) -> None:
        item = {"t": datetime.now(UTC).isoformat(), "passo": passo, **dados}
        self.log.append(item)
        resumo = {k: v for k, v in dados.items() if k not in ("payload",)}
        print(f"[{passo}] {json.dumps(resumo, ensure_ascii=False, default=str)[:400]}", file=sys.stderr)

    def _h(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def get(self, path: str) -> httpx.Response:
        return self.cli.get(self.base + path, headers=self._h())

    def post(self, path: str, **kw: Any) -> httpx.Response:
        return self.cli.post(self.base + path, headers=self._h(), **kw)

    def patch(self, path: str, **kw: Any) -> httpx.Response:
        return self.cli.patch(self.base + path, headers=self._h(), **kw)

    def salvar(self, nome: str, dados: Any) -> None:
        with open(self.out / f"{nome}.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(dados, ensure_ascii=False, indent=1, default=str))

    # ── passos ───────────────────────────────────────────────────────────
    def login(self) -> None:
        r = self.cli.post(
            self.base + "/auth/login",
            data={"username": self.seed["email"], "password": self.seed["password"]},
            headers={"X-Auth-Profile": "internal"},
        )
        assert r.status_code == 200, f"login falhou: {r.status_code} {r.text}"
        self.token = r.json()["access_token"]
        self._rec("login", status=r.status_code, email=self.seed["email"])

    def logout(self) -> None:
        r = self.post("/auth/logout")
        self._rec("logout", status=r.status_code)
        self.token = None
        # A sessão antiga não pode mais ler nada.
        r2 = self.get(f"/processes/{self.seed['process_id']}")
        self._rec("sessao_antiga_sem_token", status=r2.status_code)
        assert r2.status_code == 401, "sem token ainda leu o processo"

    def upload(self, nome: str, doc_type: str, categoria: str) -> dict[str, Any]:
        pid = self.seed["process_id"]
        caminho = self.pdfs / nome
        dados = caminho.read_bytes()
        r = self.post("/documents/upload-url", json={"process_id": pid, "filename": nome,
                                                     "content_type": "application/pdf"})
        assert r.status_code == 200, f"upload-url: {r.status_code} {r.text}"
        url, key = r.json()["upload_url"], r.json()["storage_key"]
        put = self.cli.put(url, content=dados, headers={"Content-Type": "application/pdf"})
        assert put.status_code in (200, 204), f"PUT storage: {put.status_code} {put.text[:200]}"
        r = self.post("/documents/confirm-upload", json={
            "process_id": pid, "storage_key": key, "filename": nome,
            "content_type": "application/pdf", "file_size_bytes": len(dados),
            "document_type": doc_type, "document_category": categoria,
        })
        assert r.status_code in (200, 201, 202), f"confirm-upload: {r.status_code} {r.text}"
        doc = r.json()
        self._rec("upload", arquivo=nome, document_id=doc.get("id"), status=r.status_code,
                  lifecycle_status=doc.get("lifecycle_status"))
        return doc

    def esperar_extracao(self, ids: list[int], timeout_s: int = 1500) -> list[dict[str, Any]]:
        """Espera OCR + extração de TODOS os documentos. Critério: nenhum doc em
        pending/processing e, para os que têm texto legível, staging presente
        ou `extraction_status` preenchido (o extrator escreve um ou outro)."""
        pid = self.seed["process_id"]
        inicio = time.time()
        while True:
            docs = self.get(f"/documents/?process_id={pid}").json()
            por_id = {d["id"]: d for d in docs}
            staging = self.get(f"/processes/{pid}/staging-fields").json()
            com_staging = {f.get("document_id") for f in staging}
            pendentes = []
            for i in ids:
                d = por_id.get(i, {})
                if d.get("ocr_status") in (None, "pending", "processing"):
                    pendentes.append((i, "ocr"))
                    continue
                if d.get("tem_texto") and i not in com_staging and not d.get("extraction_status"):
                    pendentes.append((i, "extracao"))
            if not pendentes:
                self._rec("extracao_concluida", segundos=int(time.time() - inicio),
                          staging_total=len(staging),
                          por_doc={str(i): sum(1 for f in staging if f.get("document_id") == i) for i in ids},
                          lifecycle={str(i): por_id[i].get("lifecycle_status") for i in ids})
                return docs
            if time.time() - inicio > timeout_s:
                raise TimeoutError(f"extração não terminou: {pendentes}")
            time.sleep(10)

    def telas(self, rotulo: str) -> dict[str, Any]:
        pid, prop = self.seed["process_id"], self.seed["property_id"]
        saida: dict[str, Any] = {}
        for tela, rotas in SCREENS.items():
            saida[tela] = {}
            for rota in rotas:
                path = rota.format(pid=pid, prop=prop)
                r = self.get(path)
                saida[tela][path] = {"status": r.status_code, "payload": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text}
        self.salvar(f"telas_{rotulo}", saida)
        self._rec("telas", rotulo=rotulo, resumo=_resumo_telas(saida))
        return saida

    def decidir_tres(self, decisoes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        pid = self.seed["process_id"]
        feitas: list[dict[str, Any]] = []

        def _post(chave: dict[str, str], **extra: Any) -> dict[str, Any]:
            r = self.post(f"/processes/{pid}/staging-decisions/decidir", json={**chave, **extra})
            assert r.status_code == 200, f"decidir {chave} {extra}: {r.status_code} {r.text}"
            return r.json()

        pendentes = [d for d in decisoes if d["estado"] == "pendente"]
        # (1) composição de uma matrícula — o REC-001 literal (CAR + certidão).
        comp = next((d for d in pendentes if d["chave"]["aspecto"] == "composicao"), None)
        # (2) área ou gravames de outra matrícula.
        outra = next((d for d in pendentes if d["chave"]["aspecto"] in ("area", "car", "reserva_legal")
                      and d is not comp), None)
        # (3) EDIÇÃO DE TIPO: uma evidência tipada de uma decisão de gravames
        # (o tipo é o que o consultor corrige quando o modelo erra — ADR-065).
        grav = next((d for d in pendentes if d["chave"]["aspecto"] == "gravames"
                     and any(e.get("tipo_observacao") for e in d["evidencias"])), None)
        assert comp and outra and grav, f"faltou decisão para o gate: comp={bool(comp)} outra={bool(outra)} grav={bool(grav)}"

        r1 = _post(comp["chave"], acao="aceitar")
        feitas.append({"decisao": comp["chave"], "acao": "aceitar", "estado_depois": r1["estado"]})
        r2 = _post(outra["chave"], acao="aceitar")
        feitas.append({"decisao": outra["chave"], "acao": "aceitar", "estado_depois": r2["estado"]})

        ev = next(e for e in grav["evidencias"] if e.get("tipo_observacao"))
        tipo_antes = ev["tipo_observacao"]
        # Gravame → gravame: exercita o mecanismo sem inventar fato (a
        # reclassificação real é decisão da consultora, não do gate).
        tipo_novo = "alienacao_fiduciaria" if tipo_antes != "alienacao_fiduciaria" else "hipoteca"
        r3 = _post(grav["chave"], acao="reclassificar", staging_id=ev["staging_id"], tipo_observacao=tipo_novo)
        ev_depois = next(e for e in r3["evidencias"] if e["staging_id"] == ev["staging_id"])
        assert ev_depois["tipo_observacao"] == tipo_novo, ev_depois
        linha = next(f for f in self.get(f"/processes/{pid}/staging-fields").json() if f["id"] == ev["staging_id"])
        assert (linha.get("atributos") or {}).get("tipo_sugerido") == tipo_antes, linha.get("atributos")
        feitas.append({"decisao": grav["chave"], "acao": "reclassificar", "staging_id": ev["staging_id"],
                       "tipo_sugerido": tipo_antes, "tipo_decidido": tipo_novo,
                       "evidencia_depois": ev_depois, "estado_depois": r3["estado"]})
        # e a mesma decisão de gravames, agora com o tipo decidido, é aceita.
        r4 = _post(grav["chave"], acao="aceitar")
        feitas.append({"decisao": grav["chave"], "acao": "aceitar", "estado_depois": r4["estado"]})
        self._rec("decisoes", feitas=feitas)
        self.salvar("decisoes_feitas", feitas)
        return feitas

    def consolidar(self) -> dict[str, Any]:
        pid = self.seed["process_id"]
        r = self.post(f"/processes/{pid}/consolidar", json={})
        assert r.status_code == 200, f"consolidar: {r.status_code} {r.text}"
        res = r.json()
        self._rec("consolidar", status=r.status_code, resumo={k: v for k, v in res.items() if not isinstance(v, (list, dict))})
        self.salvar("consolidacao", res)
        return res

    def artefatos_e_proposta(self) -> dict[str, Any]:
        """Diagnóstico (POST + validate), rota (via API se houver; senão registra
        ausência) e proposta (POST + send) — o chão que o documento novo vai
        invalidar."""
        pid, cid = self.seed["process_id"], self.seed["client_id"]
        diag = self.post(f"/processes/{pid}/diagnoses", json={"content": {
            "content": "Diagnóstico preliminar — gate E2E Frente J.",
            "sources": [{"type": "legislation", "ref": "gate-e2e"}],
            "hipoteses": ["CAR pendente de retificação"], "lacunas": [], "riscos": [],
            "checklist_documental": ["Matrícula"],
        }})
        assert diag.status_code == 201, f"diagnoses: {diag.status_code} {diag.text}"
        versao = diag.json()["version"]
        val = self.patch(f"/processes/{pid}/diagnoses/{versao}/validate")
        assert val.status_code == 200, f"validate: {val.status_code} {val.text}"
        prop = self.post("/proposals/", json={
            "client_id": cid, "process_id": pid, "title": "Proposta — gate E2E Frente J",
            "scope_items": [{"description": "Retificação do CAR", "unit": "un", "qty": 1,
                             "unit_price": 1000.0, "total": 1000.0}],
            "total_value": 1000.0, "validity_days": 30,
        })
        assert prop.status_code == 201, f"proposal: {prop.status_code} {prop.text}"
        prop_id = prop.json()["id"]
        env = self.post(f"/proposals/{prop_id}/send")
        assert env.status_code == 200, f"send: {env.status_code} {env.text}"
        antes = {
            "diagnostico": self.get(f"/processes/{pid}/diagnoses").json(),
            "rota": self.get(f"/processes/{pid}/rota").json(),
            "proposta": self.get(f"/proposals/{prop_id}").json(),
        }
        self.salvar("artefatos_antes", antes)
        self._rec("artefatos_criados", diagnostico_versao=versao, proposta_id=prop_id,
                  aviso_diag=_ultimo_aviso(antes["diagnostico"]),
                  aviso_prop=antes["proposta"].get("aviso_desatualizado"))
        return {"proposta_id": prop_id, "versao": versao, "antes": antes}

    def invalidar_e_recusar(self, ctx: dict[str, Any]) -> dict[str, Any]:
        pid = self.seed["process_id"]
        # Documento NOVO depois do diagnóstico validado e da proposta enviada:
        # reenvio do CAR (mesmo texto; o que importa é a chegada).
        doc = self.upload("CAR FAZ B1 B2 B3 E BA - ELODI 2016.pdf", "car", "ambientais")
        depois = {
            "diagnostico": self.get(f"/processes/{pid}/diagnoses").json(),
            "rota": self.get(f"/processes/{pid}/rota").json(),
            "proposta": self.get(f"/proposals/{ctx['proposta_id']}").json(),
        }
        self.salvar("artefatos_depois", depois)
        aviso_diag = _ultimo_aviso(depois["diagnostico"])
        aviso_prop = depois["proposta"].get("aviso_desatualizado")
        aviso_rota = (depois["rota"] or {}).get("aviso_desatualizado") if depois["rota"] else "sem rota no processo"
        assert aviso_diag, "diagnóstico validado NÃO ficou desatualizado após documento novo"
        assert aviso_prop, "proposta enviada NÃO ficou desatualizada após documento novo"
        rec = self.post(f"/proposals/{ctx['proposta_id']}/accept")
        assert rec.status_code == 422, f"aceite deveria ser recusado: {rec.status_code} {rec.text}"
        prop_final = self.get(f"/proposals/{ctx['proposta_id']}").json()
        assert prop_final["status"] == "sent", prop_final["status"]
        resultado = {"documento_novo": doc, "aviso_diagnostico": aviso_diag, "aviso_rota": aviso_rota,
                     "aviso_proposta": aviso_prop, "aceite": {"status": rec.status_code, "detail": rec.json()},
                     "status_proposta_depois": prop_final["status"]}
        self._rec("invalidacao", **{k: v for k, v in resultado.items() if k != "documento_novo"})
        self.salvar("invalidacao", resultado)
        return resultado

    # ── orquestração ─────────────────────────────────────────────────────
    def run(self) -> None:
        pid = self.seed["process_id"]
        self.login()
        docs = [self.upload(*d) for d in DOCS]
        self.esperar_extracao([d["id"] for d in docs])
        self.telas("apos_extracao")

        decisoes = self.get(f"/processes/{pid}/staging-decisions").json()
        self.salvar("decisoes_apos_extracao", decisoes)
        self._rec("conferencia", decisoes=len(decisoes["decisoes"]), sem_agrupamento=len(decisoes["sem_agrupamento"]),
                  total_staging=decisoes["total_staging"],
                  chaves=[f"{d['chave']['entidade']}:{d['chave']['identificador']}:{d['chave']['aspecto']}" for d in decisoes["decisoes"]])
        self.decidir_tres(decisoes["decisoes"])
        self.consolidar()

        a = self.telas("apos_consolidar")
        b = self.telas("recarregar")          # mesma sessão, GET de novo
        self.logout()
        self.login()
        c = self.telas("sessao_nova")         # logout/login
        difs_ab = _diff_telas(a, b)
        difs_ac = _diff_telas(a, c)
        self._rec("comparacao_telas", recarregar_vs_consolidar=difs_ab, sessao_nova_vs_consolidar=difs_ac)
        assert not difs_ab, f"recarregar mudou algo: {difs_ab}"
        assert not difs_ac, f"sessão nova mudou algo: {difs_ac}"

        ctx = self.artefatos_e_proposta()
        self.invalidar_e_recusar(ctx)
        self.salvar("log", self.log)
        print(json.dumps({"ok": True, "out": str(self.out)}, ensure_ascii=False))


def _ultimo_aviso(diags: list[dict[str, Any]]) -> Any:
    if not diags:
        return None
    ultimo = max(diags, key=lambda d: d.get("version", 0))
    return ultimo.get("aviso_desatualizado")


def _limpar(obj: Any) -> Any:
    """Remove campos voláteis (carimbos de tempo, URLs presignadas) antes de
    comparar telas — o que tem de bater é o CONTEÚDO, não o relógio."""
    if isinstance(obj, dict):
        return {k: _limpar(v) for k, v in obj.items() if k not in VOLATEIS}
    if isinstance(obj, list):
        return [_limpar(v) for v in obj]
    return obj


def _diff_telas(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    difs = []
    for tela in a:
        for rota in a[tela]:
            la, lb = _limpar(a[tela][rota]), _limpar(b[tela].get(rota))
            if la != lb:
                difs.append(f"{tela} {rota}")
    return difs


def _resumo_telas(t: dict[str, Any]) -> dict[str, Any]:
    r: dict[str, Any] = {}
    conf = t.get("conferencia", {})
    for rota, v in conf.items():
        p = v.get("payload")
        if rota.endswith("staging-decisions") and isinstance(p, dict):
            r["decisoes"] = len(p.get("decisoes", []))
            r["sem_agrupamento"] = len(p.get("sem_agrupamento", []))
            r["estados"] = sorted({d["estado"] for d in p.get("decisoes", [])})
        if rota.endswith("progresso") and isinstance(p, dict):
            r["progresso"] = p.get("conferencia")
        if rota.endswith("staging-fields") and isinstance(p, list):
            r["staging"] = len(p)
    docs = t.get("documentos", {})
    for v in docs.values():
        if isinstance(v.get("payload"), list):
            r["documentos"] = {d.get("original_file_name", "")[:24]: d.get("lifecycle_status") for d in v["payload"]}
    return r


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--seed", required=True, help="JSON impresso por setup_db.py (arquivo)")
    ap.add_argument("--pdfs", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    seed = json.loads(Path(args.seed).read_text(encoding="utf-8"))
    Gate(args.base, seed, Path(args.pdfs), Path(args.out)).run()


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()
