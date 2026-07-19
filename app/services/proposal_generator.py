"""
Proposal Generator — S5-A (escopo nasce da Rota; ADR-028)

A proposta comercial **nasce da Rota validada** (E5): cada passo classificado
como ``item_proposta`` (faturável) vira um item de escopo RASTREÁVEL (o item
aponta o passo de origem via ``rota_passo_id``). Passos ``direcao`` (orientação)
NÃO entram no escopo faturável.

A ``PRICE_TABLE`` **mudou de papel** (ADR-028): deixou de ser a FONTE do escopo
(antes o ``scope_base`` fixo por demand_type gerava os itens) e passou a ser
PRECIFICAÇÃO — a faixa (min/max/prazo) por demanda × complexidade sugere o valor,
distribuído entre os itens faturáveis como preço unitário default (editável).

Sem Rota validada (ou sem passo faturável), a geração é BLOQUEADA com mensagem
honesta — coerente com o gate E5→E6 (``has_rota_validada``). Determinístico
(sem LLM).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from app.models.checklist_template import ProcessChecklist
from app.models.process import Process
from app.models.rota import Rota, RotaPassoClassificacao, RotaStatus
from app.models.task import Task


class ProposalGenerationError(Exception):
    """Geração bloqueada — carrega mensagem honesta para o consultor (ex.: sem
    Rota validada). O endpoint traduz em HTTP 422."""

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
    # S5-A — rastreabilidade: o item aponta o passo da Rota que o originou.
    rota_passo_id: Optional[int] = None
    detail: Optional[str] = None
    norma_ref: Optional[str] = None
    prazo_dias: Optional[int] = None


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
    # S5-A — Rota validada de origem (proveniência no nível da proposta).
    rota_id: Optional[int] = field(default=None)


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def generate_proposal_from_rota(
    db: Session,
    process_id: int,
    tenant_id: int,
) -> ProposalDraft:
    """Gera o rascunho da proposta A PARTIR da(s) Rota(s) validada(s) (S5-A).

    Cada passo ``item_proposta`` vira um item de escopo rastreável (aponta o
    ``rota_passo_id``). A ``PRICE_TABLE`` precifica: a faixa da demanda ×
    complexidade sugere o valor da rota, distribuído entre seus itens faturáveis
    como preço unitário default (editável pelo consultor).

    Bloqueia (``ProposalGenerationError``) se não houver Rota validada ou se
    nenhuma tiver passo faturável — mensagem honesta, coerente com o gate E5→E6.
    """
    process = db.query(Process).filter(
        Process.id == process_id,
        Process.tenant_id == tenant_id,
    ).first()
    if process is None:
        raise ProposalGenerationError("Processo não encontrado.")

    rotas = (
        db.query(Rota)
        .filter(
            Rota.tenant_id == tenant_id,
            Rota.process_id == process_id,
            Rota.status == RotaStatus.validada,
        )
        .order_by(Rota.id.asc())
        .all()
    )
    if not rotas:
        raise ProposalGenerationError(
            "A proposta nasce da Rota: feche (valide) a Rota Regulatória na etapa "
            "'Caminho Regulatório' (E5) antes de gerar a proposta."
        )

    urgency = process.urgency if process else "media"
    complexity = _estimate_complexity(db, process_id, tenant_id, urgency)

    scope_items: list[dict] = []
    value_min = 0.0
    value_max = 0.0
    value_suggested = 0.0
    estimated_days = 0

    for rota in rotas:
        billable = [
            p for p in rota.passos
            if p.classificacao == RotaPassoClassificacao.item_proposta
        ]
        if not billable:
            continue
        price_info = PRICE_TABLE.get(rota.demand_type or "", DEFAULT_PRICE)
        band = price_info[complexity]
        rota_min, rota_max = float(band["min"]), float(band["max"])
        rota_suggested = round((rota_min + rota_max) / 2, -2)
        # Distribui o valor sugerido da rota entre seus itens faturáveis (default
        # editável). Ajuste de arredondamento no último item para fechar a soma.
        per_item = round(rota_suggested / len(billable), 2)
        value_min += rota_min
        value_max += rota_max
        value_suggested += rota_suggested
        estimated_days = max(estimated_days, int(band["prazo"]))
        acc = 0.0
        for idx, passo in enumerate(billable):
            unit_price = round(rota_suggested - acc, 2) if idx == len(billable) - 1 else per_item
            acc += unit_price
            scope_items.append({
                "description": passo.titulo,
                "detail": passo.descricao or None,
                "unit": "serv.",
                "qty": 1.0,
                "unit_price": unit_price,
                "total": unit_price,
                "rota_passo_id": passo.id,
                "norma_ref": passo.norma_ref,
                "prazo_dias": passo.prazo_estimado_dias,
            })

    if not scope_items:
        raise ProposalGenerationError(
            "A Rota validada não tem passos faturáveis: classifique ao menos um "
            "passo como 'item de proposta' (os passos de 'direção' orientam, mas "
            "não entram no escopo cobrável)."
        )

    title = f"Proposta — {process.title}" if process.title else "Proposta Comercial"
    demand_type = process.demand_type.value if process.demand_type else None
    payment_terms = "50% na assinatura do contrato e 50% na entrega do serviço."
    if complexity == "alta":
        payment_terms = "30% na assinatura, 40% na conclusão do protocolo, 30% na entrega final."

    return ProposalDraft(
        title=title,
        demand_type=demand_type,
        complexity=complexity,
        scope_items=scope_items,
        suggested_value_min=round(value_min, 2),
        suggested_value_max=round(value_max, 2),
        suggested_value=round(value_suggested, 2),
        estimated_days=estimated_days,
        payment_terms=payment_terms,
        notes=_build_notes(demand_type, complexity),
        rota_id=rotas[0].id if len(rotas) == 1 else None,
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
