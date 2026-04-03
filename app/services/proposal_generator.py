"""
Proposal Generator — Sprint 4

Geração automática de rascunho de proposta comercial com base em:
- Tipo de demanda (demand_type)
- Complexidade estimada (nº de documentos pendentes, nº de etapas da trilha)
- Urgência do processo

Implementação: regras estáticas (sem LLM — Wave 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.checklist_template import ProcessChecklist
from app.models.process import Process
from app.models.task import Task

# ---------------------------------------------------------------------------
# Tabela de preços base por tipo de demanda (valores em R$)
# ---------------------------------------------------------------------------

PRICE_TABLE: dict[str, dict] = {
    "car": {
        "name": "Cadastro Ambiental Rural (CAR)",
        "baixa":  {"min": 800,   "max": 1_500,  "prazo": 15},
        "media":  {"min": 1_500, "max": 2_800,  "prazo": 25},
        "alta":   {"min": 2_800, "max": 5_000,  "prazo": 40},
        "scope_base": [
            "Levantamento e organização da documentação fundiária",
            "Levantamento GPS / georreferenciamento da propriedade",
            "Análise de passivo ambiental (APP, Reserva Legal)",
            "Elaboração e submissão do CAR no SICAR",
            "Acompanhamento da análise junto ao órgão competente",
            "Emissão e entrega do recibo/protocolo ao cliente",
        ],
    },
    "retificacao_car": {
        "name": "Retificação do CAR",
        "baixa":  {"min": 600,   "max": 1_200,  "prazo": 10},
        "media":  {"min": 1_200, "max": 2_200,  "prazo": 20},
        "alta":   {"min": 2_200, "max": 4_000,  "prazo": 35},
        "scope_base": [
            "Análise do CAR existente e identificação de inconsistências",
            "Novo levantamento GPS (se necessário)",
            "Elaboração e submissão da retificação no SICAR",
            "Acompanhamento da reanálise junto ao órgão",
        ],
    },
    "licenciamento": {
        "name": "Licenciamento Ambiental",
        "baixa":  {"min": 3_000,  "max": 7_000,  "prazo": 60},
        "media":  {"min": 7_000,  "max": 18_000, "prazo": 120},
        "alta":   {"min": 18_000, "max": 45_000, "prazo": 180},
        "scope_base": [
            "Diagnóstico ambiental preliminar e enquadramento da licença",
            "Coleta e organização da documentação técnica",
            "Elaboração dos estudos ambientais (EIA/RIMA, RAS, PCA ou RAP)",
            "Protocolo do processo junto ao órgão licenciador",
            "Atendimento a exigências técnicas do órgão",
            "Acompanhamento até a emissão da licença",
        ],
    },
    "regularizacao_fundiaria": {
        "name": "Regularização Fundiária",
        "baixa":  {"min": 2_500, "max": 5_500,  "prazo": 60},
        "media":  {"min": 5_500, "max": 12_000, "prazo": 90},
        "alta":   {"min": 12_000,"max": 25_000, "prazo": 150},
        "scope_base": [
            "Levantamento documental completo do imóvel",
            "Georreferenciamento certificado pelo INCRA (SIGEF)",
            "Elaboração do memorial descritivo e planta georref.",
            "Certificação junto ao INCRA e registro em cartório",
        ],
    },
    "outorga": {
        "name": "Outorga de Uso da Água",
        "baixa":  {"min": 1_500, "max": 3_500,  "prazo": 45},
        "media":  {"min": 3_500, "max": 7_000,  "prazo": 90},
        "alta":   {"min": 7_000, "max": 15_000, "prazo": 120},
        "scope_base": [
            "Diagnóstico da necessidade e tipo de uso hídrico",
            "Levantamento hidrológico e de disponibilidade",
            "Elaboração e protocolo do pedido de outorga",
            "Acompanhamento junto à ANA/SEMA até emissão da portaria",
        ],
    },
    "defesa": {
        "name": "Defesa Administrativa Ambiental",
        "baixa":  {"min": 1_200, "max": 2_800,  "prazo": 20},
        "media":  {"min": 2_800, "max": 6_000,  "prazo": 40},
        "alta":   {"min": 6_000, "max": 15_000, "prazo": 60},
        "scope_base": [
            "Análise do auto de infração e prazo recursal",
            "Levantamento de evidências e documentação técnica",
            "Elaboração e protocolo da defesa administrativa",
            "Acompanhamento do recurso junto ao órgão autuador",
        ],
    },
    "compensacao": {
        "name": "Compensação Ambiental / PRAD",
        "baixa":  {"min": 2_000, "max": 5_000,  "prazo": 60},
        "media":  {"min": 5_000, "max": 12_000, "prazo": 120},
        "alta":   {"min": 12_000,"max": 30_000, "prazo": 180},
        "scope_base": [
            "Diagnóstico e vistoria da área degradada",
            "Elaboração do Plano de Recuperação de Área Degradada (PRAD)",
            "Aprovação do PRAD pelo órgão competente",
            "Execução, monitoramento e relatório de recuperação",
            "Obtenção do atestado de cumprimento do PRAD",
        ],
    },
    "exigencia_bancaria": {
        "name": "Atendimento a Exigência Bancária",
        "baixa":  {"min": 500,   "max": 1_200,  "prazo": 10},
        "media":  {"min": 1_200, "max": 2_500,  "prazo": 20},
        "alta":   {"min": 2_500, "max": 5_000,  "prazo": 30},
        "scope_base": [
            "Análise da exigência do banco e verificação de pendências",
            "Regularização das pendências ambientais identificadas",
            "Elaboração do laudo técnico ou declaração de regularidade",
            "Entrega da documentação ao banco e ao cliente",
        ],
    },
}

DEFAULT_PRICE = {
    "name": "Consultoria Ambiental",
    "baixa":  {"min": 800,   "max": 2_000,  "prazo": 20},
    "media":  {"min": 2_000, "max": 5_000,  "prazo": 45},
    "alta":   {"min": 5_000, "max": 15_000, "prazo": 90},
    "scope_base": ["Serviços de consultoria ambiental conforme escopo a definir."],
}


# ---------------------------------------------------------------------------
# Estrutura de retorno
# ---------------------------------------------------------------------------

@dataclass
class ScopeItem:
    description: str
    unit: str = "serv."
    qty: float = 1.0
    unit_price: float = 0.0
    total: float = 0.0


@dataclass
class ProposalDraft:
    title: str
    demand_type: Optional[str]
    complexity: str              # "baixa" | "media" | "alta"
    scope_items: list[dict]
    suggested_value_min: float
    suggested_value_max: float
    suggested_value: float       # ponto médio arredondado
    estimated_days: int
    payment_terms: str
    notes: str


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def generate_proposal_draft(
    db: Session,
    process_id: int,
    tenant_id: int,
) -> ProposalDraft:
    """
    Gera um rascunho de proposta com base nos dados do processo.
    Usa regras estáticas de precificação por tipo de demanda.
    """
    process = db.query(Process).filter(
        Process.id == process_id,
        Process.tenant_id == tenant_id,
    ).first()

    demand_type = process.demand_type.value if process and process.demand_type else None
    urgency = process.urgency if process else "media"

    # Determinar complexidade
    complexity = _estimate_complexity(db, process_id, tenant_id, urgency)

    price_info = PRICE_TABLE.get(demand_type or "", DEFAULT_PRICE)
    price_band = price_info[complexity]

    # Escopo base
    scope_items = [
        {
            "description": desc,
            "unit": "serv.",
            "qty": 1.0,
            "unit_price": 0.0,
            "total": 0.0,
        }
        for desc in price_info["scope_base"]
    ]

    # Valor sugerido = média da faixa
    value_min = float(price_band["min"])
    value_max = float(price_band["max"])
    value_suggested = round((value_min + value_max) / 2, -2)  # arredonda para centena

    demand_label = price_info["name"]
    title = f"Proposta — {demand_label}"
    if process and process.title:
        title = f"Proposta — {process.title}"

    payment_terms = "50% na assinatura do contrato e 50% na entrega do serviço."
    if complexity == "alta":
        payment_terms = "30% na assinatura, 40% na conclusão do protocolo, 30% na entrega final."

    notes = _build_notes(demand_type, complexity)

    return ProposalDraft(
        title=title,
        demand_type=demand_type,
        complexity=complexity,
        scope_items=scope_items,
        suggested_value_min=value_min,
        suggested_value_max=value_max,
        suggested_value=value_suggested,
        estimated_days=price_band["prazo"],
        payment_terms=payment_terms,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _estimate_complexity(
    db: Session,
    process_id: int,
    tenant_id: int,
    urgency: Optional[str],
) -> str:
    """
    Estima complexidade do processo baseado em indicadores objetivos.
    Retorna "baixa", "media" ou "alta".
    """
    score = 0

    # Urgência
    if urgency == "alta":
        score += 1
    elif urgency == "critica":
        score += 2

    # Documentos pendentes
    checklist = (
        db.query(ProcessChecklist)
        .filter(ProcessChecklist.process_id == process_id)
        .first()
    )
    if checklist:
        items = checklist.items or []
        pending = sum(1 for i in items if i.get("status") == "pending")
        if pending >= 8:
            score += 2
        elif pending >= 4:
            score += 1

    # Nº de tarefas na trilha
    task_count = (
        db.query(Task)
        .filter(Task.process_id == process_id, Task.tenant_id == tenant_id)
        .count()
    )
    if task_count >= 7:
        score += 1

    if score >= 3:
        return "alta"
    elif score >= 1:
        return "media"
    return "baixa"


def _build_notes(demand_type: Optional[str], complexity: str) -> str:
    notes_map = {
        "car": "Prazo sujeito à disponibilidade de vistoria de campo e tempo de análise do SICAR.",
        "licenciamento": "O prazo indicado refere-se à elaboração dos estudos e protocolo. O tempo de análise do órgão é variável e depende da carga de trabalho do órgão.",
        "regularizacao_fundiaria": "Prazo para certificação pelo INCRA pode variar conforme demanda do órgão.",
        "outorga": "O prazo de emissão da portaria de outorga está sujeito ao cronograma da ANA/SEMA.",
        "defesa": "O prazo de resposta do órgão autuador é estabelecido por lei e não está sujeito ao controle da contratada.",
        "compensacao": "Prazo de execução do PRAD sujeito a condições climáticas e disponibilidade de mudas.",
        "exigencia_bancaria": "Prazo poderá ser impactado por pendências de órgãos externos.",
    }
    base = notes_map.get(demand_type or "", "Prazo e valores estimados. Contrato definitivo sujeito a revisão após análise detalhada.")
    if complexity == "alta":
        base += " Dada a alta complexidade, recomenda-se reunião presencial para alinhamento de escopo."
    return base
