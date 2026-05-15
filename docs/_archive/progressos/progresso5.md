# Progresso 5 — Reestruturacao para 7 Macroetapas + Quadro de Acoes

Padrao deste arquivo:

- linguagem executiva e de historico de execucao
- foco em resultado, decisao, validacao, risco e pendencia
- evitar instrucoes operacionais detalhadas; isso pertence ao `RunbookOperacional.md`

## Projeto: Amigao do Meio Ambiente
## Referencia: Plano Mestre v2 — Fases 4 e 5

---

## Objetivo da rodada

Reestruturar o fluxo de processos de 11 status genericos para 7 macroetapas que refletem o fluxo real da consultoria ambiental brasileira, conforme validado com o prototipo Regente (socia) e o consultor ambiental da equipe.

---

## Contexto e motivacao

O sistema original tinha 11 status de processo (lead, triagem, diagnostico, planejamento, execucao, protocolo, aguardando_orgao, pendencia_orgao, concluido, cancelado, arquivado) que misturavam etapas pre e pos-contrato. O prototipo Regente da socia demonstrou que o fluxo real do consultor ambiental segue 7 macroetapas sequenciais ate a formalizacao do contrato:

1. Entrada da Demanda
2. Diagnostico Preliminar
3. Coleta Documental
4. Diagnostico Tecnico Consolidado
5. Definicao do Caminho Regulatorio
6. Orcamento e Negociacao
7. Contrato e Formalizacao

O consultor ambiental tambem identificou como diferencial-chave um agente de IA com base de conhecimento legislativa (RAG) que sugere o caminho regulatorio — planejado para as Fases 1-3 do Plano Mestre v2.

---

## Execucao Fase 4 — Backend das 7 Macroetapas (08/04/2026)

### 1. Modelo Macroetapa (app/models/macroetapa.py)

Criado:
- Enum `Macroetapa` com 7 valores
- `MACROETAPA_TRANSITIONS` para maquina de estados sequencial
- `STATUS_TO_MACROETAPA` para backward compatibility com status legado
- `MACROETAPA_LABELS` em pt-BR
- `MACROETAPA_AGENT_CHAIN` vinculando cada etapa ao agente/chain do orchestrator
- `DEFAULT_ACTIONS` com checklist padrao por macroetapa (5-8 acoes cada)
- Model `MacroetapaChecklist` com acoes em JSON, completion_pct, unique constraint (process_id, macroetapa)

Decisao: usar `String` ao inves de `Enum` PostgreSQL na coluna para evitar migrations de ALTER TYPE ao adicionar macroetapas futuras (MVP2 pos-contrato).

### 2. Coluna macroetapa no Process (app/models/process.py)

Adicionado:
- `macroetapa = Column(String, nullable=True, index=True)`
- Estrategia aditiva: coluna coexiste com `status` para backward compatibility
- Processos legados mapeados via data migration

### 3. Engine de Macroetapas (app/services/macroetapa_engine.py)

Criado:
- `initialize_macroetapa_checklists()` — cria checklists de todas as 7 etapas
- `advance_macroetapa()` — valida transicao e avanca
- `toggle_action()` — marca/desmarca acao no checklist
- `calculate_completion_pct()` — calcula % de conclusao
- `get_macroetapa_status()` — retorna stepper completo com todas as etapas

### 4. Schemas Pydantic (app/schemas/macroetapa.py)

Criado:
- `MacroetapaAdvanceRequest`, `ActionToggleRequest`
- `MacroetapaStatusResponse` com steps, completion, next_action
- `KanbanProcessCard` (card enriquecido: client, property, demand_type, urgency, completion %)
- `KanbanColumn`, `KanbanResponse`

### 5. Endpoints API (app/api/v1/processes.py)

Adicionados 5 endpoints:
- `GET /processes/{id}/macroetapa/status` — stepper completo
- `POST /processes/{id}/macroetapa` — avancar macroetapa
- `POST /processes/{id}/macroetapa/initialize` — inicializar checklists
- `PATCH /processes/{id}/macroetapa/{etapa}/actions` — toggle acao
- `GET /processes/kanban` — kanban enriquecido por macroetapa

### 6. Leitura da IA (app/api/v1/dashboard.py)

Adicionado:
- `GET /dashboard/kanban-insights` — analisa gargalos por macroetapa, conta pendencias criticas, gera mensagem de recomendacao

### 7. Orchestrator (app/agents/orchestrator.py)

