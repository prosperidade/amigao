# Auditoria Completa + Plano de Implementação — Amigão do Meio Ambiente

**Data:** 2026-04-03  
**Maturidade Geral: 65% (AMARELO)**  
**Esforço total estimado para correções:** ~110 horas (~14 dias úteis)

---

# PARTE 1 — AUDITORIA COMPLETA

---

## RESUMO EXECUTIVO

O sistema é um SaaS multi-tenant bem arquitetado com fundação sólida, mas apresenta **11 vulnerabilidades críticas**, **18 de alto risco** e **24 de médio risco** que precisam ser resolvidas antes de ir para produção.

---

## 1. BACKEND (FastAPI) — 75% Maturo

### 1.1 Funcionalidades Implementadas

- 14 routers REST completos (auth, clients, processes, documents, tasks, dashboard, AI, proposals, contracts, intake, checklists, workflows, dossier, threads)
- Máquina de estados completa: Process (11 estados), Task (7 estados), Document (7 estados), AIJob (6 estados)
- Multi-tenancy com `tenant_id` em todas as queries via BaseRepository
- JWT com perfis `internal` e `client_portal`
- AI Gateway multi-provider via LiteLLM (OpenAI, Gemini, Claude)
- 7 tipos de Celery tasks (email, PDF, AI summarization, audit)
- Métricas Prometheus artesanais + tracing W3C traceparent
- Webhook alerts com HMAC signing
- Startup warm-up (DB, security, storage)
- Structured logging JSON com correlation IDs
- WebSocket real-time events via Redis pub/sub

### 1.2 Visão Geral dos Routers

| Router | Linhas | Issues | Notas |
|--------|--------|--------|-------|
| **auth.py** | 132 | HIGH | Email normalization OK; falta brute-force protection |
| **clients.py** | 78 | MEDIUM | CRUD simples; sem soft delete |
| **processes.py** | 179 | CRITICAL | Falta validação de client_id no update; N+1 no list |
| **documents.py** | 149 | HIGH | Risco de SQL injection em parsing de extensão |
| **properties.py** | 64 | LOW | CRUD simples; geoalchemy sem index |
| **tasks.py** | 211 | CRITICAL | Risco de deadlock em dependências; falta cascade |
| **intake.py** | 308 | HIGH | Checklist template com N+1; sem paginação |
| **checklists.py** | 210 | MEDIUM | Link de documento via checklist_item_id frágil |
| **workflows.py** | 199 | MEDIUM | Versionamento de template não implementado |
| **proposals.py** | 334 | HIGH | Geração de proposta sem transaction boundary |
| **contracts.py** | 278 | MEDIUM | Geração de PDF síncrona (bloqueante) |
| **dashboard.py** | 155 | CRITICAL | Múltiplas N+1 queries; sem paginação |
| **dossier.py** | 141 | MEDIUM | Sem soft delete para items do dossiê |
| **threads.py** | 66 | LOW | API de comunicação simples; sem paginação |
| **ai.py** | 278 | CRITICAL | Validação de custo ausente; sem timeout handling |

### 1.3 Bugs Críticos Encontrados

| # | Issue | Arquivo | Linha | Impacto |
|---|-------|---------|-------|---------|
| 1 | **Client tenant validation ausente** no JWT — portal pode acessar dados de outro tenant | `app/api/deps.py` | L70, L101-123 | Vazamento cross-tenant |
| 2 | **Secrets exportadas para os.environ** a cada chamada IA | `app/core/ai_gateway.py` | L39-46 | Secrets visíveis em crash dumps |
| 3 | **N+1 queries no Dashboard** — lazy load sem joinedload | `app/api/v1/dashboard.py` | L68-78, L99-122 | Performance degradada |
| 4 | **Custo IA sem validação** — sem limite de gastos por tenant | `app/api/v1/ai.py` | L66-74 | Gastos descontrolados |
| 5 | **Dependências circulares em Tasks** — sem detecção de ciclos | `app/api/v1/tasks.py` | L66-80 | Loop infinito / deadlock |
| 6 | **Tenant filter ausente** em `count_incomplete_tasks` | `app/repositories/` | process_repo | Contagem cross-tenant |
| 7 | **AuditLog hash chain nunca populada** — campos hash sempre NULL | `app/models/audit_log.py` | L28-29 | Integridade auditoria comprometida |
| 8 | **Soft delete inconsistente** — Document não tem `deleted_at` | `app/models/document.py` | - | Dados fantasma em listagens |

