"""Schemas Pydantic v2 da Conferência por decisões (Frente G, ADR-067).

Espelham `app.services.reconciliation_decisions` (dataclasses puras) — só
serialização, nenhuma regra aqui.
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict


class ChaveNaturalOut(BaseModel):
    entidade: str
    identificador: str
    aspecto: str

    model_config = ConfigDict(from_attributes=True)


class EvidenciaOut(BaseModel):
    staging_id: Optional[int] = None
    documento_id: Optional[int] = None
    documento_tipo: Optional[str] = None
    campo: Optional[str] = None
    valor_bruto: Optional[Any] = None
    valor_normalizado: Optional[Any] = None
    unidade: Optional[str] = None
    vigencia: Optional[str] = None
    tipo_observacao: Optional[str] = None
    status: str
    fonte_autoritativa: bool = False


class DecisaoOut(BaseModel):
    chave: ChaveNaturalOut
    chave_str: str
    label: str
    evidencias: list[EvidenciaOut] = []
    concordancia: str  # concordam | divergem | fonte_unica
    nivel_divergencia: Optional[str] = None  # informativo|atencao|alto|critico
    delta: Optional[float] = None
    percentual: Optional[float] = None
    valor_proposto: Optional[Any] = None
    fonte_autoritativa_doc: Optional[str] = None
    estado: str  # pendente | decidida | parcialmente_gravada | gravada
    staging_ids: list[int] = []


class SemAgrupamentoOut(BaseModel):
    staging_id: int
    motivo: Optional[str] = None
    target_entity: Optional[str] = None
    target_field: Optional[str] = None
    field_name: Optional[str] = None


class ReconciliationOut(BaseModel):
    decisoes: list[DecisaoOut] = []
    sem_agrupamento: list[SemAgrupamentoOut] = []
    total_staging: int = 0


class DecisaoRequest(BaseModel):
    """Corpo do POST que decide uma decisão agrupada (Frente G, §11: aceite em
    bloco não implementado — só uma decisão por chamada)."""

    entidade: str
    identificador: str
    aspecto: str
    acao: Literal["aceitar", "reabrir", "escolher_fonte", "editar", "reclassificar"]
    staging_id: Optional[int] = None
    valor: Optional[Any] = None
    tipo_observacao: Optional[str] = None
