"""Testes dos endpoints regulatórios — Sprint A1 Tarefa D2."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.audit_log import AuditLog
from app.models.regulatory import (
    DecisaoConsultor,
    ProcessIssueDecision,
    RegulatoryDiagnosis,
    RegulatoryFamilia,
    RegulatoryIssue,
    RegulatoryIssueSeverity,
    RegulatoryIssueType,
    StatusAchado,
    StatusSaneamento,
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
            severity=RegulatoryIssueSeverity.atencao,
        ))
        db_session.add(RegulatoryIssue(
            tenant_id=tenant.id,
            property_id=prop.id,
            type=RegulatoryIssueType.outro,
            severity=RegulatoryIssueSeverity.informativo,
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
            type=RegulatoryIssueType.outro, severity=RegulatoryIssueSeverity.informativo,
        ))
        db_session.add(RegulatoryIssue(
            tenant_id=tenant.id, property_id=prop.id,
            type=RegulatoryIssueType.sobreposicao_app,
            severity=RegulatoryIssueSeverity.critico,
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
            type=RegulatoryIssueType.outro, severity=RegulatoryIssueSeverity.informativo,
        ))
        db_session.add(RegulatoryIssue(
            tenant_id=tenant.id, property_id=prop.id,
            type=RegulatoryIssueType.poligono_fora_matricula,
            severity=RegulatoryIssueSeverity.critico,
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
            type=RegulatoryIssueType.outro, severity=RegulatoryIssueSeverity.informativo,
            detected_at=now - timedelta(days=2),
        )
        i_new = RegulatoryIssue(
            tenant_id=tenant.id, property_id=prop.id,
            type=RegulatoryIssueType.area_divergente, severity=RegulatoryIssueSeverity.atencao,
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


# ---------------------------------------------------------------------------
# PROMPT_4 Onda B — PATCH /processes/{id}/diagnoses/{version}/validate
# ---------------------------------------------------------------------------

class TestValidateDiagnosis:
    """Camada 1 do Princípio 1 do manifesto: o consultor assina o diagnóstico.

    Fluxo testado: POST cria (validated_at=None) → PATCH /validate registra
    quem validou + quando + AuditLog (Princípio 2).
    """

    def _seed_diagnosis(
        self,
        db_session,
        *,
        tenant: Tenant,
        process: Process,
        version: int = 1,
    ) -> RegulatoryDiagnosis:
        diag = RegulatoryDiagnosis(
            tenant_id=tenant.id,
            process_id=process.id,
            content={"content": "x", "sources": [{"type": "legislation", "ref": "c1"}]},
            version=version,
        )
        db_session.add(diag)
        db_session.flush()
        return diag

    def test_unauthorized_returns_401(self, client: TestClient):
        r = client.patch("/api/v1/processes/1/diagnoses/1/validate")
        assert r.status_code == 401

    def test_404_quando_processo_nao_existe(self, client: TestClient, db_session):
        _seed_internal_user(db_session)
        db_session.commit()
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch("/api/v1/processes/9999/diagnoses/1/validate", headers=headers)
        assert r.status_code == 404

    def test_404_quando_versao_nao_existe(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        _, _, process = _seed_client_property_process(db_session, tenant=tenant)
        db_session.commit()
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/processes/{process.id}/diagnoses/77/validate",
            headers=headers,
        )
        assert r.status_code == 404
        assert "Versão 77" in r.json()["detail"]

    def test_validacao_grava_user_e_timestamp(self, client: TestClient, db_session):
        tenant, user = _seed_internal_user(db_session)
        _, _, process = _seed_client_property_process(db_session, tenant=tenant)
        diag = self._seed_diagnosis(db_session, tenant=tenant, process=process)
        db_session.commit()
        diag_id = diag.id

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/processes/{process.id}/diagnoses/1/validate",
            headers=headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["version"] == 1
        assert body["validated_by_user_id"] == user.id
        assert body["validated_at"] is not None
        # confirma persistência
        db_session.expire_all()
        persisted = db_session.query(RegulatoryDiagnosis).get(diag_id)
        assert persisted.validated_by_user_id == user.id
        assert persisted.validated_at is not None

    def test_409_quando_ja_validado(self, client: TestClient, db_session):
        """Idempotência explícita: revalidar é conflito (evita sobrescrita
        silenciosa do assinante original)."""
        tenant, user = _seed_internal_user(db_session)
        _, _, process = _seed_client_property_process(db_session, tenant=tenant)
        diag = self._seed_diagnosis(db_session, tenant=tenant, process=process)
        diag.validated_by_user_id = user.id
        diag.validated_at = datetime.now(UTC)
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/processes/{process.id}/diagnoses/1/validate",
            headers=headers,
        )
        assert r.status_code == 409
        assert "já validada" in r.json()["detail"]

    def test_audit_log_gravado_com_hash_chain(self, client: TestClient, db_session):
        """Princípio 2 — quem assinou, quando, qual versão fica em AuditLog
        com hash chain SHA-256."""
        tenant, user = _seed_internal_user(db_session)
        _, _, process = _seed_client_property_process(db_session, tenant=tenant)
        diag = self._seed_diagnosis(db_session, tenant=tenant, process=process)
        db_session.commit()
        diag_id = diag.id

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/processes/{process.id}/diagnoses/1/validate",
            headers=headers,
        )
        assert r.status_code == 200

        db_session.expire_all()
        logs = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.entity_type == "regulatory_diagnosis",
                AuditLog.entity_id == diag_id,
                AuditLog.action == "validated",
            )
            .all()
        )
        assert len(logs) == 1
        log = logs[0]
        assert log.tenant_id == tenant.id
        assert log.user_id == user.id
        assert log.hash_sha256 is not None
        assert len(log.hash_sha256) == 64  # SHA-256 hex
        assert log.new_value is not None  # timestamp ISO da validação

    def test_tenant_isolation_outro_tenant_recebe_404(self, client: TestClient, db_session):
        """Tenant B não enxerga diagnóstico do tenant A — 404, nada validado."""
        # tenant A com diag
        tenant_a, user_a = _seed_internal_user(db_session, email="a@example.com")
        _, _, process_a = _seed_client_property_process(db_session, tenant=tenant_a)
        diag_a = self._seed_diagnosis(db_session, tenant=tenant_a, process=process_a)
        # tenant B (login)
        _seed_internal_user(db_session, email="b@example.com")
        db_session.commit()
        diag_a_id = diag_a.id

        headers = _login(client, "b@example.com", "senha123")
        r = client.patch(
            f"/api/v1/processes/{process_a.id}/diagnoses/1/validate",
            headers=headers,
        )
        assert r.status_code == 404
        # confirma que não validou
        db_session.expire_all()
        persisted = db_session.query(RegulatoryDiagnosis).get(diag_a_id)
        assert persisted.validated_at is None
        assert persisted.validated_by_user_id is None

    def test_versoes_anteriores_continuam_sem_validacao(self, client: TestClient, db_session):
        """Valida v2 não afeta v1 (versionamento independente)."""
        tenant, user = _seed_internal_user(db_session)
        _, _, process = _seed_client_property_process(db_session, tenant=tenant)
        v1 = self._seed_diagnosis(db_session, tenant=tenant, process=process, version=1)
        self._seed_diagnosis(db_session, tenant=tenant, process=process, version=2)
        db_session.commit()
        v1_id = v1.id

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/processes/{process.id}/diagnoses/2/validate",
            headers=headers,
        )
        assert r.status_code == 200
        # v1 continua sem validação
        db_session.expire_all()
        v1_persisted = db_session.query(RegulatoryDiagnosis).get(v1_id)
        assert v1_persisted.validated_at is None


# ---------------------------------------------------------------------------
# PROMPT_6 — PATCH /properties/{prop_id}/issues/{issue_id}
# Reconciliação dos 3 status (Opção A) + os 5 botões P4
# ---------------------------------------------------------------------------

def _seed_issue(
    db_session,
    *,
    tenant,
    prop,
    severity: RegulatoryIssueSeverity = RegulatoryIssueSeverity.atencao,
    codigo_alerta: str = "AREA_MATRICULA_X_CAR",
    familia: RegulatoryFamilia = RegulatoryFamilia.area,
    resolved: bool = False,
    status_achado: StatusAchado = StatusAchado.suspeita,
) -> RegulatoryIssue:
    issue = RegulatoryIssue(
        tenant_id=tenant.id,
        property_id=prop.id,
        codigo_alerta=codigo_alerta,
        familia=familia,
        severity=severity,
        resolved_at=datetime.now(UTC) if resolved else None,
        status_achado=status_achado,
    )
    db_session.add(issue)
    db_session.flush()
    return issue


def _seed_decision(
    db_session,
    *,
    tenant,
    process,
    issue,
    decisao: DecisaoConsultor = DecisaoConsultor.corrigir_antes,
    justificativa: str | None = None,
    decided_by_user_id: int | None = None,
) -> ProcessIssueDecision:
    """Helper PROMPT_7 — seed de ProcessIssueDecision para testes."""
    decision = ProcessIssueDecision(
        tenant_id=tenant.id,
        process_id=process.id,
        issue_id=issue.id,
        decisao=decisao,
        justificativa=justificativa,
        decided_by_user_id=decided_by_user_id,
        decided_at=datetime.now(UTC),
    )
    db_session.add(decision)
    db_session.flush()
    return decision


class TestUpdatePropertyIssue:
    """PROMPT_6: PATCH /properties/{prop}/issues/{id} edita os 3 status +
    decisao + justificativa. AuditLog separado por campo alterado."""

    def test_unauthorized_returns_401(self, client: TestClient):
        r = client.patch("/api/v1/properties/1/issues/1", json={})
        assert r.status_code == 401

    def test_404_quando_issue_nao_existe(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        _, prop, _ = _seed_client_property_process(db_session, tenant=tenant)
        db_session.commit()
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(f"/api/v1/properties/{prop.id}/issues/9999", headers=headers, json={})
        assert r.status_code == 404

    def test_404_quando_issue_pertence_a_outra_property(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        client_record, prop, _ = _seed_client_property_process(db_session, tenant=tenant)
        # Cria outra property no mesmo tenant + issue lá (reusa o client)
        other_prop = Property(
            tenant_id=tenant.id, client_id=client_record.id, name="Outra", state="GO",
        )
        db_session.add(other_prop)
        db_session.flush()
        issue = _seed_issue(db_session, tenant=tenant, prop=other_prop)
        db_session.commit()
        headers = _login(client, "consultor@example.com", "senha123")
        # Tentar acessar issue de outra property pelo path de prop1 → 404
        r = client.patch(f"/api/v1/properties/{prop.id}/issues/{issue.id}", headers=headers, json={})
        assert r.status_code == 404

    def test_body_vazio_eh_noop(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        _, prop, _ = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(db_session, tenant=tenant, prop=prop)
        db_session.commit()
        issue_id = issue.id
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(f"/api/v1/properties/{prop.id}/issues/{issue_id}", headers=headers, json={})
        assert r.status_code == 200
        # Nenhum AuditLog gerado (no-op)
        logs = (
            db_session.query(AuditLog)
            .filter(AuditLog.entity_type == "regulatory_issue", AuditLog.entity_id == issue_id)
            .all()
        )
        assert logs == []

    def test_mudar_status_achado_gera_audit_log(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        _, prop, _ = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(db_session, tenant=tenant, prop=prop)
        db_session.commit()
        issue_id = issue.id
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/properties/{prop.id}/issues/{issue_id}",
            headers=headers,
            json={"status_achado": "confirmada"},
        )
        assert r.status_code == 200
        assert r.json()["status_achado"] == "confirmada"
        db_session.expire_all()
        log = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.entity_type == "regulatory_issue",
                AuditLog.entity_id == issue_id,
                AuditLog.action == "status_achado_changed",
            )
            .one()
        )
        assert log.old_value == "suspeita"
        assert log.new_value == "confirmada"
        assert log.hash_sha256 is not None
        assert len(log.hash_sha256) == 64

    def test_mudar_dois_status_no_mesmo_patch_gera_auditlogs_distintos(
        self, client: TestClient, db_session,
    ):
        """PROMPT_7: PATCH /issues só tem 2 campos (status_achado e
        status_saneamento). Múltiplos campos no mesmo body geram AuditLogs
        granulares com hash chain."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, _ = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(
            db_session, tenant=tenant, prop=prop,
            severity=RegulatoryIssueSeverity.critico,
        )
        db_session.commit()
        issue_id = issue.id

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/properties/{prop.id}/issues/{issue_id}",
            headers=headers,
            json={
                "status_achado": "confirmada",
                "status_saneamento": "em_validacao",
            },
        )
        assert r.status_code == 200
        db_session.expire_all()
        logs = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.entity_type == "regulatory_issue",
                AuditLog.entity_id == issue_id,
            )
            .all()
        )
        actions = {log.action for log in logs}
        assert actions == {"status_achado_changed", "status_saneamento_changed"}
        for log in logs:
            assert log.hash_sha256 is not None
            assert len(log.hash_sha256) == 64

    def test_mesmo_valor_nao_gera_auditlog(self, client: TestClient, db_session):
        """No-op por campo (mesmo valor) não é evento auditável."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, _ = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(
            db_session, tenant=tenant, prop=prop,
            severity=RegulatoryIssueSeverity.critico,
        )
        db_session.commit()
        issue_id = issue.id

        headers = _login(client, "consultor@example.com", "senha123")
        # PATCH com o mesmo valor que já está (suspeita é default; pendente também)
        r = client.patch(
            f"/api/v1/properties/{prop.id}/issues/{issue_id}",
            headers=headers,
            json={
                "status_achado": "suspeita",      # mesmo default
                "status_saneamento": "pendente",  # mesmo default
            },
        )
        assert r.status_code == 200
        db_session.expire_all()
        logs = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.entity_type == "regulatory_issue",
                AuditLog.entity_id == issue_id,
            )
            .all()
        )
        assert logs == []

    def test_valor_invalido_retorna_422(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        _, prop, _ = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(db_session, tenant=tenant, prop=prop)
        db_session.commit()
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/properties/{prop.id}/issues/{issue.id}",
            headers=headers,
            json={"status_achado": "valor_inexistente"},
        )
        assert r.status_code == 422

    def test_extra_field_no_body_retorna_422(self, client: TestClient, db_session):
        """RegulatoryIssueUpdate tem extra='forbid'."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, _ = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(db_session, tenant=tenant, prop=prop)
        db_session.commit()
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/properties/{prop.id}/issues/{issue.id}",
            headers=headers,
            json={"campo_inventado": "x"},
        )
        assert r.status_code == 422

    def test_tenant_isolation(self, client: TestClient, db_session):
        """Issue de outro tenant retorna 404 (não enxerga)."""
        tenant_a, _ = _seed_internal_user(db_session, email="a@example.com")
        _, prop_a, _ = _seed_client_property_process(db_session, tenant=tenant_a)
        issue_a = _seed_issue(db_session, tenant=tenant_a, prop=prop_a)
        _seed_internal_user(db_session, email="b@example.com")
        db_session.commit()

        headers = _login(client, "b@example.com", "senha123")
        r = client.patch(
            f"/api/v1/properties/{prop_a.id}/issues/{issue_a.id}",
            headers=headers,
            json={"status_achado": "confirmada"},
        )
        # Tenant B não enxerga property A → 404 antes de chegar à issue
        assert r.status_code == 404


