# Estado Atual — Regente Ambiental

**Data do instantâneo:** 2026-05-18
**Próxima atualização:** ao fechamento da próxima sprint
**Responsável de atualização:** quem fechar a próxima sprint

> Este documento é regenerado a cada sprint. Reflete o estado real da plataforma agora, não o estado planejado. Quando algo muda no código, muda aqui.

---

## Visão de uma página

**O que está funcionando hoje em produção/dev:**

- Backend FastAPI com 28 routers REST + WebSocket
- 10 agentes de IA via LiteLLM (multi-provider, fallback, cost cap enforced)
- Painel do consultor (React + Vite) com 36 telas em 10 áreas
- Multi-tenant com isolamento por `tenant_id` validado no JWT
- AuditLog com hash chain SHA-256 encadeado
- RAG semântico via pgvector (22.573 chunks em 4 UFs)
- Sprint Waitlist em curso (PR 2 mergeado, PR 3 pendente)
- Sprint A2 fechada (redator + diagnóstico migrados para schema validado)

**O que está congelado:**

- Portal do cliente (`client-portal/`, Next.js 16) — ver [`../adr/009-mobile-clientportal-congelados.md`](../adr/009-mobile-clientportal-congelados.md)
- App de campo (`mobile/`, Expo) — idem

**O que está em transição:**

- Renomeação Amigão → Regente (camadas visíveis) — em execução
- Skills procedurais do agente Redator — aguardando reunião de 16/05 com a sócia

## Backend

### Agentes ativos (10)

| Agente | Arquivo | Status A2 | Custo médio observado |
|---|---|---|---|
| atendimento | `app/agents/atendimento.py` | dict legado | baixo (4 execuções) |
| extrator | `app/agents/extrator.py` | dict legado | 51 execuções históricas — mais usado |
| diagnostico | `app/agents/diagnostico.py` | ✅ A2 (DiagnosticoPreliminarContent) | $0.0002 smoke |
| legislacao | `app/agents/legislacao.py` | ✅ A2 (EnquadramentoRegulatorioContent) | $0.0047 acumulado (Gemini 2.0 Flash) |
| redator | `app/agents/redator.py` | ✅ A2 (PecaJuridicaContent) | $0.0030 smoke 7 templates |
| orcamento | `app/agents/orcamento.py` | dict legado | baixo |
| financeiro | `app/agents/financeiro.py` | dict legado | baixo |
| acompanhamento | `app/agents/acompanhamento.py` | dict legado | 1 execução |
| vigia | `app/agents/vigia.py` | rules-based (sem LLM) | $0 |
| marketing | `app/agents/marketing.py` | dict legado | baixo |

### Chains de orquestração (9)

Definidas em `app/agents/orchestrator.py:CHAINS`: `intake`, `diagnostico_completo`, `gerar_proposta`, `gerar_documento`, `analise_regulatoria`, `enquadramento_regulatorio`, `analise_financeira`, `monitoramento`, `marketing_content`. Chain principal: `diagnostico_completo` (extrator → legislacao → diagnostico → redator).

### Models SQLAlchemy (28 entidades)

Tabelas principais: `tenants`, `users`, `clients`, `properties`, `processes`, `tasks`, `documents`, `communications`, `proposals`, `contracts`, `ai_jobs`, `audit_logs`, `prompt_templates`, `intake_drafts`, `regulatory_diagnosis`, `regulatory_issues`, `knowledge_catalog`, `legislation_documents`, `pre_cadastros`, `intake_classification_feedback`, etc.

### Routers REST (28 + 1 WebSocket)

Ver `app/main.py:135-161`. Áreas: auth, clientes, processos, documentos, propriedades, tarefas, threads, intake, intake-feedback, checklists, workflows, dossier, decisions, regulatory, proposals, contracts, ai, agents, dashboard, legislation, legislation_alerts, knowledge, waitlist.

### Migrations Alembic

40 migrations aplicadas em produção. Convenção: `<8-hex>_sprint_<X>_<descricao>.py`.

## Corpus regulatório (RAG)

| UF | Chunks indexados | Provider de embedding |
|---|---|---|
| Federal | 720 | OpenAI `text-embedding-3-small` (migração de Gemini concluída) |
| GO | 3.855 | idem |
| MS | 4.587 | idem |
| MT | 13.411 | idem |
| **Total** | **22.573** | — |

Próximos estados na fila: SP, MG, TO (próxima semana).

