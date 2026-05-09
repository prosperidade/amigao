"""Endpoint de classificação canônica + stats de precisão — Sprint A1 Tarefa E.

Resolve o cenário "Plano B" da Q3 da Fase 0: como o fluxo CAM1-003 cria
todo processo com ``demand_type=nao_identificado`` e nenhum endpoint hoje
permite atualizar esse campo, criamos ``POST /processes/{id}/classify``
como ponto canônico de classificação humana.

Endpoints (auth: internal profile):
* ``POST /processes/{process_id}/classify`` — atualiza ``Process.demand_type``
  e grava log em ``intake_classification_feedback`` quando o consultor
  diverge da última saída do AtendimentoAgent.
* ``GET /admin/intake-feedback/stats`` — métricas agregadas
  (tenant-scoped: cada interno vê só os logs do seu tenant).

Idempotência:
* Cada chamada de ``/classify`` gera 1 log. ``accuracy_overall`` usa o
  **último** log por processo (consultor pode reclassificar várias vezes).

Sem máquina-de-estados em ``demand_type`` — qualquer transição é aceita,
inclusive voltar para ``nao_identificado``.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.ai_job import AIJob
from app.models.audit_log import AuditLog
from app.models.intake_classification_feedback import IntakeClassificationFeedback
from app.models.intake_draft import IntakeDraft
from app.models.process import DemandType, Process
from app.models.user import User
from app.schemas.intake_feedback import (
    ClassifyDemandRequest,
    ClassifyDemandResponse,
    IntakeFeedbackStats,
)

logger = logging.getLogger(__name__)

# 2 routers — mesmo padrão de regulatory.py / workflows.py
classify_router = APIRouter()      # montado em /processes
admin_router = APIRouter()         # montado em /admin

TOP_CORRECTIONS_LIMIT = 10


def _last_atendimento_job(
    db: Session, *, tenant_id: int, intake_draft_id: int | None,
) -> AIJob | None:
    """Retorna o último AIJob do AtendimentoAgent vinculado ao mesmo intake.

    O AtendimentoAgent roda durante o draft (antes do commit). O AIJob
    correspondente fica registrado com ``agent_name='atendimento'`` e o
    ``intake_draft.linked_process_id`` aponta para o ``Process`` resultante.

    Aceitamos também jobs que não estão vinculados ao draft (ex.: agentes
    rodados manualmente via ``/agents/run`` com ``intake_draft_id`` em
    ``input_payload``) — fallback que, em produção, raramente ocorre.
    """
    query = (
        db.query(AIJob)
        .filter(
            AIJob.tenant_id == tenant_id,
            AIJob.agent_name == "atendimento",
        )
        .order_by(desc(AIJob.id))
    )
    if intake_draft_id is not None:
        # entity_id pode apontar para draft ou processo dependendo do caller;
        # filtramos amplamente pra cobrir os 2 cenários.
        query = query.filter(
            (AIJob.entity_type == "intake_draft") & (AIJob.entity_id == intake_draft_id),
        )
    return query.first()


@classify_router.post(
    "/{process_id}/classify",
    response_model=ClassifyDemandResponse,
)
def classify_demand(
    process_id: int,
    payload: ClassifyDemandRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Atualiza Process.demand_type + log de feedback quando IA divergir.

    Sem máquina-de-estados — aceita qualquer transição (inclusive voltar
    para ``nao_identificado``).
    """
    process = (
        db.query(Process)
        .filter(Process.id == process_id, Process.tenant_id == current_user.tenant_id)
        .first()
    )
    if process is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")

    previous = process.demand_type.value if process.demand_type else None
    new_value: DemandType = payload.demand_type

    # Localizar o draft que originou esse processo (se houver) — vincula ao log.
    draft = (
        db.query(IntakeDraft)
        .filter(
            IntakeDraft.linked_process_id == process_id,
            IntakeDraft.tenant_id == current_user.tenant_id,
        )
        .first()
    )

    # Recuperar última classificação do AtendimentoAgent para o mesmo intake.
    ai_job = _last_atendimento_job(
        db,
        tenant_id=current_user.tenant_id,
        intake_draft_id=draft.id if draft else None,
    )
    ai_demand_type: str | None = None
    ai_confidence: float | None = None
    if ai_job and isinstance(ai_job.result, dict):
        ai_demand_type = ai_job.result.get("demand_type") or ai_job.result.get("classification")
        # confidence pode vir como str ("high" | "medium" | "low") ou float
        raw_conf = ai_job.result.get("confidence")
        if isinstance(raw_conf, (int, float)):
            ai_confidence = float(raw_conf)

    # Atualiza Process.demand_type
    process.demand_type = new_value

    # Grava log SEMPRE — convenção: cada chamada de /classify é um evento.
    # Mesmo quando IA acertou, ter o registro permite confirmar accuracy.
    feedback = IntakeClassificationFeedback(
        tenant_id=current_user.tenant_id,
        process_id=process_id,
        intake_draft_id=draft.id if draft else None,
        ai_demand_type=ai_demand_type,
        ai_confidence=ai_confidence,
        ai_run_id=ai_job.id if ai_job else None,
        corrected_demand_type=new_value.value,
        corrected_by_user_id=current_user.id,
    )
    db.add(feedback)

    # Trilha de auditoria genérica (espelha decisions.py / processes.py)
    db.add(AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        entity_type="process",
        entity_id=process_id,
        action="demand_type_classified",
        details=f"demand_type {previous} → {new_value.value}",
        old_value=previous,
        new_value=new_value.value,
    ))

    db.commit()
    db.refresh(feedback)

    diverged = ai_demand_type is not None and ai_demand_type != new_value.value

    logger.info(
        "intake_feedback.classify process_id=%s previous=%s new=%s ai=%s diverged=%s",
        process_id, previous, new_value.value, ai_demand_type, diverged,
    )

    return ClassifyDemandResponse(
        process_id=process_id,
        previous_demand_type=previous,
        new_demand_type=new_value.value,
        feedback_logged=True,
        feedback_id=feedback.id,
        ai_demand_type=ai_demand_type,
        diverged_from_ai=diverged,
    )


