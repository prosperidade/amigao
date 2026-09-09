"""Contenção 4 (ADR-064, achado N3) — o AIJob do extrator para de ser cego.

Medido em produção em 09/09: os `ai_jobs` 1467–1471 e 1473 do extrator têm
`model_used`, `provider`, `tokens_in/out`, `cost_usd` e `raw_output` TODOS nulos.
O extrator nunca usou `call_llm` — ele delega a chamada a `document_extractor` e
a `ficha01_extraction`, que falam com o gateway direto. O que o LLM devolveu
deixava de existir depois da chamada, e foi por isso que a origem dos erros da
ELODI só pôde ser tratada como hipótese até a reprodução manual.
"""

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
    tenant, user, process, doc = seeded
    ctx = AgentContext(
        tenant_id=tenant.id, user_id=user.id, process_id=process.id,
        session=db_session, metadata={"document_id": doc.id, "doc_type": "matricula"},
    )

    with patch("app.core.ai_gateway.complete", return_value=_RESP_PREVIEW), \
         patch("app.services.ficha01_extraction.complete", create=True), \
         patch("app.services.document_extractor.complete", create=True), \
         patch("app.services.ficha01_extraction._extract_structured") as mock_staging:
        # `_extract_structured` devolve (parsed, janela) e chama o callback de
        # auditoria — é o contrato que a contenção 4 depende.
        def _fake(text, doc_type, *, on_llm_response=None):
            if on_llm_response is not None:
                on_llm_response(_RESP_STAGING, f"staging:{doc_type}:chunk0[0:{len(text)}]")
            return json.loads(_RESP_STAGING.content), None

        mock_staging.side_effect = _fake
        result = AgentRegistry.create("extrator", ctx).run()

    assert result.success is True

    job = (
        db_session.query(AIJob)
        .filter(AIJob.tenant_id == tenant.id)
        .order_by(AIJob.id.desc())
        .first()
    )
    assert job is not None
    # Antes desta frente, TODOS os cinco eram nulos.
    assert job.model_used == "gpt-4o-mini"
    assert job.provider == "gpt"
    assert job.tokens_in == _RESP_PREVIEW.tokens_in + _RESP_STAGING.tokens_in
    assert job.tokens_out == _RESP_PREVIEW.tokens_out + _RESP_STAGING.tokens_out
    assert job.cost_usd == pytest.approx(
        _RESP_PREVIEW.cost_usd + _RESP_STAGING.cost_usd
    )

    blocos = json.loads(job.raw_output)
    assert len(blocos) == 2, "cada chamada ao LLM tem que estar no bruto"
    rotulos = [b["rotulo"] for b in blocos]
    assert any(r.startswith("doc") and "preview" in r for r in rotulos)
    assert any("staging:matricula:chunk0" in r for r in rotulos)
    # O JSON devolvido pelo LLM é reconferível a partir do próprio job.
    staging = next(b for b in blocos if "staging" in b["rotulo"])
    assert json.loads(staging["content"])["nirf_cib"] == "6.816.752-0"


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
