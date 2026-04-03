# Runbook Operacional

Documento vivo de operacao e homologacao. A cada passada relevante, este arquivo e `docs/progresso3.md` devem ser atualizados juntos.

Funcao deste arquivo:

- linguagem operacional e prescritiva
- foco em comando, validacao, pre-requisito, evidência e resposta operacional
- evitar narrativa historica longa; isso pertence ao `progresso3.md`

## Padrao de fechamento

Ao final de cada rodada:

1. registrar o que mudou em `docs/progresso3.md`
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

- `03/04/2026`

Validado nesta rodada (backend P0/P1):

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
- suite backend: `114 passed`, `1 failed` (test_pdf_generator pre-existente)

Validado nesta rodada (frontend Sprint F2/F3):

- `npm run build` -> sem erros, sem warnings, chunk principal 416 kB
- `npm run test` -> 21 passed, 4 suites
- `npm run lint` -> `eslint --max-warnings=0` exit 0
- `npx tsc --noEmit` -> 0 erros
- 50 erros de lint eliminados (todos os `any` tipados)
- ProcessDetail.tsx decomposto em 6 subcomponentes (565 -> 146 linhas)
- Dashboard com toggle executivo/operacional, skeletons e useQueries paralelo
- code splitting funcionando (4 chunks, sem warning de tamanho)

Suite focada mais recente:

- backend: `114 passed`
- frontend: `21 passed`

## Estado dos frontends (atualizado 03/04/2026)

### Frontend Vite (painel interno)

Build: VERDE

```bash
cd frontend && npm run build
# tsc -b && vite build -> built in 16.07s
# dist/assets/index-CbMGmBO1.js   416 kB (gzip: 115 kB)
# dist/assets/vendor-BaIpEwgI.js   49 kB (gzip:  17 kB)
# dist/assets/query-BXIXmBZW.js    46 kB (gzip:  14 kB)
# dist/assets/ui-DhMXtG7N.js       21 kB (gzip:   5 kB)
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

### Client Portal Next.js

Build: VERDE

```bash
cd client-portal && npm run build
# next build -> Compiled successfully in 11.9s
# 6 routes (3 static, 1 dynamic, 2 pages)
```

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

## Pendencias atuais

- substituir o sink local por destino externo real de webhook quando houver endpoint definitivo
- modularizar o seed atual se o repositorio realmente migrar para a estrutura `seed/main.py`
- revisar referencias antigas a credenciais seed em documentacao fora do runbook principal, se surgirem novas divergencias
- incluir `http://localhost:5173` no `BACKEND_CORS_ORIGINS` do `.env` para dev local do frontend Vite
- configurar pipeline CI com gates de build/lint/typecheck para ambos os frontends
- migrar testes backend de SQLite para PostgreSQL real (JSONB incompativel) — **resolvido parcialmente: testes IA ja rodam em PostgreSQL via Testcontainers**
- ~~corrigir import faltante `emit_operational_alert` em `app/api/v1/tasks.py`~~ — **resolvido em 03/04**
- ~~corrigir `class Config` legado para `model_config = ConfigDict(...)` em `app/api/v1/dashboard.py`~~ — **resolvido em 03/04**
- ~~corrigir `.dict()` deprecado para `.model_dump()` em `processes.py` e `properties.py`~~ — **resolvido em 03/04**
- Sprint IA-2: criar `/app/agents/base.py` e `registry.py` (framework de agentes)
- Sprint IA-2: implementar validacao estrita de output LLM via JSON Schema + Pydantic
- Sprint IA-2: refatorar chamadas LLM para logging obrigatorio via `ai_gateway.py`
- Sprint IA-2: router CRUD de PromptTemplate em `/api/v1/prompts`
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
