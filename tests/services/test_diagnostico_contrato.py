"""Diagnóstico por afirmação (ADR-080): prompt-base do contrato, resposta fora do contrato com
motivo nomeado, regras de admissão D1 a D6 (D7 é do schema)."""

from __future__ import annotations

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient
from tests.e2e.test_evidence_execution import committed_case as case_fixture
from tests.e2e.test_evidence_execution import login

from app.core.ai_gateway import AIResponse
from app.main import app
from app.models.ai_job import AIJob
from app.models.evidence import EvidenceVersion
from app.schemas.evidence import EvidenceObject, ExecutionEnvelope
from app.services import diagnostico_contrato as dc

committed_case = case_fixture

DOC = EvidenceObject(id="doc:1", version=1, kind="fonte_primaria", origin="documento")
CADASTRO = EvidenceObject(id="case:declarations", version=1, kind="fonte_primaria", origin="cadastro_legado")
OBS = EvidenceObject(id="obs:1", version=1, kind="observacao", origin="extrator",
                     attributes={"predicate": "ccir", "method_version": "1"})
INVENTARIO = EvidenceObject(id="case:material", version=1, kind="derivacao", origin="document_inventory",
                            premises=[{"id": "doc:1", "version": 1}], attributes={"method_version": "1"})


def _envelope() -> ExecutionEnvelope:
    return ExecutionEnvelope(tenant_id=1, case_id=1, reference_date=date(2026, 9, 24), snapshot_id="s",
                             snapshot_hash="h", sources=[DOC, CADASTRO], observations=[OBS],
                             derivations=[INVENTARIO])


def _afirmacao(**kw) -> EvidenceObject:
    base = {"id": "x", "version": 1, "kind": "conclusao", "origin": "diagnostico", "statement": "Afirmação",
            "conclusion_class": "hipotese", "premises": [{"id": "obs:1", "version": 1}],
            "attributes": {"certainty": "media"}}
    base.update(kw)
    return EvidenceObject.model_validate(base)


def _regras(*objs) -> list[str]:
    return [f.split(":")[0] for f in dc.recusas(list(objs), _envelope())]


def test_afirmacao_bem_sustentada_e_admitida():
    risco = _afirmacao(conclusion_class="risco", applicability="aplicavel", applicability_reason="CCIR ausente",
                       attributes={"certainty": "alta", "impact": "alto", "urgency": "alta"})
    lacuna = _afirmacao(conclusion_class="lacuna", premises=[{"id": "case:material", "version": 1}],
                        attributes={"certainty": "baixa"})
    assert dc.recusas([risco, lacuna, _afirmacao()], _envelope()) == []


def test_d1_sem_premissa():
    assert _regras(_afirmacao(premises=[])) == ["D1"]


def test_d2_certeza_obrigatoria_e_alta_exige_documento():
    assert _regras(_afirmacao(attributes={})) == ["D2"]
    assert _regras(_afirmacao(premises=[{"id": "case:material", "version": 1}],
                              attributes={"certainty": "alta"})) == ["D2"]


def test_d3_ausencia_nao_vira_risco_nem_fato():
    # Só o inventário (ausência nos autos) ou só a declaração do cadastro: lacuna, não passivo.
    for premissa in ("case:material", "case:declarations"):
        fato = _afirmacao(conclusion_class="fato_documental", premises=[{"id": premissa, "version": 1}])
        assert _regras(fato) == ["D3"]
    risco = _afirmacao(conclusion_class="risco", applicability="aplicavel", applicability_reason="r",
                       premises=[{"id": "case:material", "version": 1}], attributes={"certainty": "baixa", "impact": "alto"})
    assert _regras(risco) == ["D3"]


def test_d4_risco_exige_impacto_valido():
    risco = _afirmacao(conclusion_class="risco", applicability="aplicavel", applicability_reason="r")
    assert _regras(risco) == ["D4"]
    assert _regras(_afirmacao(attributes={"certainty": "media", "impact": "gravissimo"})) == ["D4"]


def test_d5_servico_exige_aplicabilidade():
    assert _regras(_afirmacao(conclusion_class="escopo_proposto")) == ["D5"]


def test_d6_urgencia_alta_so_em_risco_aplicavel():
    assert _regras(_afirmacao(attributes={"certainty": "media", "urgency": "alta"})) == ["D6"]
    assert _regras(_afirmacao(attributes={"certainty": "media", "urgency": "ontem"})) == ["D6"]


def test_d7_ausencia_verificada_sem_consulta_e_recusada_pelo_schema():
    with pytest.raises(ValueError, match="Ausência verificada"):
        _afirmacao(conclusion_class="fato_documental", knowledge={"state": "ausencia_verificada_no_escopo"})


def test_resposta_sem_objects_tem_motivo_nomeado():
    assert dc.faltou_objects({"objects": []}) is None
    msg = dc.faltou_objects({"situacao_geral": "x", "passivos_identificados": []})
    assert "faltou a lista 'objects'" in msg and "situacao_geral" in msg


def test_prompt_base_nao_pede_formato_legado():
    registro = dc.prompt_base_registro()
    assert registro["origin"] == "contrato_080" and registro["version"] == dc.CONTRATO_VERSAO
    assert "objects" in dc.PROMPT_BASE and "nada de situacao_geral" in dc.PROMPT_BASE


# ---------------------------------------------------------------------------
# Ponta a ponta pelo agendador (provedor controlado)
# ---------------------------------------------------------------------------

