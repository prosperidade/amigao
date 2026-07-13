# ADR-024 — Abas do workspace do caso: flag de visibilidade + Tarefas não funde em Ações

**Status:** Aceita (André, 2026-07-13)
**Contexto relacionado:** Ficha 07 §3 (as 6 abas do MVP), precedente `min_stage_index`
(TabDef — bloco condicional por etapa), ADR-009 (superfícies congeladas).

## Contexto

A Ficha 07 §3 define **6 abas** no workspace do caso, na ordem do fluxo de trabalho:
**Visão geral · Documentos · Conferência · Dados · Ações · Saídas**. O componente de
detalhe do processo (`ProcessDetail.tsx`, container mapeado em `ProcessDetailTypes.ts`)
mostrava **~10 abas** — sobras acumuladas em sprints anteriores: Tarefas, Comunicação,
Histórico, Decisões, IA. Excesso de superfície = ruído para o consultor e, no caso da
aba **IA**, uma tela quebrada (não dispara a cadeia de agentes).

Escopo desta decisão: **apenas as abas internas do detalhe do caso**. Sidebar/navegação
global, kanban de casos (`QuadroAcoes.tsx`), rotas de páginas fora do detalhe e o painel
direito da etapa (`WorkspaceRightPanel`) **não são tocados** — permanecem pixel por pixel.

## Decisão

### 1. Flag de visibilidade por aba (fonte única)

Novo módulo `frontend/src/lib/tabFlags.ts` — mapa `key → visível` (`TAB_VISIBILITY_DEFAULTS`)
lido pelo container de tabs via `isTabVisible(key)`. É o eixo **ortogonal** ao
`min_stage_index` (que filtra por etapa): a Comercial precisa dos dois (flag visível **E**
etapa ≥ 6). O flag é **global** hoje; a assinatura de `isTabVisible(key, ctx?)` e o helper
`resolveTabVisibility(defaults, override)` já deixam a porta aberta para **por-tenant** e
override por env (`VITE_TAB_FLAGS`) — **sem** construir admin de flags (fora de escopo).

Abas do MVP (`true`): `diagnosis`, `documents`, `alertas` (Conferência), `dossier` (Dados),
`acoes`, `saidas`. **Comercial** (`commercial`) permanece `true` **por ora**: é o único
acesso a Proposta/Contrato até o Sprint 5 convergir tudo em Saídas — aí vira `false`.
Ocultas (`false`): `tasks`, `messages`, `ai`, `timeline`, `decisions`.

### 2. OCULTAR ≠ APAGAR

Nenhum componente, rota de API ou dado é removido. As `TabDef` das abas ocultas continuam
declaradas em `TABS` (só filtradas na renderização). O sistema **segue gravando por baixo**:
o Histórico continua registrando (audit log intacto), as `Task` continuam existindo. Só a
superfície some. Religar qualquer aba = flip de um booleano.

### 3. Deep-link de aba oculta → redirect suave

`resolveActiveTab(requested)` resolve a aba efetiva: se a requisitada (deep-link `?tab=`,
estado herdado, lixo) estiver oculta ou for desconhecida, cai na **Visão geral** — nunca
renderiza conteúdo fora da superfície, nunca área em branco, sem crash. O container usa
`effectiveTab` (guardado) para renderizar o conteúdo e marcar a aba ativa.

### 4. Tarefas NÃO funde em Ações (no MVP)

Considerou-se fundir a aba Tarefas na aba Ações ao ocultá-la. **Rejeitado.** `Task` e `Acao`
são entidades deliberadamente distintas (`app/models/acao.py:20-26`): a fusão seria 1:N (não
1:1) e perderia o grafo de dependências e o kanban operacional das `Task`. Decisão: **Tarefas
some da UI, `Task` continua viva por baixo**; a fusão real (se um dia fizer sentido) é dívida
pós-MVP (`REGISTRO_DIVIDAS` #63).

## Consequências

- **Positivas:** o consultor vê exatamente as 6 abas da Ficha (+ Comercial temporária);
  a aba IA quebrada some da frente sem apagar nada; religar aba é trivial e testável.
- **Dívidas abertas:** #63 (fusão Tarefas→Ações pós-MVP) e #64 (aba IA não dispara a
  cadeia — conserto adiado; ocultar só trata o sintoma).
- **Gatilho de reversão:** quando Saídas absorver Proposta/Contrato (Sprint 5), a Comercial
  vira `false` no mesmo flag — uma linha. Quando existir contexto de tenant, `isTabVisible`
  passa a consultar o override sem mudar os call sites.
- **Não-objetivo:** admin de flags, persistência do flag em banco, e qualquer mudança em
  estrutura de página / sidebar / painel direito ficam fora deste ADR.
