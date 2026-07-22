"""Fase 1 (N2) — Auto de infração como FATO DE PASSIVO no diagnóstico.

Spec da Isis (verbatim, campos fechados — SEM situação processual/CADIN):
número do auto, órgão autuante, autuado (nome+CPF), data da autuação, tipo de
penalidade (multa/advertência), descrição da infração, enquadramento legal
(artigo+norma), coordenadas quando presentes na descrição, valor da multa,
data de vencimento.

Diferente de `ficha01_extraction.py`: os fatos daqui NÃO passam pelo staging
cadastral (`ExtractedFieldStaging`) — não têm hint de matrícula, não são
"campo do imóvel", são evidência de passivo consumida diretamente pelo
DiagnosticoAgent via `Afirmacao`+`SourceRef` (Princípio 11). Persistidos em
`AIJob.result["auto_infracao_fato"]` do job do extrator para o documento —
sem coluna nova (Fase 1 só tem migration para a dívida #48).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from app.core.config import settings
from app.services.inconsistency_matrix import normalize_list_of_dicts

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = (
    "Voce e um especialista em fiscalizacao ambiental brasileira. Extraia EXATAMENTE "
    "os campos abaixo de um Auto de Infracao ambiental. Nao invente dado ausente - "
    "use null. Retorne APENAS JSON valido."
)

_PROMPT_TEMPLATE = """Extraia os campos abaixo deste AUTO DE INFRAÇÃO ambiental. Campos de origem
tipica (podem variar por orgao): numero/orgao no cabecalho; autuado no campo 02/03;
data da autuacao no campo 24; descricao da infracao no campo 13 (texto livre);
enquadramento legal (artigo+norma) nos campos 14-16; valor da multa no campo 19;
data de vencimento no campo 25.
{
  "numero_auto": null,
  "orgao_autuante": null,
  "autuado_nome": null,
  "autuado_cpf": null,
  "data_autuacao": null,
  "tipo_penalidade": null,
  "descricao_infracao": null,
  "enquadramento_legal": null,
  "coordenadas": null,
  "valor_multa": null,
  "data_vencimento": null,
  "confidence": {}
}
TEXTO DO DOCUMENTO:
{text}"""


def _parse_json(raw: str) -> Optional[dict[str, Any]]:
    import json

    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        logger.warning("auto_infracao_extraction: JSON invalido do LLM")
        return None


# Par lat/long simples (graus decimais, com ou sem sinal) — item 7: "par
# lat-long se parseável" na descrição livre.
_LATLONG_RE = re.compile(
    r"(-?\d{1,3}[.,]\d+)\s*[,;/]\s*(-?\d{1,3}[.,]\d+)"
)


def parse_coordenadas(texto: Optional[str]) -> Optional[tuple[float, float]]:
    """Extrai um par lat/long do texto livre da descrição, quando parseável."""
    if not texto:
        return None
    m = _LATLONG_RE.search(texto)
    if not m:
        return None
    try:
        lat = float(m.group(1).replace(",", "."))
        lon = float(m.group(2).replace(",", "."))
    except ValueError:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return (lat, lon)


def extract_auto_infracao_fato(text: str) -> Optional[dict[str, Any]]:
    """Roda 1 chamada LLM com o esqueleto do auto de infração (spec da Isis).

    Best-effort: retorna None em qualquer falha (LLM indisponível, parse).
    """
    if not settings.ai_configured or not (text or "").strip():
        return None

    from app.core.ai_gateway import AIGatewayError, complete  # noqa: PLC0415

    prompt = _PROMPT_TEMPLATE.replace("{text}", text[: settings.EXTRACTOR_MAX_CHARS])
    try:
        response = complete(prompt, system=_SYSTEM_PROMPT)
    except AIGatewayError as exc:
        logger.warning("auto_infracao_extraction: LLM falhou: %s", exc.message)
        return None
    except Exception as exc:  # pragma: no cover - defensivo
        logger.warning("auto_infracao_extraction: erro inesperado: %s", exc)
        return None

    parsed = _parse_json(response.content)
    if not parsed:
        return None

    # Coordenadas: texto livre + par lat/long parseado quando possível (item 7).
    coords_raw = parsed.get("coordenadas")
    parsed["coordenadas_latlong"] = parse_coordenadas(coords_raw) if coords_raw else None
    return parsed


# ---------------------------------------------------------------------------
# Item 8 — enquadramento legal → lookup no knowledge_catalog (mesmo caminho
# do citation_evaluator: extract_citations faz o parse regex).
# ---------------------------------------------------------------------------

def lookup_enquadramento(
    enquadramento_text: Optional[str],
    *,
    db_session,
    tenant_id: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Para cada citação encontrada no enquadramento legal, verifica se a norma
    está no `knowledge_catalog`. Retorna uma lista de
    ``{"citacao": raw, "localizada": bool, "chunk_id": int|None}``.

    Nenhum passivo sem lei, CONCRETO: norma não achada é honestamente marcada
    "não localizada no corpus" — nunca se inventa a fonte (Princípio 11).
    """
    if not (enquadramento_text or "").strip():
        return []

    from app.services.citation_evaluator import extract_citations  # noqa: PLC0415
    from app.services.knowledge_catalog import search  # noqa: PLC0415

    citations = extract_citations(enquadramento_text)
    if not citations:
        return [{"citacao": enquadramento_text.strip(), "localizada": False, "chunk_id": None}]

    results = []
    for cit in citations:
        try:
            hits = search(
                db_session, cit.raw, limit=3, tenant_id=tenant_id,
                source_type="legislation", min_similarity=0.55,
            )
        except Exception as exc:  # pragma: no cover - defensivo (RAG indisponível)
            logger.warning("auto_infracao_extraction: lookup enquadramento falhou: %s", exc)
            hits = []
        if hits:
            results.append({"citacao": cit.raw, "localizada": True, "chunk_id": hits[0].id})
        else:
            results.append({"citacao": cit.raw, "localizada": False, "chunk_id": None})
    return results


