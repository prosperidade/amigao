"""
Intake Classifier — Sprint 1

Classifica a demanda de entrada usando REGRAS ESTÁTICAS (sem LLM).
Retorna: demand_type, initial_diagnosis, documentos esperados, próximos passos.

Decisão arquitetural: MVP 1 usa regras determinísticas para ter
previsibilidade, auditabilidade e zero custo de token.
LLM entra na Wave 2 (Sprint 5+).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Estruturas de resposta
# ---------------------------------------------------------------------------

@dataclass
class DemandClassification:
    demand_type: str
    demand_label: str
    confidence: str                    # "high" | "medium" | "low"
    initial_diagnosis: str             # texto estruturado legível pelo consultor
    required_documents: List[dict]     # [{id, label, doc_type, category, required}]
    suggested_next_steps: List[str]    # ações recomendadas ao consultor
    checklist_template_demand_type: str  # chave para buscar template no BD
    urgency_flag: Optional[str]        # None | "alta" | "critica"
    relevant_agencies: List[str]       # órgãos ambientais relevantes


# ---------------------------------------------------------------------------
# Base de conhecimento — regras estáticas por tipo de demanda
# ---------------------------------------------------------------------------

_DEMAND_RULES: dict[str, dict] = {
    "car": {
        "label": "Cadastro Ambiental Rural (CAR)",
        "keywords": ["car", "cadastro ambiental", "sicar", "car pendente", "renovar car",
                     "car vencido", "app", "reserva legal", "app irregular"],
        "agencies": ["SEMA", "IBAMA", "SICAR"],
        "diagnosis": (
            "O cliente apresenta demanda relacionada ao Cadastro Ambiental Rural (CAR). "
            "Verifique o status atual do CAR no SICAR, a existência de pendências de análise, "
            "sobreposições com áreas embargadas ou inconsistências de geometria. "
            "A regularização do CAR é pré-requisito para crédito rural e licenciamento."
        ),
        "next_steps": [
            "Solicitar número do CAR e CPF/CNPJ do proprietário para consulta no SICAR",
            "Verificar se há análise pendente ou notificação de inconsistências",
            "Confirmar a geometria do imóvel e identificar APP e Reserva Legal",
            "Levantar se há embargo ou sobreposição com UC/terra indígena",
        ],
        "docs": [
            {"id": "car_numero", "label": "Número do CAR", "doc_type": "car", "category": "ambiental", "required": True},
            {"id": "matricula", "label": "Matrícula do Imóvel", "doc_type": "matricula", "category": "fundiario", "required": True},
            {"id": "ccir", "label": "CCIR", "doc_type": "ccir", "category": "fundiario", "required": True},
            {"id": "documento_proprietario", "label": "Documento do Proprietário (RG/CPF)", "doc_type": "doc_pessoal", "category": "pessoal", "required": True},
            {"id": "caf", "label": "CAF (Cadastro Agricultor Familiar)", "doc_type": "caf", "category": "fundiario", "required": False},
            {"id": "mapa_imovel", "label": "Mapa/Shapefile do Imóvel", "doc_type": "mapa", "category": "geoespacial", "required": False},
            {"id": "laudo_anterior", "label": "Laudo Ambiental Anterior (se houver)", "doc_type": "laudo", "category": "ambiental", "required": False},
        ],
    },
    "retificacao_car": {
        "label": "Retificação de CAR",
        "keywords": ["retificar car", "retificacao", "corrigir car", "car errado", "geometria errada",
                     "sobreposição car", "car sobreposto"],
        "agencies": ["SEMA", "SICAR"],
        "diagnosis": (
            "O cliente necessita de retificação do CAR existente. "
            "Isso pode envolver correção de geometria, ajuste de módulos fiscais, "
            "reclassificação de APP ou Reserva Legal, ou resolução de sobreposição com outro imóvel. "
            "É necessário identificar exatamente o tipo de inconsistência antes de iniciar o processo."
        ),
        "next_steps": [
            "Consultar o CAR atual no SICAR e identificar o tipo de inconsistência",
            "Verificar se há notificação de análise emitida pelo órgão",
            "Levantar histórico fundiário do imóvel para embasar a retificação",
            "Confirmar se é necessário novo levantamento topográfico",
        ],
        "docs": [
            {"id": "car_atual", "label": "CAR Atual (número e comprovante)", "doc_type": "car", "category": "ambiental", "required": True},
            {"id": "matricula", "label": "Matrícula do Imóvel", "doc_type": "matricula", "category": "fundiario", "required": True},
            {"id": "ccir", "label": "CCIR", "doc_type": "ccir", "category": "fundiario", "required": True},
            {"id": "notificacao_orgao", "label": "Notificação do Órgão (se houver)", "doc_type": "notificacao", "category": "administrativo", "required": False},
            {"id": "mapa_atual", "label": "Mapa/Shapefile Atual e Corrigido", "doc_type": "mapa", "category": "geoespacial", "required": True},
        ],
    },
    "licenciamento": {
        "label": "Licenciamento Ambiental",
        "keywords": ["licença ambiental", "licenciamento", "lia", "lp", "li", "lo", "licença prévia",
                     "licença instalação", "licença operação", "renovar licença", "licença vencida",
                     "atividade rural", "empreendimento"],
        "agencies": ["SEMA", "IBAMA", "IMAZON"],
        "diagnosis": (
            "O cliente demanda licenciamento ambiental. "
            "É necessário identificar o tipo de atividade, porte do empreendimento e fase do licenciamento "
            "(LP/LI/LO). O órgão competente varia conforme impacto e localização. "
            "Verifique se há licença anterior vencida ou processo em andamento."
        ),
        "next_steps": [
            "Identificar a atividade e classificar pelo porte/impacto (estadual vs federal)",
            "Verificar se há processo aberto no órgão competente",
            "Levantar documentos da atividade e do imóvel",
            "Verificar pendências de CAR ou embargo que bloqueiam o licenciamento",
        ],
        "docs": [
            {"id": "matricula", "label": "Matrícula do Imóvel", "doc_type": "matricula", "category": "fundiario", "required": True},
            {"id": "ccir", "label": "CCIR", "doc_type": "ccir", "category": "fundiario", "required": True},
            {"id": "car", "label": "CAR regularizado", "doc_type": "car", "category": "ambiental", "required": True},
            {"id": "licenca_anterior", "label": "Licença Anterior (se houver)", "doc_type": "licenca", "category": "administrativo", "required": False},
            {"id": "croqui_atividade", "label": "Croqui ou Planta da Atividade", "doc_type": "planta", "category": "tecnico", "required": False},
            {"id": "doc_proprietario", "label": "Documento do Proprietário", "doc_type": "doc_pessoal", "category": "pessoal", "required": True},
        ],
    },
    "regularizacao_fundiaria": {
        "label": "Regularização Fundiária",
        "keywords": ["regularização fundiária", "regularizar terra", "posse", "título", "sem escritura",
                     "terra sem registro", "incra", "terras devolutas", "titulação"],
        "agencies": ["INCRA", "SPU", "Cartório de Registro de Imóveis"],
        "diagnosis": (
            "O cliente apresenta demanda de regularização fundiária. "
            "Identifique se é regularização em terras particulares, devolutas ou de assentamento. "
            "Verifique a cadeia dominial do imóvel e a existência de posse ou registro informal. "
            "O caminho varia muito conforme histórico de ocupação e localização."
        ),
        "next_steps": [
            "Levantar histórico de ocupação e documentação disponível (posse, contrato, etc.)",
            "Verificar matrícula ou ausência de registro em cartório",
            "Confirmar se há sobreposição com terras públicas (INCRA/SPU)",
            "Identificar qual modalidade de regularização se aplica",
        ],
        "docs": [
            {"id": "contrato_compra", "label": "Contrato de Compra e Venda (se houver)", "doc_type": "contrato", "category": "fundiario", "required": False},
            {"id": "certidao_matricula", "label": "Certidão de Matrícula ou Transcrição", "doc_type": "matricula", "category": "fundiario", "required": False},
            {"id": "ccir", "label": "CCIR", "doc_type": "ccir", "category": "fundiario", "required": False},
            {"id": "car", "label": "CAR (se houver)", "doc_type": "car", "category": "ambiental", "required": False},
            {"id": "doc_proprietario", "label": "Documentos do Possuidor/Proprietário", "doc_type": "doc_pessoal", "category": "pessoal", "required": True},
            {"id": "declaracao_posse", "label": "Declaração de Posse ou Testemunhos", "doc_type": "declaracao", "category": "fundiario", "required": False},
        ],
    },
    "outorga": {
        "label": "Outorga de Uso de Água",
        "keywords": ["outorga", "água", "irrigação", "captação", "rio", "córrego", "poço artesiano",
                     "barragem", "açude", "uso de água", "sema agua"],
        "agencies": ["SEMA", "ANA", "IGAM"],
        "diagnosis": (
            "O cliente necessita de outorga de direito de uso de recursos hídricos. "
            "É necessário verificar a bacia hidrográfica, o volume de captação pretendido, "
            "o tipo de uso (irrigação, dessedentação, consumo humano) e se há interferência "
            "em corpos d'água. A outorga pode ser federal (ANA) ou estadual (SEMA/IGAM)."
        ),
        "next_steps": [
            "Identificar o corpo d'água e a bacia hidrográfica",
            "Levantar volume de captação e finalidade de uso",
            "Verificar se há outorga anterior ou notificação de uso irregular",
            "Confirmar competência federal (ANA) ou estadual",
        ],
        "docs": [
            {"id": "matricula", "label": "Matrícula do Imóvel", "doc_type": "matricula", "category": "fundiario", "required": True},
            {"id": "car", "label": "CAR", "doc_type": "car", "category": "ambiental", "required": True},
            {"id": "outorga_anterior", "label": "Outorga Anterior (se houver)", "doc_type": "outorga", "category": "administrativo", "required": False},
            {"id": "croqui_captacao", "label": "Croqui do Ponto de Captação", "doc_type": "planta", "category": "tecnico", "required": False},
            {"id": "doc_proprietario", "label": "Documento do Proprietário", "doc_type": "doc_pessoal", "category": "pessoal", "required": True},
        ],
    },
    "defesa": {
        "label": "Defesa Administrativa / Auto de Infração",
        "keywords": ["auto de infração", "multa ambiental", "embargo", "ibama", "notificação",
                     "defesa", "autuação", "fiscalização", "termo", "infração ambiental"],
        "agencies": ["IBAMA", "SEMA", "ICMBio"],
        "diagnosis": (
            "O cliente recebeu auto de infração ou notificação ambiental e precisa de defesa administrativa. "
            "É urgente identificar o órgão autuante, o tipo de infração, o prazo para defesa e "
            "se há embargo de atividade. Prazos são improrrogáveis — verifique imediatamente."
        ),
        "next_steps": [
            "⚠️ URGENTE: verificar prazo para defesa (normalmente 20 dias úteis do auto)",
            "Obter cópia do auto de infração e identificar o órgão autuante",
            "Levantar documentação técnica que sustente a defesa",
            "Verificar se o embargo afeta atividade produtiva e avaliar pedido de suspensão",
        ],
        "docs": [
            {"id": "auto_infracao", "label": "Auto de Infração / Notificação", "doc_type": "auto_infracao", "category": "administrativo", "required": True},
            {"id": "matricula", "label": "Matrícula do Imóvel", "doc_type": "matricula", "category": "fundiario", "required": True},
            {"id": "car", "label": "CAR", "doc_type": "car", "category": "ambiental", "required": True},
            {"id": "fotos_area", "label": "Fotos Atuais da Área", "doc_type": "foto", "category": "tecnico", "required": True},
            {"id": "doc_proprietario", "label": "Procuração / Documento do Proprietário", "doc_type": "doc_pessoal", "category": "pessoal", "required": True},
            {"id": "laudo_anterior", "label": "Laudo ou Relatório Anterior da Área", "doc_type": "laudo", "category": "ambiental", "required": False},
        ],
    },
    "compensacao": {
        "label": "Compensação / PRAD",
        "keywords": ["compensação", "prad", "recuperação de área degradada", "reserva legal compensação",
                     "app degradada", "recuperar mata", "plantio", "revegetação"],
        "agencies": ["SEMA", "IBAMA"],
        "diagnosis": (
            "O cliente precisa de compensação ambiental ou elaboração de PRAD (Plano de Recuperação "
            "de Área Degradada). Verifique se é compensação de Reserva Legal, APP ou exigência de "
            "recuperação por auto de infração ou licença. O PRAD precisa de diagnóstico técnico "
            "da área e cronograma de execução."
        ),
        "next_steps": [
            "Identificar a área degradada e o passivo ambiental específico",
            "Verificar se há exigência do órgão ou se é iniciativa do proprietário",
            "Levantar CAR e situação da Reserva Legal",
            "Definir se é compensação in loco ou por cotas de RL",
        ],
        "docs": [
            {"id": "car", "label": "CAR", "doc_type": "car", "category": "ambiental", "required": True},
            {"id": "matricula", "label": "Matrícula do Imóvel", "doc_type": "matricula", "category": "fundiario", "required": True},
            {"id": "exigencia_orgao", "label": "Exigência do Órgão (se houver)", "doc_type": "notificacao", "category": "administrativo", "required": False},
            {"id": "fotos_area_degradada", "label": "Fotos da Área Degradada", "doc_type": "foto", "category": "tecnico", "required": True},
            {"id": "laudo_solo", "label": "Laudo de Solo (se houver)", "doc_type": "laudo", "category": "ambiental", "required": False},
        ],
    },
    "exigencia_bancaria": {
        "label": "Exigência Bancária / Crédito Rural",
        "keywords": ["banco", "financiamento", "crédito rural", "pronaf", "pronamp", "bcb", "exigência banco",
                     "laudo banco", "car exigido", "caf banco", "car para financiamento"],
        "agencies": ["Banco", "BACEN"],
        "diagnosis": (
            "O cliente precisa regularizar sua situação ambiental para atender exigência de instituição "
            "financeira (banco/cooperativa). Geralmente envolve regularização do CAR, obtenção de CAF, "
            "licença ambiental ou laudo de conformidade. "
            "Identifique exatamente qual documento o banco exige para destravar o crédito."
        ),
        "next_steps": [
            "Obter a carta de exigência do banco com a lista exata de documentos necessários",
            "Verificar status de CAR, CAF e licenças já existentes",
            "Priorizar conforme prazo de proposta do financiamento",
            "Confirmar se é CAR simples ou regularização mais complexa",
        ],
        "docs": [
            {"id": "carta_exigencia_banco", "label": "Carta de Exigência do Banco", "doc_type": "carta_banco", "category": "bancario", "required": True},
            {"id": "car", "label": "CAR (atual ou a regularizar)", "doc_type": "car", "category": "ambiental", "required": True},
            {"id": "caf", "label": "DAP/CAF", "doc_type": "caf", "category": "fundiario", "required": False},
            {"id": "matricula", "label": "Matrícula do Imóvel", "doc_type": "matricula", "category": "fundiario", "required": True},
            {"id": "ccir", "label": "CCIR", "doc_type": "ccir", "category": "fundiario", "required": True},
        ],
    },
    "misto": {
        "label": "Demanda Mista / Múltiplos Passivos",
        "keywords": [],  # fallback - não é detectado por keyword, é atribuído manualmente
        "agencies": ["SEMA", "IBAMA", "INCRA"],
        "diagnosis": (
            "O caso apresenta múltiplos passivos ou combina diferentes trilhas regulatórias. "
            "É necessário priorizar as demandas pela urgência e dependências entre elas. "
            "Recomenda-se diagnóstico técnico aprofundado antes de definir o caminho."
        ),
        "next_steps": [
            "Listar todos os passivos identificados e classificar por urgência",
            "Identificar dependências (ex: CAR precisa estar regular antes do licenciamento)",
            "Propor ordem de resolução por prioridade e custo",
            "Confirmar escopo e valor com o cliente antes de iniciar",
        ],
        "docs": [
            {"id": "matricula", "label": "Matrícula do Imóvel", "doc_type": "matricula", "category": "fundiario", "required": True},
            {"id": "ccir", "label": "CCIR", "doc_type": "ccir", "category": "fundiario", "required": True},
            {"id": "car", "label": "CAR (se houver)", "doc_type": "car", "category": "ambiental", "required": False},
            {"id": "doc_proprietario", "label": "Documentos do Proprietário", "doc_type": "doc_pessoal", "category": "pessoal", "required": True},
        ],
    },
    "nao_identificado": {
        "label": "Tipo Não Identificado",
        "keywords": [],
        "agencies": [],
        "diagnosis": (
            "Não foi possível classificar automaticamente o tipo de demanda com base nas informações fornecidas. "
            "Recomenda-se conversa aprofundada com o cliente para entender a situação antes de prosseguir."
        ),
        "next_steps": [
            "Realizar triagem verbal detalhada com o cliente",
            "Solicitar qualquer documentação disponível para análise inicial",
            "Identificar a dor principal do cliente (crédito bloqueado, multa, regularização, etc.)",
        ],
        "docs": [
            {"id": "qualquer_doc", "label": "Qualquer documento disponível do imóvel", "doc_type": "outro", "category": "geral", "required": False},
        ],
    },
}

# Palavras-chave que indicam alta urgência
_URGENCY_KEYWORDS = {
    "critica": ["auto de infração", "embargo", "ibama", "prazo", "vencendo", "vencido", "urgente",
                "amanhã", "semana", "audiência", "liminar", "judicial"],
    "alta": ["banco", "financiamento", "crédito bloqueado", "bloqueado", "atrasado",
             "notificação", "intimação"],
}


# ---------------------------------------------------------------------------
# Funções de classificação
# ---------------------------------------------------------------------------

def _score_demand_type(text: str) -> dict[str, int]:
    """Pontua cada tipo de demanda com base nos keywords encontrados."""
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for demand_type, rules in _DEMAND_RULES.items():
        score = sum(1 for kw in rules["keywords"] if kw in text_lower)
        if score > 0:
            scores[demand_type] = score
    return scores


def _detect_urgency(text: str, urgency_hint: Optional[str] = None) -> Optional[str]:
    """Detecta sinalizadores de urgência no texto."""
    if urgency_hint in ("alta", "critica"):
        return urgency_hint
    text_lower = text.lower()
    for level in ("critica", "alta"):
        if any(kw in text_lower for kw in _URGENCY_KEYWORDS[level]):
            return level
    return None


def classify_demand(
    description: str,
    process_type: Optional[str] = None,
    urgency: Optional[str] = None,
    source_channel: Optional[str] = None,
) -> DemandClassification:
    """
    Classifica a demanda de entrada e retorna diagnóstico estruturado.

    Parâmetros:
        description   : texto livre da demanda (conversa, e-mail, etc.)
        process_type  : tipo de processo já informado pelo consultor (override)
        urgency       : nível de urgência informado ("baixa"|"media"|"alta"|"critica")
        source_channel: canal de entrada ("whatsapp"|"email"|etc.)

    Retorna:
        DemandClassification com demand_type, diagnóstico e documentos esperados.
    """
    # 1. Se o consultor já informou o tipo, usar diretamente
    if process_type and process_type in _DEMAND_RULES:
        demand_type = process_type
        confidence = "high"
    else:
        # 2. Pontuar por keywords no texto
        scores = _score_demand_type(description)
        if not scores:
            demand_type = "nao_identificado"
            confidence = "low"
        elif len(scores) == 1:
            demand_type = list(scores.keys())[0]
            confidence = "high" if scores[demand_type] >= 2 else "medium"
        else:
            # Múltiplos tipos detectados
            sorted_types = sorted(scores, key=lambda k: scores[k], reverse=True)
            top_score = scores[sorted_types[0]]
            second_score = scores[sorted_types[1]] if len(sorted_types) > 1 else 0
            if top_score > second_score + 1:
                demand_type = sorted_types[0]
                confidence = "medium"
            else:
                demand_type = "misto"
                confidence = "medium"

    rules = _DEMAND_RULES[demand_type]
    urgency_flag = _detect_urgency(description, urgency)

    # Diagnóstico base + nota de urgência se aplicável
    diagnosis_text = rules["diagnosis"]
    if urgency_flag == "critica":
        diagnosis_text = "⚠️ CASO URGENTE — " + diagnosis_text
    elif urgency_flag == "alta":
        diagnosis_text = "📌 Atenção: urgência detectada. " + diagnosis_text

    return DemandClassification(
        demand_type=demand_type,
        demand_label=rules["label"],
        confidence=confidence,
        initial_diagnosis=diagnosis_text,
        required_documents=rules["docs"],
        suggested_next_steps=rules["next_steps"],
        checklist_template_demand_type=demand_type,
        urgency_flag=urgency_flag,
        relevant_agencies=rules["agencies"],
    )


def get_demand_rules() -> dict:
    """Retorna todas as regras de demanda (para seed de templates)."""
    return _DEMAND_RULES
