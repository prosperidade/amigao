import enum

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class ProcessStatus(str, enum.Enum):
    """Máquina de estados conforme DocumentodeRegrasdeNegocio.md"""
    lead = "lead"
    triagem = "triagem"
    diagnostico = "diagnostico"
    planejamento = "planejamento"
    execucao = "execucao"
    protocolo = "protocolo"
    aguardando_orgao = "aguardando_orgao"
    pendencia_orgao = "pendencia_orgao"
    concluido = "concluido"
    arquivado = "arquivado"
    cancelado = "cancelado"


class ProcessPriority(str, enum.Enum):
    baixa = "baixa"
    media = "media"
    alta = "alta"
    critica = "critica"


class DemandType(str, enum.Enum):
    """Tipo de demanda ambiental identificado no intake."""
    car = "car"
    retificacao_car = "retificacao_car"
    licenciamento = "licenciamento"
    regularizacao_fundiaria = "regularizacao_fundiaria"
    outorga = "outorga"
    defesa = "defesa"
    compensacao = "compensacao"
    exigencia_bancaria = "exigencia_bancaria"
    prad = "prad"
    misto = "misto"
    nao_identificado = "nao_identificado"


class IntakeSource(str, enum.Enum):
    """Canal de entrada da demanda."""
    whatsapp = "whatsapp"
    email = "email"
    presencial = "presencial"
    banco = "banco"
    cooperativa = "cooperativa"
    parceiro = "parceiro"
    indicacao = "indicacao"
    site = "site"


# Transições válidas conforme Regras de Negócio
VALID_TRANSITIONS = {
    ProcessStatus.lead: [ProcessStatus.triagem],
    ProcessStatus.triagem: [ProcessStatus.diagnostico, ProcessStatus.cancelado],
    ProcessStatus.diagnostico: [ProcessStatus.planejamento, ProcessStatus.cancelado],
    ProcessStatus.planejamento: [ProcessStatus.execucao],
    ProcessStatus.execucao: [ProcessStatus.protocolo, ProcessStatus.cancelado],
    ProcessStatus.protocolo: [ProcessStatus.aguardando_orgao],
    ProcessStatus.aguardando_orgao: [ProcessStatus.pendencia_orgao, ProcessStatus.concluido],
    ProcessStatus.pendencia_orgao: [ProcessStatus.execucao],
    ProcessStatus.concluido: [ProcessStatus.arquivado],
    ProcessStatus.cancelado: [ProcessStatus.arquivado],
    ProcessStatus.arquivado: [],
}


TERMINAL_PROCESS_STATUSES = {ProcessStatus.arquivado}


def is_valid_transition(from_status: ProcessStatus, to_status: ProcessStatus) -> bool:
    return to_status in VALID_TRANSITIONS.get(from_status, [])


class Process(Base):
    __tablename__ = "processes"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=True, index=True)

    title = Column(String, nullable=False)
    description = Column(Text)
    process_type = Column(String, nullable=False)  # licenciamento, CAR, retificacao_car, etc.

    status = Column(Enum(ProcessStatus), default=ProcessStatus.triagem, nullable=False)
    priority = Column(Enum(ProcessPriority), default=ProcessPriority.media, nullable=True)
    urgency = Column(String, nullable=True)

    # Responsável interno
    responsible_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Dados de protocolo externo
    destination_agency = Column(String, nullable=True)
    external_protocol_number = Column(String, nullable=True)

    # Datas operacionais
    opened_at = Column(DateTime(timezone=True), nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    # Intake / classificação
    intake_source = Column(Enum(IntakeSource), nullable=True)  # canal de entrada
    demand_type = Column(Enum(DemandType), nullable=True)       # tipo de demanda classificado
    initial_diagnosis = Column(Text, nullable=True)             # pré-diagnóstico por regras
    suggested_checklist_template = Column(String, nullable=True) # demand_type do template sugerido
    intake_notes = Column(Text, nullable=True)                  # observações do intake

    # IA / score
    ai_summary = Column(Text, nullable=True)
    risk_score = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relacionamentos
    tenant = relationship("Tenant")
    client = relationship("Client", back_populates="processes")
