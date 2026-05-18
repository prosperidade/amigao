"""Schemas Pydantic v2 para o conteúdo do ``StageOutput.content_data`` (JSONB).

Sprint A1 (Tarefa C) — fecha o gap B2 do audit ("StageOutput sem schema
obrigatório por macroetapa") sem migrar agentes existentes. Este módulo
define o contrato de **conteúdo**; a tabela ``stage_outputs`` continua a
mesma — só passa a aceitar (e validar, em runtime opt-in) JSONB conforme
estes schemas.

Os schemas convivem com a forma legacy ``dict[str, Any]``: ``BaseAgent.run``
aceita os dois formatos. Adoção real (uso obrigatório nos agentes) fica
para a Sprint A2.

Decisões da Fase 0:
- Naming ``StageOutputContent`` (Q5) — não colide com ``app.models.stage_output.StageOutput``.
- ``CitationRef`` é o tipo canônico (Q1) reusado pelo evaluator da Tarefa B.
- Sem cruzamento real contra ``knowledge_catalog`` aqui (só validação de tipo).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

# Templates suportados pelo RedatorAgent — ver app/agents/redator.py:VALID_TEMPLATES
PecaTemplate = Literal[
    "prad",
    "memorial",
    "oficio",
    "proposta",
    "resposta_notificacao",
    "contrato",
    "comunicacao",
]

CitationKind = Literal[
    "lei",
    "lei_complementar",
    "decreto",
    "decreto_lei",
    "resolucao_conama",
    "instrucao_normativa",
    "portaria",
    "medida_provisoria",
    "outro",
]

CitationJurisdicao = Literal["federal", "estadual", "municipal", "outro"]

SourceKind = Literal["legislation", "document", "manual"]
RiscoSeveridade = Literal["baixo", "medio", "alto"]


class _StrictModel(BaseModel):
    """Base interna: Pydantic v2 com extras proibidos para evitar drift de schema."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Source(_StrictModel):
    """Fonte de uma afirmação no conteúdo da etapa."""

    type: SourceKind
    ref: str = Field(..., min_length=1, description="ID do KnowledgeChunk, doc, ou ref livre")
    excerpt: str | None = Field(default=None)


class CitationRef(_StrictModel):
    """Referência canônica a uma norma legal.

    Reusada pelo evaluator de citação (Tarefa B): sai do regex já normalizada
    para ``kind/numero/ano`` e opcionalmente carrega o ``chunk_id`` quando o
    cruzamento contra ``knowledge_catalog`` der match.

    Sprint A1 B — incluídos campos opcionais ``jurisdicao`` (ortogonal ao
    ``kind`` — evita explosão combinatória "lei_estadual/decreto_estadual/
    portaria_estadual...") e ``artigo`` (capturado em extração; consumido
    como informação descritiva por enquanto, base para cruzamento por
    artigo em V2).
    """

    kind: CitationKind
    numero: str = Field(..., min_length=1, description="Número da norma (ex.: '12.651' ou '12651')")
    ano: int = Field(..., ge=1500, le=3000)
    raw: str = Field(..., min_length=1, description="Forma original como apareceu no texto")
    chunk_id: int | None = Field(
        default=None,
        description="ID em knowledge_catalog quando a citação é validada; None quando não confirmada.",
    )
    jurisdicao: CitationJurisdicao | None = Field(
        default=None,
        description="Esfera da norma — populado em validação a partir do chunk; None na extração crua.",
    )
    artigo: str | None = Field(
        default=None,
        description="Artigo/parágrafo citado (ex.: '7º', 'art. 12, § 2º'); descritivo em V1.",
    )


class Risco(_StrictModel):
    """Risco identificado pelo agente de diagnóstico."""

    descricao: str = Field(..., min_length=1)
    severidade: RiscoSeveridade
    mitigacao_sugerida: str | None = None


# ---------------------------------------------------------------------------
# Conteúdos — base + 3 derivados
# ---------------------------------------------------------------------------

class StageOutputContent(_StrictModel):
    """Base de qualquer conteúdo de ``StageOutput.content_data``.

    Validações:
    - ``sources`` precisa ter pelo menos 1 fonte.
    - ``confidence`` quando presente deve estar em [0, 1].
    """

    content: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    sources: list[Source] = Field(default_factory=list)
    confidence: float | None = Field(default=None)

    @field_validator("sources")
    @classmethod
    def _sources_non_empty(cls, value: list[Source]) -> list[Source]:
        if not value:
            raise ValueError("StageOutputContent.sources não pode ser vazio")
        return value

    @field_validator("confidence")
    @classmethod
    def _confidence_in_range(cls, value: float | None) -> float | None:
        if value is None:
            return value
        if not 0.0 <= value <= 1.0:
            raise ValueError("confidence deve estar em [0, 1]")
        return value


