"""
MacroetapaEngine — logica de negocio para avancar, calcular e inicializar macroetapas.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.macroetapa import (
    DEFAULT_ACTIONS,
    MACROETAPA_AGENT_CHAIN,
    MACROETAPA_INDEX,
    MACROETAPA_LABELS,
    MACROETAPA_ORDER,
    Macroetapa,
    MacroetapaChecklist,
    get_stage_agents,
    is_valid_macroetapa_transition,
)
from app.models.process import Process

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Inicializar checklists para um processo
# ---------------------------------------------------------------------------

def initialize_macroetapa_checklists(
    db: Session,
    process: Process,
    tenant_id: int,
) -> list[MacroetapaChecklist]:
    """Cria os checklists de todas as 7 macroetapas para um processo."""
    created = []
    for etapa in MACROETAPA_ORDER:
        existing = (
            db.query(MacroetapaChecklist)
            .filter(
                MacroetapaChecklist.process_id == process.id,
                MacroetapaChecklist.macroetapa == etapa,
            )
            .first()
        )
        if existing:
            continue

        actions = [
            {**a, "completed": False, "completed_at": None, "agent_suggestion": None}
            for a in DEFAULT_ACTIONS.get(etapa, [])
        ]
        checklist = MacroetapaChecklist(
            tenant_id=tenant_id,
            process_id=process.id,
            macroetapa=etapa,
            actions=actions,
            completion_pct=0.0,
        )
        db.add(checklist)
        created.append(checklist)

    if created:
        db.flush()
    return created


# ---------------------------------------------------------------------------
# Calcular completion %
# ---------------------------------------------------------------------------

def calculate_completion_pct(actions: list[dict]) -> float:
    """Calcula % de conclusao baseado nas acoes do checklist."""
    if not actions:
        return 0.0
    completed = sum(1 for a in actions if a.get("completed"))
    return round((completed / len(actions)) * 100, 1)


def recalculate_checklist(checklist: MacroetapaChecklist) -> None:
    """Recalcula completion_pct de um checklist existente."""
    checklist.completion_pct = calculate_completion_pct(checklist.actions)


# ---------------------------------------------------------------------------
# Toggle acao do checklist
# ---------------------------------------------------------------------------

def toggle_action(
    db: Session,
    checklist: MacroetapaChecklist,
    action_id: str,
    completed: bool,
) -> MacroetapaChecklist:
    """Marca/desmarca uma acao no checklist."""
    actions = list(checklist.actions)  # copia para trigger de update
    found = False
    for action in actions:
        if action.get("id") == action_id:
            action["completed"] = completed
            action["completed_at"] = datetime.now(UTC).isoformat() if completed else None
            # Se desmarcou, invalida validação humana (precisa revalidar)
            if not completed:
                action["validated_at"] = None
                action["validated_by_user_id"] = None
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail=f"Ação '{action_id}' não encontrada")

    checklist.actions = actions
    checklist.completion_pct = calculate_completion_pct(actions)
    db.flush()
    return checklist


def validate_action(
    db: Session,
    checklist: MacroetapaChecklist,
    action_id: str,
    *,
    user_id: int,
) -> MacroetapaChecklist:
    """CAM3WS-005 — humano valida o resultado de uma ação que exige validação.

    A ação precisa estar `completed=True` e ter `needs_human_validation=True`.
    """
    actions = list(checklist.actions)
    found = False
    for action in actions:
        if action.get("id") == action_id:
            if not action.get("completed"):
                raise HTTPException(
                    status_code=409,
                    detail="Ação não está completa — não pode ser validada.",
                )
            if not action.get("needs_human_validation"):
                raise HTTPException(
                    status_code=409,
                    detail="Ação não exige validação humana.",
                )
            action["validated_at"] = datetime.now(UTC).isoformat()
            action["validated_by_user_id"] = user_id
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail=f"Ação '{action_id}' não encontrada")

    checklist.actions = actions
    db.flush()
    return checklist


def mark_action_needs_validation(
    db: Session,
    checklist: MacroetapaChecklist,
    action_id: str,
    *,
    needs: bool = True,
    agent_suggestion: Optional[str] = None,
) -> MacroetapaChecklist:
    """Helper interno — agentes IA usam pra sinalizar que sua saída precisa
    de validação humana antes de a etapa ser considerada pronta.
    """
    actions = list(checklist.actions)
    for action in actions:
        if action.get("id") == action_id:
            action["needs_human_validation"] = needs
            if agent_suggestion is not None:
                action["agent_suggestion"] = agent_suggestion
            if not needs:
                # Limpa rastros de validação anterior se não exige mais
                action["validated_at"] = None
                action["validated_by_user_id"] = None
            break
    checklist.actions = actions
    db.flush()
    return checklist


# ---------------------------------------------------------------------------
# Avancar macroetapa
# ---------------------------------------------------------------------------

def advance_macroetapa(
    db: Session,
    process: Process,
    target: Macroetapa,
    *,
    user_id: int,
    tenant_id: int,
) -> Process:
    """Avanca o processo para a macroetapa destino, validando transicao."""
    current = Macroetapa(process.macroetapa) if process.macroetapa else None

    if current is None:
        # Processo sem macroetapa (legado) — permitir ir para qualquer etapa
        process.macroetapa = target.value
        db.flush()
        _ensure_checklist(db, process, tenant_id)
        logger.info("process %d: macroetapa inicializada para %s", process.id, target.value)
        return process

    if not is_valid_macroetapa_transition(current, target):
        raise HTTPException(
            status_code=400,
            detail=f"Transição inválida: {current.value} → {target.value}",
        )

    process.macroetapa = target.value
    db.flush()
    _ensure_checklist(db, process, tenant_id)
    logger.info("process %d: macroetapa %s → %s", process.id, current.value, target.value)
    return process


def _ensure_checklist(db: Session, process: Process, tenant_id: int) -> None:
    """Garante que o checklist da macroetapa atual existe."""
    etapa = Macroetapa(process.macroetapa)
    existing = (
        db.query(MacroetapaChecklist)
        .filter(
            MacroetapaChecklist.process_id == process.id,
            MacroetapaChecklist.macroetapa == etapa,
        )
        .first()
    )
    if not existing:
        actions = [
            {**a, "completed": False, "completed_at": None, "agent_suggestion": None}
            for a in DEFAULT_ACTIONS.get(etapa, [])
        ]
        checklist = MacroetapaChecklist(
            tenant_id=tenant_id,
            process_id=process.id,
            macroetapa=etapa,
            actions=actions,
            completion_pct=0.0,
        )
        db.add(checklist)
        db.flush()


def ensure_macroetapa_checklists(
    db: Session, process: Process, tenant_id: int
) -> bool:
    """Fase 0.2 — backfill idempotente de checklists para casos legados.

    Casos criados antes da Fase 0.2 nasceram sem `MacroetapaChecklist` (o intake
    não inicializava) — `can_advance` travava em False para sempre. Chamado nos
    caminhos de LEITURA da macroetapa (status/gate); se faltar checklist, cria os
    7 (lazy, self-healing). Retorna True se criou algo (o caller deve commitar).
    """
    if not process.macroetapa:
        return False
    existing = (
        db.query(MacroetapaChecklist.id)
        .filter(MacroetapaChecklist.process_id == process.id)
        .first()
    )
    if existing:
        return False
    created = initialize_macroetapa_checklists(db, process, tenant_id)
    return bool(created)


# ---------------------------------------------------------------------------
# Elo evento→card (Fase 0.2) — agentes da etapa concluídos → "pronto para avançar"
# ---------------------------------------------------------------------------

def mark_stage_agents_done(
    db: Session,
    process: Process,
    *,
    tenant_id: int,
    chain_name: str | None = None,
) -> MacroetapaChecklist | None:
    """Marca o checklist da etapa ATUAL como produzido pelos agentes da etapa.

    É o elo "rodar os agentes de uma etapa → card fica pronto para avançar"
    (Ficha 07 §6). Princípio 1: os agentes PROPÕEM (marcam o checklist e levam o
    card a `pronta_para_avancar`); o consultor DECIDE (confirma o avanço no botão
    "Avançar etapa"). NÃO avança a macroetapa aqui.

    - Só marca se `chain_name` for a chain da etapa atual (`MACROETAPA_AGENT_CHAIN`)
      — evita que um agente avulso de outra etapa marque a etapa corrente.
    - Idempotente: se já está tudo marcado, é no-op.
    - Cria o checklist da etapa se faltar (caso legado).
    """
    current = Macroetapa(process.macroetapa) if process.macroetapa else None
    if current is None:
        return None

    expected_chain = MACROETAPA_AGENT_CHAIN.get(current)
    if chain_name is not None and expected_chain is not None and chain_name != expected_chain:
        return None  # chain avulsa — não é a da etapa corrente

    _ensure_checklist(db, process, tenant_id)
    checklist = (
        db.query(MacroetapaChecklist)
        .filter(
            MacroetapaChecklist.process_id == process.id,
            MacroetapaChecklist.macroetapa == current,
        )
        .first()
    )
    if checklist is None:
        return None

    suggestion = f"Produzido pela execução dos agentes da etapa ({chain_name or expected_chain or current.value})"
    # Dicts NOVOS (não compartilham referência com o snapshot carregado): a coluna
    # `actions` é PortableJSON sem MutableList, então mutar in-place não é detectado
    # como dirty. Construir objetos novos + flag_modified garante a persistência.
    now = datetime.now(UTC).isoformat()
    actions = []
    for src in (checklist.actions or []):
        action = dict(src)
        if not action.get("completed"):
            action["completed"] = True
            action["completed_at"] = now
            action["agent_suggestion"] = action.get("agent_suggestion") or suggestion
            # Os agentes propõem; a confirmação humana é o clique em "Avançar etapa"
            # (não exigimos validação por item nesta fase — gate fica no avanço).
            action["needs_human_validation"] = False
        actions.append(action)
    checklist.actions = actions
    flag_modified(checklist, "actions")
    checklist.completion_pct = calculate_completion_pct(actions)
    db.flush()
    return checklist


# ---------------------------------------------------------------------------
# Status completo de macroetapa para um processo
# ---------------------------------------------------------------------------

def get_macroetapa_status(
    db: Session,
    process: Process,
) -> dict:
    """Retorna status completo da macroetapa do processo."""
    current = Macroetapa(process.macroetapa) if process.macroetapa else None
    current_index = MACROETAPA_INDEX.get(current, -1) if current else -1

    # Buscar todos os checklists do processo
    checklists = (
        db.query(MacroetapaChecklist)
        .filter(MacroetapaChecklist.process_id == process.id)
        .all()
    )
    checklist_map = {c.macroetapa: c for c in checklists}

    steps = []
    for i, etapa in enumerate(MACROETAPA_ORDER):
        cl = checklist_map.get(etapa)
        status = "pending"
        if current and i < current_index:
            status = "completed"
            # Sprint 1 (Ficha 07) — a coleta documental (E3) pode ser PULADA pelo
            # ramo da E2 (E2→E4 quando não há documento essencial pendente). Um
            # step pulado NÃO pode aparecer como "completed" (o badge não mente):
            # se ficou para trás com o checklist intocado (0%), é "skipped".
            if etapa is Macroetapa.coleta_documental and (
                cl is None or float(cl.completion_pct or 0.0) == 0.0
            ):
                status = "skipped"
        elif current and i == current_index:
            status = "active"

        stage_agents = get_stage_agents(etapa)
        steps.append({
            "macroetapa": etapa.value,
            "label": MACROETAPA_LABELS[etapa],
            "order": i,
            "status": status,
            "completion_pct": cl.completion_pct if cl else 0.0,
            "actions": cl.actions if cl else [],
            "agent_chain": MACROETAPA_AGENT_CHAIN.get(etapa),
            # CAM3WS-004 — agentes principais e secundários da etapa (metadado).
            "primary_agents": stage_agents["primary"],
            "secondary_agents": stage_agents["secondary"],
        })

    # Proxima acao: primeira acao nao concluida da etapa atual
    next_action: Optional[str] = None
    if current and current in checklist_map:
        for action in checklist_map[current].actions:
            if not action.get("completed"):
                next_action = action.get("label")
                break

    return {
        "current_macroetapa": current.value if current else None,
        "current_label": MACROETAPA_LABELS[current] if current else None,
        "current_index": current_index,
        "total_steps": len(MACROETAPA_ORDER),
        "next_action": next_action,
        "steps": steps,
    }
