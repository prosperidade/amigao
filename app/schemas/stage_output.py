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

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    """

    kind: CitationKind
    numero: str = Field(..., min_length=1, description="Número da norma (ex.: '12.651' ou '12651')")
    ano: int = Field(..., ge=1500, le=3000)
    raw: str = Field(..., min_length=1, description="Forma original como apareceu no texto")
    chunk_id: int | None = Field(
        default=None,
        description="ID em knowledge_catalog quando a citação é validada; None quando não confirmada.",
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
    """Conteúdo de peça jurídica gerada pelo RedatorAgent."""

    template: PecaTemplate
    legal_citations: list[CitationRef] = Field(default_factory=list)
    addressee: str | None = Field(default=None, description="Órgão/pessoa destinatária da peça")


class RespostaNotificacaoContent(PecaJuridicaContent):
    """Resposta a notificação — subtipo de ``PecaJuridicaContent``.

    Modelado como subclasse porque toda resposta de notificação é também
    uma peça jurídica + os campos próprios de prazo e ato regulatório.
    """

    template: Literal["resposta_notificacao"] = "resposta_notificacao"
    prazo_dias: int = Field(..., ge=0, description="Prazo concedido pelo órgão (em dias corridos)")
    ato_regulatorio: str = Field(..., min_length=1, description="Identificação do ato/notificação que está sendo respondido")
