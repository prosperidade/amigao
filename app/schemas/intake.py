"""
Schemas de Intake — Sprint 1 (Regente v3 Camada 1)

Mudanças Regente v3 (2026-04):
  - description agora é OPCIONAL (card nasce sem descrição completa)
  - entry_type adicionado: 5 cenários (novo/existente + docs)
  - initial_summary separado da description técnica
"""
import enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.process import EntryType


class IntakeClassifyRequest(BaseModel):
    description: str = Field(..., min_length=10, description="Descrição da demanda em texto livre")
    process_type: Optional[str] = Field(None, description="Tipo pré-selecionado pelo consultor (opcional)")
    urgency: Optional[str] = Field(None, description="Nível de urgência: baixa | media | alta | critica")
    source_channel: Optional[str] = Field(None, description="Canal de entrada: whatsapp | email | presencial | etc.")


class DocumentRequirement(BaseModel):
    id: str
    label: str
    doc_type: str
    category: str
    required: bool


class IntakeClassifyResponse(BaseModel):
    demand_type: str
    demand_label: str
    confidence: str
    initial_diagnosis: str
    required_documents: list[DocumentRequirement]
    suggested_next_steps: list[str]
    checklist_template_demand_type: str
    urgency_flag: Optional[str]
    relevant_agencies: list[str]


class IntakeClientCreate(BaseModel):
    full_name: str
    phone: Optional[str] = None
    # Decisão Isis (2026-05-28): e-mail é OBRIGATÓRIO no contato (não opcional).
    email: str = Field(..., description="E-mail do contato — OBRIGATÓRIO (decisão Isis 2026-05-28).")
    cpf_cnpj: Optional[str] = None
    client_type: Optional[str] = "pf"
    source_channel: Optional[str] = None

    @field_validator("email")
    @classmethod
    def _email_nao_vazio(cls, v: str) -> str:
        v = (v or "").strip()
        if not v or "@" not in v:
            raise ValueError("E-mail é obrigatório e deve ser válido.")
        return v


class IntakePropertyCreate(BaseModel):
    name: str
    municipality: Optional[str] = None
    state: Optional[str] = None
    car_number: Optional[str] = None
    ccir_number: Optional[str] = None
    area_hectares: Optional[float] = None


class IntakeCreateCaseRequest(BaseModel):
    # Cenário Regente: define o fluxo da tela
    entry_type: Optional[EntryType] = Field(
        EntryType.novo_cliente_novo_imovel,
        description="Cenário do cadastro (5 opções Regente Cam1). Default mantém compat.",
    )

    # Dados do cliente (cria novo ou vincula existente)
    client_id: Optional[int] = Field(None, description="Vincula cliente existente")
    new_client: Optional[IntakeClientCreate] = Field(None, description="Cria novo cliente")

    # Dados do imóvel
    property_id: Optional[int] = Field(None, description="Vincula imóvel existente")
    new_property: Optional[IntakePropertyCreate] = Field(None, description="Cria novo imóvel")

    # Dados do processo
    # description agora é OPCIONAL — card nasce sem descrição (regra Regente Cam1)
    description: Optional[str] = Field(
        None,
        description="Descrição técnica da demanda (opcional — pode ser enriquecida depois).",
    )
    initial_summary: Optional[str] = Field(
        None,
        description="Resumo curto da demanda na voz do cliente (primeiro contato).",
    )
    urgency: Optional[str] = "media"
    source_channel: Optional[str] = None
    intake_notes: Optional[str] = None

    # Áudio da entrevista (decisão Isis 2026-05-28): entra como input para
    # transcrição (Whisper) pelo agente de atendimento. A transcrição em si é
    # PR própria do agente; aqui só carregamos a referência do arquivo.
    audio_url: Optional[str] = Field(
        None, description="URL/storage key do áudio da entrevista (transcrição via agente)."
    )

    # Classificação (pode vir do /classify ou ser informada diretamente)
    demand_type: Optional[str] = None
    process_type: Optional[str] = None

    # PR fix Isis #2: finalização migra os docs do rascunho para o processo.
    draft_id: Optional[int] = Field(
        None,
        description="Se presente, migra os Documents do IntakeDraft para o processo criado (mesma transação).",
    )


class IntakeCaseCreatedResponse(BaseModel):
    client_id: int
    property_id: Optional[int]
    process_id: int
    demand_type: str
    demand_label: str
    initial_diagnosis: str
    checklist_generated: bool
    suggested_next_steps: list[str]
    process_title: str


# ---------------------------------------------------------------------------
# Rascunhos (CAM1-008/009) — salvar e continuar depois
# ---------------------------------------------------------------------------

class IntakeDraftCreateRequest(BaseModel):
    """Payload livre — o wizard salva o estado parcial do formulário."""
    entry_type: Optional[EntryType] = None
    form_data: dict = Field(default_factory=dict)


class IntakeDraftUpdateRequest(BaseModel):
    entry_type: Optional[EntryType] = None
    form_data: Optional[dict] = None


