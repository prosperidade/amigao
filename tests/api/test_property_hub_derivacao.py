"""Item 2 (Isis 16/06) — o Imóvel Hub DERIVA Matrícula e Área das matrículas.

Antes o Hub lia as colunas cruas de Property (registry_number/total_area_ha) que
a consolidação nunca grava (área é derivada; matrícula vive em Matricula). Logo,
mesmo após "Confirmar e gravar", o Hub mostrava "—". Agora deriva e mostra.
"""

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.matricula import Matricula
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User


def _login(client: TestClient, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": "x12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_hub_deriva_matricula_e_area_das_matriculas(client: TestClient, db_session):
    tenant = Tenant(name="HubDeriv")
    db_session.add(tenant)
    db_session.flush()
    user = User(email="hub@example.com", full_name="C", hashed_password=get_password_hash("x12345"),
                tenant_id=tenant.id, is_active=True, is_superuser=True)
    cli = Client(tenant_id=tenant.id, full_name="Cli", email="c.hub@example.com",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add_all([user, cli])
    db_session.flush()
    # Property com colunas cruas VAZIAS (como após consolidação real)
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda São Jorge",
                    registry_number=None, total_area_ha=None)
    db_session.add(prop)
    db_session.flush()
    db_session.add_all([
        Matricula(tenant_id=tenant.id, property_id=prop.id, numero_matricula="4698", area_ha=660.6561),
        Matricula(tenant_id=tenant.id, property_id=prop.id, numero_matricula="6776", area_ha=349.9022),
    ])
    db_session.commit()

    h = _login(client, "hub@example.com")
    r = client.get(f"/api/v1/properties/{prop.id}/summary", headers=h)
    assert r.status_code == 200, r.text
    header = r.json()["header"]
    # Matrícula e Área DERIVADAS — fim dos "—"
    assert header["registry_number"] == "4698; 6776"
    assert header["total_area_ha"] == 1010.5583


def test_hub_sem_matriculas_mantem_none(client: TestClient, db_session):
    tenant = Tenant(name="HubVazio")
    db_session.add(tenant)
    db_session.flush()
    user = User(email="hub2@example.com", full_name="C", hashed_password=get_password_hash("x12345"),
                tenant_id=tenant.id, is_active=True, is_superuser=True)
    cli = Client(tenant_id=tenant.id, full_name="Cli", email="c.hub2@example.com",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add_all([user, cli])
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Sem Matrícula")
    db_session.add(prop)
    db_session.commit()

    h = _login(client, "hub2@example.com")
    r = client.get(f"/api/v1/properties/{prop.id}/summary", headers=h)
    assert r.status_code == 200, r.text
    header = r.json()["header"]
    assert header["registry_number"] is None
    assert header["total_area_ha"] is None
