import logging
from datetime import UTC
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
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
    DocumentTextResponse,
    DocumentUpdateRequest,
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
    # Áudio de reunião/ligação (dívida #103 · ADR-060). O seletor "🎙️ Áudio de
    # reunião/ligação" existia na tela do caso desde a rodada anterior, mas a
    # allowlist do backend nunca ganhou as extensões — o upload morria com
    # 400 "Extensão '.m4a' não permitida" antes de qualquer transcrição.
    "mp3", "m4a", "wav", "ogg", "oga", "opus", "webm", "flac", "aac",
    "mpga", "amr", "wma", "3gp", "aiff", "caf",
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
    if content_type in MIME_EXTENSION_MAP and ext not in MIME_EXTENSION_MAP[content_type]:
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
    property_id: Optional[int] = None,
    db: Session = Depends(get_db),
    access_context: AccessContext = Depends(get_access_context),
):
    """Lista documentos respeitando o escopo do usuário autenticado.

    - Usuário do portal: escopo fixo no próprio client_id (query params client_id/property_id ignorados).
    - Usuário interno (consultor): pode filtrar por client_id, process_id e/ou property_id.
    """
    doc_repo = DocumentRepository(db, access_context.tenant_id)

    if process_id:
        proc_repo = ProcessRepository(db, access_context.tenant_id)
        proc_repo.get_scoped_or_404(process_id, client_id=access_context.client_id)

    # Portal tem escopo fixo; interno usa query params quando fornecidos.
    effective_client_id = access_context.client_id if access_context.client_id else client_id
    effective_property_id = None if access_context.client_id else property_id

    docs = doc_repo.list_scoped(
        client_id=effective_client_id,
        process_id=process_id,
        property_id=effective_property_id,
    )

    # Visibilidade (ADR-060): "material interno" é do escritório. O consultor vê
    # tudo — inclusive o que ele mesmo marcou como interno, com o rótulo na tela.
    # O portal do cliente não. Filtrar aqui, e não no repositório, mantém a regra
    # ao lado de quem conhece o perfil de quem perguntou.
    if access_context.is_client_portal:
        docs = [d for d in docs if not getattr(d, "is_internal", False)]

    return docs


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


