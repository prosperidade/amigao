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
