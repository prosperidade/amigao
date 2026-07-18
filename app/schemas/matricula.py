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
    # Cadeia de fichas (#60) — sinais registrais da linhagem (opcionais no cadastro).
    registro_anterior: Optional[str] = None
    denominacao_anterior: Optional[str] = None


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
    # Vigência da cadeia (#60): 'vigente' soma/gera lacuna; 'historica' é linhagem.
    vigencia: str = "vigente"
    superseded_by_id: Optional[int] = None
    deactivated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Cadeia de fichas (Dívida #60) — detecção + curadoria de vigência
# ---------------------------------------------------------------------------

class ChainProposalOut(BaseModel):
    """Proposta de cadeia: ``anterior`` é ficha anterior de ``vigente`` (#60).

    Exibida PRÉ-MARCADA na Conferência; 1 clique confirma. Nada muda sem o
    aceite do consultor (IA propõe, humano decide)."""

    anterior_id: int
    anterior_numero: Optional[str] = None
    vigente_id: int
    vigente_numero: Optional[str] = None
    sinal: str            # registro_anterior | denominacao_area | lote_area
    confianca: str        # alta | media | baixa
    evidencia: str


class ChainPair(BaseModel):
    anterior_id: int
    vigente_id: int


class ChainApplyRequest(BaseModel):
    """1 clique confirma a cadeia inteira: cada par (anterior→vigente) marca a
    anterior como histórica, encadeada à vigente."""

    pairs: list[ChainPair]


class ChainApplyResult(BaseModel):
    aplicadas: list[dict[str, Any]] = []
    count: int = 0


class VigenciaRequest(BaseModel):
    """Ajuste manual/reversão de vigência de UMA matrícula (em Dados).

    ``vigente`` volta a somar (limpa o encadeamento); ``historica`` exige a
    vigente que a substitui (``superseded_by_id``)."""

    vigencia: str                                # vigente | historica
    superseded_by_id: Optional[int] = None
