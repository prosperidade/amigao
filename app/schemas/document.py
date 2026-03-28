from pydantic import BaseModel
from datetime import datetime
from typing import Optional


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
    file_size_bytes: int
    document_type: Optional[str] = None
    document_category: Optional[str] = None


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
    review_required: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
