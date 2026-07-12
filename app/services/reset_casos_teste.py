"""Reset de casos de teste — FASE 2 (ferramenta, não execução).

Apaga TODO o rastro de um conjunto EXPLÍCITO de casos (processos) de um tenant:
staging, ações, rotas, diagnóstico, issues regulatórias, checklists, propostas,
contratos, documentos (linha + objeto no R2), AIJobs, drafts órfãos, e — quando
ficam órfãos — o imóvel, matrículas e cliente. O objetivo é destravar o resubir
de casos de teste sem contaminar dados de referência ou de outros casos.

Este módulo é a lógica reutilizável; o CLI é ``scripts/reset_casos_teste.py``
(mesma divisão de ``ficha01_extraction.sanear_staging_process`` ↔
``scripts/sanear_staging.py``). Nada aqui faz ``commit`` — quem chama decide.

Decisões de projeto (com evidência medida em 2026-07-12):

1.  **Escopo explícito, nunca "tudo".** A entrada é uma lista de ``process_id``.
    Imóvel/cliente só entram no escopo se ficarem ÓRFÃOS (nenhum processo fora
    do escopo os referencia) — senão são preservados e apenas desvinculados
    pela própria deleção do processo (FK ``SET NULL``/``CASCADE`` medidas).

2.  **Allowlist HARD-CODED** (``ALLOWLIST_TABLES``): o plano de deleção assevera
    em runtime que NENHUM passo mira uma tabela de referência/catálogo/tenant.
    Se algum passo violar, o serviço aborta (erro de programação, não de dados).

3.  **``audit_logs`` é PRESERVADO, não apagado.** A hash chain é por-tenant,
    ordenada por ``id``, e cada registro embute o ``hash_previous`` do anterior
    (``app/services/audit_hash.py``). Apagar registros de auditoria no meio da
    cadeia quebraria (``broken_previous_link``) todos os posteriores do tenant.
    Portanto o reset NÃO é invisível: ele se registra como um NOVO ``AuditLog``
    (``action="reset_casos_teste"``), carimbado por último. Isto diverge do
    "APAGA audit_logs" literal da missão — de propósito, com evidência.

4.  **``legislation_alerts`` é PRESERVADO** (allowlist). Como tem FK
    ``process_id ON DELETE CASCADE``, as linhas ligadas aos processos do escopo
    seriam levadas pelo CASCADE. Para preservá-las (regra da allowlist), elas são
    DESVINCULADAS (``process_id → NULL``) ANTES de apagar o processo. A contagem
    de linhas da tabela permanece constante — invariante verificada nos testes.

5.  **R2/storage:** a chave do objeto está direto em ``Document.storage_key``
    (fallback ``s3_key``); não se recompõe de tenant/processo. O
    ``StorageService`` não tem delete — este módulo apaga via ``delete_objects``
    no client boto3 passado pelo chamador, em lotes de 1000. Só no ``--execute``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.acao import Acao
from app.models.ai_job import AIJob
from app.models.audit_log import AuditLog
from app.models.checklist_template import ProcessChecklist
from app.models.client import Client
from app.models.communication import CommunicationThread, Message
from app.models.contract import Contract
from app.models.credential import Credential
from app.models.document import Document
from app.models.extracted_field_staging import ExtractedFieldStaging
from app.models.intake_classification_feedback import IntakeClassificationFeedback
from app.models.intake_draft import IntakeDraft
from app.models.legislation_alert import LegislationAlert
from app.models.macroetapa import MacroetapaChecklist
from app.models.matricula import Matricula
from app.models.process import Process
from app.models.process_decision import ProcessDecision
from app.models.property import Property
from app.models.proposal import Proposal
from app.models.regulatory import (
    ProcessIssueDecision,
    RegulatoryDiagnosis,
    RegulatoryIssue,
)
from app.models.rota import Rota, RotaPasso
from app.models.stage_output import StageOutput
from app.models.task import Task
from app.services.audit_hash import stamp_audit_hash

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Allowlist — tabelas que o reset se RECUSA a apagar. Hard-coded de propósito.
# ---------------------------------------------------------------------------
# Referência/catálogo/identidade + audit_logs (integridade da hash chain, ver
# decisão 3 no docstring do módulo). O plano de deleção é validado contra este
# conjunto em runtime (_assert_plan_safe): nenhum passo pode mirar aqui.
ALLOWLIST_TABLES: frozenset[str] = frozenset(
    {
        "knowledge_catalog",
        "legislation_documents",
        "legislation_alerts",
        "regulatory_issue_catalog",
        "users",
        "tenants",
        "pre_cadastros",  # tabela real do "waitlist" (rota /api/v1/waitlist)
        "prompt_templates",
        "workflow_templates",
        "contract_templates",
        "checklist_templates",  # catálogo; instância por-caso é process_checklists
        "audit_logs",  # hash chain por-tenant — preservada, só recebe append
    }
)


class ResetScopeError(ValueError):
    """Escopo inválido (processo inexistente, tenant divergente, lista vazia)."""


@dataclass
class ResetScope:
    """Fronteira do reset — tudo que será tocado, resolvido antes de qualquer
    escrita. ``property_ids`` / ``client_ids`` já são só os ÓRFÃOS."""

    tenant_id: int
    process_ids: list[int]
    property_ids: list[int]  # imóveis órfãos (serão apagados)
    client_ids: list[int]  # clientes órfãos (serão apagados)
    property_ids_preserved: list[int] = field(default_factory=list)
    client_ids_preserved: list[int] = field(default_factory=list)
    document_ids: list[int] = field(default_factory=list)
    document_storage_keys: list[str] = field(default_factory=list)
    proposal_ids: list[int] = field(default_factory=list)
    contract_ids: list[int] = field(default_factory=list)
    rota_ids: list[int] = field(default_factory=list)
    thread_ids: list[int] = field(default_factory=list)
    intake_draft_ids: list[int] = field(default_factory=list)


@dataclass
class PlanStep:
    """Um passo de deleção: apaga linhas de ``model`` que casam ``whereclause``.
    A ordem na lista importa (folha → raiz, respeitando FKs RESTRICT)."""

    label: str
    model: Any
    whereclause: Any


@dataclass
class ResetReport:
    """O que o dry-run mostra e o que o execute fez. Serializável para o CLI."""

    tenant_id: int
    process_ids: list[int]
    property_ids: list[int]
    client_ids: list[int]
    property_ids_preserved: list[int]
    client_ids_preserved: list[int]
    counts: dict[str, int]
    r2_objects: int
    legislation_alerts_detached: int
    executed: bool

    def total_rows(self) -> int:
        return sum(self.counts.values())

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "process_ids": self.process_ids,
            "property_ids_apagar": self.property_ids,
            "client_ids_apagar": self.client_ids,
            "property_ids_preservados": self.property_ids_preserved,
            "client_ids_preservados": self.client_ids_preserved,
            "counts": self.counts,
            "total_rows": self.total_rows(),
            "r2_objects": self.r2_objects,
            "legislation_alerts_detached": self.legislation_alerts_detached,
            "executed": self.executed,
        }


# ---------------------------------------------------------------------------
# 1. Resolução do escopo
# ---------------------------------------------------------------------------

def _ids(rows) -> list[int]:
    return [r[0] for r in rows if r[0] is not None]


def collect_scope(
    db: Session,
    process_ids: list[int],
    tenant_id: Optional[int] = None,
) -> ResetScope:
    """Resolve a fronteira do reset a partir de uma lista EXPLÍCITA de processos.

    Valida que todos existem e pertencem ao mesmo tenant (ou ao ``tenant_id``
    dado). Deriva imóveis/clientes candidatos e decide quais são órfãos.
    """
    process_ids = sorted(set(int(p) for p in process_ids))
    if not process_ids:
        raise ResetScopeError("nenhum process_id informado — o reset nunca opera em 'tudo'.")

    procs = db.query(Process).filter(Process.id.in_(process_ids)).all()
    found = {p.id for p in procs}
    missing = set(process_ids) - found
    if missing:
        raise ResetScopeError(
            f"processo(s) inexistente(s): {sorted(missing)} — abortando antes de tocar o banco."
        )

    tenants = {p.tenant_id for p in procs}
    if len(tenants) > 1:
        raise ResetScopeError(
            f"processos de tenants diferentes: {sorted(tenants)} — reset é por tenant."
        )
    derived_tenant = next(iter(tenants))
    if tenant_id is not None and tenant_id != derived_tenant:
        raise ResetScopeError(
            f"--tenant-id={tenant_id} não bate com o tenant real dos processos ({derived_tenant})."
        )
    tenant_id = derived_tenant
    P = process_ids

    cand_prop = sorted({p.property_id for p in procs if p.property_id is not None})
    cand_client = sorted({p.client_id for p in procs if p.client_id is not None})

    # Propostas / contratos / rotas do escopo (por process_id).
    proposal_ids = _ids(db.query(Proposal.id).filter(Proposal.process_id.in_(P)).all())
    contract_ids = _ids(db.query(Contract.id).filter(Contract.process_id.in_(P)).all())
    rota_ids = _ids(db.query(Rota.id).filter(Rota.process_id.in_(P)).all())

    # Imóvel é órfão se nenhum processo FORA do escopo o referencia.
    shared_prop = set(
        _ids(
            db.query(Process.property_id)
            .filter(Process.property_id.in_(cand_prop), Process.id.notin_(P))
            .distinct()
            .all()
        )
    ) if cand_prop else set()
    property_ids = sorted(set(cand_prop) - shared_prop)
    property_ids_preserved = sorted(shared_prop)
    PR = property_ids

    # Cliente é órfão se, após remover o escopo, nada mais o referencia:
    # processo, imóvel (que não vá ser apagado), proposta ou contrato fora do escopo.
    shared_client: set[int] = set()
    if cand_client:
        shared_client |= set(
            _ids(
                db.query(Process.client_id)
                .filter(Process.client_id.in_(cand_client), Process.id.notin_(P))
                .distinct().all()
            )
        )
        shared_client |= set(
            _ids(
                db.query(Property.client_id)
                .filter(Property.client_id.in_(cand_client), Property.id.notin_(PR or [0]))
                .distinct().all()
            )
        )
        shared_client |= set(
            _ids(
                db.query(Proposal.client_id)
                .filter(
                    Proposal.client_id.in_(cand_client),
                    Proposal.id.notin_(proposal_ids or [0]),
                ).distinct().all()
            )
        )
        shared_client |= set(
            _ids(
                db.query(Contract.client_id)
                .filter(
                    Contract.client_id.in_(cand_client),
                    Contract.id.notin_(contract_ids or [0]),
                ).distinct().all()
            )
        )
    client_ids = sorted(set(cand_client) - shared_client)
    client_ids_preserved = sorted(shared_client)
    CL = client_ids

    # Drafts: ligados aos processos do escopo + os referenciados pelos docs do escopo.
    draft_ids = set(
        _ids(db.query(IntakeDraft.id).filter(IntakeDraft.linked_process_id.in_(P)).all())
    )

    # Documentos do escopo: por processo, por imóvel órfão, por cliente órfão,
    # ou por draft do escopo (mesmo padrão de _collect_client_scope do cascade).
    doc_conds = [Document.process_id.in_(P)]
    if PR:
        doc_conds.append(Document.property_id.in_(PR))
    if CL:
        doc_conds.append(Document.client_id.in_(CL))
    if draft_ids:
        doc_conds.append(Document.intake_draft_id.in_(sorted(draft_ids)))
    docs = (
        db.query(Document.id, Document.storage_key, Document.s3_key, Document.intake_draft_id)
        .filter(Document.tenant_id == tenant_id, or_(*doc_conds))
        .all()
    )
    document_ids = [d[0] for d in docs]
    storage_keys: list[str] = []
    for d in docs:
        key = d[1] or d[2]  # storage_key, fallback s3_key
        if key:
            storage_keys.append(key)
        if d[3] is not None:
            draft_ids.add(d[3])

    # Threads do escopo: por processo (case) + por cliente órfão.
    thread_conds = [CommunicationThread.process_id.in_(P)]
    if CL:
        thread_conds.append(CommunicationThread.client_id.in_(CL))
    thread_ids = _ids(
        db.query(CommunicationThread.id).filter(or_(*thread_conds)).all()
    )

    return ResetScope(
        tenant_id=tenant_id,
        process_ids=P,
        property_ids=PR,
        client_ids=CL,
        property_ids_preserved=property_ids_preserved,
        client_ids_preserved=client_ids_preserved,
        document_ids=document_ids,
        document_storage_keys=sorted(set(storage_keys)),
        proposal_ids=proposal_ids,
        contract_ids=contract_ids,
        rota_ids=rota_ids,
        thread_ids=thread_ids,
        intake_draft_ids=sorted(draft_ids),
    )


# ---------------------------------------------------------------------------
# 2. Plano de deleção (ordenado folha → raiz)
# ---------------------------------------------------------------------------

def build_plan(scope: ResetScope) -> list[PlanStep]:
    """Monta os passos de deleção na ordem que respeita as FKs medidas.

    ``audit_logs`` e ``legislation_alerts`` NÃO aparecem aqui (preservados; ver
    docstring do módulo). Passos com lista vazia são omitidos.
    """
    P = scope.process_ids
    PR = scope.property_ids
    CL = scope.client_ids
    steps: list[PlanStep] = []

    def add(label: str, model: Any, whereclause: Any, guard: bool) -> None:
        if guard:
            steps.append(PlanStep(label, model, whereclause))

    # --- filhos por processo ---
    add("process_issue_decisions", ProcessIssueDecision, ProcessIssueDecision.process_id.in_(P), bool(P))
    add("regulatory_diagnoses", RegulatoryDiagnosis, RegulatoryDiagnosis.process_id.in_(P), bool(P))
    add("extracted_field_staging", ExtractedFieldStaging, ExtractedFieldStaging.process_id.in_(P), bool(P))
    add("stage_outputs", StageOutput, StageOutput.process_id.in_(P), bool(P))
    add("acoes", Acao, Acao.process_id.in_(P), bool(P))
    add("macroetapa_checklists", MacroetapaChecklist, MacroetapaChecklist.process_id.in_(P), bool(P))
    add("intake_classification_feedback", IntakeClassificationFeedback, IntakeClassificationFeedback.process_id.in_(P), bool(P))
    add("process_decisions", ProcessDecision, ProcessDecision.process_id.in_(P), bool(P))
    add("rota_passos", RotaPasso, RotaPasso.rota_id.in_(scope.rota_ids), bool(scope.rota_ids))
    add("rotas", Rota, Rota.process_id.in_(P), bool(P))
    add("tasks", Task, Task.process_id.in_(P), bool(P))
    add("process_checklists", ProcessChecklist, ProcessChecklist.process_id.in_(P), bool(P))
    add("messages", Message, Message.thread_id.in_(scope.thread_ids), bool(scope.thread_ids))
    add("communication_threads", CommunicationThread, CommunicationThread.id.in_(scope.thread_ids), bool(scope.thread_ids))
    add("contracts", Contract, Contract.id.in_(scope.contract_ids), bool(scope.contract_ids))
    add("proposals", Proposal, Proposal.id.in_(scope.proposal_ids), bool(scope.proposal_ids))
    add("documents", Document, Document.id.in_(scope.document_ids), bool(scope.document_ids))
    add("intake_drafts", IntakeDraft, IntakeDraft.id.in_(scope.intake_draft_ids), bool(scope.intake_draft_ids))
    # AIJob liga-se por (entity_type, entity_id) sem FK — filtragem manual.
    aijob_conds = [(AIJob.entity_type == "process") & (AIJob.entity_id.in_(P))]
    if scope.document_ids:
        aijob_conds.append((AIJob.entity_type == "document") & (AIJob.entity_id.in_(scope.document_ids)))
    if scope.proposal_ids:
        aijob_conds.append((AIJob.entity_type == "proposal") & (AIJob.entity_id.in_(scope.proposal_ids)))
    add("ai_jobs", AIJob, or_(*aijob_conds), bool(P))

    # --- processos (libera RESTRICT de client) ---
    add("processes", Process, Process.id.in_(P), bool(P))

    # --- entidades laterais órfãs ---
    add("regulatory_issues", RegulatoryIssue, RegulatoryIssue.property_id.in_(PR), bool(PR))
    add("matriculas", Matricula, Matricula.property_id.in_(PR), bool(PR))
    add("credentials", Credential, Credential.client_id.in_(CL), bool(CL))
    add("properties", Property, Property.id.in_(PR), bool(PR))
    add("clients", Client, Client.id.in_(CL), bool(CL))

    return steps


def _assert_plan_safe(steps: list[PlanStep]) -> None:
    """Guard da allowlist: nenhum passo pode mirar tabela de referência."""
    for step in steps:
        table = step.model.__tablename__
        if table in ALLOWLIST_TABLES:
            raise AssertionError(
                f"BUG: plano de reset tentaria apagar tabela protegida '{table}' "
                f"(passo '{step.label}'). Abortado antes de qualquer escrita."
            )


# ---------------------------------------------------------------------------
# 3. Dry-run (contagem) e execução
# ---------------------------------------------------------------------------

def _count_alerts_to_detach(db: Session, scope: ResetScope) -> int:
    if not scope.process_ids:
        return 0
    return (
        db.query(LegislationAlert)
        .filter(LegislationAlert.process_id.in_(scope.process_ids))
        .count()
    )


def dry_run(db: Session, scope: ResetScope) -> ResetReport:
    """Conta o que cairia, sem escrever nada. É a lista que o André vê antes de
    autorizar o wipe de verdade."""
    steps = build_plan(scope)
    _assert_plan_safe(steps)
    counts = {
        step.label: db.query(step.model).filter(step.whereclause).count()
        for step in steps
    }
    return ResetReport(
        tenant_id=scope.tenant_id,
        process_ids=scope.process_ids,
        property_ids=scope.property_ids,
        client_ids=scope.client_ids,
        property_ids_preserved=scope.property_ids_preserved,
        client_ids_preserved=scope.client_ids_preserved,
        counts=counts,
        r2_objects=len(scope.document_storage_keys),
        legislation_alerts_detached=_count_alerts_to_detach(db, scope),
        executed=False,
    )


def _delete_r2_objects(s3_client, bucket: str, keys: list[str]) -> int:
    """Apaga objetos do R2/S3 em lotes de 1000 (limite do delete_objects).
    Retorna quantos foram enviados para deleção. Erros são logados, não
    mascarados — mas não abortam o reset do banco (objeto órfão < dado sujo)."""
    deleted = 0
    for i in range(0, len(keys), 1000):
        batch = keys[i : i + 1000]
        try:
            resp = s3_client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True},
            )
            errors = resp.get("Errors") or []
            for err in errors:
                logger.error(
                    "reset_casos: falha ao apagar objeto R2 %s: %s",
                    err.get("Key"), err.get("Message"),
                )
            deleted += len(batch) - len(errors)
        except Exception as exc:  # noqa: BLE001 — logamos e seguimos
            logger.error("reset_casos: erro no delete_objects (lote %d): %s", i // 1000, exc)
    return deleted


def execute_reset(
    db: Session,
    scope: ResetScope,
    *,
    user_id: Optional[int],
    s3_client: Any = None,
    bucket: Optional[str] = None,
) -> ResetReport:
    """Executa o reset dentro da transação atual (NÃO faz commit).

    Ordem: (1) apaga objetos R2 dos documentos do escopo; (2) desvincula
    legislation_alerts (preserva a linha); (3) roda o plano de deleção
    folha→raiz; (4) anexa o AuditLog do reset carimbado por último.
    """
    steps = build_plan(scope)
    _assert_plan_safe(steps)

    # (1) R2 primeiro — se o banco falhar depois e der rollback, o pior caso é
    # objeto órfão no storage (que o próprio reset já tolera), nunca linha viva
    # apontando para objeto morto.
    r2_deleted = 0
    if s3_client is not None and scope.document_storage_keys:
        r2_deleted = _delete_r2_objects(s3_client, bucket or "", scope.document_storage_keys)

    # (2) Preserva legislation_alerts desvinculando do processo antes do CASCADE.
    alerts_detached = 0
    if scope.process_ids:
        alerts_detached = (
            db.query(LegislationAlert)
            .filter(LegislationAlert.process_id.in_(scope.process_ids))
            .update({LegislationAlert.process_id: None}, synchronize_session=False)
        )

    # (3) Deleção ordenada.
    counts: dict[str, int] = {}
    for step in steps:
        counts[step.label] = (
            db.query(step.model)
            .filter(step.whereclause)
            .delete(synchronize_session=False)
        )
    db.flush()

    # (4) Registro do reset — carimbado por último para encadear no topo do tenant.
    report = ResetReport(
        tenant_id=scope.tenant_id,
        process_ids=scope.process_ids,
        property_ids=scope.property_ids,
        client_ids=scope.client_ids,
        property_ids_preserved=scope.property_ids_preserved,
        client_ids_preserved=scope.client_ids_preserved,
        counts=counts,
        r2_objects=r2_deleted,
        legislation_alerts_detached=alerts_detached,
        executed=True,
    )
    audit = AuditLog(
        tenant_id=scope.tenant_id,
        user_id=user_id,
        entity_type="reset",
        entity_id=scope.process_ids[0] if scope.process_ids else 0,
        action="reset_casos_teste",
        details=json.dumps(report.to_dict(), ensure_ascii=False),
    )
    db.add(audit)
    db.flush()
    stamp_audit_hash(db, audit)

    return report
