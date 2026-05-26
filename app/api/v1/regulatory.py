"""Endpoints REST regulatórios.

Sprint A1 Tarefa D2 (read-only) + Onda B Fase 2 (POST) + PROMPT_4 Onda B
(PATCH ... /validate — camada 1 do Princípio 1) + PROMPT_6 (camada 2 do
Princípio 1 — 5 botões P4 + reconciliação dos 3 status).

* ``GET   /processes/{process_id}/diagnoses``                       (lista versões, mais nova primeiro)
* ``GET   /processes/{process_id}/diagnoses/{version}``             (versão específica)
* ``POST  /processes/{process_id}/diagnoses``                       (cria versão nova; ativa A4 Pydantic↔JSONB)
* ``PATCH /processes/{process_id}/diagnoses/{version}/validate``    (assinatura humana — camada 1; **gate** rejeita se faltar decisao_consultor em alerta crítico — camada 2)
* ``GET   /properties/{property_id}/issues?status=...``             (lista issues, filtro por status)
* ``PATCH /properties/{property_id}/issues/{issue_id}``             (consultor edita os 3 status + decisao — PROMPT_6)

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
    RegulatoryDiagnosis,
    RegulatoryIssue,
    RegulatoryIssueSeverity,
)
from app.models.user import User
from app.schemas.regulatory import (
    IssueStatusFilter,
    RegulatoryDiagnosisCreate,
    RegulatoryDiagnosisOut,
    RegulatoryIssueOut,
    RegulatoryIssueUpdate,
)
from app.schemas.stage_output import validate_diagnostic_content
from app.services.audit_hash import stamp_audit_hash

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

    # PROMPT_6 — **Camada 2 do Princípio 1**: a IA propõe, o humano decide,
    # alerta por alerta. Todo `RegulatoryIssue` crítico do imóvel deste
    # processo precisa ter `decisao_consultor` preenchido antes da assinatura
    # do diagnóstico. Sem isso, retornamos 422 com a lista de issues
    # pendentes — o frontend mostra cada uma para o consultor decidir.
    if process.property_id is not None:
        pendentes = (
            db.query(RegulatoryIssue)
            .filter(
                RegulatoryIssue.tenant_id == current_user.tenant_id,
                RegulatoryIssue.property_id == process.property_id,
                RegulatoryIssue.severity == RegulatoryIssueSeverity.critico,
                RegulatoryIssue.decisao_consultor.is_(None),
                RegulatoryIssue.resolved_at.is_(None),
            )
            .all()
        )
        if pendentes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": (
                        f"{len(pendentes)} alerta(s) crítico(s) sem decisão do consultor — "
                        "camada 2 do Princípio 1 exige decisão alerta por alerta antes da "
                        "assinatura do diagnóstico"
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
    """**PROMPT_6** — consultor edita os 3 status + decisão sobre alerta.

    Implementa a **Opção A** da reconciliação (3 dimensões ortogonais
    + decisão da camada 2 do Princípio 1).

    Comportamento:
    1. Valida que property existe e pertence ao tenant + issue pertence à
       property.
    2. Para cada campo presente no body (parcial é OK), grava
       `AuditLog(entity_type="regulatory_issue", action="<campo>_changed")`
       com hash chain SHA-256. `old_value` e `new_value` populados em string.
       Mudança "sem mudança" (mesmo valor) **não** gera AuditLog.
    3. Quando `decisao_consultor` é setado pela primeira vez (transição
       NULL → valor), `decisao_consultor_at` é gravado automaticamente.
       Mudança valor → outro valor também atualiza o timestamp.
    4. Retorna a issue atualizada (com taxonomia rica + 3 status).

    O body é parcial — campos ausentes não são tocados. Body vazio é OK
    (no-op + retorna o estado atual).
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

    # Coleta de mudanças efetivas (campo, valor antigo, valor novo). Só
    # gera AuditLog para campos que de fato mudaram — repetir o mesmo valor
    # não é evento auditável.
    changes: list[tuple[str, str | None, str | None]] = []

    body = payload.model_dump(exclude_unset=True)

    if "status_achado" in body and body["status_achado"] != issue.status_achado:
        old = issue.status_achado.value if issue.status_achado else None
        new = body["status_achado"].value
        issue.status_achado = body["status_achado"]
        changes.append(("status_achado", old, new))

    if "decisao_consultor" in body and body["decisao_consultor"] != issue.decisao_consultor:
        old = issue.decisao_consultor.value if issue.decisao_consultor else None
        new = body["decisao_consultor"].value if body["decisao_consultor"] else None
        issue.decisao_consultor = body["decisao_consultor"]
        # Timestamp da decisão: marca em qualquer mudança não-trivial.
        # Limpar (NULL) também é decisão — registra timestamp de "tirei a decisão".
        issue.decisao_consultor_at = datetime.now(UTC)
        changes.append(("decisao_consultor", old, new))

    if "decisao_consultor_justificativa" in body and (
        body["decisao_consultor_justificativa"] != issue.decisao_consultor_justificativa
    ):
        old = issue.decisao_consultor_justificativa
        new = body["decisao_consultor_justificativa"]
        issue.decisao_consultor_justificativa = new
        changes.append(("decisao_consultor_justificativa", old, new))

    if "status_saneamento" in body and body["status_saneamento"] != issue.status_saneamento:
        old = issue.status_saneamento.value if issue.status_saneamento else None
        new = body["status_saneamento"].value
        issue.status_saneamento = body["status_saneamento"]
        changes.append(("status_saneamento", old, new))

    if not changes:
        # No-op: nenhum campo mudou de valor. Retorna estado atual sem
        # gerar AuditLog (não é evento auditável).
        return issue

    db.flush()

    # Um AuditLog por campo alterado (Princípio 2 — auditoria granular).
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
