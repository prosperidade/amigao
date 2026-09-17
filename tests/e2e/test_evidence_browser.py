"""Browser gate: built UI, real HTTP/login and committed PostgreSQL.

CI enables EVIDENCE_BROWSER_GATE after building frontend and installing Chromium.
The provider is controlled; Celery uses its eager transport, not a mocked API.
"""

import json
import os
import socket
import subprocess
import time
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

committed_case = case_fixture


@pytest.mark.skipif(os.getenv("EVIDENCE_BROWSER_GATE") != "1", reason="Dedicated CI browser gate")
def test_browser_review_reload_new_session_and_resume(committed_case, monkeypatch):
    factory, case = committed_case
    root = Path(__file__).resolve().parents[2]
    dist = root / "frontend" / "dist"
    assert (dist / "index.html").exists(), "Build frontend before the browser gate"
    received = []

    def controlled_provider(prompt, **kwargs):
        envelope = json.loads(prompt)
        received.append(envelope)
        source = envelope["sources"][0]
        output = {"objects": [{"id": "proposed", "version": 1, "kind": "conclusao", "origin": "diagnostico",
            "statement": "Hipótese controlada do navegador", "conclusion_class": "hipotese",
            "premises": [{"id": source["id"], "version": source["version"]}]}]}
        return AIResponse(content=json.dumps(output), model_used="controlled", provider="test",
                          tokens_in=1, tokens_out=1, cost_usd=0, duration_ms=1)

    monkeypatch.setattr("app.core.ai_gateway.complete", controlled_provider)
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
               "EVIDENCE_CASE": str(case["case"])}
        result = subprocess.run(["node", "scripts/evidence-browser-gate.mjs"], cwd=root / "frontend",
                                env=env, capture_output=True, text=True, encoding="utf-8", timeout=180)
        assert result.returncode == 0, result.stdout + result.stderr
        assert len(received) == 2
        assert "Hipótese controlada do navegador" not in json.dumps(received[1], ensure_ascii=False)
        with factory() as db:
            assert db.query(AIJob).filter(AIJob.tenant_id == case["tenant"], AIJob.entity_id == case["case"]).count() == 2
    finally:
        server.should_exit = True
        thread.join(timeout=15)
        sock.close()
        app.router.routes[:] = original_routes
