"""
Schemas do Imóvel Hub (Regente Cam2 — CAM2IH-001 a CAM2IH-010).
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# CAM2IH-002 — Bloco 1: Cabeçalho
class PropertyHubHeader(BaseModel):
    id: int
    name: str
    client_id: int
    client_name: Optional[str] = None
    registry_number: Optional[str] = None   # matrícula
    ccir: Optional[str] = None
    nirf: Optional[str] = None
    car_code: Optional[str] = None
    car_status: Optional[str] = None
    total_area_ha: Optional[float] = None
    municipality: Optional[str] = None
    state: Optional[str] = None
    biome: Optional[str] = None
    has_embargo: bool = False
    created_at: Optional[datetime] = None
    # CAM2IH-007 — origem por campo: raw | ai_extracted | human_validated
    field_sources: dict = {}

    # CAM2IH-003/004 (Sprint H) — campos técnicos expostos na Aba Informações
    rl_status: Optional[str] = None                 # averbada | proposta | pendente | cancelada
    app_area_ha: Optional[float] = None
    regulatory_issues: list = []                    # [{tipo, descricao, severidade}]
    area_documental_ha: Optional[float] = None
    area_grafica_ha: Optional[float] = None
    tipologia: Optional[str] = None                 # agricultura | pecuaria | misto | outro
    strategic_notes: Optional[str] = None


class PropertyFieldValidateRequest(BaseModel):
    fields: list[str]  # nomes dos campos que o humano está validando
    source: Optional[str] = "human_validated"  # ou "ai_extracted" / "raw"


class PropertyHubChips(BaseModel):
    has_car: bool = False
    car_pending: bool = False
    has_embargo: bool = False
    has_active_cases: bool = False
    has_doc_pending: bool = False


# CAM2IH-003 — Bloco 2: Dashboard técnico (KPIs do imóvel)
class PropertyHubTechnicalKpis(BaseModel):
    cases_count: int = 0
    cases_active: int = 0
    documents_count: int = 0
    analyses_count: int = 0
    last_document_at: Optional[datetime] = None
    last_analysis_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    pending_critical: int = 0


# CAM2IH-006 — Bloco 6: Indicadores de saúde (score de maturidade)
class PropertyHealthScore(BaseModel):
    """Score 0-100 + componentes."""
    overall: int                           # 0-100
    documental_completeness: int           # 0-100
    regulatory_update: int                 # 0-100
    analysis_depth: int                    # 0-100
    consistency: int                       # 0-100
    confidence_base: int                   # 0-100
    pending_critical: int = 0
    label: str                             # "ruim" | "media" | "boa" | "consolidada"


# CAM2IH-008 — Estado do hub
class PropertyHubSummary(BaseModel):
    header: PropertyHubHeader
    chips: PropertyHubChips
    kpis: PropertyHubTechnicalKpis
    health: PropertyHealthScore
    state: str                             # recem_criado | em_construcao | memoria_estruturada | com_alertas | consolidado


# Timeline de eventos do imóvel (aba Histórico)
class PropertyHubEvent(BaseModel):
    when: datetime
    kind: str
    label: str
    entity_type: str
    entity_id: Optional[int] = None
    macroetapa: Optional[str] = None
    user_id: Optional[int] = None


# Aba Casos
class PropertyHubCase(BaseModel):
    id: int
    title: str
    demand_type: Optional[str] = None
    urgency: Optional[str] = None
    macroetapa: Optional[str] = None
    macroetapa_label: Optional[str] = None
    state: Optional[str] = None
    next_step: Optional[str] = None
    responsible_user_name: Optional[str] = None
    last_activity_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# CAM2IH-005 — Painel lateral de IA
class PropertyAISummary(BaseModel):
    text: str
    main_inconsistency: Optional[str] = None
    top_pending: Optional[str] = None
    recommendation: Optional[str] = None
    source: str = "deterministic"
