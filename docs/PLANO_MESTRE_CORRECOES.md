# Plano Mestre de Correcoes e Melhorias -- Amigao do Meio Ambiente

**Data:** 2026-04-03
**Base:** auditoria1.md + auditoria2.md + analise de codigo por 5 agentes especializados

---

## INDICE

1. [Visao Geral e Estado Atual](#1-visao-geral-e-estado-atual)
2. [Bugs Criticos Encontrados](#2-bugs-criticos-encontrados)
3. [Plano Backend](#3-plano-backend)
4. [Plano Frontend](#4-plano-frontend)
5. [Plano Arquitetural](#5-plano-arquitetural)
6. [Plano de Agentes de IA](#6-plano-de-agentes-de-ia)
7. [Roadmap Unificado de Sprints (12 semanas)](#7-roadmap-unificado-de-sprints)

---

## 1. Visao Geral e Estado Atual

| Modulo | Maturidade | Estado |
|--------|-----------|--------|
| Backend API (FastAPI) | 75% | Funcional, 14 routers, auth JWT, multi-tenant |
| Banco/Migrations | 45% | 12 migrations, mas cadeia nao validada E2E |
| Worker (Celery) | 70% | 7 tasks, retries, sinais com metricas |
| Observabilidade | 35% | Logs JSON + metricas artesanais, sem OTel real |
| Testes Backend | 35% | 13 arquivos, mas falham por JSONB/SQLite |
| Frontend Vite (painel) | 40% | 25 componentes, build com problemas TS |
| Client Portal (Next.js) | 65% | Login, processos, timeline, upload. Build falha offline |
| Mobile (Expo) | 50% | 10 telas, offline-first, mas hardcodes e templates |

### Gargalos Criticos de Integracao

1. **Build quebrado do Frontend Vite** -- impede deploy do painel interno
2. **Testes dependem de SQLite** -- JSONB e Geometry quebram testes
3. **CORS nao inclui porta Vite (5173)** -- frontend dev retorna 403
4. **Estados divergentes** entre backend, frontends e documentacao
5. **Segredos comitados no .env** (OpenAI key, SMTP password)

---

## 2. Bugs Criticos Encontrados

### CRITICOS (crash em runtime)

| Bug | Arquivo | Linha | Impacto |
|-----|---------|-------|---------|
| `emit_operational_alert` nao importado | `app/api/v1/tasks.py` | 49 | NameError quando tarefa vence |
| JSONB em SQLite quebra testes | `app/models/ai_job.py` | 58-59 | Zero cobertura de regressao |
| Segredos no `.env` (OpenAI key, SMTP) | `.env` | 25, 34, 52 | Credenciais expostas |

### ALTOS (warnings/deprecacao)

| Bug | Arquivo | Linha | Impacto |
|-----|---------|-------|---------|
| `class Config` legado Pydantic v1 | `app/api/v1/dashboard.py` | 35, 47 | Warnings, quebra futura |
| `.dict()` deprecado | `app/api/v1/processes.py` | 47, 100 | Warnings Pydantic v2 |
| `.dict()` deprecado | `app/api/v1/properties.py` | 19, 67 | Warnings Pydantic v2 |
| `db: DbDep` nao usado em endpoints IA | `app/api/v1/ai.py` | 82-191 | Sessoes desperdicadas |
| Interceptor 403 ausente no frontend | `frontend/src/lib/api.ts` | 34-43 | Usuario preso com token invalido |
| Google Fonts sem fallback local | `client-portal/src/app/layout.tsx` | 2, 5-8 | Build falha offline |
| Typo "Caregando" | `frontend/src/pages/Clients/index.tsx` | 152 | UX |

### MEDIOS

| Bug | Arquivo | Impacto |
|-----|---------|---------|
| `redis` e `bcrypt` faltam no requirements.txt | `requirements.txt` | Falha em deploy limpo |
| Auth portal por match de email | `app/api/v1/auth.py` | Acesso indevido se emails duplicados |
| ai_summarizer nao usa ai_gateway | `app/workers/ai_summarizer.py` | Inconsistencia de chamadas LLM |
| Estados legados no client-portal | `client-portal/src/lib/process-status.ts` | Mapeamento de status diverge |
| Import axios direto (bypass auth) | `client-portal/src/.../[id]/page.tsx` | Upload sem interceptor |

---

## 3. Plano Backend

### P0 -- Esta Semana

1. **Criar `app/models/types.py`** com `PortableJSON` (JSONB em Postgres, JSON em SQLite)
2. **Atualizar `app/models/ai_job.py`** para usar PortableJSON
3. **Adicionar import** `emit_operational_alert` em `app/api/v1/tasks.py`
4. **Fix `class Config`** -> `model_config = ConfigDict(...)` em `app/api/v1/dashboard.py`
5. **Fix `.dict()`** -> `.model_dump()` em `processes.py` e `properties.py`
6. **Adicionar `redis` e `bcrypt`** ao `requirements.txt`
7. **Remover `.env` do git tracking** (`git rm --cached .env`)
8. **Remover `db: DbDep` nao usado** dos endpoints IA sincronos

### P1 -- Semanas 2-4

1. Unificar maquina de estados de tarefas (testes de contrato)
2. Testes de state machine para Task e Process
3. Migration check no CI (`alembic check` + upgrade/downgrade)
4. Refatorar `_persist_job` para aceitar sessao externa
5. Smoke tests para endpoints IA e dashboard
6. Cobertura minima por dominio (70% models, 60% API)

### P2 -- Meses 1-3

1. Observabilidade real (OpenTelemetry, Prometheus oficial)
2. Testes E2E com Postgres real
3. Hardening de auth (tabela `client_portal_access`, rate limiting, refresh token)
4. Cache Redis para dashboard (TTL 30s)
5. Paginacao cursor-based
6. Dead letter queue no Celery

---

## 4. Plano Frontend

### P0 -- Esta Semana

| # | Tarefa | Arquivo | Estimativa |
|---|--------|---------|------------|
| 1 | Fix interceptor 403 | `frontend/src/lib/api.ts` | 1h |
| 2 | Remover import axios nao usado | `frontend/src/components/DocumentUpload.tsx` | 5min |
| 3 | Remover `useQueryClient()` orfao | `frontend/src/pages/Processes/ProcessDetail.tsx` L106 | 5min |
| 4 | Corrigir typo "Caregando" | `frontend/src/pages/Clients/index.tsx` L152 | 5min |
| 5 | Tipar `icon: any` e `query: any` | `ProcessCommercial.tsx`, `AIPanel.tsx` | 30min |
| 6 | Fix Google Fonts -> local font | `client-portal/src/app/layout.tsx` | 2h |
| 7 | Fix axios direto no client-portal | `client-portal/.../[id]/page.tsx` | 30min |

### Sprint F1 (Semanas 1-2): Build Verde + Quality Gates

- Todas as correcoes P0 acima
- Criar `.github/workflows/ci.yml`
- Adicionar script `typecheck` no client-portal
- **Total: ~7h**

### Sprint F2 (Semanas 3-4): Testes e Limpeza

- Configurar vitest no frontend
- Testes para `store/auth.ts` e `lib/auth.ts`
- Smoke test Login
- ESLint strict rules
- Extrair componentes do ProcessesPage (index.tsx 457 linhas -> < 200)
- Code splitting com React.lazy em App.tsx
- **Total: ~17h**

### Sprint F3 (Semanas 5-6): Dashboard Enhancements

- Filtros (periodo, tipo, responsavel) com React Query
- Dashboard Executivo vs Operacional (tab selector)
- Backend: query params no `/dashboard/summary`
- Endpoint SLA metrics
- **Total: ~25h**

### Sprint F4 (Semanas 7-8): UX e Performance

- Mobile sidebar (hamburger menu)
- Toast notifications (substituir alert)
- Eliminar waterfall em ProcessDetail (useQueries paralelo)
- Skeleton loading padronizado
- Setup Playwright E2E (2 cenarios)
- **Total: ~20h**

### Sprint F5 (Semanas 9-10): Client Portal Polish

- Guard SSR no api.ts
- Breadcrumbs
- E2E: Login + Intake wizard
- Audit de bundle size
- **Total: ~20h**

---

## 5. Plano Arquitetural

### Problemas Estruturais a Resolver

1. **Settings singleton import-time** -- `settings = Settings()` exige SECRET_KEY sempre
   - Solucao: `get_settings()` com `lru_cache` + `override_settings()` para testes
   - 19 arquivos afetados

2. **Camada repositories vazia** -- queries diretas nos routers
   - Criar 10 repositories: Process, Client, Document, Task, AIJob, Checklist, Workflow, Proposal, Contract, Audit

3. **Divergencia de estados** (documento vs codigo)
   - DocumentStatus: 7 estados do doc de negocio NAO implementados no model
   - AIJobStatus: faltam `timeout` e `cancelled`

4. **Testes com SQLite** -- incompativel com JSONB/Geometry
   - Migrar para testcontainers com PostgreSQL real

5. **Frontends sem padrao compartilhado** de API client, tipos, error handling

### Definition of Done Transversal

Todo PR deve passar:
- Backend: pytest verde + ruff check + cobertura 60%
- Frontend Vite: tsc --noEmit + eslint + build verde
- Client Portal: tsc --noEmit + eslint + build verde
- Integracao: docker compose build sem erros

### Observabilidade

| Componente | Estado | Acao |
|-----------|--------|------|
| Logs JSON | Implementado | Adicionar SanitizeFilter para PII |
| Metricas Prometheus | Artesanal | Migrar para `prometheus_client` oficial |
| Tracing | Caseiro (ContextVar) | Migrar para OpenTelemetry SDK |
| Alertas | 5 regras definidas | Adicionar alertas de IA, email, custo |
| Dashboards | Nenhum | Adicionar Prometheus + Grafana ao compose |

---

## 6. Plano de Agentes de IA

### Estado Atual da IA

| Componente | Arquivo | Estado |
|-----------|---------|--------|
| AI Gateway multi-provider | `app/core/ai_gateway.py` | Funcional (litellm) |
| Classificador LLM | `app/services/llm_classifier.py` | Funcional, hibrido regras+LLM |
| Extrator de documentos | `app/services/document_extractor.py` | 5 tipos de doc |
| Summarizer semanal | `app/workers/ai_summarizer.py` | NAO usa gateway (chama litellm direto) |
| Modelo AIJob | `app/models/ai_job.py` | 4 job types |

### Lacunas Criticas

- Prompts hardcoded nos servicos, sem versionamento
- Parse de JSON fragil (busca `{` e `}` manualmente)
- Zero testes para qualidade de output IA
- Sem metricas de precision/recall
- Sem A/B testing de prompts
- Sem guardrails de output

### 6 Agentes a Implementar

| Agente | Modelo | Objetivo |
|--------|--------|----------|
| **Analise Documental** | gpt-4o (complexo) / gpt-4o-mini (simples) | Extrair dados de documentos ambientais com validacao cruzada |
| **Classificacao de Processos** | gpt-4o-mini | Auto-classificar tipo, prioridade, risk_score (0-100) |
| **Predicao de Prazos** | Hibrido (regras + ML + LLM) | Estimar deadlines com intervalo de confianca |
| **Verificacao de Conformidade** | gpt-4o | Validar documentos contra requisitos regulatorios |
| **Comunicacao com Cliente** | gpt-4o-mini | Gerar comunicacoes adaptadas por canal (email/whatsapp) |
| **Geracao de Relatorios** | gpt-4o | Pareceres tecnicos, diagnosticos, resumos executivos |

### Arquitetura: Agent Framework

```
app/agents/
  base.py                    # BaseAgent, AgentResult, AgentContext
  registry.py                # Registro de agentes por nome
  prompt_manager.py          # Carrega/versiona prompts (tabela PromptTemplate)
  output_validator.py        # Validacao JSON Schema + domain rules
  schemas/                   # JSON Schema por agente
  document_analyst.py
  process_classifier.py
  deadline_predictor.py
  compliance_checker.py
  client_communicator.py
  report_generator.py
```

### Prompt Engineering

- **Versionamento:** tabela `PromptTemplate` (agent_name, version semver, system_prompt, user_template, few_shot_examples, output_schema, is_active)
- **Validacao em 5 camadas:** JSON parse -> Schema validation -> Domain validation -> Cross-validation -> Safety check
- **Retry:** max 2 retries com prompt corretivo se output invalido
- **A/B Testing:** modelo `PromptExperiment` com traffic split e comparacao de metricas

### Data Science / Avaliacao

| Agente | Metricas | Meta Sprint 1 | Meta 6 meses |
|--------|----------|---------------|-------------|
| Classificacao | Accuracy, F1 macro | 85% | 93% |
| Extracao | Precision/Recall por campo | 75% EM | 88% EM |
| Predicao Prazos | MAE (dias) | < 15d | < 7d |
| Conformidade | Precision/Recall violacoes | 70% recall | 85% recall |
| Comunicacao | Avaliacao humana | 4.0/5.0 | 4.5/5.0 |
| Relatorios | Avaliacao humana | 3.5/5.0 | 4.3/5.0 |

### Sprints de IA

- **Sprint IA-1 (Sem 1-2):** Framework base (BaseAgent, PromptTemplate, output_validator, migrar prompts hardcoded)
- **Sprint IA-2 (Sem 3-4):** Agentes Classificacao v2 e Extracao v2 + golden datasets + evaluators
- **Sprint IA-3 (Sem 5-6):** Agente Conformidade + cache semantico Redis + dashboard custos IA
- **Sprint IA-4 (Sem 7-8):** Agentes Comunicacao e Predicao de Prazos (fase 1: regras)
- **Sprint IA-5 (Sem 9-10):** Agente Relatorios + framework A/B testing
- **Sprint IA-6 (Sem 11-12):** Predicao ML (fase 2), CI para testes IA, rate limiting por tenant

---

## 7. Roadmap Unificado de Sprints (12 Semanas)

### Sprint 1-2: ESTABILIZACAO (Build Verde, Testes Verdes)

**Objetivo:** Tudo compila, tudo testa, Docker sobe sem erros.

| Tarefa | Area | Prioridade |
|--------|------|-----------|
| Completar requirements.txt | Backend | P0 |
| Fix import `emit_operational_alert` em tasks.py | Backend | P0 |
| Fix `class Config` -> `model_config` no dashboard | Backend | P0 |
| Fix `.dict()` -> `.model_dump()` | Backend | P0 |
| Remover `.env` do git tracking + rotacionar chaves | Infra | P0 |
| Criar `PortableJSON` type + fix JSONB/SQLite | Backend | P0 |
| Remover `db: DbDep` nao usado em endpoints IA | Backend | P0 |
| Fix interceptor 403 no frontend | Frontend | P0 |
| Fix Google Fonts -> local font no client-portal | Frontend | P0 |
| Corrigir erros TS (imports, tipos, typo) | Frontend | P0 |
| Migrar testes para PostgreSQL (testcontainers) | Backend | P0 |
| Adicionar CORS para porta 5173 | Backend | P0 |
| Validar cadeia de migrations Alembic | Backend | P0 |

### Sprint 3-4: QUALITY GATES E CI

| Tarefa | Area |
|--------|------|
| Criar `.github/workflows/ci.yml` (lint, typecheck, test, build) | Infra |
| Adicionar ruff + mypy para backend | Backend |
| ESLint strict no frontend | Frontend |
| Migration check no CI | Backend |
| Gerar tipos TypeScript via OpenAPI | Frontend |
| Testes de contrato para endpoints criticos | Backend |
| Testes unitarios Zustand stores | Frontend |
| Branch protection rules no GitHub | Infra |

### Sprint 5-6: FUNCIONALIDADES PENDENTES

| Tarefa | Area |
|--------|------|
| Implementar camada de repositories | Backend |
| Filtros no Dashboard (periodo, responsavel, tipo) | Backend + Frontend |
| Dashboard Executivo vs Operacional | Frontend |
| Endpoint SLA metrics | Backend |
| Framework base de agentes IA (BaseAgent, PromptTemplate) | Backend |
| Migrar prompts hardcoded para tabela versionada | Backend |

### Sprint 7-8: OBSERVABILIDADE E PRODUCAO

| Tarefa | Area |
|--------|------|
| Prometheus + Grafana no docker-compose | Infra |
| OpenTelemetry SDK (substituir tracing caseiro) | Backend |
| Healthcheck endpoints para Worker e Portal | Backend |
| `docker-compose.production.yml` | Infra |
| Rate limiting na API | Backend |
| Agentes IA: Classificacao v2, Extracao v2, Conformidade | Backend |
| Cache semantico Redis para IA | Backend |
| `docs/OPERACAO_REAL.md` | Infra |

### Sprint 9-10: UX, PERFORMANCE E IA

| Tarefa | Area |
|--------|------|
| Mobile sidebar, toast notifications | Frontend |
| Eliminar waterfalls em ProcessDetail | Frontend |
| Code splitting com React.lazy | Frontend |
| Cache Redis para dashboard | Backend |
| Paginacao cursor-based | Backend |
| Agentes IA: Comunicacao, Predicao de Prazos, Relatorios | Backend |
| Framework A/B testing de prompts | Backend |
| Setup Playwright E2E (5 jornadas) | Frontend |

### Sprint 11-12: GOVERNANCA IA E E2E

| Tarefa | Area |
|--------|------|
| Golden datasets + evaluators para todos os agentes | Backend |
| CI para testes de regressao de IA | Backend |
| Guardrails de saida (JSON Schema validation) | Backend |
| Rate limiting de IA por tenant | Backend |
| Refresh token flow | Backend |
| Tabela client_portal_access (substituir match email) | Backend |
| Suite E2E Playwright (5 jornadas criticas) | Frontend |
| Documentacao final (arquitetura real, ADRs) | Todos |
| Retrospectiva e backlog do proximo ciclo | Todos |

---

## Investimento por Equipe

| Sprint | Backend | Frontend | Infra | Mobile |
|--------|---------|----------|-------|--------|
| 1-2 | 60% | 30% | 10% | - |
| 3-4 | 40% | 40% | 20% | - |
| 5-6 | 50% | 30% | 10% | 10% |
| 7-8 | 40% | 10% | 40% | 10% |
| 9-10 | 40% | 30% | 10% | 20% |
| 11-12 | 40% | 30% | 20% | 10% |

---

## Arquivos Criticos para Implementacao

### Backend
- `app/api/v1/tasks.py` -- import faltante (crash em runtime)
- `app/models/ai_job.py` -- JSONB incompativel com testes
- `app/api/v1/dashboard.py` -- Pydantic v1 legado
- `app/api/v1/ai.py` -- dependencias nao usadas
- `app/core/config.py` -- singleton em import-time
- `tests/conftest.py` -- migrar para PostgreSQL

### Frontend
- `frontend/src/lib/api.ts` -- interceptor 403 ausente
- `frontend/src/App.tsx` -- code splitting
- `frontend/src/pages/Processes/ProcessDetail.tsx` -- waterfall de queries
- `client-portal/src/app/layout.tsx` -- Google Fonts
- `client-portal/src/lib/process-status.ts` -- estados legados

### IA
- `app/core/ai_gateway.py` -- base para todos os agentes
- `app/services/llm_classifier.py` -- refatorar para Agent v2
- `app/services/document_extractor.py` -- refatorar para Agent v2
- `app/workers/ai_summarizer.py` -- nao usa gateway (inconsistencia)
