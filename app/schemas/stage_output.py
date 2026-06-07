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

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

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

# Enum legado mantido para dual-emit. "critico" é aditivo (Sprint A4):
# o Risco antigo só tinha 3 níveis; a taxonomia oficial pede 4. Manter os
# 3 antigos garante compat retroativa; somar "critico" garante mapeamento
# limpo com o novo `grau="critico_impeditivo_potencial"`.
RiscoSeveridade = Literal["baixo", "medio", "alto", "critico"]

# Taxonomia oficial do Mapa de Riscos (skill diagnostico/situacao_ambiental_imovel_rural).
# Sprint A4 — 7 categorias + 4 graus + 5 status + 4 prioridades de triagem.
RiscoCategoria = Literal[
    "fundiario",
    "geoespacial",
    "ambiental",
    "territorial",
    "cadastral_sistemico",
    "atividade_produtiva",
    "credito_mercado",
]
RiscoGrau = Literal[
    "informativo",
    "atencao",
    "alto",
    "critico_impeditivo_potencial",
]
RiscoStatusSaneamento = Literal[
    "pendente",
    "em_validacao",
    "saneado",
    "descartado",
    "nao_aplicavel",
]
# Dimensão ortogonal à gravidade (grau): expressa urgência/prazo.
# Um déficit de RL pode ser grau=alto mas prioridade_triagem=media;
# embargo travando crédito é grau=critico_impeditivo_potencial e
# prioridade_triagem=urgentissima.
RiscoPrioridadeTriagem = Literal[
    "urgentissima",
    "alta",
    "media",
    "estrategica",
]

NivelRiscoGeral = Literal["baixo", "medio", "alto", "critico"]
NivelConfiancaDiagnostico = Literal["baixa", "media", "alta"]


# Mapeamentos dual-emit Risco antigo (3 campos) ↔ novo (8 campos).
_SEVERIDADE_TO_GRAU: dict[str, str] = {
    "baixo": "informativo",
    "medio": "atencao",
    "alto": "alto",
    "critico": "critico_impeditivo_potencial",
}
_GRAU_TO_SEVERIDADE: dict[str, str] = {
    "informativo": "baixo",
    "atencao": "medio",
    "alto": "alto",
    "critico_impeditivo_potencial": "critico",
}


