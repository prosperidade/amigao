# Resumo — sessão de 2026-04-23

**Destinatário:** brainstorm arquitetural externo (outro chat / outra pessoa).
**Commits da sessão (em ordem):** `3b27516` → `c33c4ad` → `1e6fdcc` → `bda2123` → `c009bcf`.
**Duração estimada:** ~1 dia de trabalho.

---

## 1. O que mudou — estado antes × depois

| Eixo | Antes (manhã de 23/04) | Depois (final da sessão) |
|---|---|---|
| **Kanban legado** | `/processes` tinha 9 colunas + Quadro novo em paralelo | Removido; rota vai direto ao Quadro de Ações |
| **UI minor** | "Processos", "Nova Demanda", textos técnicos em inglês | "Quadro de ações", "Novo Caso", PT-BR acentuado |
| **Budget IA** | `AI_MAX_COST_PER_JOB_USD` e `AI_HOURLY_COST_LIMIT_USD` somente | + `AI_BUDGET_USD_MONTHLY_PER_TENANT_DEFAULT` + override por tenant (`Tenant.ai_monthly_budget_usd`) + endpoint `GET /agents/budget` + card na `AgentsPage` |
| **Gemini default p/ legislação** | Declarado em Sprint O mas **100% do custo real em gpt-4o-mini** (chave não populada) | Health-check no boot loga WARNING quando flag ativa sem chave; `.env.example` documenta formato |
| **Cost guard por job** | Constante `AI_MAX_COST_PER_JOB_USD=0.10` declarada mas **não enforçada** | Enforçada em `ai_gateway.complete()` com fail-fast; `AIGatewayError` preserva cost/tokens/model para auditoria; `BaseAgent._fail_job` persiste esses campos no AIJob; override per-call via `max_cost_override_usd` |
| **`search_legislation(demand_type=...)`** | Argumento aceito mas **ignorado na query** | Filtro JSONB aplicado; docs com `demand_types=NULL` ficam fora quando há filtro (prioriza especializado) |
| **`Document.extracted_text`** | Campo lido em `ExtratorAgent` mas **não existia no schema** | Migration adicionada (aditiva); Extrator lê do banco quando metadata omite `text` e cacheia quando vem (evita re-OCR) |
| **MemPalace (pacote PyPI)** | Dependência instalada, chamado em cada execução de agente | **Removido** por supply-chain red flags; `app/agents/memory.py` vira stub no-op preservando assinaturas |
| **Legislação (corpus)** | `legislation_documents` vazia; agente alucinava | **23 diplomas / 1.67M tokens** ingeridos (13 estaduais GO + 10 federais) |
| **Gemini context window** | Documentado internamente como 2M | Corrigido: **Flash 2.0 = 1M**; Pro 1.5 = 2M. Implementado roteamento dinâmico Flash → Pro com threshold 800K tokens |
| **Docker-compose** | `mempalace_data` volume + `python -m mempalace init` no entrypoint | Removidos |
| **Tests** | 28 failed / 137 passed | **23 failed / 159 passed** (18 novos passando, 4 pré-existentes agora determinísticos com stub, 0 regressão) |

---

## 2. Sprints executados

### Sprint R — Orçamento mensal de IA por tenant
Pré-existente desta sessão. Terceira camada de guardrails de custo (por job + por hora + por mês/tenant). Endpoint `GET /agents/budget` retorna `used_usd`, `limit_usd`, `pct`, `unlimited`, `alert` (≥80%), `period_end`.

### Sprint -1 — Faxina
Quatro dívidas que invalidavam decisões arquiteturais:
- **A.** Health-check Gemini no boot + testes de fallback chain (4 testes)
- **B.** Cost guard per-job fail-fast + `AIGatewayError` com métricas (5 testes)
- **C.** Filtro `demand_type` em `search_legislation` + prioridade especializado (4 testes)
- **D.** Migration `documents.extracted_text` + cache no Extrator (3 testes)

**18 testes novos, 0 regressão.** Pré-requisito para Sprints 0 e 1.

