"""Schemas do selo de 3 estados (Ficha 07 §3.4) — Sprint 3.

O selo É o vocabulário de ``field_sources`` (ADR-022), não um enum de banco:

- ``human_validated``         → "Validado"
- ``pendente_oficializacao``  → "Correto, pendente de oficialização"
- ``nao_validado``            → remove a marca (volta ao default por construção:
                                raw | ai_extracted | derived_matricula | ausente)
"""

from typing import Literal

from pydantic import BaseModel, Field

SeloValue = Literal["human_validated", "pendente_oficializacao", "nao_validado"]
SeloEntity = Literal["cliente", "imovel", "matricula"]


class FieldSeloRequest(BaseModel):
    entity: SeloEntity
    entity_id: int
    field: str = Field(..., min_length=1)
    selo: SeloValue


class FieldSeloResponse(BaseModel):
    entity: SeloEntity
    entity_id: int
    field: str
    selo: SeloValue
    field_sources: dict[str, str]
    acao_criada: bool
    acao_id: int | None = None