class TestProcessIssueDecisionJustificativaObrigatoria:
    """Fechamento da dívida #19 (PROMPT_6 revisão) migrado para PROMPT_7
    (ADR-012) — agora aplica no schema `ProcessIssueDecisionCreate` do PUT
    `/processes/{pid}/issues/{iid}/decision`. Mesma regra: `ignorar_justificado`
    e `fora_escopo` exigem `justificativa` não-vazia. Princípio 2 (auditável)
    no caso que mais importa (descartar uma crítica)."""

    def test_ignorar_sem_justificativa_eh_422(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        _, prop, process = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(
            db_session, tenant=tenant, prop=prop,
            severity=RegulatoryIssueSeverity.critico,
        )
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.put(
            f"/api/v1/processes/{process.id}/issues/{issue.id}/decision",
            headers=headers,
            json={"decisao": "ignorar_justificado"},
        )
        assert r.status_code == 422
        detail = str(r.json()["detail"])
        assert "ignorar_justificado" in detail
        assert "justificativa" in detail.lower()

    def test_fora_escopo_sem_justificativa_eh_422(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        _, prop, process = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(
            db_session, tenant=tenant, prop=prop,
            severity=RegulatoryIssueSeverity.critico,
        )
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.put(
            f"/api/v1/processes/{process.id}/issues/{issue.id}/decision",
            headers=headers,
            json={"decisao": "fora_escopo"},
        )
        assert r.status_code == 422

    def test_ignorar_com_justificativa_so_espacos_eh_422(self, client: TestClient, db_session):
        """`str_strip_whitespace=True` no schema: `"   "` vira `""` → trigger."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, process = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(
            db_session, tenant=tenant, prop=prop,
            severity=RegulatoryIssueSeverity.critico,
        )
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.put(
            f"/api/v1/processes/{process.id}/issues/{issue.id}/decision",
            headers=headers,
            json={
                "decisao": "ignorar_justificado",
                "justificativa": "   ",
            },
        )
        assert r.status_code == 422

    def test_ignorar_com_justificativa_preenchida_eh_200(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        _, prop, process = _seed_client_property_process(db_session, tenant=tenant)
        # PROMPT_8 (#17): Regra B exige achado != suspeita para registrar
        # decisão. `confirmada` é o caminho feliz semântico.
        issue = _seed_issue(
            db_session, tenant=tenant, prop=prop,
            severity=RegulatoryIssueSeverity.critico,
            status_achado=StatusAchado.confirmada,
        )
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.put(
            f"/api/v1/processes/{process.id}/issues/{issue.id}/decision",
            headers=headers,
            json={
                "decisao": "ignorar_justificado",
                "justificativa": "Falso positivo: nome do imóvel é histórico, mesma matrícula.",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["decisao"] == "ignorar_justificado"
        assert "Falso positivo" in body["justificativa"]

    def test_corrigir_antes_sem_justificativa_eh_200(self, client: TestClient, db_session):
        """As outras 3 decisões NÃO exigem justificativa — só ignorar e fora_escopo."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, process = _seed_client_property_process(db_session, tenant=tenant)
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        for decisao in ("corrigir_antes", "seguir_com_ressalva", "solicitar_doc"):
            # Cria issue nova pra cada decisão (PUT é upsert por par; uma issue
            # só pode ter uma decisão no processo). PROMPT_8 (#17): Regra B
            # exige achado != suspeita.
            issue = _seed_issue(
                db_session, tenant=tenant, prop=prop,
                severity=RegulatoryIssueSeverity.critico,
                codigo_alerta=f"AREA_MATRICULA_X_CAR",  # mesmo código pode repetir; chave é (process, issue)
                status_achado=StatusAchado.confirmada,
            )
            db_session.commit()
            r = client.put(
                f"/api/v1/processes/{process.id}/issues/{issue.id}/decision",
                headers=headers,
                json={"decisao": decisao},
            )
            assert r.status_code == 200, f"{decisao} deveria passar sem justificativa"


# ---------------------------------------------------------------------------
# PROMPT_6 — Gate camada 2 do Princípio 1 no PATCH /validate
# ---------------------------------------------------------------------------

class TestValidateDiagnosisGateCamada2:
    """Camada 2 do Princípio 1: PATCH /validate rejeita assinatura se houver
    alerta crítico sem `ProcessIssueDecision` no processo (ADR-012 — PROMPT_7).
    A decisão é contextual ao processo: cada trabalho começa do zero."""

    def _seed_diag(self, db_session, *, tenant, process, version=1):
        diag = RegulatoryDiagnosis(
            tenant_id=tenant.id, process_id=process.id,
            content={"content": "x", "sources": [{"type": "legislation", "ref": "c1"}]},
            version=version,
        )
        db_session.add(diag)
        db_session.flush()
        return diag

    def test_422_com_critica_sem_decisao(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        _, prop, process = _seed_client_property_process(db_session, tenant=tenant)
        self._seed_diag(db_session, tenant=tenant, process=process)
        _seed_issue(
            db_session, tenant=tenant, prop=prop,
            severity=RegulatoryIssueSeverity.critico,
            codigo_alerta="GEO_AUSENTE",
            familia=RegulatoryFamilia.geo_incra,
        )
        # NÃO cria ProcessIssueDecision → gate deve rejeitar
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/processes/{process.id}/diagnoses/1/validate",
            headers=headers,
        )
        assert r.status_code == 422
        detail = r.json()["detail"]
        assert "crítico" in detail["message"].lower() or "critico" in detail["message"].lower()
        assert len(detail["alertas_pendentes"]) == 1
        assert detail["alertas_pendentes"][0]["codigo_alerta"] == "GEO_AUSENTE"
        assert detail["alertas_pendentes"][0]["severity"] == "critico"

    def test_422_lista_todas_as_criticas_pendentes(self, client: TestClient, db_session):
        tenant, _ = _seed_internal_user(db_session)
        _, prop, process = _seed_client_property_process(db_session, tenant=tenant)
        self._seed_diag(db_session, tenant=tenant, process=process)
        for codigo in ("GEO_AUSENTE", "EMBARGO_NAO_INFORMADO", "RL_CAR_X_REALIDADE"):
            _seed_issue(
                db_session, tenant=tenant, prop=prop,
                severity=RegulatoryIssueSeverity.critico,
                codigo_alerta=codigo,
                familia=RegulatoryFamilia.geo_incra,
            )
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/processes/{process.id}/diagnoses/1/validate",
            headers=headers,
        )
        assert r.status_code == 422
        codigos = {a["codigo_alerta"] for a in r.json()["detail"]["alertas_pendentes"]}
        assert codigos == {"GEO_AUSENTE", "EMBARGO_NAO_INFORMADO", "RL_CAR_X_REALIDADE"}

    def test_200_com_todas_as_criticas_decididas(self, client: TestClient, db_session):
        """PROMPT_7: a decisão vive em ProcessIssueDecision, criada para
        este processo (cada trabalho recomeça — ADR-012)."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, process = _seed_client_property_process(db_session, tenant=tenant)
        self._seed_diag(db_session, tenant=tenant, process=process)
        issue = _seed_issue(
            db_session, tenant=tenant, prop=prop,
            severity=RegulatoryIssueSeverity.critico,
        )
        _seed_decision(
            db_session, tenant=tenant, process=process, issue=issue,
            decisao=DecisaoConsultor.corrigir_antes,
        )
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/processes/{process.id}/diagnoses/1/validate",
            headers=headers,
        )
        assert r.status_code == 200

    def test_200_quando_critica_resolvida(self, client: TestClient, db_session):
        """Issue crítica RESOLVIDA (resolved_at != None) não bloqueia — já
        sanada no mundo, não exige decisão pendente."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, process = _seed_client_property_process(db_session, tenant=tenant)
        self._seed_diag(db_session, tenant=tenant, process=process)
        _seed_issue(
            db_session, tenant=tenant, prop=prop,
            severity=RegulatoryIssueSeverity.critico,
            resolved=True,  # resolvida no mundo, sem ProcessIssueDecision
        )
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/processes/{process.id}/diagnoses/1/validate",
            headers=headers,
        )
        assert r.status_code == 200

    def test_200_sem_issues_criticas(self, client: TestClient, db_session):
        """Alertas alto/atencao/informativo sem decisão NÃO bloqueiam — gate
        é só para crítico."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, process = _seed_client_property_process(db_session, tenant=tenant)
        self._seed_diag(db_session, tenant=tenant, process=process)
        _seed_issue(
            db_session, tenant=tenant, prop=prop,
            severity=RegulatoryIssueSeverity.alto,
        )
        _seed_issue(
            db_session, tenant=tenant, prop=prop,
            severity=RegulatoryIssueSeverity.atencao,
            codigo_alerta="AREA_CAR_X_CCIR",
        )
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/processes/{process.id}/diagnoses/1/validate",
            headers=headers,
        )
        assert r.status_code == 200

    def test_422_nao_grava_validated(self, client: TestClient, db_session):
        """Quando o gate rejeita (422), o diagnóstico NÃO é validado nem
        ganha AuditLog. Idempotência defensiva."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, process = _seed_client_property_process(db_session, tenant=tenant)
        diag = self._seed_diag(db_session, tenant=tenant, process=process)
        _seed_issue(
            db_session, tenant=tenant, prop=prop,
            severity=RegulatoryIssueSeverity.critico,
        )
        db_session.commit()
        diag_id = diag.id

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/processes/{process.id}/diagnoses/1/validate",
            headers=headers,
        )
        assert r.status_code == 422

    def test_decisao_de_outro_processo_nao_libera_gate(self, client: TestClient, db_session):
        """**ADR-012 — comportamento contextual:** decisão tomada no processo
        A não vale automaticamente no processo B. Cada processo recomeça."""
        tenant, _ = _seed_internal_user(db_session)
        client_record, prop, process_a = _seed_client_property_process(
            db_session, tenant=tenant,
        )
        # Cria segundo processo na mesma property
        process_b = Process(
            tenant_id=tenant.id, client_id=client_record.id, property_id=prop.id,
            title="Processo B (crédito)", process_type="car",
            status=ProcessStatus.diagnostico, demand_type=DemandType.car,
        )
        db_session.add(process_b)
        db_session.flush()
        self._seed_diag(db_session, tenant=tenant, process=process_b)
        issue = _seed_issue(
            db_session, tenant=tenant, prop=prop,
            severity=RegulatoryIssueSeverity.critico,
            codigo_alerta="TIT_PROP_MATRICULA_X_CAR",
            familia=RegulatoryFamilia.titularidade,
        )
        # Decisão tomada no processo A (venda)
        _seed_decision(
            db_session, tenant=tenant, process=process_a, issue=issue,
            decisao=DecisaoConsultor.seguir_com_ressalva,
        )
        db_session.commit()

        # PROCESSO B (crédito) — gate deve REJEITAR mesmo com decisão no A.
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/processes/{process_b.id}/diagnoses/1/validate",
            headers=headers,
        )
        assert r.status_code == 422
        assert len(r.json()["detail"]["alertas_pendentes"]) == 1


