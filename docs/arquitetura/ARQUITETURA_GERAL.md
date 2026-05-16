# Arquitetura Geral

**Documento:** Arquitetura · referência viva
**Estado:** atualizar a cada sprint que altere desenho
**Última revisão:** 2026-05-15

---

Este documento descreve o sistema do Regente Ambiental como ele existe hoje no código. É referência técnica, não plano. Tudo aqui pode ser verificado abrindo o arquivo citado.

## Visão macro

```
Cliente Web (consultor)                Cliente Web (lead/waitlist)
        │                                       │
        │  HTTPS + JWT                          │  HTTPS público
        ▼                                       ▼
┌───────────────────────────────────────────────────────────┐
│                    FastAPI (app/main.py)                  │
│                                                           │
│   28 routers REST + 1 WebSocket router                    │
│   Middlewares: RequestContext, SecurityHeaders, CORS      │
│   Rate limit: slowapi (per-IP)                            │
│   Auth: JWT com 2 perfis (internal / client_portal)       │
└────────────┬────────────────────────┬─────────────────────┘
             │                        │
             │ SQLAlchemy 2.x         │ Celery (Redis broker)
             ▼                        ▼
┌──────────────────────┐     ┌──────────────────────────────┐
│  PostgreSQL 15       │     │  Worker Celery (app/workers) │
│  + PostGIS 3.3       │     │                              │
│  + pgvector 0.8      │     │  11 módulos de tasks:        │
│                      │     │  - ocr_tasks                 │
│  ~28 entidades       │     │  - ai_tasks                  │
│  40 migrations       │     │  - agent_tasks               │
│  22.573 chunks RAG   │     │  - intake_tasks              │
└──────────────────────┘     │  - legislation_tasks         │
             ▲               │  - knowledge_indexer         │
             │               │  - waitlist_tasks            │
             │               │  - webhook_tasks             │
             ▼               │  - pdf_generator             │
┌──────────────────────┐     │  - ai_summarizer             │
│  Redis 7             │     └──────────────┬───────────────┘
│  - Celery broker     │                    │
│  - Pubsub (events)   │                    │
│  - Rate limit cache  │                    ▼
└──────────────────────┘     ┌──────────────────────────────┐
                             │  AI Gateway (LiteLLM)        │
┌──────────────────────┐     │                              │
│  MinIO (S3)          │     │  OpenAI → Gemini → Anthropic │
│  - amigao-docs       │     │  Cost cap por job e por      │
│  - documentos        │◄────│  tenant. Métricas em AIJob.  │
│    versionados       │     └──────────────────────────────┘
└──────────────────────┘
```

## Componentes

### Backend FastAPI (`app/`)

Aplicação única, monolítica por design — não há microsserviços. A separação de responsabilidades vive em camadas dentro do mesmo processo:

| Pasta | Responsabilidade |
|---|---|
| `app/api/v1/` | Routers REST (28 routers). Cada arquivo cobre um recurso/agregado. |
| `app/api/websockets.py` | Realtime via WebSocket (eventos do tenant) |
| `app/api/middleware.py` | RequestContext (trace_id, tenant_id), SecurityHeaders |
| `app/api/deps.py` | Dependency injection (auth, db session, tenant guard) |
| `app/core/` | Config, security, logging, métricas, ai_gateway, celery_app, rate_limit, alerts |
| `app/models/` | SQLAlchemy ORM (28 entidades) |
| `app/schemas/` | DTOs Pydantic v2 (request/response da API) |
| `app/services/` | Lógica de negócio (24 serviços) |
| `app/agents/` | Agentes IA (10 agentes + base + orchestrator + memory stub) |
| `app/skills/` | Skills procedurais carregadas pelo BaseAgent |
| `app/workers/` | Tasks Celery (11 módulos) |
| `app/repositories/` | Camada de acesso a dados (parcial — alguns recursos ainda chamam ORM direto do router) |
| `app/db/` | Session factory, init_db |

### Frontend painel consultor (`frontend/`)

React 18 + Vite + TypeScript + TailwindCSS. Stack frontend foi escolhida em 2026-03 e segue sólida. Componentes principais:

