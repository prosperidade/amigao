"""Endpoints REST regulatórios.

Sprint A1 Tarefa D2 (read-only) + Onda B Fase 2 (POST) + PROMPT_4 Onda B
(PATCH ... /validate — assinatura humana).

* ``GET   /processes/{process_id}/diagnoses``                       (lista versões, mais nova primeiro)
* ``GET   /processes/{process_id}/diagnoses/{version}``             (versão específica)
* ``POST  /processes/{process_id}/diagnoses``                       (cria versão nova; ativa A4 Pydantic↔JSONB)
* ``PATCH /processes/{process_id}/diagnoses/{version}/validate``    (assinatura humana — camada 1 do Princípio 1)
* ``GET   /properties/{property_id}/issues?status=...``             (lista issues, filtro por status)

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
from app.models.regulatory import RegulatoryDiagnosis, RegulatoryIssue
from app.models.user import User
from app.schemas.regulatory import (
    IssueStatusFilter,
    RegulatoryDiagnosisCreate,
    RegulatoryDiagnosisOut,
    RegulatoryIssueOut,
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
    if diag.validated_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Versão {version} já validada em {diag.validated_at.isoformat()} "
                f"pelo usuário {diag.validated_by_user_id}"
            ),
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
