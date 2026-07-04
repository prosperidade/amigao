"""Selo de 3 estados por campo (Ficha 07 §3.4/§9) — Sprint 3.

O selo é gravado no ``field_sources`` PERENE da entidade (Client/Property/
Matricula) — não no processo. O GATILHO do automatismo, porém, é contextual:
só o endpoint de processo (``POST /processes/{pid}/field-selo``) dispara a
ação de oficialização; o ``validate-fields`` do Hub segue só gravando selo.
Ver ADR-022.

Selo NUNCA trava avanço de macroetapa — é sinalização + geração de trabalho.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.matricula import Matricula
from app.models.process import Process
from app.models.property import Property
from app.services.acao_generator import generate_acao_oficializacao
from app.services.audit_hash import stamp_audit_hash
from app.services.staging_consolidation import (
    _CLIENTE_FIELDS,
    _IMOVEL_FIELDS,
    _MATRICULA_FIELDS,
)

logger = get_logger(__name__)

# Campos seláveis por entidade = allowlist da consolidação + campos do imóvel
# que existem fora do staging (matrícula-mãe e área total derivada não entram:
# total_area_ha é derivada da soma das matrículas, selo nela não faz sentido).
SELO_FIELDS: dict[str, set[str]] = {
    "cliente": set(_CLIENTE_FIELDS),
    "imovel": set(_IMOVEL_FIELDS) | {"registry_number"},
    "matricula": set(_MATRICULA_FIELDS),
}


def _resolve_entity(
    db: Session, *, tenant_id: int, process: Process, entity: str, entity_id: int
) -> Any:
    """Resolve a entidade-alvo com guard de IDOR: precisa pertencer ao tenant E
    estar ligada a ESTE processo. Qualquer falha → 404 (não vaza existência)."""
    if entity == "cliente":
        if process.client_id and process.client_id == entity_id:
            return (
                db.query(Client)
                .filter(Client.id == entity_id, Client.tenant_id == tenant_id)
                .first()
            )
        return None
    if entity == "imovel":
        if process.property_id and process.property_id == entity_id:
            return (
                db.query(Property)
                .filter(Property.id == entity_id, Property.tenant_id == tenant_id)
                .first()
            )
        return None
    if entity == "matricula":
        if not process.property_id:
            return None
        return (
            db.query(Matricula)
            .filter(
                Matricula.id == entity_id,
                Matricula.tenant_id == tenant_id,
                Matricula.property_id == process.property_id,
            )
            .first()
        )
    return None


def set_field_selo(
    db: Session,
    *,
    tenant_id: int,
    process_id: int,
    user_id: Optional[int],
    entity: str,
    entity_id: int,
    field: str,
    selo: str,
) -> dict[str, Any]:
    """Grava o selo no ``field_sources`` da entidade e, se
    ``pendente_oficializacao``, dispara a ação de oficialização no processo.

    - ``human_validated`` / ``pendente_oficializacao`` → grava a marca.
    - ``nao_validado`` → REMOVE a marca (o estado "não validado" é default por
      construção; não inventamos origem que não conhecemos mais).
    - Selo que volta a ``human_validated`` NÃO remove a ação já criada — o
      consultor dispensa/conclui (sistema não desfaz triagem humana).
    """
    process = (
        db.query(Process)
        .filter(Process.id == process_id, Process.tenant_id == tenant_id)
        .first()
    )
    if process is None:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")

    obj = _resolve_entity(
        db, tenant_id=tenant_id, process=process, entity=entity, entity_id=entity_id
    )
    if obj is None:
        raise HTTPException(
            status_code=404,
            detail=f"{entity} {entity_id} não encontrada neste processo.",
        )

    allowed = SELO_FIELDS[entity]
    if field not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Campo '{field}' não é selável em '{entity}'. Aceitos: {sorted(allowed)}",
        )

    fs_prev = dict(obj.field_sources or {})
    anterior = fs_prev.get(field)
    if selo == "nao_validado":
        fs_prev.pop(field, None)
    else:
        fs_prev[field] = selo
    obj.field_sources = fs_prev
    db.flush()

    acao = None
    criada = False
    if selo == "pendente_oficializacao":
        acao, criada = generate_acao_oficializacao(
            db,
            process=process,
            tenant_id=tenant_id,
            entity=entity,
            entity_id=entity_id,
            field=field,
        )

    log = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        entity_type="process",
        entity_id=process_id,
        action="field_selo",
        details=json.dumps(
            {
                "entity": entity,
                "entity_id": entity_id,
                "field": field,
                "selo": selo,
                "anterior": anterior,
                "acao_criada": criada,
                "acao_id": acao.id if acao else None,
            },
            ensure_ascii=False,
        ),
    )
    db.add(log)
    db.flush()
    stamp_audit_hash(db, log)
    db.commit()

    logger.info(
        "field_selo_set",
        extra={
            "process_id": process_id,
            "tenant_id": tenant_id,
            "entity": entity,
            "entity_id": entity_id,
            "field": field,
            "selo": selo,
            "acao_criada": criada,
        },
    )
    return {
        "entity": entity,
        "entity_id": entity_id,
        "field": field,
        "selo": selo,
        "field_sources": dict(obj.field_sources or {}),
        "acao_criada": criada,
        "acao_id": acao.id if acao else None,
    }
