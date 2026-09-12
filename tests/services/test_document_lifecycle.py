"""DOC-001 (Frente H, ADR-068) — estado do documento derivado + transição
auditada no `audit_log` existente (sem tabela/coluna nova).

Gate da frente: colar a sequência recebido → lido → classificado → extraído →
conferido de um documento, com autor em cada transição (`None` = automático).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User
from app.services.document_lifecycle import (
    AUDIT_ACTION,
    DocumentLifecycleStatus,
    derive_document_status,
    historico_transicoes,
    registrar_transicao_se_mudou,
)

_SEQ = {"n": 0}


def _seed(db_session):
    _SEQ["n"] += 1
    n = _SEQ["n"]
    tenant = Tenant(name=f"DocLifecycle {n}")
    db_session.add(tenant)
    db_session.flush()
    user = User(
        tenant_id=tenant.id, email=f"consultor{n}@example.com",
        hashed_password="x", full_name="Consultora", is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    cli = Client(
        tenant_id=tenant.id, full_name=f"Cliente {n}", email=f"doclc{n}@example.com",
        client_type=ClientType.pf, status=ClientStatus.active,
    )
    db_session.add(cli)
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda Teste")
    db_session.add(prop)
    db_session.flush()
    proc = Process(
        tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
        title="Caso", process_type="car", status=ProcessStatus.triagem,
        demand_type=DemandType.car,
    )
    db_session.add(proc)
    db_session.flush()
    return tenant, proc, user


def _doc(db_session, tenant, proc):
    _SEQ["n"] += 1
    d = Document(
        tenant_id=tenant.id, process_id=proc.id,
        original_file_name="matricula.pdf", filename="matricula.pdf",
        content_type="application/pdf",
        storage_key=f"doclc/{tenant.id}/{_SEQ['n']}",
    )
    db_session.add(d)
    db_session.flush()
    return d


def test_derive_status_recebido_sem_leitura(db_session):
    tenant, proc, user = _seed(db_session)
    doc = _doc(db_session, tenant, proc)
    assert derive_document_status(db_session, doc) == DocumentLifecycleStatus.recebido


def test_ocr_done_sem_texto_legivel_e_erro_de_leitura(db_session):
    tenant, proc, user = _seed(db_session)
    doc = _doc(db_session, tenant, proc)
    doc.ocr_status = OcrStatus.done
    doc.extracted_text = "Documento digital assinado."
    db_session.flush()

    assert doc.tem_texto is False
    assert derive_document_status(db_session, doc) == DocumentLifecycleStatus.erro_leitura


def test_processando_e_desatualizado_sao_estados_distintos(db_session):
    tenant, proc, user = _seed(db_session)
    doc = _doc(db_session, tenant, proc)
    doc.ocr_status = OcrStatus.processing
    db_session.flush()
    assert derive_document_status(db_session, doc) == DocumentLifecycleStatus.processando

    doc.expires_at = datetime.now(UTC) - timedelta(days=1)
    db_session.flush()
    assert derive_document_status(db_session, doc) == DocumentLifecycleStatus.desatualizado


def test_documento_removido_tem_projecao_substituido(db_session):
    tenant, proc, user = _seed(db_session)
    doc = _doc(db_session, tenant, proc)
    doc.deleted_at = datetime.now(UTC)
    db_session.flush()
    assert derive_document_status(db_session, doc) == DocumentLifecycleStatus.substituido


def test_vocabulario_inclui_estados_negativos_sem_documento():
    assert DocumentLifecycleStatus.nao_apresentado.value == "nao_apresentado"
    assert DocumentLifecycleStatus.dispensado.value == "dispensado"


def test_derive_status_lido_com_ocr_done(db_session):
    tenant, proc, user = _seed(db_session)
    doc = _doc(db_session, tenant, proc)
    doc.ocr_status = OcrStatus.done
    doc.extracted_text = "Matrícula 3.181 do Registro de Imóveis, com área rural identificada."
    db_session.flush()
    assert derive_document_status(db_session, doc) == DocumentLifecycleStatus.lido


def test_derive_status_classificado(db_session):
    tenant, proc, user = _seed(db_session)
    doc = _doc(db_session, tenant, proc)
    doc.extracted_text = "Matrícula 3.181 do Registro de Imóveis, com área rural identificada."
    doc.document_type = "matricula"
    db_session.flush()
    assert derive_document_status(db_session, doc) == DocumentLifecycleStatus.classificado


def test_derive_status_outro_nao_conta_como_classificado(db_session):
    """`document_type="outro"` é o valor de "não foi possível classificar" —
    não deve ser lido como um degrau alcançado (mesma regra de
    `document_classification._esta_vazio`, que trata "outro" como gravado mas
    não específico)."""
    tenant, proc, user = _seed(db_session)
    doc = _doc(db_session, tenant, proc)
    doc.extracted_text = "Matrícula 3.181 do Registro de Imóveis, com área rural identificada."
    doc.document_type = "outro"
    db_session.flush()
    assert derive_document_status(db_session, doc) == DocumentLifecycleStatus.lido


def test_derive_status_extraido(db_session):
    tenant, proc, user = _seed(db_session)
    doc = _doc(db_session, tenant, proc)
    doc.extracted_text = "Matrícula 3.181 do Registro de Imóveis, com área rural identificada."
    doc.document_type = "matricula"
    db_session.flush()
    db_session.add(ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=proc.id, document_id=doc.id,
        field_name="numero_matricula", field_value={"value": "3.181"},
        status=ExtractedFieldStatus.pendente, target_entity="matricula",
    ))
    db_session.flush()
    assert derive_document_status(db_session, doc) == DocumentLifecycleStatus.extraido


def test_derive_status_conferido_quando_toda_linha_decidida(db_session):
    tenant, proc, user = _seed(db_session)
    doc = _doc(db_session, tenant, proc)
    doc.extracted_text = "Matrícula 3.181 do Registro de Imóveis, com área rural identificada."
    doc.document_type = "matricula"
    db_session.flush()
    db_session.add(ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=proc.id, document_id=doc.id,
        field_name="numero_matricula", field_value={"value": "3.181"},
        status=ExtractedFieldStatus.aceito, target_entity="matricula",
    ))
    db_session.add(ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=proc.id, document_id=doc.id,
        field_name="area_registrada_ha", field_value={"value": "10"},
        status=ExtractedFieldStatus.rejeitado, target_entity="matricula",
    ))
    db_session.flush()
    assert derive_document_status(db_session, doc) == DocumentLifecycleStatus.conferido


def test_derive_status_extraido_quando_ha_linha_pendente(db_session):
    tenant, proc, user = _seed(db_session)
    doc = _doc(db_session, tenant, proc)
    doc.extracted_text = "Matrícula 3.181 do Registro de Imóveis, com área rural identificada."
    doc.document_type = "matricula"
    db_session.flush()
    db_session.add(ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=proc.id, document_id=doc.id,
        field_name="numero_matricula", field_value={"value": "3.181"},
        status=ExtractedFieldStatus.aceito, target_entity="matricula",
    ))
    db_session.add(ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=proc.id, document_id=doc.id,
        field_name="area_registrada_ha", field_value={"value": "10"},
        status=ExtractedFieldStatus.pendente, target_entity="matricula",
    ))
    db_session.flush()
    assert derive_document_status(db_session, doc) == DocumentLifecycleStatus.extraido


def test_registrar_transicao_grava_sequencia_completa_com_autor(db_session):
    """O gate: colar a sequência recebido → lido → classificado → extraído →
    conferido de UM documento, cada uma com autor (`None` = automático,
    `user.id` = gesto humano)."""
    tenant, proc, user = _seed(db_session)
    doc = _doc(db_session, tenant, proc)

    # Ainda "recebido" — nada muda, nada é gravado (baseline implícito).
    assert registrar_transicao_se_mudou(db_session, doc, user_id=None) is None
    assert historico_transicoes(db_session, doc) == []

    # → lido (automático — pipeline OCR).
    doc.ocr_status = OcrStatus.done
    doc.extracted_text = "Matrícula 3.181 do Registro de Imóveis, com área rural identificada."
    db_session.flush()
    novo = registrar_transicao_se_mudou(db_session, doc, user_id=None)
    assert novo == DocumentLifecycleStatus.lido

    # → classificado (gesto humano: consultor reclassificou na tela).
    doc.document_type = "matricula"
    db_session.flush()
    novo = registrar_transicao_se_mudou(db_session, doc, user_id=user.id)
    assert novo == DocumentLifecycleStatus.classificado

    # → extraído (automático).
    row1 = ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=proc.id, document_id=doc.id,
        field_name="numero_matricula", field_value={"value": "3.181"},
        status=ExtractedFieldStatus.pendente, target_entity="matricula",
    )
    db_session.add(row1)
    db_session.flush()
    novo = registrar_transicao_se_mudou(db_session, doc, user_id=None)
    assert novo == DocumentLifecycleStatus.extraido

    # → conferido (automático — consolidação decidiu a última linha pendente).
    row1.status = ExtractedFieldStatus.aceito
    db_session.flush()
    novo = registrar_transicao_se_mudou(db_session, doc, user_id=None)
    assert novo == DocumentLifecycleStatus.conferido

    sequencia = historico_transicoes(db_session, doc)
    passos = [(t.old_value, t.new_value, t.user_id, t.action) for t in sequencia]
    assert passos == [
        ("recebido", "lido", None, AUDIT_ACTION),
        ("lido", "classificado", user.id, AUDIT_ACTION),
        ("classificado", "extraido", None, AUDIT_ACTION),
        ("extraido", "conferido", None, AUDIT_ACTION),
    ]
    # Hash chain presente em cada transição (Princípio 2 — tudo auditável).
    assert all(t.hash_sha256 for t in sequencia)


def test_registrar_transicao_idempotente_quando_nada_mudou(db_session):
    tenant, proc, user = _seed(db_session)
    doc = _doc(db_session, tenant, proc)
    doc.ocr_status = OcrStatus.done
    doc.extracted_text = "Matrícula 3.181 do Registro de Imóveis, com área rural identificada."
    db_session.flush()

    primeiro = registrar_transicao_se_mudou(db_session, doc, user_id=None)
    segundo = registrar_transicao_se_mudou(db_session, doc, user_id=None)

    assert primeiro == DocumentLifecycleStatus.lido
    assert segundo is None
    assert len(historico_transicoes(db_session, doc)) == 1
