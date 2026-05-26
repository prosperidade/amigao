# Estado Atual — Regente Ambiental

**Data do instantâneo:** 2026-05-25 (atualização pós-PROMPT_5 remodelar-regulatory-issue)
**Próxima atualização:** ao fechamento da camada 2 do Princípio 1 (5 botões P4) — depende da decisão sobre reconciliação de status
**Responsável de atualização:** quem fechar a próxima sprint

> Este documento é regenerado a cada sprint. Reflete o estado real da plataforma agora, não o estado planejado. Quando algo muda no código, muda aqui.

---

## Visão de uma página

**O que está funcionando hoje em produção/dev:**

- Backend FastAPI com 27 routers REST + WebSocket
- 11 agentes de IA via LiteLLM (multi-provider, fallback, cost cap enforced) — `auditor_imovel` ativo na chain `diagnostico_completo` desde 2026-05-24
- Painel do consultor (React + Vite) com 36 telas em 10 áreas
- Multi-tenant com isolamento por `tenant_id` validado no JWT
- AuditLog com hash chain SHA-256 encadeado
- RAG semântico via pgvector (~23.000 chunks em 4 UFs; +466 chunks de 9 normas-chave GO/federal)
- Sprint Waitlist B1 mergeada (commit `148c25b`)
- Sprint A2 fechada (redator + diagnóstico + legislacao migrados para schema validado)
- **Fase 2 (skill diagnóstico) fechada em 2026-05-23:** Risco 8+1 (taxonomia oficial),
  citation_evaluator no Diagnóstico, `auditor_imovel` + `property_audit` determinístico,
  9 normas-chave indexadas. Ver `docs/auditoria/MAPA_GAPS_CONFIRMADO_2026-05-23.md`.
- **Pós-Fase 2 (Ondas A/B/C) fechada em 2026-05-24:** `auditor_imovel` ativo na chain
  `diagnostico_completo` via `NON_BLOCKING_REVIEW_AGENTS`; `POST /processes/{id}/diagnoses`
  versionado com gate A4 Pydantic↔JSONB; régua de 4 faixas para divergência (≤1%
  informativo / 1-5% atenção / 5-10% alto / >10% crítico) — **sempre emite** o finding.
- **PROMPT_4 (fechar-pipeline) mergeado em 2026-05-25** (commits `f93b4b4` + `c74ff2e`):
  - **Onda A** — `DiagnosticoAgent` consome `chain_data["auditor_imovel"]`. Cada finding
    vira `Divergencia` + `Risco` com `grau` 4 níveis preservado.
  - **Onda B** — `PATCH /api/v1/processes/{id}/diagnoses/{version}/validate` fecha a
    **camada 1 do Princípio 1** (consultor assina). AuditLog hash chain SHA-256.
