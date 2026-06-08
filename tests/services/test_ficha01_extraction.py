"""Ficha 01 / FASE 2 — classificação + extração estruturada por tipo → staging."""

from unittest.mock import patch

from app.models.extracted_field_staging import (
    ExtractedFieldStaging,
    ExtractedFieldStatus,
)
from app.services.ficha01_extraction import (
    build_staging_fields,
    classify_doc_type,
    extract_and_stage,
)

# ---------------------------------------------------------------------------
# Textos representativos do corpus São Jorge (equivalentes locais)
# ---------------------------------------------------------------------------

CAR_RECIBO_TEXT = """RECIBO DE INSCRIÇÃO no Cadastro Ambiental Rural (CAR/SICAR)
Número do CAR: GO-5221080-A1B2C3
Município: Uirapuru / UF: GO  Área declarada: 1010,5583 ha
Matrículas vinculadas:
 - Matrícula 4.698, registrada em 12/03/2001, Livro 2, Cartório de Registro de Imóveis de Uirapuru
 - Matrícula 6.776, registrada em 05/08/2010, Livro 2, Cartório de Registro de Imóveis de Uirapuru
"""

RAT_TEXT = """RELATÓRIO DE ANÁLISE TÉCNICA do CAR
Protocolo: GO-RAT-2025-000123  Número do CAR: GO-5221080-A1B2C3
Data de emissão: 10/02/2025  Situação: Pendente
Pendências identificadas:
 1. Sobreposição com APA estadual
 2. Supressões de vegetação pós-2008
"""

MATRICULA_TEXT = """CERTIDÃO DE MATRÍCULA — Registro de Imóveis de Uirapuru
Matrícula nº 4.698, Livro 2, Fl. 33. Área registrada: 660,6561 ha.
Proprietário: Fulano de Tal, CPF 000.000.000-00.
"""


# ---------------------------------------------------------------------------
# classify_doc_type
# ---------------------------------------------------------------------------

def test_classify_car_recibo():
    assert classify_doc_type(CAR_RECIBO_TEXT) == "car"


def test_classify_rat_antes_de_car():
    # RAT compartilha termos com o recibo do CAR; deve classificar como rat.
    assert classify_doc_type(RAT_TEXT) == "rat"


def test_classify_matricula():
    assert classify_doc_type(MATRICULA_TEXT) == "matricula"


def test_classify_respeita_tipo_especifico_existente():
    # current já específico → não sobrescreve pela heurística.
    assert classify_doc_type("texto qualquer", current="ccir") == "ccir"


def test_classify_sem_match_cai_em_outro():
    assert classify_doc_type("documento genérico sem pistas", current="outro") == "outro"


# ---------------------------------------------------------------------------
# build_staging_fields — mapeamento por tipo
# ---------------------------------------------------------------------------

def test_build_car_lista_matriculas_com_hint():
    parsed = {
        "numero_car": "GO-5221080-A1B2C3",
        "area_declarada_ha": 1010.5583,
        "municipio": "Uirapuru",
        "uf": "GO",
        "matriculas": [
            {"numero": "4.698", "data": "12/03/2001", "livro_folha": "Livro 2", "cartorio": "CRI Uirapuru"},
            {"numero": "6.776", "data": "05/08/2010", "livro_folha": "Livro 2", "cartorio": "CRI Uirapuru"},
        ],
        "confidence": {"numero_car": "high", "area_declarada_ha": "medium"},
    }
    rows = build_staging_fields("car", parsed)
    by_name = [r.field_name for r in rows]
    assert "numero_car" in by_name
    # area com unidade
    area = next(r for r in rows if r.field_name == "area_declarada_ha")
    assert area.field_value == {"value": 1010.5583, "unidade": "ha"}
    assert area.confidence == "medium"
    # 2 matrículas listadas com hint
    listadas = [r for r in rows if r.field_name == "matricula_listada"]
    assert len(listadas) == 2
    # caso #12 item B: hint normalizado (ponto de milhar removido) "4.698" → "4698".
    assert {r.matricula_hint for r in listadas} == {"4698", "6776"}
    assert all(r.target_entity == "matricula" for r in listadas)


