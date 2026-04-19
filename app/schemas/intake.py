"""
Schemas de Intake — Sprint 1 (Regente v3 Camada 1)

Mudanças Regente v3 (2026-04):
  - description agora é OPCIONAL (card nasce sem descrição completa)
  - entry_type adicionado: 5 cenários (novo/existente + docs)
  - initial_summary separado da description técnica
"""
from typing import Optional

from pydantic import BaseModel, Field

from app.models.process import EntryType


class IntakeClassifyRequest(BaseModel):
    description: str = Field(..., min_length=10, description="Descrição da demanda em texto livre")
    process_type: Optional[str] = Field(None, description="Tipo pré-selecionado pelo consultor (opcional)")
    urgency: Optional[str] = Field(None, description="Nível de urgência: baixa | media | alta | critica")
    source_channel: Optional[str] = Field(None, description="Canal de entrada: whatsapp | email | presencial | etc.")


class DocumentRequirement(BaseModel):
    id: str
    label: str
    doc_type: str
    category: str
    required: bool


class IntakeClassifyResponse(BaseModel):
    demand_type: str
    demand_label: str
    confidence: str
    initial_diagnosis: str
    required_documents: list[DocumentRequirement]
    suggested_next_steps: list[str]
    checklist_template_demand_type: str
    urgency_flag: Optional[str]
    relevant_agencies: list[str]


class IntakeClientCreate(BaseModel):
    full_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    cpf_cnpj: Optional[str] = None
    client_type: Optional[str] = "pf"
    source_channel: Optional[str] = None


class IntakePropertyCreate(BaseModel):
    name: str
    municipality: Optional[str] = None
    state: Optional[str] = None
    car_number: Optional[str] = None
    ccir_number: Optional[str] = None
    area_hectares: Optional[float] = None


class IntakeCreateCaseRequest(BaseModel):
    # Cenário Regente: define o fluxo da tela
    entry_type: Optional[EntryType] = Field(
        EntryType.novo_cliente_novo_imovel,
        description="Cenário do cadastro (5 opções Regente Cam1). Default mantém compat.",
    )

    # Dados do cliente (cria novo ou vincula existente)
    client_id: Optional[int] = Field(None, description="Vincula cliente existente")
    new_client: Optional[IntakeClientCreate] = Field(None, description="Cria novo cliente")

    # Dados do imóvel
    property_id: Optional[int] = Field(None, description="Vincula imóvel existente")
    new_property: Optional[IntakePropertyCreate] = Field(None, description="Cria novo imóvel")

    # Dados do processo
    # description agora é OPCIONAL — card nasce sem descrição (regra Regente Cam1)
    description: Optional[str] = Field(
        None,
        description="Descrição técnica da demanda (opcional — pode ser enriquecida depois).",
    )
    initial_summary: Optional[str] = Field(
        None,
        description="Resumo curto da demanda na voz do cliente (primeiro contato).",
    )
    urgency: Optional[str] = "media"
    source_channel: Optional[str] = None
    intake_notes: Optional[str] = None

    # Classificação (pode vir do /classify ou ser informada diretamente)
    demand_type: Optional[str] = None
    process_type: Optional[str] = None


class IntakeCaseCreatedResponse(BaseModel):
    client_id: int
    property_id: Optional[int]
    process_id: int
    demand_type: str
    demand_label: str
    initial_diagnosis: str
    checklist_generated: bool
    suggested_next_steps: list[str]
    process_title: str


# ---------------------------------------------------------------------------
# Rascunhos (CAM1-008/009) — salvar e continuar depois
# ---------------------------------------------------------------------------

class IntakeDraftCreateRequest(BaseModel):
    """Payload livre — o wizard salva o estado parcial do formulário."""
    entry_type: Optional[EntryType] = None
    form_data: dict = Field(default_factory=dict)


class IntakeDraftUpdateRequest(BaseModel):
    entry_type: Optional[EntryType] = None
    form_data: Optional[dict] = None


class IntakeDraftResponse(BaseModel):
    id: int
    state: str
    entry_type: Optional[str]
    form_data: dict
    linked_process_id: Optional[int]
    created_by_user_id: Optional[int]
    has_minimal_base: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# CAM1-004 — Complementar base existente
# ---------------------------------------------------------------------------

class IntakeEnrichClientFields(BaseModel):
    """Campos opcionais para enriquecer cliente existente."""
    phone: Optional[str] = None
    email: Optional[str] = None
    cpf_cnpj: Optional[str] = None
    client_type: Optional[str] = None


class IntakeEnrichPropertyFields(BaseModel):
    """Campos opcionais para enriquecer imóvel existente."""
    municipality: Optional[str] = None
    state: Optional[str] = None
    car_number: Optional[str] = None
    ccir_number: Optional[str] = None
    area_hectares: Optional[float] = None


class IntakeEnrichRequest(BaseModel):
    """Complementar base já iniciada (Regente CAM1-004).

    Atualiza campos do cliente e/ou imóvel existentes. Apenas campos informados
    são alterados — campos ausentes são preservados. Registra AuditLog.
    """
    client_id: int = Field(..., description="Cliente a enriquecer")
    property_id: Optional[int] = Field(None, description="Imóvel a enriquecer (opcional)")
    client_fields: Optional[IntakeEnrichClientFields] = None
    property_fields: Optional[IntakeEnrichPropertyFields] = None
    note: Optional[str] = Field(None, description="Nota de contexto (aparece no AuditLog)")


class IntakeEnrichResponse(BaseModel):
    client_id: int
    property_id: Optional[int]
    updated_fields: dict  # {"client": [...], "property": [...]}
    audit_log_id: Optional[int] = None


# ---------------------------------------------------------------------------
# CAM1-007 / CAM1-005 — Upload de documentos em rascunho de intake
# ---------------------------------------------------------------------------

class IntakeDraftUploadUrlRequest(BaseModel):
    filename: str
    content_type: str
    document_type: Optional[str] = None   # matricula, car, ccir, cpf_cnpj, etc.
    document_category: Optional[str] = None  # fundiario, ambiental, ...


class IntakeDraftUploadUrlResponse(BaseModel):
    upload_url: str
    storage_key: str
    expires_in: int


class IntakeDraftConfirmUploadRequest(BaseModel):
    storage_key: str
    filename: str
    content_type: str
    file_size_bytes: int = 0
    document_type: Optional[str] = None
    document_category: Optional[str] = None


class IntakeDraftDocumentResponse(BaseModel):
    id: int
    filename: str
    document_type: Optional[str]
    document_category: Optional[str]
    ocr_status: Optional[str]
    file_size_bytes: int
    created_at: Optional[str] = None


class IntakeImportRequest(BaseModel):
    """Dispara agent_extrator em todos os documentos do draft (CAM1-005).

    O agente lê cada doc via OCR+LLM, extrai campos estruturados e sugere
    preenchimento da base. Resultado fica disponível via GET do draft.
    """
    doc_ids: Optional[list[int]] = None  # se omitido, usa todos os docs do draft


class IntakeImportResponse(BaseModel):
    draft_id: int
    docs_queued: int
    task_ids: list[str] = []
