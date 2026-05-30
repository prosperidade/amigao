from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.process import DemandType, Process, ProcessStatus
from app.models.tenant import Tenant
from app.models.user import User


def _login(http: TestClient, email: str, password: str) -> dict[str, str]:
    response = http.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_apply_workflow_returns_422_when_template_missing(client: TestClient, db_session):
    tenant = Tenant(name="Tenant Workflow")
    db_session.add(tenant)
    db_session.flush()
    user = User(
        email="workflow@example.com",
        full_name="Workflow User",
        hashed_password=get_password_hash("senha123"),
        tenant_id=tenant.id,
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    db_session.flush()
    client_record = Client(
        tenant_id=tenant.id,
        full_name="Cliente Workflow",
        client_type=ClientType.pj,
        status=ClientStatus.active,
    )
    db_session.add(client_record)
    db_session.flush()
    process = Process(
        tenant_id=tenant.id,
        client_id=client_record.id,
        title="Processo sem template",
        process_type="sobreposicao",
        status=ProcessStatus.triagem,
        demand_type=DemandType.sobreposicao,
    )
    db_session.add(process)
    db_session.commit()

    headers = _login(client, "workflow@example.com", "senha123")
    response = client.post(
        f"/api/v1/processes/{process.id}/apply-workflow",
        headers=headers,
    )

    assert response.status_code == 422
    assert "sobreposicao" in response.json()["detail"]
    assert "WorkflowTemplate" in response.json()["detail"]
