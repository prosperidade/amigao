"""
Schemas de Intake — Sprint 1
"""
from pydantic import BaseModel, Field
from typing import Optional, List


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
    required_documents: List[DocumentRequirement]
    suggested_next_steps: List[str]
    checklist_template_demand_type: str
    urgency_flag: Optional[str]
    relevant_agencies: List[str]


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
    # Dados do cliente (cria novo ou vincula existente)
    client_id: Optional[int] = Field(None, description="Vincula cliente existente")
    new_client: Optional[IntakeClientCreate] = Field(None, description="Cria novo cliente")

    # Dados do imóvel
    property_id: Optional[int] = Field(None, description="Vincula imóvel existente")
    new_property: Optional[IntakePropertyCreate] = Field(None, description="Cria novo imóvel")

    # Dados do processo
    description: str
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
    suggested_next_steps: List[str]
    process_title: str
