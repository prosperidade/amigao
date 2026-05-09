# Progresso IA — Amigao do Meio Ambiente

Registro cronologico de tudo que envolve IA no sistema: agentes, prompts, RAG, gateway, custos, avaliacao.

---

## Sprint IA-1 — Infraestrutura Base (03/04/2026)

### O que foi feito

- **ai_gateway.py** — Gateway multi-provider via litellm com fallback automatico (OpenAI → Gemini → Claude), custo por chamada, timeout
- **AIJob model** — Rastreia cada chamada LLM: tokens, custo, status, input/output, entidade vinculada
- **PromptTemplate model** — Templates versionados no banco com override por tenant, input/output schema, categorias (classify, extract, summarize, proposal)
- **prompt_service.py** — Cache in-process com TTL 60s, prioridade tenant-specific > global, auto-incremento de versao
- **ai_job_persistence.py** — Helper centralizado para criacao de AIJob
- **llm_classifier.py** — Classificacao 2-etapas: regras estaticas (zero custo) + LLM para baixa/media confianca
- **document_extractor.py** — Extracao de campos estruturados (matricula, CAR, CCIR, auto de infracao, licenca)
- **ai_summarizer.py** — Resumo semanal de processo (usa litellm direto — bug a ser corrigido)
- **API /ai/** — 7 endpoints: classify, extract, classify-async, extract-async, jobs list/get, status
- **Celery tasks** — run_llm_classification, run_document_extraction (async com retries)

### Decisoes de arquitetura

- litellm como camada de abstracao (sem LangChain no core)
- Fallback multi-provider: OpenAI → Gemini → Claude
- Limite de custo por tenant: $5 USD/hora (hardcoded, migrar para config)
- 2-stage classification: regras sempre rodam primeiro (economia de custo)
- Prompts versionados no banco com fallback hardcoded em cada servico

### Metricas de aceite

- 30 testes passando para camada IA
- Zero consumo de API key em testes (mocks de ai_gateway.complete)
- Startup da API nao impactado por PromptTemplate import

---

## Sprint IA-2 — Sistema de Agentes e Orquestrador (08/04/2026)

### Motivacao

A infraestrutura IA da Sprint IA-1 era isolada — cada chamada LLM operava independentemente. Nao havia:
- Framework padronizado para agentes
- Orquestracao ou encadeamento de agentes
- Monitoramento continuo (prazos, email de orgaos)
- Agentes para diagnostico de propriedade, legislacao, financeiro, marketing
- Validacao estruturada de output LLM
- Eventos de agente para rastreabilidade

### O que foi criado

#### Framework (`app/agents/`)

| Arquivo | Descricao |
|---------|-----------|
| `base.py` | BaseAgent (ABC), AgentContext, AgentResult, AgentRegistry |
| `validators.py` | OutputValidationPipeline: JSON parse → Schema → Dominio → Safety |
| `events.py` | emit_agent_event via Redis pub/sub + AuditLog |
| `orchestrator.py` | OrchestratorAgent com 8 chains deterministicas |
| `__init__.py` | Re-exports + auto-registro dos agentes |

**BaseAgent.run()** e um template method que gerencia o lifecycle completo:
1. `check_tenant_cost_limit` — verifica limite de custo
2. `validate_preconditions` — checa dados obrigatorios
3. `_create_running_job` — cria AIJob em status running
4. `execute()` — logica do agente (subclass implementa)
5. `validate_output` — validacao de output
6. `_complete_job` — persiste resultado e metricas LLM no AIJob
7. `emit_agent_event` — emite evento via Redis + AuditLog

#### 10 Agentes

| # | Agente | Funcao | LLM | Status |
|---|--------|--------|-----|--------|
| 1 | **atendimento** | Classificacao de demanda / lead | Sim | Wraps llm_classifier existente |
| 2 | **extrator** | Extracao de campos de documentos | Sim | Wraps document_extractor existente |
| 3 | **diagnostico** | Analise do imovel + remediacao | Sim | Novo — com fallback de regras |
| 4 | **legislacao** | Consulta regulatoria | Sim | Novo — RAG placeholder para fase futura |
| 5 | **redator** | PRAD, memorial, oficios, propostas | Sim | Novo — 7 templates de documento |
| 6 | **orcamento** | Proposta comercial com escopo | Sim | Enriquece estimativa de regras com LLM |
| 7 | **financeiro** | Analise financeira e custos | Opcional | Agregacao SQL + insights LLM opcionais |
| 8 | **acompanhamento** | Parsing de email de orgaos | Sim | Novo — detecta respostas de IBAMA/SEMA/ICMBio |
| 9 | **vigia** | Monitoramento de prazos | Nao | Somente queries e regras — sem LLM |
| 10 | **marketing** | Conteudo para campanhas | Sim | Posts, emails, WhatsApp, blog, banner |

#### Chains do orquestrador

| Chain | Sequencia | Uso |
|-------|-----------|-----|
| `intake` | atendimento | Qualificacao de lead |
| `diagnostico_completo` | extrator → legislacao → diagnostico | Analise completa de propriedade |
| `gerar_proposta` | diagnostico → orcamento | Proposta com diagnostico |
| `gerar_documento` | redator | Geracao de documento formal |
| `analise_regulatoria` | legislacao | Consulta juridica pontual |
| `analise_financeira` | financeiro | Custos e projecoes |
| `monitoramento` | acompanhamento → vigia | Email de orgaos + prazos |
| `marketing_content` | marketing | Conteudo de campanha |

**Regra fundamental:** O orquestrador e deterministico — roteia por regras, nao por LLM. Isso garante auditabilidade e o principio "IA nunca decide sozinha".

**Human-in-the-loop:** Se `stop_on_review=True` (default), a chain para automaticamente quando um agente retorna `requires_review=True`. O humano valida antes de continuar.

#### API e infraestrutura

| Item | Detalhe |
|------|---------|
| Endpoints | 6: run, chain, run-async, chain-async, registry, chains |
| Schemas | AgentRunRequest/Response, ChainRunRequest/Response, AgentInfo, AsyncTaskResponse |
| Celery tasks | run_agent, run_agent_chain, vigia_scheduled_check |
| Migration | b1c2d3e4f5a6: colunas agent_name + chain_trace_id em ai_jobs, novos enums |
| Router | `app/api/v1/agents.py` registrado em main.py como `/api/v1/agents` |

### Decisoes de arquitetura

- **Orquestrador deterministico**: Sem LLM para roteamento — chains sao pre-definidas e o intent vem da API. Garante auditabilidade.
- **Session caller-owned**: Agentes nunca fazem commit. O endpoint ou Celery task controla a transacao.
- **chain_data acumulativo**: Cada agente deposita seu resultado em `ctx.chain_data[agent_name]`, e o proximo agente na chain pode usa-lo.
- **Fallback de prompts**: Cada agente define `_fallback_prompts()` com prompts hardcoded. Se o banco tiver PromptTemplate ativo, usa o banco (via prompt_service com cache).
- **Degradacao graciosa**: Agentes como diagnostico, legislacao, orcamento e acompanhamento funcionam sem LLM (retornam resultado baseado em regras).
- **Todos agentes herdam BaseAgent**: Lifecycle padronizado — cost check, AIJob, execute, validate, persist, event.

### Mudancas no banco

```
ai_jobs:
  + agent_name   VARCHAR(50) NULL, INDEXED
  + chain_trace_id VARCHAR(32) NULL

AIJobType enum:
  + diagnostico_propriedade
  + consulta_regulatoria
  + gerar_documento
  + analise_financeira
  + acompanhamento_processo
  + monitoramento_vigia
  + gerar_conteudo_marketing

PromptCategory enum:
  + diagnostico, legislacao, redator, financeiro, acompanhamento, vigia, marketing
```

### Arquivos criados (18)

```
app/agents/__init__.py
app/agents/base.py
app/agents/validators.py
app/agents/events.py
app/agents/orchestrator.py
app/agents/atendimento.py
app/agents/extrator.py
app/agents/diagnostico.py
app/agents/legislacao.py
app/agents/redator.py
app/agents/orcamento.py
app/agents/financeiro.py
app/agents/acompanhamento.py
app/agents/vigia.py
app/agents/marketing.py
app/schemas/agent.py
app/api/v1/agents.py
app/workers/agent_tasks.py
alembic/versions/b1c2d3e4f5a6_add_agent_system_columns_and_enums.py
```

### Arquivos modificados (4)

```
app/models/ai_job.py         — 7 novos AIJobType + colunas agent_name, chain_trace_id
app/models/prompt_template.py — 7 novos PromptCategory
app/services/prompt_service.py — _infer_category atualizado para novas categorias
app/main.py                   — Router /agents registrado
```

### Verificacao de syntax

Todos os 20 arquivos passaram na verificacao AST em 08/04/2026.

---

## Sprint V — RAG ao vivo + auto-fill de Hub (06/05/2026)

### Motivacao

A auditoria de 2026-04-29 listou 13 gaps. Os 3 bloqueios criticos eram **#4 (IA → dados estruturados), #7 (Hubs auto-alimentados) e #8 (separacao cadastro/diagnostico)**. Sprint V destrava #4 e #7 sem migration nova de modelo (so adiciona enum value e coluna JSONB).

### O que foi feito

| ID | Item | Commit | Descricao |
|---|---|---|---|
| **I1** | RAG no agente `legislacao` | `3b6a6c5` | Agente passou a chamar `knowledge_catalog.search()` antes do prompt. Top-k=8 chunks com filtro de UF + fallback global, output expoe `chunks_referenced` (id, source_ref, similarity) pra UI. Prompt user separa "TRECHOS HIPER-RELEVANTES" (RAG, prioritario) de "BASE LEGISLATIVA AMPLA" (dump por metadados). Settings `LEGISLATION_RAG_TOP_K=8`. |
| **A4** | `DocumentSource.intake` | `1fc40cb` | Novo valor no enum + migration `b3d5c7e9f1a2` (`autocommit_block` pra rodar `ALTER TYPE ... ADD VALUE` fora de transacao). Upload do Intake seta `source=DocumentSource.intake`, distinguindo cadastro de uploads do Workspace. |
| **A1** | Hook auto-enrich Property/Client | `4206dbe` | Novo `app/services/intake_enrichment.py` — apos `commit_draft` migrar docs do rascunho pro processo, agrega extracoes do agente extrator (mesma logica de `/drafts/{id}/extraction-results`) e preenche apenas campos vazios. Property: `registry_number, car_code, ccir, nirf, total_area_ha, app_area_ha, municipality, state`. Coercao: areas aceitam "1.234,56"/numerico; UF normaliza pra 2 letras. Marca `Property.field_sources[campo]="ai_extracted"` pra UI. Falhas no enrichment nao bloqueiam o commit. |
| **Backend Client.field_sources** | Coluna + schema + endpoint | `65110a0` | `Client.field_sources` (PortableJSON) + migration `c4e6f8a0d2b3`. `ClientHubHeader.field_sources` exposto via `/clients/{id}/hub`. Enrichment grava no client tambem. |
| **F2** | Badge "extraido pela IA" no Cliente Hub | `93355c3` | Componente `FieldSourceBadge` (espelho do PropertyHub/CAM2IH-007). Aplicado em `full_name, cpf_cnpj, email, phone`. PropertyHub ja tinha o componente desde Sprint H — ativado pelo backend de A1. |

### Decisoes de arquitetura

- **Auto-fill conservador**: nunca sobrescreve campo ja preenchido, mesmo se a origem anterior for `ai_extracted`. Protege qualquer ajuste manual feito pelo consultor entre upload e commit.
- **Proveniencia explicita**: `field_sources[campo] = "raw"|"ai_extracted"|"human_validated"` permite UI distinguir origem visual e ainda permite endpoint `/properties/{id}/validate-fields` (existente) marcar como validado humano.
- **RAG com fallback amplo**: Mesmo com chunks recuperados, o dump por metadados continua entrando como contexto complementar — robustez se o RAG retorna pouco.
- **Migration enum em autocommit**: `ALTER TYPE ... ADD VALUE` requer fora de transacao em algumas versoes do PG; usamos `op.get_context().autocommit_block()`.

### Mudancas no banco

```
documentsource enum:
  + intake  (Sprint V — origem "wizard de Intake")

clients (nova coluna):
  + field_sources  PortableJSON  default {}
```

Migrations: `b3d5c7e9f1a2` (intake enum) → `c4e6f8a0d2b3` (clients.field_sources).

### Arquivos criados (3)

```
app/services/intake_enrichment.py
alembic/versions/b3d5c7e9f1a2_sprint_v_document_source_intake.py
alembic/versions/c4e6f8a0d2b3_sprint_v_client_field_sources.py
```

### Arquivos modificados (8)

```
app/agents/legislacao.py            — RAG semantico antes do prompt
app/core/config.py                   — LEGISLATION_RAG_TOP_K=8
app/models/document.py               — DocumentSource.intake
app/models/client.py                 — field_sources column
app/api/v1/intake.py                 — upload seta source=intake; commit chama enrichment
app/api/v1/clients.py                — get_client_hub_summary expoe field_sources
app/schemas/client_hub.py            — ClientHubHeader.field_sources
frontend/src/pages/Clients/ClientHub.tsx — FieldSourceBadge nos campos do header
docker-compose.yml                   — porta exposta do db: 5433 → 55432 (conflito com vereda_postgres)
```

### Pontos criticos da auditoria 2026-04-29

| # | Ponto | Antes | Depois |
|---|---|---|---|
| #1 | Docs Intake → caso criado | UPDATE migrava sem origem clara | A4 marca `source=intake`, rastreavel |
| #4 | IA → dados estruturados | Extrator existia, sem fluxo pos-commit | I1 + A1: extracao alimenta Hubs automaticamente |
| #7 | Hubs auto-alimentados | Criacao manual pelo consultor | A1 popula Property+Client; F2 mostra badge |

### Validacao em ambiente local

- `alembic upgrade head` aplicou as 2 migrations sem erro. Head atual: `c4e6f8a0d2b3`.
- `/health` retorna 200 OK.
- Stack docker-compose subiu com 6 servicos (db, redis, minio, api, worker, client-portal).
- Teste end-to-end pelo wizard ainda pendente (sera feito em 2026-05-07).

### Pendencias da Sprint V

- Teste manual end-to-end pelo Intake → criar caso → conferir badges nos Hubs.
- Opcional: testar I1 chamando `/api/v1/agents/run` com `agent_name=legislacao` e validar que `chunks_referenced` vem populado.

---



### Sprint IA-3 — Consolidacao e Testes
- [ ] Testes unitarios para cada agente com mock de ai_gateway
- [ ] Testes de integracao para chains (intake, diagnostico_completo)
- [ ] Seed de prompt templates no banco para cada agente
- [ ] Router CRUD de PromptTemplate em `/api/v1/prompts`
- [ ] Migrar ai_summarizer.py para usar ai_gateway (corrigir bypass)
- [ ] Configurar Celery Beat para VigiaAgent (lista dinamica de tenant_ids)

### Sprint IA-4 — RAG e Legislacao
- [ ] Integracao pgvector para LegislacaoAgent
- [ ] Chunking e embedding de base regulatoria federal
- [ ] Escopo global (legislacao federal) + por tenant (precedentes internos)
- [ ] Versionamento de fonte com marcacao de vigencia/revogacao

### Sprint IA-5 — Governanca e Avaliacao
- [ ] A/B testing de prompts via PromptTemplate versioning
- [ ] Cache semantico Redis para queries repetidas
- [ ] Golden datasets por agente para avaliacao de qualidade
- [ ] Dashboard de custos de IA por tenant/agente/chain
- [ ] Rate limiting por agente (alem do limite horario global)

### Sprint IA-6 — Inteligencia Avancada
- [ ] Predicao de prazo de processo com base em historico
- [ ] Classificacao automatica de email recebido (trigger de AcompanhamentoAgent)
- [ ] Integracao com MapBiomas API para enriquecimento de diagnostico
- [ ] Geracao de relatorios PDF a partir do output do RedatorAgent

---

## Sprint A1 — Arquitetura procedural (08/05/2026)

**Status:** ✅ **CONCLUÍDA** — 6/6 tarefas mergeadas (A, C, D1, D2, B, E).
**Doc completo:** [`docs/sprints/sprint_a1.md`](sprints/sprint_a1.md).
**Fase 0 report:** [`SPRINT_A1_FASE0_REPORT.md`](../SPRINT_A1_FASE0_REPORT.md) (raiz).
**Prompt:** [`SPRINT_A1_REGENTE_AMBIENTAL.md`](../SPRINT_A1_REGENTE_AMBIENTAL.md) (raiz).

### Motivacao

Sprint 1 original (Skills) ficava bloqueada em gate de PDFs-gabarito da socia desde 23/04. A Sprint A1 separa **infraestrutura procedural** de **skills de dominio** — constroi tudo que A3 (Skills) precisa e nao depende dos PDFs.

### O que foi entregue (5 commits)

| Tarefa | Commit | Descricao | Testes |
|---|---|---|---|
| **A** | `100f7da` | `app/skills/` — registry filesystem (Forma B) + integracao no `BaseAgent.call_llm` (`<!-- skills:start -->` markers). Placeholders `_template/SKILL.md` para redator + extrator. | 26 |
| **C** | `8001fc7` | `app/schemas/stage_output.py` (Pydantic v2): `StageOutputContent` base + `DiagnosticoPreliminarContent` + `PecaJuridicaContent` + `RespostaNotificacaoContent`. Tipo canonico `CitationRef(kind, numero, ano, raw, chunk_id?, jurisdicao?, artigo?)` reusado em B. | 32 |
| **D1** | `5756e9d` | `app/models/regulatory.py` — `RegulatoryDiagnosis` (versionado por processo) + `RegulatoryIssue` (vinculado a property + opcional document). Migration `a8e1d4c7f3b6` (up/down testados). **Sem tabela N–N** (Q4). | 10 |
| **D2** | `dc165c7` | `app/api/v1/regulatory.py` — 3 endpoints REST read-only: `/processes/{id}/diagnoses`, `/processes/{id}/diagnoses/{version}`, `/properties/{id}/issues?status=...`. Smoke validado live (auth, 404, 422, tenant isolation). | 15 |
| **B** | `09e6f85` | `app/services/citation_evaluator.py` — extract_citations (regex multi-formato) + validate_citations (sem novas chamadas RAG) + hook em RedatorAgent. Detecta normas inventadas no output do LLM, marca `requires_review=True` + `citation_issues` no `AIJob.result`. **Nao bloqueia.** | 35 |
| **E** | `3a8e1f8` | `app/api/v1/intake_feedback.py` + `app/models/intake_classification_feedback.py` + migration `b9d2e5a8f4c1`. Plano B da Q3: `POST /processes/{id}/classify` como ponto canonico de classificacao + log automatico de divergencia IA × consultor + `GET /admin/intake-feedback/stats` (tenant-scoped). | 10 |

### Decisoes arquiteturais aplicadas (Fase 0)

- **Q1:** `AIJob.result["citation_issues"]` (nao `output_data` — campo nao existe).
- **Q3:** Plano B confirmado — novo endpoint `POST /processes/{id}/classify` (nao havia ponto de captura natural).
- **Q4:** sem tabela N–N entre Diagnosis e Issue. Diagnostico referencia issues via `content["issue_ids"]`.
- **Q5:** naming `StageOutputContent` (nao `StageOutputBase`) — evita colisao com ORM `StageOutput`.
- **Q6:** testes nao usam Alembic; validacao manual da migration documentada na docstring.
- **Q7:** `_load_skills_for_context(self)` sem dict paralelo — alinha com `AgentContext`.
- **Q8:** tabela dedicada `intake_classification_feedback` (mais explicito que reuso de `audit_log`).
- Sequencia reordenada `A → C → D1 → D2 → B → E` (C antes de B fixa `CitationRef` antes de B reusar).

### Bugs fixados durante implementacao

- D1/D2: `relationship(..., backref=...)` causa `ArgumentError: property of that name exists on mapper` em hot-reload do uvicorn — substituido por `foreign_keys=[...]` puro.
- B: regex `(\d{2}|\d{4})` capturava so "20" para "2012" — invertido para `(\d{4}|\d{2})` (re alternation e leftmost).

### Metricas finais (6/6 tarefas)

- 6 commits feature + 1 commit doc, **+4.163 / −6 linhas**, **128 testes novos** (103 rodaveis no container, 25 exigem pytest no host por causa de Testcontainers + DB real).
- Lint `ruff check` limpo em todos os arquivos tocados.
- Smoke tests live: todos os endpoints novos validados contra a API rodando.

### Proximos passos (FORA da Sprint A1)

- **Sprint A2** — adocao gradual de `StageOutputContent` nos 5 agentes (extrator → atendimento → diagnostico → redator → legislacao). Cada um vira sub-commit; os outros continuam aceitando `dict` enquanto nao migram.
- **Sprint A3** — Skills de dominio (chega quando os PDFs-gabarito da socia chegarem). Cria os arquivos `.md` em `app/skills/redator/` e `app/skills/extrator/`. A infra ja existe (Tarefa A).
- **Sprint Y** — Auditor de inconsistencias C6 (depende de `Property.geom` populado + parser shapefile). Modelos `RegulatoryIssue` ja existem; falta o agente `auditor_imovel` + endpoint `POST /properties/{id}/audit`.
- **Sprint W4** — OCR worker (paralelo, ja priorizado).

---

## Sprint A2-redator — Adocao de PecaJuridicaContent (09/05/2026)

**Status:** ✅ **CONCLUIDA** — 4/4 tarefas mergeadas (A, B, C1, C2).
**Doc completo:** [`docs/sprints/sprint_a2_redator.md`](sprints/sprint_a2_redator.md).
**Smoke real:** [`docs/sprints/sprint_a2_redator_smoke.md`](sprints/sprint_a2_redator_smoke.md).

### Motivacao

A1 entregou `StageOutputContent` mas adocao ficou opt-in. A2-redator e a primeira adocao real, escolhida pelo redator porque (1) ja tinha `CitationRef` integrado da A1-B, (2) e o agente mais arriscado (pecas vao pra orgao regulador), (3) destrava A3 (skills de dominio) sem refator quando os PDFs da socia chegarem.

### O que foi entregue (4 commits)

| Tarefa | Commit | Descricao | Testes |
|---|---|---|---|
| **A** | `1e8566f` | RedatorAgent emite `PecaJuridicaContent` serializado. Helpers `_derive_sources` (cascata legal_data → manual), `_resolve_addressee` (cascata metadata → process), `_build_peca` (subclass enriched ou fallback). Parsers regex `_parse_prazo_dias`/`_parse_ato_regulatorio`. `CitationValidationResult.all_citations` (extensao aditiva). | 32 unit |
| **B** | `0acbb8f` | Frontend `RedatorResult` le `r.template \|\| r.document_type` (defesa em profundidade — alias computed_field na schema + fallback no front). Badges `addressee` e "Citacoes suspeitas". | typecheck |
| **C1** | `d0e0c4f` | Bateria E2E paramétrica × 7 templates com LLM stubado. Pipeline `run()` → `AgentResult` → JSON dump round-trip. | 9 E2E |
| **C2** | `12ca673` | Smoke real com gpt-4o-mini × 7 templates, custo `$0.0030` (100× abaixo do orcamento `$0.35`). 7/7 ✅. Relatorio em `docs/sprints/sprint_a2_redator_smoke.md`. | manual |

### Decisoes da Fase 0 aplicadas (todas)

- **Q1:** migrar todos os 7 templates (`proposta`/`contrato` com log INFO marcando rota concorrente).
- **Q2:** defesa em profundidade — `@computed_field document_type` no schema + frontend lendo ambos.
- **Q3:** `RespostaNotificacaoContent` com fallback gracioso pra `PecaJuridicaContent` puro quando `prazo_dias`/`ato_regulatorio` faltam (cascata metadata → parse content → fallback).
- **Q4/Q5/Q6:** C1 stubado pra CI + C2 manual com LLM real, sem flag `legacy_dict_output`, C dividida em C1+C2.

### Bugs fixados

- C2: imports tardios (`emit_agent_event`/`record_agent_execution`) → patch no modulo de origem.
- C2: `MagicMock(session)` faz `get_active_prompt()` retornar mock truthy → patch `get_active_prompt → None` força fallback hardcoded. Pattern documentado no docstring de `_enter_smoke_patches` para reuso em sprints futuras.

### Metricas

- 4 commits feature, **+1.453 / −16 linhas**, **41 testes Python** + 9 E2E + smoke real.
- Lint `ruff check` limpo.
- 134/134 verde (regressao zero — A1 inteira preservada).
- `requires_review=True` em 7/7 templates — por design (hardcoded para pecas formais).

### Proximo agente recomendado a migrar

**`DiagnosticoAgent` → `DiagnosticoPreliminarContent`** (Sprint A2-diagnostico). Razao: output do diagnostico e input para a peca do redator — formalizar a saida melhora a entrada do agente que acabamos de migrar. Risco medio (chain `diagnostico_completo` e a mais usada).
