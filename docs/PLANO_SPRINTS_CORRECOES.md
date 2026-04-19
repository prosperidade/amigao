# Plano de Sprints de Correções — Amigão do Meio Ambiente

**Data:** 2026-04-03  
**Baseado na:** Auditoria completa de 2026-04-03  
**Esforço total estimado:** ~110 horas (~14 dias úteis)  
**Estrutura:** 7 sprints de 2 dias cada (exceto Sprint 0)

---

## Convenções

- **Aceite Mínimo** = critério binário (passa/não passa) que valida a entrega
- **Validação** = comando exato para verificar o aceite
- **Bloqueio** = o que impede avançar para o próximo sprint
- Cada sprint tem um **smoke test** de saída obrigatório
- Sprints 0-2 são **bloqueantes para produção**
- Sprints 3-6 são **recomendados antes de escala**

---

## Sprint 0 — Emergência de Segurança (4h)

> **Objetivo:** Eliminar exposição imediata de credenciais e fechar vetores de ataque triviais.
> **Bloqueante:** SIM — não avançar sem completar.

### Tarefas

| # | Tarefa | Arquivo | Esforço |
|---|--------|---------|---------|
| 0.1 | Rotacionar chave OpenAI (revogar a exposta, gerar nova) | `.env` | 15min |
| 0.2 | Rotacionar senha Gmail (app password nova) | `.env` | 15min |
| 0.3 | Remover credenciais hardcoded do Login.tsx | `frontend/src/pages/Auth/Login.tsx` L9-10 | 15min |
| 0.4 | Restringir CORS: methods e headers explícitos | `app/main.py` L87-88 | 30min |
| 0.5 | Adicionar security headers middleware | `app/main.py` (novo middleware) | 1h |
| 0.6 | Desabilitar Swagger/OpenAPI em produção | `app/main.py` L76 | 15min |
| 0.7 | Remover IP hardcoded do mobile | `mobile/src/lib/api.ts` L7 | 15min |
| 0.8 | Alterar senha default do PostgreSQL no docker-compose | `docker-compose.yml` L6 | 15min |

### Aceite Mínimo

```
□ .env NÃO contém a chave OpenAI antiga (sk-proj-zE_I7...)
□ .env NÃO contém a senha Gmail antiga (qcykudlyojpuoiwp)
□ Login.tsx: useState('') para email e password (sem defaults)
□ main.py: allow_methods lista explícita (sem "*")
□ main.py: allow_headers lista explícita (sem "*")
□ main.py: response inclui X-Frame-Options, X-Content-Type-Options
□ main.py: docs_url=None quando ENVIRONMENT != "development"
□ mobile/src/lib/api.ts: sem IP 192.168.x.x
□ docker-compose.yml: POSTGRES_PASSWORD sem default "password"
```

### Validação

```bash
# Credenciais não vazaram
grep -r "sk-proj-zE" . --include="*.py" --include="*.ts" --include="*.env" | wc -l  # deve ser 0
grep -r "qcykudly" . --include="*.py" --include="*.ts" --include="*.env" | wc -l   # deve ser 0
grep -r "192.168.1.42" . --include="*.ts" | wc -l                                   # deve ser 0

# CORS restrito
grep -n 'allow_methods' app/main.py  # deve listar ["GET","POST","PUT","PATCH","DELETE","OPTIONS"]
grep -n 'allow_headers' app/main.py  # deve listar headers específicos

# Security headers
curl -sI http://localhost:8000/health | grep -i "x-frame-options"        # DENY
curl -sI http://localhost:8000/health | grep -i "x-content-type-options" # nosniff

# Swagger desabilitado em prod
ENVIRONMENT=production python -c "from app.core.config import settings; print(settings.ENVIRONMENT)"  # production
curl -s http://localhost:8000/docs | grep -c "Swagger"  # 0 (quando ENVIRONMENT=production)

# Login sem defaults
grep "useState(" frontend/src/pages/Auth/Login.tsx | grep -v "useState('')" | grep -v "useState(false)" | wc -l  # 0

# Testes passam
pytest tests/ -q --tb=short  # 114+ passed
```