### Sprint Z — Abandono do MemPalace
**Diligência 2026-04-23** revelou sinais fortes de supply-chain attack no pacote PyPI `mempalace`:
- 49k stars em 18 dias (implausível organicamente)
- Wheel de 213 KB incompatível com escopo prometido (KG + vetor + MCP)
- Autor com metadata ofuscada
- Primeira release em v2/v3 (evasão de escrutínio)
- README com "scam alert" performativo
- Zero menções independentes em repos públicos

**Decisão:** abandonar. Substituto planejado: **pgvector na Sprint U/Week 1**.

**Estratégia de remoção (Opção A — conservadora):**
- `pip uninstall mempalace` do venv
- Linha removida de `requirements.txt`
- `app/agents/memory.py` → **stub no-op** preservando 10 assinaturas (`diary_write`, `diary_read`, `kg_add`, `kg_query`, `search`, `save_to_room`, `recall_agent_context`, `log_agent_execution`, `is_available`) para não quebrar chamadas em `BaseAgent` (`_mempalace_log`, `_mempalace_log_failure`, `recall_memory`) e no `orchestrator._mempalace_log_chain`
- Volume `mempalace_data` + entrypoint `python -m mempalace init` removidos do `docker-compose.yml`
- ADR em `docs/adr/adr_mempalace_REVOKED.md` com lição aprendida e checklist de cirurgia completa agendada

**Dívida registrada explicitamente no ADR:** próxima rodada deleta `memory.py`, remove `palace_room` dos 10 agentes, remove hooks e chamadas em `BaseAgent.run()`, remove `_mempalace_log_chain` em `orchestrator.py`, remove blocos de recall em `diagnostico.py:44-67` e `legislacao.py:71-96`.

**Distinção importante:** o pacote `claude-mem@thedotmack` (npm/plugin Claude Code para gravar sessões de dev aqui) **não é o mesmo pacote** e segue ativo em `~/.claude-mem/`.

### Sprint 0 — Ingestão de legislação
Objetivo: popular `legislation_documents` com corpus mínimo viável e **validar que o agente `legislacao` consome a base real** em vez de alucinar.

**Scripts criados:**
- `scripts/ingest_legislation.py` — CLI genérica (URL ou PDF, idempotente, preview, validação por keyword)
- `scripts/inspect_legislation_pdfs.py` — regex pypdf para inferir scope/UF/agency/identifier/date
- `scripts/ingest_pasta_socia.py` — orquestrador com metadata curada dos 15 PDFs da pasta
- `scripts/ingest_federais_canonicos.py` — 10 federais alvo (planalto.gov.br + Sisconama)

**Corpus final:** 23 diplomas, 1.67M tokens.

| UF / escopo | Docs | Tokens | Destaques |
|---|---|---|---|
| **Federal** | 11 | 185.574 | Lei 12.651 Código Florestal, Lei 9.605 Crimes Ambientais, Lei 9.985 SNUC, Lei 6.938 PNMA, LC 140, Decreto 7.830 SICAR, Decreto 8.235 PRA, Res. CONAMA 001/86, IN MMA 02/2014, IN IBAMA 14/2024, Manual SFB SICAR 2023 |
| **Estadual GO** | 12 | 1.490.195 | Decreto 9.308/2018 compensação; IN SEMAD 01/2024 autocomposição; IN SEMAD 09/2024 CAR; Portaria SEMAD 501/2024 fiscalização; Res. CEMAm 259/2024 licenciamento; Matriz IPÊ; coletâneas de licenciamento, outorga, regularização; Plano de Manejo Pouso Alto |

**Validação end-to-end:** agente legislação, rodado contra o corpus, retornou `confidence=alta` citando **IN MMA 2/2014** e **Lei 12.651/2012** — ambas ingeridas hoje. Não é mais hallucination do LLM.

---

## 3. Decisões arquiteturais tomadas (e por quê)

### 3.1. Roteamento dinâmico Gemini Flash → Pro no agente legislação

**Problema:** Gemini 2.0 Flash tem janela de **1M tokens** (sócia me corrigiu — eu tinha assumido 2M). Coletâneas grandes podem gerar contexto > 1M quando combinadas. Trocar para Gemini 1.5 Pro globalmente (janela 2M, mas $2.50/1M acima de 200K) encareceria 25× o custo médio.

**Solução:**
```
Contexto ≤ 800K tokens  →  Gemini 2.0 Flash   ($0.10/1M, cost_limit $0.30)
Contexto > 800K tokens  →  Gemini 1.5 Pro      ($2.50/1M, cost_limit $5.00)
```

