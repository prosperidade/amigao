"""Endpoints REST regulatórios.

Sprint A1 Tarefa D2 (read-only) + Onda B Fase 2 (POST) + PROMPT_4 Onda B
(PATCH ... /validate — camada 1 do Princípio 1) + PROMPT_6 (camada 2 do
Princípio 1 — 5 botões P4 + reconciliação dos 3 status) + PROMPT_7 (ADR-012:
`decisao_consultor` vira contextual ao processo, em `ProcessIssueDecision`).

* ``GET   /processes/{process_id}/diagnoses``                                    (lista versões)
* ``GET   /processes/{process_id}/diagnoses/{version}``                          (versão específica)
* ``POST  /processes/{process_id}/diagnoses``                                    (cria versão nova; gate A4)
* ``PATCH /processes/{process_id}/diagnoses/{version}/validate``                 (assinatura humana — camada 1; gate camada 2 rejeita se faltar ProcessIssueDecision em alerta crítico)
* ``GET   /properties/{property_id}/issues?status=...``                          (lista issues)
* ``PATCH /properties/{property_id}/issues/{issue_id}``                          (consultor edita os 2 status perenes — PROMPT_7 perdeu campos de decisão)
* ``GET   /processes/{process_id}/issues/{issue_id}/decision``                   (lê a decisão deste processo — PROMPT_7)
* ``PUT   /processes/{process_id}/issues/{issue_id}/decision``                   (cria/atualiza a decisão — PROMPT_7)

Auth: perfil ``internal``. Tenant isolation aplicada em todas as queries.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.audit_log import AuditLog
from app.models.process import Process
from app.models.property import Property
from app.models.regulatory import (
    ProcessIssueDecision,
    RegulatoryDiagnosis,
    RegulatoryIssue,
    RegulatoryIssueSeverity,
    StatusAchado,
)
from app.models.user import User
from app.schemas.regulatory import (
    IssueStatusFilter,
    ProcessIssueDecisionCreate,
    ProcessIssueDecisionOut,
    RegulatoryDiagnosisCreate,
    RegulatoryDiagnosisOut,
    RegulatoryIssueOut,
    RegulatoryIssueUpdate,
)
from app.schemas.stage_output import validate_diagnostic_content
from app.services.audit_hash import stamp_audit_hash
from app.services.regulatory_coherence import (
    StatusCoherenceError,
    assert_decisao_permitida,
    assert_status_coerente,
)

# Routers separados — segue padrão do app/api/v1/workflows.py com 2 prefixes
process_router = APIRouter()
property_router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_process_or_404(db: Session, process_id: int, tenant_id: int) -> Process:
    process = (
        db.query(Process)
        .filter(Process.id == process_id, Process.tenant_id == tenant_id)
        .first()
    )
    if process is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    return process


def _get_property_or_404(db: Session, property_id: int, tenant_id: int) -> Property:
    prop = (
        db.query(Property)
        .filter(Property.id == property_id, Property.tenant_id == tenant_id)
        .first()
    )
    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imóvel não encontrado")
    return prop


# ---------------------------------------------------------------------------
# /processes/{process_id}/diagnoses
# ---------------------------------------------------------------------------

@process_router.get("/{process_id}/diagnoses", response_model=list[RegulatoryDiagnosisOut])
def list_diagnoses(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> list[RegulatoryDiagnosis]:
    """Lista as versões de diagnóstico regulatório de um processo, mais nova primeiro."""
    _get_process_or_404(db, process_id, current_user.tenant_id)
    return (
        db.query(RegulatoryDiagnosis)
        .filter(
            RegulatoryDiagnosis.process_id == process_id,
            RegulatoryDiagnosis.tenant_id == current_user.tenant_id,
        )
        .order_by(RegulatoryDiagnosis.version.desc())
        .all()
    )


@process_router.get(
    "/{process_id}/diagnoses/{version}",
    response_model=RegulatoryDiagnosisOut,
)
def get_diagnosis_version(
    process_id: int,
    version: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> RegulatoryDiagnosis:
    """Retorna a versão específica do diagnóstico de um processo."""
    _get_process_or_404(db, process_id, current_user.tenant_id)
    diag = (
        db.query(RegulatoryDiagnosis)
        .filter(
            RegulatoryDiagnosis.process_id == process_id,
            RegulatoryDiagnosis.version == version,
            RegulatoryDiagnosis.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if diag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Versão {version} de diagnóstico não encontrada para este processo",
        )
    return diag


@process_router.post(
    "/{process_id}/diagnoses",
    response_model=RegulatoryDiagnosisOut,
    status_code=status.HTTP_201_CREATED,
)
def create_diagnosis(
    process_id: int,
    payload: RegulatoryDiagnosisCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> RegulatoryDiagnosis:
    """Cria nova versão do `RegulatoryDiagnosis` para um processo (Onda B Fase 2).

    Fluxo:
    1. Confirma que o processo existe e pertence ao tenant.
    2. Valida `payload.content` contra `DiagnosticoPreliminarContent` via
       `validate_diagnostic_content` — gate A4 Pydantic↔JSONB. ValidationError
       vira HTTP 422 com os detalhes do Pydantic.
    3. Calcula próxima versão como `max(version) + 1` para esse processo
       (ou 1 se for o primeiro).
    4. Persiste com `requires_review` implícito (validated_by_user_id=None,
       validated_at=None) — Princípio 1 do manifesto: humano valida.

    Concorrência: não trata race na geração da versão; em alta concorrência o
    `UniqueConstraint("process_id","version")` do model captura via IntegrityError
    (retorna 409). Para a sócia/consultor único, é cenário improvável.
    """
    _get_process_or_404(db, process_id, current_user.tenant_id)

    # 1) Gate Pydantic↔JSONB (A4) — valida shape antes de gravar no JSONB livre
    try:
        validate_diagnostic_content(payload.content)
    except ValidationError as exc:
        # include_context=False pula o `ctx.error` (ValueError do custom validator
        # como `_sources_non_empty`), que não é JSON-serializável.
        # include_url=False evita poluir resposta com URL da doc do pydantic.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "content não respeita o schema DiagnosticoPreliminarContent",
                "errors": exc.errors(include_url=False, include_context=False),
            },
        ) from exc

    # 2) Próxima versão
    max_version = (
        db.query(func.max(RegulatoryDiagnosis.version))
        .filter(
            RegulatoryDiagnosis.process_id == process_id,
            RegulatoryDiagnosis.tenant_id == current_user.tenant_id,
        )
        .scalar()
    )
    next_version = (max_version or 0) + 1

    # 3) Persistir
    diag = RegulatoryDiagnosis(
        tenant_id=current_user.tenant_id,
        process_id=process_id,
        content=payload.content,
        version=next_version,
        # validated_by/validated_at None — Princípio 1 (humano valida depois).
    )
    db.add(diag)
    db.commit()
    db.refresh(diag)
    return diag


@process_router.patch(
    "/{process_id}/diagnoses/{version}/validate",
    response_model=RegulatoryDiagnosisOut,
)
def validate_diagnosis(
    process_id: int,
    version: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> RegulatoryDiagnosis:
    """Marca a versão específica do `RegulatoryDiagnosis` como validada pelo
    consultor — fecha a **camada 1 do Princípio 1** ("a IA propõe; o humano
    decide e assina"). PROMPT_4 Onda B.

    Comportamento:
    1. Garante que o processo existe e pertence ao tenant.
    2. Carrega a versão específica do diagnóstico.
    3. Se já validado → **409 Conflict** (idempotência explícita; revalidação
       não silenciosa, evita sobrescrita acidental do assinante original).
    4. Grava `validated_by_user_id = current_user.id` e
       `validated_at = now(UTC)`.
    5. Cria `AuditLog(entity_type="regulatory_diagnosis", action="validated")`
       com hash chain SHA-256 (Princípio 2 — quem assinou, quando, qual
       versão).

    Não revalida o `content` aqui — o gate Pydantic já rodou na criação (POST).
    """
    process = _get_process_or_404(db, process_id, current_user.tenant_id)
    diag = (
        db.query(RegulatoryDiagnosis)
        .filter(
            RegulatoryDiagnosis.process_id == process_id,
            RegulatoryDiagnosis.version == version,
            RegulatoryDiagnosis.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if diag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Versão {version} de diagnóstico não encontrada para este processo",
        )
    if diag.validated_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Versão {version} já validada em {diag.validated_at.isoformat()} "
                f"pelo usuário {diag.validated_by_user_id}"
            ),
        )

    # PROMPT_6 + ADR-012 (PROMPT_7) — **Camada 2 do Princípio 1**:
    # cada processo decide alerta por alerta. A decisão é **contextual ao
    # processo** (ADR-012) — não herda decisão de outro trabalho. Aqui o
    # gate olha `ProcessIssueDecision` para este `process.id`, não mais um
    # campo no próprio `RegulatoryIssue`.
    #
    # PROMPT_10 — gate só cobra decisão de críticos em estado **não-terminal**
    # do achado (`suspeita` ou `confirmada`). Em `descartada`/`resolvida`/
    # `ignorada` o consultor já adjudicou que não há divergência ativa a
    # tratar — exigir decisão seria dupla negação (cf. enum `StatusAchado`
    # em `app/models/regulatory.py`). `suspeita` permanece dentro: força o
    # consultor a confirmar/descartar antes de assinar (não é deadlock, ele
    # pode mover o estado pelo `PATCH /properties/.../issues/{id}`).
    # `resolved_at IS NULL` continua porque é critério ortogonal (estado do
    # campo persistido), mesmo que nenhum fluxo do app o utilize ainda.
    if process.property_id is not None:
        issues_criticas = (
            db.query(RegulatoryIssue)
            .filter(
                RegulatoryIssue.tenant_id == current_user.tenant_id,
                RegulatoryIssue.property_id == process.property_id,
                RegulatoryIssue.severity == RegulatoryIssueSeverity.critico,
                RegulatoryIssue.resolved_at.is_(None),
                RegulatoryIssue.status_achado.in_(
                    [StatusAchado.suspeita, StatusAchado.confirmada]
                ),
            )
            .all()
        )
        if issues_criticas:
            decided_issue_ids = {
                d.issue_id for d in (
                    db.query(ProcessIssueDecision.issue_id)
                    .filter(
                        ProcessIssueDecision.tenant_id == current_user.tenant_id,
                        ProcessIssueDecision.process_id == process.id,
                        ProcessIssueDecision.issue_id.in_([i.id for i in issues_criticas]),
                    )
                    .all()
                )
            }
            pendentes = [i for i in issues_criticas if i.id not in decided_issue_ids]
            if pendentes:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "message": (
                            f"{len(pendentes)} alerta(s) crítico(s) sem decisão do consultor "
                            "neste processo — camada 2 do Princípio 1 exige decisão alerta "
                            "por alerta antes da assinatura do diagnóstico"
                        ),
                        "alertas_pendentes": [
                            {
                                "id": issue.id,
                                "codigo_alerta": issue.codigo_alerta,
                                "familia": issue.familia.value if issue.familia else None,
                                "severity": issue.severity.value,
                            }
                            for issue in pendentes
                        ],
                    },
                )

    diag.validated_by_user_id = current_user.id
    diag.validated_at = datetime.now(UTC)
    db.flush()

    # AuditLog com hash chain (Princípio 2 — auditabilidade)
    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        entity_type="regulatory_diagnosis",
        entity_id=diag.id,
        action="validated",
        new_value=diag.validated_at.isoformat(),
        details=(
            f"Diagnóstico v{version} do processo {process_id} validado "
            f"pelo consultor {current_user.email}"
        ),
    )
    db.add(audit)
    db.flush()
    stamp_audit_hash(db, audit)

    db.commit()
    db.refresh(diag)
    return diag


# ---------------------------------------------------------------------------
# /properties/{property_id}/issues
# ---------------------------------------------------------------------------

@property_router.get("/{property_id}/issues", response_model=list[RegulatoryIssueOut])
def list_property_issues(
    property_id: int,
    status_filter: IssueStatusFilter = Query(
        "open",
        alias="status",
        description="open=resolved_at is null, resolved=resolved_at is not null, all=tudo",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> list[RegulatoryIssue]:
    """Lista issues regulatórios do imóvel, filtrável por status."""
    _get_property_or_404(db, property_id, current_user.tenant_id)
    query = (
        db.query(RegulatoryIssue)
        .filter(
            RegulatoryIssue.property_id == property_id,
            RegulatoryIssue.tenant_id == current_user.tenant_id,
        )
    )
    if status_filter == "open":
        query = query.filter(RegulatoryIssue.resolved_at.is_(None))
    elif status_filter == "resolved":
        query = query.filter(RegulatoryIssue.resolved_at.is_not(None))
    # "all" → sem filtro adicional
    return query.order_by(RegulatoryIssue.detected_at.desc()).all()


@property_router.patch(
    "/{property_id}/issues/{issue_id}",
    response_model=RegulatoryIssueOut,
)
def update_property_issue(
    property_id: int,
    issue_id: int,
    payload: RegulatoryIssueUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> RegulatoryIssue:
    """Consultor edita os 2 status **perenes** do fato do imóvel.

    PROMPT_7 (ADR-012): perdeu os 3 campos de decisão (`decisao_consultor`,
    `justificativa`, `at`). A decisão é contextual ao processo agora; vive
    em `ProcessIssueDecision` e é editada via `PUT /processes/{pid}/issues/
    {iid}/decision`. Aqui ficam só `status_achado` (natureza do indício) e
    `status_saneamento` (saneamento REAL no mundo) — perenes.

    Body parcial. Cada campo alterado gera AuditLog próprio com hash chain
    SHA-256 (Princípio 2). No-op por campo (mesmo valor) NÃO gera AuditLog.

    PROMPT_8 (#17): valida coerência sobre o **estado resultante** (corpo
    aplicado sobre a issue carregada). Saneamento em `em_validacao`/`saneado`
    exige achado em `confirmada`/`resolvida`. 422 com mensagem acionável.
    """
    _get_property_or_404(db, property_id, current_user.tenant_id)
    issue = (
        db.query(RegulatoryIssue)
        .filter(
            RegulatoryIssue.id == issue_id,
            RegulatoryIssue.property_id == property_id,
            RegulatoryIssue.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if issue is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issue {issue_id} não encontrada para este imóvel",
        )

    # Coleta de mudanças efetivas (campo, valor antigo, valor novo).
    changes: list[tuple[str, str | None, str | None]] = []
    body = payload.model_dump(exclude_unset=True)

    # PROMPT_8 (#17) — coerência sobre o **estado resultante**. Cobre o caso
    # de PATCH parcial (só um dos campos no body): o helper compara o que
    # vai ficar gravado após o merge. Só roda quando ao menos um dos dois
    # status vem no body — issue não tocada nesses campos não é
    # responsabilidade desta requisição.
    if "status_achado" in body or "status_saneamento" in body:
        status_achado_final = body.get("status_achado") or issue.status_achado
        status_saneamento_final = body.get("status_saneamento") or issue.status_saneamento
        try:
            assert_status_coerente(status_achado_final, status_saneamento_final)
        except StatusCoherenceError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

    if "status_achado" in body and body["status_achado"] != issue.status_achado:
        old = issue.status_achado.value if issue.status_achado else None
        new = body["status_achado"].value
        issue.status_achado = body["status_achado"]
        changes.append(("status_achado", old, new))

    if "status_saneamento" in body and body["status_saneamento"] != issue.status_saneamento:
        old = issue.status_saneamento.value if issue.status_saneamento else None
        new = body["status_saneamento"].value
        issue.status_saneamento = body["status_saneamento"]
        changes.append(("status_saneamento", old, new))

    if not changes:
        return issue

    db.flush()

    for field, old_value, new_value in changes:
        audit = AuditLog(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            entity_type="regulatory_issue",
            entity_id=issue.id,
            action=f"{field}_changed",
            old_value=old_value,
            new_value=new_value,
            details=(
                f"Issue {issue.id} (cod={issue.codigo_alerta}) — consultor "
                f"{current_user.email} mudou {field}: {old_value!r} → {new_value!r}"
            ),
        )
        db.add(audit)
        db.flush()
        stamp_audit_hash(db, audit)

    db.commit()
    db.refresh(issue)
    return issue


# ---------------------------------------------------------------------------
# PROMPT_7 (ADR-012) — Decisão do consultor por processo (ProcessIssueDecision)
# ---------------------------------------------------------------------------

@process_router.get(
    "/{process_id}/issues/{issue_id}/decision",
    response_model=ProcessIssueDecisionOut,
)
def get_process_issue_decision(
    process_id: int,
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> ProcessIssueDecision:
    """Retorna a decisão do consultor sobre `issue_id` no contexto do
    `process_id`. 404 se ainda não há decisão (cada processo começa do
    zero — ADR-012)."""
    process = _get_process_or_404(db, process_id, current_user.tenant_id)
    decision = (
        db.query(ProcessIssueDecision)
        .filter(
            ProcessIssueDecision.tenant_id == current_user.tenant_id,
            ProcessIssueDecision.process_id == process.id,
            ProcessIssueDecision.issue_id == issue_id,
        )
        .first()
    )
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Issue {issue_id} sem decisão registrada no processo {process_id} — "
                "cada processo decide do zero (ADR-012)"
            ),
        )
    return decision


@process_router.put(
    "/{process_id}/issues/{issue_id}/decision",
    response_model=ProcessIssueDecisionOut,
)
def upsert_process_issue_decision(
    process_id: int,
    issue_id: int,
    payload: ProcessIssueDecisionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> ProcessIssueDecision:
    """**ADR-012** — cria ou atualiza (upsert) a decisão do consultor sobre
    `issue_id` no contexto do `process_id`.

    Comportamento:
    1. Valida que processo existe e pertence ao tenant.
    2. Valida que issue existe e pertence à property do processo. Se a
       property do processo é NULL, rejeita (não dá pra decidir sobre uma
       issue de outro imóvel).
    3. Se já existe decisão para `(process_id, issue_id)`, **atualiza** os
       campos alterados; gera AuditLog granular por campo
       (`entity_type="process_issue_decision"`, `action="<campo>_changed"`).
    4. Se não existe, **cria** uma nova com `decided_by_user_id=current_user.id`
       e `decided_at=now()`; gera AuditLog `action="created"`.
    5. `decided_at` é gerenciado pelo servidor em toda mudança (não aceita
       override do body).

    Validator de Pydantic já rejeita 422 quando `decisao in
    {ignorar_justificado, fora_escopo}` sem `justificativa` (Princípio 2).
    """
    process = _get_process_or_404(db, process_id, current_user.tenant_id)

    # Validar que a issue pertence à property do processo (tenant isolation
    # + integridade contextual: não dá pra decidir sobre issue de outro
    # imóvel via path do processo errado).
    if process.property_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Processo {process_id} não tem property vinculada",
        )
    issue = (
        db.query(RegulatoryIssue)
        .filter(
            RegulatoryIssue.id == issue_id,
            RegulatoryIssue.property_id == process.property_id,
            RegulatoryIssue.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if issue is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Issue {issue_id} não encontrada para o imóvel do processo "
                f"{process_id}"
            ),
        )

    # PROMPT_8 (#17) — Regra B: não dá pra decidir sobre achado em `suspeita`.
    # Decide-se o que fazer depois de confirmar que a divergência é real.
    # A mensagem é acionável para que a UI oriente o consultor a mover o
    # `status_achado` no PATCH /issues antes de tentar a decisão de novo.
    try:
        assert_decisao_permitida(issue.status_achado)
    except StatusCoherenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    existing = (
        db.query(ProcessIssueDecision)
        .filter(
            ProcessIssueDecision.tenant_id == current_user.tenant_id,
            ProcessIssueDecision.process_id == process.id,
            ProcessIssueDecision.issue_id == issue_id,
        )
        .first()
    )

    audit_entries: list[AuditLog] = []

    if existing is None:
        # Criação inicial — 1 AuditLog action="created".
        decision = ProcessIssueDecision(
            tenant_id=current_user.tenant_id,
            process_id=process.id,
            issue_id=issue_id,
            decisao=payload.decisao,
            justificativa=payload.justificativa,
            decided_by_user_id=current_user.id,
            decided_at=datetime.now(UTC),
        )
        db.add(decision)
        db.flush()

        audit_entries.append(AuditLog(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            entity_type="process_issue_decision",
            entity_id=decision.id,
            action="created",
            new_value=payload.decisao.value,
            details=(
                f"Decisão criada: processo {process_id}, issue {issue_id} "
                f"(cod={issue.codigo_alerta}) — decisao={payload.decisao.value} "
                f"por {current_user.email}"
            ),
        ))
    else:
        # Atualização — AuditLog granular por campo alterado.
        decision = existing
        if payload.decisao != decision.decisao:
            old = decision.decisao.value
            new = payload.decisao.value
            decision.decisao = payload.decisao
            decision.decided_by_user_id = current_user.id
            decision.decided_at = datetime.now(UTC)
            audit_entries.append(AuditLog(
                tenant_id=current_user.tenant_id,
                user_id=current_user.id,
                entity_type="process_issue_decision",
                entity_id=decision.id,
                action="decisao_changed",
                old_value=old,
                new_value=new,
                details=(
                    f"Decisão alterada: processo {process_id}, issue {issue_id} "
                    f"(cod={issue.codigo_alerta}) — decisao: {old!r} → {new!r}"
                ),
            ))

        if payload.justificativa != decision.justificativa:
            old = decision.justificativa
            new = payload.justificativa
            decision.justificativa = payload.justificativa
            audit_entries.append(AuditLog(
                tenant_id=current_user.tenant_id,
                user_id=current_user.id,
                entity_type="process_issue_decision",
                entity_id=decision.id,
                action="justificativa_changed",
                old_value=old,
                new_value=new,
                details=(
                    f"Justificativa alterada: processo {process_id}, issue "
                    f"{issue_id} (cod={issue.codigo_alerta})"
                ),
            ))

        if not audit_entries:
            # No-op: nenhum campo mudou. Retorna estado atual.
            return decision

        db.flush()

    # Persiste AuditLogs com hash chain SHA-256.
    for audit in audit_entries:
        db.add(audit)
        db.flush()
        stamp_audit_hash(db, audit)

    db.commit()
    db.refresh(decision)
    return decision
