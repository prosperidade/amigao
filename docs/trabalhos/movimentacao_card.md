# Fase 0.2 — Movimentação do Card (inicializar checklist + elo evento→card)

> Branch `feat/movimentacao-card` (base `main`, com o fix da consolidação #79–#81
> mergeado). Base de causa: `docs/trabalhos/diagnostico_movimentacao.md` (#78).
> Data: 2026-06-29.

## O que estava quebrado (medido no #78)
A máquina de 7 etapas (`Macroetapa`) já existia (1:1 com E1..E7, transições,
gate, mapa agente→etapa), mas o card não andava por **dois furos de fiação**:
1. O intake **não criava** `MacroetapaChecklist` → `macroetapa_checklists=0` →
   `can_advance` sempre `False` ("Etapa não iniciada (sem checklist)").
2. Faltava o **elo evento→card**: rodar os agentes não marcava o checklist nem
   deixava o card pronto. A lógica estava **invertida** — avançar o card é que
   disparava a chain (`processes.py:854`).

## Decisão de produto (fechada, André)
Ao terminar os agentes de uma etapa, o card fica **"PRONTO PARA AVANÇAR"** e o
**consultor confirma** o avanço. Não é automático. ("Agentes propõem; consultor
decide" — Princípio 1.)

---

## O que foi feito

### 1. Checklist inicializado no nascimento do caso
- **Novos casos:** `app/api/v1/intake.py` agora chama
  `initialize_macroetapa_checklists(db, process, tenant_id)` logo após criar o
  `Process` (cria os 7 `MacroetapaChecklist`). Sem isso o gate trava em False.
- **Casos legados (os 2 de prod):** backfill **lazy e idempotente**
  (`ensure_macroetapa_checklists`) nos caminhos de **leitura** da macroetapa
  (`GET /macroetapa/status` e `_compute_can_advance`/`GET /can-advance`). Na
  primeira vez que a UI abre o caso, os checklists são criados (self-healing).
  Escolhi lazy em vez de migration de dados: idempotente, sem acoplar a migration
  ao app, e cobre tanto os 2 atuais quanto qualquer caso órfão futuro.

### 2. Elo evento→card (`mark_stage_agents_done`)
- Novo `app/services/macroetapa_engine.py:mark_stage_agents_done(process, *, tenant_id, chain_name)`:
  marca o checklist da **etapa atual** como produzido pelos agentes (completa as
  ações, `agent_suggestion` preenchido, `completion_pct=100`). **Não** avança a
  macroetapa — só leva o card a `pronta_para_avancar`.
  - **Guard:** só marca se `chain_name` for a chain da etapa atual
    (`MACROETAPA_AGENT_CHAIN`) — um agente avulso de outra etapa não marca a
    corrente.
  - **Idempotente.** Persistência robusta: a coluna `actions` é `PortableJSON`
    sem `MutableList`, então o marcador constrói **dicts novos** + `flag_modified`
    (mutar in-place não era detectado como dirty — só o `completion_pct` persistia).
- **Worker hook:** `app/workers/agent_tasks.py:run_agent_chain` chama
  `mark_stage_agents_done` ao concluir a chain **com sucesso** (best-effort, em
  try/except próprio — nunca derruba a chain). Esse é o elo real assíncrono:
  terminou a chain da etapa → checklist marca → card "pronto".

### 3. De-inversão (rodar ≠ avançar) — ADR-018
- **Removido** de `POST /processes/{id}/macroetapa` (advance) o disparo de chain
  ao avançar (o antigo `_MACROETAPA_CHAINS` em `processes.py:854`). Avançar só
  move o card (com o gate já validado).
- **Novo** `POST /processes/{id}/macroetapa/run-agents`: dispara a chain da etapa
  atual (`MACROETAPA_AGENT_CHAIN`), async. Etapas sem chain (`coleta_documental`,
  `contrato_formalizacao`) retornam `dispatched=false` (são manuais). Audita
  `stage_agents_dispatched`.

### 4. UI mínima (painel da etapa — `WorkspaceRightPanel.tsx`)
- Botão **"Rodar agentes da etapa"** (POST `/macroetapa/run-agents`) — só aparece
  quando a etapa tem chain. Ao concluir, invalida o status/gate.
- Estado da etapa (badge `pronta_para_avancar`/`travada`/...) e botão **"Avançar
  etapa"** já existiam e já são gated por `can_advance` — agora destravam de fato
  porque o checklist passa a existir e a ser marcado. (Não construí as 6 abas —
  fase seguinte.)

### Travas respeitadas (seção 7 da Ficha 07)
- **E1→E2:** gate exige checklist da E1 completo (= agentes do intake rodados).
- **E2→E3/E4:** `diagnostico_preliminar`/`diagnostico_tecnico` exigem
  `RegulatoryDiagnosis.validated_at` (diagnóstico assinado) — e a consolidação,
  destravada por #79–#81, alimenta a base que o diagnóstico lê.
- **Travas "simples" (reportadas):**
  - O **ramo E2→E3|E4** (pular coleta quando não há doc essencial pendente) **não**
    foi implementado: as transições seguem **lineares** (`MACROETAPA_TRANSITIONS`
    é E2→E3→E4...). Implementá-lo exige permitir `diagnostico_preliminar→
    diagnostico_tecnico` + as abas de E3/E4 — fase seguinte.
  - **E5..E7** ficam com gate simples (checklist completo da etapa), sem a lógica
    fina de rota/proposta/contrato.

---

## Inconsistência observada (NÃO corrigida — fora de escopo, flag p/ André)
O gate compara `completion_pct < 1.0`, mas `completion_pct` é gravado como
**percentual 0–100** (`calculate_completion_pct` retorna `*100`). Logo o blocker
"checklist incompleto" só dispara quando o pct é praticamente 0 — um checklist a
20% passaria. Não afeta esta entrega (o marcador leva a etapa a **100**), mas é um
furo latente do gate. Vale uma decisão separada: tratar `completion_pct` como
fração (0–1) **ou** ajustar o gate para `< 100`. Não toquei (a regra era não
refatorar o que está fora do escopo da movimentação).

---

## Validação (aceite)
Suíte nova `tests/api/test_movimentacao_card.py` (8 testes, verdes), provando o
ciclo de forma determinística (sem LLM/broker):
- caso nasce/recebe os **7 checklists** (novo + backfill lazy do legado);
- `mark_stage_agents_done("intake")` → checklist 100% → `can_advance=True`,
  `current_state="pronta_para_avancar"`;
- guard de chain estranha (no-op);
- `POST /macroetapa/run-agents` dispara a chain da etapa (audit) e **não** dispara
  em etapa manual;
- **card anda E1→E2** após os agentes + confirmação, com `macroetapa_changed`
  auditado, e **sem** disparar chain no avanço (de-inversão);
- avanço **bloqueado** (409) antes de rodar os agentes.

Regressão: `test_macroetapa_gate` + `test_agent_tasks_retry` verdes;
`test_intake`/`test_regulatory`/`test_processes` verdes. `tsc` + `build` verdes.

### Como funciona o caso real (com Celery + chaves)
1. Consultor abre o caso → checklists existem (intake novo) ou self-heal (legado).
2. Clica **"Rodar agentes da etapa"** → `run-agents` enfileira a chain (ex. E1 =
   `intake`).
3. Worker conclui a chain → `mark_stage_agents_done` marca o checklist → card
   `pronta_para_avancar`.
4. Consultor clica **"Avançar etapa"** → gate valida → `macroetapa` sobe → o card
   muda de coluna no Quadro. `macroetapa_changed` registrado.
