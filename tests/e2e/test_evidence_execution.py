"""Real auth, committed PostgreSQL sessions and application ports; only LLM controlled.

This proves contract routing, not domain quality or the original Jobson documents.
"""

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db
from app.core.ai_gateway import AIResponse
from app.core.security import get_password_hash
from app.main import app
from app.models.ai_job import AIJob
from app.models.base import Base
from app.models.client import Client
from app.models.document import Document
from app.models.evidence import EvidenceReview, EvidenceVersion
from app.models.process import Process
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.evidence import EvidenceObject, ReviewRequest
from app.services.evidence import build_envelope, capture_snapshot, persist_object, review_object


@pytest.fixture
def committed_case(db_engine):
    suffix = uuid4().hex
    # Real commits must not leak fixtures into the transaction-based legacy suite.
    schema = f"evidence_test_{suffix}"
    with db_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated = create_engine(db_engine.url,
        connect_args={"options": f"-csearch_path={schema},public"},
        execution_options={"schema_translate_map": {None: schema}})
    Base.metadata.create_all(isolated)
    factory = sessionmaker(bind=isolated)
    with factory() as db:
        tenant = Tenant(name=f"Contract {suffix}")
        db.add(tenant)
        db.flush()
        user = User(tenant_id=tenant.id, email=f"{suffix}@example.com",
                    hashed_password=get_password_hash("ContractTest123!"), is_active=True)
        client = Client(tenant_id=tenant.id, full_name="Contract fixture")
        db.add_all([user, client])
        db.flush()
        prop = Property(tenant_id=tenant.id, client_id=client.id, name="Fixture", state="GO", has_embargo=False)
        db.add(prop)
        db.flush()
        case = Process(tenant_id=tenant.id, client_id=client.id, property_id=prop.id,
                       title="Contract fixture", process_type="car", macroetapa="diagnostico_tecnico")
        db.add(case)
        db.flush()
        doc = Document(tenant_id=tenant.id, process_id=case.id, original_file_name="fixture.txt",
                       filename="fixture.txt", storage_key=suffix, content_type="text/plain",
                       document_type="matricula", extracted_text="Documento controlado para verificar roteamento.",
                       checksum_sha256="a" * 64)
        db.add(doc)
        db.commit()
        data = {"tenant": tenant.id, "user": user.id, "case": case.id, "doc": doc.id, "email": user.email}
    def override_db():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    try:
        yield factory, data
    finally:
        app.dependency_overrides.clear()
        isolated.dispose()
        with db_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


