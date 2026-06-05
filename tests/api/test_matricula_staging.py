"""Ficha 01 / FASE 1 — Matrícula + staging de campos extraídos.

Cobre: model + ``Property.area_total_matriculas()`` (soma derivada), repositórios
(escopo por tenant), e os endpoints de leitura/criação. Inclui o caso real da
Ficha (matrículas 4.698 e 6.776 → soma 1.010,5583 ha).
"""

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.extracted_field_staging import (
    ExtractedFieldStaging,
    ExtractedFieldStatus,
)
from app.models.matricula import Matricula
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories import (
    ExtractedFieldStagingRepository,
    MatriculaRepository,
)

# Caso real da Ficha 01 (seções 5.4-5.7).
_M1 = ("4.698", 660.6561)
_M2 = ("6.776", 349.9022)
_SOMA = 1010.5583


def _setup_tenant(db_session, *, email: str, password: str = "interno123", name: str = "Tenant Ficha"):
    """Cria tenant + usuário interno + cliente + imóvel. Retorna (tenant, property)."""
    tenant = Tenant(name=name)
    db_session.add(tenant)
    db_session.flush()

    user = User(
        email=email,
        full_name="Consultor Interno",
        hashed_password=get_password_hash(password),
        tenant_id=tenant.id,
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)

    cli = Client(
        tenant_id=tenant.id,
        full_name="Fazenda Boa Vista LTDA",
        email=f"cli.{email}",
        client_type=ClientType.pf,
        status=ClientStatus.active,
    )
    db_session.add(cli)
    db_session.flush()

    prop = Property(
        tenant_id=tenant.id,
        client_id=cli.id,
        name="Fazenda Boa Vista",
        car_code="GO-5221080-ABCDE",
    )
    db_session.add(prop)
    db_session.flush()
    return tenant, prop


def _login(client: TestClient, email: str, password: str = "interno123") -> dict[str, str]:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Model + soma derivada
# ---------------------------------------------------------------------------

def test_area_total_matriculas_soma_caso_real(db_session):
    _, prop = _setup_tenant(db_session, email="soma@example.com")
    for numero, area in (_M1, _M2):
        db_session.add(
            Matricula(
                tenant_id=prop.tenant_id, property_id=prop.id,
                numero_matricula=numero, area_ha=area,
            )
        )
    db_session.flush()
    db_session.refresh(prop)

    assert len(prop.matriculas) == 2
    assert prop.area_total_matriculas() == _SOMA
    # O campo legado de área NÃO é tocado nesta fase.
    assert prop.total_area_ha is None


def test_area_total_matriculas_sem_matriculas_e_zero(db_session):
    _, prop = _setup_tenant(db_session, email="vazio@example.com")
    assert prop.area_total_matriculas() == 0.0


def test_area_total_matriculas_ignora_area_nula(db_session):
    _, prop = _setup_tenant(db_session, email="nula@example.com")
    db_session.add(Matricula(tenant_id=prop.tenant_id, property_id=prop.id, numero_matricula="1", area_ha=10.5))
    db_session.add(Matricula(tenant_id=prop.tenant_id, property_id=prop.id, numero_matricula="2", area_ha=None))
    db_session.flush()
    db_session.refresh(prop)
    assert prop.area_total_matriculas() == 10.5


# ---------------------------------------------------------------------------
# Repositórios (escopo por tenant)
# ---------------------------------------------------------------------------

def test_matricula_repo_scoped_por_tenant(db_session):
    _, prop_a = _setup_tenant(db_session, email="ta@example.com", name="Tenant A")
    _, prop_b = _setup_tenant(db_session, email="tb@example.com", name="Tenant B")
    db_session.add(Matricula(tenant_id=prop_a.tenant_id, property_id=prop_a.id, numero_matricula="A1", area_ha=1.0))
    db_session.add(Matricula(tenant_id=prop_b.tenant_id, property_id=prop_b.id, numero_matricula="B1", area_ha=2.0))
    db_session.flush()

    repo_a = MatriculaRepository(db_session, prop_a.tenant_id)
    a_list = repo_a.list_by_property(prop_a.id)
    assert [m.numero_matricula for m in a_list] == ["A1"]
    # Tenant A não enxerga a matrícula do imóvel do tenant B.
    assert repo_a.list_by_property(prop_b.id) == []