Implementado em `app/agents/legislacao.py` como cálculo de `context_chars` antes do `call_llm`, escolhendo `model` e `max_cost_override_usd` apropriados. Outros agentes seguem com `AI_MAX_COST_PER_JOB_USD=0.10` default.

**Custo esperado:** ~95% das consultas ficam em Flash (~$0.05/call). ~5% migram para Pro (~$2-4/call). **Custo médio ~$0.20/call.**

### 3.2. Skills em arquivo (Forma A, não Forma B)

**Contexto:** Sprint 1 introduz camada procedural (skills) que encapsula "como redigir um ofício SEMAD", "como fazer memorial CAR", etc.

**Forma A escolhida:** skill é arquivo `.md` compilado no system prompt no momento da instanciação do agente. Uma chamada ao LLM, custo único, previsível.

**Forma B rejeitada:** skill como tool call (`load_skill("oficio_semad")`). Duas chamadas (decidir + executar), custo 2×, mais lento.

**Por que não explode com escala:** skills são por **tipo de procedimento** (um `oficio_semad.md` cobre todos os SEMA/SEMAD — UF entra como variável em runtime), **não** por lei nem por caso. Estimativa: 40 skills no sistema inteiro. Cada uma ~500-2K tokens. Prompt final do agente: ~3-4K tokens, <0,5% da janela do Flash.

**Skills ≠ Legislação ≠ Histórico de casos** — três camadas separadas:
- Skills = templates procedurais (~40 arquivos fixos)
- Legislação = base de conhecimento jurídico (`legislation_documents` + `search_legislation` com top-20 filtrado)
- Histórico = ofícios/diagnósticos passados (**Sprint U/pgvector**, ainda não implementado)

### 3.3. Separação skills-public × skills-tenant

- **Pública:** `app/skills/public/{agent}/{skill}.md` no git
- **Tenant-específica:** MinIO sob `skills/{tenant_id}/{agent}/{skill_name}.md`
- Fallback: tenant → public → prompt hardcoded atual
- **V1 não tem tabela `skills` no Postgres** — migração fica para V2 se precisar governança

### 3.4. Congelar prompts dos agentes
Regra explícita registrada na memória do projeto: **não alterar prompts/chains dos 10 agentes existentes**. Skills são camada aditiva — complementam sem quebrar contratos de saída JSON dos agentes.

### 3.5. Abandono do MemPalace (ver Sprint Z acima)
Substituído por stub no-op até a Sprint U entrar com pgvector como backend único de memória.

---

## 4. Estado do sistema agora (números reais, DB live)

| Métrica | Valor | Observação |
|---|---|---|
| Diplomas indexados | **23** | era 0 antes da Sprint 0 |
| Tokens no corpus legislativo | **1.67M** | 11 federais + 12 estaduais GO |
| Maior diploma individual | 430K tokens (Coletânea Licenciamento GO) | cabe folgado em Flash |
| AIJobs totais | 24 + 7 da sessão = ~31 | ainda volume de smoke, não produção |
| Custo acumulado em 18 dias | ~$0.004 USD | smoke |
| MemPalace embeddings | 0 | removido |
| Tests passando | 159 / 182 | 23 falhas pré-existentes (auth, e2e, pdf) |
| Propriedades com `geom` | 0 de 7 | PostGIS ainda dormindo, plano separado |

---

## 5. Dívidas técnicas registradas

