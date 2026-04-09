"""Schemas para resultado do enquadramento regulatorio."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class EtapaRegulatoria(BaseModel):
    ordem: int
    titulo: str
    descricao: str
    prazo_estimado_dias: Optional[int] = None
    orgao: Optional[str] = None
    dependencia: Optional[str] = None


class LegislacaoCitada(BaseModel):
    identificador: str  # "Lei 12.651/2012, Art. 12"
    titulo: str
    relevancia: str  # breve explicacao de por que se aplica


class RiscoIdentificado(BaseModel):
    descricao: str
    severidade: str  # baixo, medio, alto, critico
    mitigacao: Optional[str] = None


class PrazosEstimados(BaseModel):
    total_dias: Optional[int] = None
    fase_documental_dias: Optional[int] = None
    fase_protocolo_dias: Optional[int] = None
    fase_analise_orgao_dias: Optional[int] = None


class EnquadramentoResult(BaseModel):
    caminho_regulatorio: str  # ex: "Licenciamento Ambiental Simplificado via SEMA-MT"
    orgao_competente: str
    etapas: list[EtapaRegulatoria]
    legislacao_aplicavel: list[LegislacaoCitada]
    riscos: list[RiscoIdentificado]
    documentos_necessarios: list[str]
    prazos_estimados: PrazosEstimados
    confianca: str  # baixa, media, alta
    justificativa: str  # raciocinio completo do agente
    recomendacoes: list[str] = []
