"""
E2E Test — Intake flow: classify → create-case → verify process & checklist.
"""
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.tenant import Tenant
from app.models.user import User


def _login(tc: TestClient, email: str, password: str) -> dict[str, str]:
    resp = tc.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_intake_classify_returns_demand_type(client: TestClient, db_session):
    """POST /intake/classify returns classification without creating records."""
    tenant = Tenant(name="Tenant Intake Classify")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        email="intake.classify@example.com",
        full_name="Consultor Intake",
        hashed_password=get_password_hash("Consultor1"),
        tenant_id=tenant.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    headers = _login(client, "intake.classify@example.com", "Consultor1")

    resp = client.post(
        "/api/v1/intake/classify",
        json={
            "description": "Preciso de licenciamento ambiental para uma fazenda de 500 hectares com desmatamento irregular",
            "source_channel": "website",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "demand_type" in data
    assert "demand_label" in data
    assert "initial_diagnosis" in data
    assert "required_documents" in data
    assert isinstance(data["required_documents"], list)


def test_intake_full_flow(client: TestClient, db_session):
    """Full E2E: classify → create-case → verify process persisted."""
    tenant = Tenant(name="Tenant Intake E2E")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        email="intake.e2e@example.com",
        full_name="Consultor E2E",
        hashed_password=get_password_hash("Consultor1"),
        tenant_id=tenant.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    headers = _login(client, "intake.e2e@example.com", "Consultor1")

    # 1. Classify
    classify_resp = client.post(
        "/api/v1/intake/classify",
        json={
            "description": "Preciso de licenciamento ambiental para uma fazenda de 500 hectares",
            "source_channel": "email",
        },
        headers=headers,
    )
    assert classify_resp.status_code == 200
    classify_data = classify_resp.json()
    demand_type = classify_data["demand_type"]

    # 2. Create case (new client + new property)
    create_resp = client.post(
        "/api/v1/intake/create-case",
        json={
            "new_client": {
                "full_name": "Fazendeiro E2E",
                "phone": "11999990000",
                "email": "fazendeiro.e2e@example.com",
                "cpf_cnpj": "12345678901",
                "client_type": "pf",
                "source_channel": "email",
            },
            "new_property": {
                "name": "Fazenda E2E",
                "municipality": "Ribeirão Preto",
                "state": "SP",
                "area_hectares": 500.0,
            },
            "description": "Preciso de licenciamento ambiental para uma fazenda de 500 hectares",
            "urgency": "media",
            "source_channel": "email",
            "demand_type": demand_type,
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    case_data = create_resp.json()
    assert case_data["client_id"] is not None
    assert case_data["process_id"] is not None
    assert case_data["checklist_generated"] is True
    assert case_data["demand_type"] is not None
    assert case_data["process_title"]

    process_id = case_data["process_id"]

    # 3. Verify process is persisted and retrievable
    process_resp = client.get(
        f"/api/v1/processes/{process_id}",
        headers=headers,
    )
    assert process_resp.status_code == 200
    process_data = process_resp.json()
    assert process_data["id"] == process_id
    assert process_data["status"] == "triagem"
    assert process_data["client_id"] == case_data["client_id"]


def test_intake_create_case_requires_client(client: TestClient, db_session):
    """create-case without client_id or new_client returns 422."""
    tenant = Tenant(name="Tenant Intake Validation")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        email="intake.val@example.com",
        full_name="Consultor Val",
        hashed_password=get_password_hash("Consultor1"),
        tenant_id=tenant.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    headers = _login(client, "intake.val@example.com", "Consultor1")

    resp = client.post(
        "/api/v1/intake/create-case",
        json={
            "description": "Demanda sem cliente associado",
        },
        headers=headers,
    )
    assert resp.status_code == 422