| Prioridade | Item | Origem | Fonte |
|---|---|---|---|
| 🔴 alta | Cirurgia completa MemPalace (deletar `memory.py`, remover `palace_room` dos 10 agentes, remover hooks no `BaseAgent`) | Sprint Z | `docs/adr/adr_mempalace_REVOKED.md` |
| 🔴 alta | Sprint U — pgvector como memória dos agentes | Auditoria inicial | `CONTEXTO_ARQUITETURAL.md` §3 |
| 🟡 média | Ingerir CONAMA 237/1997 e 369/2006 (URLs do Sisconama retornaram textos trocados; revalidar) | Sprint 0 | `scripts/ingest_federais_canonicos.py` CONAMA_TODO |
| 🟡 média | Ativar crawlers DOU/DOE/IBAMA no Celery Beat (já implementados, falta rodar em ambiente controlado) | Sprint 0 | `app/workers/legislation_tasks.py` |
| 🟡 média | Quebrar coletâneas grandes em diplomas individuais (05_LICENCIAMENTO 430K, 09_FISCALIZACAO 257K, 10_OUTORGA 146K, Plano Manejo 243K) | Sprint 0 | `docs/sprints/sprint_0.md` |
| 🟢 baixa | Apagar `~/.mempalace/knowledge_graph.sqlite3*` residual (arquivos travados por processos externos) | Sprint Z | `scripts/cleanup_mempalace_storage.ps1` |
| 🟢 baixa | PostGIS ativo — parse de shapefile + ST_Intersects (CAR × APP × RL × UC) | Auditoria inicial | fora de escopo do ciclo |
| 🟢 baixa | 27 falhas pré-existentes de teste (auth, dashboard, e2e, pdf) | Sprint -1 | `docs/sprints/sprint_minus1.md` |

---

## 6. Perguntas em aberto para brainstorm externo

Essas são as decisões que ainda não batemos, que agradeceria ouvir outra cabeça:

### 6.1. Quando e como ativar pgvector (Sprint U)
- Imagem Docker atual (`postgis/postgis:15-3.3`) **não tem pgvector**. Duas opções:
  - Imagem community `imresamu/postgis-pgvector:15-3.3.5-0.6.0` (combinada — 1 linha de diff em 3 lugares)
  - Dockerfile custom em cima da `postgis/postgis` com `apt install postgresql-15-pgvector`
- **Escopo do primeiro uso:** memória de casos (ofícios/diagnósticos passados para recall semântico) ou RAG de legislação (chunks com similaridade)? Ou os dois ao mesmo tempo?

### 6.2. Embedding provider
- OpenAI `text-embedding-3-small` — $0.02/1M tokens, 1536 dims, qualidade alta, pago
- Gemini `text-embedding-004` — free tier generoso, 768 dims
- bge-m3 local — zero custo recorrente, ~2GB modelo, requer CPU/GPU decente no container

**Critério principal**: custo em escala vs qualidade semântica em português técnico-jurídico brasileiro. Alguém já comparou os 3 nesse domínio?

### 6.3. Quebrar coletâneas em diplomas individuais
PDFs como `05_LEGISLACAO_LICENCIAMENTO_AMBIENTAL.pdf` (796 páginas) são na verdade compilações de N atos normativos. Hoje estão ingeridos como 1 documento `source_type='manual'`. **Vale a curadoria manual** (identificar cada ato dentro de cada coletânea, extrair individualmente, ingerir com metadata própria) ou o custo-benefício está no ponto atual (um doc grande que o Pro aguenta)?

### 6.4. PostGIS como diferencial govtech
Imóveis têm coluna `geom` (SRID 4674 SIRGAS 2000) mas 0 de 7 propriedades no banco tem geometria preenchida. Zero operações `ST_*` no código. O diferencial "consultoria ambiental que cruza CAR × APP × Reserva Legal × UC automaticamente" depende disso ativo. **Vale priorizar antes de skills/RAG/pgvector, ou deixar pós-MVP?**

### 6.5. Chaves Gemini de produção
Testes em dev estouraram RPD do free tier do Gemini (1500 requests/dia). Validação end-to-end completa exige chave paga. **Quando fazer o upgrade** — antes de Sprint 1, antes da sócia começar a usar de verdade, ou depois do piloto com ela?

### 6.6. Roteamento Flash→Pro — threshold real
Defini 800K tokens como threshold (char/tokens ~4:1). Na prática, o corpus atual só ultrapassa isso em uma única combinação de consulta (licenciamento GO completo). **O threshold está conservador demais** (forçando Pro em casos que caberiam em Flash se o search_legislation fosse mais agressivo na filtragem)? Ou está no ponto?

---

## 7. Próximos passos planejados

