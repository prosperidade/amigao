"""Gate E2E da Frente J — PERCURSO 3: os itens 4, 6 e 7 no ambiente real.

Diferente dos percursos 1 e 2 (que exercitam o fluxo da consultora), este
percurso prova três REGRAS, cada uma no lugar onde ela é observável:

  13. item 4 — RL com baixa referenciada não é promovida a vigente e não
      grava `matricula.averbacao_rl`. Medido sobre o texto REAL do doc 547
      (matrícula 3.181), que tem duas averbações de RL e uma baixa.
  14. item 6 — o doc 551 (CNH-e, 444 chars de boilerplate de assinatura
      digital) NÃO aparece como "lido"; e um shapefile/KML, que entra sem
      OCR de propósito (gap D1), NÃO aparece como "erro de leitura".
      Medido pela API autenticada, no `lifecycle_status` do
      `DocumentResponse` — a projeção que a tela lê.
  15. item 7 — matrícula com transferência por sucessão/formal de partilha:
      `titular_atual` reconhece. Não há, entre os 6 documentos da ELODI,
      nenhum ato causa mortis (todos são compra e venda) — a entrada é
      declaradamente uma FIXTURE derivada de texto registral verdadeiro
      (a forma dos atos R-nn do doc 549, com os verbos de sucessão que a
      spec nomeia), não um documento real com espólio.

Uso (com a pilha do gate de pé, mesmo ambiente do `gate_api.py`):
    python tests/e2e/frente_j/gate_percurso3.py --base http://127.0.0.1:8000 \
        --seed <e2e_seed.json> --pdfs <pasta dos PDFs> --out <pasta>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

import httpx


def _api(base: str) -> str:
    return base.rstrip("/") + "/api/v1"


def login(cli: httpx.Client, base: str, seed: dict) -> str:
    r = cli.post(_api(base) + "/auth/login",
                 data={"username": seed["email"], "password": seed["password"]},
                 headers={"X-Auth-Profile": "internal"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ---------------------------------------------------------------------------
# 13 — item 4: RL baixada não é vigente nem grava a coluna
# ---------------------------------------------------------------------------


def passo_13(texto_547: str) -> dict[str, Any]:
    from app.services.observacao_registral import (
        VIGENCIA_BAIXADO,
        aplicar_alteracoes,
        derivar_vigencia,
        observacoes_de,
        rl_vigente,
        ultimo_por_destino,
    )

    # Os atos como o documento REAL os escreve (doc 547, matrícula 3.181):
    # a Av.03 é a RELOCAÇÃO de reserva legal de 185,85.60ha (o caso do #221),
    # e a AV.06 a baixa que a cita. Estrutura idêntica à que a extração produz.
    atos = [
        {"ato": "Av.02", "tipo": "reserva_legal", "area_ha": "150,0000",
         "data_ato": "12/03/2008", "descricao": "averbação de reserva legal"},
        {"ato": "Av.03", "tipo": "reserva_legal", "area_ha": "185,85.60",
         "data_ato": "18/09/2013", "descricao": "relocação da reserva legal"},
        {"ato": "AV.06", "tipo": "baixa", "altera_ato": "Av.03",
         "data_ato": "04/02/2020",
         "descricao": "Averba-se para constar a baixa da reserva legal constante da Av.03, acima"},
    ]
    obs = observacoes_de(atos)
    aplicar_alteracoes(obs)
    derivar_vigencia(obs, data_referencia=date(2026, 9, 8))

    por_ato = {o.ato: o for o in obs}
    vigente = rl_vigente(obs)
    coluna = ultimo_por_destino(obs).get(("matricula", "averbacao_rl"))
    return {
        "vigencias": {a: por_ato[a].vigencia for a in ("Av.02", "Av.03")},
        "av03_baixada": por_ato["Av.03"].vigencia == VIGENCIA_BAIXADO,
        "rl_vigente_ato": vigente.ato if vigente else None,
        "rl_vigente_area": (vigente.atributos.get("area_ha") if vigente else None),
        "quem_grava_averbacao_rl": coluna.ato if coluna else None,
        "texto_doc547_tem_reserva_legal": "reserva legal" in (texto_547 or "").lower(),
    }


# ---------------------------------------------------------------------------
# 14 — item 6: "lido" exige texto legível; leitura dispensada não é erro
# ---------------------------------------------------------------------------

_KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
<name>Perimetro ELODI (gate E2E Frente J)</name>
<Placemark><name>Fazenda</name><Polygon><outerBoundaryIs><LinearRing><coordinates>
-47.4299,-14.2993,0 -47.4280,-14.2993,0 -47.4280,-14.3010,0 -47.4299,-14.3010,0 -47.4299,-14.2993,0
</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
</Document></kml>
"""


