import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import AccessContext, get_access_context, get_current_internal_user, get_db
from app.core.metrics import record_document_upload
from app.models.document import Document
from app.models.document_categories import (
    REGENTE_CATEGORIES,
    REGENTE_CATEGORY_LABELS,
    normalize_category,
)
from app.models.user import User
from app.repositories import DocumentRepository, ProcessRepository
from app.schemas.document import (
    DocumentConfirmRequest,
    DocumentResponse,
    DocumentUploadUrlRequest,
    DocumentUploadUrlResponse,
)
from app.services.storage import StorageService, get_storage_service

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "csv",
    "jpg", "jpeg", "png", "tiff", "tif", "bmp",
    "zip", "rar", "7z",
    "dwg", "dxf", "shp", "kml", "kmz", "geojson",
    "txt", "rtf", "odt", "ods",
}

MIME_EXTENSION_MAP: dict[str, set[str]] = {
    "application/pdf": {"pdf"},
    "image/jpeg": {"jpg", "jpeg"},
    "image/png": {"png"},
    "image/tiff": {"tiff", "tif"},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {"docx"},
    "application/msword": {"doc"},
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {"xlsx"},
    "application/vnd.ms-excel": {"xls"},
    "text/csv": {"csv"},
    "application/zip": {"zip"},
    "text/plain": {"txt"},
}


def _validate_file(filename: str, content_type: str) -> str:
    """Valida extensão e consistência MIME do arquivo. Retorna a extensão normalizada."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Extensão '.{ext}' não permitida. Permitidas: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    if content_type in MIME_EXTENSION_MAP:
        if ext not in MIME_EXTENSION_MAP[content_type]:
            raise HTTPException(
                status_code=400,
                detail=f"Content-type '{content_type}' incompatível com extensão '.{ext}'",
            )
    return ext


def _get_storage_service() -> StorageService:
    return get_storage_service()


@router.get("/categories")
def list_document_categories(
    current_user: User = Depends(get_current_internal_user),
):
    """CAM2IH-010 — Lista as 6 categorias canônicas Regente com labels."""
    return [
        {"value": v, "label": REGENTE_CATEGORY_LABELS[v]}
        for v in REGENTE_CATEGORIES
    ]


@router.get("/", response_model=list[DocumentResponse])
def list_documents(
    process_id: Optional[int] = None,
    client_id: Optional[int] = None,
    db: Session = Depends(get_db),
    access_context: AccessContext = Depends(get_access_context),
):
    """Lista documentos respeitando o escopo do usuário autenticado.

    - Usuário do portal: escopo fixo no próprio client_id (query param ignorado).
    - Usuário interno (consultor): pode filtrar por client_id e/ou process_id.
    """
    doc_repo = DocumentRepository(db, access_context.tenant_id)

    if process_id:
        proc_repo = ProcessRepository(db, access_context.tenant_id)
        proc_repo.get_scoped_or_404(process_id, client_id=access_context.client_id)

    # Portal tem escopo fixo; interno usa query param quando fornecido.
    effective_client_id = access_context.client_id if access_context.client_id else client_id

    return doc_repo.list_scoped(
        client_id=effective_client_id,
        process_id=process_id,
    )


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
    proc_repo = ProcessRepository(db, access_context.tenant_id)
    proc_repo.get_scoped_or_404(body.process_id, client_id=access_context.client_id)

    _validate_file(body.filename, body.content_type)

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
    proc_repo = ProcessRepository(db, access_context.tenant_id)
    process = proc_repo.get_scoped_or_404(body.process_id, client_id=access_context.client_id)

    ext = _validate_file(body.filename, body.content_type)

    doc_repo = DocumentRepository(db, access_context.tenant_id)
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
    db.add(db_doc)
    db.flush()

    doc_repo.add_audit(
        user_id=access_context.user.id,
        document=db_doc,
        action="uploaded",
        details="Documento confirmado via upload direto",
    )
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

    # Trigger Agente Extrator para doc_types extraiveis (async, fire-and-forget)
    EXTRACTABLE_DOC_TYPES = {"matricula", "car", "ccir", "auto_infracao", "licenca"}
    if body.document_type and body.document_type in EXTRACTABLE_DOC_TYPES:
        try:
            from app.workers.agent_tasks import run_agent  # noqa: PLC0415
            run_agent.delay(
                agent_name="extrator",
                tenant_id=access_context.tenant_id,
                user_id=access_context.user.id,
                process_id=body.process_id,
                metadata={
                    "document_id": db_doc.id,
                    "doc_type": body.document_type,
                },
            )
            logger.info("Agente extrator enfileirado para document_id=%s", db_doc.id)
        except Exception as exc:
            logger.warning("Falha ao enfileirar agente extrator para document_id=%s: %s", db_doc.id, exc)

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
    doc_repo = DocumentRepository(db, access_context.tenant_id)
    doc = doc_repo.get_scoped(document_id, client_id=access_context.client_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    url = _get_storage_service().generate_presigned_get_url(doc.storage_key)
    return {"download_url": url, "expires_in": 300}
