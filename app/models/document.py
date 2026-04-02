from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Float, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
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


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    process_id = Column(Integer, ForeignKey("processes.id"), nullable=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=True, index=True)

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
    extraction_status = Column(String, nullable=True)
    confidence_score = Column(Float, nullable=True)
    review_required = Column(Boolean, default=False)

    uploaded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Sprint 2 — vínculo com item de checklist e validade documental
    checklist_item_id = Column(String, nullable=True)   # id do item no ProcessChecklist.items[]
    expires_at = Column(DateTime(timezone=True), nullable=True)  # data de validade do documento

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tenant = relationship("Tenant")
    process = relationship("Process")
    client = relationship("Client")
