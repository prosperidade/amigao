"""Ficha 01 / FASE 2 — o ExtratorAgent grava staging SEM alterar extracted_fields.

Mocka o LLM legado (``extract_document_fields``) e o LLM estruturado
(``ficha01_extraction._extract_structured``) — o ``extract_and_stage`` real roda e
persiste as linhas. Prova: (1) o shape de ``extracted_fields`` continua igual;
(2) o staging é populado com os campos certos por tipo + matricula_hint.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.agents.base import AgentContext, AgentRegistry
from app.models.client import Client
from app.models.document import Document, OcrStatus
from app.models.extracted_field_staging import ExtractedFieldStaging
from app.models.process import Process, ProcessStatus
from app.models.tenant import Tenant
from app.models.user import User

_CAR_TEXT = "RECIBO DE INSCRIÇÃO no Cadastro Ambiental Rural — Município Uirapuru/GO"

_LEGACY_FIELDS = {
    "numero_car": "GO-5221080-A1B2C3",
    "area_total_ha": 1010.5583,
    "municipio": "Uirapuru",
    "confidence": {"numero_car": "high"},
}

_STRUCTURED = {
    "numero_car": "GO-5221080-A1B2C3",
    "area_declarada_ha": 1010.5583,
    "municipio": "Uirapuru",
    "uf": "GO",
    "matriculas": [
        {"numero": "4.698", "data": "12/03/2001", "livro_folha": "L2", "cartorio": "CRI"},
        {"numero": "6.776", "data": "05/08/2010", "livro_folha": "L2", "cartorio": "CRI"},
    ],
    "confidence": {"numero_car": "high"},
}


@pytest.fixture
def seeded(db_session):
    tenant = Tenant(name="Ficha02 Agent Tenant")
    db_session.add(tenant)
    db_session.flush()
    user = User(
        email="f2@example.com", full_name="F2", hashed_password="x" * 60,
        tenant_id=tenant.id, is_active=True,
    )
    client = Client(tenant_id=tenant.id, full_name="Cli", email="cli2@example.com")
    db_session.add_all([user, client])
    db_session.flush()
    process = Process(
        tenant_id=tenant.id, client_id=client.id, title="Caso CAR",
        process_type="prad", status=ProcessStatus.triagem,
    )
    db_session.add(process)
    db_session.flush()
    doc = Document(
        tenant_id=tenant.id, process_id=process.id, client_id=client.id,
        original_file_name="recibo_car.pdf", filename="recibo_car.pdf",
        content_type="application/pdf", storage_key=f"tenant-{tenant.id}/recibo.pdf",
        document_type="car", ocr_status=OcrStatus.done, extracted_text=_CAR_TEXT,
    )
    db_session.add(doc)
    db_session.flush()
    return tenant, user, process, doc


def test_extrator_grava_staging_sem_mexer_extracted_fields(seeded, db_session):
    tenant, user, process, doc = seeded
    ctx = AgentContext(
        tenant_id=tenant.id, user_id=user.id, process_id=process.id,
        session=db_session, metadata={"document_id": doc.id, "doc_type": "car"},
    )

    with patch(
        "app.services.document_extractor.extract_document_fields",
        return_value=(dict(_LEGACY_FIELDS), None),
    ), patch(
        "app.services.ficha01_extraction._extract_structured",
        return_value=dict(_STRUCTURED),
    ):
        agent = AgentRegistry.create("extrator", ctx)
        result = agent.run()

    assert result.success is True
    # (1) extracted_fields permanece com o shape/conteúdo legado.
    assert result.data["extracted_fields"] == _LEGACY_FIELDS
    assert result.data["doc_type"] == "car"

    # (2) staging populado para o processo/documento.
    rows = (
        db_session.query(ExtractedFieldStaging)
        .filter(
            ExtractedFieldStaging.tenant_id == tenant.id,
            ExtractedFieldStaging.process_id == process.id,
        )
        .all()
    )
    assert rows, "staging deveria ter sido populado"
    assert all(r.source_doc_type == "car" for r in rows)
    assert all(r.document_id == doc.id for r in rows)
    # ai_job_id rastreável (job da execução corrente).
    assert all(r.ai_job_id is not None for r in rows)
    listadas = [r for r in rows if r.field_name == "matricula_listada"]
    assert {r.matricula_hint for r in listadas} == {"4.698", "6.776"}