### Smoke Test de Saída

```bash
# Stack sobe sem erros
docker compose up -d && sleep 30
curl -f http://localhost:8000/health  # 200
docker compose down
```

---

## Sprint 1 — Autenticação e Tenant Isolation (8h)

> **Objetivo:** Fechar brechas de isolamento multi-tenant no JWT e WebSocket.
> **Bloqueante:** SIM — sem isso, dados de tenants podem vazar.

### Tarefas

| # | Tarefa | Arquivo | Esforço |
|---|--------|---------|---------|
| 1.1 | Adicionar validação `user.tenant_id == token.tenant_id` em `get_current_user` | `app/api/deps.py` L70 | 1h |
| 1.2 | Diferenciar exceções JWT (ExpiredSignature, JWTError, ValidationError) | `app/api/deps.py` L50-64 | 1h |
| 1.3 | Adicionar try/catch JWT + tenant validation no WebSocket | `app/api/websockets.py` L125-169 | 2h |
| 1.4 | Adicionar rate limiting no `/auth/login` (5/min por IP) | `app/api/v1/auth.py` + `app/main.py` | 2h |
| 1.5 | Adicionar response interceptor no mobile (401 → logout) | `mobile/src/lib/api.ts` | 1h |
| 1.6 | Criar teste de isolamento cross-tenant | `tests/api/test_tenant_isolation.py` (novo) | 1h |

### Aceite Mínimo

```
□ get_current_user filtra por tenant_id do token (não apenas user_id)
□ Token expirado retorna 401 (não 403 genérico)
□ Token inválido retorna 403 com mensagem distinguível
□ WebSocket rejeita token expirado com close code 1008
□ WebSocket valida tenant_id do user contra token
□ /auth/login retorna 429 após 5 tentativas em 1 minuto do mesmo IP
□ Mobile: requisição com 401 dispara logout automático
□ Teste cross-tenant: user de tenant A recebe 404 ao acessar process de tenant B
```

### Validação

```bash
# Tenant isolation no deps.py
grep -n "tenant_id" app/api/deps.py | grep -c "token_data.tenant_id"  # >= 1

# Exceções diferenciadas
grep -n "ExpiredSignatureError" app/api/deps.py | wc -l  # >= 1
grep -n "401" app/api/deps.py | wc -l                     # >= 1

# WebSocket JWT
grep -n "try:" app/api/websockets.py | wc -l  # >= 1 (wrapping jwt.decode)
grep -n "1008" app/api/websockets.py | wc -l   # >= 1

# Rate limiting
grep -rn "limiter\|slowapi\|RateLimitMiddleware" app/ | wc -l  # >= 1

# Mobile interceptor
grep -n "interceptors.response" mobile/src/lib/api.ts | wc -l  # >= 1

# Teste cross-tenant
pytest tests/api/test_tenant_isolation.py -v  # PASSED

# Regressão
pytest tests/ -q --tb=short  # 115+ passed (novo teste incluído)
```

### Smoke Test de Saída

```bash
# Login com credenciais erradas 6x → 429 na 6ª
for i in $(seq 1 6); do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/v1/auth/login \
    -d "username=wrong@test.com&password=wrong" -H "Content-Type: application/x-www-form-urlencoded")
  echo "Attempt $i: $CODE"
done
# Últimas devem retornar 429
```

---

## Sprint 2 — Integridade de Dados (8h)

> **Objetivo:** Corrigir pool de conexões, adicionar indexes críticos, corrigir N+1 queries.
> **Bloqueante:** SIM — sem isso, performance degrada sob carga.

### Tarefas