- **Router:** React Router v7
- **Server state:** React Query
- **Client state:** Zustand (com persist para auth)
- **HTTP:** Axios via `frontend/src/lib/api.ts` com interceptors (401/403 → logout)
- **UI:** TailwindCSS puro (sem componentes shadcn ou similares — design system interno)
- **Form/validação:** react-hook-form + Zod
- **Animação:** framer-motion

36 telas em 10 áreas: Auth, Clients, Processes, Properties, Intake, Contracts, Proposals, Dashboard, AI, Settings.

### Banco de dados — Postgres + extensões

- **PostgreSQL 15** com imagem custom estendida (`docker/db/Dockerfile`) que adiciona:
  - **PostGIS 3.3** — geometrias (`Property.geom` como SIRGAS 2000 / SRID 4674)
  - **pgvector 0.8** — busca semântica (`knowledge_catalog.embedding` como `vector(768)`)
- Conexão única (não há cluster, não há réplica em dev)
- Acesso interno do API/worker via service name `db:5432`; host expõe porta `55432` por padrão

### Filas e workers — Redis + Celery

- **Redis 7** atende três papéis: broker do Celery, pubsub de eventos realtime (`amigao_events`), cache de rate limit (slowapi)
- **Worker Celery** rodando em pool `solo` em dev, `prefork` em prod
- **Beat scheduler** agenda ingestões periódicas (DOU/DOE diário 06:00 BRT, agências semanal segunda 03:00)
- Toda task tem `max_retries=3` + `retry_backoff=True`

### Storage — MinIO

- MinIO single-node em dev, S3-compatible
- Bucket único: `amigao-docs` (codinome técnico, ver [`../adr/004-regente-vs-amigao.md`](../adr/004-regente-vs-amigao.md))
- Upload via presigned URL — frontend pega URL temporária do backend, faz PUT direto no MinIO, depois confirma com o backend
- Versionamento por documento (cada `Document` aponta para o arquivo no MinIO via `file_path`)

### AI Gateway (`app/core/ai_gateway.py`)

Camada única de contato entre o produto e provedores de IA. LiteLLM como driver. Política multi-provider:

1. **OpenAI** (default, `gpt-4o-mini` para a maioria, `gpt-4o` para tarefas complexas)
2. **Gemini** (fallback automático, default para `LegislacaoAgent` por causa da janela de 1M-2M tokens)
3. **Anthropic Claude** (segundo fallback)

Toda chamada retorna `AIResponse` com `cost_usd`, `tokens_in`, `tokens_out`, `model_used`, `duration_ms`, `provider`. Tudo persistido no `AIJob` correspondente.

Detalhes em [`GOVERNANCA_IA.md`](./GOVERNANCA_IA.md).

## Padrões arquiteturais aplicados

### Multi-tenant por linha (`tenant_id`)

Toda tabela transacional tem `tenant_id` como FK não-nula. Toda query do backend filtra explicitamente por `tenant_id` extraído do JWT. Tentativa de manipular entidade de outro tenant retorna 403. Exceção: `pre_cadastros` (waitlist é lead anônimo pré-conta).

Detalhes em [`MULTITENANT_LGPD.md`](./MULTITENANT_LGPD.md).

### Auth com dois perfis

JWT carrega `profile ∈ {internal, client_portal}`. Endpoints internos usam `get_current_internal_user` que rejeita tokens do portal cliente com 403. Endpoints do portal usam `get_current_portal_user`.

### Auditabilidade encadeada

Toda escrita relevante (mudança de status, atribuição de tarefa, geração de peça, decisão IA) registra em `AuditLog` com `hash_sha256` encadeado a `hash_previous`. Permite verificação de integridade temporal posterior.

### Agentes IA isolados por responsabilidade

10 agentes herdam de `BaseAgent` (`app/agents/base.py`). Cada um tem `name`, `palace_room` (vestígio do MemPalace, em remoção), e um método `_run_internal` que executa a tarefa. O `BaseAgent.run()` cuida do lifecycle: criar `AIJob`, validar cost cap, executar, registrar custo/tokens, emitir evento realtime, marcar `requires_review` quando aplicável.

