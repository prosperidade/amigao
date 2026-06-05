"""
Ficha 01 / FASE 4 — decisão do consultor + consolidação na base real.

Princípio: "agentes propõem (staging), consultor decide (Alertas), sistema grava
(base)". Tudo DETERMINÍSTICO (sem LLM). Nada é gravado sem decisão explícita do
consultor (status=aceito). Auditável.

- ``decide_field`` — aceitar / escolher_fonte / editar / rejeitar (1 campo).
- ``bulk_accept_consistentes`` — aceita em lote os status=consistente.
- ``consolidate_process`` — grava o staging aceito em Client/Property/Matricula.
  Idempotente; NÃO sobrescreve ``Property.total_area_ha`` (área = derivada da
  soma das matrículas, Ficha 01).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import Date, Float, Numeric
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.extracted_field_staging import (
    ExtractedFieldStaging,
    ExtractedFieldStatus,
)
from app.services.inconsistency_matrix import _to_float_br

logger = logging.getLogger(__name__)

_DIVERGENTES = {
    ExtractedFieldStatus.divergente_transcricao,
    ExtractedFieldStatus.divergente_fundo,
}


# ---------------------------------------------------------------------------
# Allowlist de colunas graváveis por entidade (+ aliases staging→coluna)
# ---------------------------------------------------------------------------
# total_area_ha NÃO está na lista do imóvel: a área do imóvel é derivada da soma
# das matrículas (Property.area_total_matriculas()) — nunca sobrescrita aqui.
_CLIENTE_FIELDS = {"full_name", "legal_name", "cpf_cnpj", "email", "phone", "secondary_phone", "birth_date"}
_CLIENTE_ALIAS = {"document": "cpf_cnpj", "address": None}

_IMOVEL_FIELDS = {"car_code", "car_status", "municipality", "state", "app_area_ha",
                  "area_grafica_ha", "area_documental_ha", "biome", "ccir", "nirf", "tipologia"}
_IMOVEL_ALIAS: dict[str, Optional[str]] = {}

_MATRICULA_FIELDS = {"numero_matricula", "cartorio", "registro_livro_folha_ficha",
                     "codigo_incra_sncr", "nirf_cib", "area_ha", "denominacao_imovel",
                     "geo_certificacao_codigo", "geo_certificacao_status",
                     "averbacao_app", "averbacao_rl", "onus_gravames", "proprietarios"}
_MATRICULA_ALIAS: dict[str, Optional[str]] = {}


def _raw_value(row: ExtractedFieldStaging) -> Any:
    """Valor efetivo da decisão: decided_value se houver, senão a fonte."""
    src = row.decided_value if row.decided_value is not None else row.field_value
    if isinstance(src, dict) and "value" in src:
        return src["value"]
    return src


def _coerce(value: Any, column_type: Any) -> Any:
    """Coage o valor para o tipo da coluna (área PT-BR → float, data → date)."""
    if value is None:
        return None
    if isinstance(column_type, (Float, Numeric)):
        return _to_float_br(value)
    if isinstance(column_type, Date):
        if isinstance(value, (date, datetime)):
            return value if isinstance(value, date) else value.date()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(str(value).strip(), fmt).date()
            except ValueError:
                continue
        return None
    return value


# ---------------------------------------------------------------------------
# Decisão por campo
# ---------------------------------------------------------------------------

def decide_field(
    db: Session, *, tenant_id: int, process_id: int, field_id: int,
    acao: str, valor: Any = None, fonte: Optional[str] = None, user_id: Optional[int] = None,
) -> ExtractedFieldStaging:
    row = (
        db.query(ExtractedFieldStaging)
        .filter(
            ExtractedFieldStaging.id == field_id,
            ExtractedFieldStaging.tenant_id == tenant_id,
            ExtractedFieldStaging.process_id == process_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Campo de staging não encontrado.")

    irmaos: list[int] = []
    if acao == "rejeitar":
        row.status = ExtractedFieldStatus.rejeitado
        row.decided_value = None
    elif acao == "editar":
        if valor is None:
            raise HTTPException(status_code=422, detail="'valor' é obrigatório na ação 'editar'.")
        row.status = ExtractedFieldStatus.aceito
        row.decided_value = {"value": valor}
    elif acao == "aceitar":
        # Gate: divergente_transcricao exige escolha ativa (escolher_fonte/editar).
        if row.status == ExtractedFieldStatus.divergente_transcricao:
            raise HTTPException(
                status_code=422,
                detail="Campo divergente (transcrição) exige 'escolher_fonte' ou 'editar', não 'aceitar'.",
            )
        row.status = ExtractedFieldStatus.aceito
        # divergente_fundo é aceito como ACHADO (issue/escopo já roteado pela
        # matriz) — sem gravação automática de valor.
        row.decided_value = None if row.status == ExtractedFieldStatus.divergente_fundo else {"value": _raw_value(row)}
    elif acao == "escolher_fonte":
        row.status = ExtractedFieldStatus.aceito
        row.decided_value = {"value": _raw_value(row)}
        irmaos = _reject_siblings(db, tenant_id, process_id, row)
    else:
        raise HTTPException(status_code=422, detail=f"Ação desconhecida: {acao}")

    row.decided_by_user_id = user_id
    row.decided_at = datetime.now(UTC)
    db.flush()

    _audit(db, tenant_id, process_id, user_id, "staging_decidir", {
        "field_id": row.id, "acao": acao, "status": row.status.value,
        "target_entity": row.target_entity, "target_field": row.target_field,
        "matricula_hint": row.matricula_hint, "fonte": fonte,
        "irmaos_rejeitados": irmaos, "staging_origin_ai_job_id": row.ai_job_id,
    })
    db.commit()
    return row


def _reject_siblings(db: Session, tenant_id: int, process_id: int, row: ExtractedFieldStaging) -> list[int]:
    """Rejeita campos irmãos (mesmo destino) de outras fontes — 'escolher a fonte'."""
    q = (
        db.query(ExtractedFieldStaging)
        .filter(
            ExtractedFieldStaging.tenant_id == tenant_id,
            ExtractedFieldStaging.process_id == process_id,
            ExtractedFieldStaging.id != row.id,
            ExtractedFieldStaging.target_entity == row.target_entity,
            ExtractedFieldStaging.target_field == row.target_field,
        )
    )
    if row.matricula_hint is None:
        q = q.filter(ExtractedFieldStaging.matricula_hint.is_(None))
    else:
        q = q.filter(ExtractedFieldStaging.matricula_hint == row.matricula_hint)

    rejeitados: list[int] = []
    for sib in q.all():
        if sib.status in (ExtractedFieldStatus.aceito,):
            continue
        sib.status = ExtractedFieldStatus.rejeitado
        rejeitados.append(sib.id)
    return rejeitados


def bulk_accept_consistentes(
    db: Session, *, tenant_id: int, process_id: int, user_id: Optional[int] = None,
) -> list[int]:
    """Aceita em lote TODOS os campos status=consistente. Divergentes NUNCA entram
    no lote (exigem escolha ativa)."""
    rows = (
        db.query(ExtractedFieldStaging)
        .filter(
            ExtractedFieldStaging.tenant_id == tenant_id,
            ExtractedFieldStaging.process_id == process_id,
            ExtractedFieldStaging.status == ExtractedFieldStatus.consistente,
        )
        .all()
    )
    ids: list[int] = []
    now = datetime.now(UTC)
    for row in rows:
        row.status = ExtractedFieldStatus.aceito
        row.decided_value = {"value": _raw_value(row)}
        row.decided_by_user_id = user_id
        row.decided_at = now
        ids.append(row.id)
    db.flush()
    if ids:
        _audit(db, tenant_id, process_id, user_id, "staging_aceitar_consistentes",
               {"field_ids": ids, "count": len(ids)})
    db.commit()
    return ids


# ---------------------------------------------------------------------------
# Consolidação na base real
# ---------------------------------------------------------------------------

def consolidate_process(
    db: Session, *, tenant_id: int, process_id: int, user_id: Optional[int] = None,
) -> dict[str, Any]:
    from app.models.process import Process  # noqa: PLC0415

    process = (
        db.query(Process)
        .filter(Process.id == process_id, Process.tenant_id == tenant_id)
        .first()
    )
    if process is None:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")

    accepted = (
        db.query(ExtractedFieldStaging)
        .filter(
            ExtractedFieldStaging.tenant_id == tenant_id,
            ExtractedFieldStaging.process_id == process_id,
            ExtractedFieldStaging.status == ExtractedFieldStatus.aceito,
        )
        .order_by(ExtractedFieldStaging.id.asc())
        .all()
    )

    writes: list[dict[str, Any]] = []
    ignorados: list[str] = []
    cliente_tocado = False
    imovel_tocado = False
    mat_criadas = 0
    mat_atualizadas = 0

    client = _load_client(db, tenant_id, process.client_id) if process.client_id else None
    prop = _load_property(db, tenant_id, process.property_id) if process.property_id else None

    # cache de matrículas por hint (upsert idempotente)
    mat_cache: dict[str, tuple[Any, bool]] = {}

    for row in accepted:
        value = _raw_value(row)
        if value is None:
            continue
        entity = (row.target_entity or "").lower()

        if entity == "cliente" and client is not None:
            if _write_entity(client, row, value, _CLIENTE_FIELDS, _CLIENTE_ALIAS, writes, ignorados):
                cliente_tocado = True
        elif entity == "imovel" and prop is not None:
            if _write_entity(prop, row, value, _IMOVEL_FIELDS, _IMOVEL_ALIAS, writes, ignorados):
                imovel_tocado = True
        elif entity == "matricula" and prop is not None:
            hint = row.matricula_hint
            if not hint:
                ignorados.append(f"matricula sem matricula_hint: {row.target_field}")
                continue
            if hint not in mat_cache:
                mat, created = _upsert_matricula(db, tenant_id, prop.id, hint)
                mat_cache[hint] = (mat, created)
                if created:
                    mat_criadas += 1
                else:
                    mat_atualizadas += 1
            mat, _created = mat_cache[hint]
            # matricula_listada não escreve coluna (só estabelece a matrícula).
            if row.field_name != "matricula_listada":
                _write_entity(mat, row, value, _MATRICULA_FIELDS, _MATRICULA_ALIAS, writes, ignorados)
        else:
            ignorados.append(f"{entity or '—'}: sem destino (target_field={row.target_field})")

    db.flush()

    area_total = prop.area_total_matriculas() if prop is not None else None

    if writes:
        _audit(db, tenant_id, process_id, user_id, "consolidar", {
            "process_id": process_id, "campos_gravados": len(writes),
            "matriculas_criadas": mat_criadas, "matriculas_atualizadas": mat_atualizadas,
            "writes": writes,
        })
    db.commit()

    return {
        "process_id": process_id,
        "campos_gravados": len(writes),
        "matriculas_criadas": mat_criadas,
        "matriculas_atualizadas": mat_atualizadas,
        "cliente_atualizado": cliente_tocado,
        "imovel_atualizado": imovel_tocado,
        "area_total_matriculas": area_total,
        "writes": writes,
        "ignorados": ignorados,
    }


def _write_entity(
    obj: Any, row: ExtractedFieldStaging, value: Any,
    allowed: set[str], alias: dict[str, Optional[str]],
    writes: list[dict[str, Any]], ignorados: list[str],
) -> bool:
    """Grava 1 campo no objeto ORM, respeitando allowlist + alias + tipo. Marca
    a proveniência em ``field_sources`` quando o modelo tiver a coluna."""
    target = row.target_field or ""
    col = alias.get(target, target) if target in alias else target
    if col is None:
        ignorados.append(f"{row.target_entity}.{target} (sem coluna na base)")
        return False
    if col not in allowed or col not in obj.__table__.columns:
        ignorados.append(f"{row.target_entity}.{target}")
        return False

    coerced = _coerce(value, obj.__table__.columns[col].type)
    if coerced is None:
        ignorados.append(f"{row.target_entity}.{col} (valor incoercível)")
        return False

    setattr(obj, col, coerced)
    # proveniência por campo (padrão field_sources)
    if "field_sources" in obj.__table__.columns:
        fs = dict(getattr(obj, "field_sources", None) or {})
        fs[col] = "human_validated"
        obj.field_sources = fs
    writes.append({
        "entity": row.target_entity, "entity_id": getattr(obj, "id", None),
        "field": col, "value": coerced if not isinstance(coerced, date) else coerced.isoformat(),
        "staging_id": row.id, "created": False,
    })
    return True


def _upsert_matricula(db: Session, tenant_id: int, property_id: int, hint: str):
    from app.models.matricula import Matricula  # noqa: PLC0415

    mat = (
        db.query(Matricula)
        .filter(
            Matricula.tenant_id == tenant_id,
            Matricula.property_id == property_id,
            Matricula.numero_matricula == hint,
        )
        .first()
    )
    if mat is not None:
        return mat, False
    mat = Matricula(tenant_id=tenant_id, property_id=property_id, numero_matricula=hint)
    db.add(mat)
    db.flush()
    return mat, True


def _load_client(db: Session, tenant_id: int, client_id: int):
    from app.models.client import Client  # noqa: PLC0415
    return db.query(Client).filter(Client.id == client_id, Client.tenant_id == tenant_id).first()


def _load_property(db: Session, tenant_id: int, property_id: int):
    from app.models.property import Property  # noqa: PLC0415
    return db.query(Property).filter(Property.id == property_id, Property.tenant_id == tenant_id).first()


def _audit(db: Session, tenant_id: int, process_id: int, user_id: Optional[int],
           action: str, details: dict[str, Any]) -> None:
    db.add(AuditLog(
        tenant_id=tenant_id, user_id=user_id, entity_type="process",
        entity_id=process_id, action=action,
        details=json.dumps(details, ensure_ascii=False, default=str),
    ))