def _rodar(case, monkeypatch, conteudo: dict):
    enviados = []

    def responder(prompt, **kwargs):
        enviados.append(kwargs)
        return AIResponse(content=json.dumps(conteudo), model_used="controlled", provider="test",
                          tokens_in=1, tokens_out=1, cost_usd=0, duration_ms=1)
    monkeypatch.setattr("app.core.ai_gateway.complete", responder)
    with TestClient(app) as client:
        headers = login(client, case["email"])
        r = client.post("/api/v1/agents/run", headers=headers,
                        json={"agent_name": "diagnostico", "process_id": case["case"]})
        assert r.status_code == 200, r.text
        return r.json(), enviados


def test_formato_legado_falha_com_motivo_e_nao_grava(committed_case, monkeypatch):
    factory, case = committed_case
    result, enviados = _rodar(case, monkeypatch, {"situacao_geral": "legado", "passivos_identificados": []})
    assert result["status"] == "failed"
    assert "faltou a lista 'objects'" in result["steps"][0]["error"]
    # O prompt-base legado não vai no pedido; o do contrato vai, com teto de saída do diagnóstico.
    assert "Retorne APENAS JSON valido com: situacao_geral" not in enviados[0]["system"]
    assert dc.PROMPT_BASE in enviados[0]["system"]
    assert enviados[0]["max_tokens"] > 4096
    from app.core.config import settings
    assert enviados[0]["max_cost_override_usd"] == settings.AI_MAX_COST_PER_JOB_USD_DIAGNOSTICO
    with factory() as db:
        job = db.query(AIJob).filter(AIJob.tenant_id == case["tenant"]).one()
        assert job.input_payload["base_prompt"]["origin"] == "contrato_080"
        assert db.query(EvidenceVersion).filter(EvidenceVersion.job_id == job.id).count() == 0


def test_afirmacao_sem_suporte_recusa_a_execucao_inteira(committed_case, monkeypatch):
    factory, case = committed_case

    with factory() as db:
        from app.services.evidence import build_envelope
        env = build_envelope(db, case["tenant"], case["user"], case["case"])
        fonte = env.sources[0]
    risco_sem_impacto = {"id": "r", "version": 1, "kind": "conclusao", "origin": "diagnostico",
                         "statement": "Risco sem grau", "conclusion_class": "risco", "applicability": "aplicavel",
                         "applicability_reason": "teste", "premises": [{"id": fonte.id, "version": fonte.version}],
                         "attributes": {"certainty": "media"}}
    result, _ = _rodar(case, monkeypatch, {"objects": [risco_sem_impacto]})
    assert result["status"] == "failed"
    assert "ADR-080" in result["steps"][0]["error"] and "D4" in result["steps"][0]["error"]
    with factory() as db:
        assert db.query(EvidenceVersion).filter(EvidenceVersion.process_id == case["case"],
                                                EvidenceVersion.kind == "conclusao").count() == 0



def test_resposta_sem_sintaxe_ganha_uma_nova_chamada_e_fica_no_job(committed_case, monkeypatch):
    factory, case = committed_case
    respostas = iter(['{"objects": [{"id": "a", "limits": ["x"}]}', '{"objects": []}'])
    chamadas = []

    def responder(prompt, **kwargs):
        chamadas.append(1)
        return AIResponse(content=next(respostas), model_used="controlled", provider="test",
                          tokens_in=1, tokens_out=1, cost_usd=0, duration_ms=1)
    monkeypatch.setattr("app.core.ai_gateway.complete", responder)
    with TestClient(app) as client:
        headers = login(client, case["email"])
        r = client.post("/api/v1/agents/run", headers=headers,
                        json={"agent_name": "diagnostico", "process_id": case["case"]}).json()
    assert len(chamadas) == 2 and r["steps"][0]["status"] == "completed"
    with factory() as db:
        job = db.query(AIJob).filter(AIJob.tenant_id == case["tenant"]).one()
        assert "Expecting" in job.input_payload["resposta_sem_sintaxe"]["erro"]
        assert job.input_payload["resposta_sem_sintaxe"]["raw"].startswith('{"objects"')


def test_sintaxe_invalida_duas_vezes_falha_sem_terceira_chamada(committed_case, monkeypatch):
    factory, case = committed_case
    chamadas = []

    def responder(prompt, **kwargs):
        chamadas.append(1)
        return AIResponse(content='{"objects": [', model_used="controlled", provider="test",
                          tokens_in=1, tokens_out=1, cost_usd=0, duration_ms=1)
    monkeypatch.setattr("app.core.ai_gateway.complete", responder)
    with TestClient(app) as client:
        headers = login(client, case["email"])
        r = client.post("/api/v1/agents/run", headers=headers,
                        json={"agent_name": "diagnostico", "process_id": case["case"]}).json()
    assert len(chamadas) == 2 and r["status"] == "failed"



def test_modelo_nao_escolhe_especie_nem_identidade():
    objs = dc.para_objetos([{"id": "x9", "version": 7, "origin": "modelo", "kind": "conclusao",
                             "statement": "s", "conclusion_class": "lacuna"},
                            {"statement": "t", "conclusion_class": "hipotese"}])
    assert [(o.kind, o.origin, o.version) for o in objs] == [("conclusao", "diagnostico", 1)] * 2
    assert "kind" not in json.dumps(dc.SCHEMA_AFIRMACAO["properties"])


def test_classe_em_kind_e_erro_nomeado():
    with pytest.raises(ValueError, match="kind='risco'; a classe vai em conclusion_class"):
        dc.para_objetos([{"kind": "risco", "statement": "s"}])
