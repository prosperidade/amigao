"""Testes do feedback loop AtendimentoAgent — Sprint A1 Tarefa E.

Cobre tanto o endpoint /classify quanto /admin/intake-feedback/stats,
incluindo a idempotência (cada call gera log; último por processo conta
nas stats), tenant isolation e captura automática da última saída do
AtendimentoAgent.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.ai_job import AIJob, AIJobStatus, AIJobType
from app.models.client import Client, ClientStatus, ClientType
from app.models.intake_classification_feedback import IntakeClassificationFeedback
from app.models.intake_draft import IntakeDraft, IntakeDraftState
from app.models.process import DemandType, Process, ProcessStatus
from app.models.tenant import Tenant
from app.models.user import User


def _login(http: TestClient, email: str, password: str) -> dict[str, str]:
    response = http.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _seed_internal(db_session, *, email: str = "consultor@example.com") -> tuple[Tenant, User]:
    tenant = Tenant(name="Tenant E")
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


def _seed_process_with_draft(
    db_session, *, tenant: Tenant, ai_demand_type: str | None = None,
) -> tuple[Process, IntakeDraft, AIJob | None]:
    client = Client(
        tenant_id=tenant.id,
        full_name="Cliente E",
        client_type=ClientType.pj,
        status=ClientStatus.active,
    )
    db_session.add(client)
    db_session.flush()

    draft = IntakeDraft(
        tenant_id=tenant.id,
        state=IntakeDraftState.card_criado,
        form_data={},
    )
    db_session.add(draft)
    db_session.flush()

    process = Process(
        tenant_id=tenant.id,
        client_id=client.id,
        title="Processo E",
        process_type="car",
        status=ProcessStatus.diagnostico,
        demand_type=DemandType.nao_identificado,
    )
    db_session.add(process)
    db_session.flush()

    draft.linked_process_id = process.id

    ai_job: AIJob | None = None
    if ai_demand_type is not None:
        ai_job = AIJob(
            tenant_id=tenant.id,
            entity_type="intake_draft",
            entity_id=draft.id,
            job_type=AIJobType.classify_demand,
            status=AIJobStatus.completed,
            agent_name="atendimento",
            result={"demand_type": ai_demand_type, "confidence": "high"},
        )
        db_session.add(ai_job)
        db_session.flush()

    return process, draft, ai_job


# ---------------------------------------------------------------------------
# POST /processes/{id}/classify
# ---------------------------------------------------------------------------

class TestClassifyEndpoint:
    def test_unauthorized_returns_401(self, client: TestClient):
        r = client.post("/api/v1/processes/1/classify", json={"demand_type": "car"})
        assert r.status_code == 401

    def test_404_when_process_missing(self, client: TestClient, db_session):
        _seed_internal(db_session)
        db_session.commit()
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.post(
            "/api/v1/processes/99999/classify",
            json={"demand_type": "car"},
            headers=headers,
        )
        assert r.status_code == 404

    def test_invalid_demand_type_returns_422(self, client: TestClient, db_session):
        tenant, _ = _seed_internal(db_session)
        process, _, _ = _seed_process_with_draft(db_session, tenant=tenant)
        db_session.commit()
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.post(
            f"/api/v1/processes/{process.id}/classify",
            json={"demand_type": "naoexiste"},
            headers=headers,
        )
        assert r.status_code == 422

    def test_classify_updates_demand_type_and_logs(self, client: TestClient, db_session):
        tenant, _ = _seed_internal(db_session)
        process, _, ai_job = _seed_process_with_draft(
            db_session, tenant=tenant, ai_demand_type="car",
        )
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.post(
            f"/api/v1/processes/{process.id}/classify",
            json={"demand_type": "retificacao_car"},
            headers=headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["previous_demand_type"] == "nao_identificado"
        assert body["new_demand_type"] == "retificacao_car"
        assert body["feedback_logged"] is True
        assert body["ai_demand_type"] == "car"
        assert body["diverged_from_ai"] is True

        db_session.expire_all()
        process_db = db_session.query(Process).get(process.id)
        assert process_db.demand_type == DemandType.retificacao_car

        log = (
            db_session.query(IntakeClassificationFeedback)
            .filter_by(process_id=process.id)
            .first()
        )
        assert log is not None
        assert log.ai_demand_type == "car"
        assert log.corrected_demand_type == "retificacao_car"
        assert log.ai_run_id == ai_job.id

    def test_classify_logs_even_when_ai_did_not_run(self, client: TestClient, db_session):
        tenant, _ = _seed_internal(db_session)
        process, _, _ = _seed_process_with_draft(db_session, tenant=tenant)  # sem AIJob
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        r = client.post(
            f"/api/v1/processes/{process.id}/classify",
            json={"demand_type": "licenciamento"},
            headers=headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ai_demand_type"] is None
        assert body["diverged_from_ai"] is False

        log = (
            db_session.query(IntakeClassificationFeedback)
            .filter_by(process_id=process.id)
            .first()
        )
        assert log is not None
        assert log.ai_demand_type is None
        assert log.corrected_demand_type == "licenciamento"

    def test_classify_idempotency_each_call_logs(self, client: TestClient, db_session):
        tenant, _ = _seed_internal(db_session)
        process, _, _ = _seed_process_with_draft(
            db_session, tenant=tenant, ai_demand_type="car",
        )
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        client.post(
            f"/api/v1/processes/{process.id}/classify",
            json={"demand_type": "retificacao_car"},
            headers=headers,
        )
        client.post(
            f"/api/v1/processes/{process.id}/classify",
            json={"demand_type": "car"},  # de volta
            headers=headers,
        )

        logs = (
            db_session.query(IntakeClassificationFeedback)
            .filter_by(process_id=process.id)
            .order_by(IntakeClassificationFeedback.id)
            .all()
        )
        assert len(logs) == 2
        assert logs[0].corrected_demand_type == "retificacao_car"
        assert logs[1].corrected_demand_type == "car"

    def test_tenant_isolation(self, client: TestClient, db_session):
        tenant_a, _ = _seed_internal(db_session, email="userA@example.com")
        process_a, _, _ = _seed_process_with_draft(db_session, tenant=tenant_a)
        tenant_b, _ = _seed_internal(db_session, email="userB@example.com")
        db_session.commit()

        headers = _login(client, "userB@example.com", "senha123")
        r = client.post(
            f"/api/v1/processes/{process_a.id}/classify",
            json={"demand_type": "car"},
            headers=headers,
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /admin/intake-feedback/stats
# ---------------------------------------------------------------------------

class TestStatsEndpoint:
    def test_unauthorized_returns_401(self, client: TestClient):
        r = client.get("/api/v1/admin/intake-feedback/stats")
        assert r.status_code == 401

    def test_empty_returns_zeros(self, client: TestClient, db_session):
        _seed_internal(db_session)
        db_session.commit()
        headers = _login(client, "consultor@example.com", "senha123")
        r = client.get("/api/v1/admin/intake-feedback/stats", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["total_classifications"] == 0
        assert body["total_corrections"] == 0
        assert body["accuracy_overall"] == 0.0
        assert body["accuracy_by_demand_type"] == {}
        assert body["top_corrections"] == []

    def test_last_log_per_process_drives_accuracy(self, client: TestClient, db_session):
        """3 processos:
        - p1: IA car, humano retificacao_car (correção)
        - p2: IA car, humano car (acerto)
        - p3: IA misto, humano retificacao_car → depois retificacao_car (último vence, IA divergente)

        accuracy_overall esperado = 1/3.
        """
        tenant, _ = _seed_internal(db_session)
        # p1
        p1, _, _ = _seed_process_with_draft(db_session, tenant=tenant, ai_demand_type="car")
        # p2
        p2, _, _ = _seed_process_with_draft(db_session, tenant=tenant, ai_demand_type="car")
        # p3
        p3, _, _ = _seed_process_with_draft(db_session, tenant=tenant, ai_demand_type="misto")
        db_session.commit()

        headers = _login(client, "consultor@example.com", "senha123")
        client.post(
            f"/api/v1/processes/{p1.id}/classify",
            json={"demand_type": "retificacao_car"},
            headers=headers,
        )
        client.post(
            f"/api/v1/processes/{p2.id}/classify",
            json={"demand_type": "car"},
            headers=headers,
        )
        # p3 reclassificado 2x — só o último conta nas stats
        client.post(
            f"/api/v1/processes/{p3.id}/classify",
            json={"demand_type": "car"},
            headers=headers,
        )
        client.post(
            f"/api/v1/processes/{p3.id}/classify",
            json={"demand_type": "retificacao_car"},
            headers=headers,
        )

        r = client.get("/api/v1/admin/intake-feedback/stats", headers=headers)
        assert r.status_code == 200
        body = r.json()

        assert body["total_classifications"] == 3
        assert body["total_corrections"] == 2  # p1 e p3 (último log de p3 ainda diverge)
        # O endpoint arredonda accuracy_overall a 4 casas decimais (intake_feedback.py:267).
        # Comparar contra 1/3 puro é precisão excessiva (0.3333333… ≠ 0.3333).
        assert body["accuracy_overall"] == round(1 / 3, 4)
        # accuracy_by_demand_type: car 1/1=1.0; retificacao_car 0/2=0.0
        assert body["accuracy_by_demand_type"]["car"] == 1.0
        assert body["accuracy_by_demand_type"]["retificacao_car"] == 0.0
        # top_corrections deve listar os 2 pares com seus counts
        pairs = {pair: count for pair, count in body["top_corrections"]}
        assert pairs.get("car -> retificacao_car") == 1
        assert pairs.get("misto -> retificacao_car") == 1

    def test_stats_tenant_scoped(self, client: TestClient, db_session):
        """Logs de outro tenant não vazam para a stats deste."""
        tenant_a, _ = _seed_internal(db_session, email="A@example.com")
        process_a, _, _ = _seed_process_with_draft(db_session, tenant=tenant_a, ai_demand_type="car")
        tenant_b, _ = _seed_internal(db_session, email="B@example.com")
        db_session.commit()

        # User A classifica seu processo
        headers_a = _login(client, "A@example.com", "senha123")
        client.post(
            f"/api/v1/processes/{process_a.id}/classify",
            json={"demand_type": "retificacao_car"},
            headers=headers_a,
        )

        # User B vê stats vazias do PRÓPRIO tenant
        headers_b = _login(client, "B@example.com", "senha123")
        r = client.get("/api/v1/admin/intake-feedback/stats", headers=headers_b)
        assert r.status_code == 200
        assert r.json()["total_classifications"] == 0

        # User A vê 1 classificação no próprio tenant
        r = client.get("/api/v1/admin/intake-feedback/stats", headers=headers_a)
        assert r.status_code == 200
        assert r.json()["total_classifications"] == 1