Adicionado:
- Chain `enquadramento_regulatorio: [extrator, legislacao]`
- Intent `regulatory_assessment`
- Dict `MACROETAPA_CHAINS` vinculando cada macroetapa a chain sugerida

### 8. Migration Alembic (alembic/versions/c2d3e4f5a6b7)

Criado:
- Adiciona coluna `macroetapa` a `processes`
- Cria tabela `macroetapa_checklists` com unique constraint
- Data migration: popula macroetapa para processos existentes baseado no status legado

### Validacao

- `python -c "from app.main import app"` → 90 rotas, sem erro
- `python -c "from app.models.macroetapa import ..."` → 7 macroetapas, labels corretos
- `npx tsc --noEmit` → sem erros de tipo no frontend

---

## Execucao Fase 5 — Frontend Quadro de Acoes (08/04/2026)

### 1. Tipos compartilhados (frontend/src/types/process.ts)

Criado:
- `Macroetapa` type union
- `KanbanProcessCard`, `KanbanColumn`, `KanbanResponse` interfaces
- `MacroetapaStatusResponse`, `ActionItem` interfaces
- `KanbanInsight` interface
- `MACROETAPA_LABELS`, `MACROETAPA_COLORS` constantes

### 2. Componente LeituraIA (frontend/src/pages/Processes/LeituraIA.tsx)

Criado:
- Banner colapsavel com insights do kanban
- Fetch de `GET /dashboard/kanban-insights`
- Exibe gargalo, pendencias criticas, recomendacao
- Estado de collapse persistido em localStorage

### 3. Componente ProcessCard (frontend/src/pages/Processes/ProcessCard.tsx)

Criado:
- Card enriquecido: nome cliente, imovel, tipo demanda, badges urgencia
- Responsavel, proxima acao, barra de progresso
- Cores por urgencia (critica=vermelho, alta=laranja, media=amarelo, baixa=verde)

### 4. Componente MacroetapaStepper (frontend/src/pages/Processes/MacroetapaStepper.tsx)

Criado:
- Stepper vertical de 7 etapas com status (completed/active/pending)
- Completion % por etapa
- Visual integrado ao painel lateral

### 5. Painel Lateral Redesenhado (frontend/src/pages/Processes/MacroetapaSidePanel.tsx)

Criado:
- Stepper de macroetapas no topo
- Checklist de acoes com checkboxes interativos
- Aba "Agente" para consultar IA da macroetapa
- Tabs: Checklist | Documentos | Timeline

### 6. Quadro de Acoes (frontend/src/pages/Processes/index.tsx)

Reescrito:
- 7 colunas por macroetapa (substituindo 9 colunas de status)
- Banner Leitura da IA no topo
- Cards enriquecidos com ProcessCard
- Drag-and-drop avanca macroetapa (chama POST /processes/{id}/macroetapa)
- Painel lateral com MacroetapaSidePanel
- Filtros por responsavel, urgencia, tipo de demanda
- Contador "X casos ativos"

### Validacao

- `npx tsc --noEmit` → sem erros
- `npm run build` → build bem-sucedido

---

## Decisoes arquiteturais desta rodada

1. **Macroetapa como String, nao Enum PG** — evita ALTER TYPE em migrations futuras
2. **Coexistencia status + macroetapa** — processos legados continuam funcionando
3. **Checklist em JSON** — flexivel, sem necessidade de tabelas auxiliares
4. **Sem biblioteca de charts** — barras CSS horizontais suficientes para MVP
5. **Claude Sonnet para agente regulatorio** — aprovado para Fase 2 futura
6. **Crawlers para 27 UFs** — aprovado para Fase 3 futura

---

## Execucao Fase 1 — Base Legislativa (08/04/2026)

### Decisao arquitetural: context loading vs chunking

Decisao do usuario: **NAO usar chunking + embeddings + pgvector.**
Em vez disso, armazenar texto completo da legislacao e enviar no contexto do Gemini (2M tokens).
Isso preserva integridade do documento legislativo e evita perda de contexto entre artigos.

### 1. Model LegislationDocument (app/models/legislation.py)

Criado:
- `LegislationDocument` com: title, source_type, identifier, uf, scope, agency, effective_date, full_text, token_count, content_hash, demand_types, keywords
- Sem tabela de chunks — texto completo armazenado em `full_text`
- tenant_id nullable para legislacao global (federal)

### 2. LegislationService (app/services/legislation_service.py)

