"""Testes dos modelos RegulatoryDiagnosis + RegulatoryIssue — Sprint A1 Tarefa D1."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, DocumentSource
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.regulatory import (
    RegulatoryDiagnosis,
    RegulatoryIssue,
    RegulatoryIssueSeverity,
    RegulatoryIssueType,
)
from app.models.tenant import Tenant
from app.models.user import User

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tenant(db_session) -> Tenant:
    t = Tenant(name="Tenant Regulatorio")
    db_session.add(t)
    db_session.flush()
    return t


@pytest.fixture
def user(db_session, tenant) -> User:
    u = User(
        email="rev@example.com",
        full_name="Revisor",
        hashed_password="x",
        tenant_id=tenant.id,
        is_active=True,
    )
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def client_record(db_session, tenant) -> Client:
    c = Client(
        tenant_id=tenant.id,
        full_name="Fazenda Teste",
        client_type=ClientType.pj,
        status=ClientStatus.active,
    )
    db_session.add(c)
    db_session.flush()
    return c


@pytest.fixture
def property_record(db_session, tenant, client_record) -> Property:
    p = Property(
        tenant_id=tenant.id,
        client_id=client_record.id,
        name="Imóvel A",
        state="GO",
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def process(db_session, tenant, client_record, property_record) -> Process:
    pr = Process(
        tenant_id=tenant.id,
        client_id=client_record.id,
        property_id=property_record.id,
        title="Caso Regulatorio",
        process_type="car",
        status=ProcessStatus.diagnostico,
        demand_type=DemandType.car,
    )
    db_session.add(pr)
    db_session.flush()
    return pr


@pytest.fixture
def document(db_session, tenant, property_record) -> Document:
    d = Document(
        tenant_id=tenant.id,
        property_id=property_record.id,
        original_file_name="matricula.pdf",
        filename="matricula.pdf",
        content_type="application/pdf",
        storage_key="t/matricula.pdf",
        source=DocumentSource.upload_manual,
    )
    db_session.add(d)
    db_session.flush()
    return d


# ---------------------------------------------------------------------------
# RegulatoryDiagnosis
# ---------------------------------------------------------------------------

class TestRegulatoryDiagnosis:
    def test_create_minimal(self, db_session, tenant, process):
        diag = RegulatoryDiagnosis(
            tenant_id=tenant.id,
            process_id=process.id,
            content={"hipoteses": ["pendência CAR"]},
        )
        db_session.add(diag)
        db_session.flush()
        assert diag.id is not None
        assert diag.version == 1
        assert diag.validated_by_user_id is None
        assert diag.validated_at is None

    def test_unique_process_version_constraint(self, db_session, tenant, process):
        d1 = RegulatoryDiagnosis(
            tenant_id=tenant.id,
            process_id=process.id,
            content={},
            version=1,
        )
        db_session.add(d1)
        db_session.flush()

        d2 = RegulatoryDiagnosis(
            tenant_id=tenant.id,
            process_id=process.id,
            content={},
            version=1,  # mesmo (process_id, version) — deve violar
        )
        db_session.add(d2)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_multiple_versions_allowed(self, db_session, tenant, process):
        d1 = RegulatoryDiagnosis(
            tenant_id=tenant.id, process_id=process.id, content={}, version=1,
        )
        d2 = RegulatoryDiagnosis(
            tenant_id=tenant.id, process_id=process.id, content={}, version=2,
        )
        db_session.add_all([d1, d2])
        db_session.flush()
        assert d1.id != d2.id

    def test_human_validation(self, db_session, tenant, process, user):
        diag = RegulatoryDiagnosis(
            tenant_id=tenant.id,
            process_id=process.id,
            content={},
            validated_by_user_id=user.id,
            validated_at=datetime.now(UTC),
        )
        db_session.add(diag)
        db_session.flush()
        assert diag.validated_by.email == "rev@example.com"

    def test_content_jsonb_can_carry_issue_ids(self, db_session, tenant, process):
        """Sem N–N (decisão Q4): issues referenciadas via lista no content."""
        diag = RegulatoryDiagnosis(
            tenant_id=tenant.id,
            process_id=process.id,
            content={"issue_ids": [1, 2, 3], "summary": "ok"},
        )
        db_session.add(diag)
        db_session.flush()
        db_session.refresh(diag)
        assert diag.content["issue_ids"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# RegulatoryIssue
# ---------------------------------------------------------------------------

class TestRegulatoryIssue:
    def test_create_minimal(self, db_session, tenant, property_record):
        issue = RegulatoryIssue(
            tenant_id=tenant.id,
            property_id=property_record.id,
            type=RegulatoryIssueType.area_divergente,
            detected_by="auditor_imovel",
        )
        db_session.add(issue)
        db_session.flush()
        assert issue.id is not None
        # default severity = warning
        assert issue.severity == RegulatoryIssueSeverity.warning
        assert issue.resolved_at is None
        assert issue.detected_at is not None
        assert issue.document_id is None

    def test_with_document_link(self, db_session, tenant, property_record, document):
        issue = RegulatoryIssue(
            tenant_id=tenant.id,
            property_id=property_record.id,
            document_id=document.id,
            type=RegulatoryIssueType.poligono_fora_matricula,
            severity=RegulatoryIssueSeverity.critical,
            payload={"diff_ha": 12.4},
            detected_by="auditor_imovel",
        )
        db_session.add(issue)
        db_session.flush()
        assert issue.document.original_file_name == "matricula.pdf"

    def test_severity_enum_values(self, db_session, tenant, property_record):
        for sev in [RegulatoryIssueSeverity.info, RegulatoryIssueSeverity.warning, RegulatoryIssueSeverity.critical]:
            issue = RegulatoryIssue(
                tenant_id=tenant.id,
                property_id=property_record.id,
                type=RegulatoryIssueType.outro,
                severity=sev,
            )
            db_session.add(issue)
        db_session.flush()
        rows = (
            db_session.query(RegulatoryIssue)
            .filter_by(property_id=property_record.id)
            .all()
        )
        assert {r.severity for r in rows} == {
            RegulatoryIssueSeverity.info,
            RegulatoryIssueSeverity.warning,
            RegulatoryIssueSeverity.critical,
        }

    def test_resolved_at_marks_done(self, db_session, tenant, property_record):
        issue = RegulatoryIssue(
            tenant_id=tenant.id,
            property_id=property_record.id,
            type=RegulatoryIssueType.area_divergente,
        )
        db_session.add(issue)
        db_session.flush()
        assert issue.resolved_at is None

        issue.resolved_at = datetime.now(UTC)
        db_session.flush()
        assert issue.resolved_at is not None

    def test_no_n_n_with_diagnosis(self, db_session, tenant, process, property_record):
        """Decisão Q4: NÃO existe FK ou tabela associativa entre Issue e Diagnosis.

        Confirma o desenho: issue não tem coluna apontando pra diagnosis,
        e diagnosis não tem relacionamento ORM puxando issues.
        """
        issue = RegulatoryIssue(
            tenant_id=tenant.id,
            property_id=property_record.id,
            type=RegulatoryIssueType.outro,
        )
        diag = RegulatoryDiagnosis(
            tenant_id=tenant.id,
            process_id=process.id,
            content={},
        )
        db_session.add_all([issue, diag])
        db_session.flush()

        # Não há atributo 'issues' no Diagnosis nem 'diagnosis_id' na Issue
        assert not hasattr(diag, "issues")
        assert not hasattr(issue, "diagnosis_id")
        assert not hasattr(issue, "diagnosis")
