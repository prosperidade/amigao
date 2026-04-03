"""
Dossier Service — Sprint 3

Agrega dados do processo (cliente, imóvel, documentos, checklist)
e executa validações de consistência técnica por regras estáticas.
Lógica pura (sem dependência de request/response HTTP).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.checklist_template import ProcessChecklist
from app.models.client import Client
from app.models.document import Document
from app.models.process import Process
from app.models.property import Property
from app.models.task import Task

# ---------------------------------------------------------------------------
# Estruturas de retorno
# ---------------------------------------------------------------------------

@dataclass
class Inconsistency:
    code: str
    severity: str          # "error" | "warning" | "info"
    title: str
    description: str
    field: Optional[str]   # campo/entidade relacionada


@dataclass
class ProcessDossier:
    process_id: int
    process: dict[str, Any]
    client: Optional[dict[str, Any]]
    property: Optional[dict[str, Any]]
    documents: list[dict[str, Any]]
    checklist_summary: Optional[dict[str, Any]]
    tasks_summary: dict[str, Any]
    previous_processes: list[dict[str, Any]]
    inconsistencies: list[Inconsistency]


# ---------------------------------------------------------------------------
# Funções públicas
# ---------------------------------------------------------------------------

def generate_dossier(db: Session, process_id: int, tenant_id: int) -> ProcessDossier:
    """
    Agrega todos os dados relevantes do processo num dossiê unificado.
    """
    process = db.query(Process).filter(
        Process.id == process_id,
        Process.tenant_id == tenant_id,
    ).first()

    if not process:
        return ProcessDossier(
            process_id=process_id,
            process={},
            client=None,
            property=None,
            documents=[],
            checklist_summary=None,
            tasks_summary={},
            previous_processes=[],
            inconsistencies=[{"code": "NOT_FOUND", "severity": "error",
                               "title": "Processo não encontrado", "description": "", "field": None}],
        )

    # Cliente
    client_data: Optional[dict[str, Any]] = None
    if process.client_id:
        client = db.query(Client).filter(Client.id == process.client_id).first()
        if client:
            client_data = {
                "id": client.id,
                "full_name": client.full_name,
                "document_number": getattr(client, "document_number", None),
                "phone": getattr(client, "phone", None),
                "email": getattr(client, "email", None),
            }

    # Imóvel
    property_data: Optional[dict[str, Any]] = None
    if process.property_id:
        prop = db.query(Property).filter(Property.id == process.property_id).first()
        if prop:
            property_data = {
                "id": prop.id,
                "name": prop.name,
                "registry_number": prop.registry_number,
                "ccir": prop.ccir,
                "nirf": prop.nirf,
                "car_code": prop.car_code,
                "car_status": prop.car_status,
                "total_area_ha": prop.total_area_ha,
                "municipality": prop.municipality,
                "state": prop.state,
                "biome": prop.biome,
                "has_embargo": prop.has_embargo,
                "has_geom": prop.geom is not None,
            }

    # Documentos
    documents = (
        db.query(Document)
        .filter(Document.process_id == process_id, Document.tenant_id == tenant_id)
        .order_by(Document.created_at.desc())
        .all()
    )
    docs_data = [
        {
            "id": d.id,
            "filename": d.original_file_name,
            "document_type": d.document_type,
            "document_category": d.document_category,
            "checklist_item_id": d.checklist_item_id,
            "expires_at": d.expires_at,
            "created_at": d.created_at,
        }
        for d in documents
    ]

    # Checklist
    checklist = (
        db.query(ProcessChecklist)
        .filter(ProcessChecklist.process_id == process_id)
        .first()
    )
    checklist_summary: Optional[dict[str, Any]] = None
    if checklist:
        items = checklist.items or []
        received = sum(1 for i in items if i.get("status") == "received")
        waived = sum(1 for i in items if i.get("status") == "waived")
        pending = len(items) - received - waived
        checklist_summary = {
            "checklist_id": checklist.id,
            "total": len(items),
            "received": received,
            "pending": pending,
            "waived": waived,
            "completion_pct": round((received + waived) / len(items) * 100, 1) if items else 0.0,
        }

    # Tarefas
    tasks = (
        db.query(Task)
        .filter(Task.process_id == process_id, Task.tenant_id == tenant_id)
        .all()
    )
    tasks_by_status: dict[str, int] = {}
    for t in tasks:
        key = t.status.value
        tasks_by_status[key] = tasks_by_status.get(key, 0) + 1
    tasks_summary = {
        "total": len(tasks),
        "by_status": tasks_by_status,
        "completed": tasks_by_status.get("concluida", 0),
    }

    # Histórico de processos do mesmo cliente
    previous = (
        db.query(Process)
        .filter(
            Process.client_id == process.client_id,
            Process.tenant_id == tenant_id,
            Process.id != process_id,
        )
        .order_by(Process.created_at.desc())
        .limit(5)
        .all()
    )
    previous_data = [
        {
            "id": p.id,
            "title": p.title,
            "status": p.status.value,
            "demand_type": p.demand_type.value if p.demand_type else None,
            "created_at": p.created_at,
        }
        for p in previous
    ]

    # Inconsistências
    inconsistencies = validate_technical_consistency(
        process=process,
        prop=db.query(Property).filter(Property.id == process.property_id).first() if process.property_id else None,
        documents=documents,
        checklist=checklist,
    )

    return ProcessDossier(
        process_id=process_id,
        process={
            "id": process.id,
            "title": process.title,
            "description": process.description,
            "status": process.status.value,
            "priority": process.priority.value if process.priority else None,
            "urgency": process.urgency,
            "process_type": process.process_type,
            "demand_type": process.demand_type.value if process.demand_type else None,
            "intake_source": process.intake_source.value if process.intake_source else None,
            "initial_diagnosis": process.initial_diagnosis,
            "intake_notes": process.intake_notes,
            "destination_agency": process.destination_agency,
            "external_protocol_number": process.external_protocol_number,
            "opened_at": process.opened_at,
            "due_date": process.due_date,
            "created_at": process.created_at,
        },
        client=client_data,
        property=property_data,
        documents=docs_data,
        checklist_summary=checklist_summary,
        tasks_summary=tasks_summary,
        previous_processes=previous_data,
        inconsistencies=inconsistencies,
    )


def validate_technical_consistency(
    process: Process,
    prop: Optional[Property],
    documents: list[Document],
    checklist: Optional[ProcessChecklist],
) -> list[Inconsistency]:
    """
    Aplica regras de consistência técnica por tipo de demanda.
    Retorna lista de inconsistências detectadas.
    """
    issues: list[Inconsistency] = []
    demand = process.demand_type.value if process.demand_type else None
    doc_types = {d.document_type for d in documents if d.document_type}

    # ── Regras globais ────────────────────────────────────────────────────────

    if not process.property_id:
        issues.append(Inconsistency(
            code="NO_PROPERTY",
            severity="warning",
            title="Imóvel não vinculado",
            description="O processo não possui um imóvel rural vinculado. Vincule o imóvel para habilitar diagnóstico completo.",
            field="property_id",
        ))

    if prop:
        if not prop.registry_number:
            issues.append(Inconsistency(
                code="MISSING_MATRICULA",
                severity="error",
                title="Matrícula do imóvel ausente",
                description="O imóvel não possui número de matrícula registrado. Documento essencial para a maioria das demandas.",
                field="property.registry_number",
            ))

        if not prop.car_code and demand in ("licenciamento", "regularizacao_fundiaria", "outorga", "compensacao"):
            issues.append(Inconsistency(
                code="MISSING_CAR",
                severity="error",
                title="CAR não cadastrado",
                description="Imóvel sem CAR ativo. O Cadastro Ambiental Rural é pré-requisito para esta demanda.",
                field="property.car_code",
            ))

        if prop.has_embargo:
            issues.append(Inconsistency(
                code="PROPERTY_EMBARGO",
                severity="error",
                title="Imóvel com embargo ambiental",
                description="O imóvel possui embargo ambiental registrado. Regularização deve ser tratada antes de prosseguir.",
                field="property.has_embargo",
            ))

        if not prop.geom and demand in ("car", "retificacao_car", "regularizacao_fundiaria"):
            issues.append(Inconsistency(
                code="MISSING_GEOM",
                severity="warning",
                title="Georreferenciamento ausente",
                description="Imóvel sem geometria georreferenciada. Necessário para esta demanda.",
                field="property.geom",
            ))

        if not prop.total_area_ha:
            issues.append(Inconsistency(
                code="MISSING_AREA",
                severity="warning",
                title="Área total do imóvel não informada",
                description="A área total em hectares não foi cadastrada. Pode impactar cálculos de passivo ambiental.",
                field="property.total_area_ha",
            ))

    # ── Regras por tipo de demanda ────────────────────────────────────────────

    if demand == "car":
        if "matricula" not in doc_types and prop and not prop.registry_number:
            issues.append(Inconsistency(
                code="CAR_NO_MATRICULA_DOC",
                severity="warning",
                title="Matrícula não anexada",
                description="Para o CAR, é necessário anexar a matrícula ou o CCIR do imóvel.",
                field="documents",
            ))

    if demand in ("car", "regularizacao_fundiaria") and prop and not prop.ccir:
        issues.append(Inconsistency(
            code="MISSING_CCIR",
            severity="warning",
            title="CCIR não cadastrado",
            description="O Certificado de Cadastro de Imóvel Rural (CCIR) não está informado.",
            field="property.ccir",
        ))

    if demand == "outorga" and prop and not prop.municipality:
        issues.append(Inconsistency(
            code="OUTORGA_NO_MUNICIPIO",
            severity="warning",
            title="Município do imóvel não informado",
            description="Para outorga é necessário identificar o município e a bacia hidrográfica.",
            field="property.municipality",
        ))

    if demand == "exigencia_bancaria" and not prop:
        issues.append(Inconsistency(
            code="BANCO_NO_PROPERTY",
            severity="error",
            title="Imóvel necessário para exigência bancária",
            description="O banco exige dados do imóvel para liberação do crédito rural. Vincule o imóvel ao processo.",
            field="property_id",
        ))

    # ── Checklist ────────────────────────────────────────────────────────────

    if checklist:
        items = checklist.items or []
        required_pending = [i for i in items if i.get("required") and i.get("status") == "pending"]
        if required_pending:
            issues.append(Inconsistency(
                code="REQUIRED_DOCS_PENDING",
                severity="warning",
                title=f"{len(required_pending)} documento(s) obrigatório(s) pendente(s)",
                description="Há documentos marcados como obrigatórios no checklist que ainda não foram recebidos.",
                field="checklist",
            ))

    return issues
