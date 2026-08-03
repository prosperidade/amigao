from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DocumentUploadUrlRequest(BaseModel):
    """Solicita presigned URL para upload direto ao MinIO."""
    process_id: int
    filename: str
    content_type: str


class DocumentUploadUrlResponse(BaseModel):
    """Retorna presigned URL e storage_key para upload."""
    upload_url: str
    storage_key: str
    expires_in: int


class DocumentConfirmRequest(BaseModel):
    """Confirma metadados após upload direto ao MinIO."""
    process_id: int
    storage_key: str
    filename: str
    content_type: str
    file_size_bytes: int = Field(gt=0, le=104857600, description="Tamanho em bytes, máximo 100MB")
    document_type: Optional[str] = None
    document_category: Optional[str] = None
    checklist_item_id: Optional[str] = None


class DocumentResponse(BaseModel):
    id: int
    process_id: Optional[int] = None
    tenant_id: int
    filename: str
    original_file_name: str
    content_type: str
    storage_key: str
    file_size_bytes: int
    document_type: Optional[str] = None
    document_category: Optional[str] = None
    ocr_status: Optional[str] = None
    # Motivo legível da última falha de leitura (OCR ou transcrição). Já existia na
    # coluna e não chegava à tela — sem ele, "falhou" é silêncio com outro nome.
    ocr_error: Optional[str] = None
    # ADR-060 — documento com leitura pronta pode ter o texto aberto na tela
    # (`GET /documents/{id}/text`). Evita a tela pedir o texto de quem não tem.
    tem_texto: bool = False
    is_internal: bool = False
    extraction_status: Optional[str] = None
    review_required: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentUpdateRequest(BaseModel):
    """Campos do documento editáveis pelo consultor.

    Hoje só a visibilidade (ADR-060, decisão 3b). PATCH em vez de uma rota
    `/marcar-interno` porque o próximo campo editável (tipo corrigido à mão, por
    exemplo) entra aqui sem inventar rota nova."""

    is_internal: Optional[bool] = None


class DocumentTextResponse(BaseModel):
    """Texto lido do documento — OCR de PDF ou transcrição de áudio (ADR-060)."""

    document_id: int
    filename: Optional[str] = None
    ocr_status: Optional[str] = None
    ocr_error: Optional[str] = None
    # Marcado como transcrição de reunião? A tela rotula a origem sem ter de
    # reconhecer o formato do arquivo por conta própria.
    eh_transcricao: bool = False
    chars: int = 0
    text: Optional[str] = None
