"""Gate do Incremento 3 (geometria, ADR-072) — percurso autenticado em dev.

Sobe o app real contra o banco de DEV (127.0.0.1:15432/amigao_db, confirmado
antes de qualquer escrita), grava um KMZ real no MinIO de dev, faz login pela
rota real (/auth/login), lê a geometria, roda o confronto, recarrega (GET de
novo) e abre nova sessão (novo login) — tudo por HTTP real via TestClient,
nenhum mock de banco/storage/auth.

O polígono usado é uma CONSTRUÇÃO PRÓPRIA calibrada no PostGIS para medir
≈2,7250 ha — a área do KMZ real de Jobson (caso #25), documentada no Plano
§4.5. Os bytes de produção (documento 560, `MEDIDA_POLIGONO.kmz`, 832 bytes,
guardado desde 13/09 sem checksum) não foram trazidos para dev: o acesso a
produção neste projeto é SQL somente-leitura (`supabase-prod-ro`); não há
canal de storage de produção nesta máquina. Ver ADR-072 e o relatório do PR.
"""
from __future__ import annotations

# Environment isolation must precede imports that instantiate settings/engines.
# ruff: noqa: E402
import hashlib
import io
import json
import os
import zipfile
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT.parent / ".env")
os.environ.update(POSTGRES_SERVER="127.0.0.1", POSTGRES_PORT=os.environ["HOST_DB_PORT"], DATABASE_URL="",
                  ENVIRONMENT="development", LOG_LEVEL="WARNING", ALERT_WEBHOOK_URL="",
                  REDIS_URL="redis://127.0.0.1:6379/15",
                  # .env tem uma segunda linha `MINIO_SERVER=` vazia (pensada pro compose,
                  # onde o service name `minio` resolve); dotenv lê as duas e a última
                  # vence. Fora do compose, o host expõe o MinIO em localhost:9000
                  # (docker-compose.yml: "9000:9000").
                  MINIO_SERVER="localhost:9000")
os.environ.pop("MIGRATE_DATABASE_URL", None)

from sqlalchemy.engine import make_url

from app.core.config import settings

target = make_url(settings.SQLALCHEMY_DATABASE_URI)
assert (target.host, target.port, target.database, target.username) == ("127.0.0.1", 15432, "amigao_db", "postgres"), (
    f"Alvo inesperado: {target.host}:{target.port}/{target.database}@{target.username} — PARAR")
print(f"alvo confirmado: {target.host}:{target.port}/{target.database}@{target.username}")

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

# Calibrado no PostGIS (ST_Area geodésica, elipsoide GRS80) para medir 2,72502 ha
# — o valor documentado do KMZ real de Jobson (2,7250 ha, Plano §4.5).
KML = (b'<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2">\n'
       b'<Document><Placemark><name>Perimetro</name>'
       b'<Polygon><outerBoundaryIs><LinearRing><coordinates>'
       b'-49.45,-16.35,0 -49.4515447,-16.35,0 -49.4515447,-16.3514920,0 -49.45,-16.3514920,0 -49.45,-16.35,0'
       b'</coordinates></LinearRing></outerBoundaryIs></Polygon>'
       b'</Placemark></Document>\n</kml>')
_buf = io.BytesIO()
with zipfile.ZipFile(_buf, "w") as _zf:
    _zf.writestr("doc.kml", KML)
KMZ_BYTES = _buf.getvalue()
KMZ_SHA256 = hashlib.sha256(KMZ_BYTES).hexdigest()

SENHA = "GateInc3Geometria!2026"


