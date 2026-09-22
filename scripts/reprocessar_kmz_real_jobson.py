"""Reprocessamento do KMZ REAL de Jobson (doc 560, caso #25) em dev — ADR-072.

Diferente de `gate_incremento3_geometria.py` (polígono sintético, calibrado
para medir o valor arredondado do Plano): este script lê os BYTES REAIS do
arquivo entregue pelo André em `amigao_geo_producao/MEDIDA_POLIGONO.kmz`
(fora de qualquer repositório git), grava no MinIO de dev e roda o percurso
autenticado completo. O número relatado é o que a geometria real mede — não
uma confirmação do valor documentado.

Alvo confirmado antes de qualquer escrita (127.0.0.1:15432/amigao_db).
"""
from __future__ import annotations

# Environment isolation must precede imports that instantiate settings/engines.
# ruff: noqa: E402
import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT.parent / ".env")
os.environ.update(POSTGRES_SERVER="127.0.0.1", POSTGRES_PORT=os.environ["HOST_DB_PORT"], DATABASE_URL="",
                  ENVIRONMENT="development", LOG_LEVEL="WARNING", ALERT_WEBHOOK_URL="",
                  REDIS_URL="redis://127.0.0.1:6379/15", MINIO_SERVER="localhost:9000")
os.environ.pop("MIGRATE_DATABASE_URL", None)

from sqlalchemy.engine import make_url

from app.core.config import settings

target = make_url(settings.SQLALCHEMY_DATABASE_URI)
assert (target.host, target.port, target.database, target.username) == ("127.0.0.1", 15432, "amigao_db", "postgres"), (
    f"Alvo inesperado: {target.host}:{target.port}/{target.database}@{target.username} — PARAR")
print(f"alvo confirmado: {target.host}:{target.port}/{target.database}@{target.username}")

KMZ_PATH = Path(r"C:\Users\Administrador\Desktop\amigao_geo_producao\MEDIDA_POLIGONO.kmz")
KMZ_BYTES = KMZ_PATH.read_bytes()
KMZ_SHA256 = hashlib.sha256(KMZ_BYTES).hexdigest()
# Produção (doc 560) não tem checksum_sha256 gravado — não há hash contra o
# qual conferir identidade bit a bit. O único fato comparável é o tamanho.
PRODUCAO_FILE_SIZE_BYTES = 832
assert len(KMZ_BYTES) == PRODUCAO_FILE_SIZE_BYTES, (
    f"Tamanho não bate com o registrado em produção: {len(KMZ_BYTES)} != {PRODUCAO_FILE_SIZE_BYTES}")
print(f"arquivo: {len(KMZ_BYTES)} bytes (bate com o tamanho registrado em produção), sha256={KMZ_SHA256}")

from fastapi.testclient import TestClient

from app.core.celery_app import celery_app
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.main import app
from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User
from app.services.storage import get_storage_service

celery_app.conf.update(task_always_eager=True, task_eager_propagates=True, task_store_eager_result=False,
                       broker_url="memory://", result_backend="cache+memory://")

SENHA = "GateInc3JobsonReal!2026"


def preparar():
    with SessionLocal() as db:
        from uuid import uuid4
        suffix = uuid4().hex[:10]
        tenant = Tenant(name=f"Incremento 3 geometria REAL Jobson {suffix}")
        db.add(tenant)
        db.flush()
        email = f"inc3-geo-real-{suffix}@example.com"
        user = User(tenant_id=tenant.id, email=email, full_name="Reprocessamento KMZ real — Jobson",
                   hashed_password=get_password_hash(SENHA), is_active=True)
        db.add(user)
        db.flush()
        client = Client(tenant_id=tenant.id, full_name="Jobson (KMZ real, doc 560)",
                        email=f"cliente-{suffix}@example.com", client_type=ClientType.pf,
                        status=ClientStatus.active)
        db.add(client)
        db.flush()
        prop = Property(tenant_id=tenant.id, client_id=client.id, name="Fazenda Jobson (KMZ real)", state="GO")
        db.add(prop)
        db.flush()
        case = Process(tenant_id=tenant.id, client_id=client.id, property_id=prop.id,
                      title="Reprocessamento #25 — KMZ real (doc 560)", process_type="car",
                      status=ProcessStatus.triagem, demand_type=DemandType.car)
        db.add(case)
        db.flush()

        storage = get_storage_service()
        upload = storage.upload_bytes(KMZ_BYTES, "MEDIDA_POLIGONO.kmz",
                                      "application/vnd.google-earth.kmz", tenant.id, case.id)
        doc = Document(tenant_id=tenant.id, process_id=case.id, original_file_name="MEDIDA_POLIGONO.kmz",
                       filename="MEDIDA_POLIGONO.kmz", content_type="application/vnd.google-earth.kmz",
                       extension="kmz", storage_key=upload["storage_key"], checksum_sha256=KMZ_SHA256,
                       file_size_bytes=len(KMZ_BYTES), document_type="kml_sigef", ocr_status=OcrStatus.not_required)
        db.add(doc)
        db.flush()

        # Área documental real de Jobson (Plano §4.5: "área calculada do KMZ" ×
        # "área documental" 2,6893 ha) — pelo pipeline real (fonte_documental +
        # persist_object), como o extrator faria.
        matricula = Document(tenant_id=tenant.id, process_id=case.id, original_file_name="matricula.pdf",
                            filename="matricula.pdf", content_type="application/pdf", extension="pdf",
                            storage_key=f"gate-inc3-real/{tenant.id}/matricula-{suffix}",
                            document_type="matricula", ocr_status=OcrStatus.done,
                            checksum_sha256="2" * 64, extracted_text="Consta da matrícula: Área total: 2,6893.")
        db.add(matricula)
        db.flush()
        from app.schemas.evidence import EvidenceObject
        from app.services.entrada_semantica import fonte_documental
        from app.services.evidence import persist_object
        fonte = fonte_documental(db, matricula)
        obs = EvidenceObject(id=f"obs:{matricula.id}:1:1:{suffix}", version=1, kind="observacao", origin="extrator",
                             premises=[{"id": fonte.object_id, "version": fonte.version}],
                             attributes={"predicate": "area_total", "literal": "Área total: 2,6893.", "unit": "ha",
                                        "document_id": matricula.id})
        persist_object(db, tenant.id, case.id, obs)
        db.commit()
        return {"tenant_id": tenant.id, "email": email, "case_id": case.id, "doc_id": doc.id,
                "storage_key": upload["storage_key"]}