- **PROMPT_5 (remodelar `RegulatoryIssue`) finalizado em 2026-05-25** (PR a abrir):
  - **Onda A** — `RegulatoryIssue` ganha taxonomia rica: `familia` (enum estável 11) +
    `codigo_alerta` (FK em `regulatory_issue_catalog`, catálogo evolutivo via INSERT) +
    campos `muda_rota_regulatoria`/`muda_escopo_preco_prazo`/`documentos_cruzados`.
    `severity` passa de 3 para 4 níveis (`informativo`/`atencao`/`alto`/`critico`) — sai
    o `_GRADE_TO_SEVERITY` que colapsava (dívida #4 fechada). `type` legado fica nullable.
    Migration `c1b2d3e4f5a7` cria, popula 45 entradas seed e migra dados antigos.
  - **Onda B** — auditor emite codigos reais (📄: AREA_MATRICULA_X_CAR, GEO_AUSENTE,
    RL_MATRICULA_DIVERGENTE_RL_CAR, etc.); 🛰️ e 🔌 ficam no catálogo mas não emitidos.
  - **Onda C** — proposta de reconciliação dos 3 status em
    `docs/arquitetura/RECONCILIACAO_STATUS_ALERTAS.md` (Opção A recomendada).
- **Pipeline ponta a ponta no nível de código:** `extrator → auditor_imovel → legislacao →
  diagnostico → POST /diagnoses (versionado + gate Pydantic) → PATCH /validate (assina +
  AuditLog)`. UI do `PATCH /validate` ainda pendente no frontend. Taxonomia rica do
  RegulatoryIssue ativa em produção pós-merge.

**O que está congelado:**

- Portal do cliente (`client-portal/`, Next.js 16) — ver [`../adr/009-mobile-clientportal-congelados.md`](../adr/009-mobile-clientportal-congelados.md)
- App de campo (`mobile/`, Expo) — idem

**O que está em transição:**

- Renomeação Amigão → Regente: rebrand interno feito (`PROJECT_NAME`, docstrings); 8 contratos
  externos (`X-Amigao-*` headers em `alerts.py` + crawlers User-Agent) pendentes — coordenação
  com consumidores antes (dívida #13).
- **Remodelagem do `RegulatoryIssue`** (família + codigo_alerta + 4 níveis) — próxima rodada
  (PROMPT_5), aguardando validação da skill `auditor_imovel/analise_divergencias_documentais`
  pela sócia.

## Backend

### Agentes ativos (11)

| Agente | Arquivo | Status A2 | Custo médio observado |
|---|---|---|---|
| atendimento | `app/agents/atendimento.py` | dict legado | baixo (4 execuções) |
| extrator | `app/agents/extrator.py` | dict legado | 51 execuções históricas — mais usado |
| diagnostico | `app/agents/diagnostico.py` | ✅ A2+A3 (DiagnosticoPreliminarContent + citation_evaluator) | $0.0002 smoke |
| legislacao | `app/agents/legislacao.py` | ✅ A2 (EnquadramentoRegulatorioContent) | $0.0047 acumulado (Gemini 2.0 Flash) |
| redator | `app/agents/redator.py` | ✅ A2 (PecaJuridicaContent) | $0.0030 smoke 7 templates |
| auditor_imovel | `app/agents/auditor_imovel.py` | ✅ A2-Fase2 (deterministic tools, sem LLM) | $0 — cruzamento via `app/services/property_audit.py` |
| orcamento | `app/agents/orcamento.py` | dict legado | baixo |
| financeiro | `app/agents/financeiro.py` | dict legado | baixo |
| acompanhamento | `app/agents/acompanhamento.py` | dict legado | 1 execução |
| vigia | `app/agents/vigia.py` | rules-based (sem LLM) | $0 |
| marketing | `app/agents/marketing.py` | dict legado | baixo |

### Chains de orquestração (9)

Definidas em `app/agents/orchestrator.py:CHAINS`: `intake`, `diagnostico_completo`, `gerar_proposta`, `gerar_documento`, `analise_regulatoria`, `enquadramento_regulatorio`, `analise_financeira`, `monitoramento`, `marketing_content`. Chain principal: `diagnostico_completo` (extrator → legislacao → diagnostico → redator).

### Models SQLAlchemy (28 entidades)

Tabelas principais: `tenants`, `users`, `clients`, `properties`, `processes`, `tasks`, `documents`, `communications`, `proposals`, `contracts`, `ai_jobs`, `audit_logs`, `prompt_templates`, `intake_drafts`, `regulatory_diagnosis`, `regulatory_issues`, `knowledge_catalog`, `legislation_documents`, `pre_cadastros`, `intake_classification_feedback`, etc.

### Routers REST (27 + 1 WebSocket)

Ver `app/main.py:135-161`. Áreas: auth, clientes, processos, documentos, propriedades, tarefas, threads, intake, intake-feedback, checklists, workflows, dossier, decisions, regulatory, proposals, contracts, ai, agents, dashboard, legislation, legislation_alerts, knowledge, waitlist.

**Endpoints regulatórios (2026-05-25):**
- `GET   /api/v1/processes/{id}/diagnoses` — lista versões (mais nova primeiro)
- `GET   /api/v1/processes/{id}/diagnoses/{version}` — versão específica
- `POST  /api/v1/processes/{id}/diagnoses` — cria versão nova (gate A4 Pydantic↔JSONB)
- `PATCH /api/v1/processes/{id}/diagnoses/{version}/validate` — **(PROMPT_4 Onda B)** consultor assina; AuditLog hash chain; 409 se já validado
- `GET   /api/v1/properties/{id}/issues?status=open|resolved|all` — issues do imóvel

### Migrations Alembic

39 migrations aplicadas em produção. Convenção: `<8-hex>_sprint_<X>_<descricao>.py`.

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

- 42+ arquivos de teste em `tests/`
- Testcontainers PostgreSQL+PostGIS (function-scoped session em transação rollback)
- pytest + pytest-cov, `fail_under=70` em coverage
- **Estado verde após PROMPT_4:** **585 passed, 0 failed** (vs 562 antes da rodada — +23 testes:
  15 do `test_diagnostico_consume_auditor.py` + 8 do `TestValidateDiagnosis` em `test_regulatory.py`).
- 4 falhas pré-existentes em main resolvidas na Onda A do PROMPT_3 (24/05) — não há mais falhas
  pré-existentes mascarando o estado.

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
| Fase 0 (auditoria skill) | Skill `situacao_ambiental_imovel_rural` posicionada + ADR-010 + mapa de gaps | ✅ commit `7877652` |
| Fase 2 Onda 1 — A4 (schema) | Risco estendido (8+1), Divergencia, NotificacaoItem, dual-emit, validate_diagnostic_content | ✅ commit `43ac9d5` |
| Fase 2 Onda 1 — K3 (RAG) | 9 normas-chave ingeridas + reindex (466 chunks novos) | ✅ commit `92f6376` |
| Fase 2 Onda 2 — A3 (citation) | citation_evaluator no DiagnosticoAgent (espelha RedatorAgent) | ✅ commit `5c4dd33` |
| Fase 2 Onda 2 — A2 (auditor) | AuditorImovelAgent + property_audit determinístico | ✅ commit `1830e70` |
| Pós-Fase 2 (Ondas A/B/C — PROMPT_3) | 4 fixes pré-existentes + `auditor_imovel` na chain + `POST /diagnoses` + régua 4 faixas | ✅ commits `357993c` + `5e64db4` (mergeado em main) |
| PROMPT_4 — fechar pipeline | Diagnóstico consome auditor + `PATCH /validate` (camada 1 do Princípio 1) | ✅ commits `f93b4b4` + `c74ff2e` (PR aberto, pendente de merge) |
| Upstash polling redução | `polling_interval=5.0`, `vigia 6h→12h`, `acompanhamento 30min→2h` (-85% de comandos Redis) | ✅ commit `a746eb0` (PR #2 mergeado, `bc98c93`) |

## Sprints em curso

| Sprint | Conteúdo | Estado |
|---|---|---|
| Waitlist | Endpoint público + Resend + drip educativo | PR 2 mergeado, PR 3 pendente |
| Governança documental | Mover/arquivar docs conforme `GOVERNANCA_DOCUMENTAL.md`; capturar duráveis | Em curso (esta rodada) |

## Pendências críticas

| Item | Bloqueio | Janela |
|---|---|---|
| Remodelagem `RegulatoryIssue` (dívida #3) | PROMPT_5 — aguarda sócia validar skill `auditor_imovel/analise_divergencias_documentais` | Próxima rodada |
| Camada 2 do Princípio 1 (5 botões P4) | Depende da remodelagem do `RegulatoryIssue` + reconciliação de status (dívida #5) | Pós-PROMPT_5 |
| UI consultor-assina (frontend do `PATCH /validate`) | Endpoint pronto desde PROMPT_4; frontend precisa consumir e renderizar | Curto |
| Property.geom populado | Falta parser shapefile + ingestão de KML/SHP — destrava alertas geoespaciais (dívidas #14/#15) | Médio |
| Crawlers DOU/DOE ativados em prod | Apenas esqueleto pronto | Médio |
| Connector e-mail inbound (acompanhamento) | Sem integração de inbound hoje | Médio |
| R1 polish dos 8 contratos externos (dívida #13) | Headers `X-Amigao-*` em `alerts.py` + crawlers User-Agent — quebra webhook + allowlists SEMAs; coordenar antes | Médio |
| Hardening de produção (secrets, CORS, Swagger desabilitado) | Checklist em `ops/production-secrets-checklist.md` | Curto |
| State-leakage entre testes em suite (29 fails que passam isolados) | Pytest e2e desbloqueado em 17/05 (`0e17ebd`). Sprint dedicada: fixture `autouse=True` resetando `slowapi.Limiter._storage` + auditar testes que committam manualmente. Não bloqueia deploy. | Curto |

## Próximos marcos

- **PROMPT_5 — remodelar `RegulatoryIssue`**: `familia` (enum estável) + `codigo_alerta`
  (catálogo evolutivo) + 4 níveis em severity. Pré-requisito: skill da sócia validada.
- **Camada 2 do Princípio 1** (5 botões P4) — após reconciliação de status (PROMPT_5 Onda C
  só **propõe**).
- **UI do consultor-assina** — frontend consome `PATCH /validate`.
- **Property.geom + parser shapefile** (D1) — destrava overlay PostGIS para
  `auditor_imovel` (sobreposição com APP/UC/terceiros).

## Métricas operacionais

(Esta seção precisa ser preenchida com query SQL real do banco de produção. Marcador para próxima atualização.)

- Clientes cadastrados: a apurar
- Processos abertos: a apurar
- Documentos extraídos: a apurar
- AI Jobs (últimos 30 dias): a apurar
- Custo total IA (últimos 30 dias): a apurar
- Tenant ativo: 1 (sócia)