def login(client, email):
    response = client.post("/api/v1/auth/login", data={"username": email, "password": "ContractTest123!"},
                           headers={"X-Auth-Profile": "internal"})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_authenticated_review_correction_reload_resume_and_context(committed_case, monkeypatch):
    factory, case = committed_case
    received = []
    empty_mode = False
    def llm(prompt, **kwargs):
        envelope = json.loads(prompt)
        received.append(envelope)
        source = envelope["sources"][0]
        output = {"objects": [{"id": "proposed", "version": 1, "kind": "conclusao", "origin": "diagnostico",
            "statement": "Conclusão controlada para revisão", "conclusion_class": "hipotese",
            "premises": [{"id": source["id"], "version": source["version"]}]}]}
        if empty_mode:
            output = {"objects": []}
        return AIResponse(content=json.dumps(output), model_used="controlled", provider="test",
                          tokens_in=1, tokens_out=1, cost_usd=0, duration_ms=1)
    monkeypatch.setattr("app.core.ai_gateway.complete", llm)
    with TestClient(app) as client:
        headers = login(client, case["email"])
        response = client.post("/api/v1/agents/run", headers=headers,
                               json={"agent_name": "diagnostico", "process_id": case["case"],
                                     "idempotency_key": "first", "metadata": {"uf": "SP", "tenant_id": 999}})
        assert response.status_code == 200, response.text
        run = response.json()
        assert len(received) == 1
        assert received[0]["case"]["uf"] == "GO"
        assert "has_embargo" not in json.dumps(received[0])
        evidence = client.get(f"/api/v1/evidence/cases/{case['case']}", headers=headers).json()
        conclusion = next(x for x in evidence["objects"] if x["object"]["kind"] == "conclusao")
        obj = conclusion["object"]
        url = f"/api/v1/evidence/cases/{case['case']}/objects/{obj['id']}/review"
        rejected = client.post(url, headers=headers, json={"expected_version": 1, "expected_revision": 0,
                              "action": "rejeitar", "justification": "Sem suporte suficiente"})
        assert rejected.status_code == 200, rejected.text
        second = client.post("/api/v1/agents/run", headers=headers,
                             json={"agent_name": "diagnostico", "process_id": case["case"], "metadata": {}})
        assert second.status_code == 200, second.text
        assert obj["statement"] not in json.dumps(received[-1], ensure_ascii=False)
        corrected = {**obj, "statement": "Hipótese corrigida pelo consultor"}
        correction = client.post(url, headers=headers, json={"expected_version": 1, "expected_revision": 1,
            "action": "corrigir", "justification": "Correção fundamentada", "correction": corrected})
        assert correction.status_code == 200, correction.text
        assert correction.json()["version"] == 2 and correction.json()["status"] == "pendente"
        stale = client.post(url, headers=headers, json={"expected_version": 1, "expected_revision": 1,
            "action": "aprovar", "justification": "Tela antiga"})
        assert stale.status_code == 409
    # New HTTP client + new login; persistence crosses both browser session and DB sessions.
    with TestClient(app) as client:
        headers = login(client, case["email"])
        reloaded = client.get(f"/api/v1/evidence/cases/{case['case']}", headers=headers)
        assert reloaded.status_code == 200
        history = [r for r in reloaded.json()["objects"] if r["object"]["id"] == obj["id"]]
        assert {r["object"]["version"] for r in history} == {1, 2}
        assert next(r for r in history if r["object"]["version"] == 1)["review"]["action"] == "corrigir"
        resumed = client.post(f"/api/v1/evidence/executions/{run['id']}/resume", headers=headers,
                              json={"expected_revision": run["revision"]})
        assert resumed.status_code == 200, resumed.text
        assert len(received) == 2
    with factory() as db:
        job = db.query(AIJob).filter(AIJob.id == run["steps"][0]["job_id"]).one()
        assert job.input_payload["manifest"]["applied"][0]["name"].startswith("diagnostico/")
        assert job.input_payload["system"] and job.input_payload["user"]
        reviews = db.query(EvidenceReview).filter(EvidenceReview.process_id == case["case"]).all()
        assert len(reviews) == 2 and all(r.author_id == case["user"] for r in reviews)
        assert db.query(EvidenceVersion).filter(EvidenceVersion.process_id == case["case"],
            EvidenceVersion.object_id == obj["id"]).count() == 2
    # Same authenticated scenario: both transports consume the same post-review
    # snapshot and actual reconciled skill. Empty output keeps that input stable.
    from app.core.celery_app import celery_app
    monkeypatch.setattr("app.db.session.SessionLocal", factory)
    for key, value in {"task_always_eager": True, "task_eager_propagates": True,
                       "task_store_eager_result": False, "broker_url": "memory://",
                       "result_backend": "cache+memory://"}.items():
        monkeypatch.setitem(celery_app.conf, key, value)
    empty_mode = True
    with TestClient(app) as client:
        headers = login(client, case["email"])
        body = {"agent_name": "diagnostico", "process_id": case["case"]}
        assert client.post("/api/v1/agents/run", headers=headers, json=body).status_code == 200
        assert client.post("/api/v1/agents/run-async", headers=headers, json=body).status_code == 202
    assert len(received) == 4 and received[-1] == received[-2]
    assert received[-1]["manifest"]["applied"][0]["version"] == "1.3.0"
    with factory() as db:
        jobs = db.query(AIJob).filter(AIJob.tenant_id == case["tenant"]).order_by(AIJob.id.desc()).limit(2).all()
        assert jobs[0].input_payload["context_hash"] == jobs[1].input_payload["context_hash"]


def test_sync_and_worker_share_context_and_skill_manifest(committed_case, monkeypatch):
    from types import SimpleNamespace

    from app.workers.agent_tasks import resume_connected_execution
    factory, case = committed_case
    inputs = []
    def response(prompt, **kwargs):
        inputs.append((json.loads(prompt), kwargs["system"]))
        return AIResponse(content='{"objects": []}', model_used="controlled", provider="test",
                          tokens_in=1, tokens_out=1, cost_usd=0, duration_ms=1)
    monkeypatch.setattr("app.core.ai_gateway.complete", response)
    monkeypatch.setattr("app.db.session.SessionLocal", factory)
    def dispatch(**kwargs):
        resume_connected_execution.apply(kwargs=kwargs, throw=True)
        return SimpleNamespace(id="eager-transport")
    monkeypatch.setattr(resume_connected_execution, "delay", dispatch)
    with TestClient(app) as client:
        headers = login(client, case["email"])
        body = {"agent_name": "diagnostico", "process_id": case["case"], "metadata": {"uf": "SP"}}
        sync = client.post("/api/v1/agents/run", headers=headers, json=body)
        asynchronous = client.post("/api/v1/agents/run-async", headers=headers, json=body)
        assert sync.status_code == 200 and asynchronous.status_code == 202
    assert len(inputs) == 2 and inputs[0] == inputs[1]
    assert inputs[0][0]["manifest"]["applied"][0]["version"] == "1.3.0"
    with factory() as db:
        jobs = db.query(AIJob).filter(AIJob.entity_id == case["case"], AIJob.tenant_id == case["tenant"]).all()
        assert len(jobs) == 2
        assert jobs[0].input_payload["context_hash"] == jobs[1].input_payload["context_hash"]


