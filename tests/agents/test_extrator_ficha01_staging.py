# ADR-069: isolated legacy algorithm/projection tests; authenticated execution is tested in tests/e2e/test_evidence_execution.py.
"""Ficha 01 / FASE 2 — o ExtratorAgent grava staging SEM alterar extracted_fields.

Mocka o LLM legado (``extract_document_fields``) e o LLM estruturado
(``ficha01_extraction._extract_structured``) — o ``extract_and_stage`` real roda e
persiste as linhas. Prova: (1) o shape de ``extracted_fields`` continua igual;
(2) o staging é populado com os campos certos por tipo + matricula_hint.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.agents.base import AgentContext, AgentRegistry
from app.models.client import Client
from app.models.document import Document, OcrStatus
from app.models.extracted_field_staging import ExtractedFieldStaging
from app.models.process import Process, ProcessStatus
from app.models.tenant import Tenant
from app.models.user import User

# ADR-064 (âncora): o texto do documento precisa CONTER os valores que o
# mock diz ter extraído — senão eles viram linha barrada, sem destino, e o
# teste passaria a medir o gate em vez do mapeamento por tipo.
_CAR_TEXT = (
    "RECIBO DE INSCRIÇÃO no Cadastro Ambiental Rural — Município Uirapuru/GO\n"
    "Número do CAR: GO-5221080-A1B2C3  ·  Área declarada: 1010,5583 ha\n"
    "Matrículas vinculadas: 4.698 (12/03/2001) e 6.776 (05/08/2010), Livro 2, CRI\n"
)

_LEGACY_FIELDS = {
    "numero_car": "GO-5221080-A1B2C3",
    "area_total_ha": 1010.5583,
    "municipio": "Uirapuru",
    "confidence": {"numero_car": "high"},
}

_STRUCTURED = {
    "numero_car": "GO-5221080-A1B2C3",
    "area_declarada_ha": 1010.5583,
    "municipio": "Uirapuru",
    "uf": "GO",
    "matriculas": [
        {"numero": "4.698", "data": "12/03/2001", "livro_folha": "L2", "cartorio": "CRI"},
        {"numero": "6.776", "data": "05/08/2010", "livro_folha": "L2", "cartorio": "CRI"},
    ],
    "confidence": {"numero_car": "high"},
}


@pytest.fixture
def seeded(db_session):
    tenant = Tenant(name="Ficha02 Agent Tenant")
    db_session.add(tenant)
    db_session.flush()
    user = User(
        email="f2@example.com", full_name="F2", hashed_password="x" * 60,
        tenant_id=tenant.id, is_active=True,
    )
    client = Client(tenant_id=tenant.id, full_name="Cli", email="cli2@example.com")
    db_session.add_all([user, client])
    db_session.flush()
    process = Process(
        tenant_id=tenant.id, client_id=client.id, title="Caso CAR",
        process_type="prad", status=ProcessStatus.triagem,
    )
    db_session.add(process)
    db_session.flush()
    doc = Document(
        tenant_id=tenant.id, process_id=process.id, client_id=client.id,
        original_file_name="recibo_car.pdf", filename="recibo_car.pdf",
        content_type="application/pdf", storage_key=f"tenant-{tenant.id}/recibo.pdf",
        document_type="car", ocr_status=OcrStatus.done, extracted_text=_CAR_TEXT,
    )
    db_session.add(doc)
    db_session.flush()
    return tenant, user, process, doc


def test_extrator_grava_staging_sem_mexer_extracted_fields(seeded, db_session):
    # Inc2: staging referencia observao; preview achatado deixou de ser contrato.
    import json
    from hashlib import sha256

    from app.core.ai_gateway import AIResponse
    from app.models.evidence import EvidenceVersion
    tenant, user, process, doc = seeded
    doc.checksum_sha256 = sha256(b"controlled CAR PDF bytes").hexdigest()
    payload = {"observacoes": [{"predicado": "car_area_ha", "valor": 1010.5583,
        "unidade": "ha", "trecho": "Área declarada: 1010,5583 ha"}]}
    response = AIResponse(content=json.dumps(payload), model_used="controlled", provider="test",
        tokens_in=10, tokens_out=10, cost_usd=0, duration_ms=1)
    ctx = AgentContext(tenant_id=tenant.id, user_id=user.id, process_id=process.id,
        session=db_session, metadata={"document_id": doc.id})
    with patch("app.core.ai_gateway.complete", return_value=response) as gateway:
        result = AgentRegistry.create("extrator", ctx)._run_legacy_unconnected()
    assert result.success, result.error
    assert gateway.call_count == 1
    assert "extracted_fields" not in result.data
    rows = db_session.query(ExtractedFieldStaging).filter_by(document_id=doc.id).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.ai_job_id is not None
    observation = db_session.get(EvidenceVersion, row.observacao_ref)
    assert observation.kind == "observacao"
    assert observation.content["attributes"]["normalized"]["valor"] == row.field_value["value"]
    assert (row.source_doc_type, row.target_entity, row.target_field) == ("car", "property", "area_grafica_ha")


# ---------------------------------------------------------------------------
# Fase 1 (N1) — planta lida como CCIR (caso 13, docs 228/230): classificador
# honesto + nota visível de processamento (item 3, P12).
# ---------------------------------------------------------------------------

# Shape real do doc 228: uma PLANTA topográfica que cita "CCIR" na legenda
# como referência do imóvel — antes da Fase 1, a menção fraca "ccir" roubava
# a classificação (caía em `ccir`, gerava matrícula espúria).
_PLANTA_COM_CCIR_NA_LEGENDA = """
PLANTA TOPOGRÁFICA — LEVANTAMENTO PLANIALTIMÉTRICO
Fazenda São Jorge — Lote 1B
Escala gráfica 1:10.000 — Norte magnético
Sistema de referência: SIRGAS 2000, UTM Fuso 22S

