"""
Proposal Generator — a proposta nasce do orçamento do tenant (ADR-081, dívida #284).

Cadeia (ADR-028 → ADR-074 → ADR-081): Rota assinada → especificação de escopo aprovada →
orçamento aprovado e atual, com os métodos e preços do tenant → proposta. Cada item da proposta
aponta o item do orçamento e o passo da Rota.

Não há mais preço de código: a ``PRICE_TABLE`` (faixa por demanda distribuída igualmente entre os
itens) e o ``OrcamentoAgent._estimate_by_rules`` saíram. Caso sem orçamento é recusa honesta — sem
Rota assinada, pede a assinatura (decisão 6: a Rota validada manda); com a Rota assinada, pede o
orçamento. Determinístico (sem LLM).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from app.models.checklist_template import ProcessChecklist
from app.models.process import Process
from app.models.rota import Rota, RotaStatus
from app.models.task import Task


class ProposalGenerationError(Exception):
    """Geração bloqueada — carrega mensagem honesta para o consultor (ex.: sem
    Rota validada). O endpoint traduz em HTTP 422."""

# ---------------------------------------------------------------------------
# Estrutura de retorno
# ---------------------------------------------------------------------------

@dataclass
class ProposalDraft:
    title: str
    demand_type: Optional[str]
    complexity: str              # "baixa" | "media" | "alta"
    scope_items: list[dict]
    suggested_value_min: float
    suggested_value_max: float
    suggested_value: float       # ponto médio arredondado
    estimated_days: int
    payment_terms: str
    notes: str
    # S5-A — Rota validada de origem (proveniência no nível da proposta).
    rota_id: Optional[int] = field(default=None)
    # ADR-074 §7 / ADR-081 — orçamento aprovado de origem (sempre presente).
    orcamento_id: Optional[int] = field(default=None)


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def generate_proposal_from_rota(
    db: Session,
    process_id: int,
    tenant_id: int,
) -> ProposalDraft:
    """Rascunho da proposta a partir do orçamento aprovado e atual do caso (ADR-081).

    Sem orçamento → ``ProposalGenerationError`` com o próximo passo: assinar a Rota ou gerar e
    aprovar o orçamento. Nunca preço de tabela.
    """
    process = db.query(Process).filter(
        Process.id == process_id,
        Process.tenant_id == tenant_id,
    ).first()
    if process is None:
        raise ProposalGenerationError("Processo não encontrado.")
    return _draft_do_orcamento(db, process, tenant_id, exigir_orcamento(db, tenant_id, process_id))


def exigir_orcamento(db: Session, tenant_id: int, process_id: int, orcamento_id: Optional[int] = None):
    """Porta única da proposta de um caso (criar, rascunho, renegociar): o orçamento aprovado e atual.

    Decisão 6 (ADR-074): a Rota assinada manda — sem ela, a recusa pede a assinatura antes de
    falar de orçamento.
    """
    orc = orcamento_para_proposta(db, tenant_id, process_id, orcamento_id)
    if orc is not None:
        return orc
    assinada = db.query(Rota.id).filter(Rota.tenant_id == tenant_id, Rota.process_id == process_id,
                                        Rota.status == RotaStatus.validada).first()
    if assinada is None:
        raise ProposalGenerationError(
            "A proposta nasce da Rota assinada: feche (assine) a Rota Regulatória na etapa "
            "'Caminho Regulatório' antes de gerar a proposta."
        )
    raise ProposalGenerationError(
        "A proposta nasce do orçamento: gere e aprove o relatório, o escopo e o orçamento da Rota "
        "assinada (aba Comercial) antes da proposta."
    )


# ---------------------------------------------------------------------------
# Orçamento (ADR-074 §7)
# ---------------------------------------------------------------------------

_UNIDADE_PROPOSTA = {"hora": "h", "unidade": "un", "fixo": "serv."}


def orcamento_para_proposta(db: Session, tenant_id: int, process_id: int, orcamento_id: Optional[int] = None):
    """O orçamento de onde a proposta nasce, ou None se o caso não tem orçamento.

    Havendo orçamento, ele manda: a versão mais nova, aprovada e atual. Pedir outra
    versão, ou uma que não esteja aprovada e atual, é recusa honesta — nunca preço de tabela.
    """
    from app.services.comercial import base as base_mod  # noqa: PLC0415

    orc = base_mod.ultimo_orcamento(db, tenant_id, process_id)
    if orc is None:
        if orcamento_id is not None:
            raise ProposalGenerationError("Este processo não tem o orçamento informado.")
        return None
    if orcamento_id is not None and orcamento_id != orc.id:
        raise ProposalGenerationError(f"A proposta nasce do orçamento mais novo (v{orc.versao}, id {orc.id}).")
    if orc.estado_revisao != "aprovada":
        raise ProposalGenerationError(f"O orçamento v{orc.versao} ainda não foi aprovado pelo consultor.")
    atual = base_mod.atualidade(db, orc)
    if atual["estado"] != "vigente":
        raise ProposalGenerationError(f"O orçamento v{orc.versao} está desatualizado: " + "; ".join(atual["motivos"])
                                      + ". Gere o orçamento de novo.")
    return orc


def itens_do_orcamento(orcamento) -> list[dict]:
    return [{
        "description": i.descricao,
        "detail": i.calculo,
        "unit": _UNIDADE_PROPOSTA.get(i.unidade, "serv."),
        "qty": float(i.quantidade),
        "unit_price": float(i.valor_unitario),
        "total": float(i.total),
        "rota_passo_id": i.rota_passo_id,
        "orcamento_item_id": i.id,
        "norma_ref": (i.fundamento or {}).get("caminho"),
        "prazo_dias": None,
    } for i in orcamento.itens]


def _draft_do_orcamento(db: Session, process: Process, tenant_id: int, orcamento) -> ProposalDraft:
    from app.models.rota import RotaPasso  # noqa: PLC0415

    passo_ids = [i.rota_passo_id for i in orcamento.itens if i.rota_passo_id]
    prazos = [p for (p,) in db.query(RotaPasso.prazo_estimado_dias)
              .filter(RotaPasso.id.in_(passo_ids), RotaPasso.tenant_id == tenant_id) if p] if passo_ids else []
    itens = itens_do_orcamento(orcamento)
    total = float(orcamento.total)
    complexity = _estimate_complexity(db, process.id, tenant_id, process.urgency)
    demand_type = process.demand_type.value if process.demand_type else None
    return ProposalDraft(
        title=f"Proposta — {process.title}" if process.title else "Proposta Comercial",
        demand_type=demand_type,
        complexity=complexity,
        scope_items=itens,
        suggested_value_min=total,
        suggested_value_max=total,
        suggested_value=total,
        estimated_days=max(prazos, default=0),
        payment_terms="50% na assinatura do contrato e 50% na entrega do serviço.",
        notes=f"Valores do orçamento v{orcamento.versao}, aprovado; cada item aponta o passo da Rota validada.",
        rota_id=orcamento.rota_id,
        orcamento_id=orcamento.id,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _estimate_complexity(
    db: Session,
    process_id: int,
    tenant_id: int,
    urgency: Optional[str],
) -> str:
    """
    Estima complexidade do processo baseado em indicadores objetivos.
    Retorna "baixa", "media" ou "alta".
    """
    score = 0

    # Urgência
    if urgency == "alta":
        score += 1
    elif urgency == "critica":
        score += 2

    # Documentos pendentes
    checklist = (
        db.query(ProcessChecklist)
        .filter(ProcessChecklist.process_id == process_id)
        .first()
    )
    if checklist:
        items = checklist.items or []
        pending = sum(1 for i in items if i.get("status") == "pending")
        if pending >= 8:
            score += 2
        elif pending >= 4:
            score += 1

    # Nº de tarefas na trilha
    task_count = (
        db.query(Task)
        .filter(Task.process_id == process_id, Task.tenant_id == tenant_id)
        .count()
    )
    if task_count >= 7:
        score += 1

    if score >= 3:
        return "alta"
    elif score >= 1:
        return "media"
    return "baixa"