## Frontend (painel consultor)

- React 18 + Vite + TypeScript + TailwindCSS + React Query + Zustand
- 36 telas em 10 áreas (Auth, Clients, Processes, Properties, Intake, Contracts, Proposals, Dashboard, AI, Settings)
- TypeScript strict, zero `any` explícito, mutations uniformizadas via async/await
- Token em Zustand persist + interceptor de 401/403 em `frontend/src/lib/api.ts`

## Testes

- 102 arquivos de teste em `tests/`
- Testcontainers PostgreSQL+PostGIS 15-3.3 (function-scoped session em transação rollback)
- pytest + pytest-cov, `fail_under=70` em coverage
- Estado verde após A2: 156/156 testes passando

## Infraestrutura

- Docker Compose com serviços: db (Postgres+PostGIS+pgvector), redis, minio, api, worker, client-portal (congelado)
- Variáveis de ambiente em `.env.example` (40+ variáveis)
- Métricas Prometheus em `/metrics`
- Health check em `/health`
- OpenAPI em `/docs`

## Sprints concluídas (últimas 6)

| Sprint | Conteúdo | Status |
|---|---|---|
| Sprint -1 (faxina) | Cost cap, filtro demand_type, cache OCR, MemPalace stub | ✅ |
| Sprint 0 (ingestão) | Corpus federal+GO+MS+MT no `knowledge_catalog` | ✅ |
| Sprint U (RAG) | pgvector instalado, busca semântica, embeddings | ✅ |
| Sprint A1 (infra) | `app/skills/`, `StageOutputContent`, RegulatoryDiagnosis, CitationEvaluator | ✅ |
| Sprint A2-redator | RedatorAgent emite `PecaJuridicaContent` (7 templates) | ✅ |
| Sprint A2-diagnostico | DiagnosticoAgent emite `DiagnosticoPreliminarContent` | ✅ |
| Sprint A2-legislacao | LegislacaoAgent emite `EnquadramentoRegulatorioContent` (18 testes A2) | ✅ |

## Sprints em curso

| Sprint | Conteúdo | Estado |
|---|---|---|
| Waitlist | Endpoint público + Resend + drip educativo | PR 2 mergeado, PR 3 pendente |

## Pendências críticas

| Item | Bloqueio | Janela |
|---|---|---|
| Skills procedurais (redator + extrator) | Aguardando PDFs-gabarito da sócia (reunião 16/05) | Curto |
| Renomeação visível Amigão→Regente | Patch sendo preparado | Curto |
| Property.geom populado | Falta parser shapefile + ingestão de KML/SHP | Médio |
| Agente auditor_imovel | Depende de geom populado | Médio |
| Crawlers DOU/DOE ativados em prod | Apenas esqueleto pronto | Médio |
| Connector e-mail inbound (acompanhamento) | Sem integração de inbound hoje | Médio |
| Hardening de produção (secrets, CORS, Swagger desabilitado) | Checklist em `ops/production-secrets-checklist.md` | Curto |
| State-leakage entre testes (29 fails na suite, passam isolados) | Pytest e2e foi desbloqueado em 2026-05-17 (commit `0e17ebd`): venv host saudável + Testcontainers usando imagem `amigao_do_meio_ambiente-db` (postgis+pgvector). **339 testes passam**. Sobram 29 que falham só em suite — slowapi rate-limit state vaza entre testes, alguns testes committam transações. Sprint dedicada de saneamento: fixture `autouse=True` que reseta `slowapi.Limiter._storage` + auditar testes que committam manualmente. Não bloqueia deploy (suite roda localmente; mostra testes verdes isolados). | Curto |

## Próximos marcos

- **16/05 (sábado):** reunião sócia + tecnologia para escrever 4-6 skills procedurais
- **Semana 19-23/05:** ingestão SP+MG+TO + cirurgia MemPalace + renomeação visível + Sprint A2-legislacao
- **Reunião institucional SEMAD-GO:** sem data confirmada, mas pacote de preparação em curso

## Métricas operacionais

(Esta seção precisa ser preenchida com query SQL real do banco de produção. Marcador para próxima atualização.)

- Clientes cadastrados: a apurar
- Processos abertos: a apurar
- Documentos extraídos: a apurar
- AI Jobs (últimos 30 dias): a apurar
- Custo total IA (últimos 30 dias): a apurar
- Tenant ativo: 1 (sócia)
