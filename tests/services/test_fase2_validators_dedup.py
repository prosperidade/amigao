"""Fase 2 robusta (2026-06-06) — 4b (validação de formato por campo) e
4c (deduplicação). Valores reais do caso São Jorge.
"""

from unittest.mock import patch

from app.models.extracted_field_staging import ExtractedFieldStaging
from app.services.ficha01_extraction import build_staging_fields, extract_and_stage
from app.services.field_validators import check_format

# --- 4b: validadores de formato -------------------------------------------

def test_codigo_sigef_valido():
    assert check_format("codigo_certificacao", "029231.2.0006776-55") is True


def test_codigo_sigef_com_vertice_grudado_reprova():
    """O bug real: código + detalhe de vértice grudado → fora do formato."""
    ruim = "029231.2.0006776-55 inicia-se no vértice ZNXA-V-203"
    assert check_format("codigo_certificacao", ruim) is False


def test_numero_car_valido():
    assert check_format("numero_car", "GO-5220009-3B9F4F19156B455D9EE371CAEF57623C") is True


def test_area_valida_e_invalida():
    assert check_format("area_registrada_ha", "349,9022") is True
    assert check_format("area_registrada_ha", "1.010,7113") is True
    assert check_format("area_registrada_ha", "n/d") is False


def test_campo_sem_validador_retorna_none():
    assert check_format("denominacao", "Fazenda Shangri-lá") is None
    assert check_format("codigo_certificacao", ["lista"]) is None  # não-escalar


def test_build_rebaixa_confidence_e_preserva_bruto():
    """Valor fora do formato → confidence 'low' + format_ok False + bruto intacto."""
    bruto = "029231.2.0006776-55 inicia-se no vértice ZNXA-V-203"
    parsed = {"codigo_certificacao": bruto, "confidence": {"codigo_certificacao": "high"}}
    rows = build_staging_fields("sigef", parsed)
    cod = [r for r in rows if r.field_name == "codigo_certificacao"][0]
    assert cod.confidence == "low"
    assert cod.field_value["format_ok"] is False
    assert cod.field_value["value"] == bruto  # valor bruto PRESERVADO


def test_build_mantem_confidence_quando_formato_ok():
    parsed = {"codigo_certificacao": "029231.2.0006776-55", "confidence": {"codigo_certificacao": "high"}}
    rows = build_staging_fields("sigef", parsed)
    cod = [r for r in rows if r.field_name == "codigo_certificacao"][0]
    assert cod.confidence == "high"
    assert "format_ok" not in cod.field_value


# --- 4c: deduplicação na persistência -------------------------------------

def _tenant(db_session):
    from app.models.tenant import Tenant
    t = Tenant(name="T Fase2 Dedup")
    db_session.add(t)
    db_session.flush()
    return t


def test_reextracao_identica_nao_duplica(db_session):
    """Triplicação: re-rodar a extração do mesmo doc não recria linhas."""
    tenant = _tenant(db_session)
    canned = {
        "numero_matricula": "6776",
        "area_registrada_ha": "349,9022",
        "denominacao": "Fazenda Shangri-lá (Parte 2)",
        "confidence": {"numero_matricula": "high"},
    }
    with patch("app.services.ficha01_extraction._extract_structured", return_value=canned):
        r1 = extract_and_stage(
            text="...", doc_type="matricula", tenant_id=tenant.id, db_session=db_session,
        )
        r2 = extract_and_stage(
            text="...", doc_type="matricula", tenant_id=tenant.id, db_session=db_session,
        )
    assert r1.rows_written >= 2
    assert r2.rows_written == 0  # tudo já existia → dedup
    total = (
        db_session.query(ExtractedFieldStaging)
        .filter(ExtractedFieldStaging.tenant_id == tenant.id)
        .count()
    )
    assert total == r1.rows_written  # sem duplicatas


def test_valor_diferente_mesma_fonte_e_mantido(db_session):
    """Divergência interna (valor diferente da mesma fonte) NÃO é deduplicada."""
    tenant = _tenant(db_session)
    v1 = {"denominacao": "Fazenda Shangri-lá (Parte 2)", "confidence": {}}
    v2 = {"denominacao": "Fazenda São Jorge Lote 01-C", "confidence": {}}
    with patch("app.services.ficha01_extraction._extract_structured", return_value=v1):
        extract_and_stage(text="...", doc_type="matricula", tenant_id=tenant.id,
                          db_session=db_session)
    with patch("app.services.ficha01_extraction._extract_structured", return_value=v2):
        extract_and_stage(text="...", doc_type="matricula", tenant_id=tenant.id,
                          db_session=db_session)
    denoms = (
        db_session.query(ExtractedFieldStaging)
        .filter(ExtractedFieldStaging.tenant_id == tenant.id,
                ExtractedFieldStaging.field_name == "denominacao")
        .all()
    )
    assert len(denoms) == 2  # duas denominações distintas mantidas
