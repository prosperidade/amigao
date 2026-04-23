"""Sprint -1 D — ExtratorAgent lê e cacheia Document.extracted_text."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.agents.base import AgentContext, AgentRegistry
from app.models.client import Client
from app.models.document import Document, OcrStatus
from app.models.process import Process, ProcessStatus
from app.models.tenant import Tenant
from app.models.user import User


@pytest.fixture
def seeded(db_session):
    tenant = Tenant(name="Extrator Tenant")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        email="ext@example.com",
        full_name="Ext User",
        hashed_password="x" * 60,
        tenant_id=tenant.id,
        is_active=True,
    )
    client = Client(
        tenant_id=tenant.id,
        full_name="Cliente Teste",
        email="cli@example.com",
    )
    db_session.add_all([user, client])
    db_session.flush()

    process = Process(
        tenant_id=tenant.id,
        client_id=client.id,
        title="Processo Teste",
        process_type="car",
        status=ProcessStatus.triagem,
    )
    db_session.add(process)
    db_session.flush()

    doc = Document(
        tenant_id=tenant.id,
        process_id=process.id,
        client_id=client.id,
        original_file_name="matricula.pdf",
        filename="matricula.pdf",
        content_type="application/pdf",
        storage_key=f"tenant-{tenant.id}/matricula.pdf",
        document_type="matricula",
        ocr_status=OcrStatus.done,
    )
    db_session.add(doc)
    db_session.flush()

    return tenant, user, process, doc


def test_extrator_caches_text_when_passed_in_metadata(seeded, db_session):
    """Sprint -1 D: quando texto vem via metadata e doc.extracted_text é NULL,
    o extrator persiste o texto na coluna para futuras execuções."""
    tenant, user, process, doc = seeded

    ctx = AgentContext(
        tenant_id=tenant.id,
        user_id=user.id,
        process_id=process.id,
        session=db_session,
        metadata={
            "text": "MATRÍCULA Nº 15234 COMARCA SORRISO — ÁREA 432,5 HA",
            "doc_type": "matricula",
            "document_id": doc.id,
        },
    )

    # Mock extract_document_fields pra não chamar LLM de verdade
    with patch(
        "app.services.document_extractor.extract_document_fields",
        return_value=({"numero_matricula": "15234", "area_hectares": 432.5}, None),
    ):
        agent = AgentRegistry.create("extrator", ctx)
        result = agent.run()

    assert result.success is True

    # O texto deve ter sido cacheado no doc
    db_session.refresh(doc)
    assert doc.extracted_text == "MATRÍCULA Nº 15234 COMARCA SORRISO — ÁREA 432,5 HA"
    assert doc.extracted_at is not None


def test_extrator_reads_extracted_text_when_metadata_omits_text(seeded, db_session):
    """Sprint -1 D: segunda execução sem `text` em metadata busca da coluna."""
    tenant, user, process, doc = seeded

    # Primeiro: popular extracted_text
    doc.extracted_text = "Texto já extraído em OCR anterior"
    db_session.flush()

    ctx = AgentContext(
        tenant_id=tenant.id,
        user_id=user.id,
        process_id=process.id,
        session=db_session,
        metadata={"document_id": doc.id, "doc_type": "matricula"},
    )

    with patch(
        "app.services.document_extractor.extract_document_fields",
        return_value=({"numero_matricula": "15234"}, None),
    ) as mock_extract:
        agent = AgentRegistry.create("extrator", ctx)
        result = agent.run()

    assert result.success is True
    # Confirma que extract_document_fields recebeu o texto cacheado
    called_kwargs = mock_extract.call_args.kwargs
    assert called_kwargs["text"] == "Texto já extraído em OCR anterior"


def test_extrator_raises_when_no_text_and_no_cache(seeded, db_session):
    """Sprint -1 D: sem texto e com doc.extracted_text NULL, levanta ValueError claro."""
    tenant, user, process, doc = seeded

    # doc.extracted_text fica NULL — cenário inicial

    ctx = AgentContext(
        tenant_id=tenant.id,
        user_id=user.id,
        process_id=process.id,
        session=db_session,
        metadata={"document_id": doc.id, "doc_type": "matricula"},
    )

    agent = AgentRegistry.create("extrator", ctx)
    result = agent.run()

    # Agent deve ter falhado de forma graceful (BaseAgent captura exceções)
    assert result.success is False
    assert "OCR" in (result.error or "") or "texto extraido" in (result.error or "")
