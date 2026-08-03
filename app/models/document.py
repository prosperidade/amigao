import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class OcrStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"
    not_required = "not_required"


class DocumentSource(str, enum.Enum):
    upload_manual = "upload_manual"
    email = "email"
    whatsapp = "whatsapp"
    integration = "integration"
    generated_ai = "generated_ai"
    field_app = "field_app"
    # Sprint V (2026-04-29) — origem "wizard de Intake": diferencia documentos
    # anexados durante o cadastro inicial dos uploads feitos no Workspace depois
    # do caso criado. Habilita Cliente/Imóvel Hub a destacarem documentos vindos
    # do onboarding e o auditor_imovel a priorizar fontes da abertura do caso.
    intake = "intake"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    process_id = Column(Integer, ForeignKey("processes.id", ondelete="CASCADE"), nullable=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="SET NULL"), nullable=True, index=True)
    # Regente Cam1 — docs podem ser anexados a um rascunho antes do processo existir
    intake_draft_id = Column(Integer, ForeignKey("intake_drafts.id", ondelete="SET NULL"), nullable=True, index=True)

    # Metadados do arquivo
    original_file_name = Column(String, nullable=False)
    filename = Column(String, nullable=False)   # mantido por compatibilidade
    content_type = Column(String, nullable=False)
    mime_type = Column(String, nullable=True)
    extension = Column(String, nullable=True)
    storage_key = Column(String, nullable=False, unique=True)  # chave no MinIO/S3
    s3_key = Column(String, nullable=True)  # alias legado
    storage_provider = Column(String, default="minio")
    file_size_bytes = Column(Integer, default=0)
    size = Column(Integer, default=0)   # alias legado
    checksum_sha256 = Column(String, nullable=True)

    # Classificação documental
    document_type = Column(String, nullable=True)      # matricula, car, ccir, etc.
    document_category = Column(String, nullable=True)  # fundiario, ambiental, etc.
    version_number = Column(Integer, default=1)
    source = Column(Enum(DocumentSource), default=DocumentSource.upload_manual)

    # Pipeline OCR / Extração
    ocr_status = Column(Enum(OcrStatus), default=OcrStatus.pending)
    # Motivo legível do último OCR falho (fim do "failed silencioso"): storage,
    # formato não suportado, todas as cascatas falharam, etc. Limpo no sucesso.
    ocr_error = Column(String, nullable=True)
    extraction_status = Column(String, nullable=True)
    confidence_score = Column(Float, nullable=True)
    review_required = Column(Boolean, default=False)

    # Visibilidade (dívida #103 · ADR-060) — "material interno" do escritório.
    # Nasceu com a transcrição de áudio: a gravação registra o que o cliente
    # contou numa conversa, e nem toda conversa deve voltar para ele pelo portal.
    # Default conservador e explícito: FALSE — o áudio entra como documento normal
    # do caso. Marcado como interno, some da listagem do portal do cliente; segue
    # valendo integralmente para o consultor e para o diagnóstico (é material de
    # trabalho dele, não material que o sistema esconde de quem trabalha).
    is_internal = Column(Boolean, default=False, nullable=False, server_default="false")

    uploaded_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Sprint 2 — vínculo com item de checklist e validade documental
    checklist_item_id = Column(String, nullable=True)   # id do item no ProcessChecklist.items[]
    expires_at = Column(DateTime(timezone=True), nullable=True)  # data de validade do documento

    # Sprint -1 D — texto extraído do documento (OCR/PDF parse) disponível para o agente
    # extrator. Hoje o fluxo passa `text` direto em metadata; a coluna permite
    # chamadas com apenas document_id.
    extracted_text = Column(Text, nullable=True)
    extracted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    @property
    def tem_texto(self) -> bool:
        """Este documento já tem leitura (OCR ou transcrição) disponível?

        Exposto no `DocumentResponse` para a tela saber se vale abrir o texto sem
        precisar carregá-lo na listagem inteira."""
        return bool((self.extracted_text or "").strip())

    tenant = relationship("Tenant")
    process = relationship("Process")
    client = relationship("Client")
