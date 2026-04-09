"""
Macroetapa — 7 etapas do fluxo real da consultoria ambiental (MVP1 pre-contrato).

Cada processo avanca por estas etapas sequencialmente.
A MacroetapaChecklist armazena as acoes de cada etapa por processo.
"""

from __future__ import annotations

import enum

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.types import PortableJSON


# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------

class Macroetapa(str, enum.Enum):
    """7 macroetapas do MVP1 (pre-contrato)."""
    entrada_demanda = "entrada_demanda"
    diagnostico_preliminar = "diagnostico_preliminar"
    coleta_documental = "coleta_documental"
    diagnostico_tecnico = "diagnostico_tecnico"
    caminho_regulatorio = "caminho_regulatorio"
    orcamento_negociacao = "orcamento_negociacao"
    contrato_formalizacao = "contrato_formalizacao"


# Ordem para calculo de progresso e stepper
MACROETAPA_ORDER: list[Macroetapa] = list(Macroetapa)

MACROETAPA_INDEX: dict[Macroetapa, int] = {m: i for i, m in enumerate(MACROETAPA_ORDER)}


# ---------------------------------------------------------------------------
# Transicoes validas
# ---------------------------------------------------------------------------

MACROETAPA_TRANSITIONS: dict[Macroetapa, list[Macroetapa]] = {
    Macroetapa.entrada_demanda: [Macroetapa.diagnostico_preliminar],
    Macroetapa.diagnostico_preliminar: [Macroetapa.coleta_documental],
    Macroetapa.coleta_documental: [Macroetapa.diagnostico_tecnico],
    Macroetapa.diagnostico_tecnico: [Macroetapa.caminho_regulatorio],
    Macroetapa.caminho_regulatorio: [Macroetapa.orcamento_negociacao],
    Macroetapa.orcamento_negociacao: [Macroetapa.contrato_formalizacao],
    Macroetapa.contrato_formalizacao: [],  # terminal para MVP1
}

TERMINAL_MACROETAPAS = {Macroetapa.contrato_formalizacao}


def is_valid_macroetapa_transition(
    from_etapa: Macroetapa, to_etapa: Macroetapa
) -> bool:
    return to_etapa in MACROETAPA_TRANSITIONS.get(from_etapa, [])


# ---------------------------------------------------------------------------
# Mapeamento status legado → macroetapa
# ---------------------------------------------------------------------------

from app.models.process import ProcessStatus  # noqa: E402

STATUS_TO_MACROETAPA: dict[ProcessStatus, Macroetapa | None] = {
    ProcessStatus.lead: Macroetapa.entrada_demanda,
    ProcessStatus.triagem: Macroetapa.entrada_demanda,
    ProcessStatus.diagnostico: Macroetapa.diagnostico_preliminar,
    ProcessStatus.planejamento: Macroetapa.caminho_regulatorio,
    ProcessStatus.execucao: None,          # pos-contrato (MVP2)
    ProcessStatus.protocolo: None,         # pos-contrato (MVP2)
    ProcessStatus.aguardando_orgao: None,  # pos-contrato (MVP2)
    ProcessStatus.pendencia_orgao: None,   # pos-contrato (MVP2)
    ProcessStatus.concluido: None,         # terminal
    ProcessStatus.cancelado: None,         # terminal
    ProcessStatus.arquivado: None,         # terminal
}


# ---------------------------------------------------------------------------
# Labels pt-BR
# ---------------------------------------------------------------------------

MACROETAPA_LABELS: dict[Macroetapa, str] = {
    Macroetapa.entrada_demanda: "Entrada da Demanda",
    Macroetapa.diagnostico_preliminar: "Diagnóstico Preliminar",
    Macroetapa.coleta_documental: "Coleta Documental",
    Macroetapa.diagnostico_tecnico: "Diagnóstico Técnico",
    Macroetapa.caminho_regulatorio: "Caminho Regulatório",
    Macroetapa.orcamento_negociacao: "Orçamento e Negociação",
    Macroetapa.contrato_formalizacao: "Contrato e Formalização",
}


# ---------------------------------------------------------------------------
# Agente vinculado a cada macroetapa
# ---------------------------------------------------------------------------

MACROETAPA_AGENT_CHAIN: dict[Macroetapa, str | None] = {
    Macroetapa.entrada_demanda: "intake",
    Macroetapa.diagnostico_preliminar: "diagnostico_completo",
    Macroetapa.coleta_documental: None,  # manual + extrator sob demanda
    Macroetapa.diagnostico_tecnico: "diagnostico_completo",
    Macroetapa.caminho_regulatorio: "analise_regulatoria",
    Macroetapa.orcamento_negociacao: "gerar_proposta",
    Macroetapa.contrato_formalizacao: None,  # manual com redator sob demanda
}


