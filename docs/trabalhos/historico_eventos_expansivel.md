# Histórico de eventos — marcos visíveis, decisões recolhidas (expansível)

**Branch:** `feat/historico-eventos-expansivel` (base `main`)
**Data:** 2026-06-29
**Relacionado:** `historico_eventos.md` (humanização dos eventos), Ficha 01 Fase 4,
limpeza do caso 13 ([[project_caso13_wipe_e_historico_2026-06-29]]).

## Problema

A aba **Histórico de eventos** (`TimelineTab`) renderizava **todos** os eventos do
caso em cards planos. No caso 13 eram **124 eventos**, ~77 deles rejeições
individuais da conferência — um paredão que "mais confunde do que ajuda" (André).

## Princípio (pedido do André)

> Cada seção só preserva na interface os **resultados**; o resto fica oculto num
> **histórico expansível**.

Aplicado ao Histórico de eventos: os **marcos** (caso criado, extração,
consolidação, mudança de status/etapa, classificação, resumo) ficam sempre
visíveis na linha do tempo; as **decisões individuais de conferência**
(aceito/rejeitado/escolhido/editado), quando vêm em sequência, **colapsam num
único bloco-resumo expansível**.

## O que mudou

- **Novo módulo `historicoBlocos.ts`** (lógica pura, testável):
  - `agruparBlocos(eventos)` — varre a timeline e agrupa **runs contíguos** de
    decisões num `cluster`; marcos viram `marco`. Run de **1** decisão NÃO colapsa
    (não é paredão). Um marco no meio quebra o cluster em dois (ordem cronológica
    preservada).
  - `resumoCluster(itens)` — "32 decisões de conferência · 29 aceitas · 3 rejeitadas".
  - `DECISAO_KINDS` = `{aceito, rejeitado, escolhido, editado}`.
- **`TimelineTab.tsx`** — renderiza `marco` como card normal e `cluster` como card
  **colapsável** (fechado por padrão; `ChevronRight` gira ao abrir; lista os
  eventos individuais ao expandir). Ponto da timeline do cluster usa ícone de
  lista, tom neutro.
- A humanização de cada evento (`historicoEventos.ts`) **não mudou** — continua a
  fonte das frases PT-BR.

## Validação

- `historicoBlocos.test.ts` — **6 verdes**: run contíguo colapsa; decisão isolada
  vira marco; marco no meio quebra em dois clusters; paredão de 77 → 1 cluster;
  `resumoCluster` conta total + breakdown; singular/plural.
- Suíte frontend completa: **70 passed** (11 arquivos). `tsc --noEmit` verde.
  `eslint --max-warnings=0` verde. `vite build` verde.

### Aceite (visual)
- Histórico do caso: marcos legíveis; bloco "N decisões de conferência [expandir]"
  no lugar do paredão de rejeições.

## Fora de escopo
- O trilho de auditoria (backend) **não** é alterado — só a apresentação.
- Botão "Consolidar na base": follow-up parado (decisão do André sobre para qual
  seção ele migra) — **não** tocado.
- `client-portal/` e `mobile/` congelados (ADR-009) — não tocados.