class IntakeDraftResponse(BaseModel):
    id: int
    state: str
    entry_type: Optional[str]
    form_data: dict
    linked_process_id: Optional[int]
    created_by_user_id: Optional[int]
    has_minimal_base: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    # Sprint F Bloco 3 — rascunho expira em 15 dias (decisão sócia 2026-04-19).
    expires_at: Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# CAM1-004 — Complementar base existente
# ---------------------------------------------------------------------------

class IntakeEnrichClientFields(BaseModel):
    """Campos opcionais para enriquecer cliente existente."""
    phone: Optional[str] = None
    email: Optional[str] = None
    cpf_cnpj: Optional[str] = None
    client_type: Optional[str] = None


class IntakeEnrichPropertyFields(BaseModel):
    """Campos opcionais para enriquecer imóvel existente."""
    municipality: Optional[str] = None
    state: Optional[str] = None
    car_number: Optional[str] = None
    ccir_number: Optional[str] = None
    area_hectares: Optional[float] = None


class IntakeEnrichRequest(BaseModel):
    """Complementar base já iniciada (Regente CAM1-004).

    Atualiza campos do cliente e/ou imóvel existentes. Apenas campos informados
    são alterados — campos ausentes são preservados. Registra AuditLog.
    """
    client_id: int = Field(..., description="Cliente a enriquecer")
    property_id: Optional[int] = Field(None, description="Imóvel a enriquecer (opcional)")
    client_fields: Optional[IntakeEnrichClientFields] = None
    property_fields: Optional[IntakeEnrichPropertyFields] = None
    note: Optional[str] = Field(None, description="Nota de contexto (aparece no AuditLog)")


class IntakeEnrichResponse(BaseModel):
    client_id: int
    property_id: Optional[int]
    updated_fields: dict  # {"client": [...], "property": [...]}
    audit_log_id: Optional[int] = None


# ---------------------------------------------------------------------------
# CAM1-007 / CAM1-005 — Upload de documentos em rascunho de intake
# ---------------------------------------------------------------------------

class IntakeDraftUploadUrlRequest(BaseModel):
    filename: str
    content_type: str
    document_type: Optional[str] = None   # matricula, car, ccir, cpf_cnpj, etc.
    document_category: Optional[str] = None  # fundiario, ambiental, ...


class IntakeDraftUploadUrlResponse(BaseModel):
    upload_url: str
    storage_key: str
    expires_in: int


class IntakeDraftConfirmUploadRequest(BaseModel):
    storage_key: str
    filename: str
    content_type: str
    file_size_bytes: int = 0
    document_type: Optional[str] = None
    document_category: Optional[str] = None


class IntakeDraftDocumentResponse(BaseModel):
    id: int
    filename: str
    document_type: Optional[str]
    document_category: Optional[str]
    ocr_status: Optional[str]
    file_size_bytes: int
    created_at: Optional[str] = None


class IntakeImportRequest(BaseModel):
    """Dispara agent_extrator em todos os documentos do draft (CAM1-005).

    O agente lê cada doc via OCR+LLM, extrai campos estruturados e sugere
    preenchimento da base. Resultado fica disponível via GET do draft.
    """
    doc_ids: Optional[list[int]] = None  # se omitido, usa todos os docs do draft


class IntakeImportResponse(BaseModel):
    draft_id: int
    docs_queued: int
    task_ids: list[str] = []


# CAM1-005 Parte A (Sprint L) — resultados de extração prontos para revisão.
class IntakeExtractedDocument(BaseModel):
    document_id: int
    filename: Optional[str] = None
    document_type: Optional[str] = None
    ocr_status: Optional[str] = None
    extracted_fields: dict = {}           # campos extraídos (cpf_cnpj, matricula, car_code, etc.)
    fields_count: int = 0
    extracted_at: Optional[str] = None    # ISO timestamp


class IntakeExtractionResultsResponse(BaseModel):
    """CAM1-005 Parte A — retorna sugestões extraídas dos docs do draft.

    Consultor revisa em `suggestions` (agregado por campo, prioridade por confiança)
    e detalhe em `by_document` (origem da sugestão). Aplica manualmente no formulário.
    """
    draft_id: int
    docs_total: int
    docs_with_results: int
    by_document: list[IntakeExtractedDocument] = []
    suggestions: dict = {}                # campo → valor mais confiável (ex: cpf_cnpj, matricula)


# ---------------------------------------------------------------------------
# Campos derivados do intake (decisões Isis 2026-05-28)
#
# Três famílias de campos, separadas por PROCEDÊNCIA:
#   - ManualFields    → o consultor digita (contato, funil, pessoa, atividade).
#   - ExtractedFields → a IA (agent_extrator) lê dos documentos; o consultor
#                       NÃO digita. Cada campo carrega value/confidence/origem.
#   - TriagemFields   → 2 eixos independentes de prioridade + observação.
#
# Não substituem o `form_data` livre do draft — documentam e validam a estrutura
# que o wizard envia. Sintoma, Dor e "Possui arquivo do CAR" NÃO entram (decisão
# Isis: são interpretação do consultor / o sistema infere do anexo).
# ---------------------------------------------------------------------------

