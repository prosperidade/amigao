# SPRINT 0 — Aba "Conferência" (renomear Alertas + botão visível + alertas → Visão geral)

**Branch:** `feat/sprint0-aba-conferencia` (base `main`)
**Data:** 2026-06-29
**Decisão de domínio:** Isis + André (fechada). Ficha 07 — "Conferência é onde o
que foi lido vira base".
**Relacionado:** Ficha 07 (Ações), ADR-012 (decisão contextual ao processo),
`historico_eventos_expansivel.md`. NÃO refaz limpeza/histórico (#84/#85/#86).

## Problema

A aba "Alertas" (`AlertasTab`) misturava duas coisas: a **conferência/consolidação**
do staging (a ação "o que foi lido vira base") e os **alertas regulatórios** do
auditor. Pior: o botão de gravar estava **enterrado no fim** de uma lista enorme.

## O que mudou

### 1. Aba "Alertas" → "Conferência"
- `ProcessDetailTypes.ts` TABS: `label` da aba de `key:'alertas'` agora é
  **"Conferência"** (a `key` permanece `'alertas'` — mudá-la quebraria roteamento,
  `TabKey` e os `#alerta-{id}`).
- `AlertasTab.tsx` → renomeado para **`ConferenciaTab.tsx`**, agora renderiza
  **só** o `ConsolidacaoPanel` (campos a conferir + divergências) + um **empty
  state** ("Nada para conferir ainda") quando o staging está vazio — antes a aba
  ficaria em branco (ex.: caso 13 pós-wipe).
- `ProcessDetail.tsx`: import/uso atualizado; texto auxiliar em
  `DiagnosisAssinatura.tsx` deixou de mandar "ir para Alertas".

### 2. Botão "Gravar na base" visível
- `ConsolidacaoPanel.tsx`: a barra de ação (resumo + botão) virou **rodapé fixo
  (`sticky bottom-0`)** do card — sempre à vista, não mais no fim do scroll. O
  resultado pós-consolidação passou para ANTES da barra. Texto do botão renomeado
  de "Consolidar na base" → **"Gravar na base"** (vocabulário da Ficha 07). A
  **lógica de consolidação não mudou** (mesmo endpoint `POST /consolidar`).

### 3. Alertas regulatórios → Visão geral
- O bloco de `AlertaCard`/`useIssues` saiu da aba Conferência e passou para a
  **`DiagnosisTab`** (Visão geral), logo abaixo da assinatura — nascem junto do
  diagnóstico. `useIssues` tem a mesma queryKey (cache compartilhado, sem fetch
  duplicado). `onGoToAlerta` (modal do gate) agora só **rola** até o card (mesma
  aba), sem trocar de aba.
- **Botão "→ Ações"** novo em cada `AlertaCard`: envia o alerta para a aba Ações
  via `useCreateAcao` (fluxo de criação **já existente** — `POST /processes/{id}/acoes`).
  O alerta **não vira ação sozinho**; é o consultor que clica. _Limitação aceita
  no sprint:_ a ação nasce `origem='manual'` (o payload atual não aceita `issue_id`;
  vincular alerta→ação com origem `auditor` é sprint futuro)._

## Validação

- `tsc --noEmit` · `eslint --max-warnings=0` · `vite build` — verdes.
- Testes (vitest): **73 passed** (12 arquivos). Novos:
  - `AlertaCard.test.tsx` — "→ Ações" chama `POST /processes/42/acoes` com título do alerta.
  - `ProcessDetailTypes.test.ts` — aba usa label "Conferência" e não existe mais "Alertas".
  - Regressão: `AlertaCard` (Regra B / #19), `DiagnosisAssinatura` verdes.

### Aceite (caso 13 real, pós-deploy)
- A aba aparece como **"Conferência"** (não "Alertas").
- Ao abrir, **"Gravar na base"** está visível (rodapé fixo), sem rolar até o fim.
  Clicar grava (consolidação como hoje).
- Os alertas regulatórios aparecem na **Visão geral**, cada um com **"→ Ações"**.

## Fora de escopo (sprints seguintes)
- Esconder outras abas / fundir Tarefas em Ações (Sprint 6).
- Vincular alerta→ação com `issue_id`/origem `auditor` (precisa endpoint/payload novo).
- Ramo E2→E3/E4, Rota, selos, contrato 13 blocos.
- `client-portal/`/`mobile/` congelados (ADR-009).
