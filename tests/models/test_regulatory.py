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
    RegulatoryAlertFactibilidade,
    RegulatoryDiagnosis,
    RegulatoryFamilia,
    RegulatoryIssue,
    RegulatoryIssueCatalog,
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
    """PROMPT_5 Onda A: taxonomia rica — codigo_alerta (FK no catálogo) +
    familia + severity 4 níveis + campos `muda_*` + documentos_cruzados.
    `type` legado continua nullable apenas para retrocompat."""

    def test_create_minimal_com_taxonomia_rica(self, db_session, tenant, property_record):
        issue = RegulatoryIssue(
            tenant_id=tenant.id,
            property_id=property_record.id,
            codigo_alerta="AREA_MATRICULA_X_CAR",
            familia=RegulatoryFamilia.area,
            severity=RegulatoryIssueSeverity.alto,
            detected_by="auditor_imovel",
        )
        db_session.add(issue)
        db_session.flush()
        assert issue.id is not None
        assert issue.severity == RegulatoryIssueSeverity.alto
        assert issue.codigo_alerta == "AREA_MATRICULA_X_CAR"
        assert issue.familia == RegulatoryFamilia.area
        assert issue.resolved_at is None
        assert issue.detected_at is not None
        assert issue.document_id is None
        # type legado fica None em registros novos (PROMPT_5)
        assert issue.type is None

    def test_default_severity_is_atencao(self, db_session, tenant, property_record):
        """Default mudou de `warning` (3 níveis) para `atencao` (4 níveis)."""
        issue = RegulatoryIssue(
            tenant_id=tenant.id,
            property_id=property_record.id,
            codigo_alerta="DOCUMENTO_AUSENTE",
            familia=RegulatoryFamilia.validade_documental,
        )
        db_session.add(issue)
        db_session.flush()
        assert issue.severity == RegulatoryIssueSeverity.atencao

    def test_with_document_link(self, db_session, tenant, property_record, document):
        issue = RegulatoryIssue(
            tenant_id=tenant.id,
            property_id=property_record.id,
            document_id=document.id,
            codigo_alerta="CAR_LOCALIZACAO_DIVERGENTE_REALIDADE",
            familia=RegulatoryFamilia.car,
            severity=RegulatoryIssueSeverity.critico,
            muda_rota_regulatoria=True,
            muda_escopo_preco_prazo=True,
            documentos_cruzados=["CAR", "GEO"],
            payload={"diff_ha": 12.4},
            detected_by="auditor_imovel",
        )
        db_session.add(issue)
        db_session.flush()
        assert issue.document.original_file_name == "matricula.pdf"
        assert issue.muda_rota_regulatoria is True
        assert issue.documentos_cruzados == ["CAR", "GEO"]

    def test_severity_enum_values_4_niveis(self, db_session, tenant, property_record):
        """PROMPT_5: severity passou de 3 para 4 níveis. `critico` é novo."""
        for sev in [
            RegulatoryIssueSeverity.informativo,
            RegulatoryIssueSeverity.atencao,
            RegulatoryIssueSeverity.alto,
            RegulatoryIssueSeverity.critico,
        ]:
            issue = RegulatoryIssue(
                tenant_id=tenant.id,
                property_id=property_record.id,
                codigo_alerta="OUTRO_GENERICO",
                familia=RegulatoryFamilia.validade_documental,
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
            RegulatoryIssueSeverity.informativo,
            RegulatoryIssueSeverity.atencao,
            RegulatoryIssueSeverity.alto,
            RegulatoryIssueSeverity.critico,
        }

    def test_resolved_at_marks_done(self, db_session, tenant, property_record):
        issue = RegulatoryIssue(
            tenant_id=tenant.id,
            property_id=property_record.id,
            codigo_alerta="AREA_MATRICULA_X_CAR",
            familia=RegulatoryFamilia.area,
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
            codigo_alerta="OUTRO_GENERICO",
            familia=RegulatoryFamilia.validade_documental,
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

    def test_legacy_type_continua_nullable_para_retrocompat(self, db_session, tenant, property_record):
        """Registros novos NÃO preenchem `type` (deprecated). Registros antigos
        gravados antes da migration têm type preenchido + codigo_alerta=None
        (a migration de dados migra; mas o schema tolera ambos os shapes)."""
        # Forma legada (não deve ser usada em código novo — só teste de tolerância)
        issue = RegulatoryIssue(
            tenant_id=tenant.id,
            property_id=property_record.id,
            type=RegulatoryIssueType.area_divergente,
            severity=RegulatoryIssueSeverity.alto,
        )
        db_session.add(issue)
        db_session.flush()
        assert issue.type == RegulatoryIssueType.area_divergente
        assert issue.codigo_alerta is None

    def test_codigo_alerta_invalido_viola_fk(self, db_session, tenant, property_record):
        """codigo_alerta é FK no catálogo — código não existente viola."""
        issue = RegulatoryIssue(
            tenant_id=tenant.id,
            property_id=property_record.id,
            codigo_alerta="ZZZ_CODIGO_INEXISTENTE",
            familia=RegulatoryFamilia.area,
        )
        db_session.add(issue)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()


class TestRegulatoryIssueCatalog:
    """PROMPT_5 Onda A: catálogo evolutivo. Adicionar código novo é INSERT,
    não migration. O seed inicial vem da migration `c1b2d3e4f5a7`."""

    def test_seed_inicial_tem_entradas_basicas(self, db_session):
        """O seed contém pelo menos os códigos usados pelo property_audit."""
        codigos_esperados = {
            "AREA_MATRICULA_X_CAR",
            "AREA_MATRICULA_X_CCIR",
            "AREA_MATRICULA_X_ITR",
            "AREA_CAR_X_CCIR",
            "GEO_AUSENTE",
            "RL_MATRICULA_DIVERGENTE_RL_CAR",
            "VERIFICACAO_ESPACIAL_PENDENTE",
            "OUTRO_GENERICO",
        }
        rows = db_session.query(RegulatoryIssueCatalog).filter(
            RegulatoryIssueCatalog.codigo_alerta.in_(codigos_esperados)
        ).all()
        codigos_presentes = {r.codigo_alerta for r in rows}
        assert codigos_presentes == codigos_esperados

    def test_seed_total_minimo_40_entradas(self, db_session):
        """Skill auditor tem 40 códigos canônicos; seed atual vai um pouco além
        com OUTRO_GENERICO + VERIFICACAO_ESPACIAL_PENDENTE + 2 extensões de pares."""
        total = db_session.query(RegulatoryIssueCatalog).count()
        assert total >= 40

    def test_factibilidade_distingue_documental_geoespacial_externa(self, db_session):
        """3 modos de factibilidade (📄 / 🛰️ / 🔌). Ex.: AREA_MATRICULA_X_CAR é
        documental; CAR_LOCALIZACAO_DIVERGENTE_REALIDADE é geoespacial;
        EMBARGO_NAO_INFORMADO é consulta_externa."""
        area = db_session.query(RegulatoryIssueCatalog).filter_by(
            codigo_alerta="AREA_MATRICULA_X_CAR"
        ).one()
        assert area.factibilidade == RegulatoryAlertFactibilidade.documental

        car_geo = db_session.query(RegulatoryIssueCatalog).filter_by(
            codigo_alerta="CAR_LOCALIZACAO_DIVERGENTE_REALIDADE"
        ).one()
        assert car_geo.factibilidade == RegulatoryAlertFactibilidade.geoespacial

        embargo = db_session.query(RegulatoryIssueCatalog).filter_by(
            codigo_alerta="EMBARGO_NAO_INFORMADO"
        ).one()
        assert embargo.factibilidade == RegulatoryAlertFactibilidade.consulta_externa

    def test_severity_base_4_niveis(self, db_session):
        """Catálogo carrega severity_base com 4 níveis. Ex.: GEO_AUSENTE é
        critico (não colapsa em alto)."""
        geo = db_session.query(RegulatoryIssueCatalog).filter_by(
            codigo_alerta="GEO_AUSENTE"
        ).one()
        # GEO_AUSENTE é alto na skill (não crítico — a sócia distinguiu)
        assert geo.severity_base == RegulatoryIssueSeverity.alto

        embargo = db_session.query(RegulatoryIssueCatalog).filter_by(
            codigo_alerta="EMBARGO_NAO_INFORMADO"
        ).one()
        # Embargo IBAMA não informado é crítico (gatilho de decisão obrigatória)
        assert embargo.severity_base == RegulatoryIssueSeverity.critico

    def test_familia_de_cada_codigo_bate(self, db_session):
        """Cada código está na família esperada (sanity check do seed)."""
        rows = db_session.query(RegulatoryIssueCatalog).all()
        mapping = {r.codigo_alerta: r.familia for r in rows}
        assert mapping["AREA_MATRICULA_X_CAR"] == RegulatoryFamilia.area
        assert mapping["GEO_AUSENTE"] == RegulatoryFamilia.geo_incra
        assert mapping["TIT_PROP_MATRICULA_X_CAR"] == RegulatoryFamilia.titularidade
        assert mapping["RL_MATRICULA_DIVERGENTE_RL_CAR"] == RegulatoryFamilia.ambiental
        assert mapping["EMBARGO_NAO_INFORMADO"] == RegulatoryFamilia.restricao_risco
        assert mapping["LICENCA_OUTORGA_AUSENTE_VENCIDA"] == RegulatoryFamilia.licenciamento

    def test_documentos_cruzados_default_eh_lista(self, db_session):
        """O default é uma lista de strings (ex.: ['Matricula', 'CAR'])."""
        area = db_session.query(RegulatoryIssueCatalog).filter_by(
            codigo_alerta="AREA_MATRICULA_X_CAR"
        ).one()
        assert area.documentos_cruzados_default == ["Matricula", "CAR"]

    def test_catalogo_aceita_adicionar_codigo_novo_sem_migration(
        self, db_session, tenant, property_record,
    ):
        """A premissa do catálogo evolutivo: INSERT, não DDL."""
        novo = RegulatoryIssueCatalog(
            codigo_alerta="CODIGO_NOVO_DE_TESTE",
            familia=RegulatoryFamilia.area,
            descricao_curta="Código adicionado em runtime para validar evolução",
            factibilidade=RegulatoryAlertFactibilidade.documental,
            severity_base=RegulatoryIssueSeverity.atencao,
            muda_rota_regulatoria=False,
            muda_escopo_preco_prazo=True,
            documentos_cruzados_default=["Matricula"],
        )
        db_session.add(novo)
        db_session.flush()
        # Issue pode referenciar o código novo via FK imediatamente
        issue = RegulatoryIssue(
            tenant_id=tenant.id,
            property_id=property_record.id,
            codigo_alerta="CODIGO_NOVO_DE_TESTE",
            familia=RegulatoryFamilia.area,
            severity=RegulatoryIssueSeverity.atencao,
        )
        db_session.add(issue)
        db_session.flush()
        assert issue.id is not None
        assert issue.codigo_alerta == "CODIGO_NOVO_DE_TESTE"
