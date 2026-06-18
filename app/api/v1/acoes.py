"""Endpoints da Ficha 07 — Ações (aba do caso + Quadro de Ações global).

* ``GET   /processes/{process_id}/acoes``                  (lista do caso; filtra status/triagem)
* ``POST  /processes/{process_id}/acoes``                  (criação manual)
* ``POST  /processes/{process_id}/acoes/generate``         (gera do diagnóstico — idempotente)
* ``PATCH /processes/{process_id}/acoes/{acao_id}``        (edita status/prazo/prioridade/título)
* ``POST  /processes/{process_id}/acoes/{acao_id}/triagem``(tarefa/escopo/dispensar — Princípio 1)
* ``GET   /acoes/kanban``                                  (quadro global por status, todos os casos)

Auth: perfil ``internal``. Tenant isolation em todas as queries.

Princípio 1 (a IA propõe; o consultor decide): ações geradas nascem
``tipo_triagem="pendente"``; a triagem é decisão humana. Concluir uma ação
**não** altera o passivo de origem (ADR-016) — não há nenhum caminho de
escrita daqui para ``RegulatoryIssue``/achado.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.acao import (
    Acao,
    AcaoOrigem,
    AcaoStatus,
    AcaoTipoTriagem,
)
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.process import Process
from app.models.property import Property
from app.models.user import User
from app.schemas.acao import (
    AcaoCreate,
    AcaoGenerateOut,
    AcaoKanbanCard,
    AcaoKanbanColumn,
    AcaoKanbanResponse,
    AcaoOut,
    AcaoTriagemDecision,
    AcaoUpdate,
)
from app.services.acao_generator import generate_acoes_from_diagnosis
from app.services.audit_hash import stamp_audit_hash

process_router = APIRouter()
acoes_router = APIRouter()


_STATUS_LABELS: dict[AcaoStatus, str] = {
    AcaoStatus.a_fazer: "A fazer",
    AcaoStatus.em_andamento: "Em andamento",
    AcaoStatus.concluida: "Concluída",
    AcaoStatus.bloqueada: "Bloqueada",
}

_TRIAGEM_MAP: dict[Literal["tarefa", "escopo", "dispensar"], AcaoTipoTriagem] = {
    "tarefa": AcaoTipoTriagem.tarefa,
    "escopo": AcaoTipoTriagem.escopo,
    "dispensar": AcaoTipoTriagem.dispensada,
}


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


def _get_acao_or_404(db: Session, acao_id: int, process_id: int, tenant_id: int) -> Acao:
    acao = (
        db.query(Acao)
        .filter(
            Acao.id == acao_id,
            Acao.process_id == process_id,
            Acao.tenant_id == tenant_id,
        )
        .first()
    )
    if acao is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ação {acao_id} não encontrada neste processo",
        )
    return acao


def _audit(
    db: Session,
    *,
    tenant_id: int,
    user_id: int,
    acao_id: int,
    action: str,
    old_value: str | None = None,
    new_value: str | None = None,
    details: str | None = None,
) -> None:
    """AuditLog com hash chain SHA-256 (Princípio 2 — auditável)."""
    log = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        entity_type="acao",
        entity_id=acao_id,
        action=action,
        old_value=old_value,
        new_value=new_value,
        details=details,
    )
    db.add(log)
    db.flush()
    stamp_audit_hash(db, log)


# ---------------------------------------------------------------------------
# /processes/{process_id}/acoes
# ---------------------------------------------------------------------------


@process_router.get("/{process_id}/acoes", response_model=list[AcaoOut])
def list_acoes(
    process_id: int,
    status_filter: AcaoStatus | None = Query(default=None, alias="status"),
    tipo_triagem: AcaoTipoTriagem | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> list[Acao]:
    """Lista as ações deste caso, filtráveis por status e tipo de triagem."""
    _get_process_or_404(db, process_id, current_user.tenant_id)
    query = db.query(Acao).filter(
        Acao.process_id == process_id,
        Acao.tenant_id == current_user.tenant_id,
    )
    if status_filter is not None:
        query = query.filter(Acao.status == status_filter)
    if tipo_triagem is not None:
        query = query.filter(Acao.tipo_triagem == tipo_triagem)
    return query.order_by(Acao.created_at.desc(), Acao.id.desc()).all()


@process_router.post(
    "/{process_id}/acoes",
    response_model=AcaoOut,
    status_code=status.HTTP_201_CREATED,
)
def create_acao(
    process_id: int,
    payload: AcaoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Acao:
    """Criação **manual** de ação (consultor cria do zero — Ficha 07 §2)."""
    _get_process_or_404(db, process_id, current_user.tenant_id)

    acao = Acao(
        tenant_id=current_user.tenant_id,
        process_id=process_id,
        titulo=payload.titulo,
        descricao=payload.descricao,
        origem=AcaoOrigem.manual,
        origem_descricao=payload.origem_descricao,
        origem_fontes=payload.origem_fontes or [],
        vinculo_passivo=payload.vinculo_passivo,
        prioridade=payload.prioridade,
        prazo=payload.prazo,
        status=payload.status,
        tipo_triagem=payload.tipo_triagem,
        created_by_user_id=current_user.id,
        # dedupe_key NULL — manuais nunca colidem entre si.
    )
    db.add(acao)
    db.flush()
    _audit(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        acao_id=acao.id,
        action="created",
        new_value=acao.titulo,
        details=f"Ação manual criada no processo {process_id} por {current_user.email}",
    )
    db.commit()
    db.refresh(acao)
    return acao


@process_router.post(
    "/{process_id}/acoes/generate",
    response_model=AcaoGenerateOut,
)
def generate_acoes(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> AcaoGenerateOut:
    """Gera ações ``pendente`` a partir do diagnóstico mais recente do processo.

    Idempotente (Ficha 07 §2): não duplica ações já geradas. Cada ação nasce
    com fonte (#70) e aguardando triagem do consultor (Princípio 1).
    """
    process = _get_process_or_404(db, process_id, current_user.tenant_id)

    created, skipped, version = generate_acoes_from_diagnosis(
        db, process=process, tenant_id=current_user.tenant_id
    )

    for acao in created:
        _audit(
            db,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            acao_id=acao.id,
            action="generated",
            new_value=acao.titulo,
            details=(
                f"Ação gerada do diagnóstico v{version} do processo {process_id} "
                f"(origem: {acao.origem_descricao or '—'})"
            ),
        )

    db.commit()
    for acao in created:
        db.refresh(acao)

    return AcaoGenerateOut(
        created=len(created),
        skipped=skipped,
        diagnosis_version=version,
        acoes=[AcaoOut.model_validate(a) for a in created],
    )


@process_router.patch(
    "/{process_id}/acoes/{acao_id}",
    response_model=AcaoOut,
)
def update_acao(
    process_id: int,
    acao_id: int,
    payload: AcaoUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Acao:
    """Edita status, prazo, prioridade, título, descrição, responsável.

    Cada campo alterado gera AuditLog próprio com hash chain (Princípio 2).
    Concluir (``status=concluida``) carimba ``concluida_at`` mas **não** altera
    o passivo de origem (ADR-016)."""
    _get_process_or_404(db, process_id, current_user.tenant_id)
    acao = _get_acao_or_404(db, acao_id, process_id, current_user.tenant_id)

    body = payload.model_dump(exclude_unset=True)
    changes: list[tuple[str, str | None, str | None]] = []

    for field in ("titulo", "descricao", "prioridade", "status", "responsavel_id", "prazo"):
        if field not in body:
            continue
        new = body[field]
        old = getattr(acao, field)
        if old == new:
            continue
        # Enum → value; date/None → str para o audit.
        old_str = old.value if hasattr(old, "value") else (str(old) if old is not None else None)
        new_str = new.value if hasattr(new, "value") else (str(new) if new is not None else None)
        setattr(acao, field, new)
        changes.append((field, old_str, new_str))

    if not changes:
        return acao

    # Carimbo de conclusão (espelha o estado; não toca o passivo).
    if acao.status == AcaoStatus.concluida and acao.concluida_at is None:
        acao.concluida_at = datetime.now(UTC)
    elif acao.status != AcaoStatus.concluida:
        acao.concluida_at = None

    db.flush()
    for field, old_str, new_str in changes:
        _audit(
            db,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            acao_id=acao.id,
            action=f"{field}_changed",
            old_value=old_str,
            new_value=new_str,
            details=f"Ação {acao.id} — {current_user.email} mudou {field}: {old_str!r} → {new_str!r}",
        )

    db.commit()
    db.refresh(acao)
    return acao


@process_router.post(
    "/{process_id}/acoes/{acao_id}/triagem",
    response_model=AcaoOut,
)
def triar_acao(
    process_id: int,
    acao_id: int,
    payload: AcaoTriagemDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Acao:
    """Triagem do consultor (Princípio 1): tarefa | escopo | dispensar.

    ``escopo`` **apenas marca** a ação como candidata a item de proposta — a
    ponte com o Orçamento é consumida depois (NÃO construímos o Orçamento aqui).
    Nenhuma triagem altera o passivo de origem."""
    _get_process_or_404(db, process_id, current_user.tenant_id)
    acao = _get_acao_or_404(db, acao_id, process_id, current_user.tenant_id)

    novo = _TRIAGEM_MAP[payload.decisao]
    old = acao.tipo_triagem
    if old == novo:
        return acao

    acao.tipo_triagem = novo
    db.flush()
    _audit(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        acao_id=acao.id,
        action="triagem",
        old_value=old.value,
        new_value=novo.value,
        details=(
            f"Triagem da ação {acao.id} no processo {process_id}: "
            f"{old.value} → {novo.value} (por {current_user.email})"
        ),
    )
    db.commit()
    db.refresh(acao)
    return acao


# ---------------------------------------------------------------------------
# /acoes/kanban — Quadro de Ações global (por status)
# ---------------------------------------------------------------------------


@acoes_router.get("/kanban", response_model=AcaoKanbanResponse)
def acoes_kanban(
    tipo_triagem: AcaoTipoTriagem | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> AcaoKanbanResponse:
    """Quadro global: ações de TODOS os casos do tenant, agrupadas por status.

    Cada card mostra o caso de origem (título do processo, cliente, imóvel).
    Mover um card de coluna = ``PATCH .../acoes/{id}`` com novo ``status``.
    """
    rows = (
        db.query(Acao, Process.title, Client.full_name, Property.name)
        .join(Process, Process.id == Acao.process_id)
        .outerjoin(Client, Client.id == Process.client_id)
        .outerjoin(Property, Property.id == Process.property_id)
        .filter(Acao.tenant_id == current_user.tenant_id)
        .order_by(Acao.created_at.desc(), Acao.id.desc())
    )
    if tipo_triagem is not None:
        rows = rows.filter(Acao.tipo_triagem == tipo_triagem)

    grouped: dict[AcaoStatus, list[AcaoKanbanCard]] = {s: [] for s in AcaoStatus}
    total = 0
    for acao, process_title, client_name, property_name in rows.all():
        card = AcaoKanbanCard.model_validate(acao)
        card.process_title = process_title
        card.client_name = client_name
        card.property_name = property_name
        grouped[acao.status].append(card)
        total += 1

    columns = [
        AcaoKanbanColumn(
            status=s,
            label=_STATUS_LABELS[s],
            count=len(grouped[s]),
            cards=grouped[s],
        )
        # Ordem fixa das colunas do kanban.
        for s in (
            AcaoStatus.a_fazer,
            AcaoStatus.em_andamento,
            AcaoStatus.concluida,
            AcaoStatus.bloqueada,
        )
    ]
    return AcaoKanbanResponse(columns=columns, total=total)