# ---------------------------------------------------------------------------
# Checklist de acoes padrao por macroetapa (por demand_type)
# ---------------------------------------------------------------------------

DEFAULT_ACTIONS: dict[Macroetapa, list[dict]] = {
    Macroetapa.entrada_demanda: [
        {"id": "ed_01", "label": "Registrar dados básicos do cliente"},
        {"id": "ed_02", "label": "Identificar canal de entrada"},
        {"id": "ed_03", "label": "Vincular imóvel ao caso"},
        {"id": "ed_04", "label": "Registrar demanda inicial"},
        {"id": "ed_05", "label": "Verificar cliente existente (deduplicação)"},
    ],
    Macroetapa.diagnostico_preliminar: [
        {"id": "dp_01", "label": "Realizar ligação/reunião"},
        {"id": "dp_02", "label": "Aplicar roteiro de perguntas"},
        {"id": "dp_03", "label": "Gravar/transcrever áudio"},
        {"id": "dp_04", "label": "Identificar tipo de demanda"},
        {"id": "dp_05", "label": "Classificar urgência"},
        {"id": "dp_06", "label": "Validar objetivo real do cliente"},
        {"id": "dp_07", "label": "Consolidar ficha inicial do caso"},
        {"id": "dp_08", "label": "Identificar lacunas de informação"},
    ],
    Macroetapa.coleta_documental: [
        {"id": "cd_01", "label": "Gerar checklist documental"},
        {"id": "cd_02", "label": "Enviar pedido de documentos ao cliente"},
        {"id": "cd_03", "label": "Receber e registrar documentos"},
        {"id": "cd_04", "label": "Verificar completude documental"},
        {"id": "cd_05", "label": "Cobrar documentos faltantes"},
        {"id": "cd_06", "label": "Validar legibilidade e validade"},
    ],
    Macroetapa.diagnostico_tecnico: [
        {"id": "dt_01", "label": "Ler documentos e bases iniciais"},
        {"id": "dt_02", "label": "Consultar bases externas (SIGEF, MapBiomas, SiCAR)"},
        {"id": "dt_03", "label": "Detectar divergências e inconsistências"},
        {"id": "dt_04", "label": "Classificar complexidade do caso"},
        {"id": "dt_05", "label": "Avaliar risco inicial"},
        {"id": "dt_06", "label": "Consolidar diagnóstico técnico"},
    ],
    Macroetapa.caminho_regulatorio: [
        {"id": "cr_01", "label": "Cruzar diagnóstico com legislação aplicável"},
        {"id": "cr_02", "label": "Consultar agente regulatório (IA)"},
        {"id": "cr_03", "label": "Definir rota principal e alternativa"},
        {"id": "cr_04", "label": "Sequenciar etapas regulatórias"},
        {"id": "cr_05", "label": "Validar caminho com consultor sênior"},
    ],
    Macroetapa.orcamento_negociacao: [
        {"id": "on_01", "label": "Estimar escopo e esforço"},
        {"id": "on_02", "label": "Gerar proposta comercial"},
        {"id": "on_03", "label": "Enviar proposta ao cliente"},
        {"id": "on_04", "label": "Negociar ajustes de escopo/valor"},
        {"id": "on_05", "label": "Confirmar aceite do cliente"},
    ],
    Macroetapa.contrato_formalizacao: [
        {"id": "cf_01", "label": "Gerar minuta de contrato"},
        {"id": "cf_02", "label": "Revisar cláusulas e anexos"},
        {"id": "cf_03", "label": "Enviar contrato para assinatura"},
        {"id": "cf_04", "label": "Confirmar assinatura"},
        {"id": "cf_05", "label": "Registrar início oficial do caso"},
    ],
}


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class MacroetapaChecklist(Base):
    """Checklist de acoes por macroetapa, vinculado a um processo."""
    __tablename__ = "macroetapa_checklists"
    __table_args__ = (
        UniqueConstraint("process_id", "macroetapa", name="uq_macroetapa_process"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    process_id = Column(
        Integer,
        ForeignKey("processes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    macroetapa = Column(String, nullable=False, index=True)

    # [{id, label, completed: bool, completed_at: str|null, agent_suggestion: str|null}]
    actions = Column(PortableJSON, nullable=False, default=list)

    completion_pct = Column(Float, nullable=False, default=0.0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relacionamentos
    process = relationship("Process", backref="macroetapa_checklists")
