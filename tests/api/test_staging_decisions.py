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


# ---------------------------------------------------------------------------
# Frente J (item 5, CONF-002) — tipo de observação EDITÁVEL na decisão
# ---------------------------------------------------------------------------


def _setup_observacao_tipada(db_session, email="j@example.com"):
    """Uma observação de matrícula que o modelo rotulou `app` mas é hipoteca
    (o padrão medido no ADR-065: valor certo, tipo errado)."""
    tenant = Tenant(name="Frente J Tenant")
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
    row = ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=proc.id, source_doc_type="matricula",
        field_name="averbacao_app", field_value={"value": "AV.03 · APP · 15/04/2008"},
        status=ExtractedFieldStatus.pendente, target_entity="matricula",
        target_field="averbacao_app", matricula_hint="3673", tipo_observacao="app",
        atributos={"ato": "AV.03", "data_ato": "15/04/2008", "partes": ["BANCO DO BRASIL S/A"]},
    )
    db_session.add(row)
    db_session.flush()
    return tenant, proc, row


def test_reclassificar_pela_decisao_preserva_o_sugerido_e_muda_a_chave(client: TestClient, db_session):
    tenant, proc, row = _setup_observacao_tipada(db_session)
    db_session.commit()
    h = _login(client, "j@example.com")

    # Antes: `app` tem destino (averbacao_app) mas nenhuma chave natural da
    # Frente G — aparece em sem_agrupamento, visível.
    antes = client.get(f"/api/v1/processes/{proc.id}/staging-decisions", headers=h).json()
    assert antes["decisoes"] == []
    assert [i["staging_id"] for i in antes["sem_agrupamento"]] == [row.id]

    r = client.post(
        f"/api/v1/processes/{proc.id}/staging-decisions/decidir", headers=h,
        json={"entidade": "matricula", "identificador": "3673", "aspecto": "gravames",
              "acao": "reclassificar", "staging_id": row.id, "tipo_observacao": "Hipoteca"},
    )
    # A decisão-alvo (gravames) ainda não existia quando o pedido chegou —
    # ela NASCE da reclassificação. O endpoint devolve a decisão que passou a
    # conter a linha, não 404.
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["chave"]["aspecto"] == "gravames"
    assert body["evidencias"][0]["tipo_observacao"] == "hipoteca"

    db_session.refresh(row)
    assert row.tipo_observacao == "hipoteca"
    assert row.atributos["tipo_sugerido"] == "app"
    assert row.target_entity is None and row.target_field is None
    assert row.field_value["tipo_decidido"] == "hipoteca"
    assert row.field_value["sem_destino"] is True

    depois = client.get(f"/api/v1/processes/{proc.id}/staging-decisions", headers=h).json()
    assert depois["sem_agrupamento"] == []
    assert [d["chave"]["aspecto"] for d in depois["decisoes"]] == ["gravames"]


def test_reclassificar_com_tipo_desconhecido_e_422_e_nao_toca_a_linha(client: TestClient, db_session):
    tenant, proc, row = _setup_observacao_tipada(db_session)
    db_session.commit()
    h = _login(client, "j@example.com")

    r = client.post(
        f"/api/v1/processes/{proc.id}/staging-fields/{row.id}/decidir", headers=h,
        json={"acao": "reclassificar", "tipo_observacao": "xyz"},
    )
    assert r.status_code == 422, r.text
    assert "xyz" in r.json()["detail"]
    db_session.refresh(row)
    assert row.tipo_observacao == "app"
    assert "tipo_sugerido" not in (row.atributos or {})


def test_escolher_fonte_pela_decisao_exige_staging_id(client: TestClient, db_session):
    _tenant, proc = _setup(db_session, "j2@example.com")
    db_session.commit()
    h = _login(client, "j2@example.com")

    r = client.post(
        f"/api/v1/processes/{proc.id}/staging-decisions/decidir", headers=h,
        json={"entidade": "matricula", "identificador": "3181", "aspecto": "composicao",
              "acao": "escolher_fonte"},
    )
    assert r.status_code == 422
    assert "evidência" in r.json()["detail"].lower()
