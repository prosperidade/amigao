import hashlib
import logging
import re
import uuid
from functools import lru_cache
from threading import Lock

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import UploadFile

from app.core.config import settings

logger = logging.getLogger(__name__)

BUCKET_NAME = "regente-docs"


class StorageKeyInvalida(ValueError):
    """A `storage_key` enviada na confirmação não é uma chave que este tenant,
    neste processo/rascunho, poderia ter recebido do backend."""


# `tenant_{id}/process_{id}/{uuid}[.ext]` ou `tenant_{id}/draft_{id}/{uuid}[.ext]`
# — exatamente o que `_build_key` e `generate_presigned_put_url_for_draft` emitem.
# Ancorado nas duas pontas: sem `..`, sem barra extra, sem prefixo de outro tenant.
_CHAVE_ESPERADA = re.compile(
    r"^tenant_(?P<tenant>\d+)/(?P<escopo>process|draft)_(?P<escopo_id>\d+)/"
    # A extensão é o que sobra do `split('.')[-1]` do nome original: o
    # `/documents` restringe pela ALLOWED_EXTENSIONS, mas o `/intake` não —
    # então aceitamos qualquer sufixo alfanumérico razoável em vez da lista.
    # O que importa para a segurança é o que está PROIBIDO: `/` (segmento extra
    # ou traversal) e `.` (segunda extensão disfarçando caminho).
    r"(?P<uuid>[0-9a-fA-F-]{36})(?:\.[A-Za-z0-9]{1,20})?$"
)


def validar_storage_key(
    storage_key: str,
    *,
    tenant_id: int,
    process_id: int | None = None,
    draft_id: int | None = None,
) -> str:
    """Confere que `storage_key` é a chave que o backend emitiria para ESTE
    chamador, neste destino. Levanta `StorageKeyInvalida` se não for.

    O upload é presigned: o backend gera a chave (`_build_key`), o cliente faz
    PUT direto no storage e depois **devolve a chave** na confirmação. Até esta
    frente a chave devolvida era persistida crua — quem conhecesse ou enumerasse
    a chave de outro tenant fazia o banco do tenant A apontar para o objeto de B,
    e o endpoint de download de A gerava presigned URL para o objeto de B.

    Por que validar em vez de derivar no backend: nada é persistido no momento
    da emissão (`generate_presigned_put_url` devolve e esquece), e a chave carrega
    um UUID aleatório — o backend não tem como reconstruí-la sozinha na
    confirmação. Derivar de verdade exige guardar a chave emitida (ou assiná-la)
    e mudar o contrato com o frontend; ficou registrado como dívida. A validação
    abaixo fecha o buraco pelo mesmo efeito prático: a chave **tem** de carregar
    o tenant de quem confirma e o processo/rascunho que está sendo confirmado,
    então nem cross-tenant nem cross-processo passam.

    Não é 404 e sim erro de entrada (400 no chamador): a chave não é uma entidade
    cuja existência se possa vazar — é um campo malformado do próprio payload.
    """
    m = _CHAVE_ESPERADA.match(storage_key or "")
    if not m:
        raise StorageKeyInvalida(
            "Chave de upload em formato inválido. Solicite uma nova URL de upload."
        )
    if int(m.group("tenant")) != tenant_id:
        raise StorageKeyInvalida(
            "Chave de upload não pertence a este tenant. Solicite uma nova URL de upload."
        )

    escopo, escopo_id = m.group("escopo"), int(m.group("escopo_id"))
    if process_id is not None:
        if escopo != "process" or escopo_id != process_id:
            raise StorageKeyInvalida(
                "Chave de upload não corresponde a este caso. Solicite uma nova URL de upload."
            )
    elif draft_id is not None:
        if escopo != "draft" or escopo_id != draft_id:
            raise StorageKeyInvalida(
                "Chave de upload não corresponde a este rascunho. "
                "Solicite uma nova URL de upload."
            )
    return storage_key


