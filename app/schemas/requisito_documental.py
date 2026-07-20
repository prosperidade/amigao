"""DTOs dos requisitos documentais da Ficha 08 (fonte única).

O frontend consome estes campos direto: `detalhe` já vem como frase pronta e
honesta (P12), para a tela não reimplementar a redação — foi justamente a
redação duplicada em cada superfície que produziu as três respostas divergentes
do caso 15.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RequisitoDocumentalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    requisito: str = Field(description="Chave do requisito (Ficha 08 §2)")
    label: str
    status: str = Field(
        description=(
            "ausente | recebido_em_processamento | satisfeito_parcial | satisfeito"
        )
    )
    detalhe: str = Field(description="Frase pronta para o consultor — nunca diz 'ausente' com documento na base")
    document_ids: list[int] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list, description="Ficha §7.1 — sub-campos essenciais faltando")
    alertas: list[str] = Field(default_factory=list, description="Ficha §7.3 — vencimento; nunca trava")
    satisfeito_por: Optional[str] = Field(
        default=None,
        description="Ficha §7.2 — requisito equivalente que supriu este (ex.: georref embutido na matrícula)",
    )
    pendente: bool = Field(description="Conta como pendência de COLETA (só quando ausente)")


class RequisitosDocumentaisResponse(BaseModel):
    process_id: int
    requisitos: list[RequisitoDocumentalOut]
    pendentes: int = Field(description="Quantos dos 6 realmente faltam coletar")
    total: int = 6
