"""ADR-011 addendum / ADR-069 replaces raw chain_data and blanket non-blocking review.

Real committed PostgreSQL and login exercise dependency scheduling; only the LLM
response is controlled. Legacy non-blocking assertions were incompatible with the
approved v1.1 plan, rather than an infrastructure failure.
"""
import json

from fastapi.testclient import TestClient
from tests.e2e.test_evidence_execution import committed_case as case_fixture
from tests.e2e.test_evidence_execution import login

from app.core.ai_gateway import AIResponse
from app.main import app
from app.services.connected_agents import CHAINS

committed_case = case_fixture

def test_chain_keeps_independent_reading_and_stops_dependent_synthesis(committed_case):
    _, case = committed_case
    assert CHAINS["diagnostico_completo"] == ["extrator", "auditor_imovel", "legislacao", "diagnostico"]
    with TestClient(app) as client:
        headers = login(client, case["email"])
        response = client.post("/api/v1/agents/chain", headers=headers,
            json={"chain_name": "diagnostico_completo", "process_id": case["case"], "stop_on_review": False})
        assert response.status_code == 200, response.text
        result = response.json()
        statuses = {s["agent"]: s["status"] for s in result["steps"]}
        assert statuses == {"extrator": "failed", "auditor_imovel": "completed",
                            "legislacao": "capacidade_insuficiente", "diagnostico": "awaiting_review"}
        assert result["completed"] is False
        # Inc2 tem método; texto controlado sem espécie exige classificação antes do LLM.
        assert "Espécie não determinada" in result["steps"][0]["error"]


def test_review_gate_cannot_be_bypassed_and_commercial_chain_does_not_rerun_diagnosis(committed_case, monkeypatch):
    """ADR-074 §1: gerar_proposta no longer reruns the diagnosis nor waits for its review."""
    _, case = committed_case
    assert CHAINS["gerar_proposta"] == ["redator", "orcamento"]
    calls = []
    def respond(prompt, **kwargs):
        envelope = json.loads(prompt)
        calls.append(envelope)
        source = envelope["sources"][0]
        obj = {"id": "proposal", "version": 1, "kind": "conclusao", "origin": "diagnostico",
               "statement": "Controlled hypothesis", "conclusion_class": "hipotese",
               "premises": [{"id": source["id"], "version": source["version"]}]}
        return AIResponse(content=json.dumps({"objects": [obj]}), model_used="controlled", provider="test",
                          tokens_in=1, tokens_out=1, cost_usd=0, duration_ms=1)
    monkeypatch.setattr("app.core.ai_gateway.complete", respond)
    with TestClient(app) as client:
        headers = login(client, case["email"])
        body = {"chain_name": "diagnostico", "process_id": case["case"], "stop_on_review": False,
                "metadata": {"chain_data": {"diagnostico": "UNREVIEWED BYPASS TEXT"}}}
        result = client.post("/api/v1/agents/chain", headers=headers, json=body).json()
        assert result["status"] == "awaiting_review"
        assert "UNREVIEWED BYPASS TEXT" not in json.dumps(calls)
        ref = result["steps"][0]["outputs"][0]

        # Unreviewed diagnosis does not hold the commercial chain; the missing Rota does, by name.
        comercial = client.post("/api/v1/agents/chain", headers=headers,
                                json={"chain_name": "gerar_proposta", "process_id": case["case"]}).json()
        assert [s["status"] for s in comercial["steps"]] == ["failed", "awaiting_review"]
        assert "Rota validada ausente" in comercial["steps"][0]["error"]
        assert comercial["steps"][1]["waiting_for"] == ["redator"]
        assert len(calls) == 1  # the diagnosis is never rerun to price

        review = client.post(f"/api/v1/evidence/cases/{case['case']}/objects/{ref['id']}/review", headers=headers,
            json={"expected_version": 1, "expected_revision": 0, "action": "rejeitar", "justification": "Unsupported"})
        assert review.status_code == 200, review.text
        resumed = client.post(f"/api/v1/evidence/executions/{result['id']}/resume", headers=headers,
                             json={"expected_revision": result["revision"]}).json()
        assert resumed["completed"] is True
        assert len(calls) == 1  # completed step is never repeated
