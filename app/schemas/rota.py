"""Schemas Pydantic da Rota Regulatória (E5, Sprint 2).

Contratos de entrada/saída dos endpoints da Rota. ``sources`` espelha o contrato
de fonte #70 (``SourceRef``) com leitura **tolerante** (``list[dict]``) — nunca
derrubar a lista por uma linha malformada (degradar com elegância).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.rota import (
    RotaPassoClassificacao,
    RotaPassoOrigem,
    RotaPassoStatus,
    RotaStatus,
)

# ---------------------------------------------------------------------------
# Saída
# ---------------------------------------------------------------------------


class RotaPassoOut(BaseModel):
    """Saída de leitura de um ``RotaPasso``."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    rota_id: int
    ordem: int
    titulo: str
    descricao: str | None
    orgao: str | None
    prazo_estimado_dias: int | None
    prazo_fonte: str | None
    sources: list[dict[str, Any]]
    norma_ref: str | None
    classificacao: RotaPassoClassificacao | None
    origem: RotaPassoOrigem
    origem_manual_nota: str | None
    status: RotaPassoStatus
    created_at: datetime | None
    updated_at: datetime | None

    @field_validator("sources", mode="before")
    @classmethod
    def _coerce_sources(cls, v: Any) -> Any:
        if v is None:
            return []
        if isinstance(v, list):
            return [item for item in v if isinstance(item, dict)]
        return []


class RotaOut(BaseModel):
    """Saída de leitura de uma ``Rota`` (com passos ordenados)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    process_id: int
    demand_type: str
    status: RotaStatus
    caminho_regulatorio: str | None
    orgao_competente: str | None
    source_ai_job_id: int | None
    validated_by: int | None
    validated_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None
    passos: list[RotaPassoOut] = Field(default_factory=list)


class RotaMaterializeOut(BaseModel):
    """Resposta da materialização (POST .../rota/gerar)."""

    created: int = Field(..., description="Passos novos criados")
    matched: int = Field(..., description="Passos que já existiam (idempotência)")
    is_diff: bool = Field(..., description="A IA trouxe diferença vs. o snapshot anterior")
    rota: RotaOut


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------


class RotaPassoCreate(BaseModel):
    """Criação **manual** de um passo (consultor adiciona — Ficha §9).

    ``origem`` é sempre ``manual`` (servidor). Ficha §9: quando o passo não tem
    base normativa nos autos, o consultor informa o fundamento/origem em
    ``origem_manual_nota`` (ex.: "orientação verbal da secretaria").
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    titulo: str = Field(..., min_length=1)
    descricao: str | None = None
    orgao: str | None = None
    prazo_estimado_dias: int | None = Field(default=None, ge=0)
    norma_ref: str | None = None
    origem_manual_nota: str | None = None
    classificacao: RotaPassoClassificacao | None = None


class RotaPassoUpdate(BaseModel):
    """PATCH parcial de um passo — título, descrição, prazo, órgão, classificação."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    titulo: str | None = Field(default=None, min_length=1)
    descricao: str | None = None
    orgao: str | None = None
    prazo_estimado_dias: int | None = Field(default=None, ge=0)
    classificacao: RotaPassoClassificacao | None = None
    origem_manual_nota: str | None = None


class RotaReorder(BaseModel):
    """PATCH de reordenação — nova ordem dos passos (lista de ids)."""

    model_config = ConfigDict(extra="forbid")

    passo_ids: list[int] = Field(..., min_length=1, description="ids dos passos na nova ordem")
