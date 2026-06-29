"""Saneamento RETROATIVO do staging (caso 13): aplica a regra do #81 ao staging
JÁ gravado. Cobre dedup de formato, lixo em código, colapso de lista,
preservação de decisão do consultor e idempotência."""

import pytest

from app.models.client import Client, ClientStatus, ClientType
from app.models.extracted_field_staging import (
    ExtractedFieldStaging,
    ExtractedFieldStatus,
)
from app.models.process import Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.services.ficha01_extraction import sanear_staging_process


@pytest.fixture
def caso(db_session):
    """Tenant + cliente + imóvel + processo prontos para receber staging sujo."""
    tenant = Tenant(name="T-saneamento")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(tenant_id=tenant.id, full_name="C", email="c.saneamento@example.com",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add(cli)
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Faz")
    db_session.add(prop)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="C", process_type="prad", status=ProcessStatus.triagem)
    db_session.add(proc)
    db_session.flush()
    return tenant, proc


def _add(db, tenant, proc, *, field_name, value, unidade=None, source="matricula",
         hint=None, status=ExtractedFieldStatus.pendente, target_field=None, target_entity="matricula"):
    fv = {"value": value}
    if unidade:
        fv["unidade"] = unidade
    row = ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=proc.id, source_doc_type=source,
        field_name=field_name, field_value=fv, target_entity=target_entity,
        target_field=target_field or field_name, matricula_hint=hint, status=status,
    )
    db.add(row)
    db.flush()
    return row


def _rows(db, tenant, proc, field_name):
    return (db.query(ExtractedFieldStaging)
            .filter(ExtractedFieldStaging.tenant_id == tenant.id,
                    ExtractedFieldStaging.process_id == proc.id,
                    ExtractedFieldStaging.field_name == field_name)
            .all())


# ── 2a — duplicata de formato ──────────────────────────────────────────────
def test_remove_duplicata_de_formato(db_session, caso):
    tenant, proc = caso
    _add(db_session, tenant, proc, field_name="area_ha", value="349,9022", unidade="ha", hint="6776")
    _add(db_session, tenant, proc, field_name="area_ha", value="349.9022", unidade="ha", hint="6776")
    _add(db_session, tenant, proc, field_name="area_ha", value="660,6561", unidade="ha", hint="4698")
    _add(db_session, tenant, proc, field_name="area_ha", value="14.44", unidade="ha", hint="4698")
    _add(db_session, tenant, proc, field_name="area_ha", value="14,4400", unidade="ha", hint="4698")

    res = sanear_staging_process(db_session, tenant_id=tenant.id, process_id=proc.id)

    areas = _rows(db_session, tenant, proc, "area_ha")
    # 6776: 349,9022≡349.9022 → 1; 4698: 660,6561 (1) + 14.44≡14,4400 (1) → 2
    assert len(areas) == 3
    assert res.duplicates_removed == 2


def test_valores_realmente_diferentes_nao_fundem(db_session, caso):
    tenant, proc = caso
    _add(db_session, tenant, proc, field_name="area_ha", value="100,00", unidade="ha", hint="6776")
    _add(db_session, tenant, proc, field_name="area_ha", value="200,00", unidade="ha", hint="6776")
    sanear_staging_process(db_session, tenant_id=tenant.id, process_id=proc.id)
    assert len(_rows(db_session, tenant, proc, "area_ha")) == 2  # divergência real preservada


def test_fontes_diferentes_nao_fundem(db_session, caso):
    tenant, proc = caso
    _add(db_session, tenant, proc, field_name="area_ha", value="349,9022", unidade="ha", hint="6776", source="ccir")
    _add(db_session, tenant, proc, field_name="area_ha", value="349.9022", unidade="ha", hint="6776", source="sigef")
    sanear_staging_process(db_session, tenant_id=tenant.id, process_id=proc.id)
    # mesma área, fontes distintas: NÃO funde (cada fonte é insumo da matriz)
    assert len(_rows(db_session, tenant, proc, "area_ha")) == 2


# ── 2b — lixo em campo de código ───────────────────────────────────────────
def test_remove_lixo_em_campo_de_codigo(db_session, caso):
    tenant, proc = caso
    _add(db_session, tenant, proc, field_name="numero_car", value="Certidão de Embargo",
         hint="6776", target_entity="imovel", target_field="car_code")
    _add(db_session, tenant, proc, field_name="codigo_certificacao",
         value="Coordenadas não disponíveis no documento.", hint="6776")
    _add(db_session, tenant, proc, field_name="codigo_certificacao",
         value="029231.2.0006776-55", hint="4698")  # código válido fica

    res = sanear_staging_process(db_session, tenant_id=tenant.id, process_id=proc.id)

    assert res.garbage_removed == 2
    assert _rows(db_session, tenant, proc, "numero_car") == []
    cods = _rows(db_session, tenant, proc, "codigo_certificacao")
    assert len(cods) == 1
    assert cods[0].field_value["value"] == "029231.2.0006776-55"


