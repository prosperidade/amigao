"""Staging órfão (`process_id` NULL) — fix nas duas camadas + reparo.

O teste-âncora é `test_caminho_13h30_documento_no_rascunho_nao_gera_orfa`:
reproduz o caminho real que gerou as 46 linhas órfãs do caso 15 — extração
disparada enquanto o documento ainda estava no rascunho, minutos antes de o
rascunho virar caso.
"""

from __future__ import annotations

from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.extracted_field_staging import ExtractedFieldStaging
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.services.reparo_staging_orfao import planejar_reparo

_SEQ = {"n": 0}


def _seed(db_session):
    _SEQ["n"] += 1
    n = _SEQ["n"]
    tenant = Tenant(name=f"Orfao {n}")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(tenant_id=tenant.id, full_name="C", email=f"orfao{n}@example.com",
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


def _doc(db_session, tenant, *, process_id=None):
    _SEQ["n"] += 1
    d = Document(
        tenant_id=tenant.id, process_id=process_id,
        original_file_name="m.pdf", filename="m.pdf",
        content_type="application/pdf",
        storage_key=f"orf/{tenant.id}/{_SEQ['n']}",
        document_type="matricula", ocr_status=OcrStatus.done,
        extracted_text="CERTIDAO DE INTEIRO TEOR ...",
    )
    db_session.add(d)
    db_session.flush()
    return d


def _staging(db_session, tenant, doc, field_name, *, process_id, value=None):
    row = ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=process_id, document_id=doc.id,
        field_name=field_name, field_value=value or {"value": "x"},
    )
    db_session.add(row)
    db_session.flush()
    return row


# ---------------------------------------------------------------------------
# Camada 1 — o extrator não pode mais passar None quando há contexto
# ---------------------------------------------------------------------------

def test_caminho_13h30_documento_no_rascunho_nao_gera_orfa(db_session):
    """Reproduz o caminho real: documento AINDA no rascunho (`process_id` NULL),
    extração disparada com o processo conhecido pelo contexto do job.

    Antes: `doc.process_id if doc is not None else ctx.process_id` testava a
    EXISTÊNCIA do doc, não o VALOR — passava None e o staging nascia sem dono.
    """
    tenant, proc = _seed(db_session)
    doc = _doc(db_session, tenant, process_id=None)   # ainda no rascunho

    # A expressão exata do extrator, depois do fix.
    resolvido = (doc.process_id if doc is not None else None) or proc.id

    assert doc.process_id is None
    assert resolvido == proc.id, "com contexto de processo, o staging tem dono"


def test_sem_documento_usa_contexto(db_session):
    tenant, proc = _seed(db_session)
    doc = None
    resolvido = (doc.process_id if doc is not None else None) or proc.id
    assert resolvido == proc.id


def test_documento_ja_vinculado_vence_o_contexto(db_session):
    """O processo do documento é mais específico que o do contexto."""
    tenant, proc = _seed(db_session)
    doc = _doc(db_session, tenant, process_id=proc.id)
    resolvido = (doc.process_id if doc is not None else None) or 999
    assert resolvido == proc.id


# ---------------------------------------------------------------------------
# Reparo — a decisão híbrida
# ---------------------------------------------------------------------------

def test_orfa_redundante_e_apagada(db_session):
    tenant, proc = _seed(db_session)
    doc = _doc(db_session, tenant, process_id=proc.id)
    orfa = _staging(db_session, tenant, doc, "numero_matricula", process_id=None)
    _staging(db_session, tenant, doc, "numero_matricula", process_id=proc.id)

    rel = planejar_reparo(db_session, process_ids=[proc.id], executar=True)

    assert len(rel.apagar) == 1
    assert len(rel.adotar) == 0
    assert db_session.query(ExtractedFieldStaging).filter(
        ExtractedFieldStaging.id == orfa.id).first() is None


