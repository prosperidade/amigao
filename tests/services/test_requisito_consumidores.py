"""Um teste por consumidor migrado para a fonte única (auditoria 2026-07-20).

Cada teste aqui trava o comportamento de UM dos pontos que antes reimplementava
"o requisito documental está satisfeito?" por conta própria.
"""

from __future__ import annotations

from app.models.checklist_template import ProcessChecklist
from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.extracted_field_staging import ExtractedFieldStaging
from app.models.matricula import Matricula
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.services.checklist_engine import auto_link_document
from app.services.dossier import validate_technical_consistency
from app.services.requisito_documental import contar_pendentes_checklist

_SEQ = {"n": 0}


def _seed(db_session, *, com_matricula=False):
    _SEQ["n"] += 1
    n = _SEQ["n"]
    tenant = Tenant(name=f"Consumidores {n}")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(tenant_id=tenant.id, full_name="Cliente", email=f"cons{n}@example.com",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add(cli)
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda São Jorge",
                    registry_number=None)
    db_session.add(prop)
    db_session.flush()
    if com_matricula:
        db_session.add(Matricula(tenant_id=tenant.id, property_id=prop.id,
                                 numero_matricula="4698", area_ha=660.6561))
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Caso", process_type="car", status=ProcessStatus.triagem,
                   demand_type=DemandType.car)
    db_session.add(proc)
    db_session.commit()
    db_session.refresh(prop)
    return tenant, proc, prop


def _doc(db_session, tenant, proc, doc_type, *, ocr=OcrStatus.done):
    _SEQ["n"] += 1
    d = Document(
        tenant_id=tenant.id, process_id=proc.id,
        original_file_name="c.pdf", filename="Certidão Inteiro Teor.pdf",
        content_type="application/pdf",
        storage_key=f"kc/{tenant.id}/{proc.id}/{_SEQ['n']}",
        document_type=doc_type, ocr_status=ocr,
    )
    db_session.add(d)
    db_session.flush()
    return d


def _campo(db_session, tenant, proc, doc, name, value="x"):
    db_session.add(ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=proc.id, document_id=doc.id,
        field_name=name, field_value={"value": value},
    ))
    db_session.flush()


# ---------------------------------------------------------------------------
# Consumidor #5 — dossier.MISSING_MATRICULA
# ---------------------------------------------------------------------------

def test_dossie_nao_diz_ausente_com_certidao_anexada(db_session):
    """O caso do André: certidão na base, `Matricula` não consolidada.

    Antes: MISSING_MATRICULA severity=error ("Matrícula do imóvel ausente").
    Agora: MATRICULA_EM_PROCESSAMENTO severity=info, com a verdade.
    """
    tenant, proc, prop = _seed(db_session)
    doc = _doc(db_session, tenant, proc, "matricula")
    db_session.commit()

    issues = validate_technical_consistency(proc, prop, [doc], None)
    codigos = {i.code for i in issues}

    assert "MISSING_MATRICULA" not in codigos
    assert "MATRICULA_EM_PROCESSAMENTO" in codigos

    em_proc = next(i for i in issues if i.code == "MATRICULA_EM_PROCESSAMENTO")
    assert em_proc.severity == "info"
    assert "ausente" not in em_proc.title.lower()


def test_dossie_reconhece_certidao_inteiro_teor_como_matricula(db_session):
    """`certidao_inteiro_teor` conta como matrícula anexada (vocabulário único)."""
    tenant, proc, prop = _seed(db_session)
    doc = _doc(db_session, tenant, proc, "certidao_inteiro_teor")
    db_session.commit()

    codigos = {i.code for i in validate_technical_consistency(proc, prop, [doc], None)}

    assert "MISSING_MATRICULA" not in codigos
    assert "CAR_NO_MATRICULA_DOC" not in codigos   # demand_type=car


def test_dossie_ainda_acusa_ausente_sem_documento_nenhum(db_session):
    """Sem documento, "ausente" continua sendo dito — a cura não cega o radar."""
    tenant, proc, prop = _seed(db_session)
    codigos = {i.code for i in validate_technical_consistency(proc, prop, [], None)}

    assert "MISSING_MATRICULA" in codigos
    assert "MATRICULA_EM_PROCESSAMENTO" not in codigos


def test_dossie_matricula_consolidada_nao_gera_nem_um_nem_outro(db_session):
    """Consolidada: nem ausente, nem em processamento (regressão do forense)."""
    tenant, proc, prop = _seed(db_session, com_matricula=True)
    doc = _doc(db_session, tenant, proc, "matricula")
    db_session.commit()

    codigos = {i.code for i in validate_technical_consistency(proc, prop, [doc], None)}

    assert "MISSING_MATRICULA" not in codigos
    assert "MATRICULA_EM_PROCESSAMENTO" not in codigos


