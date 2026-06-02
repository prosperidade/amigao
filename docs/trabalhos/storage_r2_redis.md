# Trabalho — Storage R2 (region) + Redis SSL + download silencioso

> Arquivo único de trabalho (padrão novo). Contexto → causa raiz provada → o que
> mudou → validação → status. Branch: `fix/storage-r2-region-redis` (base `main`).
> Data: 2026-06-01.

## Contexto (sintoma)

Intake com 1 documento "não extrai nada, sem mensagem". O OCR roda mas o
documento nunca é lido — status `no_bytes`, sem causa visível. Semanas perdidas
porque o erro real era **engolido** e reportado como `no_bytes` genérico.

Log do worker (Render):
```
SignatureDoesNotMatch ... GetObject ... Check your secret access key and signing method
ocr_then_extract: storage_key=... sem bytes (MinIO)  → status no_bytes
Falha ao publicar 'document.ocr.failed' no Redis: Invalid SSL Certificate
  Requirements Flag: CERT_REQUIRED
```

## Causa raiz (PROVADA rodando)

1. **Region errada para R2 (a causa do "não lê").** `StorageService` criava os
   clients boto3 com `region_name="us-east-1"` hardcoded. Cloudflare R2 exige
   `region="auto"`: com `us-east-1` o **scope** da assinatura SigV4
   (`.../us-east-1/s3/aws4_request`) não bate no **GET server-side** (header-auth)
   → `SignatureDoesNotMatch`. O **upload presigned** (query-auth) tolerava — por
   isso o arquivo **subia** mas nunca era **lido**. Endpoint e credenciais estavam
   corretos.
2. **Erro de download silencioso.** `download_bytes` capturava **qualquer**
   `ClientError` e retornava `b""`. O `SignatureDoesNotMatch` virava `b""` →
   `ocr_then_extract` registrava `no_bytes` (objeto ausente), mascarando a causa.
3. **Redis SSL (rediss:// Upstash).** O cliente era criado com
   `from_url(REDIS_URL)` sem tratamento de SSL. O `REDIS_URL` de prod trazia
   `?ssl_cert_reqs=CERT_REQUIRED` (nome da **constante Python**); o redis-py
   espera os tokens `none`/`optional`/`required` e aborta: *"Invalid SSL
   Certificate Requirements Flag: CERT_REQUIRED"*. Isso quebrava o evento
   realtime (preview ao vivo do OCR), não o OCR em si.
4. **Endpoint forçava http.** `minio_internal_endpoint`/`minio_public_endpoint`
   prefixavam `http://` quando a env vinha sem scheme, **ignorando**
   `MINIO_SECURE=True`. O `render.yaml` documenta a env do R2 **sem** scheme →
   ia por http. (Latente; o presign client já usava o endpoint, mas a classe de
   bug é a mesma.)

## O que mudou

| Arquivo | Mudança |
|---|---|
| `app/core/config.py` | `+ S3_REGION` (default `"auto"`). `_with_scheme()` respeita `MINIO_SECURE` (https quando secure e a env não traz scheme). Helpers de Redis: `redis_url_safe` (normaliza `ssl_cert_reqs`), `redis_is_ssl`, `celery_redis_use_ssl`. |
| `app/services/storage.py` | Os 2 clients boto3 usam `region_name=settings.S3_REGION`. `download_bytes` retorna `b""` só para `NoSuchKey`/404/NoSuchBucket; **re-levanta** `StorageDownloadError(code)` para qualquer outro erro (SignatureDoesNotMatch, AccessDenied, rede) — com log ERROR do código. |
| `app/workers/ocr_tasks.py` | Captura `StorageDownloadError` no download → marca `OcrStatus.failed`, emite evento `error=storage_error:<code>` e retorna `status=storage_error` (não `no_bytes`); **sem** retry-storm (config não se cura sozinha). `NoSuchKey` segue como `no_bytes`. |
| `app/services/notifications.py`, `app/core/metrics.py` (×2), `app/api/websockets.py` | Usam `settings.redis_url_safe`. |
| `app/core/celery_app.py` | `broker`/`backend` = `redis_url_safe`; seta `broker_use_ssl`/`redis_backend_use_ssl` **só** quando `rediss://` (`settings.celery_redis_use_ssl`). |
| `.env.example`, `render.yaml` | Documentam `S3_REGION=auto` e a normalização do `ssl_cert_reqs`. |

## Validação (rodando)

Tudo no container local (MinIO, `redis-py 7.4.0`):

1. **Region** — `StorageService().s3_client.meta.region_name == "auto"`.
2. **MinIO não regride** — round-trip real `upload_bytes` → `download_bytes`
   devolve os 19 bytes idênticos com `region=auto`. `NoSuchKey` → `b""`.
3. **Download não-silencioso** — client com secret errado → `download_bytes`
   **levanta** `StorageDownloadError(code="SignatureDoesNotMatch")` e loga ERROR
   (antes: `b""` silencioso). Esta é a classe exata do bug do R2.
4. **Redis CERT** — reproduzido: `from_url(...CERT_REQUIRED).make_connection()`
   → `RedisError: Invalid SSL Certificate Requirements Flag: CERT_REQUIRED`.
   Com `redis_url_safe` (→ `ssl_cert_reqs=required`) a conexão SSL instancia
   **sem** o erro de flag.
5. **Endpoint** — `_with_scheme("abc.r2.cloudflarestorage.com")` com
   `MINIO_SECURE=True` → `https://...`; local (`secure=False`) → `http://...`.
6. **Sem regressão local** — `celery_app.conf.broker_use_ssl` fica `False`
   (URL local é `redis://`). Testes: `test_storage_service` + `test_settings` +
   `test_ocr_tasks` = **20 passed**.

### Prova definitiva contra o R2 (rodar no Render Shell do worker pós-deploy)

```bash
python -c "
from app.services.storage import get_storage_service
s = get_storage_service()
print('region:', s.s3_client.meta.region_name)            # auto
print(len(s.download_bytes('<storage_key_real_de_um_doc>')), 'bytes')  # > 0
"
```
`bytes > 0` (sem `SignatureDoesNotMatch`) = corrigido em produção.

## Status

- ✅ Region `auto` configurável (`S3_REGION`), default cobre R2 e MinIO.
- ✅ `download_bytes` não mascara mais erro ≠ NoSuchKey.
- ✅ MinIO local não regride (round-trip provado).
- ✅ Endpoint respeita `MINIO_SECURE`.
- ✅ Redis `rediss://` publica sem erro de CERT (reprodução + fix provados local).
- ⏳ Confirmação E2E contra o R2 real: snippet pronto para o André rodar no
  Render Shell após o deploy.
- ℹ️ Não fecha a dívida **#42** (bucket presigned ausente) — bug distinto, segue
  aberta.
