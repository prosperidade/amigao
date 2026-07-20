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

## Sprint W — RAG estadual MS/MT + embeddings OpenAI + UI dos agentes (14/05/2026)

### Motivacao

A Sprint V destravou RAG no agente `legislacao` mas o corpus tinha so federal + GO. A socia entregou compendios tematicos de MS (8 PDFs) e MT (11 PDFs) — material da pratica regulatoria de cada estado, organizado por nucleo (Constitucional, Territorial, Florestal/CAR, Licenciamento, Hidrico, Infracoes, Credito, Biomas, Fogo, Fauna, Ativos de Carbono).

Plano original: ingerir LegislationDocument → reindexar no knowledge_catalog com Gemini embeddings. **Plano se desfez** quando o reindex estourou a cota diaria do free tier do Gemini logo no segundo doc da fila. Sprint pivotou pra OpenAI embeddings.

### Decisoes-chave

1. **OpenAI `text-embedding-3-small` (dim=768) substitui Gemini `gemini-embedding-001` como default de embedding.** Mantem schema `vector(768)` sem migration; batch nativo (ate 100 inputs/request); 34x mais rapido no smoke test (151s → 4.5s pro mesmo doc). Custo ~$0.13 pra reindexar tudo.
2. **Vetores entre provedores sao incompativeis.** Trocar exigiu apagar todos os 2.130 chunks de legislacao existentes e re-embedar tudo. Documentado no docstring do `embeddings.py` para evitar mistura acidental.
3. **LLM do agente legislacao migrado para Gemini 2.5 Flash/Pro** (era 2.0-flash/1.5-pro — descontinuados para contas com billing novo). Necessario apos socia ativar billing.
4. **max_tokens do agente legislacao subiu para 8192** (era 4096). Gemini 2.5 Flash e verboso e estava truncando o JSON antes do fechamento, quebrando o parser.

### O que foi feito

| ID | Item | Commit | Descricao |
|---|---|---|---|
| W.1 | Ingest LegislationDocument MS/MT | `e26e6be` | Novo `scripts/ingest_legislacao_estadual.py` deriva metadata do nome do arquivo (NUC + tema). 19 docs inseridos (8 MS + 11 MT), 5.3M tokens. Bind-mount das pastas legislacao ms/mt no container api via `docker-compose.override.yml`. |
| W.2 | Refator embeddings multi-provider | `c7f19fe` | `embeddings.py` suporta OpenAI (default se `OPENAI_API_KEY`) e Gemini. Saida 768 dim nos dois via `dimensions` (OpenAI) e `outputDimensionality` (Gemini). OpenAI usa batch nativo. `current_model()` exposto para `knowledge_catalog` persistir o nome do modelo por chunk. |
| W.3 | Reindex completo MS/MT | `c7f19fe` | Apagados 2130 chunks Gemini. Re-embedados todos 42 docs com OpenAI: 22.573 chunks, zero falhas, ~10 min total. Distribuicao: MS 4587 / MT 13411 / GO 3855 / Federal 720. |
| W.4 | UI: agentes da etapa viraram botoes + filtro | `9e1618a` | `WorkspaceRightPanel` — primary/secondary_agents agora sao botoes que disparam `/agents/run-async`. Novo "Outros agentes" com TODOS os 10 do registry. `AIPanel` — filtro de agente no historico com contagem por agente. |
| W.5 | UI: botao Executar em cada card de /agents | `7991b1f` | `runAgentMutation` refatorada para aceitar `agentName` como argumento. Cada card ganhou botao "Executar" proprio com loading state por agente. |
| W.6 | UI: rename label legislacao | `3527d8c` | "Enquadramento Regulatorio" → "Legislacao" em `AGENT_LABELS`. |

### Mudancas pendentes de commit (entrelacadas com Sprint B1)

`app/core/config.py` tem mudancas misturadas. Linhas da Sprint W aguardando commit junto com a B1:

- L114: `AI_FALLBACK_MODEL = "gemini/gemini-2.5-flash"` (era 1.5-flash)
- L141-143: `CLAUDE_LEGAL_MAX_TOKENS = 8192` (era 4096)
- L148-151: `GEMINI_LEGAL_MODEL = "gemini/gemini-2.5-flash"` e `GEMINI_LEGAL_LONG_MODEL = "gemini/gemini-2.5-pro"`

### Validacao em ambiente local

Teste E2E do agente `legislacao` apos billing Gemini ativado:

- Query: "licenciamento simplificado para atividade agropecuaria de pequeno porte em Mato Grosso" / state=MT
- Resultado: `success=True`, `confidence=alta`, **8 `chunks_referenced`** todos da legislacao MT
- LLM citou normas reais: LC 592/2017 (PRA+CAR+Licenciamento MT), Decreto 697/2020 (procedimento SEMA-MT), Decreto 1.268/2022 (taxas), Decreto 1807/2026 (Autorizacao Provisoria)
- Caminho regulatorio recomendado: LAC (Licenca por Adesao e Compromisso)

### Configuracao de provider de embeddings

Auto-detect: usa OpenAI se `OPENAI_API_KEY` presente; senao Gemini. Override explicito: `EMBEDDING_PROVIDER=openai|gemini`.

⚠ **Trocar provider exige re-embedar TODOS os chunks** — vetores de provedores diferentes vivem em espacos incompativeis. Procedimento:
```bash
docker compose exec db psql -U postgres -d amigao_db -c "DELETE FROM knowledge_catalog WHERE source_type='legislation';"
docker compose exec api python scripts/reindex_sync.py
```

### Arquivos criados

```
scripts/ingest_legislacao_estadual.py
```

### Arquivos modificados (commitados)

```
docker-compose.override.yml
app/services/embeddings.py
app/services/knowledge_catalog.py
frontend/src/pages/Processes/WorkspaceRightPanel.tsx
frontend/src/pages/AI/AIPanel.tsx
frontend/src/pages/AI/AgentsPage.tsx
frontend/src/types/agent.ts
```

### Pendencias

- Commit das mudancas no `config.py` (Gemini 2.5 + max_tokens) — aguardando fechar Sprint B1
- Testar query com `state=MS` para validar que chunks MS tambem voltam
- Sprint W original (StageGap + Schemas de Saida + aba Checklist) ainda pendente

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

---

## Eixo 2 — Workflow por tipo de demanda (29/05/2026)

### O que foi feito

- `knowledge_catalog.search()` ganhou filtro estruturado `demand_type` para chunks de legislação, cruzando `knowledge_catalog.source_ref = legislation_documents:{id}` com `LegislationDocument.demand_types`.
- `LegislacaoAgent` passa esse filtro quando há `demand_type`, mantendo o tipo também na query textual como reforço semântico.
- `WorkflowEngine.apply_workflow_template()` agora levanta `TemplateNotFoundError` quando não há `WorkflowTemplate`; a API `/processes/{id}/apply-workflow` traduz para 422 claro.
- `DemandType` ganhou 5 valores: `sobreposicao`, `supressao`, `due_diligence`, `arrendamento`, `condicionantes_antigas`.
- `tools/check_template_coverage.py` lista cobertura por tipo e escreve `docs/arquivo/auditorias/2026-05-28_cobertura_templates.md`.

### Validação

- `py_compile` verde nos arquivos alterados.
- Testes unitários sem banco: `tests/services/test_workflow_engine.py` e `tests/models/test_regulatory.py::test_process_accepts_new_demand_types` verdes.
- Testes com PostgreSQL/Testcontainers ficaram bloqueados nesta máquina por acesso negado ao Docker named pipe.

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

---

## Sprint A2-diagnostico — Adocao de DiagnosticoPreliminarContent (09/05/2026)

**Status:** ✅ **CONCLUIDA** — 4/4 tarefas mergeadas (A, B, C1, C2).
**Doc completo:** [`docs/sprints/sprint_a2_diagnostico.md`](sprints/sprint_a2_diagnostico.md).
**Smoke real:** [`docs/sprints/sprint_a2_diagnostico_smoke.md`](sprints/sprint_a2_diagnostico_smoke.md).

### Motivacao

Continuacao natural da A2-redator. Output do `DiagnosticoAgent` alimenta o redator na chain `diagnostico_completo` — formalizar a saida melhora a entrada do agente recem-migrado. Aproveita schema `DiagnosticoPreliminarContent` ja entregue na A1 (sem custo extra de criacao).

### O que foi entregue (4 commits)

| Tarefa | Commit | Descricao | Testes |
|---|---|---|---|
| **A** | `8bd6885` | Migracao A.1 (path IA) + A.2 (rules-based fallback) num so commit. Helpers `_derive_sources` (cascata docs → legislation → manual fallback) e `_build_payload` (mapeamento + dual-emit). Excecao tipada `DiagnosticoOutputValidationError`. | 15 unit |
| **B** | `f4854a7` | Frontend `DiagnósticoResult` aditivo: le `r.content \|\| r.situacao_geral`, `r.hipoteses \|\| r.passivos_identificados`, etc. Novas secoes "Lacunas Documentais" + "Prioridades". | typecheck |
| **C1** | `ba5e4a4` | Bateria E2E paramétrica × 4 cenarios (AI on simples/medio/completo + AI off rules-based) + 3 testes especificos. | 7 E2E |
| **C2** | `ab0ef0c` | Smoke real com gpt-4o-mini × 2 cenarios (AI on rich context + AI off). Custo `$0.0002`. 2/2 ✅. Confirma dual-emit em runtime real. | manual |

### Decisoes da Fase 0 aplicadas (todas)

- **Q1: γ dual-emit** — schema novo + 6 chaves antigas coexistem. Frontend nao quebra.
- **Q2: lacunas = []** em V1 + log INFO. Evolucao em A3+ quando skills do redator consumirem lacunas.
- **Q3:** prioridade_acoes/observacoes em `metadata` + dual-emit.
- **Q4:** `_rules_based_diagnosis` migra junto. Sem split AI-on/AI-off.
- **Q5:** smoke com mock pesado de `_load_process_data`. Preserva isolamento de DB.
- **Q6:** gpt-4o-mini para comparabilidade cross-sprint.

### Bugs/armadilhas

- `recall_memory` sofre o mesmo MagicMock truthy bug do `get_active_prompt` (descoberto em A2-redator-C2). Patch em `_enter_smoke_patches`.
- `_load_process_data` faz query SQL real — mock pesado obrigatorio.
- Severidade fora do enum normalizada para `"medio"` + log warning.
- `content` vazio recebe placeholder + dual-emit preserva o vazio original.

### Metricas

- 4 commits feature, **+1.406 / −32 linhas**, **22 testes Python** + 7 E2E + smoke real.
- Lint `ruff check` limpo.
- 156/156 verde (regressao zero — A1 + A2-redator + A2-diagnostico).
- `requires_review=True` em 2/2 cenarios — por design (hardcoded).
- Dual-emit confirmado em runtime real (2/2 cenarios preservam 6 chaves antigas).

### Plano de deprecacao das chaves antigas (futuro)

Estrategia γ deixa chaves antigas no payload pra backward compat. Deprecacao em 2 sprints:
1. **Frontend follow-up:** confirmar 0 uso em logs/observabilidade. Ja le schema novo com fallback (Tarefa B).
2. **Sprint cleanup:** remover dual-emit do `_build_payload`. Frontend mantem fallback pra AIJobs historicos.

Registrado como divida de simplificacao em `docs/sprints/sprint_a2_diagnostico.md`.

### Proximo agente recomendado a migrar

**`LegislacaoAgent` → criar `LegislationContextContent`** (Sprint A2-legislacao). Custo extra de schema novo (vs A2-diagnostico que reaproveitou existente). Alto valor — legislacao alimenta tanto redator quanto diagnostico.

---

## Fase 0 — Auditoria do estado real (23/05/2026)

**Status:** ✅ **CONCLUIDA** — commit `7877652`. Doc completo: `docs/_archive/progressos/progresso7.md`.

Auditoria documental confrontada com codigo. Skill `diagnostico/situacao_ambiental_imovel_rural` (v1.0, depois v1.1 validada pela socia em 22/05) posicionada em `app/skills/`. ADR-010 (loop de aprendizado com consultores) proposto. Mapa de gaps em `docs/auditoria/MAPA_GAPS_CONFIRMADO_2026-05-23.md`.

**Surpresas de escopo (gaps que ja estavam fechados):** `RegulatoryDiagnosis`/`RegulatoryIssue` (A1 D1), MemPalace stub deletado (Sprint Z), `PROJECT_NAME` ja rebrandeado, `feat/ocr-automatico` era branch fantasma.

---

## Fase 2 — Implementacao das 4 dependencias da skill diagnostico (23/05/2026)

**Status:** ✅ **CONCLUIDA** — 4 commits mergeados em `feat/skill-diagnostico-impl`. Mergeado em `main` em 24/05.

| Onda | Commit | Conteudo | Testes |
|---|---|---|---|
| A4 (schema) | `43ac9d5` | `Risco` estendido 8+1 campos (taxonomia oficial + `prioridade_triagem`), `Divergencia`, `NotificacaoItem`, dual-emit via `model_validator(mode="after")`, `validate_diagnostic_content` (gate Pydantic↔JSONB), `RiscoSeveridade` ganhou `critico` | 76 schemas + 15 regressao Legislacao |
| K3 (RAG) | `92f6376` | 9 normas-chave indexadas via OpenAI 768d em `knowledge_catalog`: IN SEMAD 3/2025, 7/2024, Leis GO 18.102/13, 18.104/13, 21.231/22, Decreto GO 9.710/20, IN INCRA 131/23, CONAMA 428/10, 429/11. **+466 chunks novos**. | — |
| A3 (citation) | `5c4dd33` | `_evaluate_citations` no `DiagnosticoAgent` espelhando padrao do Redator. Citacoes sem match viram `citation_issues`. | 7 |
| A2 (auditor) | `1830e70` | `AuditorImovelAgent` novo + `app/services/property_audit.py` (matricula × CAR × CCIR/ITR + GEO INCRA + RL averbada × declarada). LLM **NAO** faz a conta. | 9 + 26 |

Decisoes: dual-emit do `Risco` via `model_validator` (nao alias — reconcile bidirecional); `RiscoSeveridade` aditivo (manteve compat); `validate_diagnostic_content` como funcao utilitaria pura (chamada antes de gravar em JSONB).

---

## Pos-Fase 2 — Ondas A/B/C (24/05/2026)

**Status:** ✅ **MERGEADA EM MAIN** — commits `357993c` (Onda A) + `5e64db4` (B+C). Doc completo: `docs/_archive/progressos/progresso7.md` (mesmo arquivo cobre Fase 0 + Fase 2 + Pos-Fase 2).