| # | Tarefa | Arquivo | Esforço |
|---|--------|---------|---------|
| 2.1 | Configurar pool_size=20, max_overflow=10, pool_recycle=3600, statement_timeout | `app/db/session.py` | 30min |
| 2.2 | Criar migration com 16 indexes compostos recomendados | `alembic/versions/` (nova migration) | 2h |
| 2.3 | Corrigir N+1 no dashboard com joinedload/selectinload | `app/api/v1/dashboard.py` L99-122 | 1.5h |
| 2.4 | Adicionar tenant_id filter em `count_incomplete_tasks` | `app/repositories/` (process_repo) | 30min |
| 2.5 | Adicionar Redis connection pool singleton | `app/services/notifications.py` | 1h |
| 2.6 | Corrigir sync destrutivo no mobile (UPSERT em vez de DELETE) | `mobile/src/services/SyncService.ts` L24-25 | 2h |
| 2.7 | Adicionar `deleted_at` ao model Document + filtrar em queries | `app/models/document.py` + migration | 30min |

### Aceite Mínimo

```
□ session.py: pool_size >= 20, pool_recycle = 3600, max_overflow >= 10
□ session.py: connect_args inclui statement_timeout (30000ms)
□ Nova migration cria >= 10 indexes compostos (processes, tasks, documents, clients, audit_logs)
□ alembic upgrade head → downgrade -1 → upgrade head: SEM ERROS
□ dashboard.py: usa joinedload ou selectinload para User em recent_activities
□ count_incomplete_tasks filtra por self.tenant_id
□ notifications.py: Redis client é singleton com ConnectionPool
□ SyncService.ts: usa INSERT ... ON CONFLICT (UPSERT), não DELETE+INSERT
□ Document model tem campo deleted_at
□ Queries de listagem de documentos filtram deleted_at IS NULL
```

### Validação

```bash
# Pool configurado
grep -n "pool_size" app/db/session.py      # >= 20
grep -n "pool_recycle" app/db/session.py   # 3600
grep -n "max_overflow" app/db/session.py   # >= 10
grep -n "statement_timeout" app/db/session.py  # presente

# Migration valida
bash ops/check_migrations.sh  # exit code 0

# N+1 corrigido
grep -n "joinedload\|selectinload" app/api/v1/dashboard.py | wc -l  # >= 1

# Tenant filter
grep -n "self.tenant_id" app/repositories/*.py | grep "count_incomplete" | wc -l  # >= 1

# Redis singleton
grep -n "ConnectionPool\|_redis_client\|get_redis_client" app/services/notifications.py | wc -l  # >= 1

# Mobile UPSERT
grep -n "ON CONFLICT" mobile/src/services/SyncService.ts | wc -l  # >= 1
grep -n "DELETE FROM tasks" mobile/src/services/SyncService.ts | wc -l  # 0

# Document soft delete
grep -n "deleted_at" app/models/document.py | wc -l  # >= 1

# Testes passam
pytest tests/ -q --tb=short  # todos passam
```

### Smoke Test de Saída

```bash
# Dashboard responde em < 500ms com dados
time curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/dashboard/summary  # 200, < 500ms
```

---

## Sprint 3 — Validação de Dados e IA (8h)

> **Objetivo:** Fechar brechas de validação em uploads, IA e transações.
> **Não-bloqueante para MVP, bloqueante para produção.**

### Tarefas

| # | Tarefa | Arquivo | Esforço |
|---|--------|---------|---------|
| 3.1 | Adicionar whitelist de extensões + validação MIME no upload | `app/api/v1/documents.py` L82 | 1.5h |
| 3.2 | Mover API keys de os.environ para passagem direta ao litellm | `app/core/ai_gateway.py` L39-46 | 1.5h |
| 3.3 | Adicionar validação de custo por tenant (limite por hora) | `app/core/ai_gateway.py` + `app/api/v1/ai.py` | 2h |
| 3.4 | Adicionar transaction boundary no intake/create-case | `app/api/v1/intake.py` | 1h |
| 3.5 | Implementar detecção de dependência circular em tasks | `app/api/v1/tasks.py` L67-71 | 1.5h |
| 3.6 | Adicionar validação de file_size_bytes (Field(gt=0, le=100MB)) | `app/schemas/document.py` | 30min |