@router.post(
    "/confirm-upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def confirm_upload(
    body: DocumentConfirmRequest,
    db: Session = Depends(get_db),
    access_context: AccessContext = Depends(get_access_context),
):
    """
    Etapa 2: Confirma metadados após upload direto ao MinIO.

    Persiste o Document e enfileira o pipeline de extração de texto:
    - PDFs → `ocr_then_extract` (OCR cascata pypdf→Gemini→OpenAI + dispatch do extrator)
    - Não-PDFs extractable → `run_agent('extrator')` direto (sem etapa de OCR)

    Retorna 202 Accepted: o documento está persistido e processado em background.
    O frontend acompanha o progresso via WebSocket (`document.ocr.completed`) ou
    polling em `Document.ocr_status`.
    """
    proc_repo = ProcessRepository(db, access_context.tenant_id)
    process = proc_repo.get_scoped_or_404(body.process_id, client_id=access_context.client_id)

    ext = _validate_file(body.filename, body.content_type)

    doc_repo = DocumentRepository(db, access_context.tenant_id)
    # CAM2IH-010 (Sprint H) — normaliza categoria para a taxonomia Regente canônica.
    normalized_category = normalize_category(body.document_category) or body.document_category
    db_doc = Document(
        tenant_id=access_context.tenant_id,
        process_id=body.process_id,
        client_id=process.client_id,
        # CAM2IH-004 (Sprint H) — herda property_id do processo para a Aba Documentos do Imóvel Hub.
        property_id=process.property_id,
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
        document_category=normalized_category,
        checklist_item_id=body.checklist_item_id,
    )
    db.add(db_doc)
    db.flush()

    doc_repo.add_audit(
        user_id=access_context.user.id,
        document=db_doc,
        action="uploaded",
        details="Documento confirmado via upload direto",
    )

    # Vínculo doc ↔ item de checklist (sintoma original: doc não vira "recebido"
    # automaticamente). Se o frontend especificar checklist_item_id, marca aquele
    # item exato; caso contrário tenta auto-vínculo pelo doc_type.
    from app.models.checklist_template import ProcessChecklist  # noqa: PLC0415
    from app.services.checklist_engine import (  # noqa: PLC0415
        auto_link_document,
        mark_item_received,
    )

    checklist = (
        db.query(ProcessChecklist)
        .filter(ProcessChecklist.process_id == body.process_id)
        .first()
    )
    if checklist is not None:
        if body.checklist_item_id:
            mark_item_received(checklist, body.checklist_item_id, db_doc.id)
        elif body.document_type:
            linked_item_id = auto_link_document(
                db, checklist, db_doc.id, body.document_type
            )
            if linked_item_id and not db_doc.checklist_item_id:
                db_doc.checklist_item_id = linked_item_id

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

    # Guard geoespacial: KML/KMZ/SHP/GeoJSON/GPX são GEOMETRIA, não documento.
    # Ficam armazenados (not_required) vinculados ao processo/imóvel, sem entrar
    # no OCR. Consumo real (parser → Property.geom) é o gap D1 (próxima frente geo).
    from app.services.geo_files import GEOSPATIAL_DOCUMENT_TYPE, is_geospatial  # noqa: PLC0415
    if is_geospatial(body.filename, body.content_type):
        from app.models.document import OcrStatus  # noqa: PLC0415
        db_doc.ocr_status = OcrStatus.not_required
        db_doc.document_type = db_doc.document_type or GEOSPATIAL_DOCUMENT_TYPE
        db.add(db_doc)
        db.commit()
        db.refresh(db_doc)
        record_document_upload(
            "client_portal" if access_context.is_client_portal else "internal", "success"
        )
        logger.info(
            "Documento #%s é geoespacial — armazenado sem OCR (gap D1) | '%s'",
            db_doc.id, body.filename,
        )
        return db_doc

    # Áudio tem leitura PRÓPRIA: transcrição (dívida #103 · ADR-060). A gravação da
    # reunião é fonte primária do caso — o que o cliente contou, o que prometeu
    # enviar, o que ficou combinado. Vira texto em `Document.extracted_text` e daí
    # herda tudo que documento já tem: entrada no diagnóstico, fonte clicável, busca.
    from app.services.audio_files import is_audio  # noqa: PLC0415
    if is_audio(body.filename, body.content_type, body.document_type):
        try:
            from app.workers.audio_tasks import transcribe_audio_document  # noqa: PLC0415
            transcribe_audio_document.delay(
                doc_id=db_doc.id,
                tenant_id=access_context.tenant_id,
                user_id=access_context.user.id,
            )
            logger.info("Pipeline de transcrição enfileirado para document_id=%s", db_doc.id)
        except Exception as exc:
            logger.warning(
                "Falha ao enfileirar transcrição para document_id=%s: %s", db_doc.id, exc
            )
        record_document_upload(
            "client_portal" if access_context.is_client_portal else "internal", "success"
        )
        logger.info(
            "Documento #%s confirmado (áudio) | tenant=%s | '%s'",
            db_doc.id, access_context.tenant_id, body.filename,
        )
        return db_doc

    # Pipeline de extração textual. PDFs passam pelo OCR cascata (pypdf → Gemini →
    # OpenAI Vision) que persiste `Document.extracted_text` antes de despachar o
    # agente extrator. Outros formatos extraíveis (imagens) caem direto no extrator
    # — ocr_pdf não rasteriza imagens isoladas.
    EXTRACTABLE_DOC_TYPES = {"matricula", "car", "ccir", "auto_infracao", "licenca"}
    if body.content_type == "application/pdf":
        try:
            from app.workers.ocr_tasks import ocr_then_extract  # noqa: PLC0415
            ocr_then_extract.delay(
                doc_id=db_doc.id,
                tenant_id=access_context.tenant_id,
                user_id=access_context.user.id,
            )
            logger.info("Pipeline OCR enfileirado para document_id=%s", db_doc.id)
        except Exception as exc:
            logger.warning("Falha ao enfileirar OCR para document_id=%s: %s", db_doc.id, exc)
    elif body.document_type and body.document_type in EXTRACTABLE_DOC_TYPES:
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
            logger.info("Agente extrator enfileirado (não-PDF) para document_id=%s", db_doc.id)
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