| Onda | Commits | Conteudo |
|---|---|---|
| A (fixes pre-existentes) | `e9c1a00`, `d9c021d`, `9ea9069`, `742a398`, `d062f71` | 4 testes pre-existentes corrigidos: `pytest.approx` (#1 float), aceita 202 (#2 endpoint async), `cost_usd=0.0` (#4 sem `or None`), `_load_tenant_logo` degrada graciosamente (#3 radar-nao-cancela aplicado ao codigo) |
| B (pipeline ativo) | `6b25602`, `7d6377e`, `b601ac7` | **B1:** `auditor_imovel` ativo na chain `diagnostico_completo` (`extrator → auditor_imovel → legislacao → diagnostico`) via `NON_BLOCKING_REVIEW_AGENTS` (agente sinaliza review mas chain segue). **B2:** `POST /api/v1/processes/{id}/diagnoses` versionado, chama `validate_diagnostic_content` antes de persistir (gate A4 vivo). |
| C (regua de divergencia) | `2348096` | Regua de **4 faixas** validada pela socia: ≤1% informativo, 1-5% atencao, 5-10% alto, >10% critico. **Sempre emite o finding** (areas iguais viram informativo — auditoria sabe que cruzamento ocorreu). |

Decisoes: `NON_BLOCKING_REVIEW_AGENTS` (criterio: agente produtor de insumo segue na chain mesmo com requires_review=True); `AuditFinding.grade` (4 niveis) ortogonal a `severity` (3 niveis) com mapeamento explicito; versionamento monotonico (`MAX(version)+1`); race no version capturada via `UniqueConstraint`.

Push final em `origin/main` em 24/05 23:30: `5e3780a..5e64db4`, 23 commits.

---

## Upstash polling redução (25/05/2026)

**Status:** ✅ **MERGEADA EM MAIN** — commit `a746eb0` (PR #2, merge `bc98c93`).

`polling_interval=5.0`, `broker_heartbeat=240`, `worker_prefetch_multiplier=1` no Celery; beat schedule do `vigia` 6h→12h e `acompanhamento` 30min→2h. **177k cmds/dia → ~25k/dia (-85%).** Cabe no PAYG Upstash ~$1.50/mês.

---

## PROMPT_4 — Fechar pipeline ponta a ponta (25/05/2026)

**Status:** ✅ **CONCLUIDA** — 2 commits em `feat/prompt4-fechar-pipeline` (PR aberto, pendente de merge). Doc completo: `docs/_archive/progressos/progresso8.md`.

| Onda | Commit | Conteudo | Testes |
|---|---|---|---|
| A (consumo do auditor) | `f93b4b4` | `DiagnosticoAgent` consome `chain_data["auditor_imovel"]["findings_raw"]` → `Divergencia` + `Risco` com `grau` 4 niveis preservado. Mapeamentos `_GRADE_TO_GRAU` (4→4, **`critico` vira `critico_impeditivo_potencial`**, NAO colapsa) e `_FINDING_TYPE_TO_CATEGORIA`. `nivel_risco_geral` derivado do pior grau. Path rules-based tambem consome. Auditor agora emite `grade` em `findings_raw` (antes omitia) e preenche grade em todos os AuditFinding (geo→crítico, rl→régua, espacial→informativo). | 15 |
| B (assinatura humana) | `c74ff2e` | `PATCH /api/v1/processes/{id}/diagnoses/{version}/validate` fecha **camada 1 do Princípio 1**. Grava `validated_by_user_id` + `validated_at`; AuditLog com hash chain SHA-256. **409 ao revalidar** (idempotencia explícita, evita sobrescrita silenciosa do assinante original). | 8 |

Decisoes: 409 nao-200 ao revalidar; `Risco.evidencia` recebe JSON serializado deterministico (`sort_keys=True`); `PropertyMock` no nivel da classe para mockar `@property` em pydantic Settings. Item rapido `PROJECT_NAME` ja estava resolvido (Fase 0).

**Suite total:** 585 passed, 0 failed (vs 562 em main — +23 testes).

### Dividas fechadas

- **#1** (Diagnóstico consome auditor) — Onda A.
- **#2** (assinatura humana, camada 1) — Onda B.
- **#4 (parcial)** alto vs. crítico preservados no **payload**. A persistência em
  `RegulatoryIssue` ainda colapsa — sai no PROMPT_5.
- **#12** (`PROJECT_NAME`) já fechada na Fase 0; confirmada.

### Proxima rodada

**PROMPT_5** — Remodelar `RegulatoryIssue`: `familia` (enum estável ~11) + `codigo_alerta`
(catálogo evolutivo, NÃO enum) + campos novos + `severity` 4 níveis. Auditor passa a gravar
`familia` + `codigo_alerta` reais (não mais `type="outro"`). Onda C: **propõe** reconciliação
de status (3 conjuntos circulantes), não implementa.

---

## PROMPT_5 — Remodelar `RegulatoryIssue` (25/05/2026)

**Status:** ✅ **CONCLUIDA** — PR `feat/prompt5-remodelar-regulatory-issue` a abrir.
Doc completo: `docs/_archive/progressos/progresso9.md`. Suite 591/591 verde.

### Motivacao

A skill `auditor_imovel/analise_divergencias_documentais` v1.1.0 (validada pela sócia em
governanca-documental) definiu 40 códigos de alerta em 11 famílias, com campos
`muda_rota_regulatoria` / `muda_escopo_preco_prazo` / `documentos_cruzados` por código e
régua de 4 níveis. O `RegulatoryIssue` antigo tinha enum `type` curto (5 valores genéricos,
maioria caía em `outro`) + `severity` 3 níveis (`info`/`warning`/`critical`) que colapsava
alto+crítico — dívidas #3 e #4 do `REGISTRO_DIVIDAS.md`.

### O que foi entregue

| Onda | Conteúdo |
|---|---|
| A (modelo + migration) | 3 enums novos (`RegulatoryFamilia`, `RegulatoryAlertFactibilidade`, `RegulatoryIssueSeverity` em 4 níveis). Model `RegulatoryIssueCatalog` (PK = `codigo_alerta` string, catálogo evolutivo via INSERT). `RegulatoryIssue` ganha `codigo_alerta` (FK) + `familia` + `muda_*` + `documentos_cruzados`; `severity` 4 níveis (substitui 3). Seed em `app/models/regulatory_catalog_seed.py` (fonte única) com 45 entradas. Migration `c1b2d3e4f5a7` cria tudo + migra dados antigos. `type` legado fica nullable (deprecated). |
| A (auditor + diagnostico) | `property_audit.py`: `AuditFinding` rico com `codigo_alerta`/`familia`/`grade`. `audit_property()` emite codigos reais por par (`AREA_MATRICULA_X_CAR`, etc.). `_GRADE_TO_SEVERITY` removido. `_FINDING_TO_ISSUE_TYPE` / `finding_to_issue_type` removidos (codigo_alerta vai direto). `auditor_imovel.py`: persiste taxonomia rica. `diagnostico.py`: `_FAMILIA_TO_CATEGORIA` (11→7) substitui `_FINDING_TYPE_TO_CATEGORIA` (4→4). |
| B | Códigos 📄 (documental) emitidos AGORA. 🛰️ (geoespacial) e 🔌 (consulta externa) ficam no catálogo mas NÃO são emitidos até infra (D1 / integrações externas). |
| C | **Proposta** em `docs/arquitetura/RECONCILIACAO_STATUS_ALERTAS.md`: 3 opções analisadas (A: três campos ortogonais; B: campo único com state machine; C: dois campos + saneamento derivado). **Recomendação técnica = Opção A.** NÃO implementada — aguarda decisão do Andre. |

### Decisões arquiteturais

- **Catálogo evolutivo via INSERT, não enum** (`regulatory_issue_catalog`). Adicionar código novo no tempo do produto sem ciclo de deploy.
- **11 famílias estáveis** (enum). Acréscimo de família é decisão arquitetural; acréscimo de código não.
- **Severity 4 níveis** (sai `_GRADE_TO_SEVERITY`). Preserva alto vs. crítico ponta a ponta (gatilho da camada 2 do Princípio 1).
- **`type` nullable** (não dropado). Retrocompat com registros antigos; novos têm `codigo_alerta` preenchido + `type=None`.
- **Onda C foi só proposta** — PROMPT_5 proibiu implementar; depende de validação da sócia + decisão do Andre.

### Suite

**591 passed, 0 failed** (vs 585 em main — +6 líquido: +7 `TestRegulatoryIssueCatalog`,
-1 do `TestFindingToIssueType` removido).

### Dividas fechadas

- **#3** (Remodelar `RegulatoryIssue` rico) — Onda A.
- **#4** (Colapso 4→3 no `_GRADE_TO_SEVERITY`) — Onda A. Severity é 4 níveis em persistência.

### Proxima rodada

- **Decisão do Andre + sócia** sobre a Opção A da reconciliação de status.
- **Camada 2 do Princípio 1** (5 botões P4 — decisão por alerta crítico) depende do acima.

---

## PROMPT_6 — Camada 2 do Princípio 1: reconciliação dos 3 status (26/05/2026)

**Status:** ✅ **CONCLUIDA** — PR `feat/prompt6-camada2-principio1` a abrir.
Doc completo: `docs/_archive/progressos/progresso10.md`.

### Motivacao

A proposta da Onda C do PROMPT_5 (`docs/arquitetura/RECONCILIACAO_STATUS_ALERTAS.md`)
foi aprovada — **Opção A: três campos ortogonais** (`status_achado` /
`decisao_consultor` / `status_saneamento`). Implementação destrava a **camada
2 do Princípio 1**: os 5 botões da P4 viram decisão obrigatória sobre cada
alerta crítico antes da assinatura do diagnóstico. Fecha dívida #5.

### O que foi entregue

| Onda | Conteúdo |
|---|---|
| A1 (modelo + migration) | 3 enums novos (`StatusAchado` 5v, `DecisaoConsultor` 5v=os 5 botões P4, `StatusSaneamento` 5v) + 5 colunas em `RegulatoryIssue`: `status_achado` (NOT NULL default `suspeita`), `decisao_consultor` (nullable), `decisao_consultor_justificativa` (texto livre), `decisao_consultor_at` (timestamp, gerenciado pelo servidor), `status_saneamento` (NOT NULL default `pendente`). Migration `d2c3e4f5a6b8` aditiva pura. |
| A2 (auditor) | Confirmação que `auditor_imovel._persist_issues` não precisa de mudança — defaults do model (`suspeita`/`pendente`) aplicam automaticamente. |
| B (endpoint PATCH) | `PATCH /api/v1/properties/{prop}/issues/{id}` aceita body parcial (`RegulatoryIssueUpdate`). AuditLog **granular por campo** com hash chain SHA-256. No-op por campo (mesmo valor) não gera AuditLog. `decisao_consultor_at` gerenciado server-side. |
| D (camada 2 do P1) | `PATCH /validate` ganha gate: **422** com lista de alertas pendentes quando há `RegulatoryIssue` com `severity=critico` sem `decisao_consultor`. Críticas RESOLVIDAS (`resolved_at != NULL`) não bloqueiam. Não-críticas não bloqueiam (a sócia afiou alto-vs-crítico de propósito). |

### Decisões arquiteturais

- **Opção A — 3 campos ortogonais**: cada um mede dimensão diferente (natureza do indício / ação escolhida / progresso prático). Sem derivação automática; cada um editável.
- **`decisao_consultor_at` server-side**: body PATCH não aceita override do timestamp. Server grava em qualquer mudança de `decisao_consultor` (inclui transições para NULL).
- **Gate só para `critico`**: alto/atencao/informativo não bloqueiam.
- **Crítica RESOLVIDA não bloqueia**: `resolved_at != NULL` = sanada no mundo, sem precisar de decisão pendente.
- **AuditLog granular por campo (não payload único)**: cada campo alterado vira AuditLog próprio com `old_value`/`new_value`.

### Testes

18 testes novos (em `tests/api/test_regulatory.py`):
- `TestUpdatePropertyIssue` (11)
- `TestValidateDiagnosisGateCamada2` (6) — *nota: numeração das classes; 6 cobre 6 cenários do gate*

Subset rodado verde (18/18). Suite completa rodando em background no fechamento.

### Dividas fechadas

- **#5** — Reconciliação dos 3 status. Opção A implementada inteira.
- **Camada 2 do Princípio 1** — os 5 botões P4 como `DecisaoConsultor` enum + gate no `PATCH /validate`.

### Proximas rodadas (frontend depende)

- **UI dos 5 botões + 3 status editáveis** — frontend consome `RegulatoryIssueOut` (com 3 campos novos) + PATCH `/properties/{prop}/issues/{id}`. Cada card de alerta crítico = 5 radios + textarea + botão "Decidir". Botão "Assinar diagnóstico" só habilita quando todas as críticas têm decisão.

---

## Pós-PROMPT_6 (26/05/2026) — revisão estrutural + decisão da Isis

Duas atualizações pequenas mas estruturalmente importantes mergeadas em 26/05:

**1. Revisão da governança (PR #6/#7, commits f4e6f6b + 3e66f45):**
- Aplicou checklist da `GOVERNANCA_DOCUMENTAL` que o PROMPT_6 deixou pendente: `MODELO_DE_DADOS` e `API_v1` atualizados com os gatilhos de estrutura (schema novo + endpoint novo).
- Fechou dívida #19 (justificativa obrigatória para `ignorar_justificado` e `fora_escopo`): `@model_validator` no `RegulatoryIssueUpdate` + 5 testes novos. Camada 2 do Princípio 1 fica completa no caso que mais importa (descartar uma crítica).
- 2 dívidas novas reveladas pela revisão: #17 (coerência entre os 3 status, P2) e #18 (verificador do hash chain, P3 com marco "antes do 1º uso jurídico").

**2. ADR-012 aceito pela Isis (a decisão do consultor é contextual ao processo):**
- A sócia validou em 26/05 a alternativa **(b) cada trabalho recomeça**. O fato da divergência é perene (Property), mas a decisão do consultor é contextual ao processo. Titularidade torta pesa diferente para vender e para dar como garantia ao banco.
- Implicação: os 3 campos de decisão (`decisao_consultor`/`justificativa`/`at`) **vão sair** do `RegulatoryIssue` na próxima rodada e virar `ProcessIssueDecision` por `(processo × issue)`. Cada processo recomeça do zero.
- O PROMPT_6 ficou **parcial** nesse aspecto — a estrutura está pronta mas no lugar errado. Não é regressão (o gate funciona, a UI funcionaria), mas o comportamento seria errado para o caso real (processo B herdaria decisão do processo A automaticamente).
- Skill `auditor_imovel/analise_divergencias_documentais` **validada integralmente** pela sócia — separação 📄/🛰️/🔌 confirmada. Atualização mergeada na mesma rodada (4 linhas no final do arquivo).
- Dívida #17 (coerência) **espera** essa re-modelagem para ser implementada — uma das regras de coerência cruza entidades agora.

### Próxima rodada (PROMPT_7 — re-modelagem ADR-012)

Nova tabela `process_issue_decisions` (FK composta `process_id × issue_id`).
Migration que move os 3 campos. `PATCH /properties/.../issues/{id}` perde os
campos de decisão; novo endpoint por processo (`PATCH /processes/{pid}/issues/{iid}/decision`).
Gate `/validate` aprendido a olhar a tabela nova. Re-examinar
`status_saneamento` para separar saneamento real (perene) de avaliação
contextual. Bloqueia a UI dos 5 botões.

---

## PROMPT_7 — Decisão contextual ao processo (ADR-012) (26/05/2026)

**Status:** ✅ **CONCLUIDA** — PR `feat/prompt7-decisao-contextual` a abrir.
Doc completo: `docs/_archive/progressos/progresso11.md`. Suite 625/625 verdes
(+16 vs 609 baseline).

### Motivacao

ADR-012 (Isis, 26/05): a decisão do consultor é **contextual ao processo**,
não perene no imóvel. O PROMPT_6 deixou `decisao_consultor` como campo do
`RegulatoryIssue` (Property — perene). Esta rodada implementa a re-modelagem.

### O que foi entregue

| Onda | Conteúdo |
|---|---|
| A (model + migration) | Nova entidade `ProcessIssueDecision` com FK composta única `(process_id, issue_id)` e campos `decisao` (NOT NULL) / `justificativa` / `decided_by_user_id` (FK users, **novo**) / `decided_at`. RegulatoryIssue **perdeu** 3 colunas (`decisao_consultor`/`justificativa`/`at`). Migration `e3d4f5g6a7b8` cria tabela + drop sem backfill nas 3 colunas (sem dados em prod). |
| B (schemas) | `RegulatoryIssueOut`/`Update` perderam 3 campos (sobraram `status_achado` e `status_saneamento`). Novos `ProcessIssueDecisionCreate`/`Out`. Validator de justificativa obrigatória **migrou** para o schema novo. |
| C (endpoints) | `PATCH /properties/.../issues/{id}` enxugou (só status perenes). Novos: `GET` e `PUT /processes/{pid}/issues/{iid}/decision` (upsert; AuditLog granular por campo com hash chain SHA-256). Gate `/validate` cruza issues críticas × `ProcessIssueDecision` **deste processo** (cross-processo não libera). |
| D (testes) | TestUpdatePropertyIssue enxugado; TestUpdatePropertyIssueJustificativaObrigatoria → TestProcessIssueDecisionJustificativaObrigatoria; TestValidateDiagnosisGateCamada2 adaptado + novo cenário `test_decisao_de_outro_processo_nao_libera_gate`; **novo** TestProcessIssueDecision (11 testes CRUD + autoria + AuditLog + tenant isolation). |

### Decisões arquiteturais

- **Nomes encurtados**: `decisao` / `justificativa` / `decided_at` (contexto da tabela já indica).
- **Drop sem backfill** (sem dados em prod ainda — Andre confirmou).
- **`decided_by_user_id`** novo (PROMPT_6 só tinha timestamp; agora autor explícito).
- **`status_achado` e `status_saneamento` permanecem em `RegulatoryIssue`** — fato perene do imóvel. YAGNI sobre "saneamento contextual" — só se aparecer demanda.

### Dívidas fechadas

- **#20** (re-modelagem ADR-012) — implementada inteira.

### Próximas rodadas

- **UI dos 5 botões + 3 status** — desbloqueada agora que o backend ADR-012
  está estável. Aba "Alertas" no ProcessDetail consome `RegulatoryIssueOut`
  (read-only nos 2 status) + `PUT /processes/.../decision`.
- **#17 (coerência entre status)** — desbloqueada também. Regras menores:
  2 sobre os campos perenes, 1 cross-entidade no PUT decision.

---

## PROMPT_8 — Coerência entre status do alerta (#17) (26/05/2026)

**Status:** ✅ **CONCLUIDA** — branch `feat/prompt8-coerencia-status`. Suite
635/635 verdes (+10 vs 625 baseline do PROMPT_7).

### Motivação

Após PROMPT_7, os 3 status (`status_achado` e `status_saneamento` perenes
em `RegulatoryIssue`; `decisao` em `ProcessIssueDecision`) eram enums
soltos no DB — o sistema aceitava combinações que o negócio considera
absurdas (saneamento concluído sobre achado em suspeita, decisão sobre
algo ainda não confirmado). Dívida #17 — esvazia o último P2 regulatório.

### O que foi entregue

| Onda | Conteúdo |
|---|---|
| A (helper puro) | `app/services/regulatory_coherence.py` — 2 funções (`assert_status_coerente`, `assert_decisao_permitida`) + exception `StatusCoherenceError(ValueError)`. Conjuntos frozen explícitos (`_SANEAMENTO_EXIGE_ACHADO_VALIDADO`, `_ACHADOS_QUE_HABILITAM_SANEAMENTO`). 100% de coverage. |
| B (schema) | `RegulatoryIssueUpdate` ganha `@model_validator(mode="after")` que delega ao helper quando os 2 status vêm juntos no body (fast-fail, sem ler o DB). |
| C (endpoints) | `PATCH /properties/.../issues/{id}` chama o helper sobre o **estado resultante** (corpo aplicado sobre a issue carregada — fonte da verdade, cobre PATCH parcial). `PUT /processes/.../decision` chama `assert_decisao_permitida(issue.status_achado)` antes do upsert — 422 com mensagem acionável. |
| D (testes) | `TestCoerenciaStatusPerene` (7 cenários: 2 fast-fail no body completo, 2 PATCH parcial, 1 transição simultânea, 1 `resolvida+saneado`, 1 saneamento descartado); `TestDecisaoBloqueadaSeAchadoSuspeita` (3 cenários: 422 com suspeita, 200 com confirmada, 422 não grava nada no DB). Adaptados 7 testes pré-existentes que seedavam issue em `suspeita` (default) e faziam `PUT /decision` esperando 200 — `_seed_issue` ganha parâmetro `status_achado`. |

### Decisões arquiteturais

- **Escopo fechado em 2 regras semânticas** (não construir máquina de
  estados completa — over-engineering para dívida P2; consultor não é
  adversário, barrar só o absurdo óbvio).
- **`resolvida` habilita saneamento ativo/concluído**, junto com
  `confirmada` (decisão de UX validada com Andre 26/05). Bloquear a
  transição simultânea `confirmada → resolvida` + `em_validacao →
  saneado` no mesmo PATCH forçaria salvar em duas etapas — friction sem
  ganho de invariante. `resolvida` é evolução terminal de `confirmada`.
- **Sem migration** — isto é validação, não modelagem. Os 3 enums
  continuam soltos no DB; a coerência é enforçada na borda (schema +
  endpoint).
- **Fonte da verdade no endpoint** — o `@model_validator` só dispara
  quando os 2 campos vêm juntos no body; o endpoint compara o estado
  resultante (corpo + DB) e é quem garante a invariante. Mesmo helper,
  sem duplicação de regra.
- **Mensagens de erro acionáveis** (UI vai consumir): Regra A cita
  `confirmada`/`resolvida`; Regra B diz "Confirme ou descarte o achado
  antes de decidir" — dica direta para o consultor.

### Dívidas fechadas

- **#17** (coerência entre os 3 status reconciliados) — implementada
  inteira. P2 regulatória esvaziada.

### Heads-up para a UI (registrado, não implementado)

Pela Regra B, alertas críticos presos em `suspeita` não aceitam decisão —
e o gate do `/validate` exige decisão para toda crítica. Logo, a aba
"Alertas" do ProcessDetail precisa deixar o consultor **mover o
`status_achado`** (`suspeita → confirmada`/`descartada`) na mesma tela em
que ele decide o que fazer, senão trava no gate sem caminho. A mensagem
422 da Regra B é o suficiente para a UI orientar.

### Próximas rodadas

- **UI dos 5 botões + 3 status** (única frente aberta agora — backend
  regulatório completo com guardas de coerência).

---

## PROMPT_9 — UI da camada 2 do Princípio 1 (26/05/2026)

**Status:** ✅ **CONCLUIDA** — branch `feat/prompt9-ui-alertas-decisao`,
31/31 testes verdes no frontend (Vitest+RTL, 21 pré-existentes + 10
novos).

### Motivação

Backend regulatório completo após PROMPT_4/5/6/7/8 — mas o consultor
ainda não tinha tela pra usar. Esta rodada consome o contrato existente
e materializa o ciclo do Princípio 1: a IA propõe, o humano decide e
assina, **alerta por alerta**. Sem inventar backend.

### O que foi entregue

| Onda | Conteúdo |
|---|---|
| A (camada de dados) | `frontend/src/lib/regulatory/{types,labels,hooks}.ts` espelha o contrato dos endpoints regulatórios (sem renomear valor nem inventar campo). Labels pt-BR + classes Tailwind por severidade (tom forte só pra `critico` — não afoga em vermelho). React Query hooks com query keys centralizadas; `useDecision` trata 404 como `null` (ADR-012). `useUpsertDecision` invalida `diagnoses` (gate cruza as duas entidades). |
| B (aba Alertas) | `AlertasTab` + `AlertaCard` em `pages/Processes/`. Lista issues do imóvel, críticos no topo. **Regra B preventiva na UI:** enquanto `status_achado === 'suspeita'`, `<fieldset>` da decisão fica `disabled` com hint claro. **#19 client-side:** botão "Registrar decisão" disabled enquanto textarea vazia em `ignorar_justificado`/`fora_escopo`. 422 da Regra A renderiza inline (não em toast). Empty state pra `property_id === null`. `TabKey` ganha `'alertas'` no `ProcessDetail`. |
| C (gate + PropertyHub) | `DiagnosisAssinatura` no topo do `DiagnosisTab` — busca última versão do `RegulatoryDiagnosis`, calcula pendentes via `useQueries` (críticas × decisões), botão "Assinar vN" com badge. 422 do gate abre modal com `detail.alertas_pendentes`; click no item troca pra aba "Alertas" e faz `scrollIntoView` do card `#alerta-{id}`. **Backend é a autoridade:** se cálculo client-side divergir do 422 (cache stale), mostra o que veio no 422. Modal segue padrão da casa (overlay fixed + backdrop-blur). **PropertyHub.AnalysesTab aumentado** (era stub): vira lente do ADR-012 — chips de TODOS os processos por issue, "Processo #N (demand) · {decisão\|pendente} · Decidir/Ver" com verbo-por-estado via `useDecision`. Cor emerald = decidida, amber = pendente. Teto visual "+N mais". |
| D (testes) | `AlertaCard.test.tsx` (7 cenários: Regra B desabilita em suspeita, `it.each` confirma habilita nos 4 outros achados, #19 desabilita submit em textarea vazia + libera ao preencher + bloqueia em só-espaços, `corrigir_antes` não exige justificativa). `DiagnosisAssinatura.test.tsx` (3 cenários: 422 do gate abre modal e click dispara `onGoToAlerta`; card "assinado" quando `validated_at`; render silencioso sem diagnóstico). Runner `frontend/scripts/run-vitest.mjs` injeta `NODE_OPTIONS=--experimental-require-module` (workaround jsdom 27 + Node 22.11). |

### Decisões arquiteturais

- **Regra B preventiva na UI**, não reativa. O 422 do backend é rede de
  segurança; a primeira linha é o `disabled` do `<fieldset>` que sai
  sozinho quando o consultor adjudica o achado (`useUpdateIssue`
  invalida `issues` → re-render → libera). É o que evita travar no gate
  sem caminho.
- **Backend é a autoridade do gate camada 2**, não o cálculo
  client-side. O badge "N pendentes" é heurística pra UI orientar; o
  422 com `alertas_pendentes` decide.
- **Verbo-por-estado nos chips do PropertyHub** ("Decidir"/"Ver"
  conforme `useDecision` retorna `null` ou objeto), com label da
  decisão visível quando há — é o ADR-012 renderizado em pixel.
  Listar TODOS os processos (não eleger "ativo"): qualquer eleição
  reintroduziria a perenidade que a Isis rejeitou.
- **Cache compartilhado** entre AlertaCard, DiagnosisAssinatura e
  IssueProcessChip via `regulatoryKeys.decision(pid, iid)` — três telas
  vêem a mesma decisão sem refetch.
- **#19 (justificativa obrigatória) tem 3 camadas:** schema Pydantic
  (rejeição definitiva), endpoint (rede de segurança), UI client-side
  (preempção do erro). Cada camada tem responsabilidade clara.
- **Sem backend novo, sem ADR novo, sem migration** — é UI sobre
  contrato existente, como o prompt explicitou.

### Dívidas reveladas

- **#22** (workaround do runner Vitest pra jsdom 27 + Node 22.11) —
  registrado como dívida P3 com marco condicional (jsdom corrigir
  upstream OU subida pra Node 22.12+). O runner é local e isolado.

### Próximas rodadas

- **Frente aberta** pra decisão do Andre: #18 (verifier de hash chain
  do AuditLog), geoespacial 🛰️ (corpus de áreas + `Property.geom`),
  mobile/client-portal (descongelar), ou continuidade do RAG estadual.

---

## PROMPT_10 — Gate camada 2 exclui achados terminais (#23) (26/05/2026)

**Status:** ✅ **CONCLUIDA** — branch `feat/prompt10-gate-exclui-terminais`.
Suite 639/639 verde (+4 vs 635 do PROMPT_8).

### Motivação

Trap descoberto na revisão do PROMPT_9 (UI da camada 2): o gate de
`PATCH /diagnoses/{version}/validate` filtrava apenas
`severity=critico AND resolved_at IS NULL`, sem olhar `status_achado`.
Resultado: um achado crítico que o consultor já tinha descartado como
falso positivo AINDA cobrava decisão — dupla negação ("não é real" via
`status_achado=descartada` + "ignorar justificado" via `decisao` +
justificativa redundante). Saída #1 do trio do Andre: estreitar o filtro,
não complicar a UI.

### Passo 0 — leituras antes de mexer

- Filtro real do gate em `regulatory.py:266-275`.
- Enum `StatusAchado` em `models/regulatory.py:138-148` — 5 valores.
- **Descoberta:** grep `resolved_at\s*=` em `app/**/*.py` retorna **zero
  matches**. Nenhum fluxo do produto seta `resolved_at` — só os testes
  via `_seed_issue(resolved=True)`. Significa que `status_achado=resolvida`
  e o critério `resolved_at IS NULL` estão **desacoplados**: precisa do
  filtro explícito por `status_achado` para o trap fechar (não duplicação).

### O que foi entregue

| Onda | Conteúdo |
|---|---|
| A (filtro) | `regulatory.py` ganha `RegulatoryIssue.status_achado.in_([StatusAchado.suspeita, StatusAchado.confirmada])` na query do gate. Comentário inline explica: terminais não cobram decisão; `suspeita` permanece para forçar adjudicação; `resolved_at IS NULL` mantido como critério ortogonal. Import de `StatusAchado` adicionado. |
| B (testes) | 4 testes novos em `TestValidateDiagnosisGateCamada2`: cada terminal (`descartada`, `resolvida`, `ignorada`) libera o gate sem decisão; `confirmada` sem decisão continua 422 (regressão explícita). `_seed_issue` já tinha `status_achado` desde PROMPT_8 — reutilizado. Pré-existentes do gate passam sem mudança (todos usam `suspeita` default). |
| C (docs) | `REGISTRO_DIVIDAS`: #23 fechada. `ESTADO_ATUAL`: bullet PROMPT_10 + follow-on do badge anotado. `API_v1`: nota inline do 422 estreitou. `FLUXOS_E2E`: nota curta sobre "descartar → assinar". `GOVERNANCA`: índice 1..14. Snapshot `progresso14.md`. |

### Decisão sobre `ignorada`

Prompt antecipou ambiguidade: pode soar como `decisao=ignorar_justificado`
ou como adjudicação terminal do achado. AskUserQuestion → Andre confirmou
**excluir** (recomendado). Semântica fechada: `status_achado=ignorada`
significa "consultor optou por não tratar como fato do imóvel" — terminal
simétrico a `descartada`. Sem ambiguidade com `ignorar_justificado` (que
é ação no contexto do processo, não adjudicação do fato).

### Decisões arquiteturais

- **Estreitar o filtro, não complicar a UI.** A UI já habilita decisão
  em todos os achados não-suspeita (PROMPT_9) — backend mais permissivo
  evita dupla negação UX.
- **`suspeita` permanece dentro do gate** — força adjudicação antes de
  assinar. Não é deadlock porque o consultor pode mover `status_achado`
  pelo PATCH /issues.
- **`resolved_at IS NULL` mantido** como critério ortogonal — mesmo
  sendo vacuoso hoje, reflete intenção semântica e cobre o caso futuro
  de fluxo que marque `resolved_at`.
- **Filtro positivo** (`in [suspeita, confirmada]`) em vez de negativo
  — mais fácil de raciocinar quando lê o código.
- **Sem migration, sem ADR, sem schema change** — é refinamento de
  query no gate camada 2 já firmado.

### Dívidas fechadas

- **#23** — gate cobrando decisão em achado terminal (trap revelado
  pós-PROMPT_9).

### Follow-on aberto

- **Badge do `DiagnosisAssinatura` (PROMPT_9)** precisa espelhar a mesma
  exclusão pra não super-contar pendentes. Aplicado depois que PROMPT_9
  estiver em main (1 linha no filtro client-side de `criticasAbertas`).
  Modal já consome `alertas_pendentes` do 422 (autoridade), então sempre
  estará correto independente do badge.

### Próximas rodadas

- **Frente aberta** — follow-on do badge OU próxima frente nova (#18
  hash-chain verifier, geoespacial 🛰️, mobile/client-portal).

---

## PROMPT_11 — Hotfix: `ignorada` volta a exigir decisão (26/05/2026)

**Status:** ✅ **CONCLUIDA** — branch `fix/prompt11-ignorada-volta-ao-gate`.
Suite 639/639 verde. Corrige furo introduzido no PROMPT_10 (#23).

### Motivação

O PROMPT_10 excluiu `ignorada` do gate junto com `descartada`/`resolvida`,
assumindo simetria entre os três. **Não são simétricos.** `descartada`
("não é divergência real") e `resolvida` ("corrigida no mundo") são
terminais sem o que decidir — exclusão correta. `ignorada`
(`models/regulatory.py:147`: "consultor optou por não tratar") é um achado
**REAL** posto de lado.

O furo: setar `status_achado=ignorada` via `PATCH /issues` NÃO exige
justificativa (o `RegulatoryIssueUpdate` só valida coerência da Regra A).
Com o gate excluindo `ignorada`, um consultor podia silenciar um crítico
real sem registrar justificativa nenhuma — recriando exatamente a porta
que o #19 fechou para `decisao=ignorar_justificado`. Como o PROMPT_10 já
estava em main (PR #12), virou hotfix.

### A mudança (escopo fechado)

- **Código (1 linha):** filtro do gate em `regulatory.py` passa de
  `status_achado.in_([suspeita, confirmada])` para
  `.in_([suspeita, confirmada, ignorada])`. Só `descartada`/`resolvida`
  ficam excluídas. Comentário do gate reescrito explicando por que
  `ignorada` é diferente.
- **Teste (1 virado):** `test_200_critica_ignorada_sem_decisao_libera_gate`
  (do #10, que documentava o furo) virou
  `test_422_critica_ignorada_sem_decisao_continua_bloqueando`. Os outros 3
  do #10 seguem (`descartada`/`resolvida` liberam; `confirmada` exige).
- **Docs:** #23 corrigido no `REGISTRO_DIVIDAS`; `ESTADO_ATUAL`, `API_v1`,
  `FLUXOS_E2E` ajustados (todos diziam "ignorada não cobra").

### Sem deadlock

Quem quer ignorar um crítico real registra `decisao=ignorar_justificado`
no PUT /decision, que exige justificativa (#19). A Regra B permite porque
`ignorada` ≠ `suspeita`. O caminho **justificado** fica; só fecha o
caminho **sem-justificativa**.

### Lição registrada

A exclusão de `ignorada` veio de uma recomendação rasa no PROMPT_10
("simetria com descartada") sem checar o impacto cruzado no #19. Antes de
recomendar excluir um estado de um gate de auditabilidade, a pergunta
obrigatória é: "isso abre caminho pra pular uma garantia que outra regra
já estabeleceu?". Aqui, abria. O André pegou na revisão antes de produção.

### Próximas rodadas

- **Follow-on do badge** (PROMPT_9): espelhar a exclusão `descartada`/
  `resolvida` no cálculo client-side de `criticasAbertas`. Agora com
  #9/#10/#11 em main, é a tarefa curta natural. OU próxima frente nova.

---

## fix/upload-checklist-binding (2026-05-28) — destrava ciclo de teste

### Motivação

Sintoma reportado: documento subido pela tela não virava "recebido" no
checklist, campos extraídos pelo `extrator` apareciam só como badge sem
mostrar o dado, e não dava pra apagar cliente/imóvel pra resubir caso de
teste (FKs RESTRICT do banco bloqueavam o DELETE direto).

### O que mudou na superfície IA

A camada de agentes em si não mudou — o `extrator` continua emitindo
`AIJob.result` no mesmo shape (`Record<string, unknown>`). O que mudou foi
o **consumo** desse resultado:

- **DocumentsTab.tsx** agora renderiza `Object.entries(j.result)` em `<dl>`
  abaixo de cada documento processado (excluindo `document_id`/`doc_type`/
  `tenant_id`/`process_id` — metadados de controle sem valor de negócio).
  Antes só aparecia o badge "Campos extraídos" sem mostrar o que foi
  extraído — o extrator vinha funcionando e ninguém via.
- **`auto_link_document` no fluxo de upload:** `POST /documents/confirm-upload`
  passa a chamar o helper de `checklist_engine.py` quando o `document_type`
  do upload casa com um item pendente do checklist — o item vira `received`
  com `document_id` automaticamente. O frontend (`DocumentUploadZone.tsx`)
  já enviava `checklist_item_id` opcional; o schema só não aceitava.

### Sem agente novo, sem chain nova

Escopo fechado de fix — não toquei prompt/chain/registry de agente.
A interação IA ↔ checklist é determinística: matching exato por
`doc_type` string. Suficiente pro ciclo da Isis; melhorias semânticas
(matching fuzzy, embedding-based) ficam pra rodada futura se aparecer
demanda real.

---

## Pulso `fix/extrator-por-processo` — extração por processo + UI honesta (28/05/2026)

### Sintoma fechado

Antes desta rodada: na página `/agents`, clicar "Executar" no card do
`extrator` sem informar processo virava
`{"skipped": True, "reason": "Nenhum documento fornecido para extracao"}`
— a UI exibia "não identificado" no histórico, sem caminho de saída pro
consultor. Pior: quando um Document existia mas o OCR ainda não tinha
rodado, o agente levantava `ValueError("Documento N nao possui texto
extraido (OCR deve rodar primeiro)")` — diagnóstico técnico sem prescrição.

E no funil de cadastro: nada impedia o consultor de avançar do Step 4
(Documentos) pra Step 5 (Confirmar) sem ter clicado em "🤖 Ler
documentos com IA" — saía achando que rodou IA. Sem botão pra remover
um upload errado antes do OCR começar.

### O que entrou (fecha dívida #25)

- **Backend.** Novo `POST /api/v1/processes/{id}/extract` em
  `app/api/v1/processes.py`. Por documento (filtrando
  `tenant_id`+`process_id`+`deleted_at IS NULL`):
  - `extracted_text` cacheado e `force=false` → `workers.run_agent.delay(agent_name="extrator", process_id=…, metadata={document_id, document_type})`. Entra em `jobs`.
  - Caso contrário (ou `force=true`) → `workers.ocr_then_extract.delay(doc_id=…, force=…)`. Chain OCR (pypdf/Gemini/OpenAI Vision) que despacha o `extrator` ao fim. Entra em `pending_ocr`.
  - **404** sem documentos. AuditLog `extractor_dispatched` reusa `ProcessRepository.add_audit`.
- **Mensagens acionáveis no `ExtratorAgent`.**
  - O `reason` do skipped agora aponta 3 caminhos: `metadata.document_id`,
    `metadata.text`, ou `POST /api/v1/processes/{id}/extract`. Mantém o
    payload (`skipped: True`) — UI continua exibindo no histórico,
    apenas com mensagem útil.
  - O `ValueError` quando `Document.extracted_text` é NULL menciona
    explicitamente `POST /processes/{id}/extract` e `workers.ocr_then_extract`.
- **UI — `AgentsPage.tsx`.** Card do `extrator` (e SÓ dele) troca o
  "Executar" pelo botão **"Rodar no processo #N"**:
  - Disabled quando "ID do Processo" está vazio (com tooltip explicando).
  - Chama nova mutation que bate em `/processes/{id}/extract`.
  - Demais agentes mantêm o "Executar" sem mudança.
- **UI — `IntakeWizard.tsx` + `DraftDocumentUploader.tsx`.**
  - `DraftDocumentUploader` ganha props `onChange` (contagem de docs) e
    `onImportTriggered` (callback ao "Ler documentos com IA" sucedido).
  - `canGoNext()` do Step 4 retorna `false` se `uploadedDocCount > 0 && !importTriggered`. Step 4 com zero docs continua liberado (upload é opcional — regra Regente preservada).
  - Aviso amarelo informativo embaixo do uploader quando o avanço está travado.
- **UI — exclusão antes do OCR.** `DraftDocumentUploader` ganha botão
  🗑 por linha, habilitado quando `ocr_status` em `{null, pending}`.
  Reusa o `DELETE /api/v1/documents/{id}` existente (soft delete via
  `deleted_at`). Após `processing|done|failed`, exclusão fica em
  `DocumentsTab` (que já tem essa ação).

### Testes

- `tests/api/test_processes.py` (+3):
  - 3 docs (2 com texto, 1 sem) → 2 em `jobs` + 1 em `pending_ocr` + AuditLog gravado.
  - 0 docs → 404.
  - `force=true` força todos os 2 cacheados pra `ocr_then_extract`.
- `tests/agents/test_extrator_cache.py` (+1):
  - Sem args, `reason` contém "POST" + "/extract" + "document_id".
- O teste pré-existente `test_extrator_raises_when_no_text_and_no_cache` continua passando (assertiva busca `"OCR"` na mensagem — minha nova mensagem mantém).

### Suite verde

- Backend: `pytest tests/api/test_processes.py tests/agents/test_extrator_cache.py` → 13/13 verde.
- Frontend: `npx tsc --noEmit` clean; `npm run build` succeede.

### Cuidados respeitados

- **Worker Celery é dependência forte.** Documentado em
  `docs/operacao/RUNBOOK_DEV.md` — sem worker, uploads ficam em
  `ocr_status='pending'` indefinidamente.
- **ADR-011 não muda.** `NON_BLOCKING_REVIEW_AGENTS` segue igual; o bloqueio do `extrator` não foi alterado.
- **AgentRegistry reusado, agente novo não criado.**
- **Zero migration.** `Process`, `Document`, `AuditLog` já tinham todos os campos.

### Marco condicional (não fechado nesta rodada)

`app/workers/ocr_tasks.py:_dispatch_extrator` ainda passa `process_id=None`
ao `run_agent.delay(...)` — o `AIJob` resultante (no caminho da chain
OCR) perde o link com o processo. Fora do escopo do sintoma do PR. Se
isso começar a doer (consultor procurando o job pela aba do processo e
não achando), abre nova dívida e ajusta `_dispatch_extrator` pra receber
e propagar `process_id` opcional.

---

## Pulso `fix/diagnostico-propaga-estado` — assinatura propaga macroetapa (28/05/2026)

### Sintoma fechado

Antes desta rodada: o consultor abria o `PATCH /processes/{id}/diagnoses/
{version}/validate`, o backend gravava `validated_at` + AuditLog, devolvia
200 — e a `Process.macroetapa` ficava onde estava. O card do kanban lia
só `MacroetapaChecklist.completion_pct` para calcular o badge; o bloco
"diagnóstico assinado" lia `RegulatoryDiagnosis.validated_at`. Pior: o
gate `can_advance_macroetapa` não cobrava a assinatura, então mesmo um
clique manual em "Avançar" passava com diagnóstico não assinado.

### Escopo (conservador — eixo 2)

- **NÃO** unificar `Process.status` com `Process.macroetapa` (isso é o
  eixo 3 / PR3-agressivo). A divergência entre os dois eixos virou a
  dívida nova **#26** no `REGISTRO_DIVIDAS`.
- **NÃO** mexer nas 4 tabelas denormalizadas que carregam o status.
- **Tocar só** `app/api/v1/regulatory.py` + `app/models/macroetapa.py`
  no nível semântico; `app/api/v1/processes.py` ganhou propagação dos
  novos kwargs para honrar o critério "badge concorda imediatamente"
  sem refatorar — propagação mínima.

### O que mudou

- **`compute_macroetapa_state` e `can_advance_macroetapa`** ganham
  kwargs `current_macroetapa: Macroetapa | None = None` e
  `diagnosis_validated: bool = False`. Quando a etapa atual cai em
  `DIAGNOSTIC_MACROETAPAS = {diagnostico_preliminar,
  diagnostico_tecnico}`:
  - O badge devolve `aguardando_validacao` se `pct >= 1.0` mas a
    assinatura ainda não saiu.
  - O gate de saída acrescenta o blocker `"Diagnóstico desta etapa
    ainda não foi assinado pelo consultor."`.
  - Callers que não passam os kwargs preservam comportamento legado
    (compatibilidade pra trás).
- **`PATCH /processes/{id}/diagnoses/{version}/validate`** após o
  `db.commit()` da assinatura: se `process.macroetapa` é diagnóstica,
  recalcula `can_advance_macroetapa` com `diagnosis_validated=True` (a
  assinatura acabou de virar fato no banco) — se passa, chama
  `advance_macroetapa(process, nexts[0], …)` automaticamente e dá novo
  commit. Mesmo critério do botão "Avançar" manual: docs obrigatórios
  + checklist 100% + assinatura.
- **Kanban (`processes.py`)** executa uma única query agregada por
  `tenant_id` para carregar o set de `process_id` com
  `RegulatoryDiagnosis.validated_at IS NOT NULL` — evita N+1 na
  listagem. `_compute_can_advance` faz a mesma consulta por processo
  (caminho de detalhe).

### Testes

- `tests/models/test_macroetapa_gate.py` (novo) — 8 unitários puros
  (sem ORM) que cobrem: gate bloqueia/libera por etapa de diagnóstico,
  etapa não-diagnóstica fica intocada, badge vira `aguardando_validacao`
  com checklist 100% sem assinatura.
- `tests/api/test_regulatory.py::TestValidateAdvancesMacroetapa` (novo) —
  3 testes E2E: assinar em `diagnostico_preliminar` com gate liberado
  avança para `coleta_documental`; assinar fora de etapa de diagnóstico
  não altera macroetapa; assinar com checklist incompleto grava
  `validated_at` mas mantém macroetapa.

### Suite verde

- Backend, abrangência da área: `pytest tests/api/test_regulatory.py
  tests/api/test_processes.py tests/test_state_machines.py
  tests/models/test_macroetapa_gate.py tests/models/test_regulatory.py
  tests/api/test_dashboard.py tests/api/test_clients.py` → **196/196
  verde** (189 + 7 dashboard/clients).

### Cuidados respeitados

- **Sem migration, sem ADR.** Mudança puramente semântica — kwargs
  novos com default seguro, query agregada e dispatch automático após
  commit existente.
- **`Process.status` não foi tocado.** A divergência entre os dois
  eixos virou a dívida **#26** com plano explícito (eixo 3).
- **`MACROETAPA_TRANSITIONS` intacto.** O auto-advance reusa o destino
  default `nexts[0]` em vez de inventar transições novas.
- **Princípio 1 reforçado em código:** peça formal só "fecha" depois da
  assinatura humana — o badge passou a refletir esse fato; o gate passou
  a cobrar esse fato.

---

## Frente D — Cripto de segredos por usuário (28/05/2026)

ADR-014 + infraestrutura de criptografia de segredos. **Approach ADR primeiro, código depois.**
Motivado por dois cenários futuros que precisam guardar segredos de terceiros no banco:
white label de LLM (consultor traz a própria chave de IA → `User.preferences.ai.api_key`, PR LLM) e
credenciais de portal por cliente (login/senha de SEMA, banco, SICAR, INCRA → modelo `Credential`, PR 2.3).

**Decisão (ADR-014):** `cryptography.fernet.Fernet` (AES-128-CBC + HMAC-SHA256). Chave-mestra em
`CREDENTIAL_ENCRYPTION_KEY`, **separada** do `SECRET_KEY` do JWT (escopos de comprometimento isolados).
`MultiFernet` para rotação sem downtime. Alternativas rejeitadas: cofre externo (custo/lock-in/latência),
reusar `SECRET_KEY` (acopla escopos), AES sem MAC (adulteração silenciosa).

**Entregue:**
- `app/core/encryption.py` — `get_fernet()` (MultiFernet com chave atual + antiga opcional),
  `encrypt_str`/`decrypt_str` (handling de None, `InvalidToken` claro em chave errada).
- `EncryptedString` (`app/models/types.py`) — type decorator: encrypt no flush, decrypt no load.
  Código de negócio lê/escreve plaintext; banco guarda ciphertext.
- `CREDENTIAL_ENCRYPTION_KEY` obrigatória em `config.py` — valida formato Fernet no startup,
  **sem fallback inseguro** (não deriva do `SECRET_KEY`, não usa default).
- `tools/gen_encryption_key.py`, `render.yaml` (`sync: false`), `.env.example`.
- 8 testes verdes: round-trip, None, string vazia, chave errada (`InvalidToken`), rotação MultiFernet,
  e ORM (plaintext no load, ciphertext em SQL cru, None round-trip).

**Não-escopo (vira dívida #27):** nenhuma coluna real foi criptografada. A infraestrutura está pronta;
a aplicação em `Credential` e `User.preferences.ai.api_key` fica para a PR 2.3 e a PR LLM.

---

## PR 2.2 — fechar testes integrados + cobertura real (30/05/2026)

PR de fechamento (sem mudança de código de aplicação). Fecha as 2 pendências de ambiente que
sobraram quando o motor de workflow por `demand_type` (PR 2.2) foi mergeado em main (PR #21).

**Pendência (a) — testes integrados:** rodaram contra o banco dev ativo (Docker up, `db` healthy
na 55432). `test_workflow_engine.py` + `test_regulatory.py` + `test_workflows.py` = **23 passed**;
`test_legislacao_a2.py` = **19 passed**. Total **42 passed, 0 failed, 0 skipped** (2 warnings de
teardown de transação, infra). Sem failures.

**Pendência (b) — cobertura de templates:** `tools/check_template_coverage.py` rodou e regenerou
`docs/arquivo/auditorias/2026-05-28_cobertura_templates.md` com contagens reais de
`LegislationDocument` por `demand_type` (antes "não verificado"). Confirma os 8 gaps de
`WorkflowTemplate` ativo (`prad`, `sobreposicao`, `supressao`, `due_diligence`, `arrendamento`,
`condicionantes_antigas`, `misto`, `nao_identificado`) já registrados na **dívida #21** — atualizada,
não duplicada. Gaps de base regulatória (0 docs) também medidos e anexados à #21.

**Divergências do prompt (registradas, não "consertadas"):**
- `tests/api/test_legislacao.py` não existe no repo — não rodado.
- Não há marker `pytest.mark.integration` na suíte → `-m integration` deselecionava 100%; os
  arquivos foram rodados diretamente (eles *são* os integrados via Testcontainers).
- Base do PR foi `origin/main` (não `feat/dashboard-redesign-v2`, deletada após seu conteúdo —
  PR 2.2 — ter sido mergeado em main via PR #21).

---

## Corpus SEMAD em main + faxina de repositório (30/05/2026)

**Corpus SEMAD (PR #24 mergeado).** A branch `feat/corpus-semad-ingestao` (trabalho de 2026-05-20,
até então sem PR) foi integrada em `main`. Entrega: 282/283 PDFs SEMAD/GO no `knowledge_catalog`
(99,6%), 1.194 chunks, classificação Gemini 2.5 Flash + embeddings OpenAI `text-embedding-3-small`
768d, custo ~$2,10. O enum `SourceType` ganhou 4 valores (`norma_procedural` 223 / `matriz_ipe` 36 /
`manual_ipe` 10 / `gabarito_laudo` 11) — **sem migration** (`source_type` é `String(50)`).
1 PDF escaneado (Errata) ficou pendente de OCR → **dívida #28**.
Docs de estrutura atualizados: `BASE_REGULATORIA` (linha do corpus + total 22.573 → 23.767) e
`MODELO_DE_DADOS` (enumeração de `SourceType` nos 2 pontos).

**Faxina de repositório.** Limpeza de higiene git após meses de sprints: de ~23 branches remotas,
13 locais e 6 worktrees para **só `main`** em uma worktree. Apagadas 22 branches remotas mergeadas
(PR 2.2, prompt4–11, captura-*, redesign, ocr, etc.), 12 branches locais e 5 worktrees-fantasma;
`main` voltou para a worktree principal. **Nenhum trabalho real perdido** — o único pendente
(corpus SEMAD) foi encaminhado via PR #24 antes de qualquer remoção, em vez de descartado.
As 2 branches não-mergeadas (`chore/captura-redesign-e-scripts` e `feat/corpus-semad-ingestao`)
foram verificadas commit a commit antes de agir: a primeira era ponteiro órfão (sua remoção de
artefatos de redesign já estava em `main` via `acc55cf`) → apagada; a segunda era trabalho real → PR #24.

---

## Intake — campos derivados (backend) (30/05/2026)

Decisões da Isis (2026-05-28) sobre os campos do cadastro, **dividido em 2 PRs** por
escolha do Andre: **PR 1 (esta) = backend testável; PR 2 (follow-up) = frontend/UX**.

**Entregue (backend):**
- **E-mail obrigatório** no contato — `IntakeClientCreate.email` virou requerido + validador
  (`create-case`/commit com e-mail vazio/ausente → 422). Decisão Isis (não é mais opcional).
- **3 famílias de schema** em `app/schemas/intake.py` (decisão Isis): `ManualFields` (consultor
  digita; inclui `audio_url` e `possui_car`), `ExtractedFields` (IA lê dos docs — cada campo
  `{value, confidence, source_document_id}`; nirf/ccir/sigef/car/município/uf/coordenadas/áreas),
  `TriagemFields` (2 eixos independentes: `urgencia` 4 níveis + `valor_estrategico` 3 níveis).
- **2 endpoints novos** no draft: `GET /intake/drafts/{id}/extracted-fields` (preview lateral —
  valor/confiança/doc de origem/flag de divergência) e `POST /intake/drafts/{id}/reconcile`
  (Opção A: consultor escolhe origem `manual`|`extracted` por campo; grava `field_sources`
  no `form_data`, aplicado a `Client`/`Property.field_sources` no commit; AuditLog hash chain).
- **`audio_url`** aceito no payload do caso (entrada da entrevista). A transcrição (Whisper)
  é PR própria do agente de atendimento — aqui só carregamos a referência.
- **Regra `prad`** no classifier — era o 16º `DemandType` sem regra (KeyError latente se
  selecionado direto). Agora os **16 demand_types são classificáveis**.
- **`field_sources`** já existia em `Client` e `Property` (Sprints V/L) → **sem migration**.

**Testes:** `tests/api/test_intake.py` (7) + `tests/services/test_intake_classifier.py` (18
via parametrize) = **25 verdes**; 14 testes de intake pré-existentes sem regressão.

**Decisões de escopo (registradas, não "puladas"):**
- Sintoma/Dor/"Possui arquivo do CAR" **não existem no backend** (nunca foram colunas; são
  campos de UI). Sua remoção é da UI → PR 2.
- Rota é `/intake/...` (singular, convenção existente), não `/intakes/...` como no prompt.
- Docs de agente (`ATENDIMENTO`/Whisper, `EXTRATOR`, `ECOSSISTEMA` 3.2) e `FLUXOS_E2E`
  (preview lateral) descrevem UX/transcrição **ainda não construídas** → documentados no PR 2,
  quando seus assuntos existirem (regra: documento vivo = fonte de verdade, não promessa).
- Dívida **#29** aberta: critério do "Valor Estratégico — nível Baixo" (Isis não definiu).

**Pendente:** Etapa 3 (frontend) = PR 2. Validação fim-a-fim com a Isis pendente.

---

## Intake — campos derivados (frontend / Etapa 3) (30/05/2026)

PR 2 (follow-up do backend #26). Consome os endpoints do PR backend sem inventar contrato.

**Entregue (frontend):**
- **Layout 2 colunas** no `IntakeWizard` quando há rascunho: formulário multi-step à esquerda,
  `PreviewPanel` à direita.
- **`PreviewPanel.tsx`** (novo) — polling 5s de `GET /intake/drafts/{id}/extracted-fields`;
  cada campo com badge de confiança (verde >0.9 / amarelo 0.7–0.9 / vermelho <0.7) + doc de
  origem; divergência abre o modal.
- **`ReconcileModal.tsx`** (novo) — 2 valores lado a lado (digitado × IA); escolha →
  `POST /intake/drafts/{id}/reconcile`.
- **`PriorityStep.tsx`** (novo) — 2 dropdowns independentes (urgência 4 níveis + valor
  estratégico 3 níveis); nível "baixo" sem critério (dívida #29).
- **Áudio da entrevista** anexável no Step 4 (presigned upload → `audio_url`).
- E-mail obrigatório já validado na UI (mantido). Sintoma/Dor/"Possui arquivo do CAR"
  **nunca existiram** no FormState → nada a remover (confirmado).

**Verificação:** `npx tsc --noEmit` (gate strict do CLAUDE.md) **limpo, zero erros nos meus
arquivos**. `npm run build`/Vitest não rodam neste ambiente — node_modules incompleto
(`vite`/`@vitejs/plugin-react`/`@types/node`/`vitest` ausentes); condição do ambiente, não do
código. **Validação fim-a-fim com a Isis pendente.**

**Escopo deferido:** docs `ATENDIMENTO_AGENTE`/`EXTRATOR_AGENTE`/`ECOSSISTEMA_AGENTICO` seguem
adiados — descrevem transcrição Whisper / agentes **ainda não construídos** (PRs próprios).
`FLUXOS_E2E` foi atualizado porque a UX (preview + reconciliação) agora existe.

---

## LLM provider plugável por consultor (white label) (30/05/2026)

Decisão André 2026-05-28: sistema white label — consultor traz a própria chave de LLM.
Consome a infra da Frente D (ADR-014). 4 providers: anthropic/google/openai/deepseek
(chinês default = `deepseek` via `settings.LLM_CHINESE_PROVIDER`).

**Entregue:**
- **Schema** (`AiPreferences`): + `provider`/`model`/`api_key` (write-only) + `api_key_masked`/
  `api_key_set` (read-only).
- **Service** (`app/services/user_preferences.py`, novo): `save_ai_preferences` cifra a chave
  (`encrypt_str`) em `preferences['ai']['api_key_encrypted']` — **nunca plaintext**; save sem
  api_key **preserva** a existente. `public_ai` mascara a saída. `get_ai_runtime` decifra p/ o gateway.
- **API**: `PATCH /auth/me/preferences` intercepta o grupo `ai` (cifra/preserva); `GET /auth/me/full`
  retorna **mascarado**; novo `GET /auth/me/preferences/ai/available-models` (lookup hardcoded).
- **Gateway** (`ai_gateway.complete(user_preferences=...)`): usa provider/model/chave do consultor
  (formato LiteLLM); **falha de auth NÃO cai no fallback global** (erro claro). `BaseAgent.call_llm`
  resolve as prefs via `ctx.user_id`.
- **Frontend**: aba Settings > IA ganhou seção "Provedor de IA" (dropdown provider + dropdown
  modelo populado por GET available-models + input password da chave + masked/"Trocar"). Validação:
  chave obrigatória se provider setado. Tooltip ADR-014.

**Testes:** `test_user_preferences.py` (8) + `test_ai_gateway.py` (+4 user-provider) +
`test_auth.py` (+4, incl. **verificação SQL direta** de que a api_key está cifrada, não plaintext)
= **28 verdes** no conjunto. Frontend `npx tsc --noEmit` limpo.

**Governança:** API_v1, MODELO_DE_DADOS (`User.preferences['ai']`), GOVERNANCA_IA (white label),
REGISTRO_DIVIDAS (#27 parcial + **#30** auditoria de uso por chave de consultor). `ECOSSISTEMA_AGENTICO`
permanece deferido (não existe no repo; recriá-lo p/ uma seção seria documentar fora de fonte-de-verdade).

**Não-escopo:** fallback global em falha de auth (proibido); provider fora dos 4; plaintext em
qualquer lugar. **Validação fim-a-fim com o André pendente** (rodar com chave real de cada provider).

---

## PR 2.3 — Cofre de credenciais de portal por cliente (30/05/2026)

Backend (UI = follow-up, escolha do André). Consome o `EncryptedString` da Frente D em **coluna
real** — fecha a dívida **#27**.

**Entregue:**
- **Model** `Credential` (`app/models/credential.py`, tabela `credentials`): `tenant_id` +
  `client_id` (FK CASCADE) + `portal` (String(50), enum `PortalType`) + `label`/`login`/`url`/
  `notes` + **`password_encrypted` (`EncryptedString`)** + soft delete. **Primeiro uso real do
  `EncryptedString` em coluna de tabela.**
- **Schemas** (`app/schemas/credential.py`): senha write-only; resposta só com `has_password`
  (nunca plaintext).
- **API** (`app/api/v1/credentials.py`, router `/api/v1/credentials`): CRUD tenant-scoped, valida
  cliente do mesmo tenant, soft delete, AuditLog hash chain em todas as operações.
- **Migration** `c0d1e2f3a4b5`: cria `credentials` **E reunifica 2 heads do Alembic** que estavam
  divergentes (`e3d4f5g6a7b8` PROMPT_7 + `e6f7a8b9c0d1` PR 2.2, ambas de `d2c3e4f5a6b8`) — bug
  pré-existente que quebrava `alembic upgrade head`. Agora head único.

**Testes:** `tests/api/test_credentials.py` (6 verdes) — **verificação SQL direta** de que a senha
está cifrada (não plaintext), nunca volta na API, isolamento por tenant (404 cross-tenant),
preserve-on-update, soft delete.

**Descoberta importante:** durante o trabalho achei a divergência de 2 heads do Alembic (não causada
por esta PR) — corrigida via a própria migration de merge. Sem isso, `alembic upgrade head` falhava.

**Não-escopo / pendente:** UI de gerenciar credenciais no Client Hub = **PR follow-up**. Endpoint de
"revelar senha" para uso humano (hoje a senha só é lida server-side) — decisão futura. Auditoria de
**leitura** de campo sensível (item 17 da auditoria Eixo 2) segue aberta.

---

## Quitação documental — sistema agêntico no repo (30/05/2026)

Doc-only. Os docs do sistema agêntico **nunca existiram no repo** (viviam em rascunhos de chat com
alegações fabricadas). Esta PR cria a infra documental **verificada contra o código real**.

**Criado:**
- `docs/agentes/ECOSSISTEMA_AGENTICO.md` (mestre, 11 seções) — catálogo real dos 11 agentes,
  padrões transversais, chains do `orchestrator`, tools shared, roadmap real.
- `docs/agentes/{EXTRATOR,LEGISLACAO,ATENDIMENTO}_AGENTE.md` (sister files, 12 seções cada).
- `docs/MEMORIA_CHAT.md` — memória de projeto/método versionada.
- `docs/arquivo/auditorias/2026-05-30_auditoria_leitura_sensivel.md`.

**Achado da auditoria de leitura sensível:** `AuditLog` audita escrita (create/update/delete/
reconciled, hash chain SHA-256); **NÃO audita uso server-side de segredo decifrado** (api_key de
LLM decifrada em `BaseAgent` por chamada; senha de `Credential` decifrada no load mas sem consumidor
hoje, não vaza). → **dívida #33** aberta (não implementar agora). Senha de portal nunca volta em
plaintext (sem `GET /secret`).

**Divergências rascunho-de-chat × código real (matéria-prima p/ corrigir a memória do chat):**
`credential_service.py` (NÃO existe — lógica em `credentials.py`); `GET /credentials/{id}/secret`
(NÃO existe); campo da senha é `password_encrypted` (não `login_password`); dívidas #11/#15 do
prompt anterior não eram "docs de agente"/"leitura sensível" (#11=race versionamento, #15=alertas
IBAMA); `docs/agentes/` não existia. "Bloqueio docker-compose" do chat anterior era phantom de EOL
— o fix já estava mergeado (PR #30).

**Dívidas:** abertas **#32** (sister files dos 8 agentes restantes) e **#33** (audit de uso de
segredo). O deferimento histórico dos "docs de agente" (nunca numerado) fica encerrado para os 4
docs centrais. Sem renumerar dívidas existentes.

---

## Quitação da dívida #32 — 8 sister files restantes (31/05/2026)

Doc-only. Fecha a **#32**. Criados os sister files dos 8 agentes que faltavam, no molde de 12
seções do `EXTRATOR_AGENTE.md`, **cada um verificado contra o código real** (referências
`arquivo:linha`; nenhuma alegação fabricada):
`DIAGNOSTICO`, `AUDITOR_IMOVEL`, `ORCAMENTO`, `FINANCEIRO`, `REDATOR`, `ACOMPANHAMENTO`, `VIGIA`,
`MARKETING`. Os 11 agentes agora têm sister file (tabela da seção 11 do mestre atualizada).

**Correção do mestre (regra "afirmação que não bate com o código sai"):** o catálogo do
`ECOSSISTEMA_AGENTICO.md` dava `diagnostico` como `requires_review`="não"; o código força `True`
(`diagnostico.py:448` — "diagnóstico SEMPRE precisa de validação humana"). Linha 26 corrigida.

**Divergências docstring×código achadas na verificação** (registradas na seção 10 do sister file de
cada agente, não elevadas ao registro central — não destravam pipeline): `orcamento` tem duas
trilhas desalinhadas (agente `_estimate_by_rules` × serviço `proposal_generator.PRICE_TABLE`, e o
endpoint usa o serviço); `financeiro` docstring promete projeção de custos não implementada;
`marketing` tem `prompt_slugs` (4) ≠ `VALID_CONTENT_TYPES` (5); `vigia` docstring diz "6h" mas o
schedule real é 2×/dia. **Validação Isis** ficou marcada como pendente em todos (não há registro de
validação fim-a-fim por agente além do caso Romilton do pipeline OCR).

---

## Dívida #33 (parcial) — auditoria de uso da api_key do consultor (31/05/2026)

Mudança de código. Fecha a parte **com uso real** da #33. No white label (ADR-014) o consultor traz
a própria chave; ela é decifrada em `BaseAgent` a cada execução e, até agora, esse **uso** não era
auditado (só a escrita da config era).

**Implementado:**
- `app/agents/events.py:emit_ai_key_use_event()` — grava `AuditLog` `action="ai_key_used"` (hash
  chain via `register_notification_audit`), `entity_type="user"`, com `provider`/`model`/`trace_id`/
  `process_id` e a chave **mascarada** (`…últimos4`). Plaintext nunca é persistido nem logado.
  Best-effort (try/except — auditoria nunca derruba o agente, padrão do `emit_agent_event`).
- `app/agents/base.py:call_llm` — quando a chave própria do consultor é resolvida, audita o uso
  **uma vez por execução** (`self._ai_key_audited`). Caminho global (chave do sistema) não audita.
  Mascaramento feito no `base.py` (plaintext não sai dali).
- `tests/agents/test_base_agent_ai_key_audit.py` — 5 testes: audita com chave do consultor /
  nunca vaza plaintext / não audita no caminho global / dedupe por execução / falha de auditoria
  não quebra o `call_llm`.

**Verificação:** 199 testes verdes (`tests/agents` + base + `user_preferences`), exit 0, sem
regressão.

**Resta da #33 (adiado, sem uso real hoje):** auditar a senha de portal (`Credential`) — só quando
ganhar consumidor (login automatizado / endpoint de revelação). Item 1 da auditoria de leitura
sensível segue aberto; #18 (verificação da hash chain) também.

---

## Dívida #18 — verificador da hash chain de AuditLog (31/05/2026)

Mudança de código. **Fecha a #18.** A hash chain tinha só escritores (`compute_audit_hash`,
`get_last_hash_for_tenant`, `stamp_audit_hash`) — sem rotina de verificação, era cerimônia.

**Implementado:**
- `app/services/audit_hash.py` — `verify_audit_chain(db, tenant_id) -> list[BrokenLink]` + helper
  puro `_verify_chain(audits)`. Percorre a cadeia carimbada (`hash_sha256` não nulo) em ordem de
  `id` e faz duas checagens ortogonais por registro: **conteúdo** (recomputa `hash_sha256` com o
  `hash_previous` persistido) e **elo** (`hash_previous` == hash do anterior). `BrokenLink` carrega
  `audit_id`/`position`/`reason` (`content_tampered` | `broken_previous_link`)/`expected`/`found`.
- `app/api/v1/audit.py` — `GET /api/v1/admin/audit/verify-chain` (montado em `/admin`), **read-only,
  superusuário**, tenant do JWT. Devolve `{tenant_id, total_checked, ok, broken_links}`.
  `app/schemas/audit.py` com os response models. Wiring em `app/main.py`.
- Testes: `tests/services/test_audit_hash.py` (7) + `tests/api/test_audit.py` (3) = **10 verdes**
  (cadeia válida / conteúdo adulterado / linha removida / isolamento por tenant / 403 não-superuser /
  detecção ponta a ponta).

**Conexão:** fecha o item 3 da auditoria de leitura sensível (30/05) e o último gap de
auditabilidade que rimava com a #33. Restam só os itens sem uso real (senha de portal, #33 parcial).

---

## PR 2.1 — canal WhatsApp inbound a caso já aberto (31/05/2026)

Integração de canal a **caso JÁ ABERTO** (mensagens inbound **NÃO criam caso** — decisão 2026-05-28).
WhatsApp via Evolution (provider plugável; Z-API stub). E-mail inbound (Resend) **adiado** (sem plano
habilitado) → dívida **#35**. **Construído DORMENTE:** ativa só ao preencher credenciais.

**Backend:**
- `app/services/messaging/` — `WhatsAppProvider` (abstrato) + `InboundMessage`; `EvolutionProvider`
  (real, httpx, send + parse); `ZAPIProvider` (stub); `registry.get_whatsapp_provider()`.
- `app/api/v1/messaging.py` — `POST /messaging/whatsapp/webhook`: HMAC (`EVOLUTION_WEBHOOK_SECRET`),
  acha `Client` por telefone → `Process` aberto mais recente → `Message` no thread; mídia → `Document`
  (`source="whatsapp"`); sem caso → thread órfão + alerta `inbound_orphan`; sem Client → ignora; 401 se
  HMAC inválido; 200 caso contrário (provider faz retry em 5xx).
- `CommunicationThread.provider` + `provider_account_id` (migration `pr21_wa_provider`, reversível;
  expostos no schema Pydantic de resposta).
- Config: `WHATSAPP_PROVIDER`, `EVOLUTION_API_URL/KEY/WEBHOOK_SECRET`, `ZAPI_*` (placeholder),
  `EMAIL_INBOUND_PROVIDER`, `RESEND_INBOUND_WEBHOOK_SECRET`. Propagadas em docker-compose (api/worker),
  `render.yaml` (sync:false) e `.env.example`.

**Infra:** serviço `evolution` (atendai/evolution-api:v2.1.1) no docker-compose sob profile `whatsapp`
(dormente; sobe com `docker compose --profile whatsapp up -d evolution`).

**Testes:** `tests/services/test_evolution_provider.py` (8) + `tests/api/test_messaging_webhook.py` (5)
= **13 verdes** (parse texto/mídia, send, erros; thread de caso aberto, mídia→Document, remetente
desconhecido, thread órfão+alerta, HMAC 401).

**Pré-requisitos pra ativar (não-código):** gerar API key da Evolution, parear o número (QR), criar o
database `evolution` no Postgres, preencher `EVOLUTION_API_URL/KEY` no `.env`. **Dívida #35** (Z-API +
e-mail inbound).

---

## Correção dos 2 críticos da Isis — upload + persistência (31/05/2026)

Auditoria `docs/arquivo/auditorias/2026-05-31_uploads_isis.md`. PR único `fix/intake-uploads-criticos-isis`.

**#2 (persistência — buraco de fluxo na finalização):** o wizard finalizava por `/intake/create-case`
sem `draft_id`; o `/commit` (que migra os docs) nunca era chamado → docs do Step 4 ficavam com
`process_id=NULL`, invisíveis na aba Documentos. **Fix:** `IntakeCreateCaseRequest.draft_id` (opcional)
+ migração dentro do `create_case` (mesma transação): bulk dos `Document`s `intake_draft_id==draft AND
process_id IS NULL AND deleted_at IS NULL` → `process/client/property`, `auto_link_document` no
checklist, `draft.state=card_criado`, `AuditLog action="draft_migrated"`. 404 (inexistente/outro
tenant), 409 (já finalizado), no-op sem docs. `/commit` mantido (deprecated no docstring). Frontend:
`buildPayload` envia `draft_id`; `handleSubmit` trata 409.

**#1 (upload em massa — transporte/UX):** `DraftDocumentUploader` reescrito — pool de 4 simultâneos
(antes loop sequencial), retry 3× com backoff 1/2/4s nas 3 etapas (presign/PUT/confirm) distinguindo
retryável (timeout/5xx/408/429) de 4xx, timeout backend 20s→30s, **botão remover sempre visível**
(removido o guard por `ocr_status`), feedback por item + "tentar novamente" individual. Visual migrado
para tokens do design system (0 ocorrências de `slate-`/`bg-white/`/`border-white/`).

**Fase 6 (DELETE doc de draft):** no-op — `delete_document` já é soft-delete por id+tenant, sem guard
de `process_id`.

**Testes:** `tests/api/test_intake_draft_migration.py` (6) + `frontend/.../DraftDocumentUploader.test.tsx`
(5). Backend 6/6; frontend vitest 36/36 (31 pré-existentes + 5); `npm run build` e `tsc --noEmit` verdes.

---

## PR I — padronização visual do Intake ao design system (31/05/2026)

Mudança **puramente visual** (zero alteração de lógica/fluxo). O wizard de intake — incluindo a
superfície de leitura IA (`PreviewPanel` de extração em tempo real + `ReconcileModal` de reconciliação
manual×IA) — usava tema **escuro** próprio (gradiente `slate-900 → emerald-950`, glassmorphism
`bg-white/5`/`border-white/10`, verde `emerald-500`), destoando do padrão **claro** do Dashboard
(constatado na auditoria `docs/arquivo/auditorias/2026-05-31_ui_credenciais_intake.md`, Frente C).

**O que mudou:** os 4 componentes do wizard (`IntakeWizard.tsx`, `PreviewPanel.tsx`, `ReconcileModal.tsx`,
`PriorityStep.tsx`) passam a consumir os tokens do design system (`bg-background`, `bg-card`,
`border-border`, `text-foreground`, `text-muted-foreground`, `bg-primary`/`text-primary-foreground` =
Verde Premium Regente `142 76% 36%`). Glassmorphism e família `slate-*` removidos. Os badges de
confiança do `PreviewPanel` **preservam a semântica** verde>0.9 / amarelo 0.7–0.9 / vermelho<0.7,
adaptados para fundo claro (não há token semântico `success`/`warning` no design system — só
`destructive`, usado nos erros).

**Fora de escopo (pendência):** `DiagnosisPanel.tsx` e `DraftDocumentUploader.tsx` (renderizados dentro
do wizard) ainda carregam tema escuro — não estavam no escopo declarado desta PR.

**Verificação:** `tsc --noEmit` limpo + `npm run build` verde. Funcionalidade inalterada.

---

## UI das credenciais de portal no Cliente Hub (31/05/2026)

Frontend follow-up do PR 2.3. Consome o backend real de `Credential` sem inventar campos.

**Entregue:**
- Aba **Credenciais** adicionada ao `ClientHub`, ao lado de Documentos/Histórico.
- `frontend/src/components/Clients/CredentialsTab/` novo: listagem por
  `GET /api/v1/credentials?client_id=X`, estados de loading/erro/vazio, badge de portal,
  badge `Senha protegida` quando `has_password=true`, link externo de `url`, ações editar/excluir.
- `CredentialModal` reutilizado para create/edit. Create envia
  `{client_id, portal, label, login, password, url, notes}`. Edit envia PATCH parcial; se a senha
  fica vazia, o campo `password` é omitido para preservar a senha existente.
- Confirmação de exclusão chama `DELETE /api/v1/credentials/{id}` e atualiza a lista.

**Contrato real confirmado:** `CredentialCreate` tem `client_id`, `portal`, `label`, `login`,
`password`, `url`, `notes`. O campo do backend é `login`, não `login_username`. Não existe
`valid_until` no model/schema/resposta atual, então a UI não implementa alerta de vencimento falso.
Dívida #36 aberta para validade/alerta proativo quando o produto decidir modelar isso.

**Verificação:** `npm run test -- CredentialsTab` verde (4/4) e `npm run build` verde. A primeira
execução falhou por `spawn EPERM` do esbuild no sandbox; rerodado com permissão elevada. Docker/SQL
manual não foram validados neste ambiente: `docker ps` sem acesso ao pipe do Docker Desktop e
`docker compose ps` bloqueado por `EVOLUTION_API_KEY` ausente.

---

## Evolution fora do boot — `docker compose up` destravado (01/06/2026)

Ops/infra (não-IA), registrado aqui por ser o pulso que destravou a validação E2E que os
agentes de IA dependiam para subir o stack.

**Problema:** `docker compose up -d` abortava antes de subir qualquer serviço. A definição do
serviço `evolution` no compose tinha `AUTHENTICATION_API_KEY: "${EVOLUTION_API_KEY:?...}"`; o
Compose interpola o arquivo inteiro no `up` (antes de filtrar profiles), então a env ausente
derrubava o boot do core — mesmo com a Evolution dormente sob o profile `whatsapp`.

**Decisão (André, 01/06):** tirar o Evolution do caminho agora; o canal WhatsApp volta quando o
core estiver de pé.

**Feito:**
- `docker-compose.yml`: removidos o serviço `evolution`, o profile `whatsapp` e o volume
  `evolution_data` (comentário no lugar apontando como reativar). As envs `EVOLUTION_*` em
  `api`/`worker` seguem com default vazio (`:-`), inofensivas.
- `app/api/v1/messaging.py`: webhook `/whatsapp/webhook` responde **503 "WhatsApp não configurado"**
  quando faltam `EVOLUTION_API_URL`/`EVOLUTION_API_KEY` — nunca quebra o boot.
- **Não tocado:** provider (`app/services/messaging/`), stub Z-API, contrato do webhook.

**Verificação:** `docker compose up -d db redis minio api worker` → db/redis/minio healthy, api/worker
up; `curl http://localhost:8000/health` → `{"status":"ok",...}` HTTP 200. `app.main` importa limpo.

**Dívida:** #37 (reintegrar Evolution ao compose/boot quando o WhatsApp for reativado). Reativação
documentada em `docs/operacao/RUNBOOK_OPS.md`.

---

## Mergulho fluxo agêntico — diagnóstico por execução + 3 P0 (01/06/2026)

Diagnóstico do fluxo intake→agentes RODANDO (não leitura). Doc completo:
`docs/arquivo/auditorias/2026-06-01_mergulho_fluxo_agentico.md`.

**Reproduzido ponta a ponta (sistema de pé, AI_ENABLED=true):**
- `/intake/classify` → demand_type=misto (LLM) ✅
- draft → upload MinIO → Document 49 (intake_draft_id=11, process_id=NULL) ✅
- `/import` → ocr_then_extract: OCR pypdf 345 chars → extrator com document_id=49
  → **12 campos** (matrícula 12.345, Romilton, 250.0 ha, MS) ✅
- `create-case` → process 30; doc migrado (process_id=30); checklist auto-link
  (matricula→received); **só `atendimento` dispara** (AIJob 121) ⚠️
- chain `diagnostico_completo`: extrator SKIP → auditor ok → **legislacao Timeout
  (bloqueante) → chain parou 3/4 → diagnostico NÃO rodou → 0 diagnoses** ❌

**Causa raiz da "entrega de diagnóstico não acontece":** soma de (a) create-case
não auto-dispara a chain, (b) extrator pulava na chain sem document_id, (c)
legislacao bloqueante e flaky aborta a chain antes do diagnostico.

**Corrigidos neste PR (revalidados rodando, antes/depois):**
1. **CORS mascara 500** — handler global reanexa CORS+request_id na resposta 500.
   Antes: 500 sem ACAO (navegador via "CORS"). Depois: 500 com
   `access-control-allow-origin` + `{detail,request_id}`. (`app/main.py`)
2. **Path do WS** — router montado também sob `/api/v1`. Antes `/api/v1/ws`=403;
   depois `/ws` e `/api/v1/ws` conectam. (`app/main.py`)
3. **Gap do extrator** — `extrator.execute()` resolve os docs OCR do processo
   quando recebe só `process_id`. Antes: skip (0 campos). Depois:
   resolved_from_process=30, 9 campos. (`app/agents/extrator.py`)

**Dívidas abertas:** #38 (chain aborta na legislacao — ALTA), #39 (robustez
legislacao), #40 (2 SKILL.md inválidos), #41 (auto-trigger pós-case — decisão
produto), #42 (bucket MinIO presigned), #43 (Error Boundary global).

**Infra p/ André:** Cloudflare WebSockets=ON; setar VITE_WS_URL=
wss://api.regenteambiental.com.br (sem /api/v1). CORS de prod já OK — o "threads
CORS" é 500 mascarado; pegar request_id no log do regente-api.

**Pergunta em aberto (não reproduzida):** gatilho exato do Error Boundary
(precisa navegador) e qual 500 específico o /threads dá em produção.

---

## PR #38 — destravar `diagnostico_completo` quando legislação falha (01/06/2026)

Mudança de orquestração, validada com sistema rodando. Fecha a dívida **#38**.

**Medição da causa:** no `process_id=30`/`tenant_id=2`, a busca local da legislação não era o gargalo:
RAG+embedding de query levou ~4,5s e retornou 0 chunks; contexto por metadados levou ~0,5s e ficou
vazio. O timeout medido ocorreu na chamada LLM do `LegislacaoAgent` para
`gemini/gemini-2.5-flash` via `ai_gateway.complete` (`AI_TIMEOUT_SECONDS=30.0`), com erro
`litellm.Timeout: Connection timed out after None seconds`.

**Correção:** `app/agents/orchestrator.py` ganhou exceção escopada por chain:
- em `diagnostico_completo`, `legislacao` é insumo intermediário e não bloqueia por
  `requires_review=True`;
- falha/timeout de `legislacao` nessa chain também não aborta a entrega: o erro fica em
  `ctx.chain_data["legislacao"]` e o `diagnostico` roda com contexto parcial;
- em chains onde `legislacao` é produto final (`analise_regulatoria`/`enquadramento_regulatorio`),
  o comportamento segue bloqueante.

Também foi ajustado `BaseAgent.run()` para registrar o nome da exceção quando `str(exc)` vem vazio
(ex.: `AIGatewayError`), evitando erro vazio no `AgentResult`.

**Revalidação rodando:**
- Cenário com timeout: `extrator` ok → `auditor_imovel` ok → `legislacao` failed (~33,6s, AIJob 134)
  → `diagnostico` **rodou** (AIJob 135) e entregou 3 itens em `passivos_identificados`.
- Cenário sem timeout, mas com revisão: `legislacao` success + `requires_review=True` (AIJob 138) →
  `diagnostico` **rodou** (AIJob 139) e entregou 3 itens.

**Docs/governança:** nova auditoria
`docs/arquivo/auditorias/2026-06-01_chain_legislacao.md`; ADR-011 atualizado; `ECOSSISTEMA_AGENTICO`,
`LEGISLACAO_AGENTE`, `ESTADO_ATUAL`, `REGISTRO_DIVIDAS` e `MEMORIA_CHAT` atualizados.

**Permanece:** #39 (robustez própria da legislação: retry/parsing/timeout), #40 (2 `SKILL.md`
inválidos), #41 (auto-trigger pós-case, decisão produto).

---

## Front-matter dos 2 SKILL.md — dívida #40 fechada (01/06/2026)

`fix/skills-frontmatter-40`. Os 2 únicos SKILL.md formais tinham front-matter
inválido e `discover_skills` os **ignorava silenciosamente** (só WARNING) — os
agentes rodavam sem a skill. Corrigido **só o front-matter** (corpo de domínio
intacto):
- `diagnostico/situacao_ambiental_imovel_rural`: `+agent: diagnostico`, `name`
  com prefixo, `applies_to` lista→`{uf: [GO, MS, MT]}`, `version` string.
- `auditor_imovel/analise_divergencias_documentais`: `name` com prefixo,
  `applies_to` string→`{doc_types: []}`, string descritiva→`description`.

**Provado rodando** (container `api`): `discover_skills()` lista as 2 **sem
warning**; `load_skill()` retorna `SkillContent`; `DiagnosticoAgent.
_compose_system_with_skills()` com `ctx.metadata={"uf":"MS"}` **injeta** o corpo
(~55 KB) entre `<!-- skills:start -->`/`<!-- skills:end -->` (prompt 45→55.504
chars). Controle negativo: **sem** `uf` não injeta. 26 testes de skills verdes.

**Gap novo (dívida #44, ligada à #38):** a chain não deriva `uf` do
imóvel/processo; a skill do diagnóstico só casa quando o caller põe `uf` no
`metadata`. Resolver a propagação é escopo da #38, não deste PR.

**Limpeza:** docx Word duplicados movidos de `docs/skills/` para
`docs/_archive/skills-fontes-word/` (fonte de verdade = SKILL.md).

## ADR-020 — verificação espacial derivada, não armazenada (30/06/2026)

Diagnóstico read-only do caso 13 (property 10): 11 `VERIFICACAO_ESPACIAL_PENDENTE`
idênticos sobreviveram a tudo. Raiz: placeholder informativo (`geom IS NULL` →
"análise espacial não rodou") era **armazenado** como `RegulatoryIssue` e
re-emitido a cada E2/E4. Decisão do André: estado derivado calcula-se na leitura,
nunca vira linha (Princípio 11).

**Mudanças (branch `fix/derivar-verificacao-espacial-d1`):**
- `property_audit.py`: removido o ramo `geom is None` (auditor para de emitir).
- Backend: `GET /properties/{id}/diagnosis-notes` deriva a nota
  (`source="derived"`, `acionavel=false`) quando `geom IS NULL`.
- Frontend `DiagnosisTab`: achados (AlertaCard) ≠ notas (linha discreta, sem botões).
- Catálogo: `VERIFICACAO_ESPACIAL_PENDENTE` aposentado (mantido p/ FK legada).
- Anti-regressão: `audit_property`/`auditor_imovel` NÃO emitem; endpoint deriva.

**Validação:** 201 backend + 76 frontend verdes; tsc/eslint ok. Gatilho D1: quando
geom for populado, a seção emite achados ESPACIAIS REAIS (persistidos). Constraint
UNIQUE (3º caso dedupe-sem-constraint) → dívida #48. Limpeza de prod é Parte 2
(pós-deploy, dry-run aprovado antes). Ver `docs/adr/020-verificacao-espacial-derivada.md`.

## Rota Regulatória (E5, Sprint 2) — materializar o caminho regulatório (30/06/2026)

Diagnóstico read-only mostrou que as `etapas` da `LegislacaoAgent` eram efêmeras
(viviam só no JSON do `AIJob`, sem tabela/tela, perdidas ao recarregar). Este
sprint materializa a Rota como **snapshot editável e assinável**.

**Mudanças (branch `feat/rota-e5-sprint2`, ADR-021):**
- Entidades `Rota` + `RotaPasso` (`app/models/rota.py`) + migration `d1e2f3a4b5c6`
  — `dedupe_key` + UNIQUE parcial desde o commit 1 (dívida #48). 4º caso a nascer
  com a constraint correta.
- `rota_materializer.py`: roda a legislação e reconstrói o `Etapa` **TIPADO**
  (`sources`+`prazo_fonte`) do dual-emit — NUNCA o bruto top-level (que quebra o
  schema strict). Reconciliação aditiva/não-destrutiva (padrão ADR-017): preserva
  edição/ordem/classificação/manual; rota validada + diff → `desatualizada`.
- Endpoints (`app/api/v1/rotas.py`): gerar/reordenar/editar/add-manual/validar/
  fechar. Validar exige classificação (Ficha §8.1); fechar exige todos validados e
  grava `AuditLog` com **hash chain SHA-256** — 1º uso real da cadeia (dívida #18).
- UI (`RotaTab.tsx`): na E5 a aba Ações vira a Rota (não é 7ª aba). Drag-reorder via
  `framer-motion <Reorder>` (sem `@dnd-kit`); badge de fonte honesto; toggle
  faturável/direção; validar passo a passo; "Fechar rota" gateado.

**Decisões travadas (André):** demand_type-driven (não religar a chain agora); ler o
típado; @dnd-kit rejeitado; "nenhum passo sem norma" enforça na validação; dedupe é
higiene não oráculo. **Validação:** 18 testes novos verdes (materializador + API);
`tsc --noEmit` limpo; migration round-trip up/down no vereda_dev. **Follow-ons
nomeados:** dívidas #49–#53 (doc em Saídas, religar auditor→legislacao, gatilho ação→
rota, auto-RAG de fundamento, aprendizado das reordenações). Ver
`docs/adr/021-rota-e5-snapshot-editavel.md`.

## Selo de 3 estados + automatismo de ação (Sprint 3 — 03/07/2026)

Ficha 07 §3.4/§9: três estados do dado (VALIDADO · CORRETO, PENDENTE DE
OFICIALIZAÇÃO · NÃO VALIDADO) e o automatismo — ao selar "pendente de
oficialização", o sistema cria sozinho a ação "Atualização de arquivos oficiais"
(proposta; o consultor edita/remove). Determinístico (sem LLM), mas fecha o loop
IA→humano: campo extraído pela IA ganha adjudicação explícita do consultor.

**Mudanças (branch `feat/selo-oficializacao-sprint3`, ADR-022):**
- Selo = vocabulário de `field_sources` (SEM enum de banco novo):
  `human_validated` (existia) · `pendente_oficializacao` (novo) · não-validado =
  default por construção (raw|ai_extracted|derived_matricula|ausente).
- `matriculas.field_sources` (migration `f2a4c6e8b0d2` + backfill legado) fecha o
  ponto cego; consolidação aposenta o fallback `old is not None` — proveniência
  explícita nas 3 entidades; `pendente_oficializacao` também protege contra
  sobrescrita silenciosa (vira reconciliação).
- `generate_acao_oficializacao` (acao_generator): origem=`oficializacao`
  (migration `a3b5d7f9c1e3`), dedupe por DESTINO
  `p{pid}:ofic:{sha1(entity|entity_id|field)[:24]}` — oscilação não duplica,
  dispensada não recria, selo→VALIDADO não remove a ação.
- De passagem: gap `seen_this_run` em `generate_acoes_from_divergencias` corrigido
  (colisão intra-run estourava a UNIQUE e derrubava a consolidação) + regressão.
- `POST /processes/{pid}/field-selo`: IDOR guard (tenant + vínculo ao processo →
  404), selo perene na entidade, AuditLog hash chain, gatilho EXCLUSIVO do
  automatismo (Hub grava selo mas não dispara). Dossiê estendido: selos por campo,
  campos-chave da matrícula (SIGEF/INCRA-SNCR/NIRF) e áreas documental × gráfica ×
  total derivada.
- UI `ProcessDossier`: campos-chave copiáveis (clipboard+toast), seletor de selo
  com rótulos COMPLETOS ("Correto, pendente de oficialização" — sem abreviar),
  áreas com "—" honesto quando falta fonte. Selo nunca trava avanço.

**Decisões travadas (André):** vocabulário de field_sources; 1 ação por campo;
Hub não dispara; dispensada não recria; #17 segue fechada e #21 (WorkflowTemplate)
renumerada para #54. **Validação:** testes de oscilação/dispensada/hub×endpoint/
IDOR/regressão seen_this_run verdes; suíte frontend 80/80; rótulo completo coberto
por teste de componente. Ver `docs/adr/022-selo-oficializacao-field-sources.md`.

---

## Sprint 4 — Granularidade matrícula×imóvel + integridade da consolidação (04/07/2026)

### Motivação (caso 13 como espécime)

Dois "CCIRs" completos e conflitantes na matrícula 2923 passaram sem divergência
(bucket único por tipo na matriz colapsava documentos) e a consolidação gravou o
vencedor por menor id — um registro frankenstein colhido da legenda de
confrontações de uma planta topográfica mal-classificada. A certidão de embargo
(classificada `sigef`) criou a "matrícula" 492262. E a soma cega de matrículas de
duas fazendas distintas alimentava os prompts de diagnóstico/legislação com 1.713 ha
onde o imóvel real tem ~1.010 ha.

### O que foi feito (toca IA)

- **Contexto dos prompts com honestidade de área:** `DiagnosticoAgent._load_process_data`
  e `LegislacaoAgent._load_process_context` passam `matriculas_contiguas` +
  `area_total_nota` (ressalva textual) — o LLM não dimensiona porte/passivo sobre
  soma possivelmente fictícia sem saber disso. Nenhum prompt-template alterado
  (entra pelo dict serializado, mesmo padrão da matriz de inconsistências).
- **Matriz de inconsistências multi-documento:** sources por (doc_type, document_id)
  (`ccir#228` × `ccir#231`) em `_group_sources` e na coleta de áreas por matrícula —
  divergência entre docs do MESMO tipo passa a ser acusada e marca o staging
  (`divergente_transcricao`/`fundo`), acionando o gate de decisão do consultor.
- **Consolidação nunca desempata conteúdo:** conflito real entre docs distintos
  volta ao consultor e vira Ação (`divergencias_devolvidas` no resultado);
  `_pick_winner` restrito a proveniência. Guard fantasma: só matricula/ccir/itr/car
  criam Matricula.
- **Sem mudança de gateway/custos** — sprint determinístico (zero chamadas LLM novas).

**Decisões travadas (André):** tri-state no Property (grupos por matrícula = #55);
declarar-e-avisar (nunca automação); soma anotada nunca suprimida; contrato
intocado; caso 13/2923 em prod gated na Isis. **Validação:** matriz 13/13 (4 novos
multi-doc), suíte de consolidação/selo/staging + `test_sprint4_contiguidade.py`
(15 novos). Ver `docs/adr/023-matriculas-contiguas-integridade-consolidacao.md`.

---

## Sprint 6 — Limpeza das abas do workspace (2026-07-13)

Sprint de superfície (UI), não de IA — registrado no pulso pelo toque na **aba IA**.

### O que toca IA

- **Aba IA do workspace OCULTADA** (flag `isTabVisible=false`, ver
  `frontend/src/lib/tabFlags.ts` + ADR-024). A aba (`AIPanel`) estava quebrada — não
  dispara a cadeia de agentes da etapa. Ocultar resolve a dor imediata (tela morta na
  frente do consultor) sem apagar nada: componente/rota/dados seguem vivos por baixo.
  O disparo real da cadeia continua pelo `WorkspaceRightPanel` ("Rodar agentes"), que
  **não** foi tocado. Conserto do painel = **dívida #64** (religar o flag depois).
- **Sem mudança de gateway/agentes/prompts/custos** — nenhuma chamada LLM nova; a
  orquestração de agentes é idêntica.

---

## Linguagem de consultor no feed + rótulos de agente (2026-07-13)

Sprint de apresentação — toca IA nos rótulos e na tradução de eventos de agente.

### O que toca IA

- **Rótulos de produto dos agentes — fonte única.** `@/types/agent.ts::AGENT_LABELS`
  passa a ser a única fonte usada em toda superfície (feed, `AIPanel`, `AgentsPage`,
  `WorkspaceRightPanel`, `ClientHub`). Rótulos revistos p/ o papel do agente:
  `vigia`→"Vigia normativo", `auditor_imovel`→"Auditoria do imóvel",
  `legislacao`→"Análise legal", `extrator`→"Leitura de documentos",
  `redator`→"Redator", `financeiro`→"Análise financeira" + `orchestrator`→"Equipe
  de agentes". Nunca mais o identificador interno na tela.
- **Tradução de eventos de agente** (`agent.{nome}.{status}`) → frase de consultor
  em `lib/activityLabels.ts` (`translateActivity`). `completed`/`failed`/`started`
  viram frases humanas; o JSON do payload (trace_id, confidence, duration_ms) vai
  só no tooltip técnico, nunca na tela. Fallback obrigatório p/ event type novo.
- **Sem mudança de gateway/cadeia/prompts/custos.** A orquestração dos agentes é
  idêntica; nenhuma chamada LLM nova. O card "Leitura da IA" do kanban
  (`/kanban-insights`) é determinístico (COUNT/GROUP BY) — corrigido só o cache
  (24h→5min) p/ refletir o sistema. Ver ADR-025.

---

## S5-B — Proposta e contrato nos moldes Mirante (2026-07-19)

Sprint de peça comercial. Toca IA pela DECISÃO de tirar a geração de proposta/
contrato do caminho LLM (`RedatorAgent`, templates `proposta`/`contrato`) e fixá-la
numa fonte DETERMINÍSTICA — as validações de consistência precisam bloquear com
certeza, e um LLM não garante que "a soma das parcelas fecha".

### O que toca IA

- **RedatorAgent NÃO é a fonte da proposta/contrato.** Confirmado o que o log de
  aviso do agente já media (`redator.py`: "template com fluxo dedicado"): a peça
  nasce de `app/services/mirante_documents.py` (determinístico, `build_proposta` /
  `build_contrato`), não do LLM. Os paths `proposta`/`contrato` do RedatorAgent
  seguem como caminho paralelo a aposentar (dívida #68).
- **Proposta nasce da Rota (S5-A) → contrato nasce da proposta ACEITA.** Seção 3 da
  proposta = passos da Rota, rastreáveis via `rota_passo_id`; cláusula 1ª do
  contrato espelha o escopo aceito (mesmo `rota_passo_id`); cláusula 2ª os valores.
- **3 validações determinísticas BLOQUEIAM (não é conselho de IA):** soma serviços
  == total; soma parcelas == bloco; matrículas VIGENTES (ADR-027). Guard de
  placeholder impede `{{...}}`/`[12]` no documento final.
- **Perfil emissor do tenant** (`tenant.settings["issuer"]`) — nunca mais CNPJ/conta
  hardcoded; perfil incompleto = geração bloqueada nomeando o que falta.
- **Sem mudança de gateway/custos** — sprint determinístico, zero chamada LLM nova.
  A peça gerada é RASCUNHO (`needs_human_validation=True`) — IA propõe, humano
  decide; assinatura fica no S5-C. Ver ADR-029 e dívida #68.

---

## S5-C — Assinatura manual + Saídas converge + Comercial oculta (2026-07-19)

Fechamento da Ficha 07. Sprint de fluxo/superfície — toca IA no que o consultor
VALIDA (o rascunho gerado pela IA vira peça assinada) e na convergência das Saídas.

### O que toca IA

- **A peça da IA fecha o ciclo com o humano (Princípio 1 completo).** O contrato que
  o S5-B gera é RASCUNHO; o S5-C dá o caminho de aprovação/assinatura: rascunho →
  ENVIADO → ASSINADO. A IA propôs, o consultor decidiu e assinou — o gate E7
  (`has_contract_signed`) enfim fecha, e a E7 mostra CONCLUÍDA (`compute_macroetapa_state`).
- **Saídas converge as peças da IA.** A aba Saídas (StageOutputs de proposta/minuta,
  gerados no S5-B) ganhou download do PDF e atalho ao contrato. As saídas que os
  geradores registram num só lugar, com estado/validação/data.
- **Comercial oculta** (isTabVisible=false): sem perda de capacidade — as ações da
  proposta (incl. renegociação) vivem no ProposalEditor; "Gerar Contrato" passou a
  chamar o gerador Mirante (S5-B), registrando a minuta em Saídas.
- **Sem mudança de gateway/cadeia/prompts/custos** — assinatura MANUAL (MVP), zero
  chamada LLM nova. Assinatura eletrônica externa = dívida #69. Ver ADR-030.

## Fonte única de requisitos documentais + Ficha 08 (20/07/2026)

`fix/fonte-unica-requisitos-documentais` · ADR-031 · dívidas #70–#77

### O gatilho

O consultor viu "4 documentos pendentes" e "Matrícula do imóvel ausente" num caso
onde a certidão de inteiro teor tinha sido enviada. Mesmo sintoma que o forense
caso Isis já havia corrigido no emissor `MISSING_MATRICULA` — reapareceu em outra
superfície.

### O que a auditoria achou (processo 15, prod)

Não era um bug: era a ausência de um conceito. **Nove** pontos do código
respondiam "o requisito documental está satisfeito?", cada um com fonte da verdade
própria. Três discordavam sobre a mesma matrícula no mesmo instante — checklist
dizia SATISFEITO, dossiê dizia AUSENTE (severity `error`), e a verdade era
RECEBIDO, EM PROCESSAMENTO (staging com `numero_matricula` = "6.776" e "4698",
zero `Matricula` materializada).

Achados que o relato original não continha:

- os "4 pendentes" **não** incluíam matrícula — a acusação vinha de outra tela
- **36 dos 42 documentos com `document_type = NULL`** → nunca vinculados
- `checklist_item_id` **NULL em 100%** dos documentos (vínculo só de um lado)
- `doc_proprietario` pendente **com a CNH anexada** (`cpf_cnpj` ≠ `doc_pessoal`)
- o teste do forense passa `documents=[]` nas duas asserções — o caso caía no
  buraco entre elas
- uma **terceira** cópia do laço de contagem, que a auditoria não tinha achado,
  alimentando justamente o gate que TRAVA o avanço da macroetapa

### O que toca IA

- **Sprint determinístico — zero chamada LLM nova.** A fonte única é regra pura
  sobre dados já extraídos; não há custo de gateway nesta rodada.
- **A extração continua sendo o sinal de "o sistema leu".** `requisito_documental`
  lê `ExtractedFieldStaging` (o que o extrator produziu), não o texto bruto do
  OCR — presença de campo é o que distingue "recebido" de "recebido e lido".
- **Presença do documento ≠ consolidação do dado.** Colapsar os dois eixos foi a
  causa raiz. A consolidação (Ficha 05) segue sendo cobrada, agora com o nome
  certo: `MATRICULA_EM_PROCESSAMENTO` (severity `info`), não "ausente" (`error`).
- **Ficha 08 versionada** (`docs/fichas/FICHA_08_BASE_DADOS_CONFERENCIA.md`) — a
  lista dos 6 obrigatórios e as regras de completude passam a ser fonte no repo.
  Licença Ambiental fica EM ABERTO (§6.4): são 6, não 7.
- **P12 aplicado a requisitos:** a frase da tela vem pronta do backend
  (`detalhe`). A UI não reescreve a semântica — foi a redação duplicada em cada
  superfície que produziu as três respostas divergentes.

### Suíte

Backend verde (piso 1221 + 30 testes novos). `tsc`, ESLint e build do frontend
limpos. Vitest local tem 9 workers que não iniciam por `ERR_REQUIRE_ESM` numa
dependência transitiva do jsdom — **verificado idêntico na `main`**, não
introduzido aqui, e o CI não roda vitest. Registrado com fix proposto.
