"""TASK 2 — limpeza do staging na origem (caso 13): dedup de formato, lixo em
campo de código, colapso de campo-lista."""

import app.services.ficha01_extraction as fe
from app.services.ficha01_extraction import (
    _dedup_token,
    _is_garbage_for_code,
    _numeric_dedup_key,
    build_staging_fields,
)


# ── 2a — dedup de formato numérico (349.9022 == 349,9022) ──────────────────
def test_numeric_dedup_key_iguala_formatos():
    assert _numeric_dedup_key("349.9022") == _numeric_dedup_key("349,9022")
    assert _numeric_dedup_key("1.010,7113") == _numeric_dedup_key("1010.7113")
    assert _numeric_dedup_key("14,4400 módulos") == _numeric_dedup_key("14.44 módulos")
    assert _numeric_dedup_key("660,6561") != _numeric_dedup_key("349,9022")
    assert _numeric_dedup_key("texto") is None


def test_dedup_token_por_tipo():
    # numérico (com unidade) normaliza formato
    assert _dedup_token("area_ha", "349.9022", "ha") == _dedup_token("area_ha", "349,9022", "ha")
    # campo-lista colapsa
    assert _dedup_token("pendencias_rat", [1, 2, 3], None) == _dedup_token("pendencias_rat", [9], None)
    assert _dedup_token("onus", "6 itens", None) == _dedup_token("onus", "1 item", None)
    # texto comum não colapsa
    assert _dedup_token("cartorio", "A", None) != _dedup_token("cartorio", "B", None)


# ── 2b — lixo (frase/título) em campo que espera código ────────────────────
def test_is_garbage_for_code():
    lixo = [
        "Certidão de Embargo",
        "Coordenadas não disponíveis no documento.",
        "Plano de Recuperação de Área Degradada (PRAD)",
        "Área embargada em São João D'Aliança, GO.",
        "Memorial descritivo da área",
    ]
    for v in lixo:
        assert _is_garbage_for_code(v) is True, v
    validos = [
        "340dbe7b-dc78-417e-992a-18a6c944c36f",
        "029231.2.0006776-55",
        "GO-5220009-3B9F4F19156B455D9EE371CAEF57623C",
        "281010000016-83",
    ]
    for v in validos:
        assert _is_garbage_for_code(v) is False, v


def test_build_descarta_lixo_em_codigo_certificacao():
    parsed = {
        "area_georreferenciada_ha": "349,9022",
        "codigo_certificacao": "Certidão de Embargo",  # lixo → não vira staging
        "numero_matricula": "6776",
    }
    rows = build_staging_fields("sigef", parsed)
    assert not any(r.field_name == "codigo_certificacao" for r in rows)
    assert any(r.field_name == "area_georreferenciada_ha" for r in rows)


def test_build_mantem_codigo_valido():
    parsed = {"codigo_certificacao": "340dbe7b-dc78-417e-992a-18a6c944c36f", "numero_matricula": "6776"}
    rows = build_staging_fields("sigef", parsed)
    assert any(r.field_name == "codigo_certificacao" for r in rows)


# ── 2c — campo-lista não vira N linhas (1 por campo/hint) ──────────────────
def test_build_colapsa_onus_lista():
    # mesmo doc, 'onus' repetido em formatos diferentes do mesmo conjunto → 1 linha
    parsed = {"numero_matricula": "4698", "onus": "6 itens"}
    rows = build_staging_fields("matricula", parsed)
    onus = [r for r in rows if r.field_name == "onus"]
    assert len(onus) == 1


# ── 2a (cross-run, DB real) — re-extração em formato diferente não duplica ──
def test_extract_and_stage_nao_duplica_formato(db_session, monkeypatch):
    from app.models.client import Client, ClientStatus, ClientType
    from app.models.extracted_field_staging import ExtractedFieldStaging
    from app.models.process import Process, ProcessStatus
    from app.models.property import Property
    from app.models.tenant import Tenant

    tenant = Tenant(name="T-limpeza")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(tenant_id=tenant.id, full_name="C", email="c.limpeza@example.com",
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

    # 1ª extração: formato BR (mock substitui o LLM inteiro)
    monkeypatch.setattr(fe, "_extract_structured",
                        lambda text, dt: {"area_ha": "349,9022", "numero_matricula": "6776"})
    fe.extract_and_stage(text="x", doc_type="ccir", tenant_id=tenant.id, db_session=db_session, process_id=proc.id)
    # 2ª extração (re-run): MESMO dado em formato US
    monkeypatch.setattr(fe, "_extract_structured",
                        lambda text, dt: {"area_ha": "349.9022", "numero_matricula": "6776"})
    fe.extract_and_stage(text="x", doc_type="ccir", tenant_id=tenant.id, db_session=db_session, process_id=proc.id)

    areas = db_session.query(ExtractedFieldStaging).filter(
        ExtractedFieldStaging.tenant_id == tenant.id,
        ExtractedFieldStaging.field_name == "area_ha",
    ).all()
    assert len(areas) == 1   # antes: 2 (349,9022 + 349.9022)
