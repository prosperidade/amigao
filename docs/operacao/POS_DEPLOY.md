# POS_DEPLOY.md — Runbook vivo do Regente Ambiental em produção

> Fonte de verdade pós-deploy. Documenta a stack real, bugs encontrados, fixes aplicados e métodos de debug validados em prod.
> Adicione novas seções por baixo, em ordem cronológica. Quando algo virar conhecimento estável, promova pra `RUNBOOK_OPS.md` ou ADR.

**Última atualização:** 2026-05-20

---

## 1. Stack de produção desplegada

| Camada | Provider | URL/Endpoint | Notas |
|---|---|---|---|
| Frontend (painel consultor) | **Netlify** | https://regenteambiental.com.br · https://www.regenteambiental.com.br | Vite build (`frontend/`), custom domain aponta pro Netlify |
| Backend API | **Render** (`regente-api`) | https://api.regenteambiental.com.br | FastAPI + uvicorn, Docker image |
| Worker Celery | **Render** (`regente-worker`) | (sem HTTP) | Mesma imagem do API, processo Celery |
| Banco | **Supabase Pro** | `aws-1-us-east-1.pooler.supabase.com` | Postgres + PostGIS + pgvector |
| Redis | **Upstash** | `tolerant-firefly-130414.upstash.io:6379` (TLS) | broker + cache |
| Storage | **Cloudflare R2** | `<ACCOUNT_ID>.r2.cloudflarestorage.com` · bucket `regente-docs` | S3-compat, presigned PUT direto do browser |
| E-mail | **Resend** | SMTP `smtp.resend.com:587` | Transactional only |

Templates de env vars: [.env.production.example](../../.env.production.example).
Runbook de deploy do zero: [docs/DEPLOY_REGENTE.md](../DEPLOY_REGENTE.md).

---

## 2. Env vars críticas no Render

Estas têm que estar **exatamente certas** no dashboard do Render (em ambos `regente-api` e `regente-worker`):

| Variável | Formato esperado | Como verificar |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres.<PROJ_REF>:<DB_PASSWORD>@aws-1-us-east-1.pooler.supabase.com:6543/postgres` | `curl -i $API/health` retorna 200 |
| `MIGRATE_DATABASE_URL` | mesma, porta `5432` (direto, sem pooler) | `alembic current` via Render shell |
| `REDIS_URL` | `rediss://default:<TOKEN>@...upstash.io:6379?ssl_cert_reqs=CERT_REQUIRED` | worker boot logs não trazem `ConnectionError` |
| `MINIO_SERVER` | `https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com` | curl OPTIONS preflight da §6 |
| `MINIO_PUBLIC_URL` | mesmo valor de `MINIO_SERVER` | idem |
| `MINIO_ACCESS_KEY` | 32 hex chars | sem `<` ou outros chars no começo/fim |
| `MINIO_SECRET_KEY` | **64 hex chars** | **sem `<` ou outros chars** — bug de 20/05 era exatamente isso |
| `BACKEND_CORS_ORIGINS` | CSV: `https://regenteambiental.com.br,https://www.regenteambiental.com.br` | curl OPTIONS da §5 retorna `access-control-allow-origin` |
| `SECRET_KEY` | ≥ 32 chars | sem isso API não sobe (fail-fast em `config.py`) |

**Lição (20/05):** se um secret começa com `<` ou `>`, é placeholder de markdown que entrou colado por engano. Edita e remove. A causa #4 da saga de upload foi exatamente um `<` extra no `MINIO_SECRET_KEY`.

---

## 3. CORS — duas camadas obrigatórias

O upload do navegador toca **dois servidores diferentes**, e cada um precisa do seu próprio CORS.

### 3.1. Backend API (FastAPI/Render)

- Configurado via env var `BACKEND_CORS_ORIGINS` (CSV)
- Aplicado em [app/main.py](../../app/main.py) via `CORSMiddleware` com `allow_origins=settings.cors_origins_list`
- Validator em [app/core/config.py](../../app/core/config.py) rejeita endereços locais em produção
- **Quando muda:** precisa redeploy do Render

**Origens que precisam estar lá:**
- `https://regenteambiental.com.br` (apex)
- `https://www.regenteambiental.com.br` (www)
- Qualquer subdomínio do frontend (`app.`, `portal.`) quando existir

### 3.2. Bucket R2 (Cloudflare)

