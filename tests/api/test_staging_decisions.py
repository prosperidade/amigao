"""Frente G (REC-001 + CONF-001, ADR-067) — endpoints da Conferência por
decisões: GET agrupa, POST decide uma decisão de cada vez (spec §11: aceite em
bloco de várias decisões não está implementado)."""

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
from app.models.process import Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User


def _login(client: TestClient, email: str, password: str = "x12345") -> dict[str, str]:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup(db_session, email="g@example.com"):
    tenant = Tenant(name="Frente G Tenant")
    db_session.add(tenant)
    db_session.flush()
    user = User(email=email, full_name="Consultor", hashed_password=get_password_hash("x12345"),
                tenant_id=tenant.id, is_active=True, is_superuser=True)
    cli = Client(tenant_id=tenant.id, full_name="ELODI AGROPECUARIA", email=f"c.{email}",
                 client_type=ClientType.pj, status=ClientStatus.active)
    db_session.add_all([user, cli])
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda")
    db_session.add(prop)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Caso", process_type="car", status=ProcessStatus.triagem)
    db_session.add(proc)
    db_session.flush()
    rows = [
        ExtractedFieldStaging(
            tenant_id=tenant.id, process_id=proc.id, source_doc_type="car",
            field_name="matricula_listada", field_value={"value": {"numero": "3181"}},
            status=ExtractedFieldStatus.pendente, target_entity="matricula",
            matricula_hint="3181",
        ),
        ExtractedFieldStaging(
            tenant_id=tenant.id, process_id=proc.id, source_doc_type="matricula",
            field_name="numero_matricula", field_value={"value": "3.181"},
            status=ExtractedFieldStatus.pendente, target_entity="matricula",
            target_field="numero_matricula", matricula_hint="3181",
        ),
    ]
    db_session.add_all(rows)
    db_session.flush()
    return tenant, proc


def test_get_agrupa_car_e_certidao_numa_decisao_so(client: TestClient, db_session):
    _tenant, proc = _setup(db_session)
    db_session.commit()
    h = _login(client, "g@example.com")

    r = client.get(f"/api/v1/processes/{proc.id}/staging-decisions", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_staging"] == 2
    assert len(body["decisoes"]) == 1
    decisao = body["decisoes"][0]
    assert decisao["chave"] == {"entidade": "matricula", "identificador": "3181", "aspecto": "composicao"}
    assert len(decisao["evidencias"]) == 2
    assert decisao["estado"] == "pendente"


def test_post_decidir_aceita_as_evidencias_da_decisao(client: TestClient, db_session):
    _tenant, proc = _setup(db_session)
    db_session.commit()
    h = _login(client, "g@example.com")

    r = client.post(
        f"/api/v1/processes/{proc.id}/staging-decisions/decidir", headers=h,
        json={"entidade": "matricula", "identificador": "3181", "aspecto": "composicao", "acao": "aceitar"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["estado"] == "decidida"

    rows = (
        db_session.query(ExtractedFieldStaging)
        .filter(ExtractedFieldStaging.process_id == proc.id)
        .all()
    )
    assert all(row.status == ExtractedFieldStatus.aceito for row in rows)


def test_processo_de_outro_tenant_da_404_nunca_403(client: TestClient, db_session):
    _tenant, proc = _setup(db_session)
    db_session.commit()
    # segundo tenant, sem vínculo com o processo acima
    tenant2 = Tenant(name="Outro Tenant")
    db_session.add(tenant2)
    db_session.flush()
    user2 = User(email="outro@example.com", full_name="Outro", hashed_password=get_password_hash("x12345"),
                 tenant_id=tenant2.id, is_active=True, is_superuser=True)
    db_session.add(user2)
    db_session.commit()
    h2 = _login(client, "outro@example.com")

    r = client.get(f"/api/v1/processes/{proc.id}/staging-decisions", headers=h2)
    assert r.status_code == 404

    r = client.post(
        f"/api/v1/processes/{proc.id}/staging-decisions/decidir", headers=h2,
        json={"entidade": "matricula", "identificador": "3181", "aspecto": "composicao", "acao": "aceitar"},
    )
    assert r.status_code == 404


def test_decisao_inexistente_da_404(client: TestClient, db_session):
    _tenant, proc = _setup(db_session)
    db_session.commit()
    h = _login(client, "g@example.com")

    r = client.post(
        f"/api/v1/processes/{proc.id}/staging-decisions/decidir", headers=h,
        json={"entidade": "matricula", "identificador": "9999", "aspecto": "composicao", "acao": "aceitar"},
    )
    assert r.status_code == 404