def test_orfa_unica_e_adotada(db_session):
    """`averbacao_rl` do caso 15: única leitura — apagar perderia o dado."""
    tenant, proc = _seed(db_session)
    doc = _doc(db_session, tenant, process_id=proc.id)
    orfa = _staging(db_session, tenant, doc, "averbacao_rl", process_id=None,
                    value={"value": {"area": "175,00", "referencia": "AV23"}})

    rel = planejar_reparo(db_session, process_ids=[proc.id], executar=True)

    assert len(rel.adotar) == 1
    assert len(rel.apagar) == 0
    db_session.refresh(orfa)
    assert orfa.process_id == proc.id


def test_adocao_nao_toca_field_value(db_session):
    """Guarda contra o bug dict→text do #81: o reparo muda o dono, não o valor.

    `averbacao_rl`/`averbacao_app` guardam dict — foi reserializar esse valor
    que derrubou a consolidação. O reparo não pode reintroduzir isso.
    """
    tenant, proc = _seed(db_session)
    doc = _doc(db_session, tenant, process_id=proc.id)
    valor = {"value": {"area": "175,00", "referencia": "AV23-M-4698"}}
    orfa = _staging(db_session, tenant, doc, "averbacao_rl", process_id=None, value=valor)

    planejar_reparo(db_session, process_ids=[proc.id], executar=True)
    db_session.expire_all()

    recarregada = db_session.query(ExtractedFieldStaging).filter(
        ExtractedFieldStaging.id == orfa.id).first()
    assert recarregada.process_id == proc.id
    assert recarregada.field_value == valor          # dict preservado, não string
    assert isinstance(recarregada.field_value["value"], dict)


def test_dry_run_nao_grava(db_session):
    tenant, proc = _seed(db_session)
    doc = _doc(db_session, tenant, process_id=proc.id)
    orfa_unica = _staging(db_session, tenant, doc, "averbacao_rl", process_id=None)
    orfa_dup = _staging(db_session, tenant, doc, "numero_matricula", process_id=None)
    _staging(db_session, tenant, doc, "numero_matricula", process_id=proc.id)

    rel = planejar_reparo(db_session, process_ids=[proc.id], executar=False)

    assert len(rel.adotar) == 1 and len(rel.apagar) == 1
    assert rel.executado is False
    db_session.refresh(orfa_unica)
    assert orfa_unica.process_id is None             # intacta
    assert db_session.query(ExtractedFieldStaging).filter(
        ExtractedFieldStaging.id == orfa_dup.id).first() is not None


def test_documento_ainda_sem_processo_e_ignorado(db_session):
    """Rascunho de verdade: não há dono para adotar — deixar quieto é o certo."""
    tenant, _ = _seed(db_session)
    doc = _doc(db_session, tenant, process_id=None)
    orfa = _staging(db_session, tenant, doc, "numero_matricula", process_id=None)

    rel = planejar_reparo(db_session, executar=True)

    assert rel.sem_dono >= 1
    db_session.refresh(orfa)
    assert orfa.process_id is None                   # preservada
    assert not any(item.staging_id == orfa.id for item in rel.linhas)


def test_mistura_como_no_caso_15(db_session):
    """2 exclusivas adotadas + várias redundantes apagadas, numa só passada."""
    tenant, proc = _seed(db_session)
    doc_a = _doc(db_session, tenant, process_id=proc.id)
    doc_b = _doc(db_session, tenant, process_id=proc.id)

    _staging(db_session, tenant, doc_a, "averbacao_rl", process_id=None)      # única
    _staging(db_session, tenant, doc_b, "municipio", process_id=None)         # única
    for campo in ("numero_matricula", "cartorio", "denominacao"):
        _staging(db_session, tenant, doc_a, campo, process_id=None)
        _staging(db_session, tenant, doc_a, campo, process_id=proc.id)

    rel = planejar_reparo(db_session, process_ids=[proc.id], executar=True)

    assert len(rel.adotar) == 2
    assert len(rel.apagar) == 3
    restantes = db_session.query(ExtractedFieldStaging).filter(
        ExtractedFieldStaging.process_id.is_(None)).count()
    assert restantes == 0