### 1.4 Bugs de Alto Risco

| # | Issue | Arquivo | Linha |
|---|-------|---------|-------|
| 1 | Token payload com catch genérico `Exception` — mascara erros reais | `app/api/deps.py` | L50-64 |
| 2 | Tenant ID fallback do header HTTP — logs podem mostrar tenant errado | `app/api/middleware.py` | L21 |
| 3 | SQL injection risk em parsing de extensão de arquivo | `app/api/v1/documents.py` | L82 |
| 4 | Deadlock risk em validação de status de tasks | `app/api/v1/tasks.py` | L66-80 |
| 5 | Proposal generation sem transaction boundary | `app/api/v1/proposals.py` | - |
| 6 | PDF generation síncrona bloqueando thread | `app/api/v1/contracts.py` | - |
| 7 | Redis client criado a cada evento — sem connection pooling | `app/services/notifications.py` | L33-40 |
| 8 | Storage bucket state per-process — multi-worker inconsistente | `app/services/storage.py` | L17-19 |
| 9 | WebSocket sem JWT error handling — exceções não tratadas | `app/api/websockets.py` | L125-169 |
| 10 | WebSocket sem tenant validation no user lookup | `app/api/websockets.py` | L136-140 |
| 11 | CORS permite todos os métodos e headers | `app/main.py` | L87-88 |
| 12 | Sem security headers (HSTS, X-Frame-Options, CSP) | `app/main.py` | - |
| 13 | Sem rate limiting em nenhum endpoint | `app/main.py` | - |
| 14 | Swagger/OpenAPI exposto publicamente em produção | `app/main.py` | L76 |

### 1.5 Core Services

#### **security.py** — Sólido
- Password hashing com bcrypt
- JWT creation com tenant_id
- `warm_up_security()` implementado
- **Falta:** Validação de força de senha

#### **logging.py** — Excelente
- Context vars injetadas (request_id, tenant_id, user_id, trace_id)
- Formato JSON em produção
- Libs externas silenciadas
- **Falta:** Log sampling para endpoints de alto volume

#### **metrics.py** — Sofisticado
- Formato Prometheus compatível
- Thread-safe com locks
- Suporte para métricas compartilhadas via Redis
- Histogram com buckets configuráveis
- **Issue:** Métricas compartilhadas só funcionam se `service_name == "worker"`

#### **tracing.py** — Correto
- Implementação W3C traceparent
- Validação hex adequada
- **Falta:** Integração OpenTelemetry

#### **alerts.py** — Forte
- HMAC signing para integridade de webhook
- Filtro por severidade
- Propagação de trace/span
- **Issue:** Webhook sem retry (fire-and-forget)

#### **ai_gateway.py** — Problemas Críticos
- API keys exportadas para `os.environ` permanentemente (L39-46)
- Sem timeout enforcement no litellm (L100-120)
- Cálculo de custo falha silenciosamente (L118)
- Sem validação de custo acumulado por tenant

### 1.6 Workers Celery

| Worker | Status | Issues |
|--------|--------|--------|
| `test_job` | Funcional | Hardcoded, apenas para smoke test |
| `log_document_uploaded` | Funcional | Não valida se documento existe no DB |
| `send_email_notification` | Funcional | Exceção pode logar password SMTP |
| `generate_pdf` | Funcional | 1 teste falhando (mock issue) |
| `generate_weekly_summary` | Parcial | Usa litellm direto sem AIJob record |
| `process_document_ocr` | Parcial | Sem error handling para timeout |
| `send_webhook_alert` | Funcional | Sem retry com backoff |