### Aceite Mínimo

```
□ Upload de arquivo .exe retorna 400 "Extensão não permitida"
□ Upload de arquivo .pdf com content_type image/jpeg retorna 400
□ Upload de arquivo > 100MB retorna 400
□ ai_gateway.py: NENHUMA linha com os.environ["OPENAI_API_KEY"] =
□ AI endpoint retorna 429 quando custo acumulado do tenant na última hora > limite
□ intake/create-case: se criação de checklist falha, client e process NÃO são persistidos
□ Task com dependência circular (A→B→A) retorna 400
□ Schema document: file_size_bytes tem gt=0 e le=104857600
```

### Validação

```bash
# Extensão proibida
curl -s -X POST http://localhost:8000/api/v1/documents/confirm-upload \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"filename":"malware.exe","process_id":1,"content_type":"application/octet-stream","file_size_bytes":1000,"storage_key":"test"}' \
  | grep -c "não permitida"  # 1

# Sem os.environ para API keys
grep -n 'os.environ\["OPENAI' app/core/ai_gateway.py | wc -l  # 0
grep -n 'os.environ\["GEMINI' app/core/ai_gateway.py | wc -l  # 0

# Circular dependency
grep -n "circular\|has_cycle\|visited" app/api/v1/tasks.py | wc -l  # >= 1

# Transaction no intake
grep -n "db.begin\|db.rollback\|commit" app/api/v1/intake.py | wc -l  # >= 2

# Schema validation
grep -n "gt=0" app/schemas/document.py | wc -l  # >= 1

# Testes passam
pytest tests/ -q --tb=short
```

### Smoke Test de Saída

```bash
# Extensão bloqueada + upload válido funciona
# (testar manualmente via frontend ou curl)
```

---

## Sprint 4 — Auditoria e Observabilidade (8h)

> **Objetivo:** Implementar hash chain de auditoria, melhorar logs e adicionar Error Boundary no frontend.

### Tarefas

| # | Tarefa | Arquivo | Esforço |
|---|--------|---------|---------|
| 4.1 | Implementar cálculo e validação de hash chain no AuditLog | `app/models/audit_log.py` + `app/services/notifications.py` | 3h |
| 4.2 | Criar migration para hash NOT NULL + índice | `alembic/versions/` (nova migration) | 1h |
| 4.3 | Adicionar Error Boundary no frontend React | `frontend/src/components/ErrorBoundary.tsx` (novo) + `App.tsx` | 1h |
| 4.4 | Substituir alert() por toast notifications no frontend | Múltiplos arquivos (5 ocorrências) | 1.5h |
| 4.5 | Corrigir logging de DB connection string (esconder password) | `app/db/init_db.py` L22 | 15min |
| 4.6 | Adicionar `any` type fixes no client-portal (3 catch blocks) | `client-portal/src/app/` (3 arquivos) | 45min |
| 4.7 | Adicionar healthcheck do MinIO no docker-compose | `docker-compose.yml` | 30min |

### Aceite Mínimo

```
□ AuditLog: todo registro novo tem hash_sha256 NOT NULL calculado
□ AuditLog: hash_previous aponta para hash do registro anterior do mesmo tenant
□ Migration valida (up/down/up sem erro)
□ Frontend: ErrorBoundary envolve a árvore de componentes no App.tsx
□ Frontend: zero ocorrências de alert() em arquivos .tsx
□ init_db.py: log NÃO mostra password na connection string
□ client-portal: zero ocorrências de ": any" em catch blocks
□ docker-compose.yml: minio tem healthcheck configurado
```

### Validação

