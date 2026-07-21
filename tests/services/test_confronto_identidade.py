"""Confronto de identidade + cadeia pré-decisão — o painel que faltava no caso 15.

O teste-âncora é `test_caso_15_ccir_2923_versus_certidao_4698`: reproduz
exatamente a situação que produziu o erro, e prova que agora o sistema coloca os
dois números lado a lado e declara qual é a fonte jurídica.
"""

from __future__ import annotations

from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.services.confronto_identidade import detectar_confronto

_SEQ = {"n": 0}


def _seed(db_session):
    _SEQ["n"] += 1
    n = _SEQ["n"]
    tenant = Tenant(name=f"Confronto {n}")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(tenant_id=tenant.id, full_name="C", email=f"conf{n}@example.com",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add(cli)
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda Sao Jorge")
    db_session.add(prop)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Caso", process_type="car", status=ProcessStatus.triagem,
                   demand_type=DemandType.car)
    db_session.add(proc)
    db_session.flush()
    return tenant, proc, prop


def _doc(db_session, tenant, proc, doc_type):
    _SEQ["n"] += 1
    d = Document(tenant_id=tenant.id, process_id=proc.id,
                 original_file_name="d.pdf", filename="d.pdf",
                 content_type="application/pdf",
                 storage_key=f"conf/{tenant.id}/{_SEQ['n']}",
                 document_type=doc_type, ocr_status=OcrStatus.done)
    db_session.add(d)
    db_session.flush()
    return d


def _linha(db_session, tenant, proc, doc, campo, valor, *, status=None):
    row = ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=proc.id, document_id=doc.id,
        field_name=campo, field_value={"value": valor},
        status=status or ExtractedFieldStatus.pendente,
        target_entity="matricula", target_field=campo,
        source_doc_type=doc.document_type,
    )
    db_session.add(row)
    db_session.flush()
    return row


# ---------------------------------------------------------------------------
# O caso real
# ---------------------------------------------------------------------------

def test_caso_15_ccir_2923_versus_certidao_4698(db_session):
    """CCIR declara o número defasado; a certidão, o atual.

    A tela nunca colocou os dois lado a lado — e o consultor escolheu o errado
    sem saber que escolhia identidade jurídica.
    """
    tenant, proc, prop = _seed(db_session)
    ccir = _doc(db_session, tenant, proc, "ccir")
    cert = _doc(db_session, tenant, proc, "matricula")
    _linha(db_session, tenant, proc, ccir, "numero_matricula", "2.923")
    _linha(db_session, tenant, proc, cert, "numero_matricula", "4698")

    c = detectar_confronto(db_session, tenant_id=tenant.id, process_id=proc.id)

    assert c.ha_confronto is True
    assert c.prevalente.numero == "4698"                  # certidão vence
    assert c.prevalente.rotulo_fonte == "certidão de matrícula"
    assert "fonte jurídica" in c.regra
    assert "§5.1" in c.regra
    assert "2.923" in c.regra                              # nomeia o perdedor


def test_linha_rejeitada_continua_no_confronto(db_session):
    """Deliberado: no caso 15 o número CORRETO estava na linha rejeitada.

    Esconder o rejeitado seria esconder a evidência de que a decisão precisa ser
    revista — exatamente o que impediria a re-decisão da Fase 3.
    """
    tenant, proc, prop = _seed(db_session)
    ccir = _doc(db_session, tenant, proc, "ccir")
    cert = _doc(db_session, tenant, proc, "matricula")
    _linha(db_session, tenant, proc, ccir, "numero_matricula", "2.923",
           status=ExtractedFieldStatus.aceito)
    _linha(db_session, tenant, proc, cert, "numero_matricula", "4698",
           status=ExtractedFieldStatus.rejeitado)

    c = detectar_confronto(db_session, tenant_id=tenant.id, process_id=proc.id)

    assert c.ha_confronto is True
    assert c.prevalente.numero == "4698"
    assert c.prevalente.status == "rejeitado"