Criado:
- `ingest_legislation_document()` — extrai texto de PDF/HTML, calcula hash e tokens, armazena completo
- `search_legislation()` — busca por metadados (UF, scope, agency, demand_type, keyword) com budget de tokens
- `build_legislation_context()` — monta contexto textual para envio ao LLM
- Extratores: PDF (pypdf), HTML (beautifulsoup4)

### 3. API Router (app/api/v1/legislation.py)

Criado:
- `POST /legislation/documents` — criar documento com texto direto
- `POST /legislation/documents/{id}/upload` — upload PDF
- `GET /legislation/documents` — listar com filtros (scope, uf, agency, status)
- `GET /legislation/documents/{id}` — detalhes
- `POST /legislation/search` — busca por metadados para context loading
- `POST /legislation/documents/{id}/reindex` — reprocessar texto

### 4. Migration (alembic/versions/d3e4f5a6b7c8)

Criado:
- Tabela `legislation_documents`
- Novos valores AIJobType: embedding_generation, enquadramento_regulatorio, monitoramento_legislacao

### 5. Config (app/core/config.py)

Adicionado:
- `LEGISLATION_MAX_CONTEXT_TOKENS` (500k default)
- `LEGISLATION_MAX_RESULTS` (20 default)
- `CLAUDE_LEGAL_MODEL`, `CLAUDE_LEGAL_MAX_TOKENS`, `CLAUDE_LEGAL_TEMPERATURE`
- `GEMINI_LEGAL_MODEL` (gemini-2.0-flash para context loading grande)

---

## Execucao Fase 2 — Agente Regulatorio (08/04/2026)

### 1. ClaudeClient (app/core/claude_client.py)

Criado:
- Client direto Anthropic SDK (nao litellm)
- `complete()` retorna `AIResponse` compativel com sistema de agentes
- Calculo de custo por modelo (Sonnet, Opus, Haiku)
- Logging de tokens, custo e duracao

### 2. LegislacaoAgent reescrito (app/agents/legislacao.py)

Reescrito completamente:
- Carrega contexto do processo (demand_type, UF, municipio, bioma, area, embargo, CAR)
- Busca legislacao relevante no banco via `search_legislation()`
- Monta contexto com `build_legislation_context()` (textos completos)
- Decisao automatica de LLM:
  - Contexto > 100k chars → Gemini (janela grande)
  - Contexto normal + ANTHROPIC_API_KEY → Claude Sonnet (raciocinio juridico)
  - Fallback → LiteLLM padrao
- Output estruturado: caminho_regulatorio, orgao_competente, etapas, legislacao_aplicavel, riscos, documentos, prazos
- `requires_review = True` sempre (consequencias juridicas)
- Backward compatible: mantem campos antigos (normas_estaduais, risco_legal)

### 3. Schemas Enquadramento (app/schemas/enquadramento.py)

Criado:
- `EnquadramentoResult` com: caminho_regulatorio, etapas[], legislacao_aplicavel[], riscos[], documentos_necessarios[], prazos_estimados, confianca, justificativa
- Sub-schemas: EtapaRegulatoria, LegislacaoCitada, RiscoIdentificado, PrazosEstimados

### Validacao

- `from app.main import app` → 96 rotas, sem erro
- Todos os imports validados com sucesso

---

## Proximas etapas (Plano Mestre v2)

- **Fase 3:** Auto-monitoramento de legislacao (Celery beat, crawlers DOU + 27 DOEs + IBAMA)

---

## Execucao Fase 3 — Auto-Monitoramento de Legislacao (08/04/2026)

### 1. Framework de Crawlers (app/services/crawlers/)

Criado:
- `BaseCrawler` ABC com `CrawledDocument` dataclass, registry, keywords ambientais
- `DOUCrawler` — Diario Oficial da Uniao (in.gov.br), busca diaria por 13 termos ambientais
- `DOECrawler` — 27 Diarios Oficiais Estaduais via Querido Diario API, config completa por UF com orgao ambiental
- `IBAMACrawler` — Normativas IBAMA (IN, portarias, resolucoes), busca semanal

### 2. LegislationMonitor (app/services/legislation_monitor.py)

Criado:
- `run_monitoring_cycle()` — orquestra: crawl → dedup (identifier+hash) → ingest → match processos → alertas
- Deduplicacao por identifier + content_hash (atualiza se conteudo mudou)
- Match automatico: nova legislacao cruzada com processos ativos por UF + demand_type
- Alertas criados por processo afetado com tipo (new_legislation/updated) e severidade

### 3. LegislationAlert model (app/models/legislation_alert.py)