```bash
# Hash chain
grep -n "hash_sha256" app/models/audit_log.py | grep "nullable=False" | wc -l  # >= 1
grep -n "compute.*hash\|sha256" app/services/notifications.py app/models/audit_log.py | wc -l  # >= 1

# Migration
bash ops/check_migrations.sh  # exit 0

# Error Boundary
grep -rn "ErrorBoundary" frontend/src/ | wc -l  # >= 2 (definição + uso)

# Sem alert()
grep -rn "alert(" frontend/src/ --include="*.tsx" | grep -v "//\|emit_operational_alert\|AlertCircle\|alertas" | wc -l  # 0

# Password escondida no log
grep -n "hide_password\|render_as_string" app/db/init_db.py | wc -l  # >= 1

# Sem any no portal
grep -rn ": any" client-portal/src/ --include="*.tsx" --include="*.ts" | wc -l  # 0

# MinIO healthcheck
grep -A3 "minio:" docker-compose.yml | grep -c "healthcheck"  # >= 1

# Testes
pytest tests/ -q --tb=short
cd frontend && npx tsc --noEmit && npm run build
cd client-portal && npx tsc --noEmit && npm run build
```

---

## Sprint 5 — Frontend e Mobile Polish (8h)

> **Objetivo:** Resolver problemas de UX, acessibilidade e robustez do mobile.

### Tarefas

| # | Tarefa | Arquivo | Esforço |
|---|--------|---------|---------|
| 5.1 | Mover URLs hardcoded para env vars (vite proxy, portal URL) | `frontend/vite.config.ts` L10, `Login.tsx` L38 | 1h |
| 5.2 | Adicionar exponential backoff no mobile sync | `mobile/src/services/SyncService.ts` | 1.5h |
| 5.3 | Adicionar error handling no fetch de upload (EvidenceService) | `mobile/src/services/EvidenceService.ts` L140-146 | 1h |
| 5.4 | Tipar expo-env.d.ts com EXPO_PUBLIC_API_URL | `mobile/expo-env.d.ts` | 15min |
| 5.5 | Adicionar input validation no login mobile (empty check) | `mobile/app/login.tsx` | 30min |
| 5.6 | Substituir divs clicáveis por buttons com keyboard support | `frontend/src/pages/Dashboard/index.tsx` + modais | 1.5h |
| 5.7 | Adicionar focus trap em modais do frontend | Componentes de modal | 1h |
| 5.8 | Memoizar timeAgo() no Dashboard | `frontend/src/pages/Dashboard/index.tsx` L95-101 | 30min |
| 5.9 | Adicionar metadata por página no client-portal | `client-portal/src/app/` (3 rotas) | 45min |

### Aceite Mínimo

```
□ vite.config.ts: proxy target usa process.env ou variável, não string literal 127.0.0.1
□ Login.tsx: URL do portal vem de import.meta.env, não hardcoded
□ SyncService.ts: retry com backoff exponencial (delay * 2^attempt)
□ EvidenceService.ts: fetch wrapped em try/catch com fallback
□ expo-env.d.ts: declara EXPO_PUBLIC_API_URL como string opcional
□ Login mobile: botão desabilitado quando email ou password vazio
□ Dashboard: elementos clicáveis são <button>, não <div onClick>
□ Modais: focus trap ativo (Tab não sai do modal)
□ timeAgo: memoizado com useMemo ou extraído para hook
□ client-portal: cada rota /dashboard/* tem metadata própria
```

### Validação

```bash
# URLs não hardcoded
grep -rn "127.0.0.1\|localhost:3000" frontend/src/ --include="*.tsx" --include="*.ts" | \
  grep -v "node_modules\|.env\|// " | wc -l  # 0

# Backoff no mobile
grep -n "backoff\|Math.pow\|exponential" mobile/src/services/SyncService.ts | wc -l  # >= 1

# Evidence error handling
grep -n "try {" mobile/src/services/EvidenceService.ts | wc -l  # >= 3

# Env types
grep -n "EXPO_PUBLIC_API_URL" mobile/expo-env.d.ts | wc -l  # >= 1

# Accessibility
grep -rn "<div.*onClick" frontend/src/pages/Dashboard/index.tsx | wc -l  # 0

# Builds passam
cd frontend && npm run build
cd client-portal && npm run build
```

