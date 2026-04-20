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
from app.models.intake_draft import IntakeDraft, IntakeDraftState, has_minimal_base
from app.models.macroetapa import Macroetapa
from app.models.process import DemandType, EntryType, IntakeSource
from app.models.process import Process as ProcessModel
from app.models.property import Property as PropertyModel
from app.models.user import User
from app.schemas.intake import (
    DocumentRequirement,
    IntakeCaseCreatedResponse,
    IntakeClassifyRequest,
    IntakeClassifyResponse,
    IntakeCreateCaseRequest,
    IntakeDraftConfirmUploadRequest,
    IntakeDraftCreateRequest,
    IntakeDraftDocumentResponse,
    IntakeDraftResponse,
    IntakeDraftUpdateRequest,
    IntakeDraftUploadUrlRequest,
    IntakeDraftUploadUrlResponse,
    IntakeEnrichRequest,
    IntakeEnrichResponse,
    IntakeImportRequest,
    IntakeImportResponse,
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

    try:
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
        # Regente Cam1: classificar só se há descrição. Sem description, processo
        # nasce com demand_type=nao_identificado e agente classifica depois.
        if payload.description and len(payload.description.strip()) >= 10:
            classification = classify_demand(
                description=payload.description,
                process_type=payload.demand_type or payload.process_type,
                urgency=payload.urgency,
                source_channel=payload.source_channel,
            )
        else:
            # Sem description suficiente — cria entrada "magra" e deixa IA classificar depois
            from app.services.intake_classifier import DemandClassification  # noqa: PLC0415
            classification = DemandClassification(
                demand_type="nao_identificado",
                demand_label="Não identificado",
                confidence="low",
                initial_diagnosis="",
                required_documents=[],
                suggested_next_steps=[
                    "Complementar descrição da demanda",
                    "Aguardar leitura da IA após upload de documentos",
                ],
                checklist_template_demand_type="nao_identificado",
                urgency_flag=None,
                relevant_agencies=[],
            )

        # CAM1-003 Opção B (Sprint I) — Process SEMPRE nasce com demand_type=nao_identificado.
        # O resultado do classificador (demand_type, initial_diagnosis, required_documents,
        # suggested_next_steps) é tratado como SUGESTÃO: fica em process_type (string),
        # initial_diagnosis e suggested_checklist_template — sem decidir a demanda oficialmente.
        # A promoção para demand_type "de verdade" é responsabilidade do consultor (ação
        # explícita) ou do task Celery run_llm_classification (que só sobrescreve quando
        # o valor atual é "nao_identificado"). Respeita a premissa da sócia: "IA não decide
        # na Camada 1 — organiza e prepara a próxima etapa."
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
        # Regente Cam1: processo nasce em macroetapa "entrada_demanda"
        # (status legado "triagem" mantido por retrocompat com máquina de estados existente)
        process = ProcessModel(
            tenant_id=current_user.tenant_id,
            client_id=client.id,
            property_id=prop.id if prop else None,
            title=process_title,
            description=payload.description,
            initial_summary=payload.initial_summary,
            process_type=classification.demand_type,
            status="triagem",
            macroetapa=Macroetapa.entrada_demanda.value,
            urgency=classification.urgency_flag or payload.urgency or "media",
            intake_source=intake_source_enum,
            entry_type=payload.entry_type,
            demand_type=demand_type_enum,
            initial_diagnosis=classification.initial_diagnosis,
            suggested_checklist_template=classification.checklist_template_demand_type,
            intake_notes=payload.intake_notes,
            responsible_user_id=current_user.id,
        )
        db.add(process)
        db.flush()

        # Audit log de criação
        audit = AuditLog(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            entity_type="process",
            entity_id=process.id,
            action="created",
            details=f"Processo criado via intake ({classification.demand_type})",
        )
        db.add(audit)
        db.flush()
        from app.services.audit_hash import stamp_audit_hash
        stamp_audit_hash(db, audit)

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
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    # --- 6. Trigger Agente Atendimento (async, fire-and-forget) ---
    # Regente Cam1: só dispara se há description suficiente — o agente exige
    # description em suas preconditions. Sem description, classificação fica
    # pendente até enrichment (CAM1-004).
    if payload.description and len(payload.description.strip()) >= 10:
        try:
            from app.workers.agent_tasks import run_agent  # noqa: PLC0415
            run_agent.delay(
                agent_name="atendimento",
                tenant_id=current_user.tenant_id,
                user_id=current_user.id,
                process_id=process.id,
                metadata={
                    "description": payload.description,
                    "process_type": classification.demand_type,
                    "urgency": classification.urgency_flag or payload.urgency,
                    "source_channel": payload.source_channel,
                },
            )
            logger.info("Agente atendimento enfileirado para process_id=%s", process.id)
        except Exception as exc:
            logger.warning("Falha ao enfileirar agente atendimento para process_id=%s: %s", process.id, exc)
    else:
        logger.info(
            "Intake sem description: agente atendimento NÃO disparado (process_id=%s)",
            process.id,
        )

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


# ---------------------------------------------------------------------------
# Rascunhos de cadastro (CAM1-008/009) — salvar e continuar depois
# ---------------------------------------------------------------------------

def _serialize_draft(d: IntakeDraft) -> IntakeDraftResponse:
    return IntakeDraftResponse(
        id=d.id,
        state=d.state.value if hasattr(d.state, "value") else str(d.state),
        entry_type=d.entry_type,
        form_data=d.form_data or {},
        linked_process_id=d.linked_process_id,
        created_by_user_id=d.created_by_user_id,
        has_minimal_base=has_minimal_base(d.form_data or {}),
        created_at=d.created_at.isoformat() if d.created_at else None,
        updated_at=d.updated_at.isoformat() if d.updated_at else None,
        expires_at=d.expires_at.isoformat() if d.expires_at else None,
    )


def _compute_state(form_data: dict) -> IntakeDraftState:
    return (
        IntakeDraftState.pronto_para_criar
        if has_minimal_base(form_data)
        else IntakeDraftState.rascunho
    )


@router.post("/drafts", response_model=IntakeDraftResponse, status_code=status.HTTP_201_CREATED)
def create_draft(
    *,
    db: Session = Depends(get_db),
    payload: IntakeDraftCreateRequest,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Cria um rascunho de cadastro (estado salvo do wizard)."""
    draft = IntakeDraft(
        tenant_id=current_user.tenant_id,
        created_by_user_id=current_user.id,
        entry_type=payload.entry_type.value if payload.entry_type else None,
        form_data=payload.form_data or {},
        state=_compute_state(payload.form_data or {}),
    )
    draft.refresh_expiration()  # TTL 15 dias
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return _serialize_draft(draft)


@router.get("/drafts", response_model=list[IntakeDraftResponse])
def list_drafts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
    state: Optional[str] = None,
) -> Any:
    """Lista rascunhos do tenant, filtrando os já commitados/expirados por padrão."""
    from datetime import datetime, timezone  # noqa: PLC0415
    now = datetime.now(timezone.utc)
    q = db.query(IntakeDraft).filter(IntakeDraft.tenant_id == current_user.tenant_id)
    if state:
        q = q.filter(IntakeDraft.state == state)
    else:
        # Por padrão, esconder drafts já commitados e já expirados
        q = q.filter(IntakeDraft.state != IntakeDraftState.card_criado)
        q = q.filter(
            (IntakeDraft.expires_at.is_(None)) | (IntakeDraft.expires_at >= now)
        )
    drafts = q.order_by(IntakeDraft.updated_at.desc().nullslast(), IntakeDraft.created_at.desc()).all()
    return [_serialize_draft(d) for d in drafts]


@router.get("/drafts/{draft_id}", response_model=IntakeDraftResponse)
def get_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    draft = db.query(IntakeDraft).filter(
        IntakeDraft.id == draft_id,
        IntakeDraft.tenant_id == current_user.tenant_id,
    ).first()
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rascunho não encontrado.")
    return _serialize_draft(draft)


@router.patch("/drafts/{draft_id}", response_model=IntakeDraftResponse)
def update_draft(
    draft_id: int,
    payload: IntakeDraftUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    draft = db.query(IntakeDraft).filter(
        IntakeDraft.id == draft_id,
        IntakeDraft.tenant_id == current_user.tenant_id,
    ).first()
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rascunho não encontrado.")
    if draft.state == IntakeDraftState.card_criado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Rascunho já foi commitado em processo; não pode ser editado.",
        )

    if payload.entry_type is not None:
        draft.entry_type = payload.entry_type.value
    if payload.form_data is not None:
        draft.form_data = payload.form_data
        draft.state = _compute_state(payload.form_data)

    # TTL: cada edição renova o prazo de 15 dias.
    draft.refresh_expiration()

    db.commit()
    db.refresh(draft)
    return _serialize_draft(draft)


@router.delete("/drafts/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> None:
    draft = db.query(IntakeDraft).filter(
        IntakeDraft.id == draft_id,
        IntakeDraft.tenant_id == current_user.tenant_id,
    ).first()
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rascunho não encontrado.")
    if draft.state == IntakeDraftState.card_criado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Rascunho já foi commitado; delete o processo associado.",
        )
    db.delete(draft)
    db.commit()


# ---------------------------------------------------------------------------
# Complementar base existente (CAM1-004)
# ---------------------------------------------------------------------------

@router.post("/enrich", response_model=IntakeEnrichResponse)
def enrich_base(
    *,
    db: Session = Depends(get_db),
    payload: IntakeEnrichRequest,
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """
    Complementa dados de cliente/imóvel já cadastrados (Regente CAM1-004).

    Apenas campos informados (não-nulos) são atualizados. Registra AuditLog
    com as mudanças pra rastreabilidade.
    """
    client = (
        db.query(ClientModel)
        .filter(
            ClientModel.id == payload.client_id,
            ClientModel.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado.")

    prop: Optional[PropertyModel] = None
    if payload.property_id:
        prop = (
            db.query(PropertyModel)
            .filter(
                PropertyModel.id == payload.property_id,
                PropertyModel.tenant_id == current_user.tenant_id,
            )
            .first()
        )
        if not prop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imóvel não encontrado.")

    updated_client_fields: list[str] = []
    updated_property_fields: list[str] = []

    # Aplica campos do cliente
    if payload.client_fields:
        cf = payload.client_fields.model_dump(exclude_unset=True, exclude_none=True)
        for key, value in cf.items():
            if getattr(client, key, None) != value:
                setattr(client, key, value)
                updated_client_fields.append(key)

    # Aplica campos do imóvel
    if prop and payload.property_fields:
        pf = payload.property_fields.model_dump(exclude_unset=True, exclude_none=True)
        field_map = {"car_number": "car_code", "ccir_number": "ccir", "area_hectares": "total_area_ha"}
        for key, value in pf.items():
            col = field_map.get(key, key)
            if getattr(prop, col, None) != value:
                setattr(prop, col, value)
                updated_property_fields.append(col)

    # Sem mudanças → retorna rápido sem audit
    if not updated_client_fields and not updated_property_fields:
        return IntakeEnrichResponse(
            client_id=client.id,
            property_id=prop.id if prop else None,
            updated_fields={"client": [], "property": []},
            audit_log_id=None,
        )

    # AuditLog de enrichment
    details_parts = []
    if updated_client_fields:
        details_parts.append(f"Cliente: {', '.join(updated_client_fields)}")
    if updated_property_fields:
        details_parts.append(f"Imóvel: {', '.join(updated_property_fields)}")
    details = "Base complementada via intake — " + " | ".join(details_parts)
    if payload.note:
        details += f" | Nota: {payload.note}"

    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        entity_type="client",
        entity_id=client.id,
        action="base_enriched",
        details=details,
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    from app.services.audit_hash import stamp_audit_hash  # noqa: PLC0415
    stamp_audit_hash(db, audit)
    db.commit()

    return IntakeEnrichResponse(
        client_id=client.id,
        property_id=prop.id if prop else None,
        updated_fields={"client": updated_client_fields, "property": updated_property_fields},
        audit_log_id=audit.id,
    )


@router.post("/drafts/{draft_id}/upload-url", response_model=IntakeDraftUploadUrlResponse)
def draft_upload_url(
    draft_id: int,
    body: IntakeDraftUploadUrlRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """CAM1-007: gera presigned URL pra upload direto ao MinIO num rascunho."""
    from app.services.storage import get_storage_service  # noqa: PLC0415

    draft = db.query(IntakeDraft).filter(
        IntakeDraft.id == draft_id,
        IntakeDraft.tenant_id == current_user.tenant_id,
    ).first()
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rascunho não encontrado.")
    if draft.state == IntakeDraftState.card_criado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Rascunho já foi commitado; anexe documentos ao processo em vez disso.",
        )

    result = get_storage_service().generate_presigned_put_url_for_draft(
        tenant_id=current_user.tenant_id,
        draft_id=draft_id,
        filename=body.filename,
        content_type=body.content_type,
    )
    return IntakeDraftUploadUrlResponse(**result)


@router.post(
    "/drafts/{draft_id}/documents",
    response_model=IntakeDraftDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def confirm_draft_upload(
    draft_id: int,
    body: IntakeDraftConfirmUploadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """CAM1-007: confirma upload e registra Document vinculado ao draft."""
    from app.models.document import Document, OcrStatus  # noqa: PLC0415

    draft = db.query(IntakeDraft).filter(
        IntakeDraft.id == draft_id,
        IntakeDraft.tenant_id == current_user.tenant_id,
    ).first()
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rascunho não encontrado.")
    if draft.state == IntakeDraftState.card_criado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Rascunho já commitado.",
        )

    ext = body.filename.split(".")[-1].lower() if "." in body.filename else None
    # CAM2IH-010 (Sprint H) — normaliza categoria para a taxonomia Regente canônica.
    from app.models.document_categories import normalize_category  # noqa: PLC0415
    normalized_category = normalize_category(body.document_category) or body.document_category
    doc = Document(
        tenant_id=current_user.tenant_id,
        intake_draft_id=draft_id,
        uploaded_by_user_id=current_user.id,
        filename=body.filename,
        original_file_name=body.filename,
        content_type=body.content_type,
        mime_type=body.content_type,
        extension=ext,
        storage_key=body.storage_key,
        s3_key=body.storage_key,
        file_size_bytes=body.file_size_bytes,
        size=body.file_size_bytes,
        document_type=body.document_type,
        document_category=normalized_category,
        ocr_status=OcrStatus.pending,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return IntakeDraftDocumentResponse(
        id=doc.id,
        filename=doc.filename,
        document_type=doc.document_type,
        document_category=doc.document_category,
        ocr_status=doc.ocr_status.value if doc.ocr_status else None,
        file_size_bytes=doc.file_size_bytes or 0,
        created_at=doc.created_at.isoformat() if doc.created_at else None,
    )


@router.get("/drafts/{draft_id}/documents", response_model=list[IntakeDraftDocumentResponse])
def list_draft_documents(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    from app.models.document import Document  # noqa: PLC0415

    draft = db.query(IntakeDraft).filter(
        IntakeDraft.id == draft_id,
        IntakeDraft.tenant_id == current_user.tenant_id,
    ).first()
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rascunho não encontrado.")

    docs = (
        db.query(Document)
        .filter(
            Document.intake_draft_id == draft_id,
            Document.tenant_id == current_user.tenant_id,
            Document.deleted_at.is_(None),
        )
        .order_by(Document.created_at.desc())
        .all()
    )
    return [
        IntakeDraftDocumentResponse(
            id=d.id,
            filename=d.filename,
            document_type=d.document_type,
            document_category=d.document_category,
            ocr_status=d.ocr_status.value if d.ocr_status else None,
            file_size_bytes=d.file_size_bytes or 0,
            created_at=d.created_at.isoformat() if d.created_at else None,
        )
        for d in docs
    ]


@router.post("/drafts/{draft_id}/import", response_model=IntakeImportResponse)
def import_draft_documents(
    draft_id: int,
    body: IntakeImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """
    CAM1-005: dispara agent_extrator (via Celery) em cada doc do draft.
    Usa o agente existente — não altera config de agentes.
    """
    from app.models.document import Document, OcrStatus  # noqa: PLC0415

    draft = db.query(IntakeDraft).filter(
        IntakeDraft.id == draft_id,
        IntakeDraft.tenant_id == current_user.tenant_id,
    ).first()
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rascunho não encontrado.")

    q = db.query(Document).filter(
        Document.intake_draft_id == draft_id,
        Document.tenant_id == current_user.tenant_id,
        Document.deleted_at.is_(None),
    )
    if body.doc_ids:
        q = q.filter(Document.id.in_(body.doc_ids))
    docs = q.all()

    if not docs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nenhum documento para importar.",
        )

    task_ids: list[str] = []
    from app.workers.agent_tasks import run_agent  # noqa: PLC0415
    for doc in docs:
        doc.ocr_status = OcrStatus.processing
        db.add(doc)
        try:
            t = run_agent.delay(
                agent_name="extrator",
                tenant_id=current_user.tenant_id,
                user_id=current_user.id,
                process_id=None,
                metadata={
                    "document_id": doc.id,
                    "storage_key": doc.storage_key,
                    "document_type": doc.document_type,
                    "intake_draft_id": draft_id,
                },
            )
            task_ids.append(t.id)
        except Exception as exc:
            logger.warning("Falha ao enfileirar extrator para doc_id=%s: %s", doc.id, exc)
    db.commit()

    return IntakeImportResponse(
        draft_id=draft_id,
        docs_queued=len(task_ids),
        task_ids=task_ids,
    )


@router.post("/drafts/{draft_id}/commit", response_model=IntakeCaseCreatedResponse)
def commit_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """
    Converte o rascunho em Process real reusando create_case.
    O draft passa a apontar pro process (linked_process_id) e muda para state=card_criado.
    Documentos vinculados ao draft são migrados pro novo processo.
    """
    from app.models.document import Document  # noqa: PLC0415

    draft = db.query(IntakeDraft).filter(
        IntakeDraft.id == draft_id,
        IntakeDraft.tenant_id == current_user.tenant_id,
    ).first()
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rascunho não encontrado.")
    if draft.state == IntakeDraftState.card_criado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Rascunho já commitado.",
        )
    if not has_minimal_base(draft.form_data or {}):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Dados mínimos faltando — complete antes de criar o card.",
        )

    # Reconstrói o payload a partir do form_data salvo
    payload = IntakeCreateCaseRequest(**(draft.form_data or {}))
    # O entry_type salvo no draft é a intenção explícita do usuário; sobrepõe
    # qualquer default do schema.
    if draft.entry_type:
        try:
            payload.entry_type = EntryType(draft.entry_type)
        except ValueError:
            pass

    response = create_case(db=db, payload=payload, current_user=current_user)

    # Regente Cam1: migrar docs do draft pro processo recém-criado
    (
        db.query(Document)
        .filter(
            Document.intake_draft_id == draft_id,
            Document.tenant_id == current_user.tenant_id,
        )
        .update(
            {
                "process_id": response.process_id,
                "client_id": response.client_id,
                "property_id": response.property_id,
            },
            synchronize_session=False,
        )
    )

    # Marca draft como committed
    draft.state = IntakeDraftState.card_criado
    draft.linked_process_id = response.process_id
    db.commit()

    return response
