"""STATE-001 (Frente H, ADR-068) — `progresso_conferencia` é a fonte única.

Gate da frente: os números que o dossiê, o endpoint de progresso e a
Conferência mostram para o MESMO processo têm de bater — porque todos chamam
a mesma função. Este arquivo mede a função isolada; `test_dossier_conferencia_
usa_indicador_canonico` (abaixo) mede que o dossiê não recalcula por conta
própria.
"""

from __future__ import annotations

from app.models.checklist_template import ProcessChecklist
from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.services.checklist_engine import get_checklist_status, mark_item_received, mark_item_waived
from app.services.dossier import generate_dossier
from app.services.process_indicators import progresso_conferencia

_SEQ = {"n": 0}


def _seed(db_session):
    _SEQ["n"] += 1
    n = _SEQ["n"]
    tenant = Tenant(name=f"Indicadores {n}")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(
        tenant_id=tenant.id, full_name=f"Cliente {n}", email=f"indic{n}@example.com",
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
    return tenant, proc, prop, cli


def _doc(db_session, tenant, proc, doc_type="matricula"):
    _SEQ["n"] += 1
    d = Document(
        tenant_id=tenant.id, process_id=proc.id,
        original_file_name=f"{doc_type}.pdf", filename=f"{doc_type}.pdf",
        content_type="application/pdf",
        storage_key=f"indic/{tenant.id}/{_SEQ['n']}",
        document_type=doc_type, ocr_status=OcrStatus.done,
    )
    db_session.add(d)
    db_session.flush()
    return d


def _linha(db_session, tenant, proc, doc, *, field_name, valor, entidade, alvo=None,
           hint=None, status=ExtractedFieldStatus.pendente, consolidated_at=None):
    row = ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=proc.id, document_id=doc.id,
        field_name=field_name, field_value={"value": valor},
        status=status, target_entity=entidade, target_field=alvo,
        matricula_hint=hint, source_doc_type=doc.document_type,
        consolidated_at=consolidated_at,
    )
    db_session.add(row)
    db_session.flush()
    return row


# ---------------------------------------------------------------------------
# progresso_conferencia
# ---------------------------------------------------------------------------


def test_progresso_conferencia_conta_decisao_nao_campo(db_session):
    """REC-001/ADR-067: 2 linhas do MESMO fato (composição da matrícula 3181)
    são UMA decisão, não duas — a unidade que a Frente G definiu."""
    tenant, proc, prop, cli = _seed(db_session)
    car = _doc(db_session, tenant, proc, "car")
    certidao = _doc(db_session, tenant, proc, "matricula")

    _linha(db_session, tenant, proc, car, field_name="matricula_listada",
           valor={"numero": "3181"}, entidade="matricula", hint="3181")
    _linha(db_session, tenant, proc, certidao, field_name="numero_matricula",
           valor="3.181", entidade="matricula", alvo="numero_matricula", hint="3181")

    resultado = progresso_conferencia(db_session, tenant_id=tenant.id, process_id=proc.id)

    assert resultado.decisoes_total == 1
    assert resultado.pendentes == 1
    assert resultado.decididas == 0
    assert resultado.gravadas == 0


def test_progresso_conferencia_decidida_e_gravada(db_session):
    tenant, proc, prop, cli = _seed(db_session)
    doc = _doc(db_session, tenant, proc, "matricula")

    # composicao: decidida mas não gravada.
    _linha(db_session, tenant, proc, doc, field_name="numero_matricula",
           valor="3.181", entidade="matricula", alvo="numero_matricula", hint="3181",
           status=ExtractedFieldStatus.aceito)
    # sem_agrupamento (campo sem regra de chave nesta frente) já gravado —
    # `field_name` deliberadamente fora de qualquer regra de `_chave_de`.
    row_gravada = _linha(db_session, tenant, proc, doc, field_name="observacao_livre",
                          valor="x", entidade="matricula", alvo="algum_campo", hint="9999",
                          status=ExtractedFieldStatus.aceito)
    from datetime import UTC, datetime
    row_gravada.consolidated_at = datetime.now(UTC)
    db_session.flush()

    resultado = progresso_conferencia(db_session, tenant_id=tenant.id, process_id=proc.id)

    assert resultado.decisoes_total == 2
    assert resultado.decididas == 2
    assert resultado.gravadas == 1
    assert resultado.pendentes == 0