| Sprint | Escopo | Status | Bloqueador |
|---|---|---|---|
| **Sprint 1 — SKILL.md** | Infra de skills + 3-5 skills do Redator + 2-3 do Extrator usando os 2 DOCX gabarito | Aguardando | Sócia + user escrevem as skills juntos |
| **Cirurgia MemPalace** | Deletar `memory.py` stub + remover `palace_room` dos 10 agentes + limpar hooks no `BaseAgent` + `orchestrator` | Agendada próxima rodada | Decisão: antes ou junto com Sprint U? |
| **Sprint U — pgvector** | Backend único de memória dos agentes + (opcionalmente) RAG de legislação | Aguardando | 3 decisões da seção 6 |

---

## 8. Trade-offs explícitos

| Trade-off | Escolha desta sessão | Alternativa rejeitada | Por quê |
|---|---|---|---|
| Skills: compilar no prompt vs tool call dinâmica | **Forma A (compilação)** | Forma B (tool `load_skill`) | Menos complexidade, custo 1× em vez de 2×, skills cabem folgado na janela |
| MemPalace: stub no-op vs cirurgia total agora | **Stub no-op** (Opção A) | Deletar tudo + 12 arquivos mexidos (Opção B) | Reduz superfície de mudança na Sprint Z; cirurgia vira sprint próprio antes da Sprint U |
| Coletâneas grandes: quebrar vs ingerir inteiras | **Ingerir inteiras como manual** | Curadoria manual para cada ato | Entrega imediata pra sócia; quebrar depois com feedback real |
| Gemini: mudar tudo para Pro vs roteamento | **Roteamento dinâmico** | Pro global ($2.50/1M) | Custo médio 25× menor; Pro só quando vale |
| pgvector: trocar imagem vs Dockerfile custom | **Adiado** | — | Depende de 3 decisões arquiteturais pendentes (seção 6) |
| Prompts dos agentes: revisar vs congelar | **Congelados** | Revisar + skills | Regra explícita na memória; skills são aditivas |
| Gemini free tier vs paga | **Manter free em dev** | Subir para pagamento já | Piloto ainda não rodou; validação funcional usou OpenAI |

---

## 9. Perfil do sistema para leitor externo

**Amigão do Meio Ambiente** — SaaS multi-tenant de consultoria ambiental brasileira (fazendas, cooperativas agropecuárias).

**Stack:** FastAPI + SQLAlchemy 2 + PostgreSQL 15 + PostGIS 3.3 + Redis + Celery + MinIO + litellm (multi-provider OpenAI/Gemini/Anthropic) + React/Next.js/Expo.

**10 agentes IA** herdando de `BaseAgent` (atendimento, extrator, diagnostico, legislacao, orcamento, redator, financeiro, acompanhamento, vigia, marketing). Agentes disparam via chain (`orchestrator.py`, 9 chains pré-definidas) ou manual via `/agents/run*`. Triggers automáticos: intake, upload de documento, transição de macroetapa, Celery Beat (vigia 6h, acompanhamento 30min).

**7 Macroetapas da jornada do cliente:** entrada → diagnóstico preliminar → coleta documental → diagnóstico técnico → caminho regulatório → orçamento → contrato.

**Maturidade atual:** MVP pré-piloto. Seeds e smoke-tests. Sócia (ambientalista, não programadora) está prestes a começar uso real.

---

## Referências de commits e docs

```
c009bcf  Sprint 0   (23/04)  ingestão de legislação
bda2123  Sprint Z   (23/04)  abandono MemPalace
1e6fdcc  Sprint -1  (23/04)  faxina
3b27516  Sprint R   (23/04)  budget mensal por tenant
c33c4ad             (23/04)  refino UI + kanban legado removido
```

**Docs da sessão:**
- `docs/sprints/sprint_minus1.md`
- `docs/sprints/sprint_0.md`
- `docs/adr/adr_mempalace_REVOKED.md`
- `docs/archive/mempalace_REVOKED.md` (conteúdo antigo arquivado)
- `CONTEXTO_ARQUITETURAL.md` (auditoria técnica profunda, 2.3K linhas — útil para mergulho técnico)
- `scripts/ingest_legislation.py`, `scripts/ingest_pasta_socia.py`, `scripts/ingest_federais_canonicos.py`, `scripts/inspect_legislation_pdfs.py` (ingestão)
- `scripts/cleanup_mempalace_storage.ps1` (cleanup pendente)

---

**Fim. Qualquer item acima pode ser aprofundado sob demanda.**