---

## Sprint 6 — CI/CD e Testes (8h)

> **Objetivo:** Expandir CI, adicionar cobertura mínima e testes E2E básicos.

### Tarefas

| # | Tarefa | Arquivo | Esforço |
|---|--------|---------|---------|
| 6.1 | Adicionar job de frontend (build + lint) no CI | `.github/workflows/ci.yml` | 1h |
| 6.2 | Adicionar job de client-portal (build + lint) no CI | `.github/workflows/ci.yml` | 1h |
| 6.3 | Adicionar threshold de cobertura mínima (70%) no pytest | `pyproject.toml` + CI | 30min |
| 6.4 | Criar teste E2E: fluxo completo de intake (client → process → checklist) | `tests/e2e/test_intake_flow.py` (novo) | 2h |
| 6.5 | Criar teste E2E: upload de documento + confirmação | `tests/e2e/test_document_flow.py` (novo) | 1.5h |
| 6.6 | Criar teste de WebSocket (conexão + desconexão + auth) | `tests/api/test_websockets.py` (novo) | 1.5h |
| 6.7 | Adicionar validação de password strength no schema de User | `app/schemas/user.py` | 30min |

### Aceite Mínimo

```
□ CI: push no main roda lint + test + migration + frontend build + portal build
□ CI: falha se cobertura < 70%
□ test_intake_flow.py: cria client, process e checklist em sequência; verifica dados persistidos
□ test_document_flow.py: gera presigned URL, simula upload, confirma; verifica document no DB
□ test_websockets.py: conecta com token válido (aceita), conecta com token expirado (rejeita)
□ Password com < 8 chars retorna 422; password com >= 8 chars aceita
□ Todos os testes passam (120+ testes)
```

### Validação

```bash
# CI jobs
grep -c "frontend\|client-portal" .github/workflows/ci.yml  # >= 2

# Coverage threshold
grep -n "cov-fail-under\|--cov-fail-under=70" .github/workflows/ci.yml pyproject.toml | wc -l  # >= 1

# Novos testes existem
ls tests/e2e/test_intake_flow.py tests/e2e/test_document_flow.py tests/api/test_websockets.py  # existem

# Password validation
grep -n "password.*len\|min_length\|@field_validator.*password" app/schemas/user.py | wc -l  # >= 1

# Testes passam com cobertura
pytest tests/ -q --cov=app --cov-fail-under=70
```

---

## Sprint 7 — Hardening Final (8h)

> **Objetivo:** Fechar itens restantes de médio risco e preparar para produção.

### Tarefas

| # | Tarefa | Arquivo | Esforço |
|---|--------|---------|---------|
| 7.1 | Adicionar CASCADE/SET NULL nas FK constraints (migration) | Nova migration | 2h |
| 7.2 | Adicionar unique constraint em properties(tenant_id, registry_number) | Nova migration | 30min |
| 7.3 | Implementar webhook retry com Celery (ao invés de fire-and-forget) | `app/core/alerts.py` + novo worker task | 1.5h |
| 7.4 | Adicionar expire_on_commit=False no SessionLocal | `app/db/session.py` | 15min |
| 7.5 | Adicionar validação de status transitions no schema (não apenas no router) | `app/schemas/process.py` | 1h |
| 7.6 | Configurar Redis com autenticação no docker-compose | `docker-compose.yml` | 30min |
| 7.7 | Adicionar timeout no Celery tasks (soft_time_limit) | `app/workers/tasks.py` + outros workers | 1h |
| 7.8 | Documentar runbook de deploy em produção | `docs/DEPLOY_PRODUCAO.md` (novo) | 1.5h |

