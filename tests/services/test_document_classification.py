"""Classificação persistida + backfill só-NULL — dívida #70.

O teste que trava a decisão do André é
`test_tipo_existente_nunca_e_sobrescrito_mesmo_divergente`: documento com tipo
já gravado e conteúdo discordando **não muda** — vira achado, nunca escrita.
"""

from __future__ import annotations

from app.models.checklist_template import ProcessChecklist
from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.services.document_classification import (
    aplicar_classificacao,
    planejar_backfill,
)

_SEQ = {"n": 0}

# Texto com marcador forte de certidão de matrícula (ficha01 `_CLASSIFY_RULES`).
TEXTO_MATRICULA = (
    "CERTIDAO DE INTEIRO TEOR do Livro no 2 de Registro Geral. "
    "O OFICIAL REGISTRADOR certifica que a matricula 6.776 encontra-se vigente."
)
TEXTO_CCIR = (
    "CERTIFICADO DE CADASTRO DE IMOVEL RURAL - CCIR. "
    "Codigo do imovel rural no SNCR. Modulos fiscais."
)
TEXTO_MUDO = "Documento sem marcadores reconheciveis de nenhum tipo especifico."


def _seed(db_session):
    _SEQ["n"] += 1
    n = _SEQ["n"]
    tenant = Tenant(name=f"Class {n}")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(tenant_id=tenant.id, full_name="Cliente", email=f"class{n}@example.com",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add(cli)
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda")
    db_session.add(prop)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Caso", process_type="car", status=ProcessStatus.triagem,
                   demand_type=DemandType.car)
    db_session.add(proc)
    db_session.flush()
    return tenant, proc


def _doc(db_session, tenant, proc, *, doc_type=None, texto=TEXTO_MATRICULA):
    _SEQ["n"] += 1
    d = Document(
        tenant_id=tenant.id, process_id=proc.id,
        original_file_name="d.pdf", filename="d.pdf",
        content_type="application/pdf",
        storage_key=f"bf/{tenant.id}/{proc.id}/{_SEQ['n']}",
        document_type=doc_type, ocr_status=OcrStatus.done,
        extracted_text=texto,
    )
    db_session.add(d)
    db_session.flush()
    return d


def _checklist(db_session, tenant, proc, items):
    cl = ProcessChecklist(tenant_id=tenant.id, process_id=proc.id,
                          template_id=None, items=items)
    db_session.add(cl)
    db_session.flush()
    return cl


# ---------------------------------------------------------------------------
# A decisão do André: só preenche NULL
# ---------------------------------------------------------------------------

def test_tipo_ausente_e_gravado(db_session):
    tenant, proc = _seed(db_session)
    doc = _doc(db_session, tenant, proc, doc_type=None)

    res = aplicar_classificacao(db_session, doc, "matricula")

    assert res.gravado is True
    assert doc.document_type == "matricula"
    assert not res.divergente


def test_tipo_existente_nunca_e_sobrescrito_mesmo_divergente(db_session):
    """Decisão fechada: tipo gravado pode ser correção manual do consultor.

    Divergência vira ACHADO no relatório, nunca escrita silenciosa.
    """
    tenant, proc = _seed(db_session)
    doc = _doc(db_session, tenant, proc, doc_type="ccir")

    res = aplicar_classificacao(db_session, doc, "matricula")

    assert res.gravado is False
    assert doc.document_type == "ccir"          # intacto
    assert res.divergente is True
    assert "achado" in res.motivo


def test_tipo_existente_igual_nao_e_divergente(db_session):
    tenant, proc = _seed(db_session)
    doc = _doc(db_session, tenant, proc, doc_type="matricula")

    res = aplicar_classificacao(db_session, doc, "matricula")

    assert res.gravado is False
    assert res.divergente is False
    assert "preservado por decisão" in res.motivo


def test_outro_nao_conta_como_vazio(db_session):
    """`outro` é valor gravado — a decisão manda preservar."""
    tenant, proc = _seed(db_session)
    doc = _doc(db_session, tenant, proc, doc_type="outro")

    res = aplicar_classificacao(db_session, doc, "matricula")

    assert res.gravado is False
    assert doc.document_type == "outro"


def test_string_vazia_conta_como_ausente(db_session):
    tenant, proc = _seed(db_session)
    doc = _doc(db_session, tenant, proc, doc_type="   ")

    res = aplicar_classificacao(db_session, doc, "matricula")

    assert res.gravado is True
    assert doc.document_type == "matricula"


