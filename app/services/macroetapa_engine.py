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

def _persistir_actions(checklist: MacroetapaChecklist, actions: list) -> None:
    """Grava as ações de forma que o SQLAlchemy DETECTE a mudança.

    `MacroetapaChecklist.actions` é JSON sem `MutableList`: o padrão
    `actions = list(...)` → mutar os dicts → reatribuir NÃO deixa o objeto
    dirty, porque os dicts são compartilhados e no instante da atribuição
    "antigo" já é igual a "novo". O flush não emite UPDATE e a marcação se
    perde.

    `mark_stage_agents_done` já tinha descoberto isso e curado no seu próprio
    ponto; os outros três (`toggle_action`, `validate_action`,
    `mark_action_needs_validation`) ficaram sem o remédio — mesma classe que a
    dívida #70 fechou no `checklist_engine` para o campo `items`.
    """
    checklist.actions = [dict(a) for a in actions]
    flag_modified(checklist, "actions")


def calculate_completion_pct(actions: list[dict]) -> float:
    """Calcula % de conclusao baseado nas acoes do checklist."""
    if not actions:
        return 0.0
    completed = sum(1 for a in actions if a.get("completed"))
    return round((completed / len(actions)) * 100, 1)


# ---------------------------------------------------------------------------
# Fase 0 (gap-analysis Ficha 07, item 2) — detectar se a Consolidação já rodou
# ---------------------------------------------------------------------------

def has_consolidated(db: Session, tenant_id: int, process_id: int) -> bool:
    """A Ficha 07 (§7) exige que a Consolidação (Ficha 05) tenha rodado antes
    de sair da E2. O sinal mais confiável hoje é o `AuditLog(action="consolidar")`
    que `consolidate_process` emite (Princípio 2 — tudo auditável).

    Lacuna conhecida e aceita: `consolidate_process` só grava esse AuditLog
    quando produz `writes`/`reconciliacoes`/`acoes_criadas`/`divergencias_devolvidas`
    (staging_consolidation.py:520-528) — uma consolidação que roda sem nada
    para gravar (staging vazio) não deixa rastro. Na prática isso não bloqueia
    um caso real (sempre há campo a consolidar), mas é honesto declarar: este
    helper detecta "consolidação produziu efeito" e não "consolidação foi
    chamada"."""
    from app.models.audit_log import AuditLog  # noqa: PLC0415

    return (
        db.query(AuditLog.id)
        .filter(
            AuditLog.tenant_id == tenant_id,
            AuditLog.entity_type == "process",
            AuditLog.entity_id == process_id,
            AuditLog.action == "consolidar",
        )
        .first()
        is not None
    )


# ---------------------------------------------------------------------------
# Fase 0 (gap-analysis Ficha 07, item 9) — os mesmos sinais para E5/E6/E7:
# as entidades (Rota, Proposal, Contract) já existem e já têm o campo de
# estado certo; o gate de macroetapa simplesmente não os lia. Espelham
# `has_consolidated` acima: 1 query indexada, sinal "produziu o estado
# esperado", não "foi chamado".
# ---------------------------------------------------------------------------

def has_rota_validada(db: Session, tenant_id: int, process_id: int) -> bool:
    """Ficha 07 §7 — saída da E5 (`caminho_regulatorio`) exige a Rota fechada
    (todos os passos validados + classificados, `RotaStatus.validada`).

    Um processo pode ter mais de uma `Rota` (uma por `demand_type` — ver
    `app/models/rota.py`); qualquer uma validada já satisfaz o gate — não é
    papel deste helper arbitrar qual demanda é "a" rota do processo."""
    from app.models.rota import Rota, RotaStatus  # noqa: PLC0415

    return (
        db.query(Rota.id)
        .filter(
            Rota.tenant_id == tenant_id,
            Rota.process_id == process_id,
            Rota.status == RotaStatus.validada,
        )
        .first()
        is not None
    )