- Configurado no dashboard: **R2 → bucket `regente-docs` → Settings → CORS Policy**
- JSON canônico (cola exato):

```json
[
  {
    "AllowedOrigins": ["https://regenteambiental.com.br", "https://www.regenteambiental.com.br"],
    "AllowedMethods": ["GET", "PUT", "HEAD"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

- **Quando muda:** R2 aplica na hora, sem redeploy de nada
- `AllowedHeaders: ["*"]` é necessário porque o navegador envia `Content-Type` no preflight; sem essa entrada, preflight falha

---

## 4. Boto3 + R2 — Signature V4 obrigatório

**Contexto:** Cloudflare R2 **só aceita AWS Signature V4**. Boto3 default em endpoint customizado cai em SigV2. URL gerada com SigV2 leva a 401 com mensagem `SigV2 authorization is not supported. Please use SigV4 instead.`, que **chega ao navegador como erro de CORS** (porque a resposta de erro do R2 não inclui `Access-Control-Allow-Origin`).

**Fix permanente** em [app/services/storage.py](../../app/services/storage.py):

```python
from botocore.config import Config as BotoConfig

_S3_BOTO_CONFIG = BotoConfig(
    signature_version="s3v4",     # OBRIGATÓRIO pra R2
    connect_timeout=5,
    read_timeout=10,
    retries={"max_attempts": 2, "mode": "standard"},
)
```

URL gerada com SigV4 tem `X-Amz-Algorithm=AWS4-HMAC-SHA256` e `X-Amz-Signature=...`. URL com SigV2 tem `AWSAccessKeyId=...&Signature=...&Expires=...` (formato antigo).

**Commit do fix:** `ff8726c` (20/05/2026).

---

## 5. Comandos de validação em prod (curl)

Use estes pra debugar qualquer suspeita rapidamente, **antes** de mexer em config.

### 5.1. API está viva?

```bash
curl -sS -o /dev/null -w "HTTP %{http_code} | %{time_total}s\n" https://api.regenteambiental.com.br/health
# Esperado: HTTP 200 | <0.5s
```

### 5.2. CORS do backend pro frontend está OK?

```bash
curl -sS -i -X OPTIONS https://api.regenteambiental.com.br/api/v1/documents/upload-url \
  -H "Origin: https://regenteambiental.com.br" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type,authorization"
# Esperado: HTTP 200 + access-control-allow-origin: https://regenteambiental.com.br
```

### 5.3. CORS do bucket R2 está OK?

```bash
curl -sS -i -X OPTIONS "https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com/regente-docs/test.pdf" \
  -H "Origin: https://regenteambiental.com.br" \
  -H "Access-Control-Request-Method: PUT" \
  -H "Access-Control-Request-Headers: content-type"