def test_build_rat_pendencias_estruturado():
    parsed = {
        "protocolo": "GO-RAT-2025-000123",
        "situacao": "Pendente",
        "pendencias": [
            {"categoria": "Sobreposição APA", "detalhamento": "...", "recomendacao": "...", "atendimento": None},
            {"categoria": "Supressão pós-2008", "detalhamento": "...", "recomendacao": "...", "atendimento": None},
        ],
        "confidence": {},
    }
    rows = build_staging_fields("rat", parsed)
    names = [r.field_name for r in rows]
    assert "protocolo" in names
    pend = next(r for r in rows if r.field_name == "pendencias_rat")
    assert isinstance(pend.field_value["value"], list)
    assert len(pend.field_value["value"]) == 2
    assert pend.target_entity == "imovel"


def test_build_matricula_hint_proprio_numero():
    parsed = {
        "numero_matricula": "4.698",
        "area_registrada_ha": 660.6561,
        "proprietarios": [{"nome": "Fulano", "cpf": "000.000.000-00"}],
        "confidence": {},
    }
    rows = build_staging_fields("matricula", parsed)
    assert rows  # não vazio
    # caso #12 item B: "4.698" normalizado para "4698" (sem ponto de milhar).
    assert all(r.matricula_hint == "4698" for r in rows)
    area = next(r for r in rows if r.field_name == "area_registrada_ha")
    assert area.field_value == {"value": 660.6561, "unidade": "ha"}


def test_build_pula_campos_vazios():
    parsed = {"numero_car": "X", "municipio": None, "uf": "", "matriculas": [], "confidence": {}}
    rows = build_staging_fields("car", parsed)
    names = [r.field_name for r in rows]
    assert names == ["numero_car"]  # só o preenchido


# ---------------------------------------------------------------------------
# extract_and_stage — persistência (LLM mockado)
# ---------------------------------------------------------------------------

def _tenant(db_session):
    from app.models.tenant import Tenant
    t = Tenant(name="Ficha02 Tenant")
    db_session.add(t)
    db_session.flush()
    return t


def test_extract_and_stage_persiste_linhas(db_session):
    tenant = _tenant(db_session)
    canned = {
        "numero_car": "GO-5221080-A1B2C3",
        "area_declarada_ha": 1010.5583,
        "matriculas": [
            {"numero": "4.698", "data": "12/03/2001", "livro_folha": "L2", "cartorio": "CRI"},
            {"numero": "6.776", "data": "05/08/2010", "livro_folha": "L2", "cartorio": "CRI"},
        ],
        "confidence": {"numero_car": "high"},
    }
    with patch("app.services.ficha01_extraction._extract_structured", return_value=canned):
        result = extract_and_stage(
            text=CAR_RECIBO_TEXT,
            doc_type="car",
            tenant_id=tenant.id,
            db_session=db_session,
            process_id=None,
            document_id=None,
            ai_job_id=None,
            created_by_agent="extrator",
        )

    assert result.rows_written >= 3  # numero_car + area + 2 matriculas
    rows = (
        db_session.query(ExtractedFieldStaging)
        .filter(ExtractedFieldStaging.tenant_id == tenant.id)
        .all()
    )
    assert len(rows) == result.rows_written
    assert all(r.source_doc_type == "car" for r in rows)
    assert all(r.status == ExtractedFieldStatus.pendente for r in rows)
    assert all(r.created_by_agent == "extrator" for r in rows)
    hints = {r.matricula_hint for r in rows if r.field_name == "matricula_listada"}
    assert hints == {"4698", "6776"}  # caso #12 item B: hint normalizado


def test_extract_and_stage_falha_extracao_nao_grava(db_session):
    tenant = _tenant(db_session)
    with patch("app.services.ficha01_extraction._extract_structured", return_value=None):
        result = extract_and_stage(
            text="x", doc_type="car", tenant_id=tenant.id, db_session=db_session,
        )
    assert result.rows_written == 0
    assert db_session.query(ExtractedFieldStaging).count() == 0


def test_extract_and_stage_tipo_sem_schema():
    # "outro" não tem schema de staging → no-op sem tocar no banco.
    result = extract_and_stage(
        text="x", doc_type="outro", tenant_id=1, db_session=None,
    )
    assert result.rows_written == 0
    assert result.skipped_reason