LEGENDA:
Ref. CCIR: 000.051.123.390-9
Área total: 660,6561 ha
Perímetro conforme levantamento topográfico de campo.
"""


def test_planta_com_ccir_na_legenda_nao_vira_ccir(seeded, db_session):
    """Item 1 (N1): precedência específica-antes-de-genérica — a menção fraca
    de "CCIR" na legenda de uma planta não sequestra mais a classificação."""
    from app.services.ficha01_extraction import classify_doc_type

    assert classify_doc_type(_PLANTA_COM_CCIR_NA_LEGENDA, current="outro") == "planta_topografica"


def test_planta_nao_grava_staging_cadastral_e_deixa_nota_visivel(seeded, db_session):
    # Inc2: preservar observao durvel sem impor destino cadastral nem segunda extrao.
    import json
    from hashlib import sha256

    from app.core.ai_gateway import AIResponse
    from app.models.evidence import EvidenceVersion
    tenant, user, process, doc = seeded
    doc.document_type = "outro"
    doc.extracted_text = _PLANTA_COM_CCIR_NA_LEGENDA
    doc.checksum_sha256 = sha256(b"controlled document bytes").hexdigest()
    payload = {"observacoes": [{"predicado": "descricao_peca", "valor": "material recebido",
        "trecho": _PLANTA_COM_CCIR_NA_LEGENDA.strip().splitlines()[0]}]}
    response = AIResponse(content=json.dumps(payload), model_used="controlled", provider="test",
        tokens_in=10, tokens_out=10, cost_usd=0, duration_ms=1)
    ctx = AgentContext(tenant_id=tenant.id, user_id=user.id, process_id=process.id,
        session=db_session, metadata={"document_id": doc.id})
    with patch("app.core.ai_gateway.complete", return_value=response):
        result = AgentRegistry.create("extrator", ctx)._run_legacy_unconnected()
    assert result.success, result.error
    assert db_session.query(ExtractedFieldStaging).filter_by(document_id=doc.id).count() == 0
    observation = db_session.query(EvidenceVersion).filter_by(tenant_id=tenant.id, kind="observacao").one()
    assert observation.source_record["especie_documental"] == "arquivo_geoespacial"
    assert observation.content["attributes"]["predicate"] == "descricao_peca"
    assert "revisão" in doc.extraction_status


# ---------------------------------------------------------------------------
# Fase 1 (N2) — auto de infração é FATO DE PASSIVO, não campo cadastral.
# ---------------------------------------------------------------------------

_AUTO_INFRACAO_TEXT = """
AUTO DE INFRAÇÃO Nº 123456-D
IBAMA — Instituto Brasileiro do Meio Ambiente

02. Autuado: José da Silva
03. CPF: 111.222.333-44
13. Descrição da infração: Supressão de vegetação nativa sem autorização,
área de 3,2 hectares.
14. Enquadramento legal: Lei 9.605/98, art. 70
19. Valor da multa: R$ 15.000,00
24. Data da autuação: 10/03/2025
25. Data de vencimento: 10/04/2025
"""

_AUTO_INFRACAO_FATO = {
    "numero_auto": "123456-D",
    "orgao_autuante": "IBAMA",
    "autuado_nome": "José da Silva",
    "autuado_cpf": "111.222.333-44",
    "data_autuacao": "10/03/2025",
    "tipo_penalidade": "multa",
    "descricao_infracao": "Supressão de vegetação nativa sem autorização, área de 3,2 hectares.",
    "enquadramento_legal": "Lei 9.605/98, art. 70",
    "coordenadas": None,
    "valor_multa": "15.000,00",
    "data_vencimento": "10/04/2025",
    "confidence": {},
    "coordenadas_latlong": None,
}


def test_auto_infracao_nao_gera_staging_cadastral_e_grava_fato_no_job(seeded, db_session):
    # Inc2: preservar observao durvel sem impor destino cadastral nem segunda extrao.
    import json
    from hashlib import sha256

    from app.core.ai_gateway import AIResponse
    from app.models.evidence import EvidenceVersion
    tenant, user, process, doc = seeded
    doc.document_type = "outro"
    doc.extracted_text = _AUTO_INFRACAO_TEXT
    doc.checksum_sha256 = sha256(b"controlled document bytes").hexdigest()
    payload = {"observacoes": [{"predicado": "auto_infracao", "valor": "material recebido",
        "trecho": _AUTO_INFRACAO_TEXT.strip().splitlines()[0]}]}
    response = AIResponse(content=json.dumps(payload), model_used="controlled", provider="test",
        tokens_in=10, tokens_out=10, cost_usd=0, duration_ms=1)
    ctx = AgentContext(tenant_id=tenant.id, user_id=user.id, process_id=process.id,
        session=db_session, metadata={"document_id": doc.id})
    with patch("app.core.ai_gateway.complete", return_value=response):
        result = AgentRegistry.create("extrator", ctx)._run_legacy_unconnected()
    assert result.success, result.error
    assert db_session.query(ExtractedFieldStaging).filter_by(document_id=doc.id).count() == 0
    observation = db_session.query(EvidenceVersion).filter_by(tenant_id=tenant.id, kind="observacao").one()
    assert observation.source_record["especie_documental"] == "peca_orgao"
    assert observation.content["attributes"]["predicate"] == "auto_infracao"
    assert "revisão" in doc.extraction_status
