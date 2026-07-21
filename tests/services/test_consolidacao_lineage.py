"""Lineage, âncora por INCRA e varredura de aceites perdidos (caso 15).

Cada teste aqui trava um dos três achados da investigação de 20/07.
"""

from __future__ import annotations

from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
from app.models.matricula import Matricula
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.services.consolidacao_lineage import (
    ancorar_por_incra,
    norm_incra,
    registrar_lineage_campo,
    registrar_lineage_criacao,
    varrer_aceites_perdidos,
)

_SEQ = {"n": 0}


def _seed(db_session):
    _SEQ["n"] += 1
    n = _SEQ["n"]
    tenant = Tenant(name=f"Lineage {n}")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(tenant_id=tenant.id, full_name="C", email=f"lin{n}@example.com",
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
    # Documento real: o staging tem FK para documents.
    doc = Document(
        tenant_id=tenant.id, process_id=proc.id,
        original_file_name='d.pdf', filename='d.pdf',
        content_type='application/pdf', storage_key=f'lin/{tenant.id}/{n}',
        document_type='matricula', ocr_status=OcrStatus.done,
    )
    db_session.add(doc)
    db_session.flush()
    proc._doc_id = doc.id
    return tenant, proc, prop


def _mat(db_session, tenant, prop, numero, incra=None):
    m = Matricula(tenant_id=tenant.id, property_id=prop.id,
                  numero_matricula=numero, codigo_incra_sncr=incra)
    db_session.add(m)
    db_session.flush()
    return m


def _staging(db_session, tenant, proc, **kw):
    row = ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=proc.id,
        document_id=kw.get("document_id") or getattr(proc, "_doc_id", None),
        field_name=kw.get("field_name", "campo"),
        field_value=kw.get("field_value", {"value": "x"}),
        status=kw.get("status", ExtractedFieldStatus.aceito),
        target_entity=kw.get("target_entity", "matricula"),
        target_field=kw.get("target_field", "numero_matricula"),
        matricula_hint=kw.get("matricula_hint"),
    )
    db_session.add(row)
    db_session.flush()
    return row


# ---------------------------------------------------------------------------
# Normalização (Ficha 08 §8)
# ---------------------------------------------------------------------------

def test_incra_do_caso_15_casa_apesar_da_formatacao():
    """CCIR pontua, ITR agrupa diferente — é o mesmo código."""
    assert norm_incra("000.051.123.390-9") == norm_incra("000051.123390-9")
    assert norm_incra("951.048.549.371-0") == norm_incra("951048.549371-0")


def test_incra_aceita_dict_do_staging():
    assert norm_incra({"value": "951.048.549.371-0"}) == "9510485493710"


def test_incra_vazio():
    assert norm_incra(None) == ""
    assert norm_incra("") == ""
    assert norm_incra("abc") == ""


def test_codigos_diferentes_nao_casam():
    assert norm_incra("000.051.123.390-9") != norm_incra("951.048.549.371-0")


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------

def test_lineage_registra_de_onde_a_matricula_nasceu(db_session):
    """A pergunta que a investigação do caso 15 não respondeu sem arqueologia."""
    tenant, proc, prop = _seed(db_session)
    mat = _mat(db_session, tenant, prop, "2923")
    origem = _staging(db_session, tenant, proc, matricula_hint="2923")

    registrar_lineage_criacao(mat, staging=origem)

    assert mat.lineage["criada_por"]["staging_id"] == origem.id
    assert mat.lineage["criada_por"]["document_id"] == origem.document_id
    assert mat.lineage["criada_por"]["numero_matricula"] == "2923"


def test_lineage_por_campo(db_session):
    tenant, proc, prop = _seed(db_session)
    mat = _mat(db_session, tenant, prop, "6776")
    linha = _staging(db_session, tenant, proc, target_field="nirf_cib")

    registrar_lineage_campo(mat, "nirf_cib", linha, extra="ancorado_por_incra")

    assert mat.lineage["campos"]["nirf_cib"]["staging_id"] == linha.id
    assert mat.lineage["campos"]["nirf_cib"]["via"] == "ancorado_por_incra"


def test_lineage_sem_staging_nao_quebra(db_session):
    tenant, proc, prop = _seed(db_session)
    mat = _mat(db_session, tenant, prop, "1")
    registrar_lineage_criacao(mat, staging=None, motivo="manual")
    assert mat.lineage["criada_por"]["motivo"] == "manual"
    assert mat.lineage["criada_por"]["staging_id"] is None


# ---------------------------------------------------------------------------
# Âncora por INCRA — o caso limpo vincula, o resto não
# ---------------------------------------------------------------------------

