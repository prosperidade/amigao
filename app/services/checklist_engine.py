"""
Checklist Engine — Sprint 2

Motor de geração e gestão de checklists documentais por processo.
Lógica pura (sem dependência de request/response HTTP).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.checklist_template import ChecklistTemplate, ProcessChecklist
from app.models.document import Document


# ---------------------------------------------------------------------------
# Estruturas de retorno
# ---------------------------------------------------------------------------

@dataclass
class ChecklistGap:
    item_id: str
    label: str
    doc_type: str
    category: str
    required: bool
    days_pending: Optional[int]  # dias desde criação do checklist sem o documento


@dataclass
class ChecklistStatus:
    process_id: int
    checklist_id: Optional[int]
    total_items: int
    received: int
    pending: int
    waived: int
    completion_pct: float
    has_required_gaps: bool
    gaps: List[ChecklistGap]


# ---------------------------------------------------------------------------
# Funções públicas
# ---------------------------------------------------------------------------

def get_or_create_checklist(
    db: Session,
    process_id: int,
    tenant_id: int,
    demand_type: Optional[str],
) -> ProcessChecklist:
    """
    Retorna o checklist existente do processo, ou gera um novo baseado
    no demand_type. Nunca cria duplicatas (unique constraint process_id).
    """
    existing = (
        db.query(ProcessChecklist)
        .filter(ProcessChecklist.process_id == process_id)
        .first()
    )
    if existing:
        return existing

    return _generate_checklist(db, process_id, tenant_id, demand_type)


def regenerate_checklist(
    db: Session,
    process_id: int,
    tenant_id: int,
    demand_type: Optional[str],
) -> ProcessChecklist:
    """
    Remove o checklist atual e gera um novo. Usado quando o demand_type
    do processo muda após o intake.
    """
    existing = (
        db.query(ProcessChecklist)
        .filter(ProcessChecklist.process_id == process_id)
        .first()
    )
    if existing:
        db.delete(existing)
        db.flush()

    return _generate_checklist(db, process_id, tenant_id, demand_type)


def get_checklist_status(checklist: ProcessChecklist) -> ChecklistStatus:
    """
    Calcula o status consolidado do checklist: itens recebidos, pendentes,
    dispensados, e gaps (itens obrigatórios ou importantes ainda pendentes).
    """
    items = checklist.items or []
    received = sum(1 for i in items if i.get("status") == "received")
    waived = sum(1 for i in items if i.get("status") == "waived")
    pending = len(items) - received - waived
    total = len(items)
    completion_pct = round((received + waived) / total * 100, 1) if total > 0 else 0.0

    # Calcular dias pendentes desde a criação do checklist
    created_at = checklist.created_at
    if created_at and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    days_since_creation = (now - created_at).days if created_at else None

    gaps: List[ChecklistGap] = []
    for item in items:
        if item.get("status") == "pending":
            gaps.append(ChecklistGap(
                item_id=item.get("id", ""),
                label=item.get("label", ""),
                doc_type=item.get("doc_type", ""),
                category=item.get("category", ""),
                required=item.get("required", False),
                days_pending=days_since_creation,
            ))

    has_required_gaps = any(g.required for g in gaps)

    return ChecklistStatus(
        process_id=checklist.process_id,
        checklist_id=checklist.id,
        total_items=total,
        received=received,
        pending=pending,
        waived=waived,
        completion_pct=completion_pct,
        has_required_gaps=has_required_gaps,
        gaps=gaps,
    )


def mark_item_received(
    checklist: ProcessChecklist,
    item_id: str,
    document_id: Optional[int] = None,
) -> bool:
    """
    Marca um item do checklist como recebido, opcionalmente vinculando o documento.
    Retorna True se o item foi encontrado e atualizado.
    """
    items = list(checklist.items or [])
    for item in items:
        if item.get("id") == item_id:
            item["status"] = "received"
            item["document_id"] = document_id
            checklist.items = items
            return True
    return False


def mark_item_waived(
    checklist: ProcessChecklist,
    item_id: str,
    reason: str,
) -> bool:
    """
    Marca um item do checklist como dispensado com justificativa.
    """
    items = list(checklist.items or [])
    for item in items:
        if item.get("id") == item_id:
            item["status"] = "waived"
            item["waiver_reason"] = reason
            item["document_id"] = None
            checklist.items = items
            return True
    return False


def mark_item_pending(
    checklist: ProcessChecklist,
    item_id: str,
) -> bool:
    """
    Reverte um item para pendente (desfaz recebimento ou dispensa).
    """
    items = list(checklist.items or [])
    for item in items:
        if item.get("id") == item_id:
            item["status"] = "pending"
            item["document_id"] = None
            item["waiver_reason"] = None
            checklist.items = items
            return True
    return False


def auto_link_document(
    db: Session,
    checklist: ProcessChecklist,
    document_id: int,
    doc_type: str,
) -> Optional[str]:
    """
    Tenta vincular automaticamente um documento recém-enviado a um item
    pendente do checklist com o mesmo doc_type. Retorna o item_id vinculado
    ou None se nenhum match.
    """
    items = list(checklist.items or [])
    for item in items:
        if (
            item.get("doc_type") == doc_type
            and item.get("status") == "pending"
        ):
            item["status"] = "received"
            item["document_id"] = document_id
            checklist.items = items
            return item.get("id")
    return None


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _generate_checklist(
    db: Session,
    process_id: int,
    tenant_id: int,
    demand_type: Optional[str],
) -> ProcessChecklist:
    """Busca o template adequado no BD e instancia o checklist."""
    template = None
    if demand_type:
        template = (
            db.query(ChecklistTemplate)
            .filter(
                ChecklistTemplate.demand_type == demand_type,
                ChecklistTemplate.is_active == True,
                (ChecklistTemplate.tenant_id == tenant_id) |
                (ChecklistTemplate.tenant_id == None),
            )
            .order_by(ChecklistTemplate.tenant_id.desc().nullslast())
            .first()
        )

    items: list
    template_id: Optional[int]

    if template:
        template_id = template.id
        items = [
            {**item, "status": "pending", "document_id": None, "waiver_reason": None}
            for item in (template.items or [])
        ]
    else:
        template_id = None
        items = []  # checklist vazio se não houver template

    checklist = ProcessChecklist(
        tenant_id=tenant_id,
        process_id=process_id,
        template_id=template_id,
        items=items,
    )
    db.add(checklist)
    db.flush()
    return checklist
