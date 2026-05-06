"""
intake_enrichment — auto-fill de Property/Client a partir das extrações IA do Intake.

Sprint V (A1) da auditoria 2026-04-29 — destrava o ponto crítico #7:
"Cliente Hub e Imóvel Hub precisam ser alimentados automaticamente".

Após `commit_draft` migrar os documentos do rascunho pro processo recém-criado,
este módulo:

1. Coleta os AIJobs do agente `extrator` (status=completed) para os documentos
   do draft, mantendo o mais recente por documento (mesma lógica de
   `get_draft_extraction_results`).
2. Agrega os campos extraídos com prioridade "primeiro valor não-vazio vence"
   (alinhado com a UI de sugestões do wizard).
3. Mapeia as chaves do extrator para colunas concretas de Property e Client.
4. Preenche **apenas campos vazios** — nunca sobrescreve valor já presente,
   nem mesmo se a origem anterior for `ai_extracted`. Isso protege qualquer
   ajuste manual feito pelo consultor entre o upload e o commit.
5. Marca cada campo auto-preenchido em `Property.field_sources[field] =
   "ai_extracted"` para que a UI possa exibir o badge de origem (F2).

A função NÃO faz commit — o caller (commit_draft) controla a transação.
Falhas no enrichment não devem bloquear o commit do caso, então tratamos
exceções localmente e logamos.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# Chaves do extrator → colunas de Property. Ordem é a prioridade de fallback
# (primeira chave não-vazia vence).
_PROPERTY_KEY_MAP: dict[str, list[str]] = {
    "registry_number": ["numero_matricula"],
    "car_code": ["numero_car"],
    "ccir": ["numero_ccir"],
    "nirf": ["nirf"],
    "total_area_ha": ["area_hectares", "area_total_ha"],
    "app_area_ha": ["area_app_ha"],
    "municipality": ["municipio"],
    "state": ["uf"],
}

_CLIENT_KEY_MAP: dict[str, list[str]] = {
    # 3 fontes possíveis: matrícula/CCIR usam proprietario_cpf_cnpj,
    # CAR usa cpf_cnpj_proprietario, auto de infração usa infrator_cpf_cnpj.
    "cpf_cnpj": [
        "proprietario_cpf_cnpj",
        "cpf_cnpj_proprietario",
        "infrator_cpf_cnpj",
    ],
}


def _parse_area_ha(value: Any) -> float | None:
    """Tenta parsear valor de área em hectares.

    Aceita number direto, "1.234,56" (BR), "1234.56", "1234,56", "1.234".
    Retorna None se não conseguir.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    # Remove sufixos comuns
    s = re.sub(r"\s*(ha|hec(tares)?)\s*$", "", s, flags=re.IGNORECASE).strip()
    # Heurística pro formato BR vs US
    if "," in s and "." in s:
        # "1.234,56" → ponto é milhar, vírgula é decimal
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        f = float(s)
        return f if f > 0 else None
    except ValueError:
        return None