### 1.7 Repositories

- `BaseRepository` com tenant scoping correto via `_base_query()`
- **Issue:** Sem limite máximo de paginação (client pode pedir `limit=1000000`)
- **Issue:** `ProcessRepository.get_scoped` com N+1 em relacionamentos
- **Issue:** `ProcessRepository.count_incomplete_tasks` sem filtro de tenant_id

---

## 2. BANCO DE DADOS & MIGRATIONS — 90% Maturo

### 2.1 Migration Chain — Íntegra

15 migrations em cadeia linear sem gaps:
1. `a8905cb51eb1` — Initial schema
2. `b69a429faaa4` — Add document model
3. `afcea9834c04` — Correct models ProcessStatus 11 states
4. `d7515c8f0c3b` — Add task model
5. `ca481d367022` — Add auditlog model
6. `e91d20acba9c` — Sprint 2 models
7. `f2a1c4b6d8e9` — Align task status machine
8. `a1b2c3d4e5f6` — Sprint 1 intake
9. `b3c4d5e6f7a8` — Sprint 2 checklist document fields
10. `c4d5e6f7a8b9` — Sprint 3 workflow templates
11. `d5e6f7a8b9c0` — Sprint 4 proposals contracts
12. `e5f6a7b8c9d0` — Sprint 5 AI jobs
13. `d7f9a24dd5a7` — Add prompt templates table
14. `024fe3f5dbeb` — Seed prompt templates data

### 2.2 Modelos (18 total) — Alinhados com Migrations

Tenant, User, Client, Process, Property, Document, Task, AuditLog, Communication (Thread+Message), ChecklistTemplate, Contract, ContractTemplate, Proposal, WorkflowTemplate, PromptTemplate, AIJob — todos alinhados.

### 2.3 Indexes Ausentes — CRÍTICO

| Tabela | Coluna(s) | Impacto |
|--------|-----------|---------|
| **processes** | `(tenant_id, status)` | CRÍTICO — workflow filtering |
| **processes** | `(tenant_id, due_date)` | ALTO — timeline queries |
| **processes** | `deleted_at` | MÉDIO — soft delete filtering |
| **tasks** | `(tenant_id, status)` | CRÍTICO — task board filtering |
| **tasks** | `(assigned_to_user_id, status)` | ALTO — workload queries |
| **tasks** | `(tenant_id, due_date)` | MÉDIO — overdue queries |
| **documents** | `(tenant_id, ocr_status)` | ALTO — OCR pipeline |
| **documents** | `(tenant_id, document_type)` | MÉDIO — classification queries |
| **documents** | `(process_id, document_type)` | MÉDIO — process documents |
| **clients** | `(tenant_id, status)` | MÉDIO — lead/active filtering |
| **proposals** | `(tenant_id, status)` | MÉDIO — proposal pipeline |
| **contracts** | `(tenant_id, status)` | MÉDIO — contract lifecycle |
| **audit_logs** | `(tenant_id, entity_type, entity_id, created_at DESC)` | ALTO — audit queries |
| **communication_threads** | `(tenant_id, created_at DESC)` | ALTO — recent threads |

### 2.4 Session Management — Subconfigurado

**Arquivo:** `app/db/session.py`

```python
engine = create_engine(settings.SQLALCHEMY_DATABASE_URI, pool_pre_ping=True)
```

**Problemas:**
- Pool size default (5 conexões) — insuficiente para multi-tenant
- Sem `pool_recycle` — conexões podem expirar
- Sem `max_overflow` — pode criar conexões ilimitadas
- Sem `statement_timeout` — queries podem travar
- Sem `expire_on_commit` — lazy-load queries pós-commit

### 2.5 Integridade de Dados