class DiagnosticoPreliminarContent(StageOutputContent):
    """Conteúdo do diagnóstico preliminar (etapa 2).

    Campos extras vêm do briefing da sócia: hipóteses, lacunas, riscos e
    checklist documental sugerido.
    """

    hipoteses: list[str] = Field(default_factory=list)
    lacunas: list[str] = Field(default_factory=list)
    riscos: list[Risco] = Field(default_factory=list)
    checklist_documental: list[str] = Field(default_factory=list)


class PecaJuridicaContent(StageOutputContent):
    """Conteúdo de peça jurídica gerada pelo RedatorAgent.

    Sprint A2-redator: ``extra="ignore"`` (override do default ``forbid`` em
    ``_StrictModel``) é proposital — round-trip via ``model_dump()`` inclui o
    ``computed_field document_type`` (alias deprecated para ``template``);
    em ``model_validate(dump)`` esse campo viraria input desconhecido e o
    "forbid" estouraria. Tradeoff aceitável: a anti-drift continua via
    typing rigoroso de ``template`` (Literal de 7 valores) e do enum-like
    ``CitationKind``.
    """

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    template: PecaTemplate
    legal_citations: list[CitationRef] = Field(default_factory=list)
    addressee: str | None = Field(default=None, description="Órgão/pessoa destinatária da peça")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def document_type(self) -> str:
        """Alias deprecated para ``template`` — backward compat com frontend
        (``AgentResultRenderer.tsx::RedatorResult``) e AIJobs históricos.

        Sprint A2-redator-B faz o frontend ler ``r.template || r.document_type``;
        em sprint posterior, depois de medir 0 uso desse alias, ele pode sumir.
        """
        return self.template


class RespostaNotificacaoContent(PecaJuridicaContent):
    """Resposta a notificação — subtipo de ``PecaJuridicaContent``.

    Modelado como subclasse porque toda resposta de notificação é também
    uma peça jurídica + os campos próprios de prazo e ato regulatório.
    """

    template: Literal["resposta_notificacao"] = "resposta_notificacao"
    prazo_dias: int = Field(..., ge=0, description="Prazo concedido pelo órgão (em dias corridos)")
    ato_regulatorio: str = Field(..., min_length=1, description="Identificação do ato/notificação que está sendo respondido")


class Etapa(_StrictModel):
    """Etapa do caminho regulatório proposto pelo LegislacaoAgent."""

    ordem: int = Field(..., ge=1)
    titulo: str = Field(..., min_length=1)
    descricao: str | None = None
    prazo_estimado_dias: int | None = Field(default=None, ge=0)
    orgao: str | None = None


class EnquadramentoRegulatorioContent(StageOutputContent):
    """Conteúdo do enquadramento regulatório emitido pelo LegislacaoAgent.

    Sprint A2-legislacao: o agente passa a emitir este Content (antes era dict
    cru). Mapeamento das chaves antigas:

    * ``caminho_regulatorio`` → campo próprio (e dual-emit)
    * ``justificativa`` → ``content`` (e dual-emit)
    * ``orgao_competente`` → campo próprio (e dual-emit)
    * ``etapas`` (list[dict]) → ``etapas: list[Etapa]`` (e dual-emit)
    * ``legislacao_aplicavel`` (list[dict|str]) → preservada via dual-emit;
      ``legal_citations`` carrega versão normalizada (``CitationRef``) quando
      possível, vazia caso contrário.
    * ``riscos`` (list[dict]) → ``riscos: list[Risco]`` (e dual-emit)
    * ``documentos_necessarios`` → campo próprio (e dual-emit)
    * ``recomendacoes`` → campo próprio (e dual-emit)
    * ``prazos_estimados`` (dict) → ``metadata["prazos_estimados"]`` (e dual-emit)
    * ``chunks_referenced`` → ``sources`` (cada chunk vira ``Source(type="legislation")``)
      e ``metadata["chunks_referenced"]`` (preserva detalhes para a UI).
    """

    caminho_regulatorio: str = Field(..., min_length=1)
    orgao_competente: str | None = None
    etapas: list[Etapa] = Field(default_factory=list)
    legal_citations: list[CitationRef] = Field(default_factory=list)
    riscos: list[Risco] = Field(default_factory=list)
    documentos_necessarios: list[str] = Field(default_factory=list)
    recomendacoes: list[str] = Field(default_factory=list)
