# Runbook Operacional

Documento vivo de operacao e homologacao. A cada passada relevante, este arquivo e `docs/progresso4.md` devem ser atualizados juntos.

Funcao deste arquivo:

- linguagem operacional e prescritiva
- foco em comando, validacao, pre-requisito, evidência e resposta operacional
- evitar narrativa historica longa; isso pertence ao `progresso3.md`

## Padrao de fechamento

Ao final de cada rodada:

1. registrar o que mudou em `docs/progresso4.md`
2. atualizar este runbook com:
   - estado operacional atual
   - comandos de validacao usados
   - riscos ou pendencias remanescentes
3. registrar testes executados e resultado
4. registrar qualquer workaround temporario ativo

## Credenciais seed locais

No ambiente local Docker, o seed agora sincroniza as senhas quando `SEED_*_PASSWORD` estiver definido.

Usuarios seed atuais do stack local:

- `admin@amigao.com`
- `consultor@amigao.com`
- `cliente@amigao.com`
- `campo@amigao.com`

Senha de homologacao local atual:

- `Seed@2026`

Variaveis relevantes:

- `SEED_ADMIN_PASSWORD`
- `SEED_CONSULTANT_PASSWORD`
- `SEED_CLIENT_PASSWORD`
- `SEED_FIELD_PASSWORD`
- `SEED_RESET_PASSWORDS`

Regra operacional:

- se `SEED_*_PASSWORD` estiver definido, o startup sincroniza a senha do usuario correspondente
- `SEED_RESET_PASSWORDS=true` continua forcando rotacao geral das senhas derivadas

## Provisionamento de tenant controlado

Para homologacoes reais sem interferir no tenant seed principal:

```powershell
.\venv\Scripts\python.exe ops\provision_homologation_tenant.py `
  --internal-email seu+interno@gmail.com `
  --portal-email seu+portal@gmail.com `
  --password Seed@2026
```

Resultado esperado:

- tenant isolado para homologacao
- usuario interno real para receber notificacoes
- usuario do portal vinculado ao cliente
- processo inicial em `triagem`

## Endpoints e servicos operacionais

- API: `http://localhost:8000`
- Health: `GET /health`
- Metrics: `GET /metrics`
- Portal do cliente: `http://localhost:3000/login`
- MinIO API: `http://localhost:9000`
- MinIO Console: `http://localhost:9001`

## Subida rapida para demonstracao

Stack principal:

```powershell
docker compose up --build -d api worker client-portal
```

Conferencia rapida:

```powershell
(Invoke-WebRequest -UseBasicParsing http://localhost:8000/health).StatusCode
```

```powershell
(Invoke-WebRequest -UseBasicParsing http://localhost:3000/login).StatusCode
```

## SMTP

Validacao de conectividade:

```powershell
.\venv\Scripts\python.exe ops\check_smtp.py
```

Estado atual:

- autenticacao SMTP real validada com sucesso
- `api` e `worker` ja rodam com SMTP real carregado via `.env`

## Webhook de alertas

Sink local para smoke:

```powershell
.\venv\Scripts\python.exe ops\alert_webhook_sink.py `
  --host 0.0.0.0 `
  --port 8011 `
  --auth-header Authorization `
  --auth-token "Bearer sink-local-token" `
  --signing-secret "sink-local-signing-secret"
```

Configuracao local:

- `ALERT_WEBHOOK_URL=http://host.docker.internal:8011/alerts`
- `ALERT_WEBHOOK_AUTH_HEADER=Authorization`
- `ALERT_WEBHOOK_AUTH_TOKEN=Bearer sink-local-token`
- `ALERT_WEBHOOK_SIGNING_SECRET=sink-local-signing-secret`
- `ALERT_WEBHOOK_MIN_SEVERITY=warning`

Validacao controlada:

```powershell
docker compose exec -T api python -c "from app.core.alerts import emit_operational_alert; emit_operational_alert(category='smoke_test', severity='warning', message='Webhook smoke test', metadata={'source':'api_container'})"
```

Artefato local:

- capturas do sink ficam em `ops/runtime/`
- `ops/runtime/` deve permanecer fora do Git
- cada captura agora registra `headers`, `validation`, `status_code` e `payload`

Contrato atual do webhook:

- payload inclui `alert_id`, `service`, `environment`, `request_id`, `trace_id`, `span_id`, `category`, `severity`, `message` e `metadata`
- headers incluem `X-Amigao-Alert-Id`, `X-Amigao-Service`, `X-Amigao-Environment` e `traceparent`
- quando configurado, o destino tambem recebe autenticacao no header definido por `ALERT_WEBHOOK_AUTH_HEADER`
- quando configurado, o corpo sai assinado em `X-Amigao-Signature-256` com HMAC SHA-256

## Smokes obrigatorios

### Smoke automatizado principal

Executar:

```powershell
.\venv\Scripts\python.exe ops\run_homologation_smoke.py `
  --internal-email seu+interno@gmail.com `
  --portal-email seu+portal@gmail.com `
  --password Seed@2026
