"""
Schemas do Cliente Hub (Regente Cam2 — CAM2CH-001 a CAM2CH-009).
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# CAM2CH-002 — Bloco 1: Cabeçalho do cliente
class ClientHubChips(BaseModel):
    is_active: bool = False
    has_active_cases: bool = False
    has_doc_pending: bool = False
    has_contract_pending: bool = False
    is_pj: bool = False


class ClientHubHeader(BaseModel):
    id: int
    full_name: str
    legal_name: Optional[str] = None
    client_type: str
    cpf_cnpj: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: str                                  # lead | active | inactive | delinquent | blocked
    status_label: str = "Ativo"                  # label operacional Regente (CAM2CH-002)
    source_channel: Optional[str] = None
    created_at: Optional[datetime] = None


# CAM2CH-003 — Bloco 2: Dashboard resumido
class ClientHubKpis(BaseModel):
    properties_count: int = 0
    cases_active: int = 0
    cases_completed: int = 0
    contracts_emitted: int = 0
    diagnoses_done: int = 0
    pending_critical: int = 0
    last_activity_at: Optional[datetime] = None


# CAM2CH-009 — Estado computado do hub
class ClientHubSummary(BaseModel):
    header: ClientHubHeader
    chips: ClientHubChips
    kpis: ClientHubKpis
    state: str  # recem_criado | em_construcao | ativo | com_alertas | consolidado


# CAM2CH-005 — Mini-timeline de eventos por imóvel
class ClientHubPropertyEvent(BaseModel):
    when: datetime
    kind: str            # cadastro_criado | caso_aberto | etapa_avancada | doc_anexado | ...
    label: str           # texto visível
    macroetapa: Optional[str] = None


# CAM2CH-004 — Bloco 3: Lista de imóveis com status
class ClientHubProperty(BaseModel):
    id: int
    name: str
    matricula: Optional[str] = None
    car_code: Optional[str] = None
    municipality: Optional[str] = None
    state: Optional[str] = None
    total_area_ha: Optional[float] = None
    cases_count: int = 0
    primary_case_id: Optional[int] = None
    primary_case_macroetapa: Optional[str] = None
    primary_case_state: Optional[str] = None
    last_activity_at: Optional[datetime] = None
    # CAM2CH-005 — Bloco 4: Atividades por imóvel (mini-timeline)
    events: list[ClientHubPropertyEvent] = []

    model_config = ConfigDict(from_attributes=True)


# CAM2CH-006 — Bloco 5: Timeline geral do cliente
class ClientHubTimelineItem(BaseModel):
    when: datetime
    entity_type: str           # client | property | process | document | proposal | contract
    entity_id: Optional[int] = None
    action: str
    description: Optional[str] = None
    user_id: Optional[int] = None


# CAM2CH-007 — Bloco 6: Painel lateral de IA
class ClientHubAISummary(BaseModel):
    """Resumo executivo do cliente gerado deterministicamente a partir dos dados
    agregados. Versão MVP sem chamada a LLM — basear em regras para evitar
    latência e custo; pode evoluir para chamar agent_atendimento/agent_acompanhamento.
    """
    text: str                                   # frase(s) consolidando a situação
    focus_property_id: Optional[int] = None     # imóvel que concentra atenção
    focus_property_name: Optional[str] = None
    top_pending: Optional[str] = None           # pendência mais crítica
    recommendation: Optional[str] = None         # próxima ação sugerida
    source: str = "deterministic"                # deterministic | agent_atendimento
