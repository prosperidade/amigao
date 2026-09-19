# ADR-069: isolated legacy algorithm/projection tests; authenticated execution is tested in tests/e2e/test_evidence_execution.py.
"""Inc2 / ADR-064: toda chamada do parser unico permanece auditavel no AIJob.
A chamada de preview foi removida; tokens, custo e bruto continuam obrigatorios."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.agents.base import AgentContext, AgentRegistry
from app.core.ai_gateway import AIResponse
from app.models.ai_job import AIJob
from app.models.client import Client
from app.models.document import Document, OcrStatus
from app.models.process import Process, ProcessStatus
from app.models.tenant import Tenant
from app.models.user import User

_TEXTO = (
    "CERTIDÃO DE MATRÍCULA Nº 3.673 — Registro de Imóveis de Alto Paraíso de Goiás. "
    "Na Receita Federal sob o nº 6.816.752-0. Área de 212,3553ha."
)

_RESP_PREVIEW = AIResponse(
    content='{"numero_matricula": "3.673"}', model_used="gpt-4o-mini",
    tokens_in=1000, tokens_out=40, cost_usd=0.0002, duration_ms=800,
    provider="gpt", finish_reason="stop",
)
_RESP_STAGING = AIResponse(
    content='{"numero_matricula": "3.673", "nirf_cib": "6.816.752-0", '
            '"confidence": {"numero_matricula": "high"}}',
    model_used="gpt-4o-mini", tokens_in=1100, tokens_out=60, cost_usd=0.0003,
    duration_ms=900, provider="gpt", finish_reason="stop",
)


@pytest.fixture
def seeded(db_session):
    tenant = Tenant(name="T-auditavel")
    db_session.add(tenant)
    db_session.flush()
    user = User(tenant_id=tenant.id, email="a.auditavel@example.com",
                hashed_password="x", full_name="A")
    db_session.add(user)
    client = Client(tenant_id=tenant.id, full_name="ELODI", email="e.aud@example.com")
    db_session.add(client)
    db_session.flush()
    process = Process(tenant_id=tenant.id, client_id=client.id, title="P",
                      process_type="prad", status=ProcessStatus.triagem)
    db_session.add(process)
    db_session.flush()
    doc = Document(
        tenant_id=tenant.id, process_id=process.id, client_id=client.id,
        original_file_name="m3673.pdf", filename="m3673.pdf",
        content_type="application/pdf", storage_key=f"tenant-{tenant.id}/m.pdf",
        document_type="matricula", ocr_status=OcrStatus.done, extracted_text=_TEXTO,
    )
    db_session.add(doc)
    db_session.flush()
    return tenant, user, process, doc


def test_ai_job_do_extrator_guarda_modelo_tokens_custo_e_bruto(seeded, db_session):
    # Inc2: uma chamada gera observação e projeção; preview não chama LLM.
    from hashlib import sha256

    from app.models.evidence import EvidenceVersion
    tenant, user, process, doc = seeded
    doc.checksum_sha256 = sha256(b"controlled original PDF bytes").hexdigest()
    payload = {"observacoes": [{"predicado": "area_documental_ha", "valor": 212.3553,
        "unidade": "ha", "trecho": "Área de 212,3553ha."}]}
    response = AIResponse(content=json.dumps(payload), model_used="controlled-model",
        provider="test", tokens_in=1100, tokens_out=60, cost_usd=0.0003, duration_ms=900)
    ctx = AgentContext(tenant_id=tenant.id, user_id=user.id, process_id=process.id,
        session=db_session, metadata={"document_id": doc.id})
    with patch("app.core.ai_gateway.complete", return_value=response) as gateway:
        result = AgentRegistry.create("extrator", ctx)._run_legacy_unconnected()
    assert result.success, result.error
    assert gateway.call_count == 1
    job = db_session.query(AIJob).filter_by(tenant_id=tenant.id).order_by(AIJob.id.desc()).first()
    assert job.model_used == response.model_used and job.provider == response.provider
    assert (job.tokens_in, job.tokens_out) == (1100, 60)
    assert job.cost_usd == pytest.approx(0.0003)
    blocks = json.loads(job.raw_output)
    assert len(blocks) == 1 and blocks[0]["rotulo"].startswith(f"doc{doc.id}:")
    assert json.loads(blocks[0]["content"]) == payload
    assert db_session.query(EvidenceVersion).filter_by(tenant_id=tenant.id, kind="observacao").count() == 1
    assert "extracted_fields" not in result.data


def test_agregacao_respeita_o_tamanho_das_colunas(db_session):
    """`model_used` é String(100) e `provider` String(50) — o corte é do schema."""
    from app.agents.extrator import ExtratorAgent

    ctx = AgentContext(tenant_id=1, user_id=None, process_id=None,
                       session=db_session, metadata={})
    agente = ExtratorAgent(ctx)
    for i in range(40):
        agente.registrar_chamada_llm(
            AIResponse(content="{}", model_used=f"modelo-muito-longo-{i}",
                       tokens_in=1, tokens_out=1, cost_usd=0.1, duration_ms=1,
                       provider=f"provider-{i}"),
            rotulo=f"c{i}",
        )
    # A agregação é lazy (acontece em `_complete_job`/`_fail_job`, uma vez por
    # execução) — aqui chamamos o agregador direto, que é o que eles chamam.
    agregado = agente._agregar_chamadas_llm()
    assert len(agregado.model_used) <= 100
    assert len(agregado.provider) <= 50
    assert agregado.tokens_in == 40
    assert agregado.cost_usd == pytest.approx(4.0)
