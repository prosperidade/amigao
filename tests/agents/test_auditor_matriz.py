"""Ficha 02 / FASE 3 — o auditor anexa a matriz e marca o staging, SEM quebrar
o shape antigo do AuditorResult.
"""

from __future__ import annotations

import pytest

from app.agents.base import AgentContext, AgentRegistry
from app.models.client import Client
from app.models.extracted_field_staging import (
    ExtractedFieldStaging,
    ExtractedFieldStatus,
)
from app.models.process import Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User


def _staging(tenant_id, process_id, source, fname, value, *, hint=None):
    return ExtractedFieldStaging(
        tenant_id=tenant_id, process_id=process_id, source_doc_type=source,
        field_name=fname, field_value={"value": value}, matricula_hint=hint,
        status=ExtractedFieldStatus.pendente, created_by_agent="extrator",
    )


@pytest.fixture
def seeded(db_session):
    tenant = Tenant(name="Matriz Tenant")
    db_session.add(tenant)
    db_session.flush()
    user = User(email="m@example.com", full_name="M", hashed_password="x" * 60,
                tenant_id=tenant.id, is_active=True)
    client = Client(tenant_id=tenant.id, full_name="Cli", email="climz@example.com")
    db_session.add_all([user, client])
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=client.id, name="Fazenda São Jorge")
    db_session.add(prop)
    db_session.flush()
    process = Process(tenant_id=tenant.id, client_id=client.id, property_id=prop.id,
                      title="Caso", process_type="prad", status=ProcessStatus.triagem)
    db_session.add(process)
    db_session.flush()
    rows = [
        _staging(tenant.id, process.id, "matricula", "area_registrada_ha", "660,6561", hint="4.698"),
        _staging(tenant.id, process.id, "matricula", "denominacao", "Fazenda São Jorge", hint="4.698"),
        _staging(tenant.id, process.id, "matricula", "area_registrada_ha", "349,9022", hint="6.776"),
        _staging(tenant.id, process.id, "matricula", "denominacao", "Shangri-lá Parte 2", hint="6.776"),
        _staging(tenant.id, process.id, "car", "area_declarada_ha", "1.010,7113"),
        _staging(tenant.id, process.id, "itr", "codigo_incra", "222"),
    ]
    db_session.add_all(rows)
    db_session.flush()
    return tenant, user, process


def test_auditor_anexa_matriz_e_preserva_shape(seeded, db_session):
    tenant, user, process = seeded
    ctx = AgentContext(tenant_id=tenant.id, user_id=user.id, process_id=process.id,
                       session=db_session, metadata={})
    agent = AgentRegistry.create("auditor_imovel", ctx)
    result = agent.run()

    assert result.success is True
    data = result.data
    # shape antigo do AuditorResult intacto
    for key in ("content", "divergencias", "issue_ids", "findings_raw", "geom_present", "method"):
        assert key in data, f"chave legada ausente: {key}"
    assert data["method"] == "deterministic_tools"

    # campo novo: matriz
    matriz = data["matriz_inconsistencias"]
    itens = {ln["item"]: ln for ln in matriz["linhas"]}
    assert itens["area_total"]["situacao"] == "divergente"
    assert itens["denominacao_imovel"]["situacao"] == "divergente"
    assert itens["sigef_georreferenciamento"]["situacao"] == "critico"

    # staging marcado (consistente/divergente_*), nunca aceito/rejeitado
    marcados = (
        db_session.query(ExtractedFieldStaging)
        .filter(ExtractedFieldStaging.process_id == process.id,
                ExtractedFieldStaging.status != ExtractedFieldStatus.pendente)
        .all()
    )
    assert marcados, "auditor deveria ter marcado linhas confrontadas"
    assert all(m.status in (ExtractedFieldStatus.consistente,
                            ExtractedFieldStatus.divergente_transcricao,
                            ExtractedFieldStatus.divergente_fundo) for m in marcados)