class StorageDownloadError(Exception):
    """Falha real ao baixar do storage (S3/MinIO/R2) — distinta de objeto
    ausente. Carrega o código do erro (ex.: SignatureDoesNotMatch, AccessDenied)
    para o chamador registrar a causa, em vez de mascarar como 'no_bytes'."""

    def __init__(self, storage_key: str, code: str, message: str = "") -> None:
        self.storage_key = storage_key
        self.code = code
        super().__init__(f"download '{storage_key}' falhou [{code}]: {message}".strip())

# Limita o tempo que uma chamada ao MinIO/R2 pode bloquear o request HTTP
# do FastAPI. Sem isso, falhas de rede para o endpoint S3 (R2 offline, DNS
# travado, credenciais inválidas em endpoint legacy) congelam o worker por
# 60s+ esperando os retries default do botocore.
_S3_BOTO_CONFIG = BotoConfig(
    # Cloudflare R2 só aceita Signature V4. Sem isso, boto3 gera URL com
    # SigV2 em endpoint customizado e o R2 responde 401 (mascarado como
    # erro CORS no navegador, pois a resposta de erro não traz headers
    # de Access-Control-Allow-Origin).
    signature_version="s3v4",
    connect_timeout=5,
    read_timeout=10,
    retries={"max_attempts": 2, "mode": "standard"},
)


class StorageService:
    _bucket_ready = False
    _bucket_lock = Lock()

    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=settings.minio_internal_endpoint,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=_S3_BOTO_CONFIG,
        )
        self.presign_client = self.s3_client
        if settings.minio_public_endpoint != settings.minio_internal_endpoint:
            self.presign_client = boto3.client(
                "s3",
                endpoint_url=settings.minio_public_endpoint,
                aws_access_key_id=settings.MINIO_ACCESS_KEY,
                aws_secret_access_key=settings.MINIO_SECRET_KEY,
                region_name="us-east-1",
                config=_S3_BOTO_CONFIG,
            )
        # Bucket check é LAZY — não roda no __init__ pra não bloquear
        # endpoints que só assinam URL (operação offline). Operações que
        # tocam o bucket (put/get server-side) chamam _ensure_bucket_exists()
        # explicitamente.

    def _ensure_bucket_exists(self):
        if self.__class__._bucket_ready:
            return

        with self.__class__._bucket_lock:
            if self.__class__._bucket_ready:
                return
            try:
                self.s3_client.head_bucket(Bucket=BUCKET_NAME)
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code in ("404", "NoSuchBucket", "NotFound"):
                    self.s3_client.create_bucket(Bucket=BUCKET_NAME)
                else:
                    # 403 normalmente significa que o bucket existe mas a
                    # credencial não tem head_bucket; segue mesmo assim.
                    logger.warning("head_bucket retornou %s — assumindo bucket existente.", code)
            except BotoCoreError as exc:
                # Falha de rede/timeout: não marca bucket como pronto,
                # mas também não derruba o serviço. A próxima chamada
                # tenta de novo.
                logger.error("Falha de conexão ao validar bucket %s: %s", BUCKET_NAME, exc)
                raise
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
        self._ensure_bucket_exists()
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
        self._ensure_bucket_exists()
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
        """Baixa um objeto do storage para a memória.

        Retorna ``b""`` SOMENTE quando o objeto realmente não existe (NoSuchKey).
        Qualquer outra falha (SignatureDoesNotMatch, AccessDenied, rede/timeout)
        é logada em ERROR com o código e **re-levantada** como
        ``StorageDownloadError`` — antes, todo erro virava ``b""`` silencioso e
        o OCR registrava 'no_bytes' genérico, mascarando a causa por semanas.
        """
        try:
            response = self.s3_client.get_object(Bucket=BUCKET_NAME, Key=storage_key)
            return response["Body"].read()
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404", "NoSuchBucket"):
                return b""
            logger.error(
                "download_bytes: erro %s ao baixar %s do storage: %s",
                code, storage_key, e,
            )
            raise StorageDownloadError(storage_key, code or "ClientError", str(e)) from e
        except BotoCoreError as e:
            logger.error(
                "download_bytes: falha de conexão ao baixar %s do storage: %s",
                storage_key, e,
            )
            raise StorageDownloadError(storage_key, "BotoCoreError", str(e)) from e


@lru_cache(maxsize=1)
def get_storage_service() -> StorageService:
    return StorageService()
