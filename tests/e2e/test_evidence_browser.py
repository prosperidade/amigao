"""Browser gate: built UI, real HTTP/login and committed PostgreSQL.

CI enables EVIDENCE_BROWSER_GATE after building frontend and installing Chromium.
The provider is controlled; Celery uses its eager transport, not a mocked API.
"""

import json
import os
import socket
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from threading import Thread

import pytest
import uvicorn
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from tests.e2e.test_evidence_execution import committed_case as case_fixture

from app.core.ai_gateway import AIResponse
from app.core.celery_app import celery_app
from app.main import app
from app.models.ai_job import AIJob
from app.models.evidence import EvidenceReview, EvidenceVersion
from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
from app.schemas.evidence import canonical_hash

committed_case = case_fixture


@pytest.mark.skipif(os.getenv("EVIDENCE_BROWSER_GATE") != "1", reason="Dedicated CI browser gate")
def test_incremento1_gate_nove_provas_no_mesmo_percurso(committed_case, monkeypatch):
    factory, case = committed_case
    root = Path(__file__).resolve().parents[2]
    dist = root / "frontend" / "dist"
    assert (dist / "index.html").exists(), "Build frontend before the browser gate"
    received = []
    missing_once = False
    missing_injections = []
    from app.services import agent_capabilities
    real_discovery = agent_capabilities.discover_skills
    skill_name = "diagnostico/situacao_ambiental_imovel_rural"

    def inject_missing_skill_once():
        nonlocal missing_once
        catalog = real_discovery()
        if missing_once:
            missing_once = False
            missing_injections.append(skill_name)
            return {name: skill for name, skill in catalog.items() if name != skill_name}
        return catalog

    # Only raw observations are fixtures; acceptance is performed via authenticated HTTP.
    with factory() as db:
        area = ExtractedFieldStaging(tenant_id=case["tenant"], process_id=case["case"], document_id=case["doc"],
            source_doc_type="car", field_name="area_declarada_ha", field_value={"value": 10},
            status=ExtractedFieldStatus.pendente)
        name = ExtractedFieldStaging(tenant_id=case["tenant"], process_id=case["case"], document_id=case["doc"],
            source_doc_type="car", field_name="denominacao", field_value={"value": "Fazenda Gate"},
            status=ExtractedFieldStatus.pendente)
        db.add_all([area, name])
        db.commit()
        staging_id = area.id

    def controlled_provider(prompt, **kwargs):
        nonlocal missing_once
        envelope = json.loads(prompt)
        received.append({"context": envelope, "system": kwargs["system"]})
        if len(received) == 1:
            observation = next(o for o in envelope["observations"] if o["id"] == f"staging:{staging_id}")
            approved = envelope["conclusions"][0]
            output = {"objects": [{"id": "proposed", "version": 1, "kind": "conclusao", "origin": "diagnostico",
                "statement": "GATE_DIAGNOSTICO_PROPOSTO", "conclusion_class": "hipotese",
                "premises": [{"id": o["id"], "version": o["version"]} for o in (observation, approved)]}]}
        elif len(received) in (2, 3):
            output = {"objects": []}  # keep evidence unchanged for transport equivalence
            missing_once = len(received) == 3
        else:
            assert len(received) == 4, "Resumption duplicated a provider effect"
            output = {"objects": [{"id": "invalid", "version": 1, "kind": "conclusao", "origin": "diagnostico",
                "statement": "GATE_AUSENCIA_SEM_VERIFICACAO", "conclusion_class": "fato_documental",
                "premises": [{"id": envelope["sources"][0]["id"], "version": envelope["sources"][0]["version"]}],
                "knowledge": {"state": "ausencia_verificada_no_escopo"}}]}
        return AIResponse(content=json.dumps(output), model_used="controlled", provider="test",
                          tokens_in=1, tokens_out=1, cost_usd=0, duration_ms=1)

    monkeypatch.setattr("app.core.ai_gateway.complete", controlled_provider)
    monkeypatch.setattr(agent_capabilities, "discover_skills", inject_missing_skill_once)
    monkeypatch.setattr("app.db.session.SessionLocal", factory)
    for key, value in {"task_always_eager": True, "task_eager_propagates": True,
                       "task_store_eager_result": False, "broker_url": "memory://",
                       "result_backend": "cache+memory://"}.items():
        monkeypatch.setitem(celery_app.conf, key, value)
    original_routes = list(app.router.routes)

    def index():
        return FileResponse(dist / "index.html")

    app.mount("/assets", StaticFiles(directory=dist / "assets"))
    for route in ("/login", "/dashboard", "/processes/{process_id}"):
        app.add_api_route(route, index, include_in_schema=False)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
    thread = Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 15
        while not server.started and time.monotonic() < deadline:
            time.sleep(.1)
        assert server.started
        env = {**os.environ, "EVIDENCE_URL": f"http://127.0.0.1:{port}", "EVIDENCE_EMAIL": case["email"],
               "EVIDENCE_CASE": str(case["case"]), "EVIDENCE_STAGING": str(staging_id)}
        result = subprocess.run(["node", "scripts/increment1-unified-gate.mjs"], cwd=root / "frontend",
                                env=env, capture_output=True, text=True, encoding="utf-8", timeout=240)
        assert result.returncode == 0, result.stdout + result.stderr
        receipt = json.loads(next(line.removeprefix("GATE_RECEIPT=") for line in result.stdout.splitlines()
                                  if line.startswith("GATE_RECEIPT=")))
        assert len(received) == 4
        # G1: actual diagnostic input, including a positive control that approved auditor output DID enter.
        effective = received[0]["context"]
        rejected = receipt["rejected"]
        assert rejected["statement"] not in json.dumps(effective, ensure_ascii=False)
        assert rejected["id"] not in {o["id"] for o in effective["conclusions"]}
        for derivation in effective["derivations"]:
            if derivation["attributes"]["method"] == "inconsistency_matrix":
                assert not {"acao_recomendada", "situacao", "destino"} & derivation["attributes"]["normalized"].keys()
        assert not any(p["id"] == rejected["id"] for o in effective["conclusions"] for p in o["premises"])
        assert set(receipt["accepted_auditor"]) <= {o["id"] for o in effective["conclusions"]}
        # G5: not merely similar metadata: full envelopes AND composed system prompts are equal.
        assert received[1] == received[2]
        assert missing_injections == [skill_name]
        with factory() as db:
            jobs = db.query(AIJob).filter(AIJob.tenant_id == case["tenant"], AIJob.entity_id == case["case"]).all()
            assert len(jobs) == 9
            by_execution = {job.chain_trace_id: job for job in jobs if job.agent_name != "redator"}
            # G4: both resumptions retain exactly ONE original diagnostic job and its effects.
            original_job = by_execution[receipt["resume"]["before"]["id"]]
            assert sum(job.chain_trace_id == original_job.chain_trace_id and job.agent_name == "diagnostico" for job in jobs) == 1
            assert original_job.id == receipt["resume"]["before"]["steps"][0]["job_id"]
            # Retrying an unavailable next responsibility records failed attempts,
            # but never duplicates the completed diagnostic or creates editorial output.
            editorial_attempts = [job for job in jobs if job.agent_name == "redator"]
            assert len(editorial_attempts) == 2
            assert all(job.result["status"] == "capacidade_insuficiente" for job in editorial_attempts)
            assert db.query(EvidenceVersion).filter(EvidenceVersion.job_id.in_([job.id for job in editorial_attempts])).count() == 0
            versions = db.query(EvidenceVersion).filter(EvidenceVersion.object_id == receipt["original"]["id"]).all()
            assert len(versions) == 2 and {v.version for v in versions} == {1, 2}
            assert next(v for v in versions if v.version == 1).content == receipt["original"]
            sync = by_execution[receipt["transports"]["sync"]]
            asynchronous = by_execution[receipt["transports"]["async"]]
            assert sync.input_payload == asynchronous.input_payload
            applied = sync.input_payload["manifest"]["applied"]
            assert len(applied) == 1 and applied[0]["name"] == skill_name and applied[0]["version"] == "1.3.0"
            assert applied[0]["content"] in sync.input_payload["system"]
            assert applied[0]["hash"] == canonical_hash(applied[0]["content"])
            # G6: missing mandatory DIAGNOSTIC skill, visible in UI, no provider invocation.
            missing = by_execution[receipt["missing"]]
            assert missing.input_payload["manifest"]["missing"] == [{"skill": skill_name, "reason": "ausente_ou_invalida"}]
            assert missing.input_payload["manifest"]["applied"] == [] and not missing.raw_output
            # G7: invalid response is retained for audit but no evidence is persisted from it.
            invalid = by_execution[receipt["invalid_absence"]]
            assert "GATE_AUSENCIA_SEM_VERIFICACAO" in invalid.raw_output and invalid.result["parse_error"]
            assert db.query(EvidenceVersion).filter(EvidenceVersion.job_id == invalid.id).count() == 0
            # G8: the original approval row remains, with original premise versions and author.
            version_two = next(v for v in versions if v.version == 2)
            approval = db.query(EvidenceReview).filter(EvidenceReview.evidence_id == version_two.id,
                                                       EvidenceReview.action == "aprovar").one()
            assert approval.author_id == case["user"] and approval.premises == version_two.content["premises"]
            assert receipt["approval_before"]["review"] == receipt["approval_after"]["review"]
            # G9: staging decision remains human-owned after the second real auditor run.
            preserved = db.get(ExtractedFieldStaging, staging_id)
            assert preserved.status == ExtractedFieldStatus.aceito and preserved.decided_value == {"value": 11}
            assert preserved.decided_by_user_id == case["user"]
            manifest_proof = {"sync_job": sync.id, "async_job": asynchronous.id,
                "context_hash": sync.input_payload["context_hash"], "system_hash": sync.input_payload["system_hash"],
                "skill": {key: applied[0][key] for key in ("name", "version", "hash")}}
            absence_proof = {"job": invalid.id, "parse_error": invalid.result["parse_error"], "persisted_objects": 0}
        artifact = {"test": "test_incremento1_gate_nove_provas_no_mesmo_percurso",
            "at": datetime.now(UTC).isoformat(), "sha": os.getenv("GATE_HEAD_SHA", "local"),
            "boundaries": {"llm": "controlled gateway response", "celery": "eager, memory transport; no remote broker",
                           "database": "real PostgreSQL, isolated schema, real commits",
                           "fault_injection": "mandatory diagnostic skill removed for one execution",
                           "ui_and_http": "DOM login/reject/correct/reload/new session/approve/missing; other steps authenticated HTTP"},
            "receipt": receipt, "manifest": manifest_proof, "absence": absence_proof,
            "diagnostic_received_conclusions": [o["id"] for o in effective["conclusions"]],
            "proved": [f"G{i}" for i in range(1, 10)]}
        path = root / "artifacts" / "gate-incremento1.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        print("GATE_INCREMENTO1: G1 G2 G3 G4 G5 G6 G7 G8 G9 PASS; artifacts/gate-incremento1.json")
    finally:
        server.should_exit = True
        thread.join(timeout=15)
        sock.close()
        app.router.routes[:] = original_routes