def descrever_pendencia_rota(db: Session, tenant_id: int, process_id: int) -> str:
    """O que EXATAMENTE falta para a rota deste processo estar fechada.

    Validação Isis 30/07: o gate E5→E6 segurou o caso e a tela dizia apenas
    "feche a rota antes de avançar" — verdadeiro e inútil. Fechar a rota tem duas
    portas em série (classificar cada passo, depois validar cada passo) e o
    consultor não tinha como saber em qual delas estava preso. Medido no caso 15:
    rota `em_validacao` com 8 passos ainda `proposto`.

    A frase sai daqui, do servidor, e não de cada componente — foi a redação
    duplicada que produziu as divergências do ADR-031. Devolve "" quando não há
    pendência (a rota já está validada).
    """
    from app.models.rota import Rota, RotaPassoStatus, RotaStatus  # noqa: PLC0415

    rotas = (
        db.query(Rota)
        .filter(Rota.tenant_id == tenant_id, Rota.process_id == process_id)
        .all()
    )
    if not rotas:
        return (
            "A rota regulatória ainda não foi gerada — abra a aba Rota e peça a "
            "proposta da IA (ou monte os passos à mão) antes de avançar."
        )
    if any(r.status == RotaStatus.validada for r in rotas):
        return ""

    rota = max(rotas, key=lambda r: (len(r.passos), r.id))
    if not rota.passos:
        return (
            "A rota existe mas está sem passos — gere a proposta da IA ou "
            "adicione os passos à mão antes de avançar."
        )
    nao_validados = [p for p in rota.passos if p.status != RotaPassoStatus.validado]
    sem_classificacao = [p for p in nao_validados if p.classificacao is None]

    if rota.status == RotaStatus.desatualizada:
        if nao_validados:
            return (
                f"A IA trouxe passos novos depois que você fechou a rota: "
                f"{len(nao_validados)} passo(s) esperam sua conferência na aba Rota. "
                "Valide-os (ou remova) e feche a rota de novo."
            )
        # Diff sem passo novo (a IA REMOVEU passo). Não há o que validar — e a
        # frase antiga mandava validar o que não existe, deixando a consultora
        # sem próximo movimento (validação 02/08).
        return (
            "A rota mudou desde a última assinatura, mas não há passo pendente: "
            'abra a aba Rota e clique em "Fechar rota" para reassinar.'
        )
    partes: list[str] = []
    if sem_classificacao:
        partes.append(
            f"{len(sem_classificacao)} passo(s) sem classificação "
            "(marque cada um como item de proposta ou direção)"
        )
    classificados_pendentes = [p for p in nao_validados if p.classificacao is not None]
    if classificados_pendentes:
        partes.append(
            f"{len(classificados_pendentes)} passo(s) classificados mas ainda não validados"
        )
    if not partes:
        return (
            "Todos os passos estão validados — falta só clicar em "
            '"Fechar rota" na aba Rota para assinar e liberar o avanço.'
        )
    return (
        "Falta fechar a rota regulatória: " + "; ".join(partes) + ". "
        'Resolva na aba Rota e clique em "Fechar rota".'
    )


def has_proposal_accepted(db: Session, tenant_id: int, process_id: int) -> bool:
    """Ficha 07 §7 — saída da E6 (`orcamento_negociacao`) exige proposta
    gerada e aceita pelo cliente (`ProposalStatus.accepted`)."""
    from app.models.proposal import Proposal, ProposalStatus  # noqa: PLC0415

    return (
        db.query(Proposal.id)
        .filter(
            Proposal.tenant_id == tenant_id,
            Proposal.process_id == process_id,
            Proposal.status == ProposalStatus.accepted,
        )
        .first()
        is not None
    )


def has_contract_signed(db: Session, tenant_id: int, process_id: int) -> bool:
    """Ficha 07 §7 — E7 (`contrato_formalizacao`) só "conclui" com o contrato
    assinado (`Contract.signed_at` preenchido).

    Lacuna conhecida e ACEITA (item 9 do adendo): nenhum fluxo escreve
    `signed_at` hoje — a assinatura (upload/registro do documento assinado)
    é o Sprint 5. Até lá este helper sempre retorna `False` em produção, e a
    E7 honestamente nunca mostra "concluída" — comportamento correto, não bug:
    o caso realmente não está concluído sem contrato assinado."""
    from app.models.contract import Contract  # noqa: PLC0415

    return (
        db.query(Contract.id)
        .filter(
            Contract.tenant_id == tenant_id,
            Contract.process_id == process_id,
            Contract.signed_at.isnot(None),
        )
        .first()
        is not None
    )


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
    *,
    user_id: Optional[int] = None,
) -> MacroetapaChecklist:
    """Marca/desmarca uma acao no checklist."""
    actions = list(checklist.actions)  # copia para trigger de update
    found = False
    for action in actions:
        if action.get("id") == action_id:
            action["completed"] = completed
            action["completed_at"] = datetime.now(UTC).isoformat() if completed else None
            # Autoria da marcação manual (item 1 da validação 20/07): quem marcou
            # e quando. Antes só o instante era gravado — sem dono, a auditoria da
            # etapa não respondia "quem disse que isto foi feito?".
            action["completed_by_user_id"] = user_id if completed else None
            # Se desmarcou, invalida validação humana (precisa revalidar)
            if not completed:
                action["validated_at"] = None
                action["validated_by_user_id"] = None
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail=f"Ação '{action_id}' não encontrada")

    _persistir_actions(checklist, actions)
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

    _persistir_actions(checklist, actions)
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
    _persistir_actions(checklist, actions)
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

def stage_agents_executados(checklist: MacroetapaChecklist | None) -> bool:
    """Os agentes desta etapa já rodaram?

    Sinal: `mark_stage_agents_done` carimba `agent_suggestion` nas ações que
    marcou. Nenhuma ação com sugestão de agente ⇒ a chain da etapa não passou
    por aqui — ou o consultor marcou tudo na mão.

    Não é bloqueio: alimenta o aviso do avanço (radar-não-cancela). O consultor
    pode avançar sem os agentes; ele só não pode fazer isso sem saber.
    """
    if checklist is None:
        return False
    return any(a.get("agent_suggestion") for a in (checklist.actions or []))


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
