"""Schemas Pydantic v2 da Matrícula (Ficha 01, FASE 1)."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class MatriculaBase(BaseModel):
    numero_matricula: Optional[str] = None
    cartorio: Optional[str] = None
    registro_livro_folha_ficha: Optional[str] = None
    codigo_incra_sncr: Optional[str] = None
    nirf_cib: Optional[str] = None
    area_ha: Optional[float] = None
    denominacao_imovel: Optional[str] = None
    geo_certificacao_codigo: Optional[str] = None
    geo_certificacao_status: Optional[str] = None
    averbacao_app: Optional[str] = None
    averbacao_rl: Optional[str] = None
    onus_gravames: Optional[str] = None
    proprietarios: Optional[list[dict[str, Any]]] = None


class MatriculaCreate(MatriculaBase):
    """Criação manual (a Isis cadastra as matrículas à mão até a fase 2 extrair).

    ``property_id``/``tenant_id`` vêm do path + JWT, não do corpo.
    """


class MatriculaUpdate(MatriculaBase):
    pass


class MatriculaMoveRequest(BaseModel):
    """Re-home (Sprint 4 / Ficha 07 §9): mover a matrícula para outro imóvel.

    Caminho mínimo para "matrículas não contíguas → tratadas separadamente":
    o consultor cadastra outro imóvel e move as matrículas do grupo. Só o
    destino é editável; tenant vem do JWT, origem vem do path.
    """

    property_id: int


class Matricula(MatriculaBase):
    id: int
    tenant_id: int
    property_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
