"""
Intake API — Sprint 1

Endpoints:
  POST /intake/classify      — classifica a demanda por tipo (sem criar nada)
  POST /intake/create-case   — cria cliente + imóvel + processo em uma transação
  GET  /intake/templates     — lista templates de checklist por tipo de demanda
  GET  /intake/demand-types  — lista tipos de demanda disponíveis
"""
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.audit_log import AuditLog
from app.models.checklist_template import ChecklistTemplate, ProcessChecklist
from app.models.client import Client as ClientModel
from app.models.process import DemandType, IntakeSource
from app.models.process import Process as ProcessModel
from app.models.property import Property as PropertyModel
from app.models.user import User
from app.schemas.intake import (
    DocumentRequirement,
    IntakeCaseCreatedResponse,
    IntakeClassifyRequest,
    IntakeClassifyResponse,
    IntakeCreateCaseRequest,
)
from app.services.intake_classifier import classify_demand, get_demand_rules

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# POST /intake/classify
# ---------------------------------------------------------------------------

@router.post("/classify", response_model=IntakeClassifyResponse)
def classify_intake(
    *,
    payload: IntakeClassifyRequest,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """
    Classifica uma demanda de entrada por tipo ambiental.

    Retorna: tipo de demanda, diagnóstico inicial, documentos esperados e
    próximos passos — tudo calculado por regras estáticas (sem LLM).
    """
    result = classify_demand(
        description=payload.description,
        process_type=payload.process_type,
        urgency=payload.urgency,
        source_channel=payload.source_channel,
    )
    return IntakeClassifyResponse(
        demand_type=result.demand_type,
        demand_label=result.demand_label,
        confidence=result.confidence,
        initial_diagnosis=result.initial_diagnosis,
        required_documents=[DocumentRequirement(**d) for d in result.required_documents],
        suggested_next_steps=result.suggested_next_steps,
        checklist_template_demand_type=result.checklist_template_demand_type,
        urgency_flag=result.urgency_flag,
        relevant_agencies=result.relevant_agencies,
    )


# ---------------------------------------------------------------------------
# POST /intake/create-case
# ---------------------------------------------------------------------------

@router.post("/create-case", response_model=IntakeCaseCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    *,
    db: Session = Depends(get_db),
    payload: IntakeCreateCaseRequest,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """
    Cria um caso completo em uma transação:
    1. Cria ou vincula cliente
    2. Cria ou vincula imóvel
    3. Classifica a demanda
    4. Cria processo com diagnóstico inicial
    5. Gera checklist documental automaticamente
    """
    # --- Validação básica ---
    if not payload.client_id and not payload.new_client:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Informe client_id (cliente existente) ou new_client (criar novo).",
        )

    # --- 1. Cliente ---
    if payload.client_id:
        client = (
            db.query(ClientModel)
            .filter(ClientModel.id == payload.client_id, ClientModel.tenant_id == current_user.tenant_id)
            .first()
        )
        if not client:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado.")
    else:
        nc = payload.new_client
        client = ClientModel(
            tenant_id=current_user.tenant_id,
            full_name=nc.full_name,
            phone=nc.phone,
            email=nc.email,
            cpf_cnpj=nc.cpf_cnpj,
            client_type=nc.client_type or "pf",
            source_channel=nc.source_channel or payload.source_channel,
            status="lead",
        )
        db.add(client)
        db.flush()

    # --- 2. Imóvel ---
    prop = None
    if payload.property_id:
        prop = (
            db.query(PropertyModel)
            .filter(PropertyModel.id == payload.property_id, PropertyModel.tenant_id == current_user.tenant_id)
            .first()
        )
        if not prop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imóvel não encontrado.")
    elif payload.new_property:
        np = payload.new_property
        prop = PropertyModel(
            tenant_id=current_user.tenant_id,
            client_id=client.id,
            name=np.name,
            municipality=np.municipality,
            state=np.state,
            car_code=np.car_number,
            ccir=np.ccir_number,
            total_area_ha=np.area_hectares,
        )
        db.add(prop)
        db.flush()

    # --- 3. Classificação ---
    classification = classify_demand(
        description=payload.description,
        process_type=payload.demand_type or payload.process_type,
        urgency=payload.urgency,
        source_channel=payload.source_channel,
    )

    # Mapear demand_type para enum (fallback para nao_identificado)
    try:
        demand_type_enum = DemandType(classification.demand_type)
    except ValueError:
        demand_type_enum = DemandType.nao_identificado

    # Mapear source_channel para enum
    intake_source_enum: Optional[IntakeSource] = None
    if payload.source_channel:
        try:
            intake_source_enum = IntakeSource(payload.source_channel)
        except ValueError:
            intake_source_enum = None

    # Título automático do processo
    process_title = f"{classification.demand_label} — {client.full_name}"
    if prop:
        process_title += f" ({prop.name})"

    # --- 4. Processo ---
    process = ProcessModel(
        tenant_id=current_user.tenant_id,
        client_id=client.id,
        property_id=prop.id if prop else None,
        title=process_title,
        description=payload.description,
        process_type=classification.demand_type,
        status="triagem",
        urgency=classification.urgency_flag or payload.urgency or "media",
        intake_source=intake_source_enum,
        demand_type=demand_type_enum,
        initial_diagnosis=classification.initial_diagnosis,
        suggested_checklist_template=classification.checklist_template_demand_type,
        intake_notes=payload.intake_notes,
        responsible_user_id=current_user.id,
    )
    db.add(process)
    db.flush()

    # Audit log de criação
    db.add(AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        entity_type="process",
        entity_id=process.id,
        action="created",
        details=f"Processo criado via intake ({classification.demand_type})",
    ))

    # --- 5. Checklist ---
    checklist_generated = False
    template = (
        db.query(ChecklistTemplate)
        .filter(
            ChecklistTemplate.demand_type == classification.demand_type,
            ChecklistTemplate.is_active == True,
        )
        .filter(
            (ChecklistTemplate.tenant_id == current_user.tenant_id) |
            (ChecklistTemplate.tenant_id == None)
        )
        .order_by(ChecklistTemplate.tenant_id.desc().nullslast())  # tenant-specific primeiro
        .first()
    )

    if template:
        checklist = ProcessChecklist(
            tenant_id=current_user.tenant_id,
            process_id=process.id,
            template_id=template.id,
            items=[
                {**item, "status": "pending", "document_id": None, "waiver_reason": None}
                for item in template.items
            ],
        )
        db.add(checklist)
        checklist_generated = True
    else:
        # Gera checklist direto dos requisitos do classificador (sem template no BD)
        checklist = ProcessChecklist(
            tenant_id=current_user.tenant_id,
            process_id=process.id,
            template_id=None,
            items=[
                {**doc, "status": "pending", "document_id": None, "waiver_reason": None}
                for doc in classification.required_documents
            ],
        )
        db.add(checklist)
        checklist_generated = True

    db.commit()
    db.refresh(process)

    logger.info(
        "Intake concluído: process_id=%s client_id=%s demand_type=%s urgency=%s",
        process.id, client.id, classification.demand_type, classification.urgency_flag,
    )

    return IntakeCaseCreatedResponse(
        client_id=client.id,
        property_id=prop.id if prop else None,
        process_id=process.id,
        demand_type=classification.demand_type,
        demand_label=classification.demand_label,
        initial_diagnosis=classification.initial_diagnosis,
        checklist_generated=checklist_generated,
        suggested_next_steps=classification.suggested_next_steps,
        process_title=process_title,
    )


# ---------------------------------------------------------------------------
# GET /intake/templates
# ---------------------------------------------------------------------------

@router.get("/templates")
def list_checklist_templates(
    demand_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Lista templates de checklist globais e do tenant, com filtro opcional por tipo."""
    query = db.query(ChecklistTemplate).filter(
        ChecklistTemplate.is_active == True,
        (ChecklistTemplate.tenant_id == current_user.tenant_id) |
        (ChecklistTemplate.tenant_id == None),
    )
    if demand_type:
        query = query.filter(ChecklistTemplate.demand_type == demand_type)
    return query.order_by(ChecklistTemplate.demand_type).all()


# ---------------------------------------------------------------------------
# GET /intake/demand-types
# ---------------------------------------------------------------------------

@router.get("/demand-types")
def list_demand_types(
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Lista todos os tipos de demanda disponíveis com labels e documentos esperados."""
    rules = get_demand_rules()
    return [
        {
            "demand_type": dt,
            "label": rules[dt]["label"],
            "agencies": rules[dt]["agencies"],
            "doc_count": len(rules[dt]["docs"]),
            "required_doc_count": sum(1 for d in rules[dt]["docs"] if d["required"]),
        }
        for dt in rules
        if dt not in ("nao_identificado",)
    ]