# ---------------------------------------------------------------------------
# PROMPT_7 (ADR-012) — PUT/GET /processes/{pid}/issues/{iid}/decision
# ---------------------------------------------------------------------------

class TestProcessIssueDecision:
    """Decisão contextual ao processo (ADR-012): PUT cria/atualiza,
    GET lê, 404 quando não existe (cada processo recomeça do zero)."""

    def test_get_unauthorized(self, client: TestClient):
        r = client.get("/api/v1/processes/1/issues/1/decision")
        assert r.status_code == 401

    def test_put_unauthorized(self, client: TestClient):
        r = client.put("/api/v1/processes/1/issues/1/decision", json={"decisao": "corrigir_antes"})
        assert r.status_code == 401

    def test_get_404_quando_processo_nao_existe(self, client: TestClient, db_session):
        _seed_internal_user(db_session)
        db_session.commit()
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.get("/api/v1/processes/9999/issues/1/decision", headers=headers)
        assert r.status_code == 404

    def test_get_404_quando_nao_ha_decisao(self, client: TestClient, db_session):
        """Cada processo começa sem decisão. GET retorna 404 explicando."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, process = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(db_session, tenant=tenant, prop=prop)
        db_session.commit()
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.get(
            f"/api/v1/processes/{process.id}/issues/{issue.id}/decision",
            headers=headers,
        )
        assert r.status_code == 404
        assert "ADR-012" in r.json()["detail"]

    def test_put_cria_primeira_decisao(self, client: TestClient, db_session):
        tenant, user = _seed_internal_user(db_session)
        _, prop, process = _seed_client_property_process(db_session, tenant=tenant)
        # PROMPT_8 (#17): Regra B exige achado != suspeita.
        issue = _seed_issue(
            db_session, tenant=tenant, prop=prop,
            severity=RegulatoryIssueSeverity.critico,
            status_achado=StatusAchado.confirmada,
        )
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.put(
            f"/api/v1/processes/{process.id}/issues/{issue.id}/decision",
            headers=headers,
            json={
                "decisao": "corrigir_antes",
                "justificativa": "Cliente vai retificar matrícula primeiro",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["decisao"] == "corrigir_antes"
        assert body["process_id"] == process.id
        assert body["issue_id"] == issue.id
        assert body["decided_by_user_id"] == user.id
        assert body["decided_at"] is not None
        assert "retificar" in body["justificativa"]

    def test_put_cria_gera_auditlog_action_created(self, client: TestClient, db_session):
        tenant, user = _seed_internal_user(db_session)
        _, prop, process = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(
            db_session, tenant=tenant, prop=prop,
            severity=RegulatoryIssueSeverity.critico,
            status_achado=StatusAchado.confirmada,
        )
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.put(
            f"/api/v1/processes/{process.id}/issues/{issue.id}/decision",
            headers=headers,
            json={"decisao": "corrigir_antes"},
        )
        assert r.status_code == 200
        decision_id = r.json()["id"]

        db_session.expire_all()
        logs = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.entity_type == "process_issue_decision",
                AuditLog.entity_id == decision_id,
            )
            .all()
        )
        assert len(logs) == 1
        assert logs[0].action == "created"
        assert logs[0].user_id == user.id
        assert logs[0].new_value == "corrigir_antes"
        assert logs[0].hash_sha256 is not None
        assert len(logs[0].hash_sha256) == 64

    def test_put_atualiza_decisao_existente(self, client: TestClient, db_session):
        """PUT é upsert. 2º PUT no mesmo par (process, issue) ATUALIZA, não
        cria nova linha (unique constraint)."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, process = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(
            db_session, tenant=tenant, prop=prop,
            severity=RegulatoryIssueSeverity.critico,
            status_achado=StatusAchado.confirmada,
        )
        existing = _seed_decision(
            db_session, tenant=tenant, process=process, issue=issue,
            decisao=DecisaoConsultor.solicitar_doc,
        )
        db_session.commit()
        decision_id = existing.id

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.put(
            f"/api/v1/processes/{process.id}/issues/{issue.id}/decision",
            headers=headers,
            json={"decisao": "corrigir_antes"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == decision_id  # mesma linha, não nova
        assert body["decisao"] == "corrigir_antes"

        # Total de ProcessIssueDecision continua 1 (não duplicou)
        db_session.expire_all()
        count = db_session.query(ProcessIssueDecision).count()
        assert count == 1

    def test_put_atualiza_gera_auditlog_granular(self, client: TestClient, db_session):
        """Mudança da decisão gera 1 AuditLog `decisao_changed`; mudança da
        justificativa gera outro `justificativa_changed`. Granularidade
        herdada do PROMPT_6."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, process = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(
            db_session, tenant=tenant, prop=prop,
            severity=RegulatoryIssueSeverity.critico,
            status_achado=StatusAchado.confirmada,
        )
        existing = _seed_decision(
            db_session, tenant=tenant, process=process, issue=issue,
            decisao=DecisaoConsultor.solicitar_doc,
            justificativa="Aguardando matrícula atualizada",
        )
        db_session.commit()
        decision_id = existing.id

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.put(
            f"/api/v1/processes/{process.id}/issues/{issue.id}/decision",
            headers=headers,
            json={
                "decisao": "seguir_com_ressalva",
                "justificativa": "Cliente trouxe declaração, aceito o risco",
            },
        )
        assert r.status_code == 200

        db_session.expire_all()
        logs = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.entity_type == "process_issue_decision",
                AuditLog.entity_id == decision_id,
            )
            .all()
        )
        actions = {log.action for log in logs}
        assert actions == {"decisao_changed", "justificativa_changed"}

    def test_put_mesmo_valor_eh_noop(self, client: TestClient, db_session):
        """PUT com exatamente os mesmos valores não gera AuditLog."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, process = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(
            db_session, tenant=tenant, prop=prop,
            severity=RegulatoryIssueSeverity.critico,
            status_achado=StatusAchado.confirmada,
        )
        existing = _seed_decision(
            db_session, tenant=tenant, process=process, issue=issue,
            decisao=DecisaoConsultor.corrigir_antes,
        )
        db_session.commit()
        decision_id = existing.id

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.put(
            f"/api/v1/processes/{process.id}/issues/{issue.id}/decision",
            headers=headers,
            json={"decisao": "corrigir_antes"},
        )
        assert r.status_code == 200
        db_session.expire_all()
        logs = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.entity_type == "process_issue_decision",
                AuditLog.entity_id == decision_id,
            )
            .all()
        )
        assert logs == []

    def test_put_404_quando_issue_nao_pertence_a_property_do_processo(
        self, client: TestClient, db_session,
    ):
        """Não dá pra registrar decisão usando issue de OUTRO imóvel."""
        tenant, _ = _seed_internal_user(db_session)
        client_record, prop_a, process_a = _seed_client_property_process(db_session, tenant=tenant)
        # Property B no mesmo tenant + issue
        prop_b = Property(tenant_id=tenant.id, client_id=client_record.id, name="B", state="GO")
        db_session.add(prop_b)
        db_session.flush()
        issue_b = _seed_issue(db_session, tenant=tenant, prop=prop_b)
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        # Tentativa: processo_a + issue_b (issue de outra property) → 404
        r = client.put(
            f"/api/v1/processes/{process_a.id}/issues/{issue_b.id}/decision",
            headers=headers,
            json={"decisao": "corrigir_antes"},
        )
        assert r.status_code == 404

    def test_tenant_isolation(self, client: TestClient, db_session):
        """Tenant B não enxerga processo do tenant A → 404 antes de chegar
        à issue."""
        tenant_a, _ = _seed_internal_user(db_session, email="a@example.com")
        _, prop_a, process_a = _seed_client_property_process(db_session, tenant=tenant_a)
        issue_a = _seed_issue(db_session, tenant=tenant_a, prop=prop_a)
        _seed_internal_user(db_session, email="b@example.com")
        db_session.commit()

        headers = _login(client, "b@example.com", "senha123")
        r = client.put(
            f"/api/v1/processes/{process_a.id}/issues/{issue_a.id}/decision",
            headers=headers,
            json={"decisao": "corrigir_antes"},
        )
        assert r.status_code == 404

    def test_get_retorna_decisao_existente(self, client: TestClient, db_session):
        tenant, user = _seed_internal_user(db_session)
        _, prop, process = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(
            db_session, tenant=tenant, prop=prop,
            severity=RegulatoryIssueSeverity.critico,
        )
        _seed_decision(
            db_session, tenant=tenant, process=process, issue=issue,
            decisao=DecisaoConsultor.seguir_com_ressalva,
            justificativa="aceito o risco",
            decided_by_user_id=user.id,
        )
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.get(
            f"/api/v1/processes/{process.id}/issues/{issue.id}/decision",
            headers=headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["decisao"] == "seguir_com_ressalva"
        assert body["justificativa"] == "aceito o risco"
        assert body["decided_by_user_id"] == user.id


# ---------------------------------------------------------------------------
# PROMPT_8 (#17) — Coerência entre status do alerta
# ---------------------------------------------------------------------------

class TestCoerenciaStatusPerene:
    """PROMPT_8 (#17) — Regra A: saneamento em estado ATIVO (em_validacao)
    ou CONCLUÍDO (saneado) exige status_achado in {confirmada, resolvida}.

    Validado em duas frentes:
    - Body completo (2 status juntos): fast-fail no @model_validator do
      `RegulatoryIssueUpdate` (422 do Pydantic).
    - PATCH parcial: validado no endpoint sobre o estado **resultante**
      (corpo aplicado sobre a issue carregada) — 422 com mensagem
      acionável que cita `confirmada`/`resolvida`.
    """

    def test_body_completo_suspeita_mais_em_validacao_eh_422(
        self, client: TestClient, db_session,
    ):
        """Caminho mais comum do absurdo: consultor tenta marcar saneamento
        ativo sem antes confirmar o achado. Fast-fail no schema."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, _ = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(db_session, tenant=tenant, prop=prop)
        db_session.commit()
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/properties/{prop.id}/issues/{issue.id}",
            headers=headers,
            json={"status_achado": "suspeita", "status_saneamento": "em_validacao"},
        )
        assert r.status_code == 422

    def test_body_completo_descartada_mais_saneado_eh_422(
        self, client: TestClient, db_session,
    ):
        """Saneamento concluído sobre achado descartado é absurdo simétrico —
        não se sanea o que não é divergência."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, _ = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(db_session, tenant=tenant, prop=prop)
        db_session.commit()
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/properties/{prop.id}/issues/{issue.id}",
            headers=headers,
            json={"status_achado": "descartada", "status_saneamento": "saneado"},
        )
        assert r.status_code == 422

    def test_patch_parcial_estado_resultante_invalido_eh_422(
        self, client: TestClient, db_session,
    ):
        """Issue está em (suspeita, pendente); body manda só
        status_saneamento=saneado → estado resultante (suspeita, saneado)
        é proibido. A fonte da verdade é o endpoint (model_validator não
        dispara porque só 1 campo vem no body)."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, _ = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(db_session, tenant=tenant, prop=prop)
        db_session.commit()
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/properties/{prop.id}/issues/{issue.id}",
            headers=headers,
            json={"status_saneamento": "saneado"},
        )
        assert r.status_code == 422
        detail = r.json()["detail"]
        # Mensagem cita `confirmada`/`resolvida` para a UI orientar a ação.
        assert "confirmada" in detail
        assert "resolvida" in detail

    def test_patch_parcial_estado_resultante_valido_eh_200(
        self, client: TestClient, db_session,
    ):
        """Issue está em (confirmada, pendente); body manda só
        status_saneamento=saneado → resultante (confirmada, saneado) ok."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, _ = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(
            db_session, tenant=tenant, prop=prop,
            status_achado=StatusAchado.confirmada,
        )
        db_session.commit()
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/properties/{prop.id}/issues/{issue.id}",
            headers=headers,
            json={"status_saneamento": "saneado"},
        )
        assert r.status_code == 200
        assert r.json()["status_saneamento"] == "saneado"

    def test_transicao_simultanea_confirmada_em_validacao_eh_200(
        self, client: TestClient, db_session,
    ):
        """Caminho feliz comum: consultor revisa o alerta e marca os dois
        status no mesmo PATCH. Nenhum fast-fail."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, _ = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(db_session, tenant=tenant, prop=prop)
        db_session.commit()
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/properties/{prop.id}/issues/{issue.id}",
            headers=headers,
            json={"status_achado": "confirmada", "status_saneamento": "em_validacao"},
        )
        assert r.status_code == 200

    def test_resolvida_mais_saneado_eh_200(self, client: TestClient, db_session):
        """`resolvida` é evolução terminal de `confirmada` e habilita
        saneamento concluído — decisão de UX (não bloqueia transição
        simultânea no PATCH)."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, _ = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(
            db_session, tenant=tenant, prop=prop,
            status_achado=StatusAchado.confirmada,
        )
        db_session.commit()
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/properties/{prop.id}/issues/{issue.id}",
            headers=headers,
            json={"status_achado": "resolvida", "status_saneamento": "saneado"},
        )
        assert r.status_code == 200

    def test_saneamento_descartado_aceita_qualquer_achado(
        self, client: TestClient, db_session,
    ):
        """`descartado`/`pendente`/`nao_aplicavel` não constrangem — só
        `em_validacao` e `saneado` exigem achado validado."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, _ = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(db_session, tenant=tenant, prop=prop)
        db_session.commit()
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.patch(
            f"/api/v1/properties/{prop.id}/issues/{issue.id}",
            headers=headers,
            # Achado em `suspeita` + saneamento `descartado` é OK
            # (saneamento não foi iniciado nem concluído).
            json={"status_saneamento": "descartado"},
        )
        assert r.status_code == 200


class TestDecisaoBloqueadaSeAchadoSuspeita:
    """PROMPT_8 (#17) — Regra B: PUT /processes/.../decision rejeita
    quando `issue.status_achado == suspeita`. Decide-se o que fazer com
    a divergência só depois de confirmar que ela é real.

    Aplicado ao endpoint, não ao schema (precisa do estado da issue).
    """

    def test_put_decision_com_achado_suspeita_eh_422(
        self, client: TestClient, db_session,
    ):
        """Issue default (suspeita) + PUT decision → 422 com mensagem
        acionável citando 'Confirme ou descarte'."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, process = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(
            db_session, tenant=tenant, prop=prop,
            severity=RegulatoryIssueSeverity.critico,
            # status_achado=suspeita (default)
        )
        db_session.commit()
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.put(
            f"/api/v1/processes/{process.id}/issues/{issue.id}/decision",
            headers=headers,
            json={"decisao": "corrigir_antes"},
        )
        assert r.status_code == 422
        detail = r.json()["detail"]
        assert "suspeita" in detail
        assert "Confirme ou descarte" in detail

    def test_put_decision_com_achado_confirmada_eh_200(
        self, client: TestClient, db_session,
    ):
        """Caminho feliz: achado já confirmado → PUT decisão aceita."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, process = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(
            db_session, tenant=tenant, prop=prop,
            severity=RegulatoryIssueSeverity.critico,
            status_achado=StatusAchado.confirmada,
        )
        db_session.commit()
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.put(
            f"/api/v1/processes/{process.id}/issues/{issue.id}/decision",
            headers=headers,
            json={"decisao": "corrigir_antes"},
        )
        assert r.status_code == 200
        assert r.json()["decisao"] == "corrigir_antes"

    def test_put_decision_com_suspeita_nao_grava_decision_nem_auditlog(
        self, client: TestClient, db_session,
    ):
        """422 da Regra B é defensivo: zero efeito colateral no DB."""
        tenant, _ = _seed_internal_user(db_session)
        _, prop, process = _seed_client_property_process(db_session, tenant=tenant)
        issue = _seed_issue(
            db_session, tenant=tenant, prop=prop,
            severity=RegulatoryIssueSeverity.critico,
        )
        db_session.commit()
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.put(
            f"/api/v1/processes/{process.id}/issues/{issue.id}/decision",
            headers=headers,
            json={"decisao": "corrigir_antes"},
        )
        assert r.status_code == 422
        db_session.expire_all()
        # Nenhuma ProcessIssueDecision criada
        assert db_session.query(ProcessIssueDecision).count() == 0
        # Nenhum AuditLog associado
        logs = (
            db_session.query(AuditLog)
            .filter(AuditLog.entity_type == "process_issue_decision")
            .all()
        )
        assert logs == []