@router.get("/{document_id}/text", response_model=DocumentTextResponse)
def get_document_text(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
):
    """Texto lido do documento — OCR de PDF ou transcrição de áudio (ADR-060).

    Rota separada da listagem de propósito: transcrição de reunião de 30 min tem
    dezenas de milhares de caracteres, e carregar isso em toda listagem de
    documentos pagaria o custo para quem só queria ver os nomes dos arquivos.

    Interna apenas. O texto de uma reunião pode conter o que o cliente disse em
    conversa; abrir isso ao portal seria decisão de produto, não detalhe de rota.
    """
    from app.services.audio_files import TRANSCRICAO_ORIGEM_LABEL  # noqa: PLC0415

    doc_repo = DocumentRepository(db, current_user.tenant_id)
    doc = doc_repo.get_scoped(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    texto = doc.extracted_text or ""
    return DocumentTextResponse(
        document_id=doc.id,
        filename=doc.original_file_name or doc.filename,
        ocr_status=doc.ocr_status.value if doc.ocr_status else None,
        ocr_error=doc.ocr_error,
        eh_transcricao=TRANSCRICAO_ORIGEM_LABEL in texto,
        chars=len(texto),
        text=texto or None,
    )


@router.patch("/{document_id}", response_model=DocumentResponse)
def update_document(
    document_id: int,
    body: DocumentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
):
    """Edita campos do documento. Hoje: visibilidade (ADR-060, decisão 3b).

    Marcar/desmarcar "material interno" é decisão do consultor e fica registrada
    no audit do documento — o cliente deixar de ver uma peça do próprio caso não
    pode ser um evento sem rastro.
    """
    doc_repo = DocumentRepository(db, current_user.tenant_id)
    doc = doc_repo.get_scoped(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    if body.is_internal is not None and bool(doc.is_internal) != body.is_internal:
        doc.is_internal = body.is_internal
        db.add(doc)
        doc_repo.add_audit(
            user_id=current_user.id,
            document=doc,
            action="visibility_changed",
            details=(
                "Marcado como material interno (oculto no portal do cliente)"
                if body.is_internal
                else "Desmarcado como material interno (visível no portal do cliente)"
            ),
        )
        db.commit()
        db.refresh(doc)

    return doc


@router.post("/{document_id}/reprocess-ocr")
def reprocess_ocr(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
):
    """Re-dispara a LEITURA de um documento (failed ou preso). Funciona para docs de
    PROCESSO e de RASCUNHO (intake_draft) — o consultor não fica preso a um
    `failed` permanente após falha transitória (ex.: storage/region). force=True
    ignora cache e re-baixa do storage.

    PDF → OCR; áudio → transcrição (ADR-060). Mesma rota, mesmo botão na tela: do
    ponto de vista do consultor a ação é uma só, "tentar ler de novo".
    """
    from app.models.document import OcrStatus  # noqa: PLC0415
    from app.services.audio_files import is_audio  # noqa: PLC0415

    doc_repo = DocumentRepository(db, current_user.tenant_id)
    doc = doc_repo.get_scoped(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    ehaudio = is_audio(doc.filename, doc.mime_type or doc.content_type, doc.document_type)
    if not ehaudio and (doc.content_type or "") != "application/pdf":
        raise HTTPException(
            status_code=422,
            detail="Reprocesso de leitura disponível apenas para PDFs e áudios.",
        )

    doc.ocr_status = OcrStatus.processing
    doc.ocr_error = None
    db.add(doc)
    db.commit()

    task = None
    try:
        if ehaudio:
            from app.workers.audio_tasks import transcribe_audio_document  # noqa: PLC0415
            task = transcribe_audio_document.delay(
                doc_id=doc.id,
                tenant_id=current_user.tenant_id,
                user_id=current_user.id,
                draft_id=doc.intake_draft_id,
                force=True,
            )
        else:
            from app.workers.ocr_tasks import ocr_then_extract  # noqa: PLC0415
            task = ocr_then_extract.delay(
                doc_id=doc.id,
                tenant_id=current_user.tenant_id,
                user_id=current_user.id,
                draft_id=doc.intake_draft_id,
                force=True,
            )
        logger.info(
            "Reprocesso de leitura (%s) enfileirado para document_id=%s task=%s",
            "transcrição" if ehaudio else "OCR", doc.id, getattr(task, "id", None),
        )
    except Exception as exc:
        logger.warning("Falha ao enfileirar reprocesso doc=%s: %s", doc.id, exc)
        raise HTTPException(status_code=503, detail="Não foi possível enfileirar o reprocesso.") from exc

    return {
        "status": "reprocessing",
        "document_id": doc.id,
        "task_id": getattr(task, "id", None),
        "ocr_status": "processing",
    }


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
):
    """Soft-delete de documento (marca `deleted_at`). Restrito ao consultor."""
    from datetime import datetime  # noqa: PLC0415

    doc_repo = DocumentRepository(db, current_user.tenant_id)
    doc = doc_repo.get_scoped(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    doc.deleted_at = datetime.now(UTC)
    db.add(doc)
    doc_repo.add_audit(
        user_id=current_user.id,
        document=doc,
        action="deleted",
        details=f"Documento '{doc.filename or doc.original_file_name}' marcado como excluido (soft delete).",
    )
    db.commit()
    return None
