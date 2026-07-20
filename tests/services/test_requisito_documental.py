"""Fonte única de requisitos documentais — Ficha 08 §2 e §7.

O teste-âncora é `test_caso_real_andre_certidao_enviada_nunca_ausente`: reproduz o
processo 15 de produção (certidões de inteiro teor 317/318 anexadas, OCR done,
`numero_matricula` já no staging, nenhuma `Matricula` materializada) e trava o
comportamento que faltava — com o documento na base, o requisito NUNCA é
"ausente".
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.extracted_field_staging import ExtractedFieldStaging
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.services.requisito_documental import (
    RequisitoStatus,
    avaliar_requisitos,
    contar_pendentes,
    requisito_de_doc_type,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SEQ = {"n": 0}


def _seed_processo(db_session):
    _SEQ["n"] += 1
    n = _SEQ["n"]
    tenant = Tenant(name=f"ReqDoc Tenant {n}")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(tenant_id=tenant.id, full_name="Cliente", email=f"reqdoc{n}@example.com",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add(cli)
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda São Jorge")
    db_session.add(prop)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Caso", process_type="car", status=ProcessStatus.triagem,
                   demand_type=DemandType.car)
    db_session.add(proc)
    db_session.flush()
    return tenant, proc, prop


def _add_doc(db_session, tenant, proc, *, doc_type, ocr=OcrStatus.done,
             filename="doc.pdf", expires_at=None):
    _SEQ["n"] += 1
    doc = Document(
        tenant_id=tenant.id, process_id=proc.id,
        original_file_name=filename, filename=filename,
        content_type="application/pdf",
        storage_key=f"k/{tenant.id}/{proc.id}/{_SEQ['n']}",
        document_type=doc_type, ocr_status=ocr, expires_at=expires_at,
    )
    db_session.add(doc)
    db_session.flush()
    return doc


def _add_campo(db_session, tenant, proc, doc, field_name, value="x"):
    db_session.add(ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=proc.id, document_id=doc.id,
        field_name=field_name, field_value={"value": value},
    ))
    db_session.flush()


# ---------------------------------------------------------------------------
# Mapa de vocabulário (divergência D3 da auditoria)
# ---------------------------------------------------------------------------

def test_vocabulario_certidao_inteiro_teor_e_matricula():
    """`certidao_inteiro_teor` casa com o requisito matrícula.

    Era o matching por igualdade exata de string que quebrava aqui.
    """
    assert requisito_de_doc_type("certidao_inteiro_teor") == "matricula"
    assert requisito_de_doc_type("certidao_matricula") == "matricula"
    assert requisito_de_doc_type("matricula") == "matricula"


def test_vocabulario_cpf_cnpj_e_identidade():
    """A CNH anexada satisfaz o requisito de identidade — bug irmão, não relatado."""
    assert requisito_de_doc_type("cpf_cnpj") == "identidade"
    assert requisito_de_doc_type("rg_cpf") == "identidade"
    assert requisito_de_doc_type("cnh") == "identidade"


def test_vocabulario_tipo_fora_dos_seis():
    assert requisito_de_doc_type("auto_infracao") is None
    assert requisito_de_doc_type("rat") is None          # RAT analisa o CAR, não É o CAR
    assert requisito_de_doc_type(None) is None
    assert requisito_de_doc_type("") is None


def test_licenca_ambiental_nao_e_o_setimo(db_session):
    """Ficha §6.4 está EM ABERTO — são 6 obrigatórios, não 7."""
    tenant, proc, _ = _seed_processo(db_session)
    res = avaliar_requisitos(db_session, proc.id, tenant.id)
    assert len(res) == 6
    assert "licenca_ambiental" not in res
    assert set(res) == {"matricula", "car", "ccir", "itr", "identidade", "planta_memorial"}


# ---------------------------------------------------------------------------
# O caso real
# ---------------------------------------------------------------------------

def test_caso_real_andre_certidao_enviada_nunca_ausente(db_session):
    """Processo 15 em prod: certidão de inteiro teor anexada, OCR done,
    `numero_matricula` no staging, ZERO `Matricula` materializada.

    Antes: o dossiê dizia "Matrícula do imóvel ausente" (severity error).
    Agora: SATISFEITO — o documento está na base e foi lido.
    """
    tenant, proc, _ = _seed_processo(db_session)
    doc = _add_doc(db_session, tenant, proc, doc_type="matricula",
                   filename="Certidão Inteiro Teor Mat. 6.776.pdf")
    _add_campo(db_session, tenant, proc, doc, "numero_matricula", "6.776")

    res = avaliar_requisitos(db_session, proc.id, tenant.id)["matricula"]

    assert res.status is RequisitoStatus.SATISFEITO
    assert res.status is not RequisitoStatus.AUSENTE
    assert res.tem_documento
    assert not res.pendente
    assert doc.id in res.document_ids
    assert "ausente" not in res.detalhe.lower()


def test_documento_recebido_sem_leitura_e_em_processamento(db_session):
    """Arquivo na base, OCR ainda rodando: honesto é "em processamento"."""
    tenant, proc, _ = _seed_processo(db_session)
    _add_doc(db_session, tenant, proc, doc_type="matricula", ocr=OcrStatus.processing)

    res = avaliar_requisitos(db_session, proc.id, tenant.id)["matricula"]

    assert res.status is RequisitoStatus.RECEBIDO_EM_PROCESSAMENTO
    assert res.tem_documento
    assert not res.pendente          # não é pendência de COLETA
    assert "em processamento" in res.detalhe


def test_ocr_done_mas_sem_staging_ainda_e_em_processamento(db_session):
    """OCR terminou mas o extrator não passou — ainda não há o que afirmar."""
    tenant, proc, _ = _seed_processo(db_session)
    _add_doc(db_session, tenant, proc, doc_type="matricula", ocr=OcrStatus.done)

    res = avaliar_requisitos(db_session, proc.id, tenant.id)["matricula"]
    assert res.status is RequisitoStatus.RECEBIDO_EM_PROCESSAMENTO


def test_sem_documento_nenhum_e_ausente(db_session):
    """Sem arquivo, "ausente" é a verdade — e continua sendo dita."""
    tenant, proc, _ = _seed_processo(db_session)
    res = avaliar_requisitos(db_session, proc.id, tenant.id)["matricula"]

    assert res.status is RequisitoStatus.AUSENTE
    assert not res.tem_documento
    assert res.pendente
    assert res.detalhe == "Matrícula: não recebido."


# ---------------------------------------------------------------------------
# Ficha §7.1 — presente ≠ completo
# ---------------------------------------------------------------------------

def test_itr_sem_diat_e_satisfeito_parcial_com_gap(db_session):
    """Ficha §7.1, caso real: ITR só com DIAC esconde a falta de VTN/área."""
    tenant, proc, _ = _seed_processo(db_session)
    doc = _add_doc(db_session, tenant, proc, doc_type="itr")
    _add_campo(db_session, tenant, proc, doc, "nirf_cib", "123")   # DIAC presente
    # `vtn` (DIAT) ausente de propósito

    res = avaliar_requisitos(db_session, proc.id, tenant.id)["itr"]

    assert res.status is RequisitoStatus.SATISFEITO_PARCIAL
    assert res.gaps == ["vtn"]
    assert res.tem_documento
    assert not res.pendente          # o arquivo chegou — não é pendência de coleta
    assert "incompleto" in res.detalhe


def test_itr_completo_e_satisfeito(db_session):
    tenant, proc, _ = _seed_processo(db_session)
    doc = _add_doc(db_session, tenant, proc, doc_type="itr")
    _add_campo(db_session, tenant, proc, doc, "nirf_cib", "123")
    _add_campo(db_session, tenant, proc, doc, "vtn", "500000")

    res = avaliar_requisitos(db_session, proc.id, tenant.id)["itr"]
    assert res.status is RequisitoStatus.SATISFEITO
    assert res.gaps == []


def test_melhor_documento_define_o_estado(db_session):
    """Um ITR completo não é rebaixado por outro incompleto anexado junto."""
    tenant, proc, _ = _seed_processo(db_session)
    incompleto = _add_doc(db_session, tenant, proc, doc_type="itr", filename="diac.pdf")
    _add_campo(db_session, tenant, proc, incompleto, "nirf_cib", "123")
    completo = _add_doc(db_session, tenant, proc, doc_type="itr", filename="completo.pdf")
    _add_campo(db_session, tenant, proc, completo, "vtn", "500000")

    res = avaliar_requisitos(db_session, proc.id, tenant.id)["itr"]
    assert res.status is RequisitoStatus.SATISFEITO
    assert len(res.document_ids) == 2


# ---------------------------------------------------------------------------
# Ficha §7.2 — satisfação por equivalência
# ---------------------------------------------------------------------------

def test_georref_embutido_na_matricula_satisfaz_planta_memorial(db_session):
    """Ficha §7.2, caso real Lote 01-B: o CCIR declara que não há SIGEF, mas a
    Matrícula traz georreferenciamento certificado. Não travar exigindo um
    arquivo que oficialmente não existe."""
    tenant, proc, _ = _seed_processo(db_session)
    mat = _add_doc(db_session, tenant, proc, doc_type="matricula")
    _add_campo(db_session, tenant, proc, mat, "numero_matricula", "4698")
    _add_campo(db_session, tenant, proc, mat, "codigo_certificacao", "281010000016-83")

    res = avaliar_requisitos(db_session, proc.id, tenant.id)["planta_memorial"]

    assert res.status is RequisitoStatus.SATISFEITO
    assert res.satisfeito_por == "matricula"
    assert not res.pendente
    assert "§7.2" in res.detalhe


def test_matricula_sem_georref_nao_supre_planta_memorial(db_session):
    """A equivalência exige georref CERTIFICADO — matrícula comum não basta."""
    tenant, proc, _ = _seed_processo(db_session)
    mat = _add_doc(db_session, tenant, proc, doc_type="matricula")
    _add_campo(db_session, tenant, proc, mat, "numero_matricula", "6776")

    res = avaliar_requisitos(db_session, proc.id, tenant.id)["planta_memorial"]
    assert res.status is RequisitoStatus.AUSENTE
    assert res.satisfeito_por is None


def test_sigef_proprio_prevalece_sobre_equivalencia(db_session):
    """Com arquivo SIGEF próprio, o requisito é satisfeito por ele mesmo."""
    tenant, proc, _ = _seed_processo(db_session)
    mat = _add_doc(db_session, tenant, proc, doc_type="matricula")
    _add_campo(db_session, tenant, proc, mat, "numero_matricula", "4698")
    _add_campo(db_session, tenant, proc, mat, "codigo_certificacao", "281010000016-83")
    sigef = _add_doc(db_session, tenant, proc, doc_type="sigef")
    _add_campo(db_session, tenant, proc, sigef, "codigo_certificacao", "281010000016-83")

    res = avaliar_requisitos(db_session, proc.id, tenant.id)["planta_memorial"]
    assert res.status is RequisitoStatus.SATISFEITO
    assert res.satisfeito_por is None
    assert res.document_ids == [sigef.id]


# ---------------------------------------------------------------------------
# Ficha §7.3 — vencido alerta, nunca trava
# ---------------------------------------------------------------------------

def test_documento_vencido_alerta_sem_rebaixar_estado(db_session):
    tenant, proc, _ = _seed_processo(db_session)
    vencido = datetime.now(UTC) - timedelta(days=30)
    doc = _add_doc(db_session, tenant, proc, doc_type="ccir",
                   filename="ccir.pdf", expires_at=vencido)
    _add_campo(db_session, tenant, proc, doc, "codigo_sncr_incra", "123")

    res = avaliar_requisitos(db_session, proc.id, tenant.id)["ccir"]

    assert res.status is RequisitoStatus.SATISFEITO   # NÃO rebaixa
    assert not res.pendente                            # NÃO trava
    assert len(res.alertas) == 1
    assert "vencido" in res.alertas[0]


def test_sem_data_de_validade_nao_gera_alerta(db_session):
    """"Nem todo CCIR tem vencimento; não assumir prazo fixo genérico" (§7.3)."""
    tenant, proc, _ = _seed_processo(db_session)
    doc = _add_doc(db_session, tenant, proc, doc_type="ccir", expires_at=None)
    _add_campo(db_session, tenant, proc, doc, "codigo_sncr_incra", "123")

    res = avaliar_requisitos(db_session, proc.id, tenant.id)["ccir"]
    assert res.alertas == []


# ---------------------------------------------------------------------------
# Contagem
# ---------------------------------------------------------------------------

def test_contar_pendentes_so_conta_ausentes(db_session):
    """Recebido-em-processamento e parcial NÃO são pendência de coleta."""
    tenant, proc, _ = _seed_processo(db_session)
    mat = _add_doc(db_session, tenant, proc, doc_type="matricula")
    _add_campo(db_session, tenant, proc, mat, "numero_matricula", "6776")
    _add_doc(db_session, tenant, proc, doc_type="cpf_cnpj", ocr=OcrStatus.processing)
    itr = _add_doc(db_session, tenant, proc, doc_type="itr")
    _add_campo(db_session, tenant, proc, itr, "nirf_cib", "1")

    res = avaliar_requisitos(db_session, proc.id, tenant.id)

    assert res["matricula"].status is RequisitoStatus.SATISFEITO
    assert res["identidade"].status is RequisitoStatus.RECEBIDO_EM_PROCESSAMENTO
    assert res["itr"].status is RequisitoStatus.SATISFEITO_PARCIAL
    # Faltam de fato: car, ccir, planta_memorial
    assert contar_pendentes(res) == 3


def test_isolamento_por_tenant(db_session):
    """Documento de outro tenant não satisfaz requisito nenhum."""
    tenant_a, proc_a, _ = _seed_processo(db_session)
    tenant_b, proc_b, _ = _seed_processo(db_session)
    doc = _add_doc(db_session, tenant_b, proc_b, doc_type="matricula")
    _add_campo(db_session, tenant_b, proc_b, doc, "numero_matricula", "999")

    res = avaliar_requisitos(db_session, proc_a.id, tenant_a.id)
    assert res["matricula"].status is RequisitoStatus.AUSENTE