def test_staging_repo_filtra_por_status(db_session):
    _, prop = _setup_tenant(db_session, email="stg@example.com")
    # process_id None é válido (FK nullable) — basta para exercitar o filtro.
    rows = [
        ExtractedFieldStaging(
            tenant_id=prop.tenant_id, field_name="numero_matricula",
            field_value={"valor": "4.698"}, status=ExtractedFieldStatus.pendente,
            created_by_agent="extrator",
        ),
        ExtractedFieldStaging(
            tenant_id=prop.tenant_id, field_name="area_ha",
            field_value={"valor": 660.6561, "unidade": "ha"},
            status=ExtractedFieldStatus.divergente_fundo, created_by_agent="auditor",
        ),
    ]
    db_session.add_all(rows)
    db_session.flush()

    repo = ExtractedFieldStagingRepository(db_session, prop.tenant_id)
    # process_id None nas linhas → busca por process_id específico não casa; testa
    # diretamente o filtro de status numa busca sem process (via _base_query).
    all_rows = repo.list(filters=[ExtractedFieldStaging.tenant_id == prop.tenant_id])
    assert len(all_rows) == 2
    pend = [r for r in all_rows if r.status == ExtractedFieldStatus.pendente]
    assert len(pend) == 1


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

def test_matriculas_endpoint_requires_auth(client: TestClient):
    assert client.get("/api/v1/properties/1/matriculas").status_code == 401


def test_post_and_list_matriculas_via_api(client: TestClient, db_session):
    _, prop = _setup_tenant(db_session, email="api@example.com")
    db_session.commit()
    headers = _login(client, "api@example.com")

    # lista vazia
    r = client.get(f"/api/v1/properties/{prop.id}/matriculas", headers=headers)
    assert r.status_code == 200
    assert r.json() == []

    # cria as 2 matrículas reais
    for numero, area in (_M1, _M2):
        rc = client.post(
            f"/api/v1/properties/{prop.id}/matriculas",
            headers=headers,
            json={"numero_matricula": numero, "area_ha": area},
        )
        assert rc.status_code == 201, rc.text
        body = rc.json()
        assert body["property_id"] == prop.id
        assert body["tenant_id"] == prop.tenant_id

    r = client.get(f"/api/v1/properties/{prop.id}/matriculas", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert round(sum(m["area_ha"] for m in data), 4) == _SOMA


def test_get_matriculas_404_para_imovel_inexistente(client: TestClient, db_session):
    _setup_tenant(db_session, email="i404@example.com")
    db_session.commit()
    headers = _login(client, "i404@example.com")
    assert client.get("/api/v1/properties/999999/matriculas", headers=headers).status_code == 404


def test_staging_fields_endpoint(client: TestClient, db_session):
    from app.models.process import Process

    _, prop = _setup_tenant(db_session, email="stgapi@example.com")
    proc = Process(
        tenant_id=prop.tenant_id, client_id=prop.client_id,
        title="Caso staging", process_type="prad",
    )
    db_session.add(proc)
    db_session.flush()
    db_session.add(
        ExtractedFieldStaging(
            tenant_id=prop.tenant_id, process_id=proc.id, field_name="area_ha",
            field_value={"valor": 660.6561}, status=ExtractedFieldStatus.pendente,
            created_by_agent="extrator",
        )
    )
    db_session.commit()
    headers = _login(client, "stgapi@example.com")

    r = client.get(f"/api/v1/processes/{proc.id}/staging-fields", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["field_name"] == "area_ha"
    assert data[0]["status"] == "pendente"

    # filtro por status que não casa → vazio
    r = client.get(
        f"/api/v1/processes/{proc.id}/staging-fields?status=aceito", headers=headers
    )
    assert r.status_code == 200
    assert r.json() == []

    # status inválido → 422
    assert client.get(
        f"/api/v1/processes/{proc.id}/staging-fields?status=xpto", headers=headers
    ).status_code == 422


def test_staging_fields_404_para_processo_inexistente(client: TestClient, db_session):
    _setup_tenant(db_session, email="p404@example.com")
    db_session.commit()
    headers = _login(client, "p404@example.com")
    assert client.get(
        "/api/v1/processes/999999/staging-fields", headers=headers
    ).status_code == 404