Criado:
- tenant_id, process_id, document_id, alert_type, severity, message, is_read
- Relacionamentos com Process e LegislationDocument

### 4. Celery Beat Schedule (app/core/celery_app.py)

Configurado:
- `monitor-legislation-dou-daily` — 06:00 BRT diario
- `monitor-legislation-doe-daily` — 06:30 BRT diario (27 estados)
- `monitor-legislation-agencies-weekly` — segunda 03:00 (IBAMA)

### 5. Celery Tasks (app/workers/legislation_tasks.py)

Criado:
- `monitor_legislation` — ciclo completo (todos crawlers)
- `monitor_legislation_dou` — apenas DOU
- `monitor_legislation_doe` — apenas DOEs estaduais
- `monitor_legislation_agencies` — apenas IBAMA
- `ingest_legislation_document_task` — processar documento individual

### 6. API de Alertas (app/api/v1/legislation_alerts.py)

Criado:
- `GET /legislation/alerts` — listar alertas (filtros: is_read, process_id)
- `PATCH /legislation/alerts/{id}/read` — marcar como lido
- `POST /legislation/monitor/trigger` — disparar monitoramento manual

### 7. Migration (alembic/versions/e4f5a6b7c8d9)

Criado:
- Tabela `legislation_alerts`

### Validacao

- `from app.main import app` → 99 rotas
- Crawlers registrados: ['dou', 'doe', 'ibama']
- `npx tsc --noEmit` → sem erros

---

## Ativacao em producao e correcao de bugs (08/04/2026)

### Migrations executadas

As 3 migrations foram executadas com sucesso no banco local:
- `c2d3e4f5a6b7` — macroetapa column + macroetapa_checklists table
- `d3e4f5a6b7c8` — legislation_documents table + novos AIJobType enums
- `e4f5a6b7c8d9` — legislation_alerts table

### Bug 1: Nome do enum PostgreSQL na migration (CORRIGIDO)

A migration `d3e4f5a6b7c8` usava `ALTER TYPE aijobtypes` mas o tipo real no PostgreSQL e `aijobtype` (singular, minusculo). Corrigido no arquivo da migration.

### Bug 2: Model MacroetapaChecklist usava Enum PostgreSQL (CORRIGIDO)

O model `MacroetapaChecklist` declarava a coluna `macroetapa` como `Column(Enum(Macroetapa))`, que tenta criar um tipo PostgreSQL `macroetapa` que nao existe. Corrigido para `Column(String)`, consistente com a migration e com o model Process.

### Bug 3: Early return antes de hooks no React (CORRIGIDO)

O `ProcessesPage` fazia `if (viewMode === 'quadro') { return <QuadroAcoes /> }` **antes** de declarar os hooks (`useState`, `useQuery`, `useMutation`) que vem depois. React exige que todos os hooks sejam chamados antes de qualquer return condicional. 

Correcao: movido o early return para depois de todos os hooks (apos `toggleTaskMutation`).

### Bug 4: Default do frontend era "quadro" em vez de "kanban" (CORRIGIDO)

O primeiro build salvava `processes-view=quadro` no localStorage, fazendo o Quadro de Acoes (vazio) aparecer como default. Corrigido: default fixo como `'kanban'` sem persistencia em localStorage. O kanban original sempre aparece primeiro.

### Data migration executada

- 19 processos existentes receberam macroetapa:
  - 11 via data migration automatica (status → macroetapa mapping)
  - 6 pos-contrato (execucao/protocolo/aguardando) → `contrato_formalizacao`
  - 2 cancelados/arquivados → `entrada_demanda`
- 133 checklists de macroetapa criados (7 por processo × 19 processos)

### Resultado final visivel

- **Kanban original**: funciona normalmente com todos os processos, como antes
- **Botao verde "Quadro de Acoes (7 Etapas)"**: visivel na pagina de Processos para alternar
- **Quadro de Acoes**: 17 processos ativos distribuidos em 4 macroetapas (entrada_demanda: 9, contrato_formalizacao: 6, caminho_regulatorio: 1, diagnostico_preliminar: 1)
- **Dashboard**: inalterado, com cards executivo/operacional funcionando
- **API**: 99 rotas, todas carregando sem erro

---

## Inventario completo de arquivos criados/modificados nesta sessao

### Arquivos novos (26)

**Backend — Models:**
- `app/models/macroetapa.py` — Enum, transicoes, labels, acoes padrao, MacroetapaChecklist
- `app/models/legislation.py` — LegislationDocument (texto completo, sem chunking)
- `app/models/legislation_alert.py` — Alertas de nova legislacao