class _StrictModel(BaseModel):
    """Base interna: Pydantic v2 com extras proibidos para evitar drift de schema."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Source(_StrictModel):
    """Fonte de uma afirmação no conteúdo da etapa."""

    type: SourceKind
    ref: str = Field(..., min_length=1, description="ID do KnowledgeChunk, doc, ou ref livre")
    excerpt: str | None = Field(default=None)


# Tipos de fonte aceitos no contrato de rastreabilidade (validação especialista 06/06).
SourceRefTipo = Literal[
    "documento",     # certidão/CCIR/ITR/recibo (nome/tipo/id do Document)
    "matriz",        # linha da matriz de inconsistências
    "rat",           # parecer do órgão (protocolo + pendência)
    "legislacao",    # trecho do RAG (chunk do knowledge_catalog)
    "atendimento",   # relato/demanda do consultor
    "auditor",       # finding determinístico do auditor
    "sem_fonte",     # marcação honesta: afirmação sem fonte identificável
]


class SourceRef(_StrictModel):
    """Rastreabilidade genérica — "nenhuma afirmação sem fonte" (validação 06/06).

    Contrato comum a TODOS os agentes (matriz/diagnóstico/legislação e, depois,
    atendimento/orçamento/redator). Cada afirmação/linha/item carrega uma lista
    destas. NUNCA inventar fonte: se não há fonte identificável, usar
    ``tipo="sem_fonte"`` (ou ``sem_fonte=True``) — honestidade explícita.
    """

    tipo: SourceRefTipo
    ref: str | None = Field(default=None, description="ID/identificador específico (doc id, chunk id, protocolo RAT, chave da linha)")
    descricao: str | None = Field(default=None, description="Rótulo legível: nome do doc, norma+artigo, protocolo do RAT")
    valor: str | None = Field(default=None, description="O dado conferido/citado, quando aplicável (ex.: área, denominação)")
    confianca: str | None = Field(default=None, description="alta | media | baixa")
    sem_fonte: bool = Field(default=False, description="True = sem fonte identificável (não inventar)")


class Afirmacao(_StrictModel):
    """Uma afirmação com rastreabilidade — texto + fonte(s). 'Nenhuma afirmação
    sem fonte': se ``fontes`` vier vazio, o parser injeta uma ``SourceRef``
    ``sem_fonte`` para a UI sinalizar (nunca silenciar)."""

    texto: str = Field(..., min_length=1)
    categoria: str | None = Field(default=None, description="passivo | acao | hipotese | lacuna")
    fontes: list[SourceRef] = Field(default_factory=list)


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
    """Risco identificado pelo agente de diagnóstico (Sprint A4).

    Dual-emit: aceita payload antigo (``descricao/severidade/mitigacao_sugerida``)
    e payload novo (8 campos da taxonomia oficial + ``prioridade_triagem``).
    O ``model_validator(mode="after")`` reconcilia ida e volta, garantindo que:

    1. Payload antigo continua validando (regressão).
    2. Round-trip via ``model_dump`` → ``model_validate`` funciona.
    3. Consumidores legados (``EnquadramentoRegulatorioContent.riscos``) continuam
       lendo ``descricao/severidade/mitigacao_sugerida`` sem alteração.

    Pelo menos um dos pares precisa estar presente:
    ``risco_identificado`` (novo) **ou** ``descricao`` (antigo); ``grau`` (novo)
    **ou** ``severidade`` (antigo).
    """

    # ── Campos novos (taxonomia oficial — Mapa de Riscos da skill) ──
    categoria: RiscoCategoria | None = None
    risco_identificado: str | None = Field(default=None, min_length=1)
    grau: RiscoGrau | None = None
    impacto_possivel: str | None = None
    evidencia: str | None = None
    proximo_passo: str | None = None
    status_saneamento: RiscoStatusSaneamento = "pendente"
    observacao_consultor: str | None = None
    prioridade_triagem: RiscoPrioridadeTriagem | None = None

    # ── Aliases dual-emit (compat com Risco pré-A4) ──
    descricao: str | None = Field(default=None, min_length=1)
    severidade: RiscoSeveridade | None = None
    mitigacao_sugerida: str | None = None

    # Rastreabilidade (06/06): fonte(s) que sustentam o risco.
    sources: list[SourceRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _reconcile_dual_emit(self) -> Risco:
        # Ida (payload antigo → campos novos)
        if self.risco_identificado is None and self.descricao is not None:
            self.risco_identificado = self.descricao
        if self.grau is None and self.severidade is not None:
            self.grau = _SEVERIDADE_TO_GRAU[self.severidade]  # type: ignore[assignment]
        if self.proximo_passo is None and self.mitigacao_sugerida is not None:
            self.proximo_passo = self.mitigacao_sugerida

        # Volta (campos novos → aliases antigos, para serialização compat)
        if self.descricao is None and self.risco_identificado is not None:
            self.descricao = self.risco_identificado
        if self.severidade is None and self.grau is not None:
            self.severidade = _GRAU_TO_SEVERIDADE[self.grau]  # type: ignore[assignment]
        if self.mitigacao_sugerida is None and self.proximo_passo is not None:
            self.mitigacao_sugerida = self.proximo_passo

        # Requisitos mínimos
        if self.risco_identificado is None:
            raise ValueError("Risco precisa de risco_identificado (ou descricao legado)")
        if self.grau is None:
            raise ValueError("Risco precisa de grau (ou severidade legado)")
        return self


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


class Divergencia(_StrictModel):
    """Linha da matriz de cruzamento documental (Sprint A4).

    Cruzamentos típicos: Matrícula × CAR, Matrícula × CCIR/ITR/SIGEF,
    CAR × Sistema Ipê, CAR declarado × cobertura real. A skill
    ``situacao_ambiental_imovel_rural`` (movimento 1) gera essas linhas
    como ponto de partida do diagnóstico.
    """

    tema: str = Field(..., min_length=1, description="Ex.: 'área', 'titularidade', 'GEO INCRA'")
    divergencia: str = Field(..., min_length=1, description="Descrição da divergência observada")
    impacto: str = Field(..., min_length=1, description="Consequência prática")
    # Rastreabilidade (06/06): docs/valores que sustentam a divergência.
    sources: list[SourceRef] = Field(default_factory=list)


class NotificacaoItem(_StrictModel):
    """Linha da matriz de resposta à notificação (estágio saneamento).

    Quando o cliente chega com um caso JÁ ABERTO (notificação/exigências do
    órgão), o diagnóstico no estágio ``saneamento`` produz uma matriz de
    resposta item a item para alimentar o RedatorAgent.
    """

    exigencia: str = Field(..., min_length=1, description="Texto da exigência do órgão")
    fundamento: str = Field(..., min_length=1, description="Fundamento legal usado para responder")
    acao: str = Field(..., min_length=1, description="Ação a ser tomada")
    responsavel: str | None = None
    status: str = Field(..., min_length=1, description="Ex.: 'pendente', 'em_andamento', 'concluido'")


class DiagnosticoPreliminarContent(StageOutputContent):
    """Conteúdo do diagnóstico preliminar (etapa 2).

    Campos extras vêm do briefing da sócia: hipóteses, lacunas, riscos e
    checklist documental sugerido. Sprint A4 adiciona, todos opcionais:
    matriz de divergências (cruzamento documental), nível de risco geral,
    nível de confiança, recomendações externas (encaminhamentos), etapa do
    funil sugerida e matriz de resposta à notificação (estágio saneamento).
    """

    hipoteses: list[str] = Field(default_factory=list)
    lacunas: list[str] = Field(default_factory=list)
    riscos: list[Risco] = Field(default_factory=list)
    checklist_documental: list[str] = Field(default_factory=list)

    # ── Campos opcionais Sprint A4 ──
    divergencias: list[Divergencia] = Field(default_factory=list)
    nivel_risco_geral: NivelRiscoGeral | None = None
    nivel_confianca_diagnostico: NivelConfiancaDiagnostico | None = None
    recomendacoes_externas: list[str] = Field(default_factory=list)
    etapa_funil_sugerida: str | None = None
    matriz_notificacao: list[NotificacaoItem] | None = None

    # ── Rastreabilidade (validação 06/06): cada passivo/ação com fonte ──
    # Aditivo: convive com hipoteses/checklist_documental (strings) para os
    # renderers antigos; a UI nova lê `afirmacoes` (texto + fontes).
    afirmacoes: list[Afirmacao] = Field(default_factory=list)


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
    # Rastreabilidade (06/06): trecho(s) do RAG que sustentam prazo/etapa.
    # Vazio + prazo presente → o agente marca "estimativa profissional" em
    # `prazo_fonte` (sem fonte normativa nos autos).
    sources: list[SourceRef] = Field(default_factory=list)
    prazo_fonte: str | None = Field(
        default=None,
        description="'norma' (com source) | 'estimativa_profissional' (sem fonte normativa)",
    )


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


# ---------------------------------------------------------------------------
# Utilitário Pydantic ↔ JSONB (Sprint A4)
# ---------------------------------------------------------------------------

def validate_diagnostic_content(content: dict[str, Any]) -> DiagnosticoPreliminarContent:
    """Valida um dict contra ``DiagnosticoPreliminarContent``.

    Use ANTES de gravar em ``RegulatoryDiagnosis.content`` (JSONB livre): garante
    que o dict respeita o shape do schema. Levanta ``pydantic.ValidationError``
    quando inválido — o caller decide se faz log/alerta/abort.

    A função é o ponto de amarração Pydantic ↔ JSONB (gap A4 do mapa de gaps
    2026-05-23): hoje o JSONB aceita qualquer forma; passa a aceitar apenas o
    que ``DiagnosticoPreliminarContent.model_validate`` aprovar.
    """
    return DiagnosticoPreliminarContent.model_validate(content)


__all__ = [
    "CitationJurisdicao",
    "CitationKind",
    "CitationRef",
    "DiagnosticoPreliminarContent",
    "Divergencia",
    "EnquadramentoRegulatorioContent",
    "Etapa",
    "NivelConfiancaDiagnostico",
    "NivelRiscoGeral",
    "NotificacaoItem",
    "PecaJuridicaContent",
    "PecaTemplate",
    "RespostaNotificacaoContent",
    "Risco",
    "RiscoCategoria",
    "RiscoGrau",
    "RiscoPrioridadeTriagem",
    "RiscoSeveridade",
    "RiscoStatusSaneamento",
    "Source",
    "SourceKind",
    "StageOutputContent",
    "validate_diagnostic_content",
]
