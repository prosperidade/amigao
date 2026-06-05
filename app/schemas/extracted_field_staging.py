"""Schemas Pydantic v2 do staging de campos extraídos (Ficha 01, FASE 1).

Apenas leitura nesta fase — o staging é escrito pelos agentes (fase 2) e decidido
pelo consultor na tela de Alertas (fase 4).
"""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict

from app.models.extracted_field_staging import ExtractedFieldStatus


class ExtractedFieldStagingOut(BaseModel):
    id: int
    tenant_id: int
    process_id: Optional[int] = None
    document_id: Optional[int] = None
    source_doc_type: Optional[str] = None
    field_name: str
    field_value: Optional[Any] = None
    confidence: Optional[str] = None
    target_entity: Optional[str] = None
    target_field: Optional[str] = None
    matricula_hint: Optional[str] = None
    status: ExtractedFieldStatus
    decided_value: Optional[Any] = None
    decided_by_user_id: Optional[int] = None
    decided_at: Optional[datetime] = None
    created_by_agent: Optional[str] = None
    ai_job_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# FASE 4 — decisão do consultor + consolidação
# ---------------------------------------------------------------------------

class StagingDecisionRequest(BaseModel):
    """Decisão do consultor sobre um campo do staging (Ficha 01 §8).

    - ``aceitar``: usa o valor da fonte (proibido em ``divergente_transcricao`` —
      exige escolha ativa). ``divergente_fundo`` é aceito como achado, sem valor.
    - ``escolher_fonte``: aceita este campo como a fonte correta e rejeita os
      campos irmãos (mesmo target_field/matrícula) das outras fontes.
    - ``editar``: grava ``valor`` (obrigatório) como override manual.
    - ``rejeitar``: descarta o campo (não entra na consolidação).
    """

    acao: Literal["aceitar", "escolher_fonte", "editar", "rejeitar"]
    valor: Optional[Any] = None   # obrigatório em "editar"
    fonte: Optional[str] = None   # metadado opcional em "escolher_fonte"


class StagingDecisionResult(BaseModel):
    field_id: int
    status: ExtractedFieldStatus
    decided_value: Optional[Any] = None
    irmaos_rejeitados: list[int] = []


class BulkAcceptResult(BaseModel):
    aceitos: int
    field_ids: list[int]


class ConsolidationWrite(BaseModel):
    entity: str             # cliente | imovel | matricula
    entity_id: Optional[int] = None
    field: str
    value: Any
    staging_id: int
    created: bool = False    # True quando criou a Matrícula


class ConsolidationResult(BaseModel):
    process_id: int
    campos_gravados: int
    matriculas_criadas: int
    matriculas_atualizadas: int
    cliente_atualizado: bool
    imovel_atualizado: bool
    area_total_matriculas: Optional[float] = None
    writes: list[ConsolidationWrite] = []
    ignorados: list[str] = []   # campos aceitos sem coluna correspondente