def test_invalidation_preserves_approval_and_only_affects_dependencies(committed_case):
    factory, case = committed_case
    with factory() as db:
        snapshot = capture_snapshot(db, case["tenant"], case["user"], case["case"])
        source = snapshot.content["sources"][0]
        observation = EvidenceObject(id="observation-test", version=1, kind="observacao", origin="extrator",
                                     premises=[source], attributes={"predicate": "area", "literal": 10})
        persist_object(db, case["tenant"], case["case"], observation)
        for identity, refs in [("dependent", [{"id": observation.id, "version": 1}]), ("independent", [source])]:
            conclusion = EvidenceObject(id=identity, version=1, kind="conclusao", origin="diagnostico",
                statement=identity, conclusion_class="hipotese", premises=refs)
            persist_object(db, case["tenant"], case["case"], conclusion)
            review_object(db, case["tenant"], case["user"], case["case"], identity,
                ReviewRequest(expected_version=1, expected_revision=0, action="aprovar", justification="Teste de premissas"))
        db.commit()
    with TestClient(app) as client:
        headers = login(client, case["email"])
        response = client.post(f"/api/v1/evidence/cases/{case['case']}/objects/observation-test/review", headers=headers,
            json={"expected_version": 1, "expected_revision": 0, "action": "corrigir", "justification": "Fonte corrigida",
                  "correction": {**observation.model_dump(mode="json"), "attributes": {"predicate": "area", "literal": 20}}})
        assert response.status_code == 200, response.text
        state = client.get(f"/api/v1/evidence/cases/{case['case']}", headers=headers).json()
        rows = {r["object"]["id"]: r for r in state["objects"]}
        assert rows["dependent"]["stale"] is True and rows["dependent"]["review"]["action"] == "aprovar"
        assert rows["independent"]["stale"] is False
        assert {o["id"] for o in state["envelope"]["conclusions"]} == {"independent"}
    with factory() as db:
        assert db.get(Process, case["case"]).macroetapa == "diagnostico_tecnico"


def test_capability_and_frozen_agents_visible(committed_case, monkeypatch):
    from app.core.celery_app import celery_app
    from app.workers.agent_tasks import acompanhamento_check_all, run_agent, vigia_all_tenants
    factory, case = committed_case
    monkeypatch.setattr("app.services.agent_capabilities.discover_skills", lambda: {})
    with TestClient(app) as client:
        headers = login(client, case["email"])
        response = client.post("/api/v1/agents/run", headers=headers,
            json={"agent_name": "diagnostico", "process_id": case["case"], "metadata": {}})
        assert response.status_code == 200 and response.json()["status"] == "capacidade_insuficiente"
        for name in ("atendimento", "financeiro", "marketing", "acompanhamento", "vigia"):
            response = client.post("/api/v1/agents/run-async", headers=headers,
                json={"agent_name": name, "process_id": case["case"], "metadata": {}})
            assert response.status_code == 409
            assert run_agent.apply(kwargs={"agent_name": name, "tenant_id": case["tenant"]}).result["status"] == "agente_desativado"
    assert vigia_all_tenants.apply().result["status"] == "agente_desativado"
    assert acompanhamento_check_all.apply().result["status"] == "agente_desativado"
    assert all("vigia" not in s["task"] and "acompanhamento" not in s["task"] for s in celery_app.conf.beat_schedule.values())


def test_cross_tenant_cannot_read_review_or_resume(committed_case):
    from app.services.connected_agents import start_execution
    factory, case = committed_case
    with factory() as db:
        execution = start_execution(db, case["tenant"], case["user"], case["case"], "diagnostico")
        execution_id = execution.id
        other = Tenant(name="Other isolated tenant")
        db.add(other)
        db.flush()
        email = f"{uuid4().hex}@example.com"
        db.add(User(tenant_id=other.id, email=email, hashed_password=get_password_hash("ContractTest123!"), is_active=True))
        db.commit()
    with TestClient(app) as client:
        headers = login(client, email)
        assert client.get(f"/api/v1/evidence/cases/{case['case']}", headers=headers).status_code == 404
        assert client.post(f"/api/v1/evidence/executions/{execution_id}/resume", headers=headers,
                           json={"expected_revision": 0}).status_code == 404
        assert client.post(f"/api/v1/evidence/cases/{case['case']}/objects/x/review", headers=headers,
            json={"expected_version": 1, "expected_revision": 0, "action": "aprovar", "justification": "Ataque"}).status_code == 404