**Backend — Services:**
- `app/services/macroetapa_engine.py` — Engine advance/toggle/completion/initialize
- `app/services/legislation_service.py` — Ingestao PDF/HTML, busca por metadados, context builder
- `app/services/legislation_monitor.py` — Orquestrador crawl → dedup → ingest → alert
- `app/services/crawlers/__init__.py` — Registry de crawlers
- `app/services/crawlers/base_crawler.py` — ABC + CrawledDocument + registry
- `app/services/crawlers/dou_crawler.py` — DOU federal
- `app/services/crawlers/doe_crawler.py` — 27 DOEs estaduais via Querido Diario
- `app/services/crawlers/ibama_crawler.py` — Normativas IBAMA

**Backend — Schemas:**
- `app/schemas/macroetapa.py` — DTOs kanban + stepper + checklist
- `app/schemas/legislation.py` — DTOs CRUD + search
- `app/schemas/enquadramento.py` — EnquadramentoResult estruturado

**Backend — API:**
- `app/api/v1/legislation.py` — CRUD + search + upload (6 endpoints)
- `app/api/v1/legislation_alerts.py` — Alertas + trigger manual (3 endpoints)
- `app/core/claude_client.py` — Anthropic SDK direto

**Backend — Workers:**
- `app/workers/legislation_tasks.py` — 5 Celery tasks de monitoramento

**Backend — Migrations:**
- `alembic/versions/c2d3e4f5a6b7_add_macroetapa_system.py`
- `alembic/versions/d3e4f5a6b7c8_add_legislation_documents.py`
- `alembic/versions/e4f5a6b7c8d9_add_legislation_alerts.py`

**Frontend:**
- `frontend/src/pages/Processes/quadro-types.ts` — Tipos TypeScript compartilhados
- `frontend/src/pages/Processes/QuadroAcoes.tsx` — Kanban 7 macroetapas
- `frontend/src/pages/Processes/QuadroProcessCard.tsx` — Card rico
- `frontend/src/pages/Processes/MacroetapaStepper.tsx` — Stepper vertical
- `frontend/src/pages/Processes/MacroetapaSidePanel.tsx` — Painel lateral
- `frontend/src/pages/Processes/LeituraIA.tsx` — Banner IA

### Arquivos modificados (12)

- `app/models/process.py` — coluna macroetapa
- `app/models/ai_job.py` — 3 novos AIJobType
- `app/models/__init__.py` — imports LegislationDocument, LegislationAlert, MacroetapaChecklist
- `app/schemas/process.py` — campo macroetapa na response
- `app/api/v1/processes.py` — 5 endpoints macroetapa + 1 kanban
- `app/api/v1/dashboard.py` — endpoint kanban-insights + import ProcessPriority
- `app/agents/orchestrator.py` — chain enquadramento_regulatorio + MACROETAPA_CHAINS
- `app/agents/legislacao.py` — reescrito: context loading + Claude/Gemini
- `app/core/config.py` — settings de legislacao, Claude, Gemini
- `app/core/celery_app.py` — beat_schedule (3 jobs) + import crontab
- `app/main.py` — routers legislation + legislation_alerts
- `frontend/src/pages/Processes/index.tsx` — toggle Quadro/Kanban + fix hooks
- `frontend/src/pages/Dashboard/index.tsx` — urgencia docs expirando + cores barras + tasks no executivo

---

## Riscos e pendencias para proxima sessao

### Alinhamento necessario (prioridade)
- Dashboard Executivo e Operacional precisam ser revisados com o usuario — verificar se os dados que aparecem sao os esperados e se faltam secoes
- Quadro de Acoes funciona mas processos estao concentrados em entrada_demanda (9) e contrato_formalizacao (6) — distribuicao reflete o status legado, nao uso real
- Painel lateral do Quadro de Acoes (MacroetapaSidePanel) precisa ser testado pelo usuario com interacao real (marcar acoes, ver documentos)

### Tecnico
- Base legislativa comeca vazia — alimentar com PDFs/textos de legislacao federal e estadual
- Claude requer `ANTHROPIC_API_KEY` configurada; sem ela, agente regulatorio usa fallback
- Dependencias pip pendentes: `anthropic`, `pypdf`, `beautifulsoup4`, `lxml`
- Celery Beat requer servico `beat` no docker-compose para monitoramento automatico
- Crawlers dependem de APIs externas — podem falhar se estrutura dos sites mudar
- DOE crawler usa Querido Diario API — cobertura municipal limitada