def test_cadeia_proposta_antes_da_decisao(db_session):
    """O registro_anterior liga os dois números: mesma terra, não dois imóveis.

    A proposta nasce da LEITURA do staging — antes de qualquer decisão. No caso
    15 ela existia e foi destruída pela rejeição antes de virar sinal.
    """
    tenant, proc, prop = _seed(db_session)
    ccir = _doc(db_session, tenant, proc, "ccir")
    cert = _doc(db_session, tenant, proc, "matricula")
    _linha(db_session, tenant, proc, ccir, "numero_matricula", "2.923")
    _linha(db_session, tenant, proc, cert, "numero_matricula", "4698")
    _linha(db_session, tenant, proc, cert, "registro_anterior", "2.923")

    c = detectar_confronto(db_session, tenant_id=tenant.id, process_id=proc.id)

    assert c.cadeia_proposta is not None
    assert c.cadeia_proposta["vigente"] == "4698"
    assert c.cadeia_proposta["historica"] == "2.923"
    assert "mesma terra" in c.cadeia_proposta["texto"]


def test_cadeia_proposta_mesmo_com_registro_anterior_rejeitado(db_session):
    """A rejeição não pode matar o sinal que evitaria a própria rejeição errada."""
    tenant, proc, prop = _seed(db_session)
    ccir = _doc(db_session, tenant, proc, "ccir")
    cert = _doc(db_session, tenant, proc, "matricula")
    _linha(db_session, tenant, proc, ccir, "numero_matricula", "2.923")
    _linha(db_session, tenant, proc, cert, "numero_matricula", "4698",
           status=ExtractedFieldStatus.rejeitado)
    _linha(db_session, tenant, proc, cert, "registro_anterior", "2.923",
           status=ExtractedFieldStatus.rejeitado)

    c = detectar_confronto(db_session, tenant_id=tenant.id, process_id=proc.id)

    assert c.cadeia_proposta is not None


# ---------------------------------------------------------------------------
# Sem confronto
# ---------------------------------------------------------------------------

def test_numeros_iguais_nao_geram_confronto(db_session):
    """'2.923' e '2923' são o mesmo número — formatação não é divergência."""
    tenant, proc, prop = _seed(db_session)
    ccir = _doc(db_session, tenant, proc, "ccir")
    cert = _doc(db_session, tenant, proc, "matricula")
    _linha(db_session, tenant, proc, ccir, "numero_matricula", "2.923")
    _linha(db_session, tenant, proc, cert, "numero_matricula", "2923")

    c = detectar_confronto(db_session, tenant_id=tenant.id, process_id=proc.id)

    assert c.ha_confronto is False
    assert c.regra == ""


def test_um_documento_so_nao_gera_confronto(db_session):
    tenant, proc, prop = _seed(db_session)
    cert = _doc(db_session, tenant, proc, "matricula")
    _linha(db_session, tenant, proc, cert, "numero_matricula", "4698")

    c = detectar_confronto(db_session, tenant_id=tenant.id, process_id=proc.id)

    assert c.ha_confronto is False


def test_sem_staging_nao_quebra(db_session):
    tenant, proc, prop = _seed(db_session)
    c = detectar_confronto(db_session, tenant_id=tenant.id, process_id=proc.id)
    assert c.ha_confronto is False
    assert c.fontes == []


def test_hierarquia_ccir_vence_itr(db_session):
    """Sem certidão no caso, o CCIR ainda vence o ITR (Ficha 08 §5.1)."""
    tenant, proc, prop = _seed(db_session)
    itr = _doc(db_session, tenant, proc, "itr")
    ccir = _doc(db_session, tenant, proc, "ccir")
    _linha(db_session, tenant, proc, itr, "numero_matricula", "1111")
    _linha(db_session, tenant, proc, ccir, "numero_matricula", "2222")

    c = detectar_confronto(db_session, tenant_id=tenant.id, process_id=proc.id)

    assert c.prevalente.numero == "2222"
    assert c.prevalente.rotulo_fonte == "CCIR"