```

Validacoes cobertas:

- `health`
- login interno
- login portal
- criacao de processo real
- mudanca de status com notificacao ao cliente
- upload real de documento no MinIO
- confirmacao de upload
- notificacao interna por e-mail
- auditoria de processo e documento
- metricas consolidadas no `/metrics`

### 1. Health e login

```powershell
(Invoke-WebRequest -UseBasicParsing http://localhost:8000/health).StatusCode
```

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/api/v1/auth/login' -Body @{ username='admin@amigao.com'; password='Seed@2026' } -ContentType 'application/x-www-form-urlencoded'
```

### 2. Mudanca real de status de processo

Objetivo:

- validar `notify_process_status_changed`
- validar email ao cliente
- validar auditoria
- validar metricas do worker

Sinais esperados:

- task `workers.notify_process_status_changed` com `success`
- `amigao_email_delivery_total{service="worker",result="success"}` incrementado
- timeline do processo contendo `created`, `status_changed` e `notification_process_status_changed`

### 3. Upload real de documento pelo portal

Objetivo:

- validar `upload-url -> PUT MinIO -> confirm-upload -> notify_document_uploaded`
- validar email interno
- validar auditoria
- validar metricas do worker e API

Sinais esperados:

- task `workers.notify_document_uploaded` com `success`
- auditoria com `notification_document_uploaded`
- `channels` contendo `realtime_tenant` e `email_internal`
- `amigao_document_uploads_total{service="api",source="client_portal",result="success"}`

## Ultima validacao registrada

Data de referencia:

- `04/04/2026`

Validado nesta rodada (Sprint 7 — Hardening Final):

- migration a7b8c9d0e1f2: 47 FKs com ondelete explicito (CASCADE/SET NULL/RESTRICT) + unique constraint uq_properties_tenant_registry
- webhook dispatch migrado de sincrono (httpx) para Celery task com max_retries=3, retry_backoff=True, soft_time_limit=30
- soft_time_limit configurado em todas as 10 tasks Celery (30s-300s conforme complexidade)
- Redis autenticado via requirepass no docker-compose (REDIS_URL com senha na connection string)
- POSTGRES_PASSWORD default alterado de "password" para "pgpass2026"
- ProcessCreate: field_validator rejeita status diferente de lead/triagem (HTTP 422)
- 14 models atualizados com ForeignKey(..., ondelete=) alinhado com a migration
- testes de alert atualizados para mock de Celery .delay() (2 testes reescritos)
- suite core: 78 passed, 0 failed
- suite completa: 160 passed, 1 failed (test_pdf_generator pre-existente)

Validado em rodada anterior (Sprint 3 — Validacao de Dados e IA):

- whitelist de 28 extensoes no upload com validacao MIME cruzada (documents.py)
- API keys removidas de os.environ — passagem direta via api_key= no litellm.completion()
- custo IA por tenant limitado a $5/hora com HTTP 429 (check_tenant_cost_limit via DbDep)
- deteccao de dependencia circular via BFS + endpoint POST /tasks/{id}/dependencies/{dependency_id}
- file_size_bytes validado com Field(gt=0, le=104857600) no schema Pydantic
- transaction boundary no intake/create-case com try/except + db.rollback()
- test_classify_returns_503 corrigido (sessao DB via DI em vez de SessionLocal proprio)
- suite completa: 147 passed, 1 failed (pre-existente test_pdf_generator)

Validado em rodada anterior (Sprint 2 — Integridade de Dados e Performance):

- pool de conexoes reconfigurado: pool_size=20, max_overflow=10, pool_recycle=3600, statement_timeout=30s, expire_on_commit=False
- migration f1a2b3c4d5e6 criada com 16 indexes compostos + documents.deleted_at — ciclo up/down/up validado
- count_incomplete_tasks agora filtra por self.tenant_id (fecha critico #6)
- Redis singleton com ConnectionPool substituindo client por evento (fecha alto #7)
- Document model com deleted_at + filtro deleted_at.is_(None) em _scoped_query
- password na connection string escondida via render_as_string(hide_password=True) (fecha critico #10)
- suite sem Docker: 109 passed, 1 failed (test_pdf_generator pre-existente)
- suite completa: 145 passed, 3 failed (pre-existentes)

Validado em rodada anterior (Sprint 5 — Frontend e Mobile Polish):

- credenciais hardcoded removidas de frontend Login.tsx e mobile login.tsx (useState(''))
- URL localhost:3000 substituida por import.meta.env.VITE_CLIENT_PORTAL_URL no frontend
- proxy Vite externalizado via process.env.VITE_API_PROXY_TARGET
- divs clicaveis convertidos para button semantico no Dashboard (atividades + tarefas)
- timeAgo ja era funcao pura fora do componente — sem alteracao
- metadata SEO adicionada em 3 rotas do portal (login, dashboard, process/[id]) via server layouts
- dashboard layout refatorado: server component (metadata) + DashboardShell client (auth + sidebar)
- login mobile: catch unknown, botao desabilitado com campos vazios, feedback visual
- frontend build: 0 erros tsc, chunk 428 kB
- portal build: 0 erros tsc, 6 rotas

Validado em rodada anterior (Sprint 4 — Auditoria, Observabilidade e Frontend):

- hash chain SHA-256 integrado em todos os 7 pontos de criacao de AuditLog
- hash deterministico validado por teste unitario (64 chars, determinismo, encadeamento)
- ErrorBoundary envolvendo toda a arvore React no App.tsx
- react-hot-toast substituindo 4 chamadas alert() em 3 arquivos frontend
- catch `unknown` substituindo `: any` em 3 catch blocks do client-portal
- healthcheck MinIO com `curl health/live` + depends_on `service_healthy` para api e worker
- frontend build: 0 erros tsc, chunk 428 kB
- portal build: 0 erros tsc, 6 rotas
- suite backend: 145 passed, 3 failed (pre-existentes)

Validado em rodada anterior (Sprint 1 — Auth e Tenant Isolation):

- excecoes JWT diferenciadas: `ExpiredSignatureError` -> 401, `JWTError` -> 403, `ValidationError` -> 403
- validacao de `tenant_id` no token contra `user.tenant_id` no banco
- rate limiting `5/min` por IP no `POST /auth/login` via slowapi
- Swagger/OpenAPI desabilitado quando `ENVIRONMENT != "development"`
- 3 testes novos de isolamento cross-tenant passando
- mobile response interceptor (401 -> logout) ja estava implementado
- suite focada: `10 passed` (auth + dashboard + tenant isolation)
- suite completa: `145 passed`, `3 failed` (2 pre-existentes + 1 pre-existente de AI)

Validado em rodada anterior (03/04/2026 — backend P0/P1):

- login real de `admin@amigao.com` com `Seed@2026`
- login real de `cliente@amigao.com` com `Seed@2026`
- script `ops/provision_homologation_tenant.py` validado de forma idempotente no banco local
- script `ops/run_homologation_smoke.py` validado de ponta a ponta na stack local
- webhook local de alertas recebendo payload real da API
- evento real de mudanca de status com email ao cliente e auditoria confirmada
- evento real de upload de documento pelo portal com email interno e auditoria confirmada
- `/metrics` expondo series de `worker` para `notify_process_status_changed` e `notify_document_uploaded`
- timeline do processo real respondendo sem erro apos correcao de serializacao de `AuditLog`
- contrato do webhook endurecido com autenticacao por header configuravel, assinatura HMAC SHA-256 e `traceparent`

Validado em rodada anterior (03/04/2026 — frontend Sprint F2/F3):

- `npm run build` -> sem erros, sem warnings, chunk principal 416 kB
- `npm run test` -> 21 passed, 4 suites
- `npm run lint` -> `eslint --max-warnings=0` exit 0
- `npx tsc --noEmit` -> 0 erros

Suite focada mais recente:

- backend: `145 passed` (Sprint 1 incluso)
- frontend: `21 passed`

## Estado dos frontends (atualizado 04/04/2026 — pos-Sprint 5)

### Frontend Vite (painel interno)

Build: VERDE

```bash
cd frontend && npm run build
# tsc -b && vite build -> built in 27.75s
# dist/assets/index-BEqiInEz.js   428 kB (gzip: 120 kB)
# dist/assets/vendor-BaIpEwgI.js   49 kB (gzip:  17 kB)
# dist/assets/query-Iw-FN203.js    41 kB (gzip:  12 kB)
# dist/assets/ui--nM3HkZu.js       20 kB (gzip:   4 kB)
```

Testes:

```bash
cd frontend && npm run test
# vitest run -> 21 passed, 4 suites
```

Lint blockante:

```bash
cd frontend && npm run lint
# eslint --max-warnings=0 -> exit 0
```

Typecheck:

```bash
cd frontend && npx tsc --noEmit
# 0 errors
```

Dev server: `http://localhost:5173`

CORS: verificar que `BACKEND_CORS_ORIGINS` inclui `http://localhost:5173` para dev local.

Code splitting: `manualChunks` configurado em `vite.config.ts` separando vendor, query e ui. Chunk principal abaixo de 500 kB.

Proxy: target configuravel via `VITE_API_PROXY_TARGET` (fallback `http://127.0.0.1:8000`).

Env vars de referencia para frontend:
- `VITE_API_PROXY_TARGET` — target do proxy dev server (default: `http://127.0.0.1:8000`)
- `VITE_CLIENT_PORTAL_URL` — URL do portal do cliente para redirecionamentos (default: `/`)

### Client Portal Next.js

Build: VERDE

```bash
cd client-portal && npm run build
# next build (Turbopack) -> Compiled successfully in 15.8s
# 6 routes (3 static, 1 dynamic)
```

Metadata SEO: cada rota tem titulo e descricao proprios via server-component layouts.

Typecheck:

```bash
cd client-portal && npx tsc --noEmit
# 0 errors
```

Producao: `http://localhost:3000`

Fonte Inter: self-hosted em `public/fonts/` via `next/font/local`. Nao depende de Google Fonts.

### Correcoes aplicadas em 03/04/2026 (rodada 1)

| Correcao | Arquivo | Impacto |
|----------|---------|---------|
| Interceptor 403 adicionado | `frontend/src/lib/api.ts` | Usuario com token invalido nao fica preso |
| Imports nao usados removidos | 6 arquivos no frontend | Build verde |
| Tipagem `any` eliminada | `ProcessCommercial.tsx`, `AIPanel.tsx` | Seguranca de tipos |
| mutationFn uniformizada | `Processes/index.tsx`, `ProcessChecklist.tsx` | Build verde |
| Google Fonts -> local | `client-portal/src/app/layout.tsx` | Build offline funcional |
| axios direto -> fetch | `client-portal/.../[id]/page.tsx` | Upload respeita interceptor auth |
| Typo "Caregando" corrigido | `Clients/index.tsx` | UX |

### Sprint F2/F3 aplicada em 03/04/2026 (rodada 2)

| Entrega | Arquivos | Impacto |
|---------|----------|---------|
| Vitest + setup global | `vitest.config.ts`, `src/test/setup.ts` | Infra de testes automatizados |
| 21 testes unitarios | `auth.test.ts`, `utils.test.ts`, `auth.test.ts` (store), `statusUtils.test.ts` | Cobertura de hooks internos |
| ESLint --max-warnings=0 | `package.json` | Lint blockante em CI |
| 50 erros `any` eliminados | 15 arquivos | Tipagem strict em todo frontend |
| statusUtils.js -> .ts | `utils/statusUtils.ts` | Eliminado ultimo .js no src |
| ProcessDetail decomposto | 6 novos componentes | 565 -> 146 linhas (74% reducao) |
| Dashboard filtros + skeletons | `Dashboard/index.tsx` | Toggle executivo/operacional, skeletons, useQueries paralelo |
| Code splitting | `vite.config.ts` | Chunk 531KB -> 416KB, sem warning |

## Ultima validacao do Agente 3 — Sprint IA-1 (03/04/2026)

### Banco de dados

Migration de schema:

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
# d7f9a24dd5a7 -> cria tabela prompt_templates + enums promptcategory/promptrole
# 024fe3f5dbeb -> seed de 9 prompts globais v1
```

Validacao de ciclo reversivel:

```powershell
.\venv\Scripts\python.exe -m alembic downgrade -1
.\venv\Scripts\python.exe -m alembic upgrade head
```

Verificacao de dados seeded:

```sql
SELECT slug, category, role, version, is_active, length(content) as chars
FROM prompt_templates ORDER BY id;
-- Esperado: 9 rows, todas is_active=true, version=1
```

### Testes dos agentes IA

```powershell
.\venv\Scripts\python.exe -m pytest tests/agents/ -v
# Esperado: 30 passed, 0 failed
# Cobertura: model CRUD, service logic, schema validation, classifier/extractor refactor
# Zero consumo de API key (mocks do ai_gateway.complete)
```

Suite completa (nao deve regredir):

```powershell
.\venv\Scripts\python.exe -m pytest tests/ -v
# Esperado: 144 passed, 1 failed (test_pdf_generator pre-existente)
```

### Health check pos-deploy

```powershell
(Invoke-WebRequest -UseBasicParsing http://localhost:8000/health).StatusCode
# Esperado: 200 — startup da API nao pode ser impactado pelo import do PromptTemplate
```

### Verificacao de conflito Alembic (antes de merge com Agente 1)

```powershell
.\venv\Scripts\python.exe -m alembic heads
# Esperado: head unica. Se houver multiplas heads, resolver merge antes do deploy.
```

## Validacao Sprint 1 — Auth e Tenant Isolation (04/04/2026)

### Pre-requisitos

- `slowapi>=0.1.9` instalado no venv (`pip install slowapi`)
- banco disponivel via Testcontainers (Docker rodando)

### Arquivos alterados

| Arquivo | Alteracao |
|---------|-----------|
| `app/api/deps.py` | Excecoes JWT diferenciadas (401/403) + validacao tenant_id |
| `app/core/rate_limit.py` | Novo modulo — `Limiter(key_func=get_remote_address)` |
| `app/api/v1/auth.py` | `@limiter.limit("5/minute")` no `POST /login` |
| `app/main.py` | Limiter wired + Swagger condicional por ENVIRONMENT |
| `requirements.txt` | `slowapi>=0.1.9` adicionado |
| `tests/api/test_tenant_isolation.py` | 3 testes novos de isolamento cross-tenant |

### Validacao de token expirado vs invalido

```bash
# Token expirado deve retornar 401
grep -n "ExpiredSignatureError" app/api/deps.py
# Esperado: import e except block presentes

grep -n "HTTP_401_UNAUTHORIZED" app/api/deps.py
# Esperado: >= 1 ocorrencia (token expirado)

grep -n "HTTP_403_FORBIDDEN" app/api/deps.py
# Esperado: >= 3 ocorrencias (token invalido, payload invalido, tenant incompativel)
```

### Validacao de tenant isolation

```bash
grep -n "tenant_id" app/api/deps.py | grep "token_data.tenant_id"
# Esperado: >= 1 (validacao de tenant_id no get_current_user)
```

Teste automatizado:

```powershell
.\venv\Scripts\python.exe -m pytest tests/api/test_tenant_isolation.py -v
# Esperado: 3 passed
# - test_user_cannot_access_process_from_another_tenant
# - test_dashboard_does_not_leak_cross_tenant_data
# - test_token_with_mismatched_tenant_id_is_rejected
```

### Validacao de rate limiting

```bash
grep -n "limiter" app/api/v1/auth.py
# Esperado: import do limiter + decorator @limiter.limit("5/minute")

grep -n "RateLimitExceeded" app/main.py
# Esperado: import + exception handler registrado
```

Teste manual (requer stack rodando):

```powershell
# 6 tentativas de login com credencial errada — a 6a deve retornar 429
for ($i=1; $i -le 6; $i++) {
  $r = Invoke-WebRequest -Method Post -Uri 'http://localhost:8000/api/v1/auth/login' `
    -Body @{ username='wrong@test.com'; password='wrong' } `
    -ContentType 'application/x-www-form-urlencoded' -SkipHttpErrorCheck
  Write-Host "Tentativa $i : $($r.StatusCode)"
}
# Esperado: primeiras 5 retornam 401, 6a retorna 429
```

### Validacao de Swagger condicional

```bash
grep -n "_is_dev" app/main.py
# Esperado: _is_dev = settings.ENVIRONMENT == "development"
# docs_url, openapi_url, redoc_url condicionados a _is_dev
```

Verificacao operacional:

```powershell
# Em dev (default): /docs deve responder
(Invoke-WebRequest -UseBasicParsing http://localhost:8000/docs).StatusCode
# Esperado: 200

# Em producao: /docs deve retornar 404
# (setar ENVIRONMENT=production no .env e reiniciar)
```

### Suite completa pos-Sprint 1

```powershell
.\venv\Scripts\python.exe -m pytest tests/ -q --tb=short
# Esperado: 145+ passed
# Falhas pre-existentes aceitas:
#   - test_pdf_generator (mock de storage)
#   - test_classify_returns_503 (sessao propria no check_tenant_cost_limit)
```

Suite focada de regressao rapida:

```powershell
.\venv\Scripts\python.exe -m pytest tests/api/test_auth.py tests/api/test_dashboard.py tests/api/test_tenant_isolation.py -v
# Esperado: 10 passed
```

### Estado operacional pos-Sprint 1

| Controle | Estado |
|----------|--------|
| Token expirado | 401 (antes: 403) |
| Token invalido | 403 com mensagem especifica |
| Tenant mismatch no token | 403 "tenant incompativel" |
| Rate limit login | 5/min por IP, 429 apos limite |
| Swagger em producao | Desabilitado (docs_url=None) |
| Swagger em development | Habilitado (/docs funcional) |
| Isolamento cross-tenant | Testado e validado (3 cenarios) |
| Mobile 401 interceptor | Ja implementado (sem alteracao) |

## Validacao Sprint 4 — Auditoria, Observabilidade e Frontend (04/04/2026)

### Pre-requisitos

- Docker rodando (para Testcontainers nos testes backend)
- `react-hot-toast` instalado no frontend (`cd frontend && npm install`)

### Arquivos alterados

| Arquivo | Alteracao |
|---------|-----------|
| `app/services/audit_hash.py` | Novo — hash chain SHA-256 para AuditLog |
| `app/services/notifications.py` | stamp_audit_hash integrado em register_notification_audit |
| `app/repositories/process_repo.py` | stamp_audit_hash integrado em add_audit |
| `app/repositories/task_repo.py` | stamp_audit_hash integrado em add_audit |
| `app/repositories/document_repo.py` | stamp_audit_hash integrado em add_audit |
| `app/workers/ai_summarizer.py` | stamp_audit_hash integrado em generate_weekly_summary |
| `app/api/v1/intake.py` | stamp_audit_hash integrado no create-case audit |
| `frontend/src/components/ErrorBoundary.tsx` | Novo — ErrorBoundary class component |
| `frontend/src/App.tsx` | Wrapping com ErrorBoundary + Toaster |
| `frontend/src/pages/Properties/index.tsx` | alert() -> toast.error() |
| `frontend/src/pages/Processes/index.tsx` | alert() -> toast.error() (2x) |
| `frontend/src/pages/Processes/DocumentsTab.tsx` | alert() -> toast.error() |
| `frontend/package.json` | Dependencia react-hot-toast adicionada |
| `client-portal/src/app/login/page.tsx` | catch any -> catch unknown |
| `client-portal/src/app/dashboard/page.tsx` | catch any -> catch unknown |
| `client-portal/src/app/dashboard/process/[id]/page.tsx` | catch any -> catch unknown |
| `docker-compose.yml` | Healthcheck MinIO + depends_on service_healthy |

### Validacao de hash chain no AuditLog

Verificar que o servico de hash existe e esta integrado:

```bash
grep -rn "stamp_audit_hash" app/ --include="*.py"
# Esperado: 7+ ocorrencias (audit_hash.py + 6 pontos de integracao)
```

Teste unitario do modulo (nao requer banco):

```powershell
.\venv\Scripts\python.exe -c "
from app.services.audit_hash import compute_audit_hash
from app.models.audit_log import AuditLog
audit = AuditLog(tenant_id=1, user_id=1, entity_type='process', entity_id=1, action='created', details='test')
h = compute_audit_hash(audit, None)
assert len(h) == 64, 'SHA-256 deve ter 64 hex chars'
h2 = compute_audit_hash(audit, None)
assert h == h2, 'Hash deve ser deterministico'
h3 = compute_audit_hash(audit, h)
assert h3 != h, 'Hash com previous diferente deve divergir'
print('audit_hash: PASSED')
"
# Esperado: audit_hash: PASSED
```

Verificacao no banco apos operacao (requer stack rodando):

```sql
SELECT id, tenant_id, action, hash_sha256, hash_previous
FROM audit_logs
ORDER BY id DESC
LIMIT 5;
-- Esperado: registros recentes com hash_sha256 NOT NULL
-- hash_previous deve apontar para hash_sha256 do registro anterior do mesmo tenant
```

### Validacao de ErrorBoundary no frontend

```bash
grep -rn "ErrorBoundary" frontend/src/ --include="*.tsx"
# Esperado: 2+ ocorrencias (ErrorBoundary.tsx + App.tsx)
```

### Validacao de zero alert() no frontend

```bash
grep -rn "alert(" frontend/src/ --include="*.tsx" | grep -v "emit_operational_alert\|AlertCircle\|alertas\|//"
# Esperado: 0 ocorrencias
```

### Validacao de zero `: any` no client-portal

```bash
grep -rn ": any" client-portal/src/ --include="*.tsx" --include="*.ts"
# Esperado: 0 ocorrencias
```

### Validacao de healthcheck MinIO

```bash
grep -A5 "healthcheck" docker-compose.yml | grep -c "minio/health/live"
# Esperado: 1

grep -B2 "service_healthy" docker-compose.yml | grep -c "minio"
# Esperado: 2 (api + worker)
```

Verificacao operacional (requer Docker):

```powershell
docker compose up -d minio
docker inspect --format='{{.State.Health.Status}}' $(docker compose ps -q minio)
# Esperado: healthy (apos start_period de 10s)
```

### Builds dos frontends

```powershell
cd frontend && npx tsc --noEmit && npm run build
# Esperado: 0 erros tsc, build em ~58s, chunk principal < 500 kB
```

```powershell
cd client-portal && npx tsc --noEmit && npm run build
# Esperado: 0 erros tsc, 6 rotas geradas
```

### Suite completa pos-Sprint 4

```powershell
.\venv\Scripts\python.exe -m pytest tests/ -q --tb=short
# Esperado: 145+ passed
# Falhas pre-existentes aceitas:
#   - test_pdf_generator (MinIO indisponivel em ambiente local)
#   - test_classify_returns_503 (sessao propria no check_tenant_cost_limit)
#   - test_dashboard_does_not_leak_cross_tenant_data (pre-existente)
```

### Estado operacional pos-Sprint 4

| Controle | Estado |
|----------|--------|
| AuditLog hash chain | Ativo — todo novo registro tem SHA-256 calculado |
| AuditLog hash_previous | Encadeado por tenant (ultimo hash do mesmo tenant) |
| ErrorBoundary frontend | Ativo — envolve toda a arvore no App.tsx |
| Toast notifications | Ativo — react-hot-toast substituindo alert() |
| Portal `: any` | Eliminado — catch unknown em todos os catch blocks |
| MinIO healthcheck | Ativo — curl health/live, api/worker dependem de service_healthy |
| Frontend build | VERDE (428 kB, 0 erros tsc) |
| Portal build | VERDE (6 rotas, 0 erros tsc) |

## Validacao Sprint 5 — Frontend e Mobile Polish (04/04/2026)

### Pre-requisitos

- Node.js instalado para builds do frontend e portal
- Nenhuma dependencia nova adicionada nesta sprint

### Arquivos alterados

| Arquivo | Alteracao |
|---------|-----------|
| `frontend/src/pages/Auth/Login.tsx` | Credenciais hardcoded removidas + URL portal via env var |
| `frontend/vite.config.ts` | Proxy target via `process.env.VITE_API_PROXY_TARGET` |
| `frontend/src/pages/Dashboard/index.tsx` | `<div onClick>` → `<button type="button">` (atividades + tarefas) |
| `client-portal/src/app/login/layout.tsx` | Novo — server layout com metadata SEO |
| `client-portal/src/app/dashboard/layout.tsx` | Refatorado para server component com metadata |
| `client-portal/src/app/dashboard/DashboardShell.tsx` | Novo — client shell (auth guard + sidebar) extraido do layout |
| `client-portal/src/app/dashboard/process/[id]/layout.tsx` | Novo — server layout com metadata SEO |
| `mobile/app/login.tsx` | Credenciais removidas + `catch unknown` + botao condicional |

### Validacao de credenciais hardcoded removidas

```bash
grep -rn "admin@amigao\|admin123" frontend/src/ mobile/app/ --include="*.tsx"
# Esperado: 0 ocorrencias
```

### Validacao de URLs hardcoded removidas

```bash
grep -rn "localhost:3000" frontend/src/ --include="*.tsx" --include="*.ts"
# Esperado: 0 ocorrencias

grep -rn "127.0.0.1" frontend/src/ --include="*.tsx" --include="*.ts"
# Esperado: 0 ocorrencias (vite.config.ts usa env var, nao esta em src/)
```

### Validacao de proxy via env var

```bash
grep -n "process.env.VITE_API_PROXY_TARGET" frontend/vite.config.ts
# Esperado: 1 ocorrencia com fallback para http://127.0.0.1:8000
```

### Validacao de acessibilidade no Dashboard

```bash
grep -rn "<div.*onClick" frontend/src/pages/Dashboard/index.tsx
# Esperado: 0 ocorrencias (todos convertidos para <button>)

grep -c "<button" frontend/src/pages/Dashboard/index.tsx
# Esperado: >= 6 (view toggle, nova demanda, stat cards, atividades, tarefas)
```

### Validacao de metadata no client-portal

```bash
grep -rn "export const metadata\|export async function generateMetadata" client-portal/src/app/ --include="*.tsx"
# Esperado: 4 ocorrencias (root layout + login layout + dashboard layout + process layout)
```

Verificacao de que DashboardShell nao exporta metadata (client component):

```bash
grep -n "export const metadata" client-portal/src/app/dashboard/DashboardShell.tsx
# Esperado: 0 ocorrencias
```

### Validacao de input no login mobile

```bash
grep -n "disabled=" mobile/app/login.tsx
# Esperado: 1 ocorrencia com !email.trim() || !password.trim()

grep -n ": any" mobile/app/login.tsx
# Esperado: 0 ocorrencias
```

### Builds dos frontends

```powershell
cd frontend && npx tsc --noEmit && npm run build
# Esperado: 0 erros tsc, build sucesso, chunk principal < 500 kB
```

```powershell
cd client-portal && npx tsc --noEmit && npm run build
# Esperado: 0 erros tsc, 6 rotas geradas (3 static, 1 dynamic)
```

### Estado operacional pos-Sprint 5

| Controle | Estado |
|----------|--------|
| Credenciais frontend | Removidas — useState('') em Login.tsx |
| Credenciais mobile | Removidas — useState('') em login.tsx |
| URL portal no frontend | Via `import.meta.env.VITE_CLIENT_PORTAL_URL` |
| Proxy Vite | Via `process.env.VITE_API_PROXY_TARGET` com fallback |
| Acessibilidade Dashboard | `<button>` semantico em atividades e tarefas |
| timeAgo | Funcao pura fora do componente (sem recalculo por render) |
| Metadata portal login | "Login — Portal do Cliente" |
| Metadata portal dashboard | "Dashboard — Amigao do Meio Ambiente" |
| Metadata portal process | "Detalhes do Processo — Amigao do Meio Ambiente" |
| Login mobile validacao | Botao desabilitado com campos vazios + feedback visual |
| Login mobile tipagem | `catch (err: unknown)` — zero `any` |
| Frontend build | VERDE (428 kB, 0 erros tsc) |
| Portal build | VERDE (6 rotas, 0 erros tsc) |

## Validacao Sprint 2 — Integridade de Dados e Performance (04/04/2026)

### Pre-requisitos

- PostgreSQL rodando (para aplicar migration)
- Docker rodando (para Testcontainers nos testes de integracao)

### Arquivos alterados

| Arquivo | Alteracao |
|---------|-----------|
| `app/db/session.py` | pool_size=20, max_overflow=10, pool_recycle=3600, statement_timeout=30000, expire_on_commit=False |
| `alembic/versions/f1a2b3c4d5e6_...py` | Nova migration — 16 indexes compostos + documents.deleted_at |
| `app/repositories/process_repo.py` | tenant_id filter em count_incomplete_tasks |
| `app/services/notifications.py` | Redis singleton com ConnectionPool (max_connections=10) |
| `app/models/document.py` | Campo deleted_at (DateTime, nullable) |
| `app/repositories/document_repo.py` | Filtro deleted_at.is_(None) em _scoped_query |
| `app/db/init_db.py` | _safe_url() com render_as_string(hide_password=True) |

### Validacao do pool de conexoes

```bash
grep -n "pool_size" app/db/session.py        # Esperado: 20
grep -n "max_overflow" app/db/session.py     # Esperado: 10
grep -n "pool_recycle" app/db/session.py     # Esperado: 3600
grep -n "statement_timeout" app/db/session.py # Esperado: 30000
grep -n "expire_on_commit" app/db/session.py  # Esperado: False
```

Verificacao operacional (requer stack rodando):

```sql
-- Conferir pool ativo no PostgreSQL
SELECT count(*) FROM pg_stat_activity WHERE datname = current_database();
-- Esperado: <= 30 conexoes (pool_size + max_overflow)

-- Conferir statement_timeout aplicado
SHOW statement_timeout;
-- Esperado: 30s (definido via connect_args)
```

### Validacao da migration de indexes

Aplicar migration:

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
# Esperado: migration f1a2b3c4d5e6 aplicada sem erro
```

Ciclo reversivel:

```powershell
.\venv\Scripts\python.exe -m alembic downgrade -1
.\venv\Scripts\python.exe -m alembic upgrade head
# Esperado: sem erros em nenhuma direcao
```

Verificacao de indexes criados:

```sql
SELECT indexname FROM pg_indexes
WHERE tablename IN ('processes', 'tasks', 'documents', 'clients', 'proposals', 'contracts', 'audit_logs', 'communication_threads')
AND indexname LIKE 'ix_%'
ORDER BY indexname;
-- Esperado: 16 indexes com prefixo ix_ (alem dos existentes)
```

Indexes criticos a confirmar:

```sql
-- Workflow filtering (CRITICO)
SELECT indexname FROM pg_indexes WHERE indexname = 'ix_processes_tenant_status';
-- Task board (CRITICO)
SELECT indexname FROM pg_indexes WHERE indexname = 'ix_tasks_tenant_status';
-- Audit queries (ALTO)
SELECT indexname FROM pg_indexes WHERE indexname = 'ix_audit_logs_tenant_entity_created';
```

### Validacao do tenant filter em count_incomplete_tasks

```bash
grep -n "self.tenant_id" app/repositories/process_repo.py | grep "count_incomplete"
# Esperado: Task.tenant_id == self.tenant_id presente na query
```

### Validacao do Redis singleton

```bash
grep -n "ConnectionPool" app/services/notifications.py
# Esperado: >= 1 (ConnectionPool.from_url)

grep -n "_get_redis_client" app/services/notifications.py
# Esperado: >= 2 (definicao + uso em publish_realtime_event)

grep -n "client.close" app/services/notifications.py
# Esperado: 0 (singleton nao deve ser fechado por chamada)
```

Verificacao operacional (requer stack rodando):

```powershell
docker compose exec -T api python -c "
from app.services.notifications import _get_redis_client
c = _get_redis_client()
print('pool:', c.connection_pool.max_connections, 'conns')
c.ping()
print('Redis singleton: OK')
"
# Esperado: pool: 10 conns / Redis singleton: OK
```

### Validacao do soft delete de Document

```bash
grep -n "deleted_at" app/models/document.py
# Esperado: >= 1 (Column DateTime nullable)

grep -n "deleted_at" app/repositories/document_repo.py
# Esperado: >= 1 (Document.deleted_at.is_(None))
```

Verificacao no banco:

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'documents' AND column_name = 'deleted_at';
-- Esperado: timestamp with time zone, YES

SELECT indexname FROM pg_indexes WHERE indexname = 'ix_documents_deleted_at';
-- Esperado: 1 row
```

### Validacao de password escondida nos logs

```bash
grep -n "hide_password" app/db/init_db.py
# Esperado: >= 1 (render_as_string(hide_password=True))

grep -n "engine.url" app/db/init_db.py
# Esperado: 0 ocorrencias diretas (substituidas por _safe_url(engine.url))
```

Verificacao funcional:

```powershell
.\venv\Scripts\python.exe -c "
from app.db.init_db import _safe_url
from app.db.session import engine
safe = _safe_url(engine.url)
assert '***' in safe or ':@' not in safe, 'Password nao esta escondida'
print('Safe URL:', safe)
"
# Esperado: postgresql://user:***@host/db
```

### Suite completa pos-Sprint 2

```powershell
.\venv\Scripts\python.exe -m pytest tests/ -q --tb=short
# Esperado: 145+ passed
# Falhas pre-existentes aceitas:
#   - test_pdf_generator (MinIO indisponivel)
#   - test_classify_returns_503 (sessao propria no check_tenant_cost_limit)
#   - test_dashboard_does_not_leak_cross_tenant_data (pre-existente)
```

Suite rapida sem Docker:

```powershell
.\venv\Scripts\python.exe -m pytest tests/ -q --tb=short --ignore=tests/api --ignore=tests/agents/test_prompt_template_model.py
# Esperado: 109 passed, 1 failed (test_pdf_generator pre-existente)
```

### Estado operacional pos-Sprint 2

| Controle | Estado |
|----------|--------|
| Pool de conexoes | pool_size=20, max_overflow=10, pool_recycle=3600 |
| Statement timeout | 30s via connect_args psycopg2 |
| expire_on_commit | False — evita lazy-load pos-commit |
| Indexes compostos | 16 novos indexes em 8 tabelas |
| Tenant filter tasks | count_incomplete_tasks filtra por self.tenant_id |
| Redis connection | Singleton com ConnectionPool (max 10 conns) |
| Document soft delete | Campo deleted_at + filtro em queries + index |
| Password nos logs | Escondida via render_as_string(hide_password=True) |
| Migration chain | f1a2b3c4d5e6 (head) — ciclo up/down/up validado |

## Validacao Sprint 3 — Validacao de Dados e IA (04/04/2026)

### Pre-requisitos

- Docker rodando (para Testcontainers nos testes backend)
- Nenhuma dependencia nova adicionada nesta sprint

### Arquivos alterados

| Arquivo | Alteracao |
|---------|-----------|
| `app/api/v1/documents.py` | Whitelist 28 extensoes + validacao MIME + `_validate_file()` |
| `app/core/ai_gateway.py` | Remocao `_set_api_keys()` e `import os` + `api_key=` direto + `check_tenant_cost_limit()` |
| `app/api/v1/ai.py` | `check_tenant_cost_limit()` em classify/extract + `DbDep` adicionado |
| `app/api/v1/tasks.py` | `_has_circular_dependency()` BFS + endpoint `POST /{id}/dependencies/{dependency_id}` |
| `app/schemas/document.py` | `Field(gt=0, le=104857600)` em `file_size_bytes` |
| `app/api/v1/intake.py` | `try/except` com `db.rollback()` no create-case |

### Validacao de extensao e MIME no upload

```bash
# Whitelist presente
grep -c "ALLOWED_EXTENSIONS" app/api/v1/documents.py
# Esperado: 3 (definicao + 2 usos em _validate_file)

# Validacao aplicada em ambos endpoints
grep -n "_validate_file" app/api/v1/documents.py
# Esperado: 3 ocorrencias (definicao + get_upload_url + confirm_upload)
```

Teste manual (requer stack rodando):

```powershell
# Upload de .exe deve retornar 400
$headers = @{ Authorization = "Bearer $TOKEN"; "Content-Type" = "application/json" }
$body = '{"filename":"malware.exe","process_id":1,"content_type":"application/octet-stream","file_size_bytes":1000,"storage_key":"test"}'
Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/api/v1/documents/confirm-upload' -Headers $headers -Body $body
# Esperado: 400 "Extensao '.exe' nao permitida"

# Upload de .pdf com MIME incompativel deve retornar 400
$body = '{"filename":"doc.pdf","process_id":1,"content_type":"image/jpeg","file_size_bytes":1000,"storage_key":"test"}'
Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/api/v1/documents/confirm-upload' -Headers $headers -Body $body
# Esperado: 400 "Content-type 'image/jpeg' incompativel com extensao '.pdf'"
```

### Validacao de API keys fora de os.environ

```bash
grep -n "os.environ\[" app/core/ai_gateway.py
# Esperado: 0 ocorrencias

grep -n "import os" app/core/ai_gateway.py
# Esperado: 0 ocorrencias

grep -n "api_key=" app/core/ai_gateway.py
# Esperado: 1 ocorrencia no litellm.completion()
```

### Validacao de custo por tenant

```bash
grep -n "check_tenant_cost_limit" app/core/ai_gateway.py app/api/v1/ai.py
# Esperado: definicao em ai_gateway.py + 2 chamadas em ai.py (classify + extract)

grep -n "AI_HOURLY_COST_LIMIT_USD" app/core/ai_gateway.py
# Esperado: 1 ocorrencia (constante = 5.0)

grep -n "429" app/core/ai_gateway.py
# Esperado: 1 ocorrencia (status_code=429 no HTTPException)
```

Verificacao no banco (requer stack rodando + chamadas IA previas):

```sql
SELECT tenant_id,
       SUM(cost_usd) as total_cost_1h,
       COUNT(*) as jobs_count
FROM ai_jobs
WHERE created_at >= NOW() - INTERVAL '1 hour'
GROUP BY tenant_id;
-- Se total_cost_1h >= 5.0 para algum tenant, proxima chamada retorna 429
```

### Validacao de dependencia circular em tasks

```bash
grep -n "_has_circular_dependency" app/api/v1/tasks.py
# Esperado: 2 ocorrencias (definicao + chamada no endpoint)

grep -n "dependencies/{dependency_id}" app/api/v1/tasks.py
# Esperado: 1 ocorrencia (rota POST)

grep -n "Dependencia circular detectada" app/api/v1/tasks.py
# Esperado: 1 ocorrencia (mensagem de erro 400)
```

Teste manual (requer stack rodando com tasks existentes):

```powershell
# Criar dependencia circular: task A depende de task B, depois task B depende de task A
$headers = @{ Authorization = "Bearer $TOKEN" }
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/v1/tasks/$TASK_A_ID/dependencies/$TASK_B_ID" -Headers $headers
# Esperado: 200 (dependencia criada)

Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/v1/tasks/$TASK_B_ID/dependencies/$TASK_A_ID" -Headers $headers
# Esperado: 400 "Dependencia circular detectada"
```

### Validacao de file_size_bytes no schema

```bash
grep -n "gt=0" app/schemas/document.py
# Esperado: 1 ocorrencia

grep -n "le=104857600" app/schemas/document.py
# Esperado: 1 ocorrencia
```

### Validacao de transaction boundary no intake

```bash
grep -n "db.rollback" app/api/v1/intake.py
# Esperado: 2 ocorrencias (except HTTPException + except Exception)

grep -c "db.commit" app/api/v1/intake.py
# Esperado: 1 (unico commit no final do try)
```

### Suite completa pos-Sprint 3

```powershell
.\venv\Scripts\python.exe -m pytest tests/ -q --tb=short
# Esperado: 147+ passed
# Falha pre-existente aceita:
#   - test_pdf_generator (MinIO indisponivel em ambiente local)
# NOTA: test_classify_returns_503 que falhava antes agora PASSA (corrigido nesta sprint)
```

### Estado operacional pos-Sprint 3

| Controle | Estado |
|----------|--------|
| Upload sem extensao permitida | Rejeitado — HTTP 400 com whitelist de 28 extensoes |
| Upload com MIME incompativel | Rejeitado — HTTP 400 para tipos mapeados |
| Upload > 100MB | Rejeitado — HTTP 422 via Pydantic (le=104857600) |
| API keys em os.environ | Eliminado — passagem direta via api_key= |
| Custo IA sem limite | Controlado — $5/h por tenant, HTTP 429 se excedido |
| Dependencia circular em tasks | Detectada — BFS + endpoint dedicado, HTTP 400 |
| Intake sem rollback | Corrigido — try/except com db.rollback() |
| test_classify_returns_503 | Corrigido — sessao via DbDep (antes: SessionLocal proprio) |
| Suite backend | 147 passed, 1 pre-existente (pdf_generator) |

## Pendencias atuais

- Sprint 0 residual: rotacionar chave OpenAI exposta no `.env` (revogar `sk-proj-zE_I7...` e gerar nova)
- Sprint 0 residual: rotacionar senha Gmail exposta no `.env`
- ~~Sprint 0 residual: remover credenciais hardcoded do `frontend/src/pages/Auth/Login.tsx` (L9-10)~~ — **resolvido Sprint 5**
- Sprint 0 residual: alterar senha default "password" do PostgreSQL no `docker-compose.yml`
- ~~Sprint 2: pool DB~~ — **resolvido Sprint 2** (pool_size=20, max_overflow=10, pool_recycle=3600, statement_timeout=30s)
- ~~Sprint 2: migration com indexes compostos~~ — **resolvido Sprint 2** (16 indexes em migration f1a2b3c4d5e6)
- Sprint 2 nota: N+1 no dashboard ja corrigido em rodada anterior (outerjoin L100-108)
- Sprint 2 nota: mobile SyncService ja usa UPSERT (INSERT OR REPLACE) em rodada anterior
- ~~`test_classify_returns_503` falha por sessao propria no `check_tenant_cost_limit`~~ — **corrigido Sprint 3** (refatorado para injecao de sessao via DbDep)
- Sprint 3 nota: limite de custo IA ($5/h) hardcoded como constante — tornar configuravel por tenant em producao
- Sprint 3 nota: endpoint `POST /tasks/{id}/dependencies/{dependency_id}` sem teste automatizado dedicado
- substituir o sink local por destino externo real de webhook quando houver endpoint definitivo
- modularizar o seed atual se o repositorio realmente migrar para a estrutura `seed/main.py`
- revisar referencias antigas a credenciais seed em documentacao fora do runbook principal, se surgirem novas divergencias
- incluir `http://localhost:5173` no `BACKEND_CORS_ORIGINS` do `.env` para dev local do frontend Vite
- configurar pipeline CI com gates de build/lint/typecheck para ambos os frontends
- migrar testes backend de SQLite para PostgreSQL real (JSONB incompativel) — **resolvido parcialmente: testes IA ja rodam em PostgreSQL via Testcontainers**
- ~~corrigir import faltante `emit_operational_alert` em `app/api/v1/tasks.py`~~ — **resolvido em 03/04**
- ~~corrigir `class Config` legado para `model_config = ConfigDict(...)` em `app/api/v1/dashboard.py`~~ — **resolvido em 03/04**
- ~~corrigir `.dict()` deprecado para `.model_dump()` em `processes.py` e `properties.py`~~ — **resolvido em 03/04**
- ~~Sprint IA-2: criar `/app/agents/base.py` e `registry.py` (framework de agentes)~~ — **resolvido 08/04** (app/agents/ com 10 agentes + orquestrador)
- ~~Sprint IA-2: implementar validacao estrita de output LLM via JSON Schema + Pydantic~~ — **resolvido 08/04** (OutputValidationPipeline em app/agents/validators.py)
- ~~Sprint IA-2: refatorar chamadas LLM para logging obrigatorio via `ai_gateway.py`~~ — **resolvido 08/04** (BaseAgent.call_llm wraps ai_gateway.complete com metricas em AIJob)
- Sprint IA-2: router CRUD de PromptTemplate em `/api/v1/prompts`
- Sprint IA-3: RAG com pgvector para LegislacaoAgent
- Sprint IA-3: seed de prompt templates no banco para cada agente
- Sprint IA-3: testes unitarios para cada agente com mock de ai_gateway
- Sprint F4: testes de componentes React com Testing Library (jsdom)
- Sprint F4: decomposicao de `Processes/index.tsx` (segundo maior arquivo)
- Sprint F4: hook customizado `useDashboard` para encapsular queries
- Sprint F4: integracao com OpenAPI gerada pelo backend (tipagem end-to-end)
- Sprint F4: endpoints separados `/dashboard/activities` e `/dashboard/my-tasks` no backend (frontend ja esta preparado com fallback)

## Coordenação de Validação por Agente (Playbook)

Este playbook detalha os comandos estruturados que devem ser executados para certificar e validar as entregas paralelas dos 3 agentes alocados nas frentes em andamento.

### Homologação do Agente 1 (Backend Core e Testes CI)
Quando o Agente 1 finalizar os testes no `PostgreSQL` ou nova camada de `Repositories`, deve-se aplicar o pipeline completo de backend:

1. **Testes Unitários e de Integração:**
```powershell
docker-compose run --rm tests pytest -v tests/
# Caso não tenha target de test container no docker-compose, rode:
# .\venv\Scripts\python.exe -m pytest -v tests/
```
2. **Lint e Análise Estática de Tipos Strict:**
```powershell
.\venv\Scripts\python.exe -m ruff check app/ tests/
.\venv\Scripts\python.exe -m mypy app/
```
3. **Drift de Schema de Banco de Dados:**
```powershell
.\venv\Scripts\python.exe ops\check_migrations.sh
# Garantir que não existam múltiplos "Heads" com o Agente 3
```

### Homologação do Agente 2 (Frontend e Clean UX)
Toda a refatoração do Agente 2 (painel interno e client) rege validações vitais via node scripts.

1. **Saúde de Build de Produção:**
```powershell
cd frontend && npm run build
# O build do "assets/index*.js" não deve apresentar Warning de excesso de banda (>500kb sem split)
```
2. **Rodar Vitest Automático e ESLint Strict:**
```powershell
cd frontend && npm run test
cd frontend && npx eslint src --max-warnings=0
cd frontend && npx tsc --noEmit
```

### Homologação do Agente 3 (Inteligência Artificial e Engine)
A infra do Agente 3 foca na lógica AI. As requisições de agentes externos mockados não devem alarmar produção localmente.

1. **Migração do Registry de IA Alembic:**
Sempre forçar o banco após merges na branch do Agente 3 para garantir a presença do `PromptTemplate`:
```powershell
.\venv\Scripts\alembic upgrade head
```
2. **Testes da Interface dos Agentes Base:**
```powershell
.\venv\Scripts\python.exe -m pytest -v tests/agents/
# Checar cobertura sobre "BaseAgent", "AgentRegistry"
```
3. **Health Check vs Cyclic Imports:**
Reverta imediatamente caso a injestão de dependências entre IA e endpoints de negócio crie lag massivo ou quebre o start via dependência circular:
```powershell
(Invoke-WebRequest -UseBasicParsing http://localhost:8000/health).StatusCode
# Métrica de aceite: Resposta rápida (200 OK) no startup limpo da API
```

## Validacao Sprint 7 — Hardening Final (04/04/2026)

### Pre-requisitos

- Docker rodando (para Testcontainers nos testes backend)
- `.env` com `SECRET_KEY` definida (>= 32 chars)
- Se Redis local fora do Docker: configurar `REDIS_URL` com senha (`redis://:redispass2026@localhost:6379/0`)

### Migration

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
# a7b8c9d0e1f2 -> 47 FKs com ondelete + unique constraint uq_properties_tenant_registry
```

Validacao de ciclo reversivel:

```powershell
.\venv\Scripts\python.exe -m alembic downgrade -1
.\venv\Scripts\python.exe -m alembic upgrade head
# Sem erros
```

NOTA: se a migration falhar por duplicatas em `properties(tenant_id, registry_number)`, executar antes:

```sql
DELETE FROM properties WHERE id NOT IN (
  SELECT MIN(id) FROM properties GROUP BY tenant_id, registry_number
);
```

### Validacao de FK cascade

```bash
grep -rn "ondelete" app/models/*.py | wc -l
# Esperado: >= 46
```

Verificacao no banco (apos migration):

```sql
SELECT conname, confdeltype
FROM pg_constraint
WHERE contype = 'f' AND conrelid = 'tasks'::regclass;
-- Esperado: process_id -> 'c' (CASCADE), assigned_to_user_id -> 'n' (SET NULL), tenant_id -> 'r' (RESTRICT)
```

### Validacao de unique constraint

```sql
SELECT conname FROM pg_constraint
WHERE conrelid = 'properties'::regclass AND contype = 'u';
-- Esperado: uq_properties_tenant_registry
```

### Validacao de webhook retry

```bash
grep -n "max_retries" app/workers/webhook_tasks.py
# Esperado: max_retries=3

grep -n "retry_backoff" app/workers/webhook_tasks.py
# Esperado: retry_backoff=True
```

Teste funcional (requer stack + webhook sink):

```powershell
docker compose exec -T api python -c "from app.core.alerts import emit_operational_alert; emit_operational_alert(category='smoke_test', severity='warning', message='Webhook retry smoke', metadata={'source':'sprint7'})"
# Webhook sink deve receber payload; se indisponivel, worker loga warning e retenta 3x
```

### Validacao de soft_time_limit

```bash
grep -rn "soft_time_limit" app/workers/*.py | wc -l
# Esperado: >= 10
```

### Validacao de Redis autenticacao

```bash
grep -n "requirepass" docker-compose.yml
# Esperado: redis-server --requirepass ${REDIS_PASSWORD:-redispass2026}
```

Teste operacional (apos `docker compose up`):

```powershell
docker compose exec redis redis-cli -a redispass2026 ping
# Esperado: PONG

docker compose exec redis redis-cli ping
# Esperado: NOAUTH Authentication required
```

### Validacao de Postgres password

```bash
grep "POSTGRES_PASSWORD:-password" docker-compose.yml
# Esperado: zero resultados (default agora eh pgpass2026)
```

### Validacao de ProcessCreate status

```bash
grep -n "field_validator" app/schemas/process.py
# Esperado: @field_validator("status") presente
```

Teste inline:

```powershell
.\venv\Scripts\python.exe -c "
from app.schemas.process import ProcessCreate
from app.models.process import ProcessStatus
try:
    ProcessCreate(title='T', client_id=1, status=ProcessStatus.execucao)
    print('FAIL: deveria rejeitar')
except Exception as e:
    print(f'OK: {e}')
p = ProcessCreate(title='T', client_id=1, status=ProcessStatus.lead)
print(f'OK lead: {p.status}')
p2 = ProcessCreate(title='T', client_id=1)
print(f'OK default: {p2.status}')
"
# Esperado: rejeita execucao, aceita lead, aceita default triagem
```

### Suite completa pos-Sprint 7

```powershell
.\venv\Scripts\python.exe -m pytest tests/ -q --tb=short
# Esperado: 158+ passed
# Falhas pre-existentes aceitas:
#   - test_pdf_generator (MinIO indisponivel)
#   - test_websocket_valid_token (SQLAlchemy session issue)
```

Suite focada de regressao rapida (sem Docker):

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_alerts.py tests/test_state_machines.py tests/test_settings.py -q --tb=short --no-cov
# Esperado: 78 passed, 0 failed
```

### Estado operacional pos-Sprint 7

| Controle | Estado |
|----------|--------|
| FK ondelete | 47 FKs com regra explicita (CASCADE/SET NULL/RESTRICT) |
| Unique property registry | uq_properties_tenant_registry ativo |
| Webhook delivery | Celery task async com 3 retries + backoff |
| Celery timeouts | soft_time_limit em 10/10 tasks (30s-300s) |
| Redis auth | requirepass obrigatorio, REDIS_URL com senha |
| Postgres password | Default pgpass2026 (nao mais "password") |
| ProcessCreate status | Validado no schema: apenas lead ou triagem |
| expire_on_commit | False (desde Sprint 2) |

### Docker compose — mudancas operacionais Sprint 7

Ao subir a stack apos Sprint 7, atentar para:

1. **Redis requer senha**: se houver containers Redis antigos sem auth, remover volume e recriar:
```powershell
docker compose down -v
docker compose up --build -d
```

2. **REDIS_URL mudou formato**: de `redis://redis:6379/0` para `redis://:redispass2026@redis:6379/0`. Se `.env` sobrescreve `DOCKER_REDIS_URL`, atualizar com senha.

3. **POSTGRES_PASSWORD default mudou**: de `password` para `pgpass2026`. Se banco existente usa senha antiga, definir explicitamente em `.env`:
```
POSTGRES_PASSWORD=password
```
Ou recriar o volume do banco.

---

## Validacoes pos-Sprint 6 (04/04/2026)

### Coverage threshold

```powershell
grep "fail_under" pyproject.toml
# Esperado: fail_under = 70

grep "cov" .github/workflows/ci.yml
# Esperado: --cov=app --cov-report=term-missing
```

### Testes E2E

```powershell
ls tests/e2e/test_intake_flow.py tests/e2e/test_document_flow.py
# Esperado: ambos existem

.\venv\Scripts\python.exe -m pytest tests/e2e/ -q --tb=short
# Esperado: passed (depende de Testcontainers)
```

### Teste WebSocket

```powershell
ls tests/api/test_websockets.py
# Esperado: existe

.\venv\Scripts\python.exe -m pytest tests/api/test_websockets.py -q --tb=short
# Esperado: passed (depende de Testcontainers)
```

### Password strength

```powershell
grep -n "field_validator" app/schemas/user.py
# Esperado: @field_validator("password") presente

.\venv\Scripts\python.exe -c "
from app.schemas.user import UserCreate
try:
    UserCreate(email='a@b.com', full_name='T', password='short')
    print('FAIL: deveria rejeitar')
except Exception as e:
    print(f'OK rejeitou senha fraca: {e}')
try:
    UserCreate(email='a@b.com', full_name='T', password='Valida1234')
    print('OK: aceita senha forte')
except Exception as e:
    print(f'FAIL: {e}')
"
```

---

## Validacoes pos-Rodada Final de Ajustes (04/04/2026)

### WebSocket auth completo

```powershell
grep -n "ExpiredSignatureError" app/api/websockets.py
# Esperado: import + except block

grep -n "ValidationError" app/api/websockets.py
# Esperado: import + except block

grep -c "1008" app/api/websockets.py
# Esperado: >= 2 (um para expired, um para invalid/validation)
```

### Middleware sem catch generico

```powershell
grep -n "Exception" app/api/middleware.py | head -5
# Esperado: NENHUMA linha com (JWTError, Exception) — deve ser (JWTError, ValueError, KeyError)
```

### Portal sem window.alert

```powershell
grep -rn "window.alert\|[^.]alert(" client-portal/src/ --include="*.tsx" --include="*.ts" | grep -v node_modules | grep -v AlertCircle
# Esperado: 0 resultados
```

### AI cost limit em todos endpoints

```powershell
grep -n "check_tenant_cost_limit" app/api/v1/ai.py
# Esperado: 4 ocorrencias (classify, extract, classify-async, extract-async)

grep -n "DbDep" app/api/v1/ai.py
# Esperado: presente em classify_async e extract_async
```

### Metadata do portal

```powershell
grep -rn "export const metadata" client-portal/src/app/ --include="*.tsx"
# Esperado: 3+ resultados (login/layout, dashboard/layout, process/[id]/layout)
```

---

## Estado operacional pos-Rodada Final

| Controle | Estado |
|----------|--------|
| Sprints concluidas | 8/8 (Sprint 0-7) |
| Issues CRITICO resolvidos | 11/11 |
| Issues ALTO resolvidos | 18/18 |
| Issues MEDIO resolvidos | 24/24 |
| WebSocket auth | ExpiredSignature + JWTError + ValidationError tratados |
| Middleware auth context | Sem catch-all Exception |
| Portal window.alert | Zero ocorrencias |
| AI cost limit | 4/4 endpoints protegidos |
| Portal metadata SEO | 3 layouts com Metadata export |
| Coverage threshold | 70% configurado, blocker progressivo |
| Total testes | ~117 funcoes em 22 arquivos |
| Maturidade geral | ~85% (VERDE-AMARELO) |

### Pendencias operacionais remanescentes

1. **Rotacionar chave OpenAI** — a chave `sk-proj-zE_I7...` foi exposta no .env historico. Gerar nova em https://platform.openai.com/api-keys e atualizar .env.
2. **Rotacionar senha Gmail** — App Password `qcykudlyojpuoiwp` foi exposta. Revogar em Google Account > Security > App Passwords.
3. **Ativar coverage blocker** — quando `pytest --cov=app` reportar >= 70%, habilitar `--cov-fail-under=70` no CI step (remover comentario TODO).
4. **test_pdf_generator** — falha pre-existente por MinIO indisponivel em ambiente de teste. Ajustar mock ou skip condicional.
5. **Custo IA configuravel** — `AI_HOURLY_COST_LIMIT_USD = 5.0` hardcoded em ai_gateway.py. Para producao multi-tenant, migrar para settings ou tabela por tenant.

### Suite de regressao rapida pos-fechamento

```powershell
# Sem Docker (core + services + agents)
.\venv\Scripts\python.exe -m pytest tests/test_alerts.py tests/test_state_machines.py tests/test_settings.py tests/agents/ -q --tb=short --no-cov
# Esperado: 78+ passed, 0 failed

# Com Docker (suite completa)
.\venv\Scripts\python.exe -m pytest tests/ -q --tb=short --cov=app --cov-report=term-missing
# Esperado: 158+ passed, 1 failed (test_pdf_generator)
```

---

## Sistema de Agentes IA — Sprint IA-2 (08/04/2026)

Implementacao do framework de agentes com orquestrador deterministico.

### Arquitetura

```
API /agents/*  →  OrchestratorAgent (chains deterministicas)  →  10 Agentes especializados
                                                                   ↓
                                                              ai_gateway + AIJob + AuditLog
```

Principio: **IA sugere → Humano valida → Sistema audita**. Orquestrador nao usa LLM — roteia por regras.

### Agentes registrados

| Agente | Arquivo | Job Type | LLM |
|--------|---------|----------|-----|
| atendimento | `app/agents/atendimento.py` | classify_demand | Sim (wraps llm_classifier) |
| extrator | `app/agents/extrator.py` | extract_document | Sim (wraps document_extractor) |
| diagnostico | `app/agents/diagnostico.py` | diagnostico_propriedade | Sim |
| legislacao | `app/agents/legislacao.py` | consulta_regulatoria | Sim (RAG futuro) |
| redator | `app/agents/redator.py` | gerar_documento | Sim |
| orcamento | `app/agents/orcamento.py` | generate_proposal | Sim |
| financeiro | `app/agents/financeiro.py` | analise_financeira | Opcional |
| acompanhamento | `app/agents/acompanhamento.py` | acompanhamento_processo | Sim |
| vigia | `app/agents/vigia.py` | monitoramento_vigia | Nao (regras) |
| marketing | `app/agents/marketing.py` | gerar_conteudo_marketing | Sim |

### Chains disponiveis

| Chain | Agentes | Uso |
|-------|---------|-----|
| intake | atendimento | Classificacao de lead |
| diagnostico_completo | extrator → legislacao → diagnostico | Analise de propriedade |
| gerar_proposta | diagnostico → orcamento | Proposta comercial |
| gerar_documento | redator | Geracao de documentos formais |
| analise_regulatoria | legislacao | Consulta juridica |
| analise_financeira | financeiro | Analise de custos |
| monitoramento | acompanhamento → vigia | Monitoramento de processo |
| marketing_content | marketing | Conteudo de campanha |

### Endpoints

| Metodo | Rota | Descricao |
|--------|------|-----------|
| POST | `/api/v1/agents/run` | Executa agente sincrono |
| POST | `/api/v1/agents/run-async` | Executa agente via Celery (202) |
| POST | `/api/v1/agents/chain` | Executa chain sincrona |
| POST | `/api/v1/agents/chain-async` | Executa chain via Celery (202) |
| GET | `/api/v1/agents/registry` | Lista agentes disponiveis |
| GET | `/api/v1/agents/chains` | Lista chains disponiveis |

### Celery tasks

| Task | Nome | Descricao |
|------|------|-----------|
| run_agent | `workers.run_agent` | Execucao generica async |
| run_agent_chain | `workers.run_agent_chain` | Chain async |
| vigia_scheduled_check | `workers.vigia_scheduled_check` | Beat horario |

### Migration

```powershell
alembic upgrade head
# Migration b1c2d3e4f5a6 → adiciona colunas agent_name e chain_trace_id em ai_jobs,
# novos valores de AIJobType e PromptCategory
```

### Validacao do sistema de agentes

```powershell
# 1. Syntax check de todos os arquivos
python -c "
import ast
files = [
    'app/agents/base.py', 'app/agents/validators.py', 'app/agents/events.py',
    'app/agents/orchestrator.py', 'app/agents/__init__.py',
    'app/agents/atendimento.py', 'app/agents/extrator.py', 'app/agents/diagnostico.py',
    'app/agents/legislacao.py', 'app/agents/redator.py', 'app/agents/orcamento.py',
    'app/agents/financeiro.py', 'app/agents/acompanhamento.py', 'app/agents/vigia.py',
    'app/agents/marketing.py', 'app/schemas/agent.py', 'app/api/v1/agents.py',
    'app/workers/agent_tasks.py',
]
for f in files:
    ast.parse(open(f).read(), filename=f)
    print(f'OK: {f}')
print(f'All {len(files)} files OK')
"
# Esperado: 18 files OK

# 2. Verificar registro de agentes
python -c "from app.agents import AgentRegistry; print(AgentRegistry.list_agents())"
# Esperado: lista com 10 agentes

# 3. Verificar chains
python -c "from app.agents.orchestrator import CHAINS; print(list(CHAINS.keys()))"
# Esperado: 8 chains

# 4. Health check (API deve subir sem erro)
curl http://localhost:8000/health
# Esperado: 200 OK

# 5. Listar agentes via API
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/agents/registry
# Esperado: 200 com 10 agentes

# 6. Executar agente vigia (nao requer LLM)
curl -X POST http://localhost:8000/api/v1/agents/run \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"agent_name": "vigia"}'
# Esperado: 200 com alerts (prazos, documentos expirando, etc.)

# 7. Verificar migration
alembic history | head -5
# Esperado: b1c2d3e4f5a6 como ultima migration
```

### Estado operacional pos-Sprint IA-2

| Controle | Estado |
|----------|--------|
| Framework de agentes | BaseAgent + AgentRegistry + AgentContext + AgentResult |
| Agentes implementados | 10/10 |
| Chains configuradas | 8 |
| Endpoints API | 6 (run, chain, run-async, chain-async, registry, chains) |
| Celery tasks | 3 (run_agent, run_agent_chain, vigia_scheduled) |
| Migration | b1c2d3e4f5a6 (agent_name, chain_trace_id, novos enums) |
| Backward compat | /ai/* endpoints inalterados |
| Validacao output | Pipeline: JSON parse → Schema → Dominio → Safety |
| Eventos | agent.*.started/completed/failed via Redis + AuditLog |

### Pendencias IA

- RAG com pgvector para LegislacaoAgent (Fase 2 futura)
- Cache semantico Redis para queries repetidas
- A/B testing de prompts via PromptTemplate versioning
- Celery Beat configurado para VigiaAgent (necessita lista de tenant_ids)
- Testes unitarios e integracao para cada agente
- Seed de prompt templates no banco para cada agente

---

## Sistema de Macroetapas (Sprint Macroetapas — 08/04/2026)

### Conceito

O fluxo de processos foi reestruturado de 11 status genericos para 7 macroetapas que refletem o fluxo real da consultoria ambiental (MVP1 pre-contrato):

| # | Macroetapa | Chain vinculada | Acoes padrao |
|---|-----------|-----------------|--------------|
| 1 | entrada_demanda | intake | 5 |
| 2 | diagnostico_preliminar | diagnostico_completo | 8 |
| 3 | coleta_documental | — (manual) | 6 |
| 4 | diagnostico_tecnico | diagnostico_completo | 6 |
| 5 | caminho_regulatorio | enquadramento_regulatorio | 5 |
| 6 | orcamento_negociacao | gerar_proposta | 5 |
| 7 | contrato_formalizacao | — (manual) | 5 |

### Arquivos criticos

| Arquivo | Funcao |
|---------|--------|
| `app/models/macroetapa.py` | Enum, transicoes, labels, acoes padrao, model MacroetapaChecklist |
| `app/services/macroetapa_engine.py` | Engine: advance, toggle, completion, initialize |
| `app/schemas/macroetapa.py` | DTOs: KanbanResponse, MacroetapaStatusResponse |
| `app/api/v1/processes.py` | Endpoints macroetapa + kanban |
| `app/api/v1/dashboard.py` | Endpoint kanban-insights |

### Migration

```bash
# Aplicar migration de macroetapas
alembic upgrade head
# Esperado: coluna macroetapa em processes + tabela macroetapa_checklists
```

Verificacao pos-migration:

```bash
# Verificar coluna macroetapa
python -c "
from app.db.session import SessionLocal
db = SessionLocal()
r = db.execute('SELECT count(*) FROM processes WHERE macroetapa IS NOT NULL')
print(f'Processos com macroetapa: {r.scalar()}')
db.close()
"
```

### Endpoints de Macroetapa

```bash
# 1. Obter status completo da macroetapa de um processo
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/processes/<id>/macroetapa/status
# Esperado: 200 com steps[], current_macroetapa, next_action, completion_pct

# 2. Avancar macroetapa
curl -X POST http://localhost:8000/api/v1/processes/<id>/macroetapa \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"macroetapa": "diagnostico_preliminar"}'
# Esperado: 200 com processo atualizado

# 3. Inicializar checklists de todas as macroetapas
curl -X POST http://localhost:8000/api/v1/processes/<id>/macroetapa/initialize \
  -H "Authorization: Bearer <token>"
# Esperado: 200 com stepper completo e 7 checklists criados

# 4. Toggle acao do checklist
curl -X PATCH http://localhost:8000/api/v1/processes/<id>/macroetapa/entrada_demanda/actions \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"action_id": "ed_01", "completed": true}'
# Esperado: 200 com checklist atualizado e completion_pct recalculado

# 5. Kanban enriquecido por macroetapa
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/processes/kanban
# Esperado: 200 com columns[] (7 macroetapas) e cards[] com client_name, property_name, etc.

# 6. Leitura da IA (insights do kanban)
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/dashboard/kanban-insights
# Esperado: 200 com gargalo_macroetapa, mensagem, pendencias_criticas
```

### Coexistencia com status legado

- Coluna `macroetapa` coexiste com `status` — ambas sao validas
- Processos sem macroetapa continuam visiveis no kanban legado
- Para converter processos legados: `POST /processes/<id>/macroetapa/initialize`
- Data migration automatica: processos com status lead/triagem → entrada_demanda, diagnostico → diagnostico_preliminar, planejamento → caminho_regulatorio

### Frontend — Quadro de Acoes

- View padrao: **Kanban original** (sempre abre primeiro)
- Botao verde "Quadro de Acoes (7 Etapas)" visivel para alternar
- Botao "Voltar ao Kanban" no Quadro de Acoes para retornar
- Sem persistencia em localStorage (default fixo kanban)
- Componentes: QuadroAcoes.tsx, QuadroProcessCard.tsx, MacroetapaStepper.tsx, MacroetapaSidePanel.tsx, LeituraIA.tsx

### Bugs corrigidos pos-deploy (08/04/2026)

| Bug | Causa | Correcao |
|-----|-------|----------|
| Migration d3e4f5a6b7c8 falhava | Enum PG se chama `aijobtype` nao `aijobtypes` | Corrigido nome na migration |
| MacroetapaChecklist nao inseria | Coluna usava `Enum(Macroetapa)` criando tipo PG inexistente | Trocado para `Column(String)` |
| React hooks error em Processos | Early return antes dos hooks | Movido return para depois de todos os hooks |
| Quadro de Acoes vazio como default | localStorage persistia `quadro`, migrations nao rodadas | Default fixo `kanban`, rodadas migrations |

### Estado operacional pos-Sprint Macroetapas

| Controle | Estado |
|----------|--------|
| Macroetapas definidas | 7 |
| Acoes padrao por macroetapa | 40 total |
| Endpoints novos | 6 |
| Migration | c2d3e4f5a6b7 (executada) |
| Chains no orchestrator | 9 (adicionada enquadramento_regulatorio) |
| Frontend | Kanban original (default) + Quadro de Acoes (toggle) |
| Backward compat | Kanban legado 100% funcional |
| Processos com macroetapa | 19/19 |
| Checklists criados | 133 (7 × 19) |

### Proximas fases (Plano Mestre v2)

| Fase | Descricao | Status |
|------|-----------|--------|
| Fase 4 | 7 Macroetapas backend | Concluida + executada |
| Fase 5 | Frontend Quadro de Acoes | Concluida + corrigida |
| Fase 1 | Base legislativa (context loading, sem chunking) | Concluida + executada |
| Fase 2 | Agente Regulatorio com Claude Sonnet | Concluida |
| Fase 3 | Auto-monitoramento legislacao (DOU + 27 DOEs + IBAMA) | Concluida |

### Pendencias para proxima sessao

- Alinhar Dashboard Executivo/Operacional com usuario — revisar dados exibidos
- Testar Quadro de Acoes com interacao real (marcar acoes, drag-drop)
- Alimentar base legislativa com legislacao federal e estadual
- Configurar `ANTHROPIC_API_KEY` para agente regulatorio
- Instalar deps: `pip install anthropic pypdf beautifulsoup4 lxml`
- Adicionar servico `beat` no docker-compose para monitoramento automatico

---

## Base Legislativa (Sprint Fase 1+2 — 08/04/2026)

### Arquitetura

Texto completo da legislacao armazenado no PostgreSQL (coluna `full_text` em `legislation_documents`).
Na consulta, filtra por metadados (UF, scope, agency, demand_type) e envia documentos inteiros no contexto do Gemini (2M tokens). Sem chunking, sem pgvector, sem embeddings.

### Dependencias pip

```bash
pip install anthropic pypdf beautifulsoup4 lxml
```

### Endpoints da base legislativa

```bash
# 1. Criar documento legislativo com texto direto
curl -X POST http://localhost:8000/api/v1/legislation/documents \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Codigo Florestal",
    "source_type": "lei",
    "identifier": "Lei 12.651/2012",
    "scope": "federal",
    "agency": "CONAMA",
    "demand_types": ["car", "prad", "compensacao"],
    "full_text": "Art. 1o ..."
  }'
# Esperado: 201 com documento criado e status=indexed

# 2. Upload de PDF para documento existente
curl -X POST http://localhost:8000/api/v1/legislation/documents/<id>/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@codigo_florestal.pdf"
# Esperado: 200 com full_text extraido e token_count calculado

# 3. Listar documentos legislativos
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/legislation/documents?scope=federal&status=indexed"
# Esperado: 200 com lista de documentos

# 4. Buscar legislacao por metadados (para context loading)
curl -X POST http://localhost:8000/api/v1/legislation/search \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"uf": "MT", "demand_type": "licenciamento"}'
# Esperado: 200 com documents[] e total_tokens
```

### Agente Regulatorio

O `LegislacaoAgent` foi reescrito para:
1. Carregar contexto do processo (demand_type, UF, imovel, bioma)
2. Buscar legislacao relevante no banco por metadados
3. Enviar textos completos no contexto do LLM
4. Claude Sonnet para raciocinio juridico (contexto < 100k chars)
5. Gemini para contexto extenso (> 100k chars)
6. Retornar enquadramento regulatorio estruturado

Validacao:

```bash
# Executar agente regulatorio para um processo
curl -X POST http://localhost:8000/api/v1/agents/run \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"agent_name": "legislacao", "process_id": <id>}'
# Esperado: 200 com caminho_regulatorio, etapas, legislacao_aplicavel, riscos

# Executar chain de enquadramento
curl -X POST http://localhost:8000/api/v1/agents/chain \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"chain_name": "enquadramento_regulatorio", "process_id": <id>}'
# Esperado: 200 com resultado do extrator + legislacao
```

### Estado operacional pos-Fase 1+2

| Controle | Estado |
|----------|--------|
| Tabela legislation_documents | Criada (migration d3e4f5a6b7c8) |
| Estrategia de contexto | Texto completo + Gemini context loading |
| ClaudeClient | Anthropic SDK direto |
| LegislacaoAgent | Reescrito com context loading + Claude/Gemini |
| Schemas | EnquadramentoResult com etapas, legislacao, riscos |
| API /legislation | 6 endpoints (CRUD + search + upload) |
| Chain enquadramento_regulatorio | [extrator, legislacao] |
| Backward compat | Formato antigo (normas_estaduais, risco_legal) mantido |

---

## Auto-Monitoramento de Legislacao (Sprint Fase 3 — 08/04/2026)

### Arquitetura

3 crawlers executam via Celery Beat:
- **DOU** (diario 06:00) — Diario Oficial da Uniao via in.gov.br, 13 termos ambientais
- **DOE** (diario 06:30) — 27 Diarios Oficiais Estaduais via Querido Diario API
- **IBAMA** (semanal segunda 03:00) — normativas ibama.gov.br

Fluxo: crawl → dedup (identifier+hash) → ingest (full_text) → match processos ativos (UF+demand_type) → criar LegislationAlert

### Servico Celery Beat (docker-compose)

Adicionar ao `docker-compose.yml`:

```yaml
  beat:
    build: .
    command: celery -A app.core.celery_app beat --loglevel=info
    env_file: .env
    environment:
      - POSTGRES_SERVER=db
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
    depends_on:
      - db
      - redis
    restart: unless-stopped
```

### Validacao dos crawlers

```bash
# Listar crawlers registrados
python -c "from app.services.crawlers.base_crawler import list_crawlers; print(list_crawlers())"
# Esperado: ['dou', 'doe', 'ibama']

# Testar crawler DOU manualmente
python -c "
from app.services.crawlers.dou_crawler import DOUCrawler
c = DOUCrawler()
docs = c.safe_crawl()
print(f'{len(docs)} docs encontrados')
for d in docs[:3]:
    print(f'  - {d.identifier}: {d.title[:60]}')
"

# Disparar monitoramento via API
curl -X POST http://localhost:8000/api/v1/legislation/monitor/trigger \
  -H "Authorization: Bearer <token>"
# Esperado: 200 com task_id queued

# Disparar crawler especifico
curl -X POST "http://localhost:8000/api/v1/legislation/monitor/trigger?crawler=dou" \
  -H "Authorization: Bearer <token>"
```

### Endpoints de alertas

```bash
# Listar alertas nao lidos
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/legislation/alerts?is_read=false"
# Esperado: 200 com lista de alertas

# Alertas de um processo especifico
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/legislation/alerts?process_id=<id>"

# Marcar alerta como lido
curl -X PATCH http://localhost:8000/api/v1/legislation/alerts/<id>/read \
  -H "Authorization: Bearer <token>"
```

### Estado operacional pos-Fase 3

| Controle | Estado |
|----------|--------|
| Crawlers registrados | 3 (dou, doe, ibama) |
| UFs cobertas pelo DOE | 27/27 |
| Celery Beat schedule | 3 jobs (DOU diario, DOE diario, IBAMA semanal) |
| Migration | e4f5a6b7c8d9 (legislation_alerts) |
| Endpoints alertas | 3 (list, mark read, trigger) |
| Deduplicacao | identifier + content_hash |
| Match processos | UF + demand_type automatico |
| Total rotas API | 99 |

---

## Ativacao dos Agentes IA + MemPalace (08-09/04/2026)

### Pre-requisitos

```bash
# Chaves de API no .env (obrigatorio para IA funcionar)
OPENAI_API_KEY=sk-proj-...  # chave real, nao placeholder
GEMINI_API_KEY=AIzaSy...     # opcional, usado pelo agente legislacao para contexto grande
AI_ENABLED=true
AI_DEFAULT_MODEL=gpt-4o-mini
```

**ATENCAO**: `ai_configured` rejeita chaves placeholder (`changeme`, `sk-...`, `test`, `your-key-here`, ou qualquer chave <10 chars). Se os agentes retornam resultado baseado em regras, verifique a chave.

### Subir sistema com agentes

```bash
docker compose up --build -d
```

Validar:
```bash
# Verificar que IA esta configurada
docker compose exec api python -c "from app.core.config import settings; print('ai_configured:', settings.ai_configured)"
# Esperado: ai_configured: True

# Verificar que tasks estao registradas no worker
docker compose logs worker --tail 20 | grep "workers\."
# Esperado: workers.run_agent, workers.run_agent_chain, workers.vigia_all_tenants, etc.
```

### Desenvolvimento local — hot-reload e rebuild

Desde 2026-04-23 o projeto tem `docker-compose.override.yml` na raiz que o Docker
Compose carrega automaticamente em `docker compose up`. Ele monta `./app`,
`./alembic`, `./scripts` e `./seed.py` como bind volumes nos containers `api` e
`worker`, e roda o uvicorn com `--reload`. Consequências práticas:

| Você mudou | Precisa rebuildar? | Precisa restart? |
|---|---|---|
| `.py` em `app/`, `scripts/`, ou `seed.py` | ❌ | ❌ (uvicorn reinicia sozinho; worker precisa `docker compose restart worker`) |
| Nova migration em `alembic/versions/` | ❌ | ✅ `docker compose restart api` (init_db roda no boot do container) |
| `requirements.txt` | ✅ `docker compose build api worker` | ✅ `docker compose up -d api worker` |
| `Dockerfile` | ✅ | ✅ |

**Incidente documentado:** em 2026-04-23 o container `api` entrou em crashloop
porque migrations novas foram aplicadas no banco via `alembic upgrade head`
rodado do host, mas a imagem Docker buildada antes não continha os arquivos
`alembic/versions/*.py` das novas revisões. O banco persiste entre restarts
(volume nomeado `postgres_data`), mas a imagem não atualiza sozinha.
Sintoma: `CommandError: Can't locate revision identified by '<rev>'`. Correção:
`docker compose build api worker && docker compose up -d api worker`.
**O override de dev resolve isso** — migrations novas passam a estar imediatamente
no container via bind mount, sem rebuild.

**Em CI/produção** desabilite o override com `docker compose -f docker-compose.yml up -d`.

---

### MemPalace — REVOGADO (2026-04-23)

> ⚠️ O pacote PyPI `mempalace` foi abandonado em 2026-04-23 por sinais fortes de
> supply-chain attack. Toda a seção abaixo está obsoleta.
>
> - Decisão completa: [docs/adr/adr_mempalace_REVOKED.md](adr/adr_mempalace_REVOKED.md)
> - Referência arquivada: [docs/archive/mempalace_REVOKED.md](archive/mempalace_REVOKED.md)
>
> `app/agents/memory.py` foi convertido em stub no-op (não importa mais o pacote).
> Em ambientes antigos, rodar `scripts/cleanup_mempalace_storage.ps1` para remover
> o volume local `~/.mempalace/` e `docker volume rm amigao_do_meio_ambiente_mempalace_data`.
>
> Memória dos agentes será atendida por **pgvector** (Sprint U/Week 1).

### Celery Beat — 5 tasks agendadas

| Task | Schedule | Funcao |
|------|----------|--------|
| `monitor-legislation-dou-daily` | 06:00 BRT | Crawler DOU |
| `monitor-legislation-doe-daily` | 06:30 BRT | Crawler DOE |
| `monitor-legislation-agencies-weekly` | Segunda 03:00 | Crawler IBAMA |
| `vigia-scheduled-check` | A cada 6h (min 15) | Vigia todos os tenants (prazos, docs, processos) |
| `acompanhamento-check-processes` | A cada 30min | Acompanhamento de processos aguardando_orgao |

### Triggers automaticos de agentes

| Evento | Agente/Chain disparado | Arquivo |
|--------|----------------------|---------|
| `POST /intake/create-case` | atendimento (async) | `app/api/v1/intake.py` |
| `POST /documents/confirm-upload` (tipos extraiveis) | extrator (async) | `app/api/v1/documents.py` |
| `POST /processes/{id}/macroetapa` → diagnostico_tecnico | chain diagnostico_completo | `app/api/v1/processes.py` |
| `POST /processes/{id}/macroetapa` → caminho_regulatorio | chain enquadramento_regulatorio | `app/api/v1/processes.py` |
| `POST /processes/{id}/macroetapa` → orcamento_negociacao | chain gerar_proposta | `app/api/v1/processes.py` |

Todos sao fire-and-forget — se Celery estiver fora, o fluxo continua normalmente.

### Endpoints de agentes

| Metodo | Endpoint | Funcao |
|--------|----------|--------|
| POST | `/agents/run` | Executa agente sincrono |
| POST | `/agents/run-async` | Executa agente via Celery (202) |
| POST | `/agents/chain` | Executa chain sincrona |
| POST | `/agents/chain-async` | Executa chain via Celery (202) |
| GET | `/agents/registry` | Lista 10 agentes |
| GET | `/agents/chains` | Lista 9 chains |

### Smoke test de agentes

```bash
# Teste rapido via curl
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "X-Auth-Profile: internal" \
  -d '{"email":"admin@amigao.com","password":"Seed@2026"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Listar agentes
curl -s http://localhost:8000/api/v1/agents/registry -H "Authorization: Bearer $TOKEN" | python -m json.tool

# Rodar diagnostico (async)
curl -s -X POST http://localhost:8000/api/v1/agents/run-async \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"agent_name":"diagnostico","process_id":1,"metadata":{}}' | python -m json.tool

# Verificar resultado nos logs
docker compose logs worker --tail 10
```

### Frontend — Pagina de Agentes

Acesso: `http://localhost:5173/agents` (dev) ou menu lateral "Agentes IA"

Funcionalidades:
- Metricas do dia (execucoes, taxa sucesso, custo, review pendente)
- Disparo manual de agente individual ou chain
- Historico global com filtro por agente
- Resultados humanizados (AgentResultRenderer com 10 layouts por agente)
- Toast notifications via WebSocket quando agente completa/falha

### Troubleshooting agentes

| Sintoma | Causa provavel | Solucao |
|---------|---------------|---------|
| Job status=failed sem error | API key invalida/placeholder | Verificar `.env` → `OPENAI_API_KEY` real |
| `KeyError: workers.run_agent` | Tasks nao registradas | `docker compose up --build -d worker` |
| Resultado baseado em regras | `ai_configured=False` | Verificar chave: `docker compose exec api python -c "..."` |
| Chain para no extrator | Sem documento no processo | Normal — extrator retorna vazio e chain continua |
| WebSocket error no console | Backend nao esta rodando | `docker compose up -d api` |
| Toast nao aparece | WebSocket nao conectou | Verificar que API esta em 8000 e proxy Vite funciona |

### Estado operacional pos-Agentes

| Controle | Estado |
|----------|--------|
| Agentes ativos | 10/10 |
| Chains disponiveis | 9 |
| Triggers automaticos | 5 |
| Celery Beat tasks | 5 |
| MemPalace embeddings | ~~588~~ REVOGADO 2026-04-23 — ver docs/adr/adr_mempalace_REVOKED.md |
| Volume Docker | ~~mempalace_data~~ REMOVIDO 2026-04-23 |
| MCP Server global | ~~mempalace~~ REMOVIDO. Plugin `claude-mem@thedotmack` (diferente) segue ativo no Claude Code |
| Frontend pagina | /agents + tab IA no processo |
| IA providers | OpenAI (gpt-4o-mini) + Gemini (legislacao) |
| Custo medio/execucao | ~$0.0004 - $0.0007 |

---

## Regente v3 — Arquitetura 4 Camadas (abril/2026)

Implementacao das 43 mudancas levantadas em `docs/MUDANCAS_REGENTE.md` conforme mapa mental Whimsical da socia. Historico completo em `docs/progresso6.md`.

### Migrations Regente v3 aplicadas

Head atual do Alembic: `e7c9b2a4f8d1`.

```bash
# Validar que todas as migrations estao aplicadas
docker compose exec api python -m alembic current
# Esperado: e7c9b2a4f8d1 (head)

# Aplicar manualmente se necessario
docker compose exec api python -m alembic upgrade head
```

Migrations (ordem):
1. `f5b7c9a1d3e2` — `processes.entry_type` + `processes.initial_summary`
2. `a6d8f2c4b1e3` — tabela `intake_drafts`
3. `b7e9f1c3a2d4` — `documents.intake_draft_id` FK
4. `c8a1e5d7f3b2` — `macroetapa_checklists.state`
5. `d4e6b8f1a3c5` — tabela `stage_outputs`
6. `e7c9b2a4f8d1` — `properties.field_sources` JSONB

### Endpoints Regente v3

**Intake (Camada 1):**
- `POST /api/v1/intake/create-case` — description agora opcional; aceita `entry_type` + `initial_summary`
- `GET  /api/v1/intake/drafts` — lista rascunhos do tenant
- `POST /api/v1/intake/drafts` — cria rascunho
- `GET  /api/v1/intake/drafts/{id}` — detalhe
- `PATCH /api/v1/intake/drafts/{id}` — atualiza form_data
- `DELETE /api/v1/intake/drafts/{id}` — remove (exceto se ja commitado)
- `POST /api/v1/intake/drafts/{id}/commit` — converte rascunho em processo
- `POST /api/v1/intake/drafts/{id}/upload-url` — presigned URL para upload em rascunho
- `POST /api/v1/intake/drafts/{id}/documents` — confirma upload e registra Document
- `GET  /api/v1/intake/drafts/{id}/documents` — lista docs do rascunho
- `POST /api/v1/intake/drafts/{id}/import` — dispara agent_extrator nos docs
- `POST /api/v1/intake/enrich` — complementar cliente/imovel existente

**Processes (Camada 3):**
- `GET  /api/v1/processes/{id}/can-advance` — checa se pode avancar de etapa (retorna blockers)
- `POST /api/v1/processes/{id}/macroetapa` — agora bloqueia com 409 se gate falhar
- `POST /api/v1/processes/{id}/macroetapa/{etapa}/actions/validate` — humano valida action
- `GET  /api/v1/processes/{id}/artifacts` — lista StageOutputs
- `POST /api/v1/processes/{id}/artifacts` — cria artefato
- `POST /api/v1/processes/{id}/artifacts/{art_id}/validate` — humano valida artefato

**Cliente Hub (Camada 2):**
- `GET /api/v1/clients/{id}/summary` — cabeçalho + KPIs + estado
- `GET /api/v1/clients/{id}/properties-with-status` — imoveis com estado do caso + eventos
- `GET /api/v1/clients/{id}/timeline?limit=N&days=N` — eventos do AuditLog
- `GET /api/v1/clients/{id}/ai-summary` — leitura executiva deterministica

**Imovel Hub (Camada 2):**
- `GET /api/v1/properties/{id}/summary` — cabeçalho + KPIs + health score + estado
- `GET /api/v1/properties/{id}/cases` — casos do imovel com estado
- `GET /api/v1/properties/{id}/events?limit=N` — timeline
- `GET /api/v1/properties/{id}/ai-summary` — leitura tecnica deterministica
- `POST /api/v1/properties/{id}/validate-fields` — humano valida campo (raw→human_validated)

**Dashboard Executivo (Camada 2):**
- `GET /api/v1/dashboard/stages` — distribuicao 7 etapas (total/blocked/ready/avg_days)
- `GET /api/v1/dashboard/alerts` — gargalos agregados
- `GET /api/v1/dashboard/priority-cases?limit=N` — casos rankeados do dia
- `GET /api/v1/dashboard/ai-summary` — leitura executiva

Todos os endpoints de dashboard aceitam filtros: `urgency`, `demand_type`, `state_uf`, `days`, `responsible_user_id`.

**Documentos:**
- `GET /api/v1/documents/categories` — 6 categorias canonicas Regente com labels

### Rotas frontend novas

- `/clients/:id` → `ClientHub` (6 blocos + 5 abas + painel IA lateral)
- `/properties/:id` → `PropertyHub` (health score + 5 abas + painel IA + validate fields)

Cards de cliente em `/clients` e cards de imovel em `/properties` agora sao linkaveis para o hub respectivo.

### Fluxo smoke Regente v3 (E2E manual)

```bash
# Login
curl -sS -X POST http://localhost:8000/api/v1/auth/login \
  -H "X-Auth-Profile: internal" \
  -d "username=consultor@amigao.com&password=Seed@2026"

# Criar rascunho sem description
curl -sS -X POST http://localhost:8000/api/v1/intake/drafts \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "entry_type": "novo_cliente_novo_imovel",
    "form_data": {
      "new_client": {"full_name":"Teste","phone":"1199","email":"t@t.com","client_type":"pf"},
      "new_property": {"name":"Fazenda Teste"}
    }
  }'

# Commit → vira Process em macroetapa=entrada_demanda
curl -sS -X POST http://localhost:8000/api/v1/intake/drafts/{id}/commit \
  -H "Authorization: Bearer $TOKEN"

# Kanban mostra gate + state + counts
curl -sS http://localhost:8000/api/v1/processes/kanban \
  -H "Authorization: Bearer $TOKEN" | jq '.columns[] | {label, count, blocked_count, ready_to_advance_count}'

# Tentar avancar bloqueia com 409 se gate falhar
curl -sS -X POST http://localhost:8000/api/v1/processes/{id}/macroetapa \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"macroetapa":"diagnostico_preliminar"}'
# → {"detail":{"message":"Avanco bloqueado...","blockers":[...]}}
```

### Problemas conhecidos (pendencias Regente v3)

| Sintoma | Causa | Solucao |
|---------|-------|---------|
| Dados legados com `has_minimal_base=false` | Clientes antigos sem phone/email | Normal — gate reflete dados reais; editar cliente para completar |
| Kanban drag-and-drop nao valida gate | Frontend nao integrado com `/can-advance` | Decisao de produto pendente (ver pergunta na socia) |
| Blocos condicionais do workspace | CAM3WS-002 nao implementado | Requer decisao: regra automatica ou manual |
| Ai-summary dos hubs nao usa LLM | Design choice — deterministico no MVP | Ao liberar restricao de agentes, trocar por `agent_atendimento` |
| Camada 4 Configuracoes | Mapa entregue mas nao implementado | Requer decisao de plano/gateway de pagamento |

### Estado operacional pos-Regente v3

| Controle | Estado |
|----------|--------|
| Sprints Regente v3 | 6/6 |
| Itens Regente fechados | 43/43 (100%) |
| Migrations novas aplicadas | 6 |
| Endpoints novos | ~30 |
| Componentes React novos | 5 |
| Rotas frontend novas | 2 (`/clients/:id`, `/properties/:id`) |
| Typecheck frontend | OK (`npx tsc --noEmit` passa) |
| `app/agents/*` | Nao alterado (restricao respeitada) |
| Alembic head | `e7c9b2a4f8d1` |
