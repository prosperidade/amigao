"""Popula um caso real via API: cliente + draft de intake + uploads de docs.

Uso:
    python scripts/populate_case.py romilton
    python scripts/populate_case.py romilton --no-commit       # parar antes do commit (deixa rascunho)
    python scripts/populate_case.py romilton --skip-enrich     # nao roda agent_extrator

Cenarios disponiveis: romilton (mais completo de Goias).

Requer:
- API rodando em http://localhost:8000
- MinIO acessivel em http://localhost:9000
- Credenciais admin@amigao.com / Seed@2026 (seed dev)
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import httpx

API = "http://localhost:8000"
LOGIN = "admin@amigao.com"
PASSWORD = "Seed@2026"

# ---------------------------------------------------------------------------
# Cenarios — caminhos relativos a raiz do projeto, sob legislacao/clientes...
# ---------------------------------------------------------------------------
CASES: dict[str, dict] = {
    "romilton": {
        "client": {
            "full_name": "Romilton da Silva (PA Mãe Maria)",
            "cpf_cnpj": None,
            "client_type": "pf",
            "status": "lead",
        },
        "form_data": {
            # IntakeCreateCaseRequest (app/schemas/intake.py)
            "demand_type": "misto",  # mistura car + autodenuncia + fiscalizacao
            "urgency": "media",
            "new_property": {
                "name": "Lotes 11 e 32 — PA Mãe Maria",
                "municipality": "Goiás",
                "state": "GO",
            },
            "intake_notes": "Caso real importado via API para teste end-to-end do fluxo Amigão.",
        },
        "base": "legislacao/clientes e documentação/005_ROMILTON_GO",
        "documents": [
            ("00_DOCUMENTOS_PESSOAIS_E_PROCURACAO/CPF_ROMILTON.pdf", "cpf", "documentos_pessoais"),
            ("01_DOCUMENTAÇÃO_FUNDIÁRIA/COMPROVANTE_ENDERECO_ROMILTON.pdf", "comprovante_endereco", "documentacao_fundiaria"),
            ("01_DOCUMENTAÇÃO_FUNDIÁRIA/ESCRITURA_PUBLICA_COMPRA_VENDA_ROMILTON.pdf", "escritura", "documentacao_fundiaria"),
            ("01_DOCUMENTAÇÃO_FUNDIÁRIA/GEO LOTE 11/Lote_11_PA_Mae_Maria_Planta.pdf", "planta_geo", "documentacao_fundiaria"),
            ("02_CADASTRO_REGULARIZACAO_AMBIENTAL/CAR Romilton.pdf", "car", "regularizacao_ambiental"),
            ("06_FISCALIZAÇÃO_E_INFRACOES/ANALISE_SOCIOAMBIENTAL_AGROTOOLS_2025.pdf", "analise_socioambiental", "fiscalizacao"),
            ("06_FISCALIZAÇÃO_E_INFRACOES/FORMULARIO_AUTODENUNCIA_2025.pdf", "autodenuncia", "fiscalizacao"),
            ("06_FISCALIZAÇÃO_E_INFRACOES/LAUDO_DESMATAMENTO_MAPBIOMAS_2025.pdf", "laudo_desmatamento", "fiscalizacao"),
        ],
    },
}


def login(client: httpx.Client) -> str:
    r = client.post(
        f"{API}/api/v1/auth/login",
        headers={"X-Auth-Profile": "internal"},
        data={"username": LOGIN, "password": PASSWORD},
    )
    r.raise_for_status()
    token = r.json()["access_token"]
    print(f"OK login — token len={len(token)}", flush=True)
    return token


def find_or_create_client(client: httpx.Client, full_name: str, payload: dict) -> int:
    # busca por nome (filtro simples — a lista e curta em dev)
    r = client.get(f"{API}/api/v1/clients/", params={"q": full_name.split()[0]})
    r.raise_for_status()
    body = r.json()
    items = body if isinstance(body, list) else body.get("items", [])
    for c in items:
        if c.get("full_name", "").startswith(full_name.split(" ")[0]):
            print(f"OK cliente ja existia id={c['id']} ({c['full_name']})", flush=True)
            return c["id"]

    r = client.post(f"{API}/api/v1/clients/", json=payload)
    r.raise_for_status()
    cid = r.json()["id"]
    print(f"OK cliente criado id={cid}", flush=True)
    return cid


def create_draft(client: httpx.Client, *, entry_type: str, form_data: dict) -> int:
    r = client.post(
        f"{API}/api/v1/intake/drafts",
        json={"entry_type": entry_type, "form_data": form_data},
    )
    r.raise_for_status()
    did = r.json()["id"]
    print(f"OK draft criado id={did} entry_type={entry_type}", flush=True)
    return did


def upload_doc(
    client: httpx.Client,
    draft_id: int,
    file_path: Path,
    doc_type: str,
    category: str,
) -> int:
    if not file_path.is_file():
        print(f"!! arquivo nao encontrado, pulando: {file_path}", flush=True)
        return 0

    size = file_path.stat().st_size
    filename = file_path.name
    content_type = "application/pdf"  # todos sao PDF nesta lista

    # 1) presigned URL
    r = client.post(
        f"{API}/api/v1/intake/drafts/{draft_id}/upload-url",
        json={
            "filename": filename,
            "content_type": content_type,
            "document_type": doc_type,
            "document_category": category,
        },
    )
    r.raise_for_status()
    presigned = r.json()
    upload_url = presigned["upload_url"]
    storage_key = presigned["storage_key"]

    # 2) PUT no MinIO. A URL pre-assinada vem com host minio:9000 (interno do Docker);
    # do host devmos reescrever pra localhost:9000.
    public_url = upload_url.replace("http://minio:9000", "http://localhost:9000")
    with file_path.open("rb") as fh:
        body = fh.read()
    put = httpx.put(public_url, content=body, headers={"Content-Type": content_type}, timeout=120)
    put.raise_for_status()

    # 3) confirma upload
    r = client.post(
        f"{API}/api/v1/intake/drafts/{draft_id}/documents",
        json={
            "storage_key": storage_key,
            "filename": filename,
            "content_type": content_type,
            "file_size_bytes": size,
            "document_type": doc_type,
            "document_category": category,
        },
    )
    r.raise_for_status()
    doc_id = r.json().get("id") or r.json().get("document_id") or 0
    kb = size / 1024
    print(f"  + {filename}  ({kb:.1f} KB)  doc_id={doc_id}", flush=True)
    return doc_id


def run_enrich(client: httpx.Client, draft_id: int, doc_ids: list[int]) -> None:
    """Dispara agent_extrator nos docs do draft (CAM1-005)."""
    if not doc_ids:
        return
    r = client.post(
        f"{API}/api/v1/intake/drafts/{draft_id}/import",
        json={"doc_ids": doc_ids},
    )
    r.raise_for_status()
    print(f"OK enrich disparado em {len(doc_ids)} docs (assincrono)", flush=True)


def commit_draft(client: httpx.Client, draft_id: int) -> dict:
    r = client.post(f"{API}/api/v1/intake/drafts/{draft_id}/commit")
    if r.status_code >= 400:
        print(f"!! commit falhou {r.status_code}: {r.text[:500]}", flush=True)
        r.raise_for_status()
    out = r.json()
    print(f"OK commit done — process_id={out.get('process_id') or out.get('id')}", flush=True)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=list(CASES.keys()))
    parser.add_argument("--no-commit", action="store_true")
    parser.add_argument("--skip-enrich", action="store_true")
    args = parser.parse_args()

    cfg = CASES[args.case]
    project_root = Path(__file__).resolve().parent.parent
    base_dir = project_root / cfg["base"]
    if not base_dir.is_dir():
        print(f"ERR pasta base nao existe: {base_dir}", file=sys.stderr)
        return 1

    with httpx.Client(timeout=60.0) as raw:
        token = login(raw)

    client = httpx.Client(
        timeout=120.0,
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        # 1) Cliente
        client_id = find_or_create_client(
            client, cfg["client"]["full_name"], cfg["client"]
        )

        # 2) Draft
        form_data = dict(cfg["form_data"])
        form_data["client_id"] = client_id
        draft_id = create_draft(
            client, entry_type="cliente_existente_novo_imovel", form_data=form_data
        )

        # 3) Uploads
        print(f"\n==> Subindo {len(cfg['documents'])} documentos...", flush=True)
        doc_ids: list[int] = []
        for rel, dtype, cat in cfg["documents"]:
            file_path = base_dir / rel
            did = upload_doc(client, draft_id, file_path, dtype, cat)
            if did:
                doc_ids.append(did)

        print(f"OK {len(doc_ids)} documentos confirmados", flush=True)

        # 4) Enrich (agent_extrator)
        if not args.skip_enrich and doc_ids:
            print("\n==> Disparando agent_extrator...", flush=True)
            run_enrich(client, draft_id, doc_ids)
            print("    (extracao roda assincrona — verificar status do draft em alguns min)", flush=True)

        # 5) Commit
        if args.no_commit:
            print(f"\n==> --no-commit: parando antes do commit. Draft id={draft_id} pronto pra UI continuar.", flush=True)
            print(f"    Abra: http://localhost:5173/intake (Retomar rascunho)", flush=True)
        else:
            print(f"\n==> Commit do draft {draft_id}...", flush=True)
            time.sleep(3)  # da chance pro enrich progredir
            result = commit_draft(client, draft_id)
            pid = result.get("process_id") or result.get("id")
            if pid:
                print(f"\n==> Processo criado: id={pid}")
                print(f"    UI: http://localhost:5173/processes/{pid}")

        return 0
    finally:
        client.close()


if __name__ == "__main__":
    # Permite rodar localmente sem o container; dependencias minimas: httpx
    sys.exit(main())
