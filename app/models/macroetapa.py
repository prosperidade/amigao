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


class MacroetapaState(str, enum.Enum):
    """Estados formais por etapa (Regente Cam3 CAM3FT-004).

    Granularidade maior que o boolean completed/completion_pct atual.
    Calculado dinamicamente — pode ser persistido como cache opcional.
    """
    nao_iniciada = "nao_iniciada"
    em_andamento = "em_andamento"
    aguardando_input = "aguardando_input"          # consultor precisa inserir algo
    aguardando_validacao = "aguardando_validacao"  # IA produziu, humano valida
    travada = "travada"                             # bloqueio impeditivo
    pronta_para_avancar = "pronta_para_avancar"
    concluida = "concluida"


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


# CAM3WS-003 — Objetivo e saída esperada por etapa (Regente Camada 3)
# Usado pelo Workspace pra mostrar "o que precisa ser produzido pra avançar"
# e pelo TransitionGuard pra validar prontidão.
MACROETAPA_METADATA: dict[Macroetapa, dict] = {
    Macroetapa.entrada_demanda: {
        "objective": "Transformar o contato inicial em caso formal aberto",
        "expected_outputs": [
            "Caso aberto",
            "Cliente vinculado ou criado",
            "Ficha inicial mínima gerada",
        ],
    },
    Macroetapa.diagnostico_preliminar: {
        "objective": "Entender o problema provável antes da coleta documental completa",
        "expected_outputs": [
            "Ficha inicial estruturada",
            "Hipótese preliminar validada",
            "Urgência definida",
            "Lacunas registradas",
            "Documentos a solicitar definidos",
        ],
    },
    Macroetapa.coleta_documental: {
        "objective": "Montar o dossiê mínimo válido para análise",
        "expected_outputs": [
            "Dossiê mínimo montado",
            "Pendências claras",
            "Base documental apta para diagnóstico técnico",
        ],
    },
    Macroetapa.diagnostico_tecnico: {
        "objective": "Transformar documentos e bases em leitura técnica confiável",
        "expected_outputs": [
            "Problema real definido",
            "Complexidade classificada",
            "Risco inicial mapeado",
            "Resumo técnico consolidado",
        ],
    },
    Macroetapa.caminho_regulatorio: {
        "objective": "Escolher a rota correta do caso",
        "expected_outputs": [
            "Caminho regulatório definido",
            "Ordem das próximas etapas",
            "Plano de contingência",
            "Checklist da próxima fase",
        ],
    },
    Macroetapa.orcamento_negociacao: {
        "objective": "Converter o caminho em proposta viável",
        "expected_outputs": [
            "Proposta emitida",
            "Proposta negociada",
            "Aceite comercial registrado",
        ],
    },
    Macroetapa.contrato_formalizacao: {
        "objective": "Transformar proposta aceita em caso formalizado e apto para execução",
        "expected_outputs": [
            "Caso formalizado",
            "Escopo fechado",
            "Autorização obtida",
            "Pronto para execução plena",
        ],
    },
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


# Regente CAM3WS-004 (Sprint N) — agentes por etapa: principal + secundários.
# Representa "quem é disparado quando", sem alterar prompts/chains dos agentes.
# Fonte: docs/MUDANCAS_REGENTE.md seção CAM3WS-004.
MACROETAPA_AGENTS: dict[Macroetapa, dict[str, list[str]]] = {
    Macroetapa.entrada_demanda: {
        "primary": ["agent_atendimento"],
        "secondary": ["agent_extrator", "agent_vigia"],
    },
    Macroetapa.diagnostico_preliminar: {
        "primary": ["agent_atendimento", "agent_diagnostico"],
        "secondary": ["agent_legislacao", "agent_extrator"],
    },
    Macroetapa.coleta_documental: {
        "primary": ["agent_extrator"],
        "secondary": ["agent_vigia", "agent_acompanhamento"],
    },
    Macroetapa.diagnostico_tecnico: {
        "primary": ["agent_diagnostico"],
        "secondary": ["agent_extrator", "agent_legislacao", "agent_redator"],
    },
    Macroetapa.caminho_regulatorio: {
        "primary": ["agent_legislacao"],
        "secondary": ["agent_diagnostico", "agent_redator", "agent_acompanhamento"],
    },
    Macroetapa.orcamento_negociacao: {
        "primary": ["agent_orcamento", "agent_financeiro"],
        "secondary": ["agent_redator", "agent_acompanhamento", "agent_vigia"],
    },
    Macroetapa.contrato_formalizacao: {
        "primary": ["agent_redator", "agent_financeiro"],
        "secondary": ["agent_legislacao", "agent_acompanhamento", "agent_vigia"],
    },
}


def get_stage_agents(etapa: Macroetapa) -> dict[str, list[str]]:
    """Retorna {primary: [...], secondary: [...]} para a etapa. Default vazio."""
    return MACROETAPA_AGENTS.get(etapa, {"primary": [], "secondary": []})


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

    # [{id, label, completed: bool, completed_at: str|null, agent_suggestion: str|null,
    #   needs_human_validation: bool, validated_at: str|null, validated_by_user_id: int|null}]
    actions = Column(PortableJSON, nullable=False, default=list)

    completion_pct = Column(Float, nullable=False, default=0.0)

    # Regente Cam3 CAM3FT-004 — estado formal da etapa (cache; valor canônico
    # vem de compute_macroetapa_state).
    state = Column(String, nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relacionamentos
    process = relationship("Process", backref="macroetapa_checklists")


# ---------------------------------------------------------------------------
# Cálculo de estado (CAM3FT-004) e gate de avanço (CAM3FT-005)
# ---------------------------------------------------------------------------


def compute_macroetapa_state(
    checklist: "MacroetapaChecklist",
    *,
    is_current: bool = False,
    has_blockers: bool = False,
) -> MacroetapaState:
    """Deriva o estado formal de uma etapa a partir do checklist + flags externas.

    Regras:
      - sem actions ou todas pendentes E não é a corrente → nao_iniciada
      - has_blockers=True → travada
      - alguma action com needs_human_validation=True não validada → aguardando_validacao
      - completion_pct >= 1.0 → concluida (ou pronta_para_avancar se ainda corrente)
      - tem actions completas mas não todas → em_andamento
      - é a corrente sem progresso → aguardando_input
    """
    actions = checklist.actions or []
    if has_blockers:
        return MacroetapaState.travada

    # Validações humanas pendentes (CAM3WS-005)
    for a in actions:
        if a.get("completed") and a.get("needs_human_validation") and not a.get("validated_at"):
            return MacroetapaState.aguardando_validacao

    pct = float(checklist.completion_pct or 0.0)
    if pct >= 1.0:
        return MacroetapaState.pronta_para_avancar if is_current else MacroetapaState.concluida
    if pct > 0:
        return MacroetapaState.em_andamento
    if is_current:
        return MacroetapaState.aguardando_input
    return MacroetapaState.nao_iniciada


def list_macroetapa_blockers(
    checklist: "MacroetapaChecklist | None",
    *,
    documents_pending_required: int = 0,
) -> list[str]:
    """Coleta blockers que impedem o avanço da etapa.

    Hoje cobre:
      - documentos obrigatórios pendentes
      - actions críticas marcadas (futuro: ações com flag `blocking=True`)
      - validação humana pendente
    """
    blockers: list[str] = []
    if documents_pending_required > 0:
        blockers.append(
            f"{documents_pending_required} documento(s) obrigatório(s) pendente(s)"
        )
    if checklist:
        for a in (checklist.actions or []):
            if a.get("completed") and a.get("needs_human_validation") and not a.get("validated_at"):
                blockers.append(f"Validação humana pendente: {a.get('label')}")
    return blockers


def can_advance_macroetapa(
    checklist: "MacroetapaChecklist | None",
    *,
    documents_pending_required: int = 0,
    require_complete: bool = True,
) -> tuple[bool, list[str]]:
    """Regente CAM3FT-005 — só avança se output mínimo OK + sem trava + validações OK."""
    blockers = list_macroetapa_blockers(
        checklist, documents_pending_required=documents_pending_required
    )
    if checklist is None:
        return False, ["Etapa não iniciada (sem checklist)."]
    if require_complete and float(checklist.completion_pct or 0.0) < 1.0:
        blockers.append("Output mínimo não atingido (checklist incompleto).")
    return (len(blockers) == 0), blockers
