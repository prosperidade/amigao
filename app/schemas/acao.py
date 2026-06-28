"""Schemas Pydantic da Ficha 07 — entidade ``Acao``.

Contratos de entrada/saída dos endpoints de ações (aba do caso + quadro global).
``origem_fontes`` espelha o contrato de fonte #70 (``SourceRef`` em
``stage_output.py``) — leitura **tolerante** (``list[dict]``) para nunca
derrubar a lista inteira por uma linha malformada (mesma lição do
``documentos_cruzados``: degradar com elegância).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.acao import (
    AcaoOrigem,
    AcaoPrioridade,
    AcaoStatus,
    AcaoTipoTriagem,
)

# ---------------------------------------------------------------------------
# Saída
# ---------------------------------------------------------------------------


class AcaoOut(BaseModel):
    """Saída de leitura de uma ``Acao``."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    process_id: int
    titulo: str
    descricao: str | None
    origem: AcaoOrigem
    origem_descricao: str | None
    origem_fontes: list[dict[str, Any]]
    vinculo_passivo: dict[str, Any] | None
    responsavel_id: int | None
    prazo: date | None
    prioridade: AcaoPrioridade
    status: AcaoStatus
    tipo_triagem: AcaoTipoTriagem
    created_by_user_id: int | None
    concluida_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None

    @field_validator("origem_fontes", mode="before")
    @classmethod
    def _coerce_fontes(cls, v: Any) -> Any:
        """Tolerante: garante ``list`` na leitura. ``None``/escalares viram []."""
        if v is None:
            return []
        if isinstance(v, list):
            return [item for item in v if isinstance(item, dict)]
        return []


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------


class AcaoCreate(BaseModel):
    """Criação **manual** de ação (consultor cria do zero — Ficha 07 §2).

    ``origem`` é sempre ``manual`` (servidor). ``tipo_triagem`` nasce em
    ``tarefa`` (manual já é uma decisão do consultor — não precisa triar de
    novo), mas pode ser sobrescrito. Sem responsável no MVP.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    titulo: str = Field(..., min_length=1)
    descricao: str | None = None
    prioridade: AcaoPrioridade = AcaoPrioridade.media
    prazo: date | None = None
    status: AcaoStatus = AcaoStatus.a_fazer
    tipo_triagem: AcaoTipoTriagem = AcaoTipoTriagem.tarefa
    # Vínculo opcional a um passivo já conhecido (rastreabilidade — não FK).
    vinculo_passivo: dict[str, Any] | None = None
    origem_descricao: str | None = None
    origem_fontes: list[dict[str, Any]] | None = None


class AcaoUpdate(BaseModel):
    """PATCH parcial — edita status, prazo, prioridade, título, descrição.

    ``responsavel_id`` aceito mas opcional (MVP: fica ``—``). Concluir uma ação
    (``status=concluida``) NÃO toca o passivo de origem (ADR-016).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    titulo: str | None = Field(default=None, min_length=1)
    descricao: str | None = None
    status: AcaoStatus | None = None
    prioridade: AcaoPrioridade | None = None
    prazo: date | None = None
    responsavel_id: int | None = None


class AcaoTriagemDecision(BaseModel):
    """POST de triagem — decisão do consultor (Princípio 1).

    ``tarefa`` = vira trabalho interno · ``escopo`` = candidata a item da
    proposta (apenas MARCA; não constrói o Orçamento) · ``dispensar`` =
    descarta.
    """

    model_config = ConfigDict(extra="forbid")

    decisao: Literal["tarefa", "escopo", "dispensar"]


class AcaoGenerateOut(BaseModel):
    """Resposta da geração a partir do diagnóstico."""

    created: int = Field(..., description="Quantas ações novas foram criadas")
    skipped: int = Field(..., description="Quantas já existiam (idempotência)")
    diagnosis_version: int | None = Field(
        default=None,
        description="Versão do diagnóstico que originou as ações (None = sem diagnóstico)",
    )
    acoes: list[AcaoOut] = Field(default_factory=list)