# Esperado: HTTP 204 + Access-Control-Allow-Origin: https://regenteambiental.com.br
# Se vier "CORS not configured for this bucket" → §3.2 não foi aplicado
```

### 5.4. Presigned URL gerada pelo backend é aceita pelo R2?

Pega uma URL real do console do navegador (DevTools → Network → request que falhou → Copy as cURL) e roda:

```bash
curl -sS -i -X PUT "<URL_PRESIGNED>" -H "Content-Type: application/pdf" --data-binary "test"
# Esperado: HTTP 200 (sem body)
# SignatureDoesNotMatch → MINIO_SECRET_KEY errado no Render
# SigV2 authorization is not supported → boto3 não está com signature_version='s3v4'
# CORS not configured → §3.2
```

---

## 6. Histórico de bugs em prod (post-mortem)

### Incidente 2026-05-20 — Upload de documentos travado (4 bugs em cascata)

**Sintoma:** sócia abriu Quadro de Ações em prod, tentou upload de PDF → UI mostrava "trava" ou erro genérico de CORS no console.

**Cascata revelada (cada fix descascava o próximo):**

| # | Causa raiz | Sintoma no navegador | Diagnóstico |
|---|---|---|---|
| 1 | `BACKEND_CORS_ORIGINS` não incluía o domínio do frontend | "blocked by CORS policy" no `/api/v1/documents/upload-url` | console mostrou origin/host na mensagem |
| 2 | Bucket R2 sem CORS Policy configurada | "blocked by CORS policy" no `r2.cloudflarestorage.com` | curl OPTIONS retornou XML `CORS not configured for this bucket` |
| 3 | boto3 gerando assinatura SigV2 (R2 só aceita SigV4) | mesma mensagem de CORS — disfarçado | curl PUT retornou XML `SigV2 authorization is not supported` |
| 4 | `<` extra colado no `MINIO_SECRET_KEY` no dashboard do Render | mesma mensagem de CORS — disfarçado | curl PUT retornou XML `SignatureDoesNotMatch` |

**Lição-mãe:** **erro "blocked by CORS policy" no navegador pode mascarar qualquer 4xx do storage.** R2 não inclui `Access-Control-Allow-Origin` em respostas de erro; navegador interpreta como CORS. Sempre rodar curl direto contra o R2 antes de assumir que o problema é CORS.

**Fixes aplicados:**
- (1) → atualizado `BACKEND_CORS_ORIGINS` no Render (dashboard, redeploy automático)
- (2) → aplicado CORS Policy no bucket via dashboard R2
- (3) → commit `ff8726c`: `signature_version="s3v4"` em `app/services/storage.py`
- (4) → editado `MINIO_SECRET_KEY` no Render, removido `<` extra

**Hardening de quebra (commit `4510e0d`):**
- Timeout no boto3 client (sem isso, qualquer hiccup do storage trava FastAPI 60s+)
- `_ensure_bucket_exists()` saiu do `__init__` — endpoint de presigned URL não bloqueia mais
- AbortController no `fetch` PUT do frontend (45s timeout)
- Mensagens de erro no frontend distinguem timeout / CORS / HTTP
- `.env.production.example` reescrito pra refletir stack real (R2 + Supabase + Upstash)
- `.gitignore` reforçado: `.env.*` bloqueado com allowlist pros `.example`

---

## 7. Pendências conhecidas em prod (sem impacto no fluxo principal)

### 7.1. WebSocket realtime (`wss://api.regenteambiental.com.br/api/v1/ws`)

**Status:** falhando em prod (browser console). Não impede upload nem fluxo de cadastro.

**Hipóteses pra investigar:**
- Render não habilita WebSocket por default em alguns planos
- CORS de WebSocket usa mecanismo diferente (Origin check no upgrade); pode precisar de allowlist específica
- Proxy intermediário (Cloudflare? Render edge?) pode estar dropando o upgrade

**Prioridade:** baixa — recurso é notification/realtime, não bloqueia operação.

### 7.2. Rotação de credenciais expostas em 19/05

Durante o deploy, secrets reais foram colados via chat e em arquivo local:
- Anthropic API key (`sk-ant-api03-...`)
- OpenAI API key (`sk-proj-...`)
- Gemini API key
- Supabase DB password
- Upstash Redis token
- R2 Access + Secret keys (parcialmente rotacionado em 20/05 ao corrigir typo)
- Resend API key

**Não é incêndio** — não foram pro Git público. Mas higiene boa de rotacionar tudo quando sobrar tempo. Ordem de urgência:

1. LLM keys (OpenAI/Anthropic/Gemini) — bots scraneiam leaks de `sk-` ativamente
2. Supabase password — acesso direto ao DB
3. Upstash token
4. Resend (pode enviar emails em nome do domínio)

Procedimento de rotação detalhado: criar memory dedicado quando for executar.

---

## 8. Próximos passos pós-fluxo de upload validado

A sócia agora consegue:
- ✅ Criar cliente no Intake
- ✅ Subir documentos no Quadro de Ações

Falta validar (não testado em prod ainda):
- [ ] Pipeline OCR + extração (`ocr_then_extract` worker) com PDF real
- [ ] Agente extrator preenchendo campos do cliente/imóvel automaticamente
- [ ] Chat com agente regulatório
- [ ] Geração de peças formais (com `requires_review=True`)
- [ ] Envio de e-mail via Resend

Quando bater bug nessas, **adicionar seção nova aqui** seguindo o template do incidente 2026-05-20.

---

## 9. Template pra próximos incidentes

```markdown
### Incidente AAAA-MM-DD — <título curto>

**Sintoma:** <o que o usuário/sócia viu>

**Causa raiz:** <bug real, não sintoma>

**Diagnóstico:** <como descobrimos — comando/log/grep que confirmou>

**Fix:** <commit hash ou config alterada>

**Lição:** <padrão pra evitar/detectar mais rápido na próxima>
```
