"""Gate E2E da Frente J — complemento dos percursos 1 e 2.

Dois passos que o `gate_api.py` não cobre e que a reauditoria exige nomeados:

  passo 5  — ESCOLHER A FONTE numa divergência SEM fonte autoritativa, pelo
             cartão agrupado, e provar que os irmãos da mesma matrícula NÃO
             são rejeitados (o bug que a validação desta frente achou:
             `_reject_siblings` casando `target_field IS NULL` derrubaria
             todas as observações sem destino daquela matrícula de uma vez).
  passo 11 — REEXTRAIR documento antigo com texto CACHEADO (o caminho literal
             do #23 em 11/09: o extrator rodado por processo relê o
             `extracted_text` que já está no banco, sem re-OCR) e provar que
             o diagnóstico validado ANTES fica desatualizado por EVIDÊNCIA
             NOVA — o falso negativo que o item 1 fecha (`created_at` de
             staging, não `updated_at`).

Roda depois do `gate_api.py`, contra a mesma pilha e o mesmo processo.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

DIAG_CONTENT = {
    "content": "Diagnóstico preliminar — gate E2E Frente J, versão para o passo 11.",
    "sources": [{"type": "legislation", "ref": "gate-e2e-passo-11"}],
    "hipoteses": ["Reserva legal a conferir entre CAR e matrículas"],
    "lacunas": [], "riscos": [], "checklist_documental": ["Matrícula"],
}


class Complemento:
    def __init__(self, base: str, seed: dict, out: Path):
        self.api = base.rstrip("/") + "/api/v1"
        self.seed = seed
        self.out = out
        self.out.mkdir(parents=True, exist_ok=True)
        self.cli = httpx.Client(timeout=300)
        r = self.cli.post(self.api + "/auth/login",
                          data={"username": seed["email"], "password": seed["password"]},
                          headers={"X-Auth-Profile": "internal"})
        assert r.status_code == 200, r.text
        self.h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    def get(self, p: str) -> Any:
        r = self.cli.get(self.api + p, headers=self.h)
        assert r.status_code == 200, f"GET {p}: {r.status_code} {r.text[:300]}"
        return r.json()

    def decisoes(self) -> dict:
        return self.get(f"/processes/{self.seed['process_id']}/staging-decisions")

    # ── passo 5 ─────────────────────────────────────────────────────────
    def passo_5(self) -> dict[str, Any]:
        pid = self.seed["process_id"]
        rec = self.decisoes()
        staging_antes = {s["id"]: s["status"] for s in self.get(f"/processes/{pid}/staging-fields")}

        # (a) divergência SEM fonte autoritativa — no caso real da ELODI é a
        # Reserva Legal do imóvel: CAR (437,7632) × soma das matrículas
        # (492,9252), 11,19%, crítico, nenhuma evidência marcada autoritativa.
        div = next(d for d in rec["decisoes"]
                   if d["concordancia"] == "divergem"
                   and not any(e.get("fonte_autoritativa") for e in d["evidencias"]))
        ev = next(e for e in div["evidencias"] if e["staging_id"] is not None)
        r = self.cli.post(f"{self.api}/processes/{pid}/staging-decisions/decidir", headers=self.h,
                          json={**div["chave"], "acao": "escolher_fonte", "staging_id": ev["staging_id"]})
        assert r.status_code == 200, f"escolher_fonte: {r.status_code} {r.text[:300]}"
        depois_a = r.json()

        # (b) o caso que exercita a guarda: escolher a fonte de UMA evidência
        # de gravame (linha SEM destino — gravame nunca tem coluna própria,
        # ADR-065). Os outros atos da MESMA matrícula não podem ser rejeitados.
        grav = next(d for d in rec["decisoes"]
                    if d["chave"]["aspecto"] == "gravames" and d["estado"] == "pendente"
                    and len(d["evidencias"]) >= 3)
        alvo = grav["evidencias"][0]
        irmaos = [e["staging_id"] for e in grav["evidencias"][1:] if e["staging_id"] is not None]
        r = self.cli.post(f"{self.api}/processes/{pid}/staging-decisions/decidir", headers=self.h,
                          json={**grav["chave"], "acao": "escolher_fonte",
                                "staging_id": alvo["staging_id"]})
        assert r.status_code == 200, f"escolher_fonte gravame: {r.status_code} {r.text[:300]}"

        staging_depois = {s["id"]: s["status"] for s in self.get(f"/processes/{pid}/staging-fields")}
        rejeitados = [i for i, st in staging_depois.items()
                      if st == "rejeitado" and staging_antes.get(i) != "rejeitado"]
        return {
            "a_divergencia_sem_fonte_autoritativa": {
                "chave": div["chave"], "nivel": div.get("nivel_divergencia"),
                "percentual": div.get("percentual"),
                "evidencias": [{k: e[k] for k in ("staging_id", "documento_tipo", "campo",
                                                  "valor_normalizado", "fonte_autoritativa")}
                               for e in div["evidencias"]],
                "escolhida": ev["staging_id"],
                "estado_depois": depois_a["estado"] if depois_a else None,
                "status_da_escolhida": staging_depois.get(ev["staging_id"]),
            },
            "b_gravame_sem_destino": {
                "chave": grav["chave"], "escolhida": alvo["staging_id"],
                "irmaos_da_mesma_matricula": irmaos,
                "status_dos_irmaos_depois": {str(i): staging_depois.get(i) for i in irmaos},
                "irmaos_rejeitados": [i for i in irmaos if staging_depois.get(i) == "rejeitado"],
            },
            "rejeitados_no_processo_inteiro": rejeitados,
        }

    # ── passo 11 ────────────────────────────────────────────────────────
    def passo_11(self) -> dict[str, Any]:
        pid = self.seed["process_id"]
        docs_antes = self.get(f"/documents/?process_id={pid}")
        extracted_antes = {d["id"]: d.get("extraction_status") for d in docs_antes}
        staging_antes = {s["id"] for s in self.get(f"/processes/{pid}/staging-fields")}

        # Diagnóstico NOVO, validado AGORA: o corte passa a ser posterior a
        # todo documento do processo — sem isto o aviso viria do documento
        # novo do percurso 2, e o item 1 não ficaria provado isoladamente.
        r = self.cli.post(f"{self.api}/processes/{pid}/diagnoses", headers=self.h,
                          json={"content": DIAG_CONTENT})
        assert r.status_code == 201, r.text
        versao = r.json()["version"]
        r = self.cli.patch(f"{self.api}/processes/{pid}/diagnoses/{versao}/validate", headers=self.h)
        assert r.status_code == 200, r.text
        validado_em = r.json().get("validated_at")
        aviso_antes = self._aviso_diag(versao)
        assert aviso_antes is None, f"diagnóstico já nasceu desatualizado: {aviso_antes}"

        # Reextração com TEXTO CACHEADO: o extrator rodado por PROCESSO relê o
        # `extracted_text` que já está no banco (nenhum re-OCR, nenhum
        # download do storage) — é o gesto do painel "Rodar no processo".
        t0 = time.time()
        r = self.cli.post(f"{self.api}/agents/run", headers=self.h,
                          json={"agent_name": "extrator", "process_id": pid})
        assert r.status_code == 200, f"agents/run: {r.status_code} {r.text[:400]}"
        corpo = r.json()

        staging_depois = {s["id"] for s in self.get(f"/processes/{pid}/staging-fields")}
        novas = sorted(staging_depois - staging_antes)
        docs_depois = self.get(f"/documents/?process_id={pid}")
        aviso_depois = self._aviso_diag(versao)
        return {
            "diagnostico_versao": versao, "validado_em": validado_em,
            "aviso_antes_da_reextracao": aviso_antes,
            "segundos_reextracao": round(time.time() - t0, 1),
            "agente": {"status": corpo.get("status"),
                       "fields_count": (corpo.get("data") or {}).get("fields_count"),
                       "documentos": [(d or {}).get("document_id")
                                      for d in ((corpo.get("data") or {}).get("por_documento") or [])]},
            "staging_antes": len(staging_antes), "staging_depois": len(staging_depois),
            "linhas_novas": len(novas), "ids_novos": novas[:40],
            "ocr_rodou_de_novo": any(
                (d.get("extraction_status") or "") != (extracted_antes.get(d["id"]) or "")
                for d in docs_depois if d["id"] in extracted_antes),
            "aviso_depois_da_reextracao": aviso_depois,
        }

    def _aviso_diag(self, versao: int) -> Any:
        diags = self.get(f"/processes/{self.seed['process_id']}/diagnoses")
        d = next((x for x in diags if x["version"] == versao), None)
        return (d or {}).get("aviso_desatualizado")

    def run(self) -> None:
        resultado = {"gerado_em": datetime.now(UTC).isoformat(),
                     "passo_5_escolher_fonte": self.passo_5(),
                     "passo_11_reextracao_cacheada": self.passo_11()}
        (self.out / "complemento.json").write_text(
            json.dumps(resultado, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        print(json.dumps(resultado, ensure_ascii=False, indent=1, default=str))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--seed", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    sys.path.insert(0, ".")
    seed = json.loads(Path(args.seed).read_text(encoding="utf-8"))
    Complemento(args.base, seed, Path(args.out)).run()


if __name__ == "__main__":
    main()
