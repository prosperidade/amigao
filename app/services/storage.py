import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile
import uuid
import hashlib
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

BUCKET_NAME = "amigao-docs"

class StorageService:
    def __init__(self):
        endpoint = settings.MINIO_SERVER if settings.MINIO_SERVER.startswith("http") else f"http://{settings.MINIO_SERVER}"
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name="us-east-1"
        )
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        try:
            self.s3_client.head_bucket(Bucket=BUCKET_NAME)
        except ClientError:
            self.s3_client.create_bucket(Bucket=BUCKET_NAME)

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
        url = self.s3_client.generate_presigned_url(
            "put_object",
            Params={"Bucket": BUCKET_NAME, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_in,
        )
        return {"upload_url": url, "storage_key": key, "expires_in": expires_in}

    def generate_presigned_get_url(self, storage_key: str, expires_in: int = 300) -> str:
        """Gera presigned URL para download seguro."""
        return self.s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": storage_key},
            ExpiresIn=expires_in,
        )

    def upload_file(self, file: UploadFile, tenant_id: int, process_id: int) -> dict:
        """Upload direto (mantido como fallback interno)."""
        import os
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