# ---------------------------------------------------------------------------
# Item 9 — cruzamento autuado × titular atual (nunca bloqueia).
# ---------------------------------------------------------------------------

def _digits(value: Optional[str]) -> str:
    return re.sub(r"\D", "", value or "")


def check_autuado_diverge_titular(
    autuado_nome: Optional[str],
    autuado_cpf: Optional[str],
    *,
    titular_nome: Optional[str] = None,
    titular_cpf: Optional[str] = None,
    matricula_proprietarios: Optional[list[dict[str, Any]]] = None,
) -> Optional[str]:
    """Compara o autuado do auto de infração contra o titular atual (Client
    do processo e/ou proprietários da Matrícula/CAR). Divergência vira NOTA
    informativa — nunca bloqueia (item 9)."""
    if not autuado_cpf and not autuado_nome:
        return None

    candidatos_cpf = {_digits(titular_cpf)} if titular_cpf else set()
    candidatos_nome = {(titular_nome or "").strip().lower()} if titular_nome else set()
    # Defesa em profundidade: a assinatura promete `list[dict]`, mas este é o
    # ponto onde o shape torto DE FATO estourou (caso 15). Uma nota informativa
    # sobre titular não pode derrubar o diagnóstico inteiro — item não-dict é
    # normalizado, não fatal.
    for p in normalize_list_of_dicts(matricula_proprietarios, item_key="nome"):
        if p.get("cpf"):
            candidatos_cpf.add(_digits(p["cpf"]))
        if p.get("nome"):
            candidatos_nome.add(str(p["nome"]).strip().lower())
    candidatos_cpf.discard("")
    candidatos_nome.discard("")

    autuado_cpf_d = _digits(autuado_cpf)
    autuado_nome_l = (autuado_nome or "").strip().lower()

    if autuado_cpf_d and candidatos_cpf:
        if autuado_cpf_d in candidatos_cpf:
            return None
        return (
            f"Autuado do auto de infração ({autuado_nome or autuado_cpf}) difere "
            "do titular atual do imóvel — confirmar se houve transferência "
            "de titularidade após a autuação."
        )
    if autuado_nome_l and candidatos_nome and autuado_nome_l not in candidatos_nome:
        return (
            f"Autuado do auto de infração ({autuado_nome}) difere do titular "
            "atual do imóvel — confirmar se houve transferência de "
            "titularidade após a autuação."
        )
    return None
