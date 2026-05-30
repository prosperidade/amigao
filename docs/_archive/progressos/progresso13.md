# Progresso 13 — PROMPT_9: UI da camada 2 do Princípio 1

## Projeto: Regente Ambiental
## Referências: ADR-012 · #17 (PROMPT_8) · #19 (PROMPT_6 revisão) · #20 (PROMPT_7)

---

## Objetivo da rodada

Tornar usável pelo consultor o que o backend já fazia. Antes do PROMPT_9
o painel via o `RegulatoryDiagnosis` mas não tinha tela pra:
- adjudicar o `status_achado` (`suspeita → confirmada`/`descartada`/…),
- decidir alerta por alerta com os 5 botões da P4,
- registrar justificativa quando exigida (#19),
- assinar o diagnóstico passando pelo gate camada 2.

Esta rodada materializa o ciclo do Princípio 1 — "a IA propõe, o humano
decide e assina, alerta por alerta" — **consumindo contrato existente,
sem inventar backend**.

---

## Estado pré-rodada

- `main` em `49a7e6a` (PR #9 do PROMPT_7 mergeado).
- `feat/prompt8-coerencia-status` pushada, em revisão (PR pra abrir;
  o PROMPT_9 foi baseado nessa branch pra espelhar o pós-merge).
- Suite backend 635/635 verde. Frontend tinha 4 arquivos de teste
  (Vitest), 21 testes — todos passando.
- Forks resolvidos antes pelo Andre:
  - **Issue × múltiplos processos no PropertyHub:** listar TODOS os
    processos, mais recente primeiro, com verbo-por-estado
    (`Decidir`/`Ver`) nos chips. Apontar pra "um processo ativo"
    contradiria literalmente o ADR-012.
- Forks deixados pro agente decidir:
  - Transições de `status_achado` a expor — escolhi expor os 5 valores
    no `<select>` (deixa o consultor reverter se errar).
  - Decisão opcional em não-críticos — mantive os 5 botões disponíveis
    para qualquer severidade (o gate só EXIGE em crítico, mas não há
    razão pra esconder a feature em `alto`/`atencao`/`informativo`).

---

## Sprints executados (PROMPT_9 — 26/05)

### Onda A — camada de dados (`lib/regulatory/`)

`types.ts` espelha o contrato — 5 enums + `RegulatoryIssue` +
`ProcessIssueDecision` + payloads + `DiagnosisGate422Detail` (shape
do 422 do gate, distinto do 422 das Regras A/B). Sets
`ACHADOS_QUE_HABILITAM_DECISAO` e `DECISAOS_QUE_EXIGEM_JUSTIFICATIVA`
viraram o coração da Regra B preventiva e do #19 client-side.

`labels.ts` — pt-BR + Tailwind. Severidade: `informativo`/`atencao`
neutros, `alto` em orange, `critico` em red. Tom forte reservado pro
crítico — não afoga a tela em vermelho. `SEVERITY_ORDER` permite sort
com críticos no topo.

`hooks.ts` — React Query: `useIssues`, `useUpdateIssue`, `useDecision`
(404 → `null` porque ADR-012), `useUpsertDecision`, `useDiagnoses`,
`useValidateDiagnosis`. Query keys centralizadas em `regulatoryKeys`.
`useUpsertDecision` invalida `diagnoses` (o gate cruza as duas).

### Onda B — aba "Alertas" no ProcessDetail

`AlertasTab` busca `useIssues(propertyId, 'open')`, ordena por
severidade decrescente (críticos no topo, desempate por `detected_at`),
renderiza um `AlertaCard` por issue.

`AlertaCard` é o coração da tela:
- Cabeçalho: severidade + família + codigo_alerta + documentos_cruzados.
- Status perenes (2 `<select>`): mutation `PATCH /properties/.../issues/{id}`.
  422 da Regra A renderiza inline em vermelho perto do controle (não
  em toast — é específico).
- Decisão neste processo: `useDecision` carrega estado atual (`null`
  se 404). 5 radios + textarea de justificativa. Mutation
  `PUT /processes/.../decision`.

**Regra B preventiva (coração da rodada):**
```tsx
const decisaoBloqueada = !ACHADOS_QUE_HABILITAM_DECISAO.has(issue.status_achado);
// = enquanto suspeita, fieldset disabled + hint claro
```
Quando o consultor adjudica o achado, `useUpdateIssue` invalida
`issues` → re-render → fieldset libera sozinho. O 422 do backend é
rede de segurança, não primeira linha de defesa.

**#19 client-side:** textarea required quando
`decisao in {ignorar_justificado, fora_escopo}`. Botão "Registrar
decisão" disabled enquanto vazia (strip whitespace coerente com
`str_strip_whitespace=True` do Pydantic).

`TabKey` ganha `'alertas'` no ProcessDetail (block_type `active`,
entre `diagnosis` e `tasks`).

### Onda C — Gate de assinatura + PropertyHub.AnalysesTab aumentado

**`DiagnosisAssinatura`** no topo do `DiagnosisTab`:
- `useDiagnoses(processId)` → pega versão mais nova.
- Sem diagnóstico → render silencioso.
- Já validado → card emerald "Diagnóstico vN assinado em {data}".
- Não validado → botão "Assinar vN" com badge "N pendentes" calculado
  via `useQueries` cruzando críticas × decisões.
- Click → `useValidateDiagnosis`. 200 → toast success. 422 com
  `detail.alertas_pendentes` (shape do gate camada 2) → modal lista.
  Click no item dispara `onGoToAlerta(id)` → ProcessDetail troca
  para aba 'alertas' + `scrollIntoView` do card `#alerta-{id}`.
- **Backend é a autoridade:** cálculo client-side é heurística pra
  badge; se divergir do 422 (cache stale), confiamos no 422.

**`PropertyHub.AnalysesTab` aumentado** — era stub mostrando 5 casos
com título; virou lente do ADR-012:
- Lista issues do imóvel (críticos no topo).
- Por issue: 2 status perenes como labels read-only.
- Chips de TODOS os processos da property (mais recente primeiro):
  "Processo #N (demand) · {decisão|pendente} · Decidir/Ver" com
  verbo-por-estado via `useDecision`. Cor emerald = decidida, amber
  = pendente.
- Teto visual: 5 chips visíveis + "+N mais" expansível.
- Read-only — click leva pra aba Alertas do processo (NÃO duplica
  a tela de decisão).

### Onda D — Testes (Vitest + RTL)

`AlertaCard.test.tsx` (7 testes):
- Regra B desabilita decisão em suspeita (hint visível, radios e botão disabled).
- `it.each(['confirmada','descartada','resolvida','ignorada'])` →
  decisão habilita (cobre o conjunto `ACHADOS_QUE_HABILITAM_DECISAO`
  exatamente).
- Justificativa (#19): submit disabled enquanto vazia em
  `ignorar_justificado`; libera ao preencher; volta a bloquear com só
  espaços.
- `corrigir_antes` NÃO exige justificativa — submit livre.

`DiagnosisAssinatura.test.tsx` (3 testes):
- 422 do gate → modal abre com `alertas_pendentes`; click no item
  dispara `onGoToAlerta(99)`.
- Já validado → card "Diagnóstico v2 assinado" + sem botão "Assinar".
- Sem diagnóstico → render silencioso.

**Infra — runner `scripts/run-vitest.mjs`:** jsdom 27 puxa
`@asamuzakjp/css-color` (CJS) que requer `@csstools/css-calc` (ESM),
o que Node 22.11 só aceita com `--experimental-require-module`.
`poolOptions.execArgv` não propaga aos workers Tinypool — só
`NODE_OPTIONS` (env var). Runner injeta a flag e re-exec do Vitest CLI.
Cross-platform (sem `VAR=val cmd`). Registrado como #22 no
REGISTRO_DIVIDAS com marco condicional (jsdom upstream OU Node 22.12+).

---

## Resultado

- Frontend Vitest+RTL: **31/31 verde** (4 arquivos pré-existentes +
  2 novos do PROMPT_9, 21 + 10 testes).
- Typecheck `tsc --noEmit` limpo.
- Backend intocado — nenhum endpoint novo. Sem migration, sem ADR
  novo. `MODELO_DE_DADOS` e `API_v1` intocados (UI é consumidora).

## Decisões arquiteturais (resumo)

- **Regra B preventiva, não reativa** — `disabled` no fieldset evita
  travar no gate sem caminho; 422 é rede de segurança.
- **Backend é a autoridade do gate** — cálculo client-side é
  heurística; o 422 com lista decide.
- **Listar TODOS os processos no PropertyHub** — eleger "ativo"
  reintroduziria a perenidade que a Isis rejeitou.
- **#19 em 3 camadas** — schema (Pydantic), endpoint (rede),
  UI client-side (preempção).
- **Cache compartilhado** entre AlertaCard, DiagnosisAssinatura e
  IssueProcessChip via `regulatoryKeys.decision(pid, iid)`.

## Dívidas reveladas

- **#22** — workaround Vitest `--experimental-require-module`,
  registrado P3 com marco condicional (jsdom upstream OU Node 22.12+).

## Arquivos tocados

**Camada de dados (commit 1):**
- `frontend/src/lib/regulatory/types.ts` (novo)
- `frontend/src/lib/regulatory/labels.ts` (novo)
- `frontend/src/lib/regulatory/hooks.ts` (novo)

**Aba Alertas (commit 2):**
- `frontend/src/pages/Processes/AlertaCard.tsx` (novo)
- `frontend/src/pages/Processes/AlertasTab.tsx` (novo)
- `frontend/src/pages/Processes/ProcessDetailTypes.ts` (+ 'alertas' no TABS)
- `frontend/src/pages/Processes/ProcessDetail.tsx` (TabKey + render)

**Gate + PropertyHub (commit 3):**
- `frontend/src/pages/Processes/DiagnosisAssinatura.tsx` (novo)
- `frontend/src/pages/Processes/DiagnosisTab.tsx` (plug + callback)
- `frontend/src/pages/Processes/ProcessDetail.tsx` (callback onGoToAlerta)
- `frontend/src/pages/Properties/PropertyHub.tsx` (AnalysesTab aumentado +
  IssueProcessChip + AnalysesIssueRow)

**Testes (commit 4):**
- `frontend/src/pages/Processes/AlertaCard.test.tsx` (novo)
- `frontend/src/pages/Processes/DiagnosisAssinatura.test.tsx` (novo)
- `frontend/scripts/run-vitest.mjs` (novo)
- `frontend/package.json` (scripts test → runner)
- `frontend/vitest.config.ts` (comentário explicando o workaround)

**Docs (commit 5):**
- `docs/estado/ESTADO_ATUAL.md`
- `docs/estado/progressoIA.md`
- `docs/arquitetura/FLUXOS_E2E.md` (Fluxo 2 com o passo de UI)
- `docs/arquitetura/GOVERNANCA_DOCUMENTAL.md` (índice 1..13)
- `docs/REGISTRO_DIVIDAS.md` (#22 P3, header atualizado)
- `docs/_archive/progressos/progresso13.md` (este arquivo)

**NÃO tocados (deliberadamente):**
- `docs/arquitetura/API_v1.md` — contrato inalterado (UI é consumidora).
- `docs/arquitetura/MODELO_DE_DADOS.md` — sem schema change.
- Sem novo ADR — implementa Princípios 1+2 já firmados.
