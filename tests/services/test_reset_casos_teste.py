"""Testes da ferramenta de reset de casos de teste (FASE 2).

Constrói um caso sintético COMPLETO (todas as tabelas do escopo) e prova:
  - dry-run lista as contagens corretas e NÃO grava;
  - execute apaga exatamente o escopo;
  - a allowlist fica INTACTA (referência/catálogo/identidade preservados);
  - legislation_alerts é preservado (desvinculado, não apagado);
  - a hash chain do AuditLog segue íntegra + registro do reset anexado;
  - idempotência (2ª execução = zero efeito);
  - orphan-guard: imóvel/cliente compartilhado com caso fora do escopo sobrevive;
  - o CLI recusa --execute sem backup e sem a frase de confirmação.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from datetime import UTC, datetime

import pytest

from app.models.acao import (
    Acao,
    AcaoOrigem,
    AcaoPrioridade,
    AcaoStatus,
    AcaoTipoTriagem,
)
from app.models.ai_job import AIJob, AIJobType
from app.models.audit_log import AuditLog
from app.models.checklist_template import ProcessChecklist
from app.models.client import Client, ClientStatus, ClientType
from app.models.contract import Contract, ContractStatus
from app.models.document import Document, DocumentSource
from app.models.extracted_field_staging import ExtractedFieldStaging
from app.models.intake_draft import IntakeDraft, IntakeDraftState
from app.models.legislation import LegislationDocument
from app.models.legislation_alert import LegislationAlert
from app.models.matricula import Matricula
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.proposal import Proposal, ProposalStatus
from app.models.regulatory import (
    DecisaoConsultor,
    ProcessIssueDecision,
    RegulatoryDiagnosis,
    RegulatoryIssue,
    RegulatoryIssueSeverity,
    RegulatoryIssueType,
)
from app.models.rota import Rota, RotaPasso, RotaPassoOrigem, RotaStatus
from app.models.stage_output import StageOutput
from app.models.tenant import Tenant
from app.models.user import User
from app.services.audit_hash import stamp_audit_hash, verify_audit_chain
from app.services.reset_casos_teste import (
    ALLOWLIST_TABLES,
    ResetScopeError,
    collect_scope,
    dry_run,
    execute_reset,
)

# ---------------------------------------------------------------------------
# Builder do caso sintético
# ---------------------------------------------------------------------------

def _build_case(db, *, tenant=None, storage_prefix="c1"):
    """Cria um caso completo (uma linha em CADA tabela do escopo) e devolve os
    objetos. Se ``tenant`` for dado, reusa (para casos que compartilham tenant).
    """
    if tenant is None:
        tenant = Tenant(name="Reset Tenant")
        db.add(tenant)
        db.flush()

    user = User(
        email=f"{storage_prefix}-rev@example.com", full_name="Rev",
        hashed_password="x", tenant_id=tenant.id, is_active=True,
    )
    db.add(user)
    cli = Client(tenant_id=tenant.id, full_name="Cliente Teste",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db.add(cli)
    db.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda", state="GO")
    db.add(prop)
    db.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Caso", process_type="car", status=ProcessStatus.diagnostico,
                   demand_type=DemandType.car)
    db.add(proc)
    db.flush()

    mat = Matricula(tenant_id=tenant.id, property_id=prop.id, numero_matricula="123")
    db.add(mat)
    doc = Document(
        tenant_id=tenant.id, process_id=proc.id, property_id=prop.id, client_id=cli.id,
        original_file_name="m.pdf", filename="m.pdf", content_type="application/pdf",
        storage_key=f"tenant_{tenant.id}/process_{proc.id}/{storage_prefix}.pdf",
        source=DocumentSource.upload_manual,
    )
    db.add(doc)
    db.add(ExtractedFieldStaging(tenant_id=tenant.id, process_id=proc.id, field_name="area_ha"))
    db.add(StageOutput(tenant_id=tenant.id, process_id=proc.id, macroetapa="diagnostico",
                       output_type="diagnostico", title="Saída"))
    db.add(Acao(tenant_id=tenant.id, process_id=proc.id, titulo="Ação",
                origem=AcaoOrigem.manual, prioridade=AcaoPrioridade.media,
                status=AcaoStatus.a_fazer, tipo_triagem=AcaoTipoTriagem.pendente))
    diag = RegulatoryDiagnosis(tenant_id=tenant.id, process_id=proc.id, content={})
    db.add(diag)
    issue = RegulatoryIssue(tenant_id=tenant.id, property_id=prop.id,
                            type=RegulatoryIssueType.outro,
                            severity=RegulatoryIssueSeverity.atencao)
    db.add(issue)
    db.flush()
    db.add(ProcessIssueDecision(tenant_id=tenant.id, process_id=proc.id, issue_id=issue.id,
                                decisao=DecisaoConsultor.corrigir_antes,
                                decided_at=datetime.now(UTC)))
    db.add(ProcessChecklist(tenant_id=tenant.id, process_id=proc.id, items=[]))
    rota = Rota(tenant_id=tenant.id, process_id=proc.id, demand_type="car",
                status=RotaStatus.proposta)
    db.add(rota)
    db.flush()
    db.add(RotaPasso(tenant_id=tenant.id, rota_id=rota.id, ordem=1, titulo="Passo",
                     origem=RotaPassoOrigem.ia, dedupe_key=f"{storage_prefix}-passo-1"))
    prop_row = Proposal(tenant_id=tenant.id, process_id=proc.id, client_id=cli.id,
                        status=ProposalStatus.draft, title="Proposta", scope_items=[])
    db.add(prop_row)
    db.add(Contract(tenant_id=tenant.id, process_id=proc.id, client_id=cli.id,
                    status=ContractStatus.draft, title="Contrato"))
    db.add(AIJob(tenant_id=tenant.id, job_type=AIJobType.extract_document,
                 entity_type="process", entity_id=proc.id))
    db.add(IntakeDraft(tenant_id=tenant.id, state=IntakeDraftState.card_criado,
                       linked_process_id=proc.id, form_data={}))
    db.flush()
    return {
        "tenant": tenant, "user": user, "client": cli, "property": prop,
        "process": proc, "matricula": mat, "document": doc, "issue": issue,
        "rota": rota, "proposal": prop_row, "diag": diag,
    }


# ---------------------------------------------------------------------------
# 1. Dry-run
# ---------------------------------------------------------------------------

def test_dry_run_conta_e_nao_grava(db_session):
    case = _build_case(db_session)
    proc_id = case["process"].id
    db_session.flush()

    report = dry_run(db_session, collect_scope(db_session, [proc_id]))

    assert report.executed is False
    assert report.counts["processes"] == 1
    assert report.counts["documents"] == 1
    assert report.counts["acoes"] == 1
    assert report.counts["rotas"] == 1
    assert report.counts["rota_passos"] == 1
    assert report.counts["extracted_field_staging"] == 1
    assert report.counts["stage_outputs"] == 1
    assert report.counts["regulatory_diagnoses"] == 1
    assert report.counts["regulatory_issues"] == 1
    assert report.counts["process_issue_decisions"] == 1
    assert report.counts["process_checklists"] == 1
    assert report.counts["proposals"] == 1
    assert report.counts["contracts"] == 1
    assert report.counts["ai_jobs"] == 1
    assert report.counts["intake_drafts"] == 1
    assert report.counts["matriculas"] == 1
    assert report.counts["properties"] == 1
    assert report.counts["clients"] == 1
    assert report.r2_objects == 1

    # NADA foi gravado: o processo ainda existe.
    assert db_session.query(Process).filter(Process.id == proc_id).count() == 1


# ---------------------------------------------------------------------------
# 2. Execute apaga o escopo
# ---------------------------------------------------------------------------

def test_execute_apaga_todo_o_escopo(db_session):
    case = _build_case(db_session)
    proc_id = case["process"].id
    prop_id = case["property"].id
    client_id = case["client"].id
    db_session.flush()

    scope = collect_scope(db_session, [proc_id])
    report = execute_reset(db_session, scope, user_id=None)

    assert report.executed is True
    assert db_session.query(Process).filter(Process.id == proc_id).count() == 0
    assert db_session.query(Property).filter(Property.id == prop_id).count() == 0
    assert db_session.query(Client).filter(Client.id == client_id).count() == 0
    for model in (Acao, Rota, RotaPasso, ExtractedFieldStaging, StageOutput,
                  RegulatoryDiagnosis, RegulatoryIssue, ProcessIssueDecision,
                  ProcessChecklist, Proposal, Contract, Document, Matricula,
                  IntakeDraft):
        assert db_session.query(model).count() == 0, f"{model.__name__} deveria estar vazio"
    assert db_session.query(AIJob).count() == 0


def test_execute_isola_caso_fora_do_escopo(db_session):
    tenant = Tenant(name="Isolamento")
    db_session.add(tenant)
    db_session.flush()
    keep = _build_case(db_session, tenant=tenant, storage_prefix="keep")
    drop = _build_case(db_session, tenant=tenant, storage_prefix="drop")
    db_session.flush()

    execute_reset(db_session, collect_scope(db_session, [drop["process"].id]), user_id=None)

    # O caso preservado segue inteiro.
    assert db_session.query(Process).filter(Process.id == keep["process"].id).count() == 1
    assert db_session.query(Property).filter(Property.id == keep["property"].id).count() == 1
    assert db_session.query(Client).filter(Client.id == keep["client"].id).count() == 1
    assert db_session.query(Document).filter(Document.id == keep["document"].id).count() == 1
    # O caso alvo sumiu.
    assert db_session.query(Process).filter(Process.id == drop["process"].id).count() == 0


# ---------------------------------------------------------------------------
# 3. Allowlist intacta
# ---------------------------------------------------------------------------

def test_allowlist_preservada(db_session):
    case = _build_case(db_session)
    tenant = case["tenant"]
    legdoc = LegislationDocument(title="Lei X", source_type="lei")
    db_session.add(legdoc)
    db_session.flush()
    # Dois alertas: um do caso (escopo) e um global (process_id NULL).
    db_session.add(LegislationAlert(tenant_id=tenant.id, process_id=case["process"].id,
                                    document_id=legdoc.id, alert_type="updated", message="x"))
    db_session.add(LegislationAlert(tenant_id=tenant.id, process_id=None,
                                    document_id=legdoc.id, alert_type="new_legislation", message="g"))
    db_session.flush()

    users_before = db_session.query(User).count()
    tenants_before = db_session.query(Tenant).count()
    legdocs_before = db_session.query(LegislationDocument).count()
    alerts_before = db_session.query(LegislationAlert).count()

    execute_reset(db_session, collect_scope(db_session, [case["process"].id]), user_id=None)

    # Nenhuma tabela da allowlist perdeu linhas (audit_logs testada à parte —
    # ela GANHA a linha do reset).
    assert db_session.query(User).count() == users_before
    assert db_session.query(Tenant).count() == tenants_before
    assert db_session.query(LegislationDocument).count() == legdocs_before
    # legislation_alerts: NENHUMA linha apagada (contagem igual)...
    assert db_session.query(LegislationAlert).count() == alerts_before == 2
    # ...mas o alerta do caso foi DESVINCULADO (preservado, não apagado).
    assert db_session.query(LegislationAlert).filter(
        LegislationAlert.process_id.isnot(None)).count() == 0


def test_plano_nunca_mira_tabela_da_allowlist(db_session):
    """Guard estrutural: build_plan + _assert_plan_safe nunca miram allowlist."""
    from app.services.reset_casos_teste import build_plan
    case = _build_case(db_session)
    db_session.flush()
    plan = build_plan(collect_scope(db_session, [case["process"].id]))
    targeted = {step.model.__tablename__ for step in plan}
    assert targeted.isdisjoint(ALLOWLIST_TABLES)


# ---------------------------------------------------------------------------
# 4. Hash chain do AuditLog
# ---------------------------------------------------------------------------

def test_audit_chain_integra_e_reset_registrado(db_session):
    case = _build_case(db_session)
    tenant = case["tenant"]
    # Um registro de auditoria pré-existente do tenant (elo anterior da cadeia).
    pre = AuditLog(tenant_id=tenant.id, user_id=None, entity_type="process",
                   entity_id=case["process"].id, action="created")
    db_session.add(pre)
    db_session.flush()
    stamp_audit_hash(db_session, pre)
    db_session.flush()

    execute_reset(db_session, collect_scope(db_session, [case["process"].id]), user_id=None)
    db_session.flush()

    # A cadeia do tenant continua íntegra (o reset encadeou no topo).
    assert verify_audit_chain(db_session, tenant.id) == []
    # E existe o registro do reset — a operação não é invisível.
    last = (db_session.query(AuditLog)
            .filter(AuditLog.tenant_id == tenant.id)
            .order_by(AuditLog.id.desc()).first())
    assert last.action == "reset_casos_teste"
    assert last.hash_sha256 is not None
    assert last.hash_previous == pre.hash_sha256


# ---------------------------------------------------------------------------
# 5. Idempotência
# ---------------------------------------------------------------------------

def test_idempotencia_segunda_execucao_zero_efeito(db_session):
    case = _build_case(db_session)
    proc_id = case["process"].id
    db_session.flush()

    execute_reset(db_session, collect_scope(db_session, [proc_id]), user_id=None)
    db_session.flush()

    # 2ª passada: o processo já não existe → collect_scope recusa.
    with pytest.raises(ResetScopeError):
        collect_scope(db_session, [proc_id])


# ---------------------------------------------------------------------------
# 6. Orphan-guard: imóvel/cliente compartilhado é preservado
# ---------------------------------------------------------------------------

def test_orphan_guard_preserva_imovel_e_cliente_compartilhados(db_session):
    tenant = Tenant(name="Compartilhado")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(tenant_id=tenant.id, full_name="C", client_type=ClientType.pf,
                 status=ClientStatus.active)
    db_session.add(cli)
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda")
    db_session.add(prop)
    db_session.flush()
    # Dois processos no MESMO imóvel/cliente.
    p_scope = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                      title="Escopo", process_type="car", status=ProcessStatus.triagem)
    p_keep = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                     title="Fora", process_type="car", status=ProcessStatus.triagem)
    db_session.add_all([p_scope, p_keep])
    db_session.flush()
    mat = Matricula(tenant_id=tenant.id, property_id=prop.id, numero_matricula="9")
    db_session.add(mat)
    db_session.flush()

    scope = collect_scope(db_session, [p_scope.id])
    # imóvel e cliente NÃO entram no escopo (há processo fora referenciando).
    assert scope.property_ids == []
    assert scope.client_ids == []
    assert prop.id in scope.property_ids_preserved
    assert cli.id in scope.client_ids_preserved

    execute_reset(db_session, scope, user_id=None)

    assert db_session.query(Process).filter(Process.id == p_scope.id).count() == 0
    assert db_session.query(Process).filter(Process.id == p_keep.id).count() == 1
    assert db_session.query(Property).filter(Property.id == prop.id).count() == 1
    assert db_session.query(Client).filter(Client.id == cli.id).count() == 1
    assert db_session.query(Matricula).filter(Matricula.id == mat.id).count() == 1


# ---------------------------------------------------------------------------
# 7. Escopo inválido
# ---------------------------------------------------------------------------

def test_collect_scope_recusa_lista_vazia(db_session):
    with pytest.raises(ResetScopeError):
        collect_scope(db_session, [])


def test_collect_scope_recusa_processo_inexistente(db_session):
    with pytest.raises(ResetScopeError):
        collect_scope(db_session, [999999])


def test_collect_scope_recusa_tenant_divergente(db_session):
    case = _build_case(db_session)
    db_session.flush()
    with pytest.raises(ResetScopeError):
        collect_scope(db_session, [case["process"].id], tenant_id=case["tenant"].id + 999)


# ---------------------------------------------------------------------------
# 8. R2: deleção dos objetos via client fake
# ---------------------------------------------------------------------------

class _FakeS3:
    def __init__(self):
        self.deleted = []

    def delete_objects(self, Bucket, Delete):  # noqa: N803 — assinatura boto3
        keys = [o["Key"] for o in Delete["Objects"]]
        self.deleted.extend(keys)
        return {}


def test_execute_apaga_objetos_r2(db_session):
    case = _build_case(db_session)
    expected_key = case["document"].storage_key
    db_session.flush()
    fake = _FakeS3()

    report = execute_reset(db_session, collect_scope(db_session, [case["process"].id]),
                           user_id=None, s3_client=fake, bucket="regente-docs")

    assert expected_key in fake.deleted
    assert report.r2_objects == 1


# ---------------------------------------------------------------------------
# 9. CLI: recusa sem backup e sem confirmação
# ---------------------------------------------------------------------------

@pytest.fixture
def reset_cli():
    """Importa scripts/reset_casos_teste.py como módulo (nome único p/ não
    colidir com o serviço app.services.reset_casos_teste)."""
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "scripts", "reset_casos_teste.py",
    )
    spec = importlib.util.spec_from_file_location("reset_cli_module", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _NoCloseSession:
    """Delega ao db_session transacional mas neutraliza close() para o CLI
    não fechar a sessão do teste no finally."""

    def __init__(self, real):
        self._real = real

    def __getattr__(self, name):
        return getattr(self._real, name)

    def close(self):
        pass


def _patch_session(monkeypatch, reset_cli, db_session):
    monkeypatch.setattr(reset_cli, "SessionLocal", lambda: _NoCloseSession(db_session))


def test_cli_dry_run_default_nao_grava(reset_cli, db_session, monkeypatch):
    case = _build_case(db_session)
    proc_id = case["process"].id
    db_session.flush()
    _patch_session(monkeypatch, reset_cli, db_session)
    monkeypatch.setattr(sys, "argv", ["reset", "--process-id", str(proc_id)])

    rc = reset_cli.main()

    assert rc == 0
    assert db_session.query(Process).filter(Process.id == proc_id).count() == 1


def test_cli_execute_sem_backup_recusa(reset_cli, db_session, monkeypatch):
    case = _build_case(db_session)
    proc_id = case["process"].id
    db_session.flush()
    _patch_session(monkeypatch, reset_cli, db_session)
    monkeypatch.setattr(sys, "argv", ["reset", "--process-id", str(proc_id), "--execute"])

    rc = reset_cli.main()

    assert rc == 3  # RECUSADO: falta --backup-confirmada
    assert db_session.query(Process).filter(Process.id == proc_id).count() == 1


def test_cli_execute_frase_errada_recusa(reset_cli, db_session, monkeypatch):
    case = _build_case(db_session)
    proc_id = case["process"].id
    db_session.flush()
    _patch_session(monkeypatch, reset_cli, db_session)
    monkeypatch.setattr(sys, "argv", [
        "reset", "--process-id", str(proc_id), "--execute",
        "--backup-confirmada", "--confirm", "frase errada",
    ])

    rc = reset_cli.main()

    assert rc == 4  # RECUSADO: confirmação não confere
    assert db_session.query(Process).filter(Process.id == proc_id).count() == 1
