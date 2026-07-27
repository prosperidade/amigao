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
    # Item 6 (pós-teste Isis): aceite que não vai pousar na base fica visível de
    # forma DURÁVEL — não só na caixa efêmera do pós-consolidação. Computado a
    # cada GET (flag_sem_casa), nunca gravado.
    sem_casa: bool = False
    sem_casa_motivo: Optional[str] = None
    # Nome do documento de origem (26/07). A Conferência agrupava TODAS as linhas
    # sem `matricula_hint` num único quadro "Matrícula" — no caso 15 isso juntou
    # 15 linhas de 3 documentos diferentes (2 ITRs + um contrato), e o mesmo campo
    # aparecia três vezes sem dizer de onde vinha. Resolvido no read-time.
    source_doc_nome: Optional[str] = None

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
    - ``criar_acao``: 3º caminho explícito da divergência (Ficha 07 §3.3) — só
      em ``divergente_transcricao``. Cria a Ação AGORA (mesmo gerador que a
      Consolidação roda automaticamente); o campo continua divergente, a
      decisão do consultor foi "virar trabalho rastreável", não "resolver".
    - ``reabrir``: devolve o campo a PENDENTE, desfazendo a decisão anterior.
      Pré-requisito da re-decisão: no caso 15 o consultor decidiu com a tela
      cega (sem o confronto 2923×4698) e precisa poder decidir de novo com a
      tela honesta. O valor anterior vai para a auditoria — reabrir não apaga
      história, acrescenta.
    """

    acao: Literal[
        "aceitar", "escolher_fonte", "editar", "rejeitar", "criar_acao", "reabrir"
    ]
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
    anterior: Any = None     # valor antes da gravação (versão anterior)
    novo: Any = None         # valor gravado
    fonte: Optional[str] = None  # sigef | ccir | matricula | consultor | …
    staging_id: int


class ConsolidationReconciliation(BaseModel):
    """Campo já consolidado cujo doc novo trouxe valor divergente — NÃO sobrescrito;
    volta como alerta para o consultor decidir (Ficha 05)."""
    entity: str
    entity_id: Optional[int] = None
    field: str
    anterior: Any = None
    novo: Any = None
    fonte: Optional[str] = None
    staging_id: int


class ConsolidationDivergenciaDevolvida(BaseModel):
    """Grupo aceito com valores conflitantes de docs distintos (Sprint 4): a
    consolidação NÃO desempata conteúdo — devolve a `divergente_transcricao`
    para o consultor decidir (Ficha §3.3); a divergência vira Ação."""
    entity: str
    matricula_hint: Optional[str] = None
    field: str
    valores: list[Any] = []
    staging_ids: list[int] = []


class ConsolidationResult(BaseModel):
    process_id: int
    campos_gravados: int
    matriculas_criadas: int
    matriculas_atualizadas: int
    cliente_atualizado: bool
    imovel_atualizado: bool
    area_total_matriculas: Optional[float] = None
    # Sprint 4 (Ficha 07 §9): ressalva quando a soma cobre matrículas não
    # declaradas contíguas — anotada, nunca suprimida.
    area_total_nota: Optional[str] = None
    acoes_criadas: int = 0   # divergências não resolvidas que viraram Ação (opção b)
    # Forense caso Isis: matrículas desativadas/reativadas na Conferência (rejeitar
    # staging desfaz a materialização e tira da soma; reaceitar reativa).
    matriculas_desativadas: list[dict[str, Any]] = []
    matriculas_reativadas: list[dict[str, Any]] = []
    writes: list[ConsolidationWrite] = []
    ignorados: list[str] = []   # campos aceitos sem coluna correspondente
    reconciliacoes: list[ConsolidationReconciliation] = []
    divergencias_devolvidas: list[ConsolidationDivergenciaDevolvida] = []
