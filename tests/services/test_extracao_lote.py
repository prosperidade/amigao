"""Escopo do lote de extração (#78) — a parte que decide gasto.

O recorte `sem_staging` é o que impede re-pagar LLM por documento já lido: no
caso 15, rodar a rota `/extract` inteira cobraria 42 documentos sendo que 10 já
estavam extraídos.
"""

from __future__ import annotations

import pytest

from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.extracted_field_staging import ExtractedFieldStaging
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.services.extracao_lote import coletar_escopo

_SEQ = {"n": 0}


def _seed(db_session):
    _SEQ["n"] += 1
    n = _SEQ["n"]
    tenant = Tenant(name=f"Lote {n}")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(tenant_id=tenant.id, full_name="C", email=f"lote{n}@example.com",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add(cli)
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="F")
    db_session.add(prop)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Caso", process_type="car", status=ProcessStatus.triagem,
                   demand_type=DemandType.car)
    db_session.add(proc)
    db_session.flush()
    return tenant, proc


def _doc(db_session, tenant, proc, *, doc_type="ccir", texto="CCIR texto aqui"):
    _SEQ["n"] += 1
    d = Document(
        tenant_id=tenant.id, process_id=proc.id,
        original_file_name="d.pdf", filename="d.pdf",
        content_type="application/pdf",
        storage_key=f"lote/{tenant.id}/{_SEQ['n']}",
        document_type=doc_type, ocr_status=OcrStatus.done, extracted_text=texto,
    )
    db_session.add(d)
    db_session.flush()
    return d


def test_escopo_obrigatorio(db_session):
    with pytest.raises(ValueError, match="escopo obrigatório"):
        coletar_escopo(db_session)


def test_sem_staging_exclui_documento_ja_lido(db_session):
    """O recorte que evita re-pagar pelo que já foi extraído."""
    tenant, proc = _seed(db_session)
    lido = _doc(db_session, tenant, proc)
    novo = _doc(db_session, tenant, proc)
    db_session.add(ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=proc.id, document_id=lido.id,
        field_name="area_ha", field_value={"value": "10"}))
    db_session.flush()

    escopo = coletar_escopo(db_session, process_ids=[proc.id], sem_staging=True)

    assert [d.id for d in escopo.documentos] == [novo.id]


def test_sem_o_recorte_todos_entram(db_session):
    """Sem `sem_staging`, o lote cobraria tudo — é o que a rota /extract faz."""
    tenant, proc = _seed(db_session)
    lido = _doc(db_session, tenant, proc)
    novo = _doc(db_session, tenant, proc)
    db_session.add(ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=proc.id, document_id=lido.id,
        field_name="area_ha", field_value={"value": "10"}))
    db_session.flush()

    escopo = coletar_escopo(db_session, process_ids=[proc.id], sem_staging=False)

    assert {d.id for d in escopo.documentos} == {lido.id, novo.id}


def test_escopo_por_document_id(db_session):
    tenant, proc = _seed(db_session)
    a = _doc(db_session, tenant, proc)
    _doc(db_session, tenant, proc)

    escopo = coletar_escopo(db_session, document_ids=[a.id])

    assert [d.id for d in escopo.documentos] == [a.id]


def test_sinaliza_sem_texto_e_sem_tipo(db_session):
    tenant, proc = _seed(db_session)
    mudo = _doc(db_session, tenant, proc, texto="")
    sem_tipo = _doc(db_session, tenant, proc, doc_type=None)

    escopo = coletar_escopo(db_session, process_ids=[proc.id])

    assert mudo.id in escopo.sem_texto
    assert sem_tipo.id in escopo.sem_tipo


def test_estimativa_de_tokens(db_session):
    tenant, proc = _seed(db_session)
    _doc(db_session, tenant, proc, texto="x" * 4000)

    escopo = coletar_escopo(db_session, process_ids=[proc.id])

    assert escopo.total_chars == 4000
    assert escopo.tokens_estimados == 1000


def test_documento_apagado_fica_fora(db_session):
    from datetime import UTC, datetime
    tenant, proc = _seed(db_session)
    d = _doc(db_session, tenant, proc)
    d.deleted_at = datetime.now(UTC)
    db_session.flush()

    escopo = coletar_escopo(db_session, process_ids=[proc.id])

    assert escopo.documentos == []
