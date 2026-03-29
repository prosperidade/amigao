import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.api.deps import AccessContext, get_access_context, get_db
from app.core.metrics import record_document_upload
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.process import Process
from app.schemas.document import (
    DocumentUploadUrlRequest,
    DocumentUploadUrlResponse,
    DocumentConfirmRequest,
    DocumentResponse,
)
from app.services.storage import StorageService, get_storage_service

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_accessible_process(
    db: Session, process_id: int, access_context: AccessContext
) -> Process:
    query = db.query(Process).filter(
        Process.id == process_id,
        Process.tenant_id == access_context.tenant_id,
    )
    if access_context.client_id is not None:
        query = query.filter(Process.client_id == access_context.client_id)

    process = query.first()
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado ou sem acesso")
    return process


def _scoped_document_query(db: Session, access_context: AccessContext):
    query = (
        db.query(Document)
        .outerjoin(Process, Document.process_id == Process.id)
        .filter(Document.tenant_id == access_context.tenant_id)
    )
    if access_context.client_id is not None:
        query = query.filter(
            or_(
                Document.client_id == access_context.client_id,
                and_(
                    Document.client_id.is_(None),
                    Process.client_id == access_context.client_id,
                ),
            )
        )
    return query


def _get_storage_service() -> StorageService:
    return get_storage_service()


@router.get("/", response_model=List[DocumentResponse])
def list_documents(
    process_id: Optional[int] = None,
    db: Session = Depends(get_db),
    access_context: AccessContext = Depends(get_access_context),
):
    """Lista documentos respeitando o escopo do usuário autenticado."""
    query = _scoped_document_query(db, access_context)
    if process_id:
        _get_accessible_process(db, process_id, access_context)
        query = query.filter(Document.process_id == process_id)
    return query.all()



@router.post("/upload-url", response_model=DocumentUploadUrlResponse)
def get_upload_url(
    body: DocumentUploadUrlRequest,
    db: Session = Depends(get_db),
    access_context: AccessContext = Depends(get_access_context),
):
    """
    Etapa 1: Solicita presigned URL para upload direto ao MinIO.
    O cliente faz PUT direto para a URL retornada, sem passar pelo servidor.
    """
    # Validar processo
    _get_accessible_process(db, body.process_id, access_context)

    result = _get_storage_service().generate_presigned_put_url(
        tenant_id=access_context.tenant_id,
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
    access_context: AccessContext = Depends(get_access_context),
):
    """
    Etapa 2: Confirma metadados após upload direto ao MinIO.
    Persiste o registro do documento no banco.
    """
    process = _get_accessible_process(db, body.process_id, access_context)
    ext = body.filename.split('.')[-1] if '.' in body.filename else ''

    db_doc = Document(
        tenant_id=access_context.tenant_id,
        process_id=body.process_id,
        client_id=process.client_id,
        uploaded_by_user_id=access_context.user.id,
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
    audit = AuditLog(
        tenant_id=access_context.tenant_id,
        user_id=access_context.user.id,
        entity_type="document",
        entity_id=0,
        action="uploaded",
        details="Documento confirmado via upload direto",
    )
    db.add(db_doc)
    db.flush()
    audit.entity_id = db_doc.id
    db.add(audit)
    db.commit()
    db.refresh(db_doc)

    try:
        from app.workers.tasks import notify_document_uploaded

        notify_document_uploaded.delay(
            tenant_id=access_context.tenant_id,
            process_id=body.process_id,
            document_id=db_doc.id,
            actor_user_id=access_context.user.id,
            source="client_portal" if access_context.is_client_portal else "internal",
        )
    except Exception as exc:
        logger.warning(
            "Falha ao enfileirar notificação do documento %s: %s",
            db_doc.id,
            exc,
        )

    record_document_upload("client_portal" if access_context.is_client_portal else "internal", "success")
    logger.info(f"Documento #{db_doc.id} confirmado | tenant={access_context.tenant_id} | '{body.filename}'")
    return db_doc


@router.get("/{document_id}/download-url")
def get_download_url(
    document_id: int,
    db: Session = Depends(get_db),
    access_context: AccessContext = Depends(get_access_context),
):
    """Gera presigned URL para download seguro do documento."""
    doc = _scoped_document_query(db, access_context).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    url = _get_storage_service().generate_presigned_get_url(doc.storage_key)
    return {"download_url": url, "expires_in": 300}
