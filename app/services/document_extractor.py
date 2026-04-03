"""
Document Extractor — Sprint 5 (Wave 2) + Sprint IA-1

Extrai campos estruturados de documentos ambientais/fundiarios via LLM.
Suporta: matricula, CAR, CCIR, auto de infracao, outorga, licenca.

Prompts carregados do banco via prompt_service (com fallback hardcoded).
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fallback hardcoded (usado quando DB nao retorna prompt)
# ---------------------------------------------------------------------------

_FALLBACK_SYSTEM_PROMPT = """Voce e um especialista em documentos fundiarios e ambientais brasileiros.
Extraia os campos solicitados do texto do documento e retorne APENAS um JSON valido.
Para campos nao encontrados, use null.
Inclua um campo "confidence" por campo extraido: "high" | "medium" | "low".
"""

_FALLBACK_DOC_PROMPTS: dict[str, str] = {
    "matricula": """Extraia do texto desta matricula de imovel:
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

    "ccir": """Extraia do texto deste CCIR (Certificado de Cadastro de Imovel Rural):
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

    "auto_infracao": """Extraia do texto deste auto de infracao ambiental:
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

    "licenca": """Extraia do texto desta licenca ambiental:
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

_FALLBACK_DEFAULT_PROMPT = """Extraia os principais campos identificaveis deste documento ambiental/fundiario.
Retorne um JSON com os campos encontrados e um campo "confidence" por campo.
TEXTO DO DOCUMENTO:
{text}"""


def _load_prompt(slug: str, db_session=None, tenant_id: Optional[int] = None) -> Optional[str]:
    """Tenta carregar prompt do banco. Retorna None se indisponivel."""
    if db_session is None:
        return None
    try:
        from app.services.prompt_service import get_active_prompt  # noqa: PLC0415
        tpl = get_active_prompt(slug, db_session, tenant_id=tenant_id)
        return tpl.content if tpl else None
    except Exception as exc:
        logger.debug("document_extractor: falha ao carregar prompt '%s' do banco: %s", slug, exc)
        return None


# ---------------------------------------------------------------------------
# Funcao principal
# ---------------------------------------------------------------------------

def extract_document_fields(
    text: str,
    doc_type: str,
    *,
    document_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
    save_job: bool = True,
    db_session=None,
) -> tuple[dict, Optional[int]]:
    """
    Extrai campos estruturados de um documento via LLM.

    Retorna (campos_extraidos, ai_job_id | None).
    Retorna ({}, None) se IA nao estiver configurada.
    """
    if not settings.ai_configured:
        logger.info("document_extractor: AI desabilitada, retornando vazio")
        return {}, None

    if not text or not text.strip():
        return {}, None

    from app.core.ai_gateway import AIGatewayError, complete  # noqa: PLC0415

    # Carrega prompts do banco com fallback hardcoded
    system_prompt = (
        _load_prompt("extract_document_system", db_session, tenant_id)
        or _FALLBACK_SYSTEM_PROMPT
    )

    db_user_prompt = _load_prompt(f"extract_{doc_type}", db_session, tenant_id)
    if db_user_prompt is not None:
        prompt_template = db_user_prompt
    else:
        prompt_template = _FALLBACK_DOC_PROMPTS.get(doc_type, _FALLBACK_DEFAULT_PROMPT)

    prompt = prompt_template.replace("{text}", text[:3000])

    try:
        response = complete(prompt, system=system_prompt)
        parsed = _parse_json(response.content)

        if parsed is None:
            logger.warning("document_extractor: falha no parse JSON para doc_type=%s", doc_type)
            parsed = {"_raw": response.content[:500], "_parse_error": True}

        ai_job_id = None
        if save_job and tenant_id:
            from app.models.ai_job import AIJobType  # noqa: PLC0415
            from app.services.ai_job_persistence import persist_ai_job  # noqa: PLC0415

            ai_job_id = persist_ai_job(
                tenant_id=tenant_id,
                job_type=AIJobType.extract_document,
                entity_type="document",
                entity_id=document_id,
                input_payload={"doc_type": doc_type, "text_preview": text[:500]},
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


def supported_doc_types() -> list[str]:
    return list(_FALLBACK_DOC_PROMPTS.keys())
