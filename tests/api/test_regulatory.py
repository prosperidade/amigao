"""Testes dos endpoints regulatórios — Sprint A1 Tarefa D2."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.regulatory import (
    RegulatoryDiagnosis,
    RegulatoryIssue,
    RegulatoryIssueSeverity,
    RegulatoryIssueType,
)
from app.models.tenant import Tenant
from app.models.user import User


def _login(http: TestClient, email: str, password: str) -> dict[str, str]:
    response = http.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _seed_internal_user(db_session, *, email: str = "consultor@example.com") -> tuple[Tenant, User]:
    tenant = Tenant(name="Tenant Reg")
    db_session.add(tenant)
    db_session.flush()
    user = User(
        email=email,
        full_name="Consultor",
        hashed_password=get_password_hash("senha123"),
        tenant_id=tenant.id,
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    db_session.flush()
    return tenant, user


def _seed_client_property_process(db_session, *, tenant: Tenant) -> tuple[Client, Property, Process]:
    client = Client(
        tenant_id=tenant.id,
        full_name="Fazenda Reg",
        client_type=ClientType.pj,
        status=ClientStatus.active,
    )
    db_session.add(client)
    db_session.flush()

    prop = Property(
        tenant_id=tenant.id,
        client_id=client.id,
        name="Imóvel Reg",
        state="GO",
    )
    db_session.add(prop)
    db_session.flush()

    process = Process(
        tenant_id=tenant.id,
        client_id=client.id,
        property_id=prop.id,
        title="Processo Reg",
        process_type="car",
        status=ProcessStatus.diagnostico,
        demand_type=DemandType.car,
    )
    db_session.add(process)
    db_session.flush()
    return client, prop, process


# ---------------------------------------------------------------------------
# /processes/{id}/diagnoses
# ---------------------------------------------------------------------------

class TestListDiagnoses:
    def test_unauthorized_returns_401(self, client: TestClient):
        r = client.get("/api/v1/processes/1/diagnoses")
        assert r.status_code == 401

    def test_empty_list_when_no_diagnoses(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        _, _, process = _seed_client_property_process(db_session, tenant=tenant)
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.get(f"/api/v1/processes/{process.id}/diagnoses", headers=headers)
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_versions_ordered_desc(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        _, _, process = _seed_client_property_process(db_session, tenant=tenant)
        for v in (1, 2, 3):
            db_session.add(RegulatoryDiagnosis(
                tenant_id=tenant.id,
                process_id=process.id,
                content={"v": v},
                version=v,
            ))
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.get(f"/api/v1/processes/{process.id}/diagnoses", headers=headers)
        assert r.status_code == 200
        versions = [item["version"] for item in r.json()]
        assert versions == [3, 2, 1]

    def test_404_when_process_does_not_exist(self, client: TestClient, db_session):
        _seed_internal_user(db_session)
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.get("/api/v1/processes/99999/diagnoses", headers=headers)
        assert r.status_code == 404
        assert "não encontrado" in r.json()["detail"].lower()

    def test_tenant_isolation(self, client: TestClient, db_session):
        # tenant A com processo + diagnóstico
        tenant_a, _ = _seed_internal_user(db_session, email="userA@example.com")
        _, _, process_a = _seed_client_property_process(db_session, tenant=tenant_a)
        db_session.add(RegulatoryDiagnosis(
            tenant_id=tenant_a.id, process_id=process_a.id, content={}, version=1,
        ))
        # tenant B (diferente)
        tenant_b, _ = _seed_internal_user(db_session, email="userB@example.com")
        db_session.commit()

        # user de B tenta acessar processo de A — deve ser 404 (não enxerga outro tenant)
        headers = _login(client, "userB@example.com", "senha123")
        r = client.get(f"/api/v1/processes/{process_a.id}/diagnoses", headers=headers)
        assert r.status_code == 404


class TestGetDiagnosisVersion:
    def test_returns_specific_version(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        _, _, process = _seed_client_property_process(db_session, tenant=tenant)
        diag = RegulatoryDiagnosis(
            tenant_id=tenant.id,
            process_id=process.id,
            content={"hipoteses": ["A"]},
            version=2,
            validated_at=datetime.now(UTC),
        )
        db_session.add(diag)
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.get(f"/api/v1/processes/{process.id}/diagnoses/2", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["version"] == 2
        assert body["content"] == {"hipoteses": ["A"]}
        assert body["validated_at"] is not None

    def test_404_when_version_missing(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        _, _, process = _seed_client_property_process(db_session, tenant=tenant)
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.get(f"/api/v1/processes/{process.id}/diagnoses/77", headers=headers)
        assert r.status_code == 404
        assert "Versão 77" in r.json()["detail"]


# ---------------------------------------------------------------------------
# /properties/{id}/issues
# ---------------------------------------------------------------------------

class TestListPropertyIssues:
    def test_unauthorized_returns_401(self, client: TestClient):
        r = client.get("/api/v1/properties/1/issues")
        assert r.status_code == 401

    def test_empty_list(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        _, prop, _ = _seed_client_property_process(db_session, tenant=tenant)
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.get(f"/api/v1/properties/{prop.id}/issues", headers=headers)
        assert r.status_code == 200
        assert r.json() == []

    def test_404_when_property_does_not_exist(self, client: TestClient, db_session):
        _seed_internal_user(db_session)
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.get("/api/v1/properties/99999/issues", headers=headers)
        assert r.status_code == 404

    def test_default_status_is_open(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        _, prop, _ = _seed_client_property_process(db_session, tenant=tenant)
        # 1 open + 1 resolved
        db_session.add(RegulatoryIssue(
            tenant_id=tenant.id,
            property_id=prop.id,
            type=RegulatoryIssueType.area_divergente,
            severity=RegulatoryIssueSeverity.warning,
        ))
        db_session.add(RegulatoryIssue(
            tenant_id=tenant.id,
            property_id=prop.id,
            type=RegulatoryIssueType.outro,
            severity=RegulatoryIssueSeverity.info,
            resolved_at=datetime.now(UTC),
        ))
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.get(f"/api/v1/properties/{prop.id}/issues", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["resolved_at"] is None

    def test_status_resolved_only(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        _, prop, _ = _seed_client_property_process(db_session, tenant=tenant)
        db_session.add(RegulatoryIssue(
            tenant_id=tenant.id, property_id=prop.id,
            type=RegulatoryIssueType.outro, severity=RegulatoryIssueSeverity.info,
        ))
        db_session.add(RegulatoryIssue(
            tenant_id=tenant.id, property_id=prop.id,
            type=RegulatoryIssueType.sobreposicao_app,
            severity=RegulatoryIssueSeverity.critical,
            resolved_at=datetime.now(UTC),
        ))
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.get(f"/api/v1/properties/{prop.id}/issues?status=resolved", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["resolved_at"] is not None
        assert body[0]["type"] == "sobreposicao_app"

    def test_status_all_returns_both(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        _, prop, _ = _seed_client_property_process(db_session, tenant=tenant)
        db_session.add(RegulatoryIssue(
            tenant_id=tenant.id, property_id=prop.id,
            type=RegulatoryIssueType.outro, severity=RegulatoryIssueSeverity.info,
        ))
        db_session.add(RegulatoryIssue(
            tenant_id=tenant.id, property_id=prop.id,
            type=RegulatoryIssueType.poligono_fora_matricula,
            severity=RegulatoryIssueSeverity.critical,
            resolved_at=datetime.now(UTC),
        ))
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.get(f"/api/v1/properties/{prop.id}/issues?status=all", headers=headers)
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_invalid_status_value_rejected(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        _, prop, _ = _seed_client_property_process(db_session, tenant=tenant)
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.get(f"/api/v1/properties/{prop.id}/issues?status=blabla", headers=headers)
        assert r.status_code == 422

    def test_results_ordered_by_detected_at_desc(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        _, prop, _ = _seed_client_property_process(db_session, tenant=tenant)

        from datetime import timedelta
        now = datetime.now(UTC)
        # detected_at é server_default=now() — manipulamos manualmente para ter ordem determinística
        i_old = RegulatoryIssue(
            tenant_id=tenant.id, property_id=prop.id,
            type=RegulatoryIssueType.outro, severity=RegulatoryIssueSeverity.info,
            detected_at=now - timedelta(days=2),
        )
        i_new = RegulatoryIssue(
            tenant_id=tenant.id, property_id=prop.id,
            type=RegulatoryIssueType.area_divergente, severity=RegulatoryIssueSeverity.warning,
            detected_at=now,
        )
        db_session.add_all([i_old, i_new])
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.get(f"/api/v1/properties/{prop.id}/issues", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body[0]["type"] == "area_divergente"
        assert body[1]["type"] == "outro"