def test_classificacao_sem_tipo_especifico_nao_grava(db_session):
    tenant, proc = _seed(db_session)
    doc = _doc(db_session, tenant, proc, doc_type=None)

    res = aplicar_classificacao(db_session, doc, "outro")

    assert res.gravado is False
    assert doc.document_type is None


# ---------------------------------------------------------------------------
# Fecha o ciclo: classificou → gravou → vinculou (o que faltava no #70)
# ---------------------------------------------------------------------------

def test_gravar_tipo_revincula_checklist_dos_dois_lados(db_session):
    tenant, proc = _seed(db_session)
    _checklist(db_session, tenant, proc, [
        {"id": "matricula", "label": "Matrícula", "doc_type": "matricula",
         "required": True, "status": "pending", "document_id": None,
         "waiver_reason": None},
    ])
    doc = _doc(db_session, tenant, proc, doc_type=None)

    res = aplicar_classificacao(db_session, doc, "matricula")

    assert res.item_vinculado == "matricula"
    assert doc.checklist_item_id == "matricula"      # lado do documento (#71)
    cl = db_session.query(ProcessChecklist).filter(
        ProcessChecklist.process_id == proc.id).first()
    assert cl.items[0]["status"] == "received"       # lado do checklist
    assert cl.items[0]["document_id"] == doc.id


def test_sem_checklist_nao_quebra(db_session):
    tenant, proc = _seed(db_session)
    doc = _doc(db_session, tenant, proc, doc_type=None)

    res = aplicar_classificacao(db_session, doc, "matricula")

    assert res.gravado is True
    assert res.item_vinculado is None


# ---------------------------------------------------------------------------
# Backfill
# ---------------------------------------------------------------------------

def test_dry_run_nao_grava_nada(db_session):
    tenant, proc = _seed(db_session)
    doc = _doc(db_session, tenant, proc, doc_type=None)

    rel = planejar_backfill(db_session, process_ids=[proc.id], executar=False)

    assert rel.executado is False
    assert rel.candidatos == 1
    assert rel.resultados[0].tipo_proposto == "matricula"
    assert rel.resultados[0].gravado is False
    assert doc.document_type is None                 # intacto
    assert "[dry-run]" in rel.resultados[0].motivo


def test_execute_grava_e_vincula(db_session):
    tenant, proc = _seed(db_session)
    _checklist(db_session, tenant, proc, [
        {"id": "matricula", "label": "Matrícula", "doc_type": "matricula",
         "required": True, "status": "pending", "document_id": None,
         "waiver_reason": None},
    ])
    doc = _doc(db_session, tenant, proc, doc_type=None)

    rel = planejar_backfill(db_session, process_ids=[proc.id], executar=True)

    assert rel.executado is True
    assert len(rel.gravados) == 1
    assert doc.document_type == "matricula"
    assert len(rel.vinculados) == 1


def test_backfill_preserva_tipo_existente(db_session):
    """O backfill em massa respeita a mesma decisão do caminho ao vivo."""
    tenant, proc = _seed(db_session)
    doc = _doc(db_session, tenant, proc, doc_type="ccir", texto=TEXTO_MATRICULA)

    rel = planejar_backfill(db_session, process_ids=[proc.id], executar=True)

    # Nem entra no escopo: a query filtra por document_type NULL/vazio.
    assert rel.candidatos == 0
    assert doc.document_type == "ccir"


def test_documento_sem_texto_e_contado_a_parte(db_session):
    """Sem texto não há o que classificar — precisa de OCR antes, e isso aparece."""
    tenant, proc = _seed(db_session)
    _doc(db_session, tenant, proc, doc_type=None, texto="")

    rel = planejar_backfill(db_session, process_ids=[proc.id], executar=False)

    assert rel.candidatos == 0
    assert rel.sem_texto == 1


def test_texto_mudo_nao_gera_tipo(db_session):
    tenant, proc = _seed(db_session)
    doc = _doc(db_session, tenant, proc, doc_type=None, texto=TEXTO_MUDO)

    rel = planejar_backfill(db_session, process_ids=[proc.id], executar=True)

    assert rel.candidatos == 1
    assert len(rel.gravados) == 0
    assert doc.document_type is None
    assert len(rel.sem_tipo_definido) == 1