def _normalize_uf(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    uf = value.strip().upper()
    return uf if len(uf) == 2 and uf.isalpha() else None


def _aggregate_suggestions(db: Session, *, draft_id: int, tenant_id: int) -> dict[str, Any]:
    """Replica a agregação 'primeiro valor não-vazio vence' do endpoint
    `get_draft_extraction_results`. Retorna {field: value}.
    """
    from app.models.ai_job import AIJob, AIJobStatus  # noqa: PLC0415
    from app.models.document import Document  # noqa: PLC0415

    docs = (
        db.query(Document)
        .filter(
            Document.intake_draft_id == draft_id,
            Document.tenant_id == tenant_id,
            Document.deleted_at.is_(None),
        )
        .all()
    )
    doc_ids = {d.id for d in docs}
    if not doc_ids:
        return {}

    jobs = (
        db.query(AIJob)
        .filter(
            AIJob.tenant_id == tenant_id,
            AIJob.agent_name == "extrator",
            AIJob.status == AIJobStatus.completed,
        )
        .order_by(AIJob.finished_at.desc().nullslast(), AIJob.id.desc())
        .all()
    )

    latest_by_doc: dict[int, AIJob] = {}
    for j in jobs:
        try:
            doc_id = (j.result or {}).get("document_id")
        except AttributeError:
            continue
        if isinstance(doc_id, int) and doc_id in doc_ids and doc_id not in latest_by_doc:
            latest_by_doc[doc_id] = j

    suggestions: dict[str, Any] = {}
    for j in latest_by_doc.values():
        fields = (j.result or {}).get("extracted_fields") or {}
        for k, v in fields.items():
            if v in (None, "", [], {}):
                continue
            if k not in suggestions:
                suggestions[k] = v
    return suggestions


def _coerce(field: str, value: Any) -> Any:
    """Coerção por campo de destino."""
    if field in ("total_area_ha", "app_area_ha"):
        return _parse_area_ha(value)
    if field == "state":
        return _normalize_uf(value)
    if isinstance(value, str):
        v = value.strip()
        return v or None
    return value


def enrich_from_intake_extraction(
    db: Session,
    *,
    draft_id: int,
    process_id: int | None,
    client_id: int | None,
    property_id: int | None,
    tenant_id: int,
) -> dict[str, list[str]]:
    """Aplica sugestões da extração do Intake em Property/Client.

    Retorna {"property": [campos preenchidos], "client": [campos preenchidos]}.
    Em caso de falha, loga e retorna dict vazio (não interrompe commit).
    """
    filled: dict[str, list[str]] = {"property": [], "client": []}

    try:
        suggestions = _aggregate_suggestions(db, draft_id=draft_id, tenant_id=tenant_id)
    except Exception as exc:
        logger.warning("intake_enrichment: falha ao agregar sugestões: %s", exc)
        return filled

    if not suggestions:
        return filled

    # --- Property ---
    if property_id:
        from app.models.property import Property  # noqa: PLC0415

        prop = (
            db.query(Property)
            .filter(Property.id == property_id, Property.tenant_id == tenant_id)
            .first()
        )
        if prop:
            sources = dict(prop.field_sources or {})
            for col, candidates in _PROPERTY_KEY_MAP.items():
                current = getattr(prop, col, None)
                if current not in (None, "", 0, 0.0):
                    continue
                raw_val = next(
                    (suggestions[k] for k in candidates if k in suggestions),
                    None,
                )
                if raw_val is None:
                    continue
                coerced = _coerce(col, raw_val)
                if coerced in (None, "", 0, 0.0):
                    continue
                setattr(prop, col, coerced)
                sources[col] = "ai_extracted"
                filled["property"].append(col)
            if filled["property"]:
                prop.field_sources = sources

    # --- Client ---
    if client_id:
        from app.models.client import Client  # noqa: PLC0415

        cli = (
            db.query(Client)
            .filter(Client.id == client_id, Client.tenant_id == tenant_id)
            .first()
        )
        if cli:
            client_sources = dict(getattr(cli, "field_sources", None) or {})
            for col, candidates in _CLIENT_KEY_MAP.items():
                current = getattr(cli, col, None)
                if current not in (None, ""):
                    continue
                raw_val = next(
                    (suggestions[k] for k in candidates if k in suggestions),
                    None,
                )
                if raw_val is None:
                    continue
                coerced = _coerce(col, raw_val)
                if coerced in (None, ""):
                    continue
                setattr(cli, col, coerced)
                client_sources[col] = "ai_extracted"
                filled["client"].append(col)
            if filled["client"]:
                cli.field_sources = client_sources

    if filled["property"] or filled["client"]:
        logger.info(
            "intake_enrichment: draft=%s process=%s prop=%s client=%s "
            "property_filled=%s client_filled=%s",
            draft_id, process_id, property_id, client_id,
            filled["property"], filled["client"],
        )
    return filled