- **Sem CASCADE delete** — todas as FKs usam RESTRICT (default)
- **`properties.registry_number`** sem unique constraint por tenant
- **`clients.cpf_cnpj`** sem unique constraint por tenant
- **AuditLog hash fields** nullable (True) — quebra integridade da chain
- **Proposal.scope_items** é JSON sem schema validation

### 2.6 PostGIS — Correto

- Extensão PostGIS criada via migration
- SRID 4674 (SIRGAS 2000) correto para coordenadas brasileiras
- GIST spatial index criado para `properties.geom`

---

## 3. FRONTEND (React/Vite) — 65% Maturo

### 3.1 O que está bom

- TypeScript strict mode com **zero `any`** types
- React Query corretamente configurado com caching
- Zustand com persist para auth
- ESLint strict + Vitest configurado (21 testes)
- Upload via presigned URLs funcional
- Skeleton components para loading states
- Bundle size: 416 kB (dentro do alvo < 500 kB)
- Sem vulnerabilidades XSS (sem dangerouslySetInnerHTML)
- Sem memory leaks detectados

### 3.2 Problemas Encontrados

| Severidade | Issue | Arquivo | Linha |
|------------|-------|---------|-------|
| CRÍTICO | **Credenciais hardcoded** (`admin@amigao.com` / `admin123`) no Login | `frontend/src/pages/Auth/Login.tsx` | L9-10 |
| ALTO | **Sem Error Boundary** — app inteiro quebra em white screen | App.tsx | - |
| MÉDIO | **`alert()` usado** em vez de toast/modal (5 ocorrências) | Múltiplos | - |
| MÉDIO | **URL hardcoded** `localhost:3000` no erro do Login | `frontend/src/pages/Auth/Login.tsx` | L38 |
| MÉDIO | **Proxy hardcoded** `127.0.0.1:8000` | `frontend/vite.config.ts` | L10 |
| MÉDIO | **console.error** sem structured logging (5 ocorrências) | Múltiplos | - |
| BAIXO | **Acessibilidade** — divs clicáveis sem role/keyboard support | Dashboard, Modals | - |
| BAIXO | **timeAgo()** recalculado em cada render sem memoização | `frontend/src/pages/Dashboard/index.tsx` | L95-101 |
| BAIXO | **Sem focus trap** em modais/drawers | Múltiplos | - |

### 3.3 Componentes e Páginas

- **Login** — Funcional, com error handling (mas credenciais hardcoded)
- **Dashboard** — Completo com skeleton, KPIs, activities, tasks
- **Processes** — Kanban com drag-and-drop, modal de criação, status transitions
- **ProcessDetail** — Tabs (diagnosis, dossier, documents, tasks, timeline, proposals, contracts)
- **Clients** — CRUD completo
- **Properties** — CRUD com campos geoespaciais
- **IntakeWizard** — Multi-step form funcional
- **ProposalEditor** — Edição com scope items
- **ContractEditor** — Visualização com download
- **DocumentUpload / DocumentUploadZone** — Upload com drag-and-drop

---

## 4. PORTAL DO CLIENTE (Next.js 16) — 70% Maturo

### 4.1 O que está bom

- `next/font/local` corretamente usado (não Google Fonts)
- Auth guards no layout com hydration check
- Upload via `fetch()` (não axios) para presigned URLs
- Strict TypeScript habilitado
- Docker standalone output configurado
- Proper metadata no root layout

### 4.2 Problemas Encontrados

