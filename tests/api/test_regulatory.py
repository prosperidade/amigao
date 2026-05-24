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


# ---------------------------------------------------------------------------
# Onda B Fase 2 — POST /processes/{id}/diagnoses
# ---------------------------------------------------------------------------

def _valid_content() -> dict:
    """Conteúdo mínimo válido para `DiagnosticoPreliminarContent`.
    `content` não vazio + `sources` não vazio (validators do schema)."""
    return {
        "content": "Diagnóstico preliminar do processo.",
        "sources": [{"type": "legislation", "ref": "chunk_1"}],
        "hipoteses": ["CAR pendente"],
        "lacunas": [],
        "riscos": [],
        "checklist_documental": ["Matrícula"],
    }


class TestCreateDiagnosis:
    def test_unauthorized_returns_401(self, client: TestClient):
        r = client.post("/api/v1/processes/1/diagnoses", json={"content": _valid_content()})
        assert r.status_code == 401

    def test_404_quando_processo_nao_existe(self, client: TestClient, db_session):
        _seed_internal_user(db_session)
        db_session.commit()
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.post(
            "/api/v1/processes/9999/diagnoses",
            headers=headers,
            json={"content": _valid_content()},
        )
        assert r.status_code == 404

    def test_cria_primeira_versao_201(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        _, _, process = _seed_client_property_process(db_session, tenant=tenant)
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.post(
            f"/api/v1/processes/{process.id}/diagnoses",
            headers=headers,
            json={"content": _valid_content()},
        )
        assert r.status_code == 201
        body = r.json()
        assert body["version"] == 1
        assert body["process_id"] == process.id
        assert body["content"]["content"] == "Diagnóstico preliminar do processo."
        # Princípio 1 do manifesto: humano valida depois — created sem validação.
        assert body["validated_by_user_id"] is None
        assert body["validated_at"] is None

    def test_versao_eh_incrementada_em_posts_sucessivos(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        _, _, process = _seed_client_property_process(db_session, tenant=tenant)
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r1 = client.post(
            f"/api/v1/processes/{process.id}/diagnoses",
            headers=headers, json={"content": _valid_content()},
        )
        assert r1.status_code == 201
        assert r1.json()["version"] == 1

        r2 = client.post(
            f"/api/v1/processes/{process.id}/diagnoses",
            headers=headers, json={"content": _valid_content()},
        )
        assert r2.status_code == 201
        assert r2.json()["version"] == 2

        r3 = client.post(
            f"/api/v1/processes/{process.id}/diagnoses",
            headers=headers, json={"content": _valid_content()},
        )
        assert r3.status_code == 201
        assert r3.json()["version"] == 3

    def test_versao_continua_apos_versoes_pre_existentes(self, client: TestClient, db_session):
        """Se já há versões 1 e 2 no banco (criadas por outra via), o POST cria a 3."""
        tenant, _ = _seed_internal_user(db_session)
        _, _, process = _seed_client_property_process(db_session, tenant=tenant)
        for v in (1, 2):
            db_session.add(RegulatoryDiagnosis(
                tenant_id=tenant.id,
                process_id=process.id,
                content={"v": v, "content": "seed"},
                version=v,
            ))
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.post(
            f"/api/v1/processes/{process.id}/diagnoses",
            headers=headers, json={"content": _valid_content()},
        )
        assert r.status_code == 201
        assert r.json()["version"] == 3

    # ---- Gate A4 — validate_diagnostic_content ANTES de persistir ---------

    def test_422_quando_content_viola_schema__content_vazio(self, client: TestClient, db_session):
        """`content` vazio viola `min_length=1` de StageOutputContent."""
        tenant, _ = _seed_internal_user(db_session)
        _, _, process = _seed_client_property_process(db_session, tenant=tenant)
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        bad = {"content": "", "sources": [{"type": "legislation", "ref": "chunk_1"}]}
        r = client.post(
            f"/api/v1/processes/{process.id}/diagnoses",
            headers=headers, json={"content": bad},
        )
        assert r.status_code == 422
        detail = r.json()["detail"]
        assert "DiagnosticoPreliminarContent" in detail["message"]
        assert isinstance(detail["errors"], list)

    def test_422_quando_content_viola_schema__sources_vazio(self, client: TestClient, db_session):
        """`sources` vazio viola `_sources_non_empty` validator."""
        tenant, _ = _seed_internal_user(db_session)
        _, _, process = _seed_client_property_process(db_session, tenant=tenant)
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        bad = {"content": "ok", "sources": []}
        r = client.post(
            f"/api/v1/processes/{process.id}/diagnoses",
            headers=headers, json={"content": bad},
        )
        assert r.status_code == 422
        # mensagem do validator chega no detail
        assert "sources" in str(r.json()["detail"]["errors"])

    def test_422_quando_content_tem_campo_desconhecido(self, client: TestClient, db_session):
        """`DiagnosticoPreliminarContent` herda de _StrictModel (extra=forbid)."""
        tenant, _ = _seed_internal_user(db_session)
        _, _, process = _seed_client_property_process(db_session, tenant=tenant)
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        bad = {
            "content": "x",
            "sources": [{"type": "legislation", "ref": "c1"}],
            "campo_inventado": 42,
        }
        r = client.post(
            f"/api/v1/processes/{process.id}/diagnoses",
            headers=headers, json={"content": bad},
        )
        assert r.status_code == 422

    def test_422_quando_content_rejeita_nao_persiste(self, client: TestClient, db_session):
        """Confirma que o gate previne escrita: depois de 422, banco continua vazio."""
        tenant, _ = _seed_internal_user(db_session)
        _, _, process = _seed_client_property_process(db_session, tenant=tenant)
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        bad = {"content": "x", "sources": []}
        r = client.post(
            f"/api/v1/processes/{process.id}/diagnoses",
            headers=headers, json={"content": bad},
        )
        assert r.status_code == 422
        # banco continua vazio
        count = (
            db_session.query(RegulatoryDiagnosis)
            .filter(RegulatoryDiagnosis.process_id == process.id)
            .count()
        )
        assert count == 0

    def test_aceita_content_com_riscos_no_formato_antigo(self, client: TestClient, db_session):
        """Dual-emit do A4: payload antigo {descricao, severidade, mitigacao_sugerida}
        é aceito sem 422 e persistido tal qual."""
        tenant, _ = _seed_internal_user(db_session)
        _, _, process = _seed_client_property_process(db_session, tenant=tenant)
        db_session.commit()

        content = _valid_content()
        content["riscos"] = [
            {"descricao": "Multa por área embargada", "severidade": "alto",
             "mitigacao_sugerida": "Defesa administrativa"},
        ]
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.post(
            f"/api/v1/processes/{process.id}/diagnoses",
            headers=headers, json={"content": content},
        )
        assert r.status_code == 201
        body = r.json()
        # JSONB preserva o que entrou (forma bruta)
        assert body["content"]["riscos"][0]["descricao"] == "Multa por área embargada"

    def test_aceita_content_com_riscos_no_formato_novo(self, client: TestClient, db_session):
        """Dual-emit do A4: payload novo (8 campos) também aceito."""
        tenant, _ = _seed_internal_user(db_session)
        _, _, process = _seed_client_property_process(db_session, tenant=tenant)
        db_session.commit()

        content = _valid_content()
        content["riscos"] = [
            {
                "categoria": "ambiental",
                "risco_identificado": "Supressão sem ASV",
                "grau": "critico_impeditivo_potencial",
                "impacto_possivel": "Embargo + multa",
                "prioridade_triagem": "urgentissima",
            },
        ]
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.post(
            f"/api/v1/processes/{process.id}/diagnoses",
            headers=headers, json={"content": content},
        )
        assert r.status_code == 201
        assert r.json()["content"]["riscos"][0]["risco_identificado"] == "Supressão sem ASV"

    def test_tenant_isolation_post_de_outro_tenant_dá_404(self, client: TestClient, db_session):
        """Process de tenant B não pode ser alvo de POST do tenant A."""
        # tenant A (consultor)
        tenant_a, _ = _seed_internal_user(db_session, email="a@example.com")
        # tenant B (com processo)
        tenant_b = Tenant(name="Tenant B")
        db_session.add(tenant_b)
        db_session.flush()
        client_b = Client(
            tenant_id=tenant_b.id, full_name="Cliente B",
            client_type=ClientType.pj, status=ClientStatus.active,
        )
        db_session.add(client_b)
        db_session.flush()
        process_b = Process(
            tenant_id=tenant_b.id, client_id=client_b.id,
            title="Processo B", process_type="car",
            status=ProcessStatus.diagnostico, demand_type=DemandType.car,
        )
        db_session.add(process_b)
        db_session.commit()

        headers = _login(client, "a@example.com", "senha123")
        r = client.post(
            f"/api/v1/processes/{process_b.id}/diagnoses",
            headers=headers, json={"content": _valid_content()},
        )
        # tenant A não vê processo do B → 404, e nada é gravado
        assert r.status_code == 404
        count = (
            db_session.query(RegulatoryDiagnosis)
            .filter(RegulatoryDiagnosis.process_id == process_b.id)
            .count()
        )
        assert count == 0

    def test_payload_sem_chave_content_da_422(self, client: TestClient, db_session):
        """RegulatoryDiagnosisCreate exige `content` no body."""
        tenant, _ = _seed_internal_user(db_session)
        _, _, process = _seed_client_property_process(db_session, tenant=tenant)
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.post(
            f"/api/v1/processes/{process.id}/diagnoses",
            headers=headers, json={},
        )
        assert r.status_code == 422

    def test_payload_com_campo_extra_no_body_da_422(self, client: TestClient, db_session):
        """RegulatoryDiagnosisCreate tem extra='forbid'."""
        tenant, _ = _seed_internal_user(db_session)
        _, _, process = _seed_client_property_process(db_session, tenant=tenant)
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.post(
            f"/api/v1/processes/{process.id}/diagnoses",
            headers=headers,
            json={"content": _valid_content(), "extra_field": "x"},
        )
        assert r.status_code == 422
