# Sprint 1 — Ramo condicional E2 → E3 / E4 (Ficha 07)

**Data:** 2026-06-29
**Branch:** `feat/sprint1-ramo-e2`
**ADR:** [019](../adr/019-ramo-condicional-e2-coleta-ou-tecnico.md)

## Objetivo

Tornar a saída da E2 (Diagnóstico Preliminar) um **ramo**: se há documento
essencial pendente → Coleta Documental (E3); senão → pula direto ao Diagnóstico
Técnico (E4). O avanço segue **confirmado pelo consultor** (ADR-018); o ramo só
decide o **destino**.

---

## TASK 0 — Verificação (medido, com evidência)

### Q1 — A E2 já emite a lista de documentos essenciais pendentes?

**Parcialmente, e o sinal canônico já existe noutro lugar.** O `DiagnosticoAgent`
(chain `diagnostico_completo` da E2) emite só `checklist_documental` =
`acoes_remediacao` (lista de strings de ações), em `DiagnosticoPreliminarContent`
(`app/agents/diagnostico.py:883`) — **não** uma lista estruturada "faltam: [X, Y]".

Porém o sistema **já tem** o sinal canônico de "documento essencial pendente":
itens do **`ProcessChecklist`** com `required=True` e `status="pending"`. Gerado no
intake (`app/api/v1/intake.py:285-308`), definido por `ChecklistTemplate` por
`demand_type` (flag `required`). Já contado como `missing_docs` no kanban
(`processes.py:214`), no detalhe (`:332`) e no gate (`:709`); exposto como
`has_required_gaps` em `checklist_engine.get_checklist_status`.

→ **TASK 1 não foi necessária.** O ramo consome esse sinal existente. Nenhuma
regra de negócio nova inventada; nenhum prompt de agente tocado (config congelada).

### Q2 — A máquina suporta sucessor condicional?

**Não (antes).** `MACROETAPA_TRANSITIONS` mapeava cada etapa a uma lista mas era
usada como sucessor único (`next_macroetapa = nexts[0]`, `processes.py:751`). Linear.

### Q3 — O gate da E4 exige "E3 concluída"?

**Não.** `can_advance_macroetapa` / `compute_macroetapa_state` só inspecionam o
checklist da etapa **corrente** (completude + docs + diagnóstico assinado); não há
checagem de "etapa anterior concluída". A E4 é alcançável da E2 desde que a
transição seja válida.

**Conflito encontrado:** `list_macroetapa_blockers` tratava `documents_pending_
required > 0` como **blocker em todas as etapas** (`macroetapa.py:427`), inclusive
a E2 — o que **travaria** a E2 exatamente quando há doc pendente, contradizendo o
ramo (que existe para ir coletá-lo). Corrigido: na E2 o doc pendente **roteia**
(não trava).

---

## Implementação

**Backend — `app/models/macroetapa.py`:**
- `MACROETAPA_TRANSITIONS[diagnostico_preliminar]` → `[coleta_documental,
  diagnostico_tecnico]` (ambas válidas; coleta em 1º = default linear).
- `resolve_next_macroetapa(current, has_essential_pending)` — destino recomendado.
- `list_macroetapa_blockers(..., current_macroetapa)` — doc pendente não trava na
  `diagnostico_preliminar`; `can_advance_macroetapa` repassa `current_macroetapa`.

**Backend — `app/api/v1/processes.py`:**
- `_compute_can_advance`: `next_macroetapa = resolve_next_macroetapa(current,
  has_essential_pending=missing_docs > 0)`.
- Kanban: `list_macroetapa_blockers` recebe `current_macroetapa` (estado da E2 não
  vira `travada` por doc pendente).
- Import de `MACROETAPA_TRANSITIONS` (não mais usado) removido.

**Backend — `app/services/macroetapa_engine.py`:**
- `get_macroetapa_status`: coleta pulada (atrás da corrente, checklist 0%) →
  status `skipped` (o badge não mente).

**Frontend:**
- `quadro-types.ts`: `MacroetapaStep.status` ganha `'skipped'`.
- `MacroetapaStepper.tsx`: estilo próprio do `skipped` (dot tracejado,
  ChevronsRight, "· pulada").

## Validação

- `tests/models/test_macroetapa_gate.py` — unit do `resolve_next_macroetapa` e do
  roteia-não-trava (22 passes, inclui baseline do gate 0–100 recém-corrigido).
- `tests/api/test_ramo_e2.py` — **dois caminhos reais provados** contra o BD:
  E2→E3 (com doc pendente) e E2→E4 (sem; coleta vira `skipped`); E4 alcançável sem
  E3; `macroetapa_changed` auditado nos dois.
- Bateria de transição/gate verde: `test_ramo_e2 + test_movimentacao_card +
  test_macroetapa_gate + test_state_machines` = **97 passes**.
- Regressão `test_processes + test_regulatory` = **100 passes**.
- Frontend `tsc --noEmit` limpo + `npm run build` ok.

## Premissas preservadas

- Avanço confirmado pelo consultor (ADR-018) — ramo decide só destino.
- Gate da E2 recém-corrigido (checklist 100% + diagnóstico assinado) **intacto**.
- Config de agentes congelada — `DiagnosticoAgent` não tocado.