# ---------------------------------------------------------------------------
# Consumidor #1 — checklist_engine.auto_link_document
# ---------------------------------------------------------------------------

def test_auto_link_casa_sinonimo_pela_fonte_unica(db_session):
    """`certidao_inteiro_teor` vincula ao item `matricula`.

    Antes o matching era `item.doc_type == doc_type` — igualdade exata, que
    nunca casava.
    """
    tenant, proc, _ = _seed(db_session)
    checklist = ProcessChecklist(
        tenant_id=tenant.id, process_id=proc.id, template_id=None,
        items=[{"id": "matricula", "label": "Matrícula do Imóvel",
                "doc_type": "matricula", "required": True,
                "status": "pending", "document_id": None, "waiver_reason": None}],
    )
    db_session.add(checklist)
    db_session.flush()

    item_id = auto_link_document(db_session, checklist, 999, "certidao_inteiro_teor")

    assert item_id == "matricula"
    assert checklist.items[0]["status"] == "received"
    assert checklist.items[0]["document_id"] == 999


def test_auto_link_casa_cpf_cnpj_com_doc_pessoal(db_session):
    """A CNH (`cpf_cnpj`) vincula ao item `doc_pessoal` — bug irmão do caso 15."""
    tenant, proc, _ = _seed(db_session)
    checklist = ProcessChecklist(
        tenant_id=tenant.id, process_id=proc.id, template_id=None,
        items=[{"id": "doc_proprietario", "label": "Documento do Proprietário",
                "doc_type": "doc_pessoal", "required": True,
                "status": "pending", "document_id": None, "waiver_reason": None}],
    )
    db_session.add(checklist)
    db_session.flush()

    assert auto_link_document(db_session, checklist, 316, "cpf_cnpj") == "doc_proprietario"


def test_auto_link_nao_casa_tipo_de_outro_requisito(db_session):
    """A tradução não pode virar promiscuidade: CCIR não satisfaz matrícula."""
    tenant, proc, _ = _seed(db_session)
    checklist = ProcessChecklist(
        tenant_id=tenant.id, process_id=proc.id, template_id=None,
        items=[{"id": "matricula", "label": "Matrícula", "doc_type": "matricula",
                "required": True, "status": "pending", "document_id": None,
                "waiver_reason": None}],
    )
    db_session.add(checklist)
    db_session.flush()

    assert auto_link_document(db_session, checklist, 314, "ccir") is None
    assert checklist.items[0]["status"] == "pending"


# ---------------------------------------------------------------------------
# Consumidores #3/#4 + 3ª cópia — contagem de pendentes
# ---------------------------------------------------------------------------

def test_contagem_nao_conta_item_com_documento_na_base(db_session):
    """Item "pending" no JSON cujo documento já chegou não é pendência de coleta."""
    tenant, proc, _ = _seed(db_session)
    doc = _doc(db_session, tenant, proc, "cpf_cnpj")
    _campo(db_session, tenant, proc, doc, "cpf", "123")
    db_session.commit()

    items = [
        {"id": "doc_proprietario", "doc_type": "doc_pessoal", "required": True,
         "status": "pending"},
        {"id": "car", "doc_type": "car", "required": True, "status": "pending"},
    ]

    # `doc_proprietario` some da contagem (CNH anexada); `car` continua faltando.
    assert contar_pendentes_checklist(db_session, proc.id, tenant.id, items) == 1


def test_contagem_preserva_itens_fora_dos_seis(db_session):
    """Fotos da área e laudo não estão na Ficha 08 §2 — seguem pelo JSON."""
    tenant, proc, _ = _seed(db_session)
    items = [
        {"id": "fotos_area", "doc_type": "foto", "required": True, "status": "pending"},
        {"id": "laudo_anterior", "doc_type": "laudo", "required": False, "status": "pending"},
        {"id": "auto_infracao", "doc_type": "auto_infracao", "required": True,
         "status": "pending"},
    ]

    # required+pending fora dos 6 → contam. O laudo não é required → não conta.
    assert contar_pendentes_checklist(db_session, proc.id, tenant.id, items) == 2


def test_contagem_vazia_sem_checklist(db_session):
    tenant, proc, _ = _seed(db_session)
    assert contar_pendentes_checklist(db_session, proc.id, tenant.id, None) == 0
    assert contar_pendentes_checklist(db_session, proc.id, tenant.id, []) == 0
