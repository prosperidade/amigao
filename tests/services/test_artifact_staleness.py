"""REV-001 (Frente H, ADR-068) — aviso, nunca regeneração.

Gate da frente: gerar diagnóstico (ou rota) → subir documento novo (ou mudar
uma decisão da Conferência) → o artefato aparece marcado desatualizado com
razão e data; nada é regenerado, nada é apagado.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.proposal import Proposal
from app.models.regulatory import RegulatoryDiagnosis
from app.models.rota import Rota, RotaStatus
from app.models.tenant import Tenant
from app.services.artifact_staleness import (
    desatualizacao_diagnostico,
    desatualizacao_proposta,
    desatualizacao_rota,
)

_SEQ = {"n": 0}


def _seed(db_session):
    _SEQ["n"] += 1
    n = _SEQ["n"]
    tenant = Tenant(name=f"Staleness {n}")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(
        tenant_id=tenant.id, full_name=f"Cliente {n}", email=f"stale{n}@example.com",
        client_type=ClientType.pf, status=ClientStatus.active,
    )
    db_session.add(cli)
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda Teste")
    db_session.add(prop)
    db_session.flush()
    proc = Process(
        tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
        title="Caso", process_type="car", status=ProcessStatus.triagem,
        demand_type=DemandType.car,
    )
    db_session.add(proc)
    db_session.flush()
    return tenant, proc


def _doc(db_session, tenant, proc, *, created_at=None):
    _SEQ["n"] += 1
    d = Document(
        tenant_id=tenant.id, process_id=proc.id,
        original_file_name="novo.pdf", filename="novo.pdf",
        content_type="application/pdf",
        storage_key=f"stale/{tenant.id}/{_SEQ['n']}",
        ocr_status=OcrStatus.done,
    )
    db_session.add(d)
    db_session.flush()
    if created_at is not None:
        d.created_at = created_at
        db_session.flush()
    return d


# ---------------------------------------------------------------------------
# Diagnóstico
# ---------------------------------------------------------------------------


def test_diagnostico_sem_novidade_nao_esta_desatualizado(db_session):
    tenant, proc = _seed(db_session)
    diag = RegulatoryDiagnosis(tenant_id=tenant.id, process_id=proc.id, content={}, version=1)
    db_session.add(diag)
    db_session.flush()

    assert desatualizacao_diagnostico(db_session, diag) is None


def test_diagnostico_documento_novo_apos_validacao_fica_desatualizado(db_session):
    tenant, proc = _seed(db_session)
    agora = datetime.now(UTC)
    diag = RegulatoryDiagnosis(
        tenant_id=tenant.id, process_id=proc.id, content={}, version=1,
        validated_at=agora, validated_by_user_id=None,
    )
    db_session.add(diag)
    db_session.flush()

    # Documento chega DEPOIS da validação — o caso literal da spec.
    _doc(db_session, tenant, proc, created_at=agora + timedelta(minutes=5))

    aviso = desatualizacao_diagnostico(db_session, diag)

    assert aviso is not None
    assert aviso.tipo == "documento_novo"
    assert "novo.pdf" in aviso.motivo
    # NADA foi regenerado nem apagado — versão e conteúdo intactos.
    assert diag.version == 1
    assert diag.content == {}


def test_diagnostico_documento_anterior_a_validacao_nao_desatualiza(db_session):
    """Documento que já existia ANTES da validação não é novidade — a
    validação já o viu (ou pôde ver)."""
    tenant, proc = _seed(db_session)
    agora = datetime.now(UTC)
    _doc(db_session, tenant, proc, created_at=agora - timedelta(days=1))

    diag = RegulatoryDiagnosis(
        tenant_id=tenant.id, process_id=proc.id, content={}, version=1,
        validated_at=agora,
    )
    db_session.add(diag)
    db_session.flush()

    assert desatualizacao_diagnostico(db_session, diag) is None


def test_diagnostico_decisao_alterada_apos_validacao_fica_desatualizado(db_session):
    tenant, proc = _seed(db_session)
    agora = datetime.now(UTC)
    doc = _doc(db_session, tenant, proc, created_at=agora - timedelta(days=1))
    diag = RegulatoryDiagnosis(
        tenant_id=tenant.id, process_id=proc.id, content={}, version=1, validated_at=agora,
    )
    db_session.add(diag)
    db_session.flush()

    row = ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=proc.id, document_id=doc.id,
        field_name="numero_matricula", field_value={"value": "3.181"},
        status=ExtractedFieldStatus.pendente, target_entity="matricula", target_field="numero_matricula",
    )
    db_session.add(row)
    db_session.flush()  # INSERT puro — `updated_at` fica NULL (sem server_default).

    # A decisão em si é um UPDATE (o que `decidir_decisao_agrupada` faz na
    # prática) — só um UPDATE popula `updated_at`, que é o sinal que
    # `_decisao_alterada_apos` lê (não `decided_at` sozinho, achado do code
    # review: `decided_at` nasce `NULL` no `reabrir` e a consolidação nunca o
    # toca — `updated_at` cobre os dois). `updated_at` setado explicitamente
    # (não via `onupdate=func.now()`): Postgres computa `now()` como o INÍCIO
    # da transação, e todo este teste roda numa transação só (fixture
    # `db_session`) — `func.now()` aqui devolveria um instante ANTERIOR a
    # `agora`, do jeito errado. Setar o valor explícito é o que representa de
    # verdade "esta linha foi tocada depois da validação".
    row.status = ExtractedFieldStatus.aceito
    row.decided_at = agora + timedelta(minutes=10)
    row.updated_at = agora + timedelta(minutes=10)
    db_session.flush()

    aviso = desatualizacao_diagnostico(db_session, diag)
    assert aviso is not None
    assert aviso.tipo == "decisao_alterada"


def test_reextracao_cacheada_cria_staging_novo_e_desatualiza_diagnostico(db_session):
    """Caminho do #23: o arquivo e o texto OCR são antigos, mas uma nova
    extração insere evidência de staging depois do artefato."""
    tenant, proc = _seed(db_session)
    agora = datetime.now(UTC)
    doc = _doc(db_session, tenant, proc, created_at=agora - timedelta(days=2))
    doc.extracted_at = agora - timedelta(days=2)
    doc.extracted_text = "Matrícula 3.181 com texto OCR já armazenado no cache."
    diag = RegulatoryDiagnosis(
        tenant_id=tenant.id, process_id=proc.id, content={}, version=1,
        validated_at=agora,
    )
    db_session.add(diag)
    db_session.flush()

    row = ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=proc.id, document_id=doc.id,
        field_name="numero_matricula", field_value={"value": "3.181"},
        status=ExtractedFieldStatus.pendente, target_entity="matricula",
        target_field="numero_matricula", created_at=agora + timedelta(minutes=3),
    )
    db_session.add(row)
    db_session.flush()

    aviso = desatualizacao_diagnostico(db_session, diag)
    assert aviso is not None
    assert aviso.tipo == "decisao_alterada"
    assert "nova evidência" in aviso.motivo


def test_diagnostico_sem_validacao_usa_criacao_como_corte(db_session):
    tenant, proc = _seed(db_session)
    diag = RegulatoryDiagnosis(tenant_id=tenant.id, process_id=proc.id, content={}, version=1)
    db_session.add(diag)
    db_session.flush()
    # created_at do rascunho é agora; documento "futuro" simulado.
    _doc(db_session, tenant, proc, created_at=diag.created_at + timedelta(minutes=1))

    aviso = desatualizacao_diagnostico(db_session, diag)
    assert aviso is not None
    assert aviso.tipo == "documento_novo"


# ---------------------------------------------------------------------------
# Rota
# ---------------------------------------------------------------------------


def test_rota_documento_novo_apos_fechamento_fica_desatualizada(db_session):
    tenant, proc = _seed(db_session)
    agora = datetime.now(UTC)
    rota = Rota(
        tenant_id=tenant.id, process_id=proc.id, demand_type="car",
        status=RotaStatus.validada, validated_at=agora,
    )
    db_session.add(rota)
    db_session.flush()

    _doc(db_session, tenant, proc, created_at=agora + timedelta(minutes=1))

    aviso = desatualizacao_rota(db_session, rota)
    assert aviso is not None
    assert aviso.tipo == "documento_novo"
    # O status da rota não foi tocado por este módulo (só lê).
    assert rota.status == RotaStatus.validada


def test_rota_documento_lido_tarde_fica_desatualizada(db_session):
    """Achado do code review: documento que chega ANTES do corte mas só fica
    LEGÍVEL (OCR/transcrição concluídos) DEPOIS — falso negativo que olhar só
    `created_at` deixava passar."""
    tenant, proc = _seed(db_session)
    agora = datetime.now(UTC)
    rota = Rota(
        tenant_id=tenant.id, process_id=proc.id, demand_type="car",
        status=RotaStatus.validada, validated_at=agora,
    )
    db_session.add(rota)
    db_session.flush()

    doc = _doc(db_session, tenant, proc, created_at=agora - timedelta(hours=2))
    doc.extracted_at = agora + timedelta(minutes=5)
    db_session.flush()

    aviso = desatualizacao_rota(db_session, rota)
    assert aviso is not None
    assert aviso.tipo == "documento_novo"
    assert "legível" in aviso.motivo


# ---------------------------------------------------------------------------
# Proposta
# ---------------------------------------------------------------------------


def test_proposta_sem_process_id_nunca_desatualiza(db_session):
    tenant, proc = _seed(db_session)
    proposal = Proposal(
        tenant_id=tenant.id, process_id=None, client_id=proc.client_id, title="Proposta avulsa",
    )
    db_session.add(proposal)
    db_session.flush()

    assert desatualizacao_proposta(db_session, proposal) is None


def test_proposta_documento_novo_apos_aceite_fica_desatualizada(db_session):
    tenant, proc = _seed(db_session)
    agora = datetime.now(UTC)
    proposal = Proposal(
        tenant_id=tenant.id, process_id=proc.id, client_id=proc.client_id,
        title="Proposta ELODI", accepted_at=agora,
    )
    db_session.add(proposal)
    db_session.flush()

    _doc(db_session, tenant, proc, created_at=agora + timedelta(minutes=1))

    aviso = desatualizacao_proposta(db_session, proposal)
    assert aviso is not None
    assert aviso.tipo == "documento_novo"


def test_proposta_sem_aceite_usa_criacao_como_corte(db_session):
    tenant, proc = _seed(db_session)
    proposal = Proposal(
        tenant_id=tenant.id, process_id=proc.id, client_id=proc.client_id,
        title="Proposta ELODI",
    )
    db_session.add(proposal)
    db_session.flush()
    _doc(db_session, tenant, proc, created_at=proposal.created_at + timedelta(minutes=1))

    aviso = desatualizacao_proposta(db_session, proposal)
    assert aviso is not None