def test_backfill_multiplos_tipos(db_session):
    tenant, proc = _seed(db_session)
    d1 = _doc(db_session, tenant, proc, doc_type=None, texto=TEXTO_MATRICULA)
    d2 = _doc(db_session, tenant, proc, doc_type=None, texto=TEXTO_CCIR)

    rel = planejar_backfill(db_session, process_ids=[proc.id], executar=True)

    assert d1.document_type == "matricula"
    assert d2.document_type == "ccir"
    assert len(rel.gravados) == 2


def test_escopo_obrigatorio(db_session):
    import pytest
    with pytest.raises(ValueError, match="escopo obrigatório"):
        planejar_backfill(db_session, executar=False)


def test_isolamento_por_tenant(db_session):
    """Backfill por tenant não toca documento de outro tenant."""
    tenant_a, proc_a = _seed(db_session)
    tenant_b, proc_b = _seed(db_session)
    doc_b = _doc(db_session, tenant_b, proc_b, doc_type=None)

    rel = planejar_backfill(db_session, tenant_id=tenant_a.id, executar=True)

    assert rel.candidatos == 0
    assert doc_b.document_type is None


# ---------------------------------------------------------------------------
# Armadilha de persistência do JSON (achado durante o #70)
# ---------------------------------------------------------------------------

def test_marcacao_do_checklist_persiste_de_verdade(db_session):
    """A marcação tem de sobreviver ao flush + reload, não só existir em memória.

    `ProcessChecklist.items` é `Column(JSON)` sem `MutableList`; o padrão antigo
    (`items = list(...)` → mutar dicts compartilhados → reatribuir) nunca deixava
    o objeto dirty. O teste anterior passava olhando o objeto em memória; este
    expira a sessão e relê do banco, que é o que o consultor vê depois do F5.
    """
    tenant, proc = _seed(db_session)
    _checklist(db_session, tenant, proc, [
        {"id": "matricula", "label": "Matrícula", "doc_type": "matricula",
         "required": True, "status": "pending", "document_id": None,
         "waiver_reason": None},
    ])
    doc = _doc(db_session, tenant, proc, doc_type=None)

    aplicar_classificacao(db_session, doc, "matricula")
    db_session.flush()
    db_session.expire_all()

    recarregado = db_session.query(ProcessChecklist).filter(
        ProcessChecklist.process_id == proc.id).first()
    assert recarregado.items[0]["status"] == "received"
    assert recarregado.items[0]["document_id"] == doc.id


def test_marcar_recebido_e_reverter_persistem(db_session):
    """Cobre os outros helpers que sofriam da mesma armadilha."""
    from app.services.checklist_engine import mark_item_pending, mark_item_received

    tenant, proc = _seed(db_session)
    cl = _checklist(db_session, tenant, proc, [
        {"id": "car", "label": "CAR", "doc_type": "car", "required": True,
         "status": "pending", "document_id": None, "waiver_reason": None},
    ])

    assert mark_item_received(cl, "car", 4242) is True
    db_session.flush()
    db_session.expire_all()
    recarregado = db_session.query(ProcessChecklist).filter(
        ProcessChecklist.process_id == proc.id).first()
    assert recarregado.items[0]["status"] == "received"
    assert recarregado.items[0]["document_id"] == 4242

    assert mark_item_pending(recarregado, "car") is True
    db_session.flush()
    db_session.expire_all()
    de_novo = db_session.query(ProcessChecklist).filter(
        ProcessChecklist.process_id == proc.id).first()
    assert de_novo.items[0]["status"] == "pending"
    assert de_novo.items[0]["document_id"] is None


def test_dispensa_persiste(db_session):
    from app.services.checklist_engine import mark_item_waived

    tenant, proc = _seed(db_session)
    cl = _checklist(db_session, tenant, proc, [
        {"id": "itr", "label": "ITR", "doc_type": "itr", "required": True,
         "status": "pending", "document_id": None, "waiver_reason": None},
    ])

    assert mark_item_waived(cl, "itr", "cliente isento") is True
    db_session.flush()
    db_session.expire_all()
    recarregado = db_session.query(ProcessChecklist).filter(
        ProcessChecklist.process_id == proc.id).first()
    assert recarregado.items[0]["status"] == "waived"
    assert recarregado.items[0]["waiver_reason"] == "cliente isento"