@admin_router.get("/intake-feedback/stats", response_model=IntakeFeedbackStats)
def intake_feedback_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Métricas agregadas de precisão do AtendimentoAgent (tenant-scoped).

    Convenção:
    * Cada processo conta apenas o **último** log (consultor pode
      reclassificar várias vezes — só a decisão final entra na métrica).
    * ``total_classifications`` é o tamanho do universo (processos com pelo
      menos 1 log no tenant).
    * ``total_corrections`` é o subconjunto onde IA divergiu do humano.
    * ``accuracy_overall`` = ``1 - corrections/classifications``.
    """
    # Pega o último feedback por processo no tenant.
    subq = (
        select(
            IntakeClassificationFeedback.process_id,
            IntakeClassificationFeedback.ai_demand_type,
            IntakeClassificationFeedback.corrected_demand_type,
            IntakeClassificationFeedback.id.label("fb_id"),
        )
        .where(IntakeClassificationFeedback.tenant_id == current_user.tenant_id)
        .order_by(
            IntakeClassificationFeedback.process_id,
            desc(IntakeClassificationFeedback.id),
        )
    )
    rows = db.execute(subq).all()

    seen: set[int] = set()
    last_by_process: list[tuple[str | None, str]] = []
    for r in rows:
        if r.process_id in seen:
            continue
        seen.add(r.process_id)
        last_by_process.append((r.ai_demand_type, r.corrected_demand_type))

    total = len(last_by_process)
    if total == 0:
        return IntakeFeedbackStats(
            total_classifications=0,
            total_corrections=0,
            accuracy_overall=0.0,
            accuracy_by_demand_type={},
            top_corrections=[],
        )

    corrections: list[tuple[str | None, str]] = [
        (ai, hu) for ai, hu in last_by_process if ai is not None and ai != hu
    ]
    correction_count = len(corrections)
    accuracy_overall = 1.0 - (correction_count / total)

    # accuracy por demand_type humano (denominador = quantos processos foram
    # classificados como esse tipo; numerador = quantos a IA acertou).
    by_type_total: Counter[str] = Counter()
    by_type_correct: Counter[str] = Counter()
    for ai, hu in last_by_process:
        by_type_total[hu] += 1
        if ai == hu:
            by_type_correct[hu] += 1
    accuracy_by_demand_type = {
        dt: round(by_type_correct[dt] / by_type_total[dt], 4)
        for dt in by_type_total
    }

    # Top corrections: pares "X -> Y" mais frequentes (X = IA, Y = humano)
    pair_counter: Counter[tuple[str, str]] = Counter()
    for ai, hu in corrections:
        if ai is not None:
            pair_counter[(ai, hu)] += 1
    top_corrections = [
        (f"{ai} -> {hu}", count)
        for (ai, hu), count in pair_counter.most_common(TOP_CORRECTIONS_LIMIT)
    ]

    return IntakeFeedbackStats(
        total_classifications=total,
        total_corrections=correction_count,
        accuracy_overall=round(accuracy_overall, 4),
        accuracy_by_demand_type=accuracy_by_demand_type,
        top_corrections=top_corrections,
    )