class UrgenciaNivel(str, enum.Enum):
    urgentissima = "urgentissima"
    alta = "alta"
    media = "media"
    baixa = "baixa"


class ValorEstrategico(str, enum.Enum):
    alto = "alto"
    medio = "medio"
    # Nível "baixo": Isis não definiu critério escrito (dívida aberta) —
    # label sem régua; consultor decide livre.
    baixo = "baixo"


class TipoAtividade(str, enum.Enum):
    agricultura = "agricultura"
    pecuaria = "pecuaria"
    florestal = "florestal"
    agroindustrial = "agroindustrial"
    outro = "outro"


class ManualContato(BaseModel):
    nome: str
    telefone: Optional[str] = None
    email: str = Field(..., description="OBRIGATÓRIO (decisão Isis).")
    fonte: Optional[str] = None  # canal de origem / IntakeSource

    @field_validator("email")
    @classmethod
    def _email_nao_vazio(cls, v: str) -> str:
        v = (v or "").strip()
        if not v or "@" not in v:
            raise ValueError("E-mail é obrigatório e deve ser válido.")
        return v


class ManualFunil(BaseModel):
    origem: Optional[str] = None
    indicado_por: Optional[str] = None
    primeiro_contato_em: Optional[str] = None  # ISO date


class ManualPessoa(BaseModel):
    tipo: str = Field("pf", description="pf | pj")
    cpf_cnpj: Optional[str] = None
    nome_legal: Optional[str] = None


class ManualFields(BaseModel):
    """Campos preenchidos manualmente pelo consultor no wizard."""
    contato: ManualContato
    funil: Optional[ManualFunil] = None
    pessoa: Optional[ManualPessoa] = None
    possui_car: bool = False
    tipo_atividade: list[TipoAtividade] = Field(default_factory=list)
    audio_url: Optional[str] = None  # vai para o extrator/transcrição


class ExtractedField(BaseModel):
    """Um campo lido pela IA, com proveniência e confiança."""
    value: Any = None
    confidence: Optional[float] = None
    source_document_id: Optional[int] = None


class ExtractedFields(BaseModel):
    """Campos extraídos pela IA dos documentos — o consultor NÃO digita."""
    nirf: Optional[ExtractedField] = None
    ccir_numero: Optional[ExtractedField] = None
    sigef_numero: Optional[ExtractedField] = None
    car_numero: Optional[ExtractedField] = None
    municipio: Optional[ExtractedField] = None
    uf: Optional[ExtractedField] = None
    coordenadas_centroide: Optional[ExtractedField] = None
    area_total_ha: Optional[ExtractedField] = None
    titular_matricula: Optional[ExtractedField] = None
    area_app: Optional[ExtractedField] = None
    area_rl: Optional[ExtractedField] = None
    area_consolidada: Optional[ExtractedField] = None


class TriagemFields(BaseModel):
    """Dois eixos independentes de prioridade (decisão Isis 2026-05-28)."""
    urgencia: UrgenciaNivel = UrgenciaNivel.media
    valor_estrategico: ValorEstrategico = ValorEstrategico.medio
    observacoes_triagem: Optional[str] = None


# ---------------------------------------------------------------------------
# Reconciliação cliente × IA (Opção A — decisão na divergência)
# ---------------------------------------------------------------------------

class IntakeReconcileRequest(BaseModel):
    """Resolve a divergência entre o valor digitado e o extraído pela IA.

    O consultor escolhe a origem vencedora para UM campo. A escolha grava
    `form_data["field_sources"][field]` (= "manual" | "extracted") e fixa o
    valor resolvido em `form_data["reconciled"][field]`, aplicado às colunas
    reais (Client/Property.field_sources) no commit do draft.
    """
    field: str = Field(..., description="Nome do campo reconciliado.")
    source: str = Field(..., description='Origem vencedora: "manual" ou "extracted".')
    value: Any = Field(None, description="Valor escolhido para o campo.")

    @field_validator("source")
    @classmethod
    def _source_valida(cls, v: str) -> str:
        if v not in ("manual", "extracted"):
            raise ValueError('source deve ser "manual" ou "extracted".')
        return v


class IntakeReconcileResponse(BaseModel):
    draft_id: int
    field: str
    source: str
    value: Any = None
    field_sources: dict = {}  # estado atual de form_data["field_sources"]


# ---------------------------------------------------------------------------
# Preview lateral — campos extraídos prontos para a UI (GET extracted-fields)
# ---------------------------------------------------------------------------

class ExtractedFieldView(BaseModel):
    field: str
    value: Any = None
    confidence: Optional[float] = None
    source_document_id: Optional[int] = None
    source_document_name: Optional[str] = None
    diverges_from_manual: bool = False  # True se o valor manual difere do extraído


class IntakeExtractedFieldsResponse(BaseModel):
    """Resposta do preview lateral: campos extraídos + flag de divergência."""
    draft_id: int
    fields: list[ExtractedFieldView] = []
    has_divergence: bool = False
