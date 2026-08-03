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
    # Sprint 1 (Ficha 07) — RAMO condicional na saída da E2: se há documento
    # essencial pendente vai para a coleta (E3); senão pula direto ao diagnóstico
    # técnico (E4). AMBOS são transições válidas; o DESTINO recomendado é resolvido
    # por `resolve_next_macroetapa`. `coleta_documental` fica em 1º (default/legado
    # — `nexts[0]` preserva o comportamento de callers que não ramificam).
    Macroetapa.diagnostico_preliminar: [
        Macroetapa.coleta_documental,
        Macroetapa.diagnostico_tecnico,
    ],
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


def resolve_next_macroetapa(
    current: Macroetapa | None,
    *,
    has_essential_pending: bool = False,
) -> Macroetapa | None:
    """Sprint 1 (Ficha 07) — resolve o DESTINO recomendado do avanço.

    Ramo na saída da E2 (`diagnostico_preliminar`):
      - há documento essencial pendente → `coleta_documental` (E3);
      - senão → `diagnostico_tecnico` (E4), pulando a coleta.

    Demais etapas: sucessor único e linear (`nexts[0]`). Terminal → ``None``.

    NÃO automatiza o avanço — só indica para onde o avanço (confirmado pelo
    consultor) deve apontar. O gate de prontidão continua valendo (#82: agentes
    propõem, consultor decide).
    """
    if current is None:
        return None
    nexts = MACROETAPA_TRANSITIONS.get(current, [])
    if not nexts:
        return None
    if current is Macroetapa.diagnostico_preliminar:
        return (
            Macroetapa.coleta_documental
            if has_essential_pending
            else Macroetapa.diagnostico_tecnico
        )
    return nexts[0]


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
    # E1 — ENTRADA. Ficha 07 §5: "Documentos: primeiros uploads + checklist;
    # Dados: cadastro básico"; §7: a saída da E1 é "mínimo essencial recebido +
    # agentes do intake rodados". Ou seja, a CONVERSA e a CLASSIFICAÇÃO da
    # demanda são trabalho da Entrada — é delas que o intake se alimenta.
    Macroetapa.entrada_demanda: [
        {"id": "ed_01", "label": "Registrar dados básicos do cliente (e verificar duplicidade)"},
        {"id": "ed_02", "label": "Identificar canal de entrada"},
        {"id": "ed_03", "label": "Vincular imóvel ao caso"},
        {"id": "ed_04", "label": "Realizar ligação/reunião aplicando o roteiro de perguntas"},
        {"id": "ed_05", "label": "Subir e transcrever o áudio da conversa"},
        {"id": "ed_06", "label": "Registrar a demanda e a intenção do empreendedor"},
        {"id": "ed_07", "label": "Subir os documentos do mínimo essencial"},
        {"id": "ed_08", "label": "Rodar os agentes do intake (tipo de demanda e urgência)"},
    ],
    # E2 — DIAGNÓSTICO PRELIMINAR. Ficha 07 §5: "Conferência: campos do intake
    # (protagonista); Dados: base consolidada; Visão geral: nasce o diagnóstico
    # preliminar; Ações: remediação + divergências + pendências"; §7: a saída é
    # "diagnóstico gerado + base consolidada (Consolidação rodou)".
    Macroetapa.diagnostico_preliminar: [
        {"id": "dp_01", "label": "Conferir os campos lidos dos documentos (Conferência)"},
        {"id": "dp_02", "label": "Resolver as divergências apontadas"},
        {"id": "dp_03", "label": "Gravar na base (Consolidação)"},
        {"id": "dp_04", "label": "Ler o diagnóstico preliminar na Visão geral"},
        {"id": "dp_05", "label": "Validar objetivo real do cliente"},
        {"id": "dp_06", "label": "Triar as ações de remediação propostas"},
        {"id": "dp_07", "label": "Identificar lacunas e documentos essenciais pendentes"},
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


DIAGNOSTIC_MACROETAPAS: frozenset[Macroetapa] = frozenset(
    {Macroetapa.diagnostico_preliminar, Macroetapa.diagnostico_tecnico}
)

# `completion_pct` é gravado na escala 0–100 em todo o sistema
# (`calculate_completion_pct` retorna `completed/total * 100`). O gate e o estado
# formal comparam contra ESTA escala — etapa só está "completa" a 100, não a 1.
COMPLETE_PCT: float = 100.0


def compute_macroetapa_state(
    checklist: MacroetapaChecklist,
    *,
    is_current: bool = False,
    has_blockers: bool = False,
    current_macroetapa: Macroetapa | None = None,
    diagnosis_validated: bool = False,
    contract_signed: bool = True,
) -> MacroetapaState:
    """Deriva o estado formal de uma etapa a partir do checklist + flags externas.

    Regras:
      - sem actions ou todas pendentes E não é a corrente → nao_iniciada
      - has_blockers=True → travada
      - alguma action com needs_human_validation=True não validada → aguardando_validacao
      - etapa de diagnóstico (`current_macroetapa in DIAGNOSTIC_MACROETAPAS`) sem
        `RegulatoryDiagnosis.validated_at` preenchido → aguardando_validacao,
        mesmo com checklist 100% (fix/diagnostico-propaga-estado — Princípio 1:
        peça formal só "fecha" depois da assinatura do consultor).
      - E7 (`contrato_formalizacao`, terminal) sem `Contract.signed_at` →
        aguardando_validacao, mesmo com checklist 100% (Fase 0, item 9: o
        caso não está concluído sem contrato assinado — honesto até o
        fluxo de assinatura do Sprint 5 existir).
      - completion_pct >= 100 → concluida (ou pronta_para_avancar se ainda corrente)
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
    is_diagnostic_stage = current_macroetapa in DIAGNOSTIC_MACROETAPAS

    if is_diagnostic_stage and pct >= COMPLETE_PCT and not diagnosis_validated:
        # Checklist cheio mas diagnóstico não assinado: ainda não é
        # pronta_para_avancar — o card precisa concordar com o bloco
        # "diagnóstico assinado".
        return MacroetapaState.aguardando_validacao

    if current_macroetapa == Macroetapa.contrato_formalizacao and pct >= COMPLETE_PCT:
        # E7 é TERMINAL: não há "avançar". Sem contrato assinado, a etapa fica
        # honestamente aguardando (o caso não está concluído); COM o contrato
        # assinado (S5-C), o caso CONCLUI — `concluida` mesmo sendo a corrente
        # (não existe pronta_para_avancar para a etapa terminal).
        if not contract_signed:
            return MacroetapaState.aguardando_validacao
        return MacroetapaState.concluida

    if pct >= COMPLETE_PCT:
        return MacroetapaState.pronta_para_avancar if is_current else MacroetapaState.concluida
    if pct > 0:
        return MacroetapaState.em_andamento
    if is_current:
        return MacroetapaState.aguardando_input
    return MacroetapaState.nao_iniciada


def list_macroetapa_blockers(
    checklist: MacroetapaChecklist | None,
    *,
    documents_pending_required: int = 0,
    current_macroetapa: Macroetapa | None = None,
) -> list[str]:
    """Coleta blockers que impedem o avanço da etapa.

    Hoje cobre:
      - documentos obrigatórios pendentes
      - actions críticas marcadas (futuro: ações com flag `blocking=True`)
      - validação humana pendente

    Sprint 1 (Ficha 07) — exceção do RAMO da E2: em `diagnostico_preliminar`
    documento essencial pendente NÃO trava o avanço; ele ROTEIA para a coleta
    (E3) via `resolve_next_macroetapa`. Travar a E2 por doc pendente impediria
    justamente o caminho que existe para coletar esse doc. Nas demais etapas
    (notadamente a própria `coleta_documental`) o doc pendente continua sendo
    blocker.
    """
    blockers: list[str] = []
    docs_block = current_macroetapa is not Macroetapa.diagnostico_preliminar
    if docs_block and documents_pending_required > 0:
        blockers.append(
            f"{documents_pending_required} documento(s) obrigatório(s) pendente(s)"
        )
    if checklist:
        for a in (checklist.actions or []):
            if a.get("completed") and a.get("needs_human_validation") and not a.get("validated_at"):
                blockers.append(f"Validação humana pendente: {a.get('label')}")
    return blockers


def can_advance_macroetapa(
    checklist: MacroetapaChecklist | None,
    *,
    documents_pending_required: int = 0,
    require_complete: bool = True,
    current_macroetapa: Macroetapa | None = None,
    diagnosis_validated: bool = False,
    consolidacao_executada: bool = True,
    rota_validada: bool = True,
    proposta_aceita: bool = True,
    rota_pendencia_detalhe: str | None = None,
) -> tuple[bool, list[str]]:
    """Regente CAM3FT-005 — só avança se output mínimo OK + sem trava + validações OK.

    fix/diagnostico-propaga-estado: ao sair de `diagnostico_preliminar` ou
    `diagnostico_tecnico` o gate exige `RegulatoryDiagnosis.validated_at`
    preenchido (Princípio 1 — peças formais sempre com assinatura humana).
    Os callers passam `current_macroetapa` (etapa que está na coluna do card)
    e `diagnosis_validated` (`True` quando existe diagnóstico assinado para
    o processo).

    Fase 0 (gap-analysis Ficha 07, item 2): a Ficha exige que a saída da E2
    dependa da Consolidação (Ficha 05) ter rodado — sem ela, "base consolidada"
    não existe. `consolidacao_executada` default `True` preserva o
    comportamento de callers que ainda não passam o sinal explicitamente;
    quem sai de `diagnostico_preliminar` deve calcular via
    `macroetapa_engine.has_consolidated()` e passar aqui.

    Fase 0 (item 9 do adendo): mesma lógica para a saída da E5 (`rota_validada`,
    via `macroetapa_engine.has_rota_validada()`) e da E6 (`proposta_aceita`,
    via `has_proposal_accepted()`) — as entidades Rota/Proposal já existem;
    só faltava o gate ler o estado real delas. Defaults `True` preservam
    callers que ainda não passam o sinal explicitamente.
    """
    blockers = list_macroetapa_blockers(
        checklist,
        documents_pending_required=documents_pending_required,
        current_macroetapa=current_macroetapa,
    )
    if checklist is None:
        return False, ["Etapa não iniciada (sem checklist)."]
    if require_complete and float(checklist.completion_pct or 0.0) < COMPLETE_PCT:
        blockers.append("Output mínimo não atingido (checklist incompleto).")
    if current_macroetapa in DIAGNOSTIC_MACROETAPAS and not diagnosis_validated:
        blockers.append("Diagnóstico desta etapa ainda não foi assinado pelo consultor.")
    if current_macroetapa == Macroetapa.diagnostico_preliminar and not consolidacao_executada:
        blockers.append(
            "Consolidação ainda não rodou para este processo — "
            "grave a Conferência na base antes de avançar."
        )
    if current_macroetapa == Macroetapa.caminho_regulatorio and not rota_validada:
        # A frase ESPECÍFICA ("3 passos sem classificação; 5 classificados mas
        # ainda não validados") vem do caller, que tem o banco à mão
        # (`macroetapa_engine.descrever_pendencia_rota`). O texto abaixo é o piso:
        # verdadeiro, e era ele que segurava a consultora sem dizer em qual das
        # duas portas — classificar, depois validar — ela estava presa (30/07).
        blockers.append(
            rota_pendencia_detalhe
            or (
                "A rota regulatória ainda não foi fechada (todos os passos "
                "validados e classificados) — feche a rota antes de avançar."
            )
        )
    if current_macroetapa == Macroetapa.orcamento_negociacao and not proposta_aceita:
        blockers.append(
            "A proposta ainda não foi aceita pelo cliente — registre o "
            "aceite antes de avançar."
        )
    return (len(blockers) == 0), blockers