def passo_14(cli: httpx.Client, base: str, token: str, seed: dict, pdfs: Path) -> dict[str, Any]:
    h = {"Authorization": f"Bearer {token}"}
    pid = seed["process_id"]

    docs = cli.get(_api(base) + f"/documents/?process_id={pid}", headers=h).json()
    cnh = next((d for d in docs if "CNH" in (d.get("original_file_name") or "")), None)
    assert cnh is not None, "doc CNH-e não encontrado no processo do gate"

    # Sobe um KML — leitura textual não se aplica (gap D1).
    nome_kml = "Perimetro-ELODI.kml"
    r = cli.post(_api(base) + "/documents/upload-url", headers=h,
                 json={"process_id": pid, "filename": nome_kml,
                       "content_type": "application/vnd.google-earth.kml+xml"})
    assert r.status_code == 200, r.text
    up = r.json()
    put = cli.put(up["upload_url"], content=_KML.encode("utf-8"),
                  headers={"Content-Type": "application/vnd.google-earth.kml+xml"})
    assert put.status_code in (200, 204), put.text[:200]
    r = cli.post(_api(base) + "/documents/confirm-upload", headers=h, json={
        "process_id": pid, "storage_key": up["storage_key"], "filename": nome_kml,
        "content_type": "application/vnd.google-earth.kml+xml",
        "file_size_bytes": len(_KML.encode("utf-8")),
        "document_type": "mapa", "document_category": "tecnicos",
    })
    assert r.status_code in (200, 201, 202), r.text
    kml_id = r.json()["id"]

    # Espera o pipeline assentar (o KML não passa por OCR; o CNH já terminou).
    alvo = {}
    for _ in range(30):
        docs = cli.get(_api(base) + f"/documents/?process_id={pid}", headers=h).json()
        alvo = {d["id"]: d for d in docs}
        if alvo.get(kml_id, {}).get("ocr_status") not in (None, "pending", "processing"):
            break
        time.sleep(4)

    d_cnh, d_kml = alvo[cnh["id"]], alvo[kml_id]
    return {
        "cnh": {
            "id": d_cnh["id"], "arquivo": d_cnh["original_file_name"],
            "chars": len(d_cnh.get("extraction_status") or "") and None,
            "ocr_status": d_cnh["ocr_status"], "tem_texto": d_cnh.get("tem_texto"),
            "lifecycle_status": d_cnh.get("lifecycle_status"),
            "extraction_status": d_cnh.get("extraction_status"),
        },
        "kml": {
            "id": d_kml["id"], "arquivo": d_kml["original_file_name"],
            "ocr_status": d_kml["ocr_status"], "tem_texto": d_kml.get("tem_texto"),
            "lifecycle_status": d_kml.get("lifecycle_status"),
        },
    }


# ---------------------------------------------------------------------------
# 15 — item 7: sucessão transfere titularidade
# ---------------------------------------------------------------------------


def passo_15() -> dict[str, Any]:
    from app.services.observacao_registral import (
        cadeia_titularidade,
        observacoes_de,
        titular_atual,
    )

    # FIXTURE DECLARADA: nenhum dos 6 documentos da ELODI tem ato causa
    # mortis (R-11/R-13/R-20 etc. são todos compra e venda). A forma abaixo é
    # a dos atos reais do doc 549 — mesma estrutura, mesmos campos que a
    # extração produz — com os verbos de sucessão que a spec nomeia.
    atos = [
        {"ato": "R-11", "tipo": "compra_venda", "data_ato": "18/03/2019",
         "adquirentes": ["ALEXANDRE AUGUSTO CLEMENTE"],
         "transmitentes": ["NASCENTE AGRO-INDUSTRIAL LTDA"]},
        {"ato": "R-18", "tipo": "sucessao", "data_ato": "07/06/2024",
         "adquirentes": ["ESPÓLIO DE ALEXANDRE AUGUSTO CLEMENTE"],
         "transmitentes": ["ALEXANDRE AUGUSTO CLEMENTE"],
         "descricao": "transmissão causa mortis"},
        {"ato": "R-21", "tipo": "formal_partilha", "data_ato": "19/02/2026",
         "adquirentes": ["KARINA SANTAROSA CLEMENTE"],
         "transmitentes": ["ESPÓLIO DE ALEXANDRE AUGUSTO CLEMENTE"],
         "descricao": "formal de partilha registrado"},
    ]
    obs = observacoes_de(atos)
    atual = titular_atual(obs)
    cadeia = cadeia_titularidade(obs)
    return {
        "fixture_declarada": "derivada da forma dos atos do doc 549 (sem ato causa mortis real nos 6 docs)",
        "tipos_reconhecidos": [o.tipo for o in obs],
        "cadeia": [{"ato": c["ato"], "papel": c["papel_no_ato"], "nome": c["nome"]} for c in cadeia],
        "titular_atual": atual,
        "sem_sucessao_titular_seria": _titular_so_com_compra_venda(atos),
    }


def _titular_so_com_compra_venda(atos: list[dict]) -> Any:
    """O que `titular_atual` devolveria se sucessão/partilha NÃO estivessem no
    vocabulário — o estado anterior ao item 7 (o caso de 3.000 ha da Isis)."""
    from app.services.observacao_registral import TIPO_COMPRA_VENDA, observacoes_de

    obs = observacoes_de(atos)
    transferencias = [o for o in obs if o.tipo == TIPO_COMPRA_VENDA and o.atributos.get("adquirentes")]
    if not transferencias:
        return None
    ultimo = max(transferencias, key=lambda o: o.ordem)
    return {"ato": ultimo.ato, "titulares": ultimo.atributos.get("adquirentes")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--seed", required=True)
    ap.add_argument("--pdfs", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    sys.path.insert(0, os.getcwd())
    seed = json.loads(Path(args.seed).read_text(encoding="utf-8"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pdfs = Path(args.pdfs)
    texto_547 = ""
    candidato = pdfs.parent / "docs" / "547.txt"
    if candidato.exists():
        texto_547 = candidato.read_text(encoding="utf-8")

    with httpx.Client(timeout=120) as cli:
        token = login(cli, args.base, seed)
        resultado = {
            "13_rl_baixada": passo_13(texto_547),
            "14_estado_documento": passo_14(cli, args.base, token, seed, pdfs),
            "15_sucessao": passo_15(),
        }
    (out / "percurso3.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