### Aceite Mínimo

```
□ FK constraints têm ON DELETE CASCADE ou SET NULL explícito (migration válida)
□ properties: unique(tenant_id, registry_number) existe
□ Webhook retry: task Celery com max_retries=3 e retry_backoff=True
□ SessionLocal: expire_on_commit=False
□ ProcessCreate: status inicial deve ser 'lead' ou 'triagem' (validado no schema)
□ Redis: requirepass configurado no docker-compose
□ Workers: soft_time_limit definido em todas as tasks (≤ 300s)
□ docs/DEPLOY_PRODUCAO.md: existe com checklist de deploy
□ Migration valida (up/down/up)
□ Todos os testes passam
```

### Validação

```bash
# CASCADE
grep -rn "ondelete" app/models/*.py | wc -l  # >= 5

# Unique constraint
grep -rn "registry_number.*unique\|UniqueConstraint.*registry" alembic/versions/*.py | wc -l  # >= 1

# Webhook retry
grep -n "max_retries\|retry_backoff" app/workers/*.py app/core/alerts.py | wc -l  # >= 1

# Session config
grep -n "expire_on_commit" app/db/session.py  # False

# Redis auth
grep -n "requirepass\|REDIS_PASSWORD" docker-compose.yml | wc -l  # >= 1

# Celery timeout
grep -n "soft_time_limit" app/workers/*.py | wc -l  # >= 2

# Runbook
test -f docs/DEPLOY_PRODUCAO.md && echo "OK"  # OK

# Migration + testes
bash ops/check_migrations.sh
pytest tests/ -q --cov=app --cov-fail-under=70
```

---

## Resumo Visual

```
Sprint 0 ──→ Sprint 1 ──→ Sprint 2 ──→ Sprint 3 ──→ Sprint 4 ──→ Sprint 5 ──→ Sprint 6 ──→ Sprint 7
(4h)         (8h)         (8h)         (8h)         (8h)         (8h)         (8h)         (8h)
Emergência   Auth/Tenant  DB/Perf      Validação    Auditoria    Frontend     CI/Testes    Hardening
BLOQUEANTE   BLOQUEANTE   BLOQUEANTE   PRODUÇÃO     PRODUÇÃO     QUALIDADE    QUALIDADE    PRODUÇÃO
```

| Marco | Após Sprint | Estado |
|-------|-------------|--------|
| **MVP Seguro** | Sprint 2 | Pode rodar em ambiente controlado (piloto) |
| **Produção Mínima** | Sprint 4 | Pode receber clientes reais com monitoramento |
| **Produção Confiável** | Sprint 7 | Pronto para escala com CI/CD e observabilidade |

---

## Checklist de Validação Global (pós-Sprint 7)

```bash
# 1. Segurança
grep -rn "sk-proj-\|qcykudly\|192.168" . --include="*.py" --include="*.ts" --include="*.env" | wc -l  # 0
curl -sI http://localhost:8000/health | grep "X-Frame-Options"  # DENY
curl -s http://localhost:8000/docs  # 404 ou redirect (prod)

# 2. Banco de dados
bash ops/check_migrations.sh  # exit 0
grep -c "pool_size" app/db/session.py  # >= 1

# 3. Testes
pytest tests/ -q --cov=app --cov-fail-under=70  # ALL PASSED, >= 70% coverage

# 4. Frontend builds
cd frontend && npm run build && npm run lint  # exit 0
cd client-portal && npm run build  # exit 0

# 5. CI
cat .github/workflows/ci.yml | grep -c "jobs:"  # >= 1 (pipeline existe)

# 6. Docker stack completa
docker compose up -d && sleep 45
curl -f http://localhost:8000/health       # 200
curl -f http://localhost:3000              # 200 (portal)
docker compose down
```