def test_lixo_com_decisao_do_consultor_e_preservado(db_session, caso):
    tenant, proc = caso
    _add(db_session, tenant, proc, field_name="numero_car", value="Certidão de Embargo",
         hint="6776", status=ExtractedFieldStatus.rejeitado, target_entity="imovel", target_field="car_code")
    res = sanear_staging_process(db_session, tenant_id=tenant.id, process_id=proc.id)
    assert res.garbage_removed == 0
    assert res.decisions_preserved == 1
    assert len(_rows(db_session, tenant, proc, "numero_car")) == 1  # decisão não apagada


# ── 2c — lista repetida ────────────────────────────────────────────────────
def test_colapsa_pendencias_rat_repetidas(db_session, caso):
    tenant, proc = caso
    for _ in range(4):
        _add(db_session, tenant, proc, field_name="pendencias_rat",
             value=[{"categoria": "APP"}, {"categoria": "RL"}],
             source="rat", hint=None, target_entity="imovel", target_field="regulatory_issues")
    res = sanear_staging_process(db_session, tenant_id=tenant.id, process_id=proc.id)
    assert len(_rows(db_session, tenant, proc, "pendencias_rat")) == 1
    assert res.lists_collapsed == 3


def test_colapsa_onus_repetidos_por_matricula(db_session, caso):
    tenant, proc = caso
    _add(db_session, tenant, proc, field_name="onus", value="Hipoteca R.05", hint="6776")
    _add(db_session, tenant, proc, field_name="onus", value="Hipoteca (R.05) - Banco X", hint="6776")
    _add(db_session, tenant, proc, field_name="onus", value="Penhor", hint="4698")  # outra matrícula fica
    res = sanear_staging_process(db_session, tenant_id=tenant.id, process_id=proc.id)
    onus = _rows(db_session, tenant, proc, "onus")
    assert len(onus) == 2  # 1 por matrícula
    assert res.lists_collapsed == 1


# ── duplicata DECIDIDA: mantém a canônica que carrega a decisão ─────────────
def test_duplicata_decidida_mantem_a_decisao(db_session, caso):
    tenant, proc = caso
    pend = _add(db_session, tenant, proc, field_name="area_ha", value="349.9022", unidade="ha", hint="6776")
    aceito = _add(db_session, tenant, proc, field_name="area_ha", value="349,9022", unidade="ha", hint="6776",
                  status=ExtractedFieldStatus.aceito)
    sanear_staging_process(db_session, tenant_id=tenant.id, process_id=proc.id)
    sobrevivente = _rows(db_session, tenant, proc, "area_ha")
    assert len(sobrevivente) == 1
    assert sobrevivente[0].id == aceito.id  # a decidida venceu; a pendente saiu
    assert sobrevivente[0].status == ExtractedFieldStatus.aceito
    assert pend.id not in [r.id for r in sobrevivente]


# ── idempotência: rodar 2× não remove nada na 2ª passada ───────────────────
def test_idempotente(db_session, caso):
    tenant, proc = caso
    _add(db_session, tenant, proc, field_name="area_ha", value="349,9022", unidade="ha", hint="6776")
    _add(db_session, tenant, proc, field_name="area_ha", value="349.9022", unidade="ha", hint="6776")
    _add(db_session, tenant, proc, field_name="numero_car", value="Certidão de Embargo",
         hint="6776", target_entity="imovel", target_field="car_code")

    r1 = sanear_staging_process(db_session, tenant_id=tenant.id, process_id=proc.id)
    assert r1.total_removed == 2
    r2 = sanear_staging_process(db_session, tenant_id=tenant.id, process_id=proc.id)
    assert r2.total_removed == 0
    assert r2.rows_before == r2.rows_after


# ── dry-run: relata mas não grava ──────────────────────────────────────────
def test_dry_run_nao_grava(db_session, caso):
    tenant, proc = caso
    _add(db_session, tenant, proc, field_name="area_ha", value="349,9022", unidade="ha", hint="6776")
    _add(db_session, tenant, proc, field_name="area_ha", value="349.9022", unidade="ha", hint="6776")
    res = sanear_staging_process(db_session, tenant_id=tenant.id, process_id=proc.id, dry_run=True)
    assert res.duplicates_removed == 1
    assert len(_rows(db_session, tenant, proc, "area_ha")) == 2  # nada removido de fato
