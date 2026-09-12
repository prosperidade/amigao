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


def _setup_observacao_tipada(db_session, email="j@example.com", tipo_obs="app"):
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
        target_field="averbacao_app", matricula_hint="3673", tipo_observacao=tipo_obs,
        atributos={"ato": "AV.03", "data_ato": "15/04/2008", "partes": ["BANCO DO BRASIL S/A"]},
    )
    db_session.add(row)
    db_session.flush()
    return tenant, proc, row


def test_reclassificar_linha_sem_agrupamento_e_pelo_campo_a_campo(client: TestClient, db_session):
    """A linha `app` não pertence a decisão nenhuma (a Frente G não agrupa APP):
    o caminho dela é o endpoint campo a campo, que é o que a tela antiga
    oferece. Depois de reclassificada para hipoteca, ela PASSA a integrar a
    decisão de gravames daquela matrícula."""
    tenant, proc, row = _setup_observacao_tipada(db_session)
    db_session.commit()
    h = _login(client, "j@example.com")

    antes = client.get(f"/api/v1/processes/{proc.id}/staging-decisions", headers=h).json()
    assert antes["decisoes"] == []
    assert [i["staging_id"] for i in antes["sem_agrupamento"]] == [row.id]

    r = client.post(
        f"/api/v1/processes/{proc.id}/staging-fields/{row.id}/decidir", headers=h,
        json={"acao": "reclassificar", "tipo_observacao": "Hipoteca"},
    )
    assert r.status_code == 200, r.text

    db_session.refresh(row)
    assert row.tipo_observacao == "hipoteca"
    assert row.atributos["tipo_sugerido"] == "app"
    assert row.target_entity is None and row.target_field is None
    assert row.field_value["tipo_decidido"] == "hipoteca"
    assert row.field_value["sem_destino"] is True

    depois = client.get(f"/api/v1/processes/{proc.id}/staging-decisions", headers=h).json()
    assert depois["sem_agrupamento"] == []
    assert [d["chave"]["aspecto"] for d in depois["decisoes"]] == ["gravames"]
    assert depois["decisoes"][0]["evidencias"][0]["tipo_observacao"] == "hipoteca"


def test_reclassificar_pela_decisao_agrupada_troca_o_tipo_da_evidencia(client: TestClient, db_session):
    """O caminho da TELA (cartão agrupado): a linha já integra a decisão de
    gravames e a consultora corrige o tipo de UM ato. A decisão continua a
    mesma; a evidência passa a dizer o tipo decidido."""
    tenant, proc, row = _setup_observacao_tipada(db_session, email="j3@example.com",
                                                 tipo_obs="hipoteca")
    db_session.commit()
    h = _login(client, "j3@example.com")

    antes = client.get(f"/api/v1/processes/{proc.id}/staging-decisions", headers=h).json()
    assert [d["chave"]["aspecto"] for d in antes["decisoes"]] == ["gravames"]

    r = client.post(
        f"/api/v1/processes/{proc.id}/staging-decisions/decidir", headers=h,
        json={"entidade": "matricula", "identificador": "3673", "aspecto": "gravames",
              "acao": "reclassificar", "staging_id": row.id,
              "tipo_observacao": "Alienação fiduciária"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["chave"]["aspecto"] == "gravames"
    assert body["evidencias"][0]["tipo_observacao"] == "alienacao_fiduciaria"

    db_session.refresh(row)
    assert row.atributos["tipo_sugerido"] == "hipoteca"


def test_reclassificar_que_tira_a_linha_da_decisao_nao_e_erro(client: TestClient, db_session):
    """Reclassificar para um tipo que a Frente G não agrupa (arrendamento)
    esvazia a decisão. A escrita FOI feita — responder erro seria mentira; o
    corpo vem `null` e a linha reaparece em `sem_agrupamento`."""
    tenant, proc, row = _setup_observacao_tipada(db_session, email="j4@example.com",
                                                 tipo_obs="hipoteca")
    db_session.commit()
    h = _login(client, "j4@example.com")

    r = client.post(
        f"/api/v1/processes/{proc.id}/staging-decisions/decidir", headers=h,
        json={"entidade": "matricula", "identificador": "3673", "aspecto": "gravames",
              "acao": "reclassificar", "staging_id": row.id,
              "tipo_observacao": "arrendamento"},
    )
    assert r.status_code == 200, r.text
    assert r.json() is None

    depois = client.get(f"/api/v1/processes/{proc.id}/staging-decisions", headers=h).json()
    assert depois["decisoes"] == []
    assert [i["staging_id"] for i in depois["sem_agrupamento"]] == [row.id]
    db_session.refresh(row)
    assert row.tipo_observacao == "arrendamento"


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
