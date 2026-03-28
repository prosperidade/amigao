import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user, get_current_tenant
from app.models.user import User
from app.models.tenant import Tenant
from app.models.document import Document
from app.models.process import Process
from app.schemas.document import (
    DocumentUploadUrlRequest,
    DocumentUploadUrlResponse,
    DocumentConfirmRequest,
    DocumentResponse,
)
from app.services.storage import StorageService

router = APIRouter()
storage_service = StorageService()
logger = logging.getLogger(__name__)


@router.get("/", response_model=List[DocumentResponse])
def list_documents(
    process_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Lista documentos de um tenant, podendo filtrar por processo."""
    query = db.query(Document).filter(Document.tenant_id == current_tenant.id)
    if process_id:
        query = query.filter(Document.process_id == process_id)
    return query.all()



@router.post("/upload-url", response_model=DocumentUploadUrlResponse)
def get_upload_url(
    body: DocumentUploadUrlRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Etapa 1: Solicita presigned URL para upload direto ao MinIO.
    O cliente faz PUT direto para a URL retornada, sem passar pelo servidor.
    """
    # Validar processo
    process = db.query(Process).filter(
        Process.id == body.process_id,
        Process.tenant_id == current_tenant.id
    ).first()
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado ou sem acesso")

    result = storage_service.generate_presigned_put_url(
        tenant_id=current_tenant.id,
        process_id=body.process_id,
        filename=body.filename,
        content_type=body.content_type,
    )
    logger.info(f"Presigned URL gerada para processo #{body.process_id} | arquivo='{body.filename}'")
    return result


@router.post("/confirm-upload", response_model=DocumentResponse)
def confirm_upload(
    body: DocumentConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Etapa 2: Confirma metadados após upload direto ao MinIO.
    Persiste o registro do documento no banco.
    """
    ext = body.filename.split('.')[-1] if '.' in body.filename else ''

    db_doc = Document(
        tenant_id=current_tenant.id,
        process_id=body.process_id,
        uploaded_by_user_id=current_user.id,
        filename=body.filename,
        original_file_name=body.filename,
        content_type=body.content_type,
        mime_type=body.content_type,
        extension=ext,
        storage_key=body.storage_key,
        s3_key=body.storage_key,
        file_size_bytes=body.file_size_bytes,
        size=body.file_size_bytes,
        document_type=body.document_type,
        document_category=body.document_category,
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)

    logger.info(f"Documento #{db_doc.id} confirmado | tenant={current_tenant.id} | '{body.filename}'")
    return db_doc


@router.get("/{document_id}/download-url")
def get_download_url(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Gera presigned URL para download seguro do documento."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.tenant_id == current_tenant.id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    url = storage_service.generate_presigned_get_url(doc.storage_key)
    return {"download_url": url, "expires_in": 300}
