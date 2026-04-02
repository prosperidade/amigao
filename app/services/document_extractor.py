"""
Document Extractor — Sprint 5 (Wave 2)

Extrai campos estruturados de documentos ambientais/fundiários via LLM.
Suporta: matrícula, CAR, CCIR, auto de infração, outorga, licença.

Workflow:
  1. Recebe texto do documento (via OCR futuro ou paste manual)
  2. Envia ao LLM com prompt específico por tipo de documento
  3. Retorna dict com campos extraídos + confiança por campo
  4. Persiste AIJob para auditoria e custo
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompts por tipo de documento
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_EXTRACTOR = """Você é um especialista em documentos fundiários e ambientais brasileiros.
Extraia os campos solicitados do texto do documento e retorne APENAS um JSON válido.
Para campos não encontrados, use null.
Inclua um campo "confidence" por campo extraído: "high" | "medium" | "low".
"""

_DOC_PROMPTS: dict[str, str] = {
    "matricula": """Extraia do texto desta matrícula de imóvel:
{
  "numero_matricula": null,
  "cartorio": null,
  "comarca": null,
  "uf": null,
  "proprietario_nome": null,
  "proprietario_cpf_cnpj": null,
  "area_hectares": null,
  "denominacao_imovel": null,
  "municipio": null,
  "descricao_limites": null,
  "data_registro": null,
  "confidence": {}
}
TEXTO DO DOCUMENTO:
{text}""",

    "car": """Extraia do texto deste documento do CAR (Cadastro Ambiental Rural):
{
  "numero_car": null,
  "situacao": null,
  "cpf_cnpj_proprietario": null,
  "nome_proprietario": null,
  "denominacao_imovel": null,
  "municipio": null,
  "uf": null,
  "area_total_ha": null,
  "area_app_ha": null,
  "area_reserva_legal_ha": null,
  "data_inscricao": null,
  "pendencias": null,
  "confidence": {}
}
TEXTO DO DOCUMENTO:
{text}""",

    "ccir": """Extraia do texto deste CCIR (Certificado de Cadastro de Imóvel Rural):
{
  "numero_ccir": null,
  "nirf": null,
  "denominacao_imovel": null,
  "municipio": null,
  "uf": null,
  "area_total_ha": null,
  "fracao_minima_ha": null,
  "proprietario_nome": null,
  "proprietario_cpf_cnpj": null,
  "data_emissao": null,
  "confidence": {}
}
TEXTO DO DOCUMENTO:
{text}""",

    "auto_infracao": """Extraia do texto deste auto de infração ambiental:
{
  "numero_auto": null,
  "orgao_autuante": null,
  "data_autuacao": null,
  "infrator_nome": null,
  "infrator_cpf_cnpj": null,
  "artigo_infringido": null,
  "descricao_infracao": null,
  "valor_multa": null,
  "prazo_defesa_dias": null,
  "embargo": null,
  "municipio": null,
  "uf": null,
  "confidence": {}
}
TEXTO DO DOCUMENTO:
{text}""",

    "licenca": """Extraia do texto desta licença ambiental:
{
  "numero_licenca": null,
  "tipo_licenca": null,
  "orgao_emissor": null,
  "empreendimento": null,
  "cnpj_empreendimento": null,
  "atividade": null,
  "municipio": null,
  "uf": null,
  "data_emissao": null,
  "data_validade": null,
  "condicionantes_count": null,
  "confidence": {}
}
TEXTO DO DOCUMENTO:
{text}""",
}

_DEFAULT_PROMPT = """Extraia os principais campos identificáveis deste documento ambiental/fundiário.
Retorne um JSON com os campos encontrados e um campo "confidence" por campo.
TEXTO DO DOCUMENTO:
{text}"""


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def extract_document_fields(
    text: str,
    doc_type: str,
    *,
    document_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
    save_job: bool = True,
) -> tuple[dict, Optional[int]]:
    """
    Extrai campos estruturados de um documento via LLM.

    Parâmetros:
        text        : texto do documento (OCR ou digitado)
        doc_type    : tipo do documento (matricula, car, ccir, auto_infracao, licenca, ...)
        document_id : ID do documento no banco para vincular o job
        tenant_id   : tenant para auditoria de custo
        save_job    : se deve persistir o AIJob no banco

    Retorna (campos_extraídos, ai_job_id | None).
    Retorna ({}, None) se IA não estiver configurada.
    """
    if not settings.ai_configured:
        logger.info("document_extractor: AI desabilitada, retornando vazio")
        return {}, None

    if not text or not text.strip():
        return {}, None

    from app.core.ai_gateway import complete, AIGatewayError  # noqa: PLC0415

    prompt_template = _DOC_PROMPTS.get(doc_type, _DEFAULT_PROMPT)
    prompt = prompt_template.format(text=text[:3000])  # trunca para controle de custo

    try:
        response = complete(prompt, system=_SYSTEM_PROMPT_EXTRACTOR)
        parsed = _parse_json(response.content)

        if parsed is None:
            logger.warning("document_extractor: falha no parse JSON para doc_type=%s", doc_type)
            parsed = {"_raw": response.content[:500], "_parse_error": True}

        ai_job_id = None
        if save_job and tenant_id:
            ai_job_id = _persist_job(
                tenant_id=tenant_id,
                document_id=document_id,
                doc_type=doc_type,
                input_text=text[:500],
                result=parsed,
                response=response,
            )

        logger.info(
            "document_extractor: extracted doc_type=%s fields=%d job_id=%s",
            doc_type, len(parsed), ai_job_id,
        )
        return parsed, ai_job_id

    except AIGatewayError as exc:
        logger.warning("document_extractor: LLM falhou. error=%s", exc.message)
        return {}, None
    except Exception as exc:
        logger.warning("document_extractor: erro inesperado. error=%s", exc)
        return {}, None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json(content: str) -> Optional[dict]:
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
    return None


def _persist_job(
    *,
    tenant_id: int,
    document_id: Optional[int],
    doc_type: str,
    input_text: str,
    result: dict,
    response,
) -> Optional[int]:
    try:
        from datetime import datetime, timezone  # noqa: PLC0415
        from app.db.session import SessionLocal  # noqa: PLC0415
        from app.models.ai_job import AIJob, AIJobStatus, AIJobType  # noqa: PLC0415

        db = SessionLocal()
        try:
            job = AIJob(
                tenant_id=tenant_id,
                entity_type="document",
                entity_id=document_id,
                job_type=AIJobType.extract_document,
                status=AIJobStatus.completed,
                model_used=response.model_used,
                provider=response.provider,
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                cost_usd=response.cost_usd,
                duration_ms=response.duration_ms,
                input_payload={"doc_type": doc_type, "text_preview": input_text},
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
        logger.warning("document_extractor: falha ao persistir AIJob: %s", exc)
        return None


def supported_doc_types() -> list[str]:
    return list(_DOC_PROMPTS.keys())