Agentes não chamam outros agentes diretamente — encadeamento acontece via `app/agents/orchestrator.py` (9 chains pré-definidas: `intake`, `diagnostico_completo`, `gerar_proposta`, `gerar_documento`, `analise_regulatoria`, `enquadramento_regulatorio`, `analise_financeira`, `monitoramento`, `marketing_content`).

### RAG via pgvector com busca por cosseno

Toda fonte indexável (legislação, ofícios-modelo, manuais) vira chunks no `knowledge_catalog`. Embedding por OpenAI `text-embedding-3-small` com `dimensions=768` explícito (compatibilidade com base histórica gerada por Gemini `text-embedding-004`, que é 768 nativo). Configuração em `app/services/embeddings.py:EMBEDDING_DIM=768`. Busca por similaridade cosseno via SQL puro em `app/services/knowledge_catalog.py` (não usa ORM para a query vector).

Detalhes em [`BASE_REGULATORIA.md`](./BASE_REGULATORIA.md).

### Workflow Engine e Macroetapa Engine

Dois motores complementam o domínio:

- **MacroetapaEngine** (`app/services/macroetapa_engine.py`) — gere as 7 macroetapas do processo (entrada, diagnóstico inicial, coleta, diagnóstico técnico, caminho regulatório, execução, encerramento) com gates de avanço
- **WorkflowEngine** (`app/services/workflow_engine.py`) — gere checklists e templates de trilha regulatória por `demand_type`

### Skills procedurais

Skills são arquivos Markdown em `app/skills/<agente>/<dominio>.md` com frontmatter YAML declarando `applies_to`. O `BaseAgent.call_llm` carrega automaticamente as skills aplicáveis ao contexto da chamada e injeta no system prompt.

Hoje só existem placeholders `_template`. Skills reais entram quando a sócia fornecer os PDFs-gabarito (reunião 16/05).

## Decisões inegociáveis materializadas em código

| Princípio (manifesto) | Onde vive no código |
|---|---|
| IA propõe, humano decide | `AgentResult.requires_review` default `True` em peças formais |
| Tudo é auditável | `AuditLog` com hash chain; `AIJob` com cost/tokens/model; `Client.field_sources` marca origem |
| Cadastro / Diagnóstico / Coleta separados | Modelos distintos: `Client`/`Property` (cadastro), `RegulatoryDiagnosis` (diagnóstico), `Document`/`ChecklistTemplate` (coleta) |
| Multi-tenant | Filtro em toda query + validação `tenant_id` no JWT |
| Multi-provider IA | LiteLLM com fallback ordenado |
| Schema antes de escala | `StageOutputContent` + 3 derivados; A2 migrando agentes gradualmente |
| Cost cap hard | `AI_MAX_COST_PER_JOB_USD` enforced em `ai_gateway.complete()` |

## Endpoints principais

- API: `http://localhost:8000`
- OpenAPI: `/docs`
- Health: `/health`
- Métricas Prometheus: `/metrics`
- Painel consultor: `http://localhost:5173` (dev)
- MinIO Console: `http://localhost:9001`
- Portal cliente: `http://localhost:3000` (congelado)

## O que NÃO está nesta arquitetura

Para evitar mal-entendido:

- **Não há microsserviços.** Tudo no mesmo processo FastAPI, separado por camadas.
- **Não há message broker formal (Kafka, RabbitMQ).** Celery + Redis cobre fila e pubsub.
- **Não há frontend mobile ativo** — mobile está congelado ([ADR-009](../adr/009-mobile-clientportal-congelados.md)).
- **Não há cluster Postgres em produção** — single instance com backup. Réplica entra quando volume justificar.
- **Não há service mesh, sidecar, ou orquestração Kubernetes.** Docker Compose puro.

## Próximas leituras

- [`MODELO_DE_DADOS.md`](./MODELO_DE_DADOS.md) — esquema do banco
- [`API_v1.md`](./API_v1.md) — superfície REST
- [`GOVERNANCA_IA.md`](./GOVERNANCA_IA.md) — política de IA
- [`FLUXOS_E2E.md`](./FLUXOS_E2E.md) — fluxos do usuário ponta a ponta
- [`OBSERVABILIDADE.md`](./OBSERVABILIDADE.md) — logs, métricas, alertas