def preparar():
    with SessionLocal() as db:
        from uuid import uuid4
        suffix = uuid4().hex[:10]
        tenant = Tenant(name=f"Incremento 3 geometria gate {suffix}")
        db.add(tenant)
        db.flush()
        email = f"inc3-geo-{suffix}@example.com"
        user = User(tenant_id=tenant.id, email=email, full_name="Gate Incremento 3",
                   hashed_password=get_password_hash(SENHA), is_active=True)
        db.add(user)
        db.flush()
        client = Client(tenant_id=tenant.id, full_name="Jobson (gate)", email=f"cliente-{suffix}@example.com",
                        client_type=ClientType.pf, status=ClientStatus.active)
        db.add(client)
        db.flush()
        prop = Property(tenant_id=tenant.id, client_id=client.id, name="Fazenda Jobson (gate)", state="GO")
        db.add(prop)
        db.flush()
        case = Process(tenant_id=tenant.id, client_id=client.id, property_id=prop.id,
                      title="Gate Incremento 3 — geometria", process_type="car",
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

        # Área documental (matrícula) para o confronto reproduzir o caso de Jobson.
        # Pelo pipeline REAL — mesma `fonte_documental`/`persist_object` que o
        # extrator usa — para exercitar as arestas e triggers reais do dev.
        matricula = Document(tenant_id=tenant.id, process_id=case.id, original_file_name="matricula.pdf",
                            filename="matricula.pdf", content_type="application/pdf", extension="pdf",
                            storage_key=f"gate-inc3/{tenant.id}/matricula-{suffix}",
                            document_type="matricula", ocr_status=OcrStatus.done,
                            checksum_sha256="1" * 64, extracted_text="Consta da matrícula: Área total: 2,6893.")
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

    resultados = {}
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
        assert feicao["valida"] is True
        area_calculada = float(feicao["area_ha"])
        assert abs(area_calculada - 2.7250) < 0.001, f"área calculada fora do esperado: {area_calculada}"
        print(f"2) leitura real do KMZ: {area_calculada:.4f} ha calculados (geodésico, GRS80) — OK")

        assert painel["projecao"]["property_geom_gravada"] is True
        print("3) Property.geom projetada automaticamente (feição poligonal única) — OK")

        linha = painel["confronto"]["linhas"][0]
        print(f"4) confronto: {linha['calculada_ha']} ha (calculada) × {linha['referencia_ha']} ha "
              f"(documental) = Δ{linha['delta_ha']} ha, {linha['percentual']}% sobre a área documental, "
              f"tolerância {linha['tolerancia_pct']}% ({linha['tolerancia_origem']}), "
              f"resultado={linha['resultado']}, grau={linha['grau']}")
        assert abs(float(linha["percentual"]) - 1.33) < 0.05
        assert linha["denominador_regra"] == "referencia_documental"
        assert linha["resultado"] == "divergente"
        resultados["primeira_leitura"] = painel

        # Recarga: novo GET, mesmo token — tem de bater com o que ficou persistido.
        recarga = client.get(f"/api/v1/processes/{prep['case_id']}/geometria", headers=headers)
        assert recarga.status_code == 200
        assert recarga.json()["arquivos"][0]["feicoes"][0]["area_ha"] == feicao["area_ha"]
        assert recarga.json()["confronto"]["execucao"] == painel["confronto"]["execucao"]
        print("5) recarga (novo GET): mesma leitura, mesmo confronto persistido — OK")

    # Nova sessão: novo TestClient (nova app/lifespan), novo login, novo token.
    with TestClient(app) as client2:
        token2 = login(client2, prep["email"])
        assert token2 != token
        nova_sessao = client2.get(f"/api/v1/processes/{prep['case_id']}/geometria",
                                  headers={"Authorization": f"Bearer {token2}"})
        assert nova_sessao.status_code == 200
        assert nova_sessao.json()["arquivos"][0]["feicoes"][0]["area_ha"] == feicao["area_ha"]
        assert nova_sessao.json()["confronto"]["linhas"][0]["percentual"] == linha["percentual"]
        print("6) nova sessão (novo login, novo token): mesmo resultado — OK")

    print("\nGATE INCREMENTO 3 — GEOMETRIA: 6/6 passos OK.")
    print(f"tenant de gate: {prep['tenant_id']} (nome prefixado 'Incremento 3 geometria gate ' — "
          "localizável para limpeza posterior).")


if __name__ == "__main__":
    main()
