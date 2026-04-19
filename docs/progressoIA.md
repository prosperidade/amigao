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

## Backlog IA (proximas sprints)

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