def test_progresso_conferencia_processo_sem_staging(db_session):
    tenant, proc, prop, cli = _seed(db_session)
    resultado = progresso_conferencia(db_session, tenant_id=tenant.id, process_id=proc.id)
    assert resultado.decisoes_total == 0
    assert resultado.decididas == 0
    assert resultado.gravadas == 0
    assert resultado.pendentes == 0


# ---------------------------------------------------------------------------
# checklist_engine — o achado da triagem (recebido sem documento)
# ---------------------------------------------------------------------------


def _checklist(db_session, tenant, proc, n_items=2):
    items = [
        {"id": f"item{i}", "label": f"Item {i}", "doc_type": "matricula",
         "category": "fundiario", "required": True, "status": "pending", "document_id": None}
        for i in range(n_items)
    ]
    checklist = ProcessChecklist(tenant_id=tenant.id, process_id=proc.id, items=items)
    db_session.add(checklist)
    db_session.flush()
    return checklist


def test_checklist_recebido_sem_documento_nao_conta_no_percentual(db_session):
    """O achado da triagem: `mark_item_received(checklist, item_id)` sem
    `document_id` grava `status=received`, mas não pode inflar o percentual."""
    tenant, proc, prop, cli = _seed(db_session)
    checklist = _checklist(db_session, tenant, proc, n_items=2)

    mark_item_received(checklist, "item0")  # SEM document_id — o caso da triagem
    doc = _doc(db_session, tenant, proc)
    mark_item_received(checklist, "item1", doc.id)  # COM document_id

    status_obj = get_checklist_status(checklist)

    assert status_obj.received == 2
    assert status_obj.received_without_document == 1
    # Só o item COM documento conta como concluído: 1/2 = 50%, não 100%.
    assert status_obj.completion_pct == 50.0


def test_checklist_waived_conta_como_concluido_mesmo_sem_documento(db_session):
    """Dispensa é uma DECISÃO do consultor (com justificativa) — não é o
    mesmo caso de "recebido" sem lastro; continua contando."""
    tenant, proc, prop, cli = _seed(db_session)
    checklist = _checklist(db_session, tenant, proc, n_items=1)
    mark_item_waived(checklist, "item0", "documento dispensado pela sócia")

    status_obj = get_checklist_status(checklist)
    assert status_obj.completion_pct == 100.0


# ---------------------------------------------------------------------------
# Dossiê usa a MESMA fonte — gate da frente (números batem)
# ---------------------------------------------------------------------------


def test_dossier_conferencia_usa_indicador_canonico(db_session):
    tenant, proc, prop, cli = _seed(db_session)
    doc = _doc(db_session, tenant, proc)
    _linha(db_session, tenant, proc, doc, field_name="numero_matricula",
           valor="3.181", entidade="matricula", alvo="numero_matricula", hint="3181",
           status=ExtractedFieldStatus.aceito)

    direto = progresso_conferencia(db_session, tenant_id=tenant.id, process_id=proc.id)
    dossie = generate_dossier(db_session, proc.id, tenant.id)

    assert dossie.conferencia_summary == direto.to_dict()


def test_dossier_checklist_summary_bate_com_checklist_engine(db_session):
    """O bug da triagem era o dossiê reimplementar a conta do checklist — e
    divergir. Agora as duas leituras vêm da mesma função."""
    tenant, proc, prop, cli = _seed(db_session)
    checklist = _checklist(db_session, tenant, proc, n_items=2)
    mark_item_received(checklist, "item0")  # sem documento — não conta

    direto = get_checklist_status(checklist)
    dossie = generate_dossier(db_session, proc.id, tenant.id)

    assert dossie.checklist_summary["completion_pct"] == direto.completion_pct
    assert dossie.checklist_summary["received_without_document"] == direto.received_without_document
