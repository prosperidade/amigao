# ADR-025 — Feed do consultor em linguagem humana (tradução + filtro de audiência)

**Status:** Aceita (André, 2026-07-13)
**Contexto relacionado:** Princípio "a IA propõe; o humano decide" (o consultor é o
público, não a máquina), ADR-020 (nota derivada na leitura), historicoEventos.ts
(humanizador já existente da timeline do workspace).

## Contexto

O feed "Atividades Recentes" do dashboard lê `AuditLog` cru e renderizava o
`action` + o `details` (JSON) direto na tela. Resultado visto pelo consultor:
`agent.vigia.completed` seguido de `{"agent_name":"vigia","trace_id":...}`, além
de eventos de sistema sem caso (vigia diário, `reset_casos_teste`, `ai_key_used`).
Linguagem de máquina na vitrine de quem paga.

Dois problemas distintos, mesma tela:
1. **Ruído de audiência** — eventos de sistema (sem vínculo com um caso) ocupavam
   o feed. O consultor só quer eventos DE CASO.
2. **Linguagem técnica** — event type e JSON crus, nomes internos de agentes
   (`auditor_imovel`, `legislacao`), status em inglês (`completed`), prioridade
   em inglês (`high`).

Regra de ouro: a **gravação** do `AuditLog` é auditoria — permanece intocada. A
correção é 100% **camada de apresentação** (read-path + render).

## Decisão

### 1. Filtro de audiência (read-path, backend)

`_recent_activities` (dashboard) exclui, na vitrine do consultor, eventos de
sistema sem caso: `entity_type in {reset, user}` e eventos de agente sem processo
(`entity_type="agent"` com `entity_id == 0`, ex.: vigia diário). Precisa ser no
QUERY porque o `limit(8)` é aplicado antes — filtrar no frontend deixaria o feed
quase vazio. Os eventos continuam gravados e consultáveis via `/audit`; só somem
da vitrine.

### 2. Dicionário de tradução evento→frase (frontend)

`frontend/src/lib/activityLabels.ts` — `translateActivity(event)` devolve
`{ title, technical, isFallback }`. `title` é uma frase PT-BR de consultor com
dados úteis interpolados (nome do caso, nº de passos da rota). `technical` (action
+ escalares úteis) vai só no tooltip/expandir. Cobre todos os event types atuais
(agente, ações de caso, `{campo}_changed`). **Fallback obrigatório:** evento sem
tradução → "Atividade registrada no sistema"; JSON cru NUNCA renderiza direto.
O backend passa `entity_label` (título do Process, resolvido sem N+1) para a
interpolação "{nome do caso}".

### 3. Rótulo de produto por agente — fonte única

`@/types/agent.ts::AGENT_LABELS` é a fonte única, usada em TODA superfície que
exibe nome de agente (feed, `AIPanel`, `AgentsPage`, `WorkspaceRightPanel`,
`ClientHub`). Rótulos revistos para o papel: `vigia`→"Vigia normativo",
`auditor_imovel`→"Auditoria do imóvel", `legislacao`→"Análise legal",
`extrator`→"Leitura de documentos", `redator`→"Redator", etc. (os 11 +
`orchestrator`→"Equipe de agentes").

### 4. Leitura da IA do kanban — cache determinístico corrigido

`/kanban-insights` (o card "Leitura da IA" em /processes) é DETERMINÍSTICO — só
`COUNT/GROUP BY` em `Process`, custo zero de IA. Estava com cache de **24h**
(TTL copiado da Leitura executiva que CHAMA o LLM), congelando o card "Hoje o
maior acúmulo…" por um dia sem refletir o sistema. TTL reduzido para **5 min**
(só amortece cargas repetidas do kanban). A decisão da sócia de "1x/dia p/
controlar custo" (2026-04-19) vale só para o endpoint que gasta IA
(`DASHBOARD_AI_SUMMARY_CACHE_TTL`), não para este.

## Consequências

- **Positivas:** o consultor vê frases humanas, só de casos; nomes de agente
  consistentes em todo o app; o card "Leitura da IA" acompanha o sistema.
- **Fallback seguro:** qualquer event type novo aparece como frase genérica com o
  técnico no tooltip — nunca vaza JSON, mesmo sem tradução dedicada.
- **Auditoria intocada:** nenhum evento deixa de ser gravado; `/audit` continua
  retornando tudo.
- **Follow-on listado (não neste PR):** o humanizador da timeline do workspace
  (`historicoEventos.ts`) não trata `agent.*` — cai no genérico semi-técnico.
  Tab hoje oculta (Sprint 6); registrado no `REGISTRO_DIVIDAS`.