| Severidade | Issue | Arquivo |
|------------|-------|---------|
| MÉDIO | **`any` type em 3 catch blocks** | login, dashboard, process detail |
| MÉDIO | **Sem metadata por página** — SEO básico apenas | Todas as rotas |
| MÉDIO | **console.error expõe detalhes** no login | `client-portal/src/app/login/page.tsx` L44 |
| BAIXO | **Zustand subscription no módulo** — não ideal para App Router | `client-portal/src/lib/api.ts` L12-18 |
| BAIXO | **Sem diretório components/** — tudo inline nas páginas | Estrutura |

### 4.3 Rotas e Proteção

| Rota | Protegida | Método | Status |
|------|-----------|--------|--------|
| `/` | N/A | Redirect para /login | OK |
| `/login` | N/A | Pública | OK |
| `/dashboard` | SIM | Auth check no layout | OK |
| `/dashboard/process/[id]` | SIM | Herda do layout | OK |

---

## 5. APP MOBILE (Expo) — 30% Maturo

### 5.1 O que está bom

- `expo-secure-store` usado corretamente (não AsyncStorage)
- SQLite com WAL mode para offline-first
- Sync queue implementada
- NetInfo para detecção de rede
- Camera + GPS com permissões corretas
- Optimistic updates em task status
- Evidence capture com foto + geolocalização

### 5.2 Problemas Encontrados

| Severidade | Issue | Arquivo | Linha |
|------------|-------|---------|-------|
| ALTO | **IP hardcoded** `192.168.1.42:8000` como fallback | `mobile/src/lib/api.ts` | L7 |
| ALTO | **Sem response interceptor** (401/403) — sem auto-logout | `mobile/src/lib/api.ts` | - |
| ALTO | **DELETE destrutivo no sync** — apaga TODOS dados locais antes de sincronizar | `mobile/src/services/SyncService.ts` | L24-25 |
| MÉDIO | **Fetch sem error handling** no upload de evidências | `mobile/src/services/EvidenceService.ts` | L140-146 |
| MÉDIO | **expo-env.d.ts vazio** — sem tipos para env vars | `mobile/expo-env.d.ts` | - |
| MÉDIO | **Sem input validation** no login (empty check) | `mobile/app/login.tsx` | - |
| MÉDIO | **Sem exponential backoff** no retry de sync | `mobile/src/services/SyncService.ts` | - |
| MÉDIO | **Sem idempotency check** na fila de sync | `mobile/src/services/SyncService.ts` | L108-122 |

### 5.3 Telas Implementadas

- **Login** — Funcional com SecureStore
- **Process List** — Offline-first via SQLite, pull-to-refresh, sync button
- **Process Detail** — Task management com optimistic updates
- **Evidence Capture** — Foto + GPS + sync queue
- **Navigation** — Tab-based com auth guard no _layout

---

## 6. SEGURANÇA & INFRAESTRUTURA

### 6.1 Vulnerabilidades Críticas

| # | Issue | Arquivo | Impacto |
|---|-------|---------|---------|
| 1 | **Chave OpenAI real exposta** no `.env` | `.env` L52 | Uso indevido da API |
| 2 | **Senha Gmail real** no `.env` | `.env` L34 | Acesso email não autorizado |
| 3 | **CORS `allow_methods=["*"]` + `allow_headers=["*"]`** | `app/main.py` L87-88 | CSRF amplificado |
| 4 | **Sem rate limiting** em nenhum endpoint | `app/main.py` | Brute force no login |
| 5 | **Token expiry 24h** no docker-compose (default 1440 min) | `docker-compose.yml` L74,137 | Exposição prolongada |
| 6 | **Swagger/OpenAPI público** em produção | `app/main.py` L76 | Exposição de endpoints |
| 7 | **Sem security headers** (HSTS, X-Frame-Options, CSP) | `app/main.py` | XSS/clickjacking |
| 8 | **Redis/MinIO sem autenticação** expostos em portas públicas | `docker-compose.yml` | Acesso direto aos dados |
| 9 | **DB password default "password"** no docker-compose | `docker-compose.yml` L6 | Acesso trivial |
| 10 | **DB connection string logada** com senha em plaintext | `app/db/init_db.py` L22 | Exposição em logs |

### 6.2 O que está bom

- JWT Algorithm HS256 com SECRET_KEY validada (>= 32 chars)
- Password hashing com bcrypt + salt
- Tenant isolation enforced via AccessContext
- `.env` no `.gitignore`
- Validação de config em produção (config.py L169-213)
- Profile-based access control (internal vs client_portal)
- Audit logging implementado
- Containers rodam como non-root user (appuser/nextjs)

### 6.3 Docker Infrastructure

| Serviço | Imagem | Healthcheck | Portas |
|---------|--------|-------------|--------|
| PostgreSQL | postgis/postgis:15-3.3 | pg_isready | 5433:5432 |
| Redis | redis:7-alpine | redis-cli ping | 6379:6379 |
| MinIO | minio/minio | **AUSENTE** | 9000, 9001 |
| API | python:3.11-slim | - | 8000 |
| Worker | python:3.11-slim | - | - |
| Client Portal | node (Next.js) | - | 3000 |

---

## 7. TESTES — 60% Cobertura

### 7.1 Suite Atual

```
Backend: 115 testes total
├── 114 passando
├── 1 falha pré-existente (test_pdf_generator — mock issue)
├── Cobertura por camada:
│   ├── Models: 100% (5 modelos core)
│   ├── Services: 68% (AI persistence, email, storage)
│   ├── API endpoints: 68% (auth, clients, processes, documents, dashboard)
│   └── State machines: 64 testes de contrato dedicados
└── Tempo: ~69 segundos

Frontend Vite: 21 testes + ESLint strict
Portal Next.js: 0 testes unitários (build only)
Mobile: 0 testes
```

### 7.2 Arquivos de Teste

**API Tests (8 arquivos):**
- `test_auth.py`, `test_clients.py`, `test_processes.py`, `test_documents.py`
- `test_dashboard.py`, `test_tasks.py`, `test_ai.py`, `test_observability.py`

**Agent/ML Tests (3 arquivos):**
- `test_classifier_extractor_refactor.py`, `test_prompt_service.py`, `test_prompt_template_model.py`

**Core Service Tests (7 arquivos):**
- `test_alerts.py`, `test_email_service.py`, `test_pdf_generator.py`
- `test_seed.py`, `test_settings.py`, `test_state_machines.py`, `test_storage_service.py`

**Infraestrutura:**
- `conftest.py`: Testcontainers PostgreSQL com rollback por teste, TestClient FastAPI, mocks Redis/WebSocket

### 7.3 Gaps Críticos

| Componente | Cobertura | Gap |
|------------|-----------|-----|
| IA Agent Framework | 0% | Sem testes para BaseAgent, AgentRegistry, output_validator |
| Offline Sync | 0% | Sem lógica implementada |
| E2E Workflows | 0% | Sem Playwright/Cypress |
| Load Testing | 0% | Sem k6/JMeter |
| Security | ~30% | Sem pentest suite explícita |
| Portal Components | 0% | Sem React Testing Library |
| Mobile | 0% | Nenhum teste |

### 7.4 CI/CD Pipeline

**Arquivo:** `.github/workflows/ci.yml`

3 jobs paralelos:
1. **Lint** — ruff check + mypy
2. **Test** — pytest com coverage (depende de lint)
3. **Migration** — alembic up/down/up (depende de lint)

**Falta:** Frontend build, portal build, mobile lint, coverage threshold enforcement

---

## 8. ARQUITETURA DO SISTEMA

### 8.1 Diagrama

```
                    +-------------------+
                    |   React/Vite      |  :5173 (painel interno)
                    +--------+----------+
                             |
+------------------+         |         +-------------------+
| Next.js Portal   +---------+---------+  Mobile Expo      |
| :3000 (cliente)  |         |         |  (campo)          |
+--------+---------+         |         +--------+----------+
         |                   |                  |
         +-------------------+------------------+
                             |
                    +--------v----------+
                    |   FastAPI :8000    |  14 routers
                    |   + Middleware     |  JWT auth
                    |   + WebSockets    |  Multi-tenant
                    +--------+----------+
                             |
              +--------------+--------------+
              |              |              |
     +--------v---+  +------v------+  +----v-------+
     | PostgreSQL  |  |   Redis     |  |  MinIO     |
     | + PostGIS   |  |   (broker + |  |  (S3)      |
     | + pgvector  |  |    cache)   |  |            |
     +-------------+  +------+------+  +------------+
                             |
                    +--------v----------+
                    |  Celery Workers    |
                    |  7 task types      |
                    |  (email, PDF, IA)  |
                    +-------------------+
                             |
                    +--------v----------+
                    |  LiteLLM Gateway  |
                    |  (OpenAI, Gemini, |
                    |   Anthropic)      |
                    +-------------------+
```

### 8.2 Decisões Arquiteturais Sólidas

1. **Separação de concerns** — API core ≠ IA worker ≠ async workers
2. **Multi-tenant by default** — tenant_id em toda tabela de negócio
3. **Audit trail imutável** — AuditLog append-only com timeline
4. **Async-first workers** — Email, PDF, IA fora do HTTP path
5. **Repository pattern** — BaseRepository com tenant scoping
6. **PostGIS + pgvector** — Geoespacial + RAG ready

### 8.3 Decisões de Risco

| Risco | Estado | Mitigação |
|-------|--------|-----------|
| Settings singleton em import-time | Parcialmente corrigido | `lru_cache + override_settings()` |
| Prompts de IA hardcoded | Em progresso | Tabela PromptTemplate existe; migrar 6 agentes |
| Sem workflow de aprovação humana | Ausente | Necessário para outputs de IA e documentos |
| Sem conflict resolution no mobile | Skipped para MVP | Regra: servidor vence para metadata |
| Sem integração com APIs governamentais | Skipped para MVP | Estratégia três-pilares definida |

### 8.4 Funcionalidades Documentadas vs Implementadas

| Feature | Status | Notas |
|---------|--------|-------|
| Process State Machine (11 estados) | IMPLEMENTADO | 64 testes de contrato |
| Task State Machine (7 estados) | IMPLEMENTADO | Testado |
| Document State Machine (7 estados) | PARCIAL | Estados definidos, falta workflow humano |
| AI Job State Machine (6 estados) | IMPLEMENTADO | Retry + fallback |
| Mobile Sync States (6 estados) | NÃO IMPLEMENTADO | Skeleton existe |
| RBAC & Permissions (5 roles) | IMPLEMENTADO | JWT com role claims |
| Human-in-the-loop IA | PARCIAL | Gateway existe, falta aprovação |
| IA Cost Tracking | PARCIAL | Jobs gravam tokens, falta billing |
| Government Integrations | NÃO INICIADO | Apenas design |
| Prompt Versioning | PARCIAL | Tabela existe, não integrada |

---

## 9. MATRIZ DE RISCO CONSOLIDADA

| Severidade | Quantidade | Exemplos Principais |
|------------|------------|---------------------|
| **CRÍTICO** | 11 | Client validation no token; N+1 dashboard; Custo IA sem validação; Dependências circulares; Secrets em os.environ; CORS permissivo; Chaves expostas |
| **ALTO** | 18 | Token catch genérico; Tenant ID fallback; SQL injection extensão; Deadlock tasks; Sem CSRF; Sem rate limiting; WebSocket sem auth; Redis sem pool |
| **MÉDIO** | 24 | Soft delete inconsistente; Pool DB pequeno; Bucket state per-process; Paginação sem limite; Race condition WebSocket; Custo IA silencioso |
| **BAIXO** | 15 | Log sampling; OpenTelemetry; Password strength; Key rotation; Acessibilidade frontend |

---

## 10. SUGESTÕES DE APRIMORAMENTO

1. **Refresh tokens** — Reduzir expiry JWT para 15-30 min + implementar refresh token rotation
2. **Row Level Security (RLS)** — Adicionar RLS no PostgreSQL como segunda camada de tenant isolation
3. **OpenTelemetry** — Substituir tracing artesanal por OTLP + Grafana Tempo
4. **Grafana dashboard** — Métricas operacionais visuais em tempo real
5. **Prompt versioning** — Migrar prompts hardcoded para PromptTemplate com A/B testing
6. **Human-in-the-loop** — Gates de aprovação para outputs de IA e documentos críticos
7. **Government API broker** — Implementar integração três-pilares (API → cert A1 → fallback humano)
8. **Lazy loading** — React.lazy para tabs pesadas no frontend
9. **Cursor-based pagination** — Para datasets grandes em vez de offset/limit
10. **k6 load testing** — Validar performance com 100+ tenants concorrentes
11. **CSRF tokens** — Adicionar middleware CSRF para mutations
12. **Content Security Policy** — Headers CSP em todas as respostas
13. **Webhook retry queue** — Celery task com exponential backoff em vez de fire-and-forget
14. **Redis Sentinel/Cluster** — HA para Redis em produção
15. **Database read replicas** — Para queries pesadas (dashboard, relatórios)

---

---

# PARTE 2 — PLANO DE SPRINTS DE CORREÇÃO

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
ENVIRONMENT=production python -c "from app.core.config import settings; print(settings.ENVIRONMENT)"
curl -s http://localhost:8000/docs | grep -c "Swagger"  # 0 (quando ENVIRONMENT=production)

# Login sem defaults
grep "useState(" frontend/src/pages/Auth/Login.tsx | grep -v "useState('')" | grep -v "useState(false)" | wc -l  # 0

# Testes passam
pytest tests/ -q --tb=short  # 114+ passed
```

### Smoke Test de Saída

```bash
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
grep -n "try:" app/api/websockets.py | wc -l  # >= 1
grep -n "1008" app/api/websockets.py | wc -l   # >= 1

# Rate limiting
grep -rn "limiter\|slowapi\|RateLimitMiddleware" app/ | wc -l  # >= 1

# Mobile interceptor
grep -n "interceptors.response" mobile/src/lib/api.ts | wc -l  # >= 1

# Teste cross-tenant
pytest tests/api/test_tenant_isolation.py -v  # PASSED

# Regressão
pytest tests/ -q --tb=short  # 115+ passed
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
pytest tests/ -q --tb=short
```

### Smoke Test de Saída

```bash
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
grep -rn "ErrorBoundary" frontend/src/ | wc -l  # >= 2

# Sem alert()
grep -rn "alert(" frontend/src/ --include="*.tsx" | grep -v "//\|emit_operational_alert\|AlertCircle\|alertas" | wc -l  # 0

# Password escondida
grep -n "hide_password\|render_as_string" app/db/init_db.py | wc -l  # >= 1

# Sem any no portal
grep -rn ": any" client-portal/src/ --include="*.tsx" --include="*.ts" | wc -l  # 0

# MinIO healthcheck
grep -A3 "minio:" docker-compose.yml | grep -c "healthcheck"  # >= 1

# Testes + builds
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
ls tests/e2e/test_intake_flow.py tests/e2e/test_document_flow.py tests/api/test_websockets.py

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

---

## Estimativa Total de Esforço

| Sprint | Horas | Acumulado | Marco |
|--------|-------|-----------|-------|
| Sprint 0 | 4h | 4h | - |
| Sprint 1 | 8h | 12h | - |
| Sprint 2 | 8h | 20h | MVP Seguro |
| Sprint 3 | 8h | 28h | - |
| Sprint 4 | 8h | 36h | Produção Mínima |
| Sprint 5 | 8h | 44h | - |
| Sprint 6 | 8h | 52h | - |
| Sprint 7 | 8h | 60h | Produção Confiável |

**Total: ~60 horas de implementação direta**  
**+ ~50 horas de teste, review e ajustes = ~110 horas totais**
