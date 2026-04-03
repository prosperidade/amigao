"""
LLM Classifier — Sprint 5 (Wave 2) + Sprint IA-1

Upgrade semantico do intake_classifier.py usando LLM.
Estrategia:
  1. Tenta classificacao com regras estaticas (zero custo)
  2. Se confidence == "low" E IA habilitada -> chama LLM para refinamento
  3. Se LLM falhar -> retorna resultado das regras (degradacao graciosa)

Prompts carregados do banco via prompt_service (com fallback hardcoded).
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from app.core.config import settings
from app.services.intake_classifier import (
    _DEMAND_RULES,
    DemandClassification,
    classify_demand,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fallback hardcoded (usado quando DB nao retorna prompt)
# ---------------------------------------------------------------------------

_FALLBACK_SYSTEM_PROMPT = """Voce e um especialista em regularizacao ambiental rural brasileira.
Sua tarefa e classificar a demanda de um cliente rural e retornar um JSON estruturado.

Tipos de demanda validos:
- car: Cadastro Ambiental Rural
- retificacao_car: Retificacao de CAR
- licenciamento: Licenciamento Ambiental
- regularizacao_fundiaria: Regularizacao Fundiaria
- outorga: Outorga de Uso de Agua
- defesa: Defesa Administrativa / Auto de Infracao
- compensacao: Compensacao / PRAD
- exigencia_bancaria: Exigencia Bancaria / Credito Rural
- misto: Demanda Mista
- nao_identificado: Nao Identificado

Retorne APENAS um JSON valido com esta estrutura:
{
  "demand_type": "<tipo>",
  "confidence": "high" | "medium" | "low",
  "diagnosis": "<texto de 2-4 frases explicando a situacao>",
  "urgency": null | "alta" | "critica",
  "relevant_agencies": ["SEMA", "IBAMA", ...],
  "next_steps": ["passo 1", "passo 2", ...]
}"""


_FALLBACK_USER_PROMPT = """Classifique esta demanda ambiental:

DESCRICAO: {description}
CANAL: {channel}
URGENCIA INFORMADA: {urgency}

Retorne apenas o JSON."""


def _load_prompt(slug: str, db_session=None, tenant_id: Optional[int] = None) -> Optional[str]:
    """Tenta carregar prompt do banco. Retorna None se indisponivel."""
    if db_session is None:
        return None
    try:
        from app.services.prompt_service import get_active_prompt  # noqa: PLC0415
        tpl = get_active_prompt(slug, db_session, tenant_id=tenant_id)
        return tpl.content if tpl else None
    except Exception as exc:
        logger.debug("llm_classifier: falha ao carregar prompt '%s' do banco: %s", slug, exc)
        return None


def classify_demand_with_llm(
    description: str,
    process_type: Optional[str] = None,
    urgency: Optional[str] = None,
    source_channel: Optional[str] = None,
    tenant_id: Optional[int] = None,
    save_job: bool = True,
    db_session=None,
) -> tuple[DemandClassification, Optional[int]]:
    """
    Classifica demanda usando regras + LLM quando necessario.

    Retorna (DemandClassification, ai_job_id | None).
    O ai_job_id e None quando so as regras foram usadas.
    """
    # Passo 1 -- regras estaticas (sempre)
    static_result = classify_demand(description, process_type, urgency, source_channel)

    # Se ja tem alta confianca ou IA desabilitada, usar resultado das regras
    if static_result.confidence == "high" or not settings.ai_configured:
        return static_result, None

    # Passo 2 -- LLM para baixa/media confianca
    from app.core.ai_gateway import AIGatewayError, complete  # noqa: PLC0415

    # Carrega prompts do banco com fallback hardcoded
    system_prompt = (
        _load_prompt("classify_demand_system", db_session, tenant_id)
        or _FALLBACK_SYSTEM_PROMPT
    )
    user_template = (
        _load_prompt("classify_demand_user", db_session, tenant_id)
        or _FALLBACK_USER_PROMPT
    )

    prompt = user_template.format(
        description=description[:2000],
        channel=source_channel or "nao informado",
        urgency=urgency or "nao informado",
    )

    ai_job_id: Optional[int] = None
    try:
        response = complete(prompt, system=system_prompt)
        parsed = _parse_llm_response(response.content)

        if parsed and parsed.get("demand_type") in _DEMAND_RULES:
            demand_type = parsed["demand_type"]
            rules = _DEMAND_RULES[demand_type]

            enriched = DemandClassification(
                demand_type=demand_type,
                demand_label=rules["label"],
                confidence=parsed.get("confidence", "medium"),
                initial_diagnosis=parsed.get("diagnosis", rules["diagnosis"]),
                required_documents=rules["docs"],
                suggested_next_steps=parsed.get("next_steps", rules["next_steps"]),
                checklist_template_demand_type=demand_type,
                urgency_flag=parsed.get("urgency") or static_result.urgency_flag,
                relevant_agencies=parsed.get("relevant_agencies", rules["agencies"]),
            )

            if save_job and tenant_id:
                from app.models.ai_job import AIJobType  # noqa: PLC0415
                from app.services.ai_job_persistence import persist_ai_job  # noqa: PLC0415

                ai_job_id = persist_ai_job(
                    tenant_id=tenant_id,
                    job_type=AIJobType.classify_demand,
                    entity_type="classification",
                    entity_id=None,
                    input_payload={"description": description, "channel": source_channel},
                    result=parsed,
                    raw_output=response.content,
                    model_used=response.model_used,
                    provider=response.provider,
                    tokens_in=response.tokens_in,
                    tokens_out=response.tokens_out,
                    cost_usd=response.cost_usd,
                    duration_ms=response.duration_ms,
                )

            logger.info(
                "llm_classifier: LLM refinement applied demand_type=%s confidence=%s",
                demand_type, enriched.confidence,
            )
            return enriched, ai_job_id

    except AIGatewayError as exc:
        logger.warning("llm_classifier: LLM falhou, usando regras. error=%s", exc.message)
    except Exception as exc:
        logger.warning("llm_classifier: erro inesperado, usando regras. error=%s", exc)

    return static_result, None


def _parse_llm_response(content: str) -> Optional[dict]:
    """Extrai JSON da resposta do LLM (tolerante a texto ao redor)."""
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    start = content.find("{")
    end = content.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass
    logger.warning("llm_classifier: falha ao parsear JSON do LLM. content=%s", content[:200])
    return None