def login(client: TestClient, email: str) -> str:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": SENHA},
                    headers={"X-Auth-Profile": "internal"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def main():
    prep = preparar()
    print(json.dumps({"prep": prep}, indent=2))

    with TestClient(app) as client:
        token = login(client, prep["email"])
        headers = {"Authorization": f"Bearer {token}"}

        vazio = client.get(f"/api/v1/processes/{prep['case_id']}/geometria", headers=headers)
        assert vazio.status_code == 200, vazio.text
        assert vazio.json()["arquivos"][0]["estado"] == "nao_lido"
        print("1) painel antes de ler: arquivo listado, ainda não lido — OK")

        lido = client.post(f"/api/v1/processes/{prep['case_id']}/geometria/documentos/{prep['doc_id']}/ler",
                          headers=headers)
        assert lido.status_code == 200, lido.text
        painel = lido.json()
        arquivo = painel["arquivos"][0]
        assert arquivo["estado"] == "lido", painel
        feicao = arquivo["feicoes"][0]
        print(f"2) leitura REAL do KMZ (doc 560): válida={feicao['valida']}, tipo={feicao['tipo']}, "
              f"área={feicao['area_ha']} ha (geodésica, GRS80) — MEDIDO, não assumido")

        print(f"3) Property.geom projetada automaticamente: {painel['projecao']}")

        if painel["confronto"]["linhas"]:
            linha = painel["confronto"]["linhas"][0]
            print(f"4) confronto REAL: {linha['calculada_ha']} ha (calculada, doc 560) × "
                  f"{linha['referencia_ha']} ha (documental, matrícula) = Δ{linha['delta_ha']} ha, "
                  f"{linha['percentual']}% sobre a área documental "
                  f"({linha['percentual_sobre_maior']}% sobre o maior valor), "
                  f"tolerância {linha['tolerancia_pct']}% ({linha['tolerancia_origem']}), "
                  f"resultado={linha['resultado']}, grau={linha['grau']}")
        else:
            print("4) confronto: sem linha (ver painel completo abaixo)")
            print(json.dumps(painel["confronto"], indent=2, ensure_ascii=False))

        recarga = client.get(f"/api/v1/processes/{prep['case_id']}/geometria", headers=headers)
        assert recarga.status_code == 200
        assert recarga.json()["arquivos"][0]["feicoes"][0]["area_ha"] == feicao["area_ha"]
        assert recarga.json()["confronto"]["execucao"] == painel["confronto"]["execucao"]
        print("5) recarga (novo GET): mesma leitura, mesmo confronto persistido — OK")

    with TestClient(app) as client2:
        token2 = login(client2, prep["email"])
        assert token2 != token
        nova_sessao = client2.get(f"/api/v1/processes/{prep['case_id']}/geometria",
                                  headers={"Authorization": f"Bearer {token2}"})
        assert nova_sessao.status_code == 200
        assert nova_sessao.json()["arquivos"][0]["feicoes"][0]["area_ha"] == feicao["area_ha"]
        print("6) nova sessão (novo login, novo token): mesmo resultado — OK")

    print("\nREPROCESSAMENTO KMZ REAL — DOC 560 (JOBSON #25): 6/6 passos OK.")
    print(f"tenant: {prep['tenant_id']} (nome prefixado 'Incremento 3 geometria REAL Jobson ' — "
          "localizável para limpeza posterior).")
    print(json.dumps({"painel_final": painel}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