def test_ancora_vincula_no_caso_limpo(db_session):
    """ITR do caso 15: um código, uma matrícula → vincula."""
    tenant, proc, prop = _seed(db_session)
    alvo = _mat(db_session, tenant, prop, "6776", incra="951.048.549.371-0")
    _mat(db_session, tenant, prop, "2923", incra="000.051.123.390-9")

    r = ancorar_por_incra(db_session, tenant_id=tenant.id, property_id=prop.id,
                          codigos_do_documento=["951048.549371-0"])

    assert r.vinculavel is True
    assert r.matricula.id == alvo.id


def test_ancora_nao_vincula_com_incra_divergente_no_documento(db_session):
    """Documento com dois INCRAs diferentes = alerta, nunca vínculo automático."""
    tenant, proc, prop = _seed(db_session)
    _mat(db_session, tenant, prop, "6776", incra="951.048.549.371-0")

    r = ancorar_por_incra(db_session, tenant_id=tenant.id, property_id=prop.id,
                          codigos_do_documento=["951048.549371-0", "000051.123390-9"])

    assert r.divergente is True
    assert r.vinculavel is False


def test_ancora_nao_vincula_quando_ambiguo(db_session):
    """Mesmo INCRA em duas matrículas: o sistema não escolhe por conta própria."""
    tenant, proc, prop = _seed(db_session)
    _mat(db_session, tenant, prop, "6776", incra="951.048.549.371-0")
    _mat(db_session, tenant, prop, "6777", incra="951048549371-0")

    r = ancorar_por_incra(db_session, tenant_id=tenant.id, property_id=prop.id,
                          codigos_do_documento=["951.048.549.371-0"])

    assert r.ambiguo is True
    assert r.vinculavel is False
    assert len(r.candidatas) == 2


def test_ancora_sem_casamento(db_session):
    tenant, proc, prop = _seed(db_session)
    _mat(db_session, tenant, prop, "6776", incra="951.048.549.371-0")

    r = ancorar_por_incra(db_session, tenant_id=tenant.id, property_id=prop.id,
                          codigos_do_documento=["111.111.111.111-1"])

    assert r.vinculavel is False
    assert r.matricula is None


def test_ancora_ignora_matricula_desativada(db_session):
    from datetime import UTC, datetime
    tenant, proc, prop = _seed(db_session)
    m = _mat(db_session, tenant, prop, "6776", incra="951.048.549.371-0")
    m.deactivated_at = datetime.now(UTC)
    db_session.flush()

    r = ancorar_por_incra(db_session, tenant_id=tenant.id, property_id=prop.id,
                          codigos_do_documento=["951.048.549.371-0"])

    assert r.vinculavel is False


# ---------------------------------------------------------------------------
# Varredura — as duas classes de aceite perdido
# ---------------------------------------------------------------------------

def test_vtn_aceito_sem_coluna_grita(db_session):
    """Caso (a): `matriculas.vtn` nao existe — o aceite nunca teve onde ir."""
    tenant, proc, prop = _seed(db_session)
    _staging(db_session, tenant, proc, field_name="vtn", target_field="vtn",
             matricula_hint="6776")

    perdidos = varrer_aceites_perdidos(db_session, tenant_id=tenant.id,
                                       process_id=proc.id)

    assert len(perdidos) == 1
    assert perdidos[0].motivo == "sem_coluna"
    assert "campo sem destino" in perdidos[0].detalhe


def test_nirf_aceito_sem_dono_vira_pendencia(db_session):
    """Caso (b): a coluna existe, o aceite e valido — falta ANCORA.

    Uma varredura so de schema deixaria isto passar em silencio.
    """
    tenant, proc, prop = _seed(db_session)
    _staging(db_session, tenant, proc, field_name="nirf_cib",
             target_field="nirf_cib", matricula_hint=None)

    perdidos = varrer_aceites_perdidos(db_session, tenant_id=tenant.id,
                                       process_id=proc.id)

    assert len(perdidos) == 1
    assert perdidos[0].motivo == "sem_dono"
    assert "aguardando vinculo" in perdidos[0].detalhe.replace("í", "i")


def test_aceito_com_destino_e_dono_nao_aparece(db_session):
    tenant, proc, prop = _seed(db_session)
    _staging(db_session, tenant, proc, field_name="numero_matricula",
             target_field="numero_matricula", matricula_hint="6776")

    assert varrer_aceites_perdidos(db_session, tenant_id=tenant.id,
                                   process_id=proc.id) == []


def test_rejeitado_nao_entra_na_varredura(db_session):
    tenant, proc, prop = _seed(db_session)
    _staging(db_session, tenant, proc, field_name="vtn", target_field="vtn",
             status=ExtractedFieldStatus.rejeitado, matricula_hint="6776")

    assert varrer_aceites_perdidos(db_session, tenant_id=tenant.id,
                                   process_id=proc.id) == []
