from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from app.models.process import ProcessStatus


class ProcessBase(BaseModel):
    title: str
    process_type: Optional[str] = "licenciamento"
    client_id: int
    description: Optional[str] = None
    status: ProcessStatus = ProcessStatus.triagem
    property_id: Optional[int] = None
    priority: Optional[str] = None
    urgency: Optional[str] = None
    responsible_user_id: Optional[int] = None
    due_date: Optional[datetime] = None


class ProcessCreate(ProcessBase):
    @field_validator("status")
    @classmethod
    def validate_initial_status(cls, v: ProcessStatus) -> ProcessStatus:
        allowed = {ProcessStatus.lead, ProcessStatus.triagem}
        if v not in allowed:
            raise ValueError(
                f"Status inicial deve ser 'lead' ou 'triagem', recebido: '{v.value}'"
            )
        return v


class ProcessUpdate(BaseModel):
    title: Optional[str] = None
    process_type: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProcessStatus] = None


class ProcessStatusUpdate(BaseModel):
    status: ProcessStatus


class Process(ProcessBase):
    id: int
    tenant_id: int
    macroetapa: Optional[str] = None
    demand_type: Optional[str] = None
    entry_type: Optional[str] = None
    initial_summary: Optional[str] = None
    initial_diagnosis: Optional[str] = None
    intake_notes: Optional[str] = None
    ai_summary: Optional[str] = None
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


# CAM1-011 (Sprint I) — detalhe do processo com gates de prontidão.
# Mesma semântica do KanbanProcessCard (paridade consultor vê os mesmos sinais).
class ProcessDetail(Process):
    has_minimal_base: bool = False            # cliente com contato + imóvel com nome
    has_complementary_base: bool = False      # existe ≥1 documento vinculado
    missing_docs_count: int = 0               # itens obrigatórios pendentes no checklist