def test_two_simultaneous_resumptions_do_not_duplicate_effects(committed_case, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from app.services.connected_agents import start_execution
    factory, case = committed_case
    entered, release = Event(), Event()
    calls = []
    def response(prompt, **kwargs):
        calls.append(prompt)
        entered.set()
        assert release.wait(15)
        return AIResponse(content='{"objects": []}', model_used="controlled", provider="test",
                          tokens_in=1, tokens_out=1, cost_usd=0, duration_ms=1)
    monkeypatch.setattr("app.core.ai_gateway.complete", response)
    with factory() as db:
        execution = start_execution(db, case["tenant"], case["user"], case["case"], "diagnostico")
        execution_id = execution.id
        db.commit()
    with TestClient(app) as client:
        headers = login(client, case["email"])
        url = f"/api/v1/evidence/executions/{execution_id}/resume"
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(client.post, url, headers=headers, json={"expected_revision": 0})
            assert entered.wait(15)
            try:
                second = client.post(url, headers=headers, json={"expected_revision": 0})
                assert second.status_code == 409, second.text
            finally:
                release.set()
            assert first.result().status_code == 200
    assert len(calls) == 1
    with factory() as db:
        assert db.query(AIJob).filter(AIJob.tenant_id == case["tenant"], AIJob.entity_id == case["case"]).count() == 1


def test_auditor_reassessment_never_replaces_human_acceptance(committed_case):
    from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
    factory, case = committed_case
    with factory() as db:
        row = ExtractedFieldStaging(tenant_id=case["tenant"], process_id=case["case"], document_id=case["doc"],
            source_doc_type="car", field_name="area_declarada_ha", field_value={"value": 10},
            status=ExtractedFieldStatus.aceito, decided_by_user_id=case["user"], decided_value={"value": 11})
        db.add(row)
        db.commit()
        row_id = row.id
    with TestClient(app) as client:
        headers = login(client, case["email"])
        for _ in range(2):
            response = client.post("/api/v1/agents/run", headers=headers,
                json={"agent_name": "auditor_imovel", "process_id": case["case"], "metadata": {}})
            assert response.status_code == 200, response.text
            assert response.json()["steps"][0]["status"] == "completed", response.text
    with factory() as db:
        row = db.get(ExtractedFieldStaging, row_id)
        assert row.status == ExtractedFieldStatus.aceito and row.decided_value == {"value": 11}
        assert row.decided_by_user_id == case["user"]
        jobs = db.query(AIJob).filter(AIJob.tenant_id == case["tenant"], AIJob.agent_name == "auditor_imovel").all()
        assert len(jobs) == 2
        assert jobs[0].result["objects"] and jobs[1].result["objects"]
        assert jobs[0].result["objects"][0]["id"] != jobs[1].result["objects"][0]["id"]


def test_rollback_between_review_and_resume_is_real(committed_case):
    factory, case = committed_case
    with factory() as db:
        snapshot = capture_snapshot(db, case["tenant"], case["user"], case["case"])
        obj = EvidenceObject(id="rollback-conclusion", version=1, kind="conclusao", origin="diagnostico",
            statement="Hipótese de teste", conclusion_class="hipotese", premises=[snapshot.content["sources"][0]])
        persist_object(db, case["tenant"], case["case"], obj)
        db.commit()
    with factory() as db:
        review_object(db, case["tenant"], case["user"], case["case"], obj.id,
            ReviewRequest(expected_version=1, expected_revision=0, action="aprovar", justification="Falhar antes do commit"))
        db.rollback()
    with factory() as db:
        assert db.query(EvidenceReview).filter(EvidenceReview.process_id == case["case"]).count() == 0
        envelope = build_envelope(db, case["tenant"], case["user"], case["case"])
        assert envelope.conclusions == []


def test_verified_absence_cannot_be_fabricated_by_provider(committed_case, monkeypatch):
    factory, case = committed_case
    def response(prompt, **kwargs):
        return AIResponse(content=json.dumps({"objects": [{"id": "fake", "version": 1,
            "kind": "conclusao", "origin": "diagnostico", "conclusion_class": "fato_documental",
            "statement": "Não há embargo", "knowledge": {"state": "ausencia_verificada_no_escopo"}}]}),
            model_used="controlled", provider="test", tokens_in=1, tokens_out=1, cost_usd=0, duration_ms=1)
    monkeypatch.setattr("app.core.ai_gateway.complete", response)
    with TestClient(app) as client:
        headers = login(client, case["email"])
        result = client.post("/api/v1/agents/run", headers=headers,
            json={"agent_name": "diagnostico", "process_id": case["case"]}).json()
        assert result["status"] == "failed"
    with factory() as db:
        assert db.query(EvidenceVersion).filter(EvidenceVersion.process_id == case["case"], EvidenceVersion.kind == "conclusao").count() == 0
        job = db.query(AIJob).filter(AIJob.tenant_id == case["tenant"]).one()
        assert job.raw_output and job.result["parse_error"]


def test_source_survives_archive_and_original_version_survives_reprocessing(committed_case):
    from datetime import UTC, datetime
    factory, case = committed_case
    with factory() as db:
        capture_snapshot(db, case["tenant"], case["user"], case["case"])
        db.commit()
        doc = db.get(Document, case["doc"])
        doc.extracted_text = "Texto substituído em reprocessamento"
        db.commit()
        capture_snapshot(db, case["tenant"], case["user"], case["case"])
        db.get(Process, case["case"]).deleted_at = datetime.now(UTC)
        doc.deleted_at = datetime.now(UTC)
        db.commit()
    with TestClient(app) as client:
        headers = login(client, case["email"])
        response = client.get(f"/api/v1/evidence/cases/{case['case']}/sources/document:{case['doc']}/versions/1", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["source"]["text"] == "Documento controlado para verificar roteamento."
        assert response.json()["object"]["attributes"]["original_hash"] == "a" * 64


def test_current_snapshot_keeps_corrected_observation_and_audit_chain(committed_case):
    from app.services.audit_hash import verify_audit_chain
    from app.services.connected_agents import resume_execution, start_execution
    factory, case = committed_case
    with factory() as db:
        execution = start_execution(db, case["tenant"], case["user"], case["case"], "extrator")
        old_snapshot = execution.snapshot_id
        source = capture_snapshot(db, case["tenant"], case["user"], case["case"]).content["sources"][0]
        obj = EvidenceObject(id="durable-observation", version=1, kind="observacao", origin="extrator",
                             premises=[source], attributes={"predicate": "area", "literal": 10})
        persist_object(db, case["tenant"], case["case"], obj)
        review_object(db, case["tenant"], case["user"], case["case"], obj.id,
            ReviewRequest(expected_version=1, expected_revision=0, action="corrigir", justification="Fonte corrigida",
                correction=obj.model_copy(update={"attributes": obj.attributes.model_copy(update={"literal": 20})})))
        db.commit()
        resume_execution(db, case["tenant"], case["user"], execution.id)
        assert execution.snapshot_id != old_snapshot
        envelope = build_envelope(db, case["tenant"], case["user"], case["case"], execution.snapshot_id)
        current = next(o for o in envelope.observations if o.id == obj.id)
        assert current.version == 2 and current.attributes.literal == 20
        assert verify_audit_chain(db, case["tenant"]) == []


def test_legacy_completed_job_is_never_an_approved_premise(committed_case):
    from app.models.ai_job import AIJobStatus, AIJobType
    factory, case = committed_case
    with factory() as db:
        db.add(AIJob(tenant_id=case["tenant"], created_by_user_id=case["user"], entity_type="process",
            entity_id=case["case"], agent_name="diagnostico", job_type=AIJobType.diagnostico_propriedade,
            status=AIJobStatus.completed, raw_output="LEGACY_UNREVIEWED_SENTINEL",
            result={"situacao_geral": "LEGACY_UNREVIEWED_SENTINEL", "requires_review": False}))
        db.commit()
        envelope = build_envelope(db, case["tenant"], case["user"], case["case"])
        assert envelope.conclusions == []
        assert "LEGACY_UNREVIEWED_SENTINEL" not in envelope.model_dump_json()


def test_verified_query_preserves_scope_and_is_invalidated_by_query_revision(committed_case):
    from datetime import UTC, datetime

    from fastapi import HTTPException
    factory, case = committed_case
    now = datetime.now(UTC)
    with factory() as db:
        query = EvidenceObject(id="query-test", version=1, kind="fonte_primaria", origin="consulta",
                               attributes={"literal": "Resposta controlada negativa no escopo"})
        record = {"status": "success", "scope": "fixture-scope", "identifiers": ["fixture-id"], "consulted_at": now.isoformat(), "response": []}
        persist_object(db, case["tenant"], case["case"], query, source_record=record)
        conclusion = EvidenceObject(id="verified-test", version=1, kind="conclusao", origin="diagnostico",
            statement="Ausência verificada no escopo sintético", conclusion_class="fato_documental",
            premises=[{"id": query.id, "version": 1}], knowledge={"state": "ausencia_verificada_no_escopo",
                "verification": {"source": {"id": query.id, "version": 1}, "preserved_response": {"id": query.id, "version": 1},
                                 "scope": record["scope"], "identifiers": record["identifiers"], "consulted_at": now}})
        persist_object(db, case["tenant"], case["case"], conclusion)
        review_object(db, case["tenant"], case["user"], case["case"], conclusion.id,
                      ReviewRequest(expected_version=1, expected_revision=0, action="aprovar", justification="Conferi o registro"))
        assert len(build_envelope(db, case["tenant"], case["user"], case["case"]).conclusions) == 1
        invalid_data = conclusion.model_dump(mode="json")
        invalid_data["id"] = "forged-scope"
        invalid_data["knowledge"]["verification"]["scope"] = "outside-preserved-scope"
        with pytest.raises(HTTPException, match="422"):
            persist_object(db, case["tenant"], case["case"], EvidenceObject.model_validate(invalid_data))
        persist_object(db, case["tenant"], case["case"], query.model_copy(update={"version": 2}), source_record=record)
        assert build_envelope(db, case["tenant"], case["user"], case["case"]).conclusions == []


def test_extrator_rejected_anchor_preserves_paid_response_and_independent_observation(committed_case, monkeypatch):
    """Controlled gateway response; invalid anchor must not erase the paid audit trail."""
    from app.core.ai_gateway import AIResponse
    from app.core.config import settings
    from app.models.ai_job import AIJob
    factory, case = committed_case
    with factory() as db:
        doc = db.get(Document, case["doc"])
        doc.document_type = "certidao_matricula"
        doc.extracted_text = "Controlled registry material. Valid area."
        db.commit()
    raw = json.dumps({"observacoes": [{"predicado": "area_documental_ha", "valor": 12,
                                      "trecho": "ANCHOR_NOT_IN_SOURCE"}, {"predicado": "area_documental_ha", "valor": 13, "trecho": "Valid area."}]})
    monkeypatch.setattr(settings, "AI_EXTRATOR_ALLOW_FALLBACK", False)
    monkeypatch.setattr(settings, "AI_EXTRATOR_MODEL", "gpt-5.6-luna")
    def gateway(*args, **kwargs):
        assert kwargs["allow_fallback"] is False
        assert kwargs["model"] == "gpt-5.6-luna"
        return AIResponse(content=raw, model_used="controlled", provider="test", tokens_in=17, tokens_out=11,
                          cost_usd=0.002, duration_ms=1)
    monkeypatch.setattr("app.core.ai_gateway.complete", gateway)
    with TestClient(app) as client:
        response = client.post("/api/v1/agents/run", headers=login(client, case["email"]),
            json={"agent_name": "extrator", "process_id": case["case"]})
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
    with factory() as db:
        job = db.query(AIJob).filter_by(tenant_id=case["tenant"], agent_name="extrator").one()
        # First call plus the repair round (the same controlled answer repairs nothing).
        assert (job.tokens_in, job.tokens_out, job.model_used) == (34, 22, "controlled")
        assert job.cost_usd == 0.004
        calls = json.loads(job.raw_output)
        assert calls[0]["raw"] == raw and calls[1]["label"].endswith(":reparo")
        assert db.query(EvidenceVersion).filter_by(tenant_id=case["tenant"], kind="observacao").count() == 1

    with factory() as db:
        report = db.query(EvidenceVersion).filter_by(tenant_id=case["tenant"],
            object_id=f"extracao:rejeicoes:{case['doc']}").one()
        normalized = report.content["attributes"]["normalized"]
        assert normalized["observacoes_preservadas"] == 1
        assert [(r["colecao"], r["indice"], r["motivo"]) for r in normalized["rejeicoes"]] == [
            ("observacoes", 0, "Trecho extraído não existe no texto versionado")]


def _controlled_extractions(monkeypatch, *responses):
    from app.core.config import settings
    pending = iter(responses)
    monkeypatch.setattr(settings, "AI_EXTRATOR_ALLOW_FALLBACK", False)
    monkeypatch.setattr(settings, "AI_EXTRATOR_MODEL", "gpt-5.6-luna")
    monkeypatch.setattr("app.core.ai_gateway.complete", lambda *args, **kwargs: AIResponse(
        content=json.dumps(next(pending)), model_used="controlled", provider="test",
        tokens_in=1, tokens_out=1, cost_usd=0.001, duration_ms=1))


def test_reextraction_supersedes_the_previous_version_except_decided_observations(committed_case, monkeypatch):
    """#258, ADR-070: a new extraction is a new version and the previous one is superseded.

    Decisions of the consultant (panel review, accepted projection) are not the
    machine's to supersede. Supersession is not a collection pendency.
    """
    from app.models.evidence import EvidenceInvalidation
    from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
    factory, case = committed_case
    with factory() as db:
        doc = db.get(Document, case["doc"])
        doc.document_type = "certidao_matricula"
        doc.extracted_text = "Registry. Area one. Area two. Area three. Area four."
        db.commit()

    def area(value, anchor):
        return {"predicado": "area_documental_ha", "valor": value, "trecho": anchor}
    _controlled_extractions(monkeypatch,
        {"observacoes": [area(1, "Area one."), area(2, "Area two."), area(3, "Area three."), area(4, "Area four.")]},
        {"observacoes": [area(1, "Area one."), {"predicado": "cabecalho", "valor": "r", "trecho": "Registry."}]})
    with TestClient(app) as client:
        headers = login(client, case["email"])

        def extract():
            return client.post("/api/v1/agents/run", headers=headers,
                               json={"agent_name": "extrator", "process_id": case["case"]}).json()["status"]
        assert extract() == "completed"
        with factory() as db:
            # Plain values: the rows expire with this session.
            first = {r.content["attributes"]["literal"]: (r.id, r.object_id) for r in db.query(EvidenceVersion).filter_by(
                tenant_id=case["tenant"], kind="observacao")}
            review_object(db, case["tenant"], case["user"], case["case"], first["Area two."][1],
                ReviewRequest(expected_version=1, expected_revision=0, action="aprovar", justification="Conferido"))
            accepted = db.query(ExtractedFieldStaging).filter_by(observacao_ref=first["Area three."][0]).one()
            accepted.status, accepted.decided_by_user_id = ExtractedFieldStatus.aceito, case["user"]
            db.commit()
        assert extract() == "completed"
        with factory() as db:
            reasons = {i.evidence_id: i.reason for i in db.query(EvidenceInvalidation).filter_by(tenant_id=case["tenant"])}
            superseded = {literal for literal, (row_id, _) in first.items() if "superada_por" in reasons.get(row_id, {})}
            assert superseded == {"Area four."}
            assert first["Area one."][0] not in reasons  # produced again by the new version
            report = db.query(EvidenceVersion).filter_by(tenant_id=case["tenant"],
                object_id=f"extracao:rejeicoes:{case['doc']}").order_by(EvidenceVersion.version.desc()).first()
            assert reasons[first["Area four."][0]]["superada_por"] == {"id": report.object_id, "version": report.version}
            assert [r["id"] for r in report.content["attributes"]["normalized"]["superadas"]] == [first["Area four."][1]]
            assert db.query(ExtractedFieldStaging).filter_by(observacao_ref=first["Area four."][0]).count() == 0
            assert db.query(ExtractedFieldStaging).filter_by(observacao_ref=first["Area three."][0]).one().status == \
                ExtractedFieldStatus.aceito
        state = client.get(f"/api/v1/evidence/cases/{case['case']}", headers=headers).json()
        rows = {r["object"]["attributes"]["literal"]: r for r in state["objects"] if r["object"]["kind"] == "observacao"}
        assert rows["Area four."]["superseded"] is True and rows["Area four."]["stale"] is True
        assert rows["Area two."]["superseded"] is False and rows["Area two."]["stale"] is False
        assert "Area four." not in {o["attributes"]["literal"] for o in state["envelope"]["observations"]}
        # The first extraction also versions the source (documento_versao), which is a
        # pendency of its own; supersession must not be one.
        client.post(f"/api/v1/evidence/cases/{case['case']}/return-to-collection", headers=headers)
    with factory() as db:
        from app.models.evidence import RetornoColeta
        returned = {r.invalidacao_id for r in db.query(RetornoColeta).filter_by(tenant_id=case["tenant"])}
        superseding = {i.id for i in db.query(EvidenceInvalidation).filter_by(tenant_id=case["tenant"])
                       if "superada_por" in i.reason}
        assert superseding and not returned & superseding


def test_field_without_support_in_its_anchor_is_persisted_empty_with_reason(committed_case, monkeypatch):
    """André, 21/09/2026: the observation enters by its anchor; the unsupported field stays empty."""
    factory, case = committed_case
    with factory() as db:
        doc = db.get(Document, case["doc"])
        doc.document_type = "certidao_matricula"
        doc.extracted_text = "Registry. Seller Ana sells the land."
        db.commit()
    _controlled_extractions(monkeypatch, {"partes": [{"chave": "a", "nome": "Ana", "natureza": "pf",
        "identificador": "123.456.789-00", "tipo_identificador": "cpf", "trecho": "Seller Ana"}]})
    with TestClient(app) as client:
        headers = login(client, case["email"])
        assert client.post("/api/v1/agents/run", headers=headers,
                           json={"agent_name": "extrator", "process_id": case["case"]}).json()["status"] == "completed"
        documents = client.get(f"/api/v1/evidence/cases/{case['case']}/documents", headers=headers).json()
    assert documents[0]["rejeicoes"] == []
    assert [(c["colecao"], c["campo"], c["conhecimento"]) for c in documents[0]["campos_sem_suporte"]] == [
        ("partes", "identificador", "nao_determinado")]
    with factory() as db:
        party = db.query(EvidenceVersion).filter_by(tenant_id=case["tenant"], kind="observacao").one()
        normalized = party.content["attributes"]["normalized"]
        assert normalized["identificador"] is None and normalized["tipo_identificador"] is None
        assert normalized["campos_sem_suporte"][0]["motivo"] == "Identificador ausente do trecho da parte"
        assert party.content["knowledge"]["state"] == "nao_determinado"


def test_repair_round_recovers_a_rejected_observation_and_records_it(committed_case, monkeypatch):
    """André, 21/09/2026: the rejected item returns once with its reason; the result is audited."""
    from app.models.ai_job import AIJob
    factory, case = committed_case
    with factory() as db:
        doc = db.get(Document, case["doc"])
        doc.document_type = "certidao_matricula"
        doc.extracted_text = "Registry. Area one. Area two."
        db.commit()
    bad = {"predicado": "area_documental_ha", "valor": 2, "trecho": "Area 2 (rewritten)"}
    _controlled_extractions(monkeypatch,
        {"observacoes": [{"predicado": "area_documental_ha", "valor": 1, "trecho": "Area one."}, bad]},
        {"reparos": [{"colecao": "observacoes", "indice": 1, "item": {**bad, "trecho": "Area two."}}]})
    with TestClient(app) as client:
        headers = login(client, case["email"])
        assert client.post("/api/v1/agents/run", headers=headers,
                           json={"agent_name": "extrator", "process_id": case["case"]}).json()["status"] == "completed"
    with factory() as db:
        literals = {r.content["attributes"]["literal"] for r in db.query(EvidenceVersion).filter_by(
            tenant_id=case["tenant"], kind="observacao")}
        assert literals == {"Area one.", "Area two."}
        report = db.query(EvidenceVersion).filter_by(tenant_id=case["tenant"],
            object_id=f"extracao:rejeicoes:{case['doc']}").one().content["attributes"]["normalized"]
        assert report["rejeicoes"] == []
        assert [(r["colecao"], r["indice"], r["resultado"]) for r in report["reparos"]] == [("observacoes", 1, "aceito")]
        calls = json.loads(db.query(AIJob).filter_by(tenant_id=case["tenant"], agent_name="extrator").one().raw_output)
        assert [c["label"].rsplit(":", 1)[-1] for c in calls] == [calls[0]["label"].rsplit(":", 1)[-1], "reparo"]

def test_process_reference_is_persisted_and_the_conference_shows_every_anchor(committed_case, monkeypatch):
    """André, 21/09/2026: process number as its own observation; document and observations side by side."""
    from app.models.entrada_semantica import Espolio
    factory, case = committed_case
    with factory() as db:
        doc = db.get(Document, case["doc"])
        doc.document_type = "contrato"
        doc.extracted_text = "Contrato de prestacao de servicos. Contratante: Espolio de J. Inventario 111-22.2022. J faleceu."
        db.commit()
    _controlled_extractions(monkeypatch, {
        "partes": [{"chave": "j", "nome": "J", "natureza": "pf", "trecho": "J faleceu"},
                   {"chave": "e", "nome": "Espolio de J", "natureza": "espolio", "falecido_chave": "j",
                    "trecho": "Espolio de J"}],
        "contratos": [{"contratante": ["e"], "objeto": "servico", "trecho": "Contrato de prestacao de servicos"}],
        "referencias_processo": [{"numero": "111-22.2022", "natureza": "inventario", "sujeito": "e",
                                  "trecho": "Inventario 111-22.2022"}]})
    with TestClient(app) as client:
        headers = login(client, case["email"])
        assert client.post("/api/v1/agents/run", headers=headers,
                           json={"agent_name": "extrator", "process_id": case["case"]}).json()["status"] == "completed"
        base = f"/api/v1/evidence/cases/{case['case']}/documents"
        conference = client.get(f"{base}/{case['doc']}/conferencia", headers=headers).json()
        assert client.get(f"{base}/{case['doc'] + 999}/conferencia", headers=headers).status_code == 404
    text = conference["texto"]
    assert {o["tipo"] for o in conference["observacoes"]} == {"parte", "contrato", "referencia_processo"}
    for observation in conference["observacoes"]:
        assert text[observation["inicio"]:observation["fim"]] == observation["trecho"]
    reference = next(o for o in conference["observacoes"] if o["tipo"] == "referencia_processo")
    assert reference["predicado"] == "referencia_processo" and reference["conteudo"]["numero"] == "111-22.2022"
    with factory() as db:
        assert [e.inventario for e in db.query(Espolio).filter_by(tenant_id=case["tenant"])] == ["111-22.2022"]

def test_case_evidence_queries_do_not_grow_with_observations(committed_case):
    """Real extractions persist ~200 observations; one review query per object took seconds."""
    from sqlalchemy import event
    factory, case = committed_case
    engine = factory.kw["bind"]

    def queries_for(total):
        with factory() as db:
            source = capture_snapshot(db, case["tenant"], case["user"], case["case"]).content["sources"][0]
            present = db.query(EvidenceVersion).filter_by(tenant_id=case["tenant"], kind="observacao").count()
            for i in range(present, total):
                obj = EvidenceObject(id=f"scale-{i}", version=1, kind="observacao", origin="extrator",
                                     premises=[source], attributes={"predicate": "area", "literal": i})
                persist_object(db, case["tenant"], case["case"], obj)
                review_object(db, case["tenant"], case["user"], case["case"], obj.id,
                    ReviewRequest(expected_version=1, expected_revision=0, action="aprovar", justification="Escala"))
            db.commit()
        with TestClient(app) as client:
            headers = login(client, case["email"])
            client.get(f"/api/v1/evidence/cases/{case['case']}", headers=headers)  # snapshot settles
            statements = []
            def count(*_args):
                statements.append(1)
            event.listen(engine, "before_cursor_execute", count)
            try:
                response = client.get(f"/api/v1/evidence/cases/{case['case']}", headers=headers)
            finally:
                event.remove(engine, "before_cursor_execute", count)
            assert response.status_code == 200
            assert len([r for r in response.json()["objects"] if r["review"]]) == total
            return len(statements)

    assert queries_for(2) == queries_for(22)


def test_citation_gate_recognizes_short_forms_and_every_norm_of_the_source(committed_case):
    """Dívida #243, no caminho ativo: persist_object deixava passar forma que a regex não
    reconhecia e recusava quem citava uma norma que não fosse a primeira da fonte."""
    from fastapi import HTTPException

    factory, case = committed_case
    with factory() as db:
        db.get(Document, case["doc"]).extracted_text = (
            "LEI Nº 12.651, DE 25 DE MAIO DE 2012, regulamentada pelo Decreto 6.514/2008. "
            "LEI COMPLEMENTAR Nº 140, DE 8 DE DEZEMBRO DE 2011. Resolução CONAMA nº 237, "
            "de 19 de dezembro de 1997. LEI Nº 18.104, DE 18 DE JULHO DE 2013.")
        db.flush()
        source = capture_snapshot(db, case["tenant"], case["user"], case["case"]).content["sources"][0]

        def conclusion(identity, statement):
            return EvidenceObject(id=identity, version=1, kind="conclusao", origin="diagnostico",
                statement=statement, conclusion_class="hipotese", premises=[source], norms=[source])

        persist_object(db, case["tenant"], case["case"], conclusion(
            "short-forms", "Aplicam-se a LC 140/2011, a Res. CONAMA 237/1997 e a Lei GO 18.104/2013."))
        persist_object(db, case["tenant"], case["case"], conclusion(
            "not-the-first-norm", "Nos termos da Lei 12.651/2012 e do Decreto 6.514/2008."))
        with pytest.raises(HTTPException) as orphan:
            persist_object(db, case["tenant"], case["case"], conclusion("orphan-short-form", "Conforme a LC 999/2011."))
        assert orphan.value.status_code == 422
        stored = {row.object_id for row in db.query(EvidenceVersion).filter(
            EvidenceVersion.process_id == case["case"], EvidenceVersion.kind == "conclusao")}
        assert stored == {"short-forms", "not-the-first-norm"}
