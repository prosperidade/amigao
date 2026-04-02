"""
LLM Classifier — Sprint 5 (Wave 2)

Upgrade semântico do intake_classifier.py usando LLM.
Estratégia:
  1. Tenta classificação com regras estáticas (zero custo)
  2. Se confidence == "low" E IA habilitada → chama LLM para refinamento
  3. Se LLM falhar → retorna resultado das regras (degradação graciosa)

O resultado do LLM é estruturado via prompt com JSON obrigatório.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from app.core.config import settings
from app.services.intake_classifier import (
    DemandClassification,
    classify_demand,
    _DEMAND_RULES,
)

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """Você é um especialista em regularização ambiental rural brasileira.
Sua tarefa é classificar a demanda de um cliente rural e retornar um JSON estruturado.

Tipos de demanda válidos:
- car: Cadastro Ambiental Rural
- retificacao_car: Retificação de CAR
- licenciamento: Licenciamento Ambiental
- regularizacao_fundiaria: Regularização Fundiária
- outorga: Outorga de Uso de Água
- defesa: Defesa Administrativa / Auto de Infração
- compensacao: Compensação / PRAD
- exigencia_bancaria: Exigência Bancária / Crédito Rural
- misto: Demanda Mista
- nao_identificado: Não Identificado

Retorne APENAS um JSON válido com esta estrutura:
{
  "demand_type": "<tipo>",
  "confidence": "high" | "medium" | "low",
  "diagnosis": "<texto de 2-4 frases explicando a situação>",
  "urgency": null | "alta" | "critica",
  "relevant_agencies": ["SEMA", "IBAMA", ...],
  "next_steps": ["passo 1", "passo 2", ...]
}"""


_USER_PROMPT_TEMPLATE = """Classifique esta demanda ambiental:

DESCRIÇÃO: {description}
CANAL: {channel}
URGÊNCIA INFORMADA: {urgency}

Retorne apenas o JSON."""


def classify_demand_with_llm(
    description: str,
    process_type: Optional[str] = None,
    urgency: Optional[str] = None,
    source_channel: Optional[str] = None,
    tenant_id: Optional[int] = None,
    save_job: bool = True,
) -> tuple[DemandClassification, Optional[int]]:
    """
    Classifica demanda usando regras + LLM quando necessário.

    Retorna (DemandClassification, ai_job_id | None).
    O ai_job_id é None quando só as regras foram usadas.
    """
    # Passo 1 — regras estáticas (sempre)
    static_result = classify_demand(description, process_type, urgency, source_channel)

    # Se já tem alta confiança ou IA desabilitada, usar resultado das regras
    if static_result.confidence == "high" or not settings.ai_configured:
        return static_result, None

    # Passo 2 — LLM para baixa/média confiança
    from app.core.ai_gateway import complete, AIGatewayError  # noqa: PLC0415

    prompt = _USER_PROMPT_TEMPLATE.format(
        description=description[:2000],  # trunca para controlar custo
        channel=source_channel or "não informado",
        urgency=urgency or "não informado",
    )

    ai_job_id: Optional[int] = None
    try:
        response = complete(prompt, system=_SYSTEM_PROMPT)
        parsed = _parse_llm_response(response.content)

        if parsed and parsed.get("demand_type") in _DEMAND_RULES:
            # LLM retornou tipo válido — enriquecer com dados das regras
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

            if save_job:
                ai_job_id = _persist_job(
                    tenant_id=tenant_id,
                    entity_type="classification",
                    entity_id=None,
                    input_payload={"description": description, "channel": source_channel},
                    result=parsed,
                    response=response,
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
    # Tenta parse direto
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    # Tenta extrair bloco JSON
    start = content.find("{")
    end = content.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass
    logger.warning("llm_classifier: falha ao parsear JSON do LLM. content=%s", content[:200])
    return None


def _persist_job(
    *,
    tenant_id: Optional[int],
    entity_type: Optional[str],
    entity_id: Optional[int],
    input_payload: dict,
    result: dict,
    response,
) -> Optional[int]:
    """Persiste o AIJob no banco. Retorna o id ou None em caso de erro."""
    if not tenant_id:
        return None
    try:
        from datetime import datetime, timezone  # noqa: PLC0415
        from app.db.session import SessionLocal  # noqa: PLC0415
        from app.models.ai_job import AIJob, AIJobStatus, AIJobType  # noqa: PLC0415

        db = SessionLocal()
        try:
            job = AIJob(
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=entity_id,
                job_type=AIJobType.classify_demand,
                status=AIJobStatus.completed,
                model_used=response.model_used,
                provider=response.provider,
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                cost_usd=response.cost_usd,
                duration_ms=response.duration_ms,
                input_payload=input_payload,
                result=result,
                raw_output=response.content,
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            return job.id
        finally:
            db.close()
    except Exception as exc:
        logger.warning("llm_classifier: falha ao persistir AIJob: %s", exc)
        return None
