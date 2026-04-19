import hashlib
import logging
import uuid
from functools import lru_cache
from threading import Lock

import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile

from app.core.config import settings

logger = logging.getLogger(__name__)

BUCKET_NAME = "amigao-docs"

class StorageService:
    _bucket_ready = False
    _bucket_lock = Lock()

    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=settings.minio_internal_endpoint,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name="us-east-1"
        )
        self.presign_client = self.s3_client
        if settings.minio_public_endpoint != settings.minio_internal_endpoint:
            self.presign_client = boto3.client(
                "s3",
                endpoint_url=settings.minio_public_endpoint,
                aws_access_key_id=settings.MINIO_ACCESS_KEY,
                aws_secret_access_key=settings.MINIO_SECRET_KEY,
                region_name="us-east-1"
            )
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        if self.__class__._bucket_ready:
            return

        with self.__class__._bucket_lock:
            if self.__class__._bucket_ready:
                return
            try:
                self.s3_client.head_bucket(Bucket=BUCKET_NAME)
            except ClientError:
                self.s3_client.create_bucket(Bucket=BUCKET_NAME)
            self.__class__._bucket_ready = True

    def _build_key(self, tenant_id: int, process_id: int, filename: str) -> str:
        ext = filename.split('.')[-1] if '.' in filename else ''
        file_uuid = str(uuid.uuid4())
        return f"tenant_{tenant_id}/process_{process_id}/{file_uuid}.{ext}" if ext else f"tenant_{tenant_id}/process_{process_id}/{file_uuid}"

    def generate_presigned_put_url(
        self,
        tenant_id: int,
        process_id: int,
        filename: str,
        content_type: str,
        expires_in: int = 300
    ) -> dict:
        """Gera presigned URL para upload direto ao MinIO (sem passar pelo servidor)."""
        key = self._build_key(tenant_id, process_id, filename)
        url = self.presign_client.generate_presigned_url(
            "put_object",
            Params={"Bucket": BUCKET_NAME, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_in,
        )
        return {"upload_url": url, "storage_key": key, "expires_in": expires_in}

    def generate_presigned_put_url_for_draft(
        self,
        tenant_id: int,
        draft_id: int,
        filename: str,
        content_type: str,
        expires_in: int = 300,
    ) -> dict:
        """Regente Cam1 — presigned URL para upload direto anexado a um rascunho."""
        ext = filename.split('.')[-1] if '.' in filename else ''
        file_uuid = str(uuid.uuid4())
        key = (
            f"tenant_{tenant_id}/draft_{draft_id}/{file_uuid}.{ext}"
            if ext
            else f"tenant_{tenant_id}/draft_{draft_id}/{file_uuid}"
        )
        url = self.presign_client.generate_presigned_url(
            "put_object",
            Params={"Bucket": BUCKET_NAME, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_in,
        )
        return {"upload_url": url, "storage_key": key, "expires_in": expires_in}

    def generate_presigned_get_url(self, storage_key: str, expires_in: int = 300) -> str:
        """Gera presigned URL para download seguro."""
        return self.presign_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": storage_key},
            ExpiresIn=expires_in,
        )

    def upload_file(self, file: UploadFile, tenant_id: int, process_id: int) -> dict:
        """Upload direto (mantido como fallback interno)."""
        key = self._build_key(tenant_id, process_id, file.filename)

        file.file.seek(0)
        content = file.file.read()
        file_size = len(content)
        checksum = hashlib.sha256(content).hexdigest()

        self.s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=content,
            ContentType=file.content_type,
        )
        return {
            "storage_key": key,
            "s3_key": key,
            "filename": file.filename,
            "original_file_name": file.filename,
            "content_type": file.content_type,
            "mime_type": file.content_type,
            "extension": file.filename.split('.')[-1] if '.' in file.filename else '',
            "file_size_bytes": file_size,
            "size": file_size,
            "checksum_sha256": checksum,
        }

    def upload_bytes(self, content: bytes, filename: str, content_type: str, tenant_id: int, process_id: int) -> dict:
        """Upload interno direto de bytes gerados pelo sistema."""
        key = self._build_key(tenant_id, process_id, filename)
        file_size = len(content)
        checksum = hashlib.sha256(content).hexdigest()

        self.s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=content,
            ContentType=content_type,
        )
        return {
            "storage_key": key,
            "filename": filename,
            "content_type": content_type,
            "file_size_bytes": file_size,
            "checksum_sha256": checksum,
        }

    def download_bytes(self, storage_key: str) -> bytes:
        """Faz o download de um arquivo do MinIO diretamente para a memória em bytes."""
        try:
            response = self.s3_client.get_object(Bucket=BUCKET_NAME, Key=storage_key)
            return response["Body"].read()
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return b""
            logger.error(f"Erro ao baixar {storage_key} do MinIO: {e}")
            return b""


@lru_cache(maxsize=1)
def get_storage_service() -> StorageService:
    return StorageService()
