# Reverter o vacilo do sidebar (rename "Casos" + aba nova "Quadro de Ações")

> Branch `fix/reverter-sidebar-quadro-acoes` (base `main`). Data: 2026-06-28.
> Reverte **somente** as duas mudanças de UI do PR #74 (`c21b6a8`) que não
> deviam ter entrado. Backend da Ficha 07 (entidade `Acao`) **preservado**.

---

## FASE 1 — MAPA (o que o #74 tocou)

PR #74 ("feat(ficha07): Aba Ações + Quadro de Ações global") fez muito além da UI
do sidebar. Separei o que reverter do que preservar.

### (a) O RENAME — board /processes "Quadro de ações" → "Casos"

Dois pontos, ambos **string de label** (rota e componente NÃO mudaram):

| # | Arquivo | O que o #74 fez |
|---|---------|-----------------|
| 1 | `frontend/src/layouts/PrivateLayout.tsx:50` | item do sidebar `{ name: 'Quadro de ações', path: '/processes' }` → `{ name: 'Casos', ... }` (+ 2 linhas de comentário) |
| 2 | `frontend/src/pages/Processes/QuadroAcoes.tsx:133` | `<h1>` da página `Quadro de Ações` → `Casos` |

Não há i18n/chave de tradução (o projeto usa strings inline), nem breadcrumb, nem
teste referenciando esses rótulos (grep em `*.test.tsx` = 0).

### (b) A ABA NOVA — sidebar "Quadro de Ações" → /acoes

| # | Arquivo | O que o #74 adicionou |
|---|---------|-----------------------|
| 1 | `frontend/src/layouts/PrivateLayout.tsx:51` | item de menu `{ name: 'Quadro de Ações', icon: ListChecks, path: '/acoes' }` (+ import `ListChecks`) |
| 2 | `frontend/src/App.tsx:12,50` | import + `<Route path="/acoes" element={<QuadroAcoesGlobal />} />` |
| 3 | `frontend/src/pages/Processes/QuadroAcoesGlobal.tsx` | componente novo (204 linhas): kanban de **ações** por status, todos os casos |

O que a aba renderiza: `QuadroAcoesGlobal` consome `useAcoesKanban` + `useMoveAcaoStatus`
de `@/lib/acoes/hooks.ts` → endpoint backend `GET /acoes/kanban` e `PATCH .../status`.

### (3) DEPENDÊNCIAS — a pergunta que evita derrubar o que não pode

- **`QuadroAcoesGlobal.tsx`**: referenciado **só** por `App.tsx` (a rota). Após
  remover a rota, fica **órfão** e **não é compartilhado** → seguro deletar.
- **`@/lib/acoes/hooks.ts` e `@/lib/acoes/types.ts`**: **COMPARTILHADOS** — a aba
  "Ações" do workspace (`AcoesTab.tsx`, que **fica**) importa `useAcoes`,
  `useCreateAcao`, `useGenerateAcoes` (hooks) e vários tipos. **NÃO mexer.**
  - `useAcoesKanban` / `useMoveAcaoStatus` ficam como exports não usados após a
    remoção — inofensivos (tsc `noUnusedLocals` não acusa export não usado; build
    verde). Não removo: é arquivo compartilhado e a remoção é limpeza
    backend-adjacente fora do escopo. **Reportado para decisão posterior.**
- **Backend Ficha 07** (model `Acao`, migration `ac7f01b9e3d5`, endpoints
  `/processes/{id}/acoes/generate`, `/triagem`, `/acoes/kanban`): referenciado
  pela aba "Ações" do workspace e pela própria entidade. **NÃO tocar** — a tarefa
  é só de UI do sidebar. O endpoint `/acoes/kanban` fica vivo, sem consumidor de
  UI por ora (a aba "Ações" do workspace usa `/acoes` de listagem, não o kanban).

### (4) MAPA DE AÇÃO

- **Para reverter (a):** `PrivateLayout.tsx` (label) + `QuadroAcoes.tsx` (h1).
- **Para deletar (b):** `PrivateLayout.tsx` (item + import `ListChecks`),
  `App.tsx` (import + rota), `QuadroAcoesGlobal.tsx` (componente órfão).
- **NÃO toco, e por quê:**
  - `lib/acoes/hooks.ts`, `lib/acoes/types.ts` → compartilhados com `AcoesTab`.
  - `AcoesTab.tsx`, `AcaoCard.tsx` (aba "Ações" do workspace) → não é o sidebar.
  - Todo o backend `Acao` (model/migration/endpoints) → fora do escopo; só UI.
  - `Settings/index.tsx:424` (`<option value="quadro_acoes">`) → preexistente,
    não foi tocado pelo #74; é outra coisa (preferência de notificação).

---

## FASE 2 — O QUE FOI FEITO

### Revertido (a)
- `PrivateLayout.tsx`: item do sidebar volta a `{ name: 'Quadro de ações',
  icon: Briefcase, path: '/processes' }` (string exata pré-#74); comentário do
  #74 removido.
- `QuadroAcoes.tsx`: `<h1>` volta a `Quadro de Ações`.

### Removido (b)
- `PrivateLayout.tsx`: item `Quadro de Ações → /acoes` deletado + import
  `ListChecks` removido (só ele usava).
- `App.tsx`: rota `/acoes` + import `QuadroAcoesGlobal` removidos.
- `QuadroAcoesGlobal.tsx`: **deletado** (órfão, não compartilhado).

> Os três arquivos editados voltaram ao **blob hash exato pré-#74**
> (`App.tsx c9775ce`, `PrivateLayout.tsx 1ccf090`, `QuadroAcoes.tsx aba40a8`) —
> a UI do sidebar é o inverso limpo do #74.

### Preservado (e por quê)
- `lib/acoes/hooks.ts`, `lib/acoes/types.ts` — compartilhados com `AcoesTab`.
- `AcoesTab.tsx`, `AcaoCard.tsx` — aba "Ações" do workspace, fora do escopo.
- Backend Ficha 07 inteiro (`Acao`, migration, `/acoes/*`) — intacto.

---

## FASE 3 — DÍVIDA RESOLVIDA (2ª passada, decisão do André: apagar agora)

> O 1º commit deixou os hooks/endpoint do quadro global como código órfão e a
> capitalização inconsistente. O André pediu para **resolver agora, sem registrar
> dívida**. Antes de apagar, verifiquei (grep) cada símbolo.

### Verificação (medição antes de apagar)
- `useAcoesKanban` / `useMoveAcaoStatus`: referenciados **só** na própria
  definição (`lib/acoes/hooks.ts`) — zero consumidores. `AcoesTab` usa
  `useAcoes`/`useCreateAcao`/`useGenerateAcoes`/`useUpdateAcao`/`useTriarAcao`,
  **não** o kanban. → órfãos.
- Tipos `AcaoKanbanCard`/`Column`/`Response` (front e back): usados só pelos
  hooks/endpoint removidos. `ACAO_STATUS_ORDER` **é** usado por `AcaoCard` →
  **preservado**. → tipos kanban órfãos.
- Endpoint `GET /acoes/kanban`: único route do `acoes_router`; helper
  `_STATUS_LABELS` e imports `Client`/`Property` em `acoes.py` só serviam a ele.
  `Process`/`Query`/`AcaoStatus`/`AcaoTipoTriagem` seguem usados → preservados.

### Removido (órfão de verdade)
- **Front:** `useAcoesKanban`, `useMoveAcaoStatus`, a key `acoesKeys.kanban()` e
  suas invalidações nos hooks sobreviventes, o import `AcaoKanbanResponse`
  (`hooks.ts`); tipos `AcaoKanbanCard`/`Column`/`Response` (`types.ts`).
- **Back:** endpoint `acoes_kanban` + `acoes_router` (e seu `include_router` em
  `main.py`), helper `_STATUS_LABELS`, imports `Client`/`Property` e
  `AcaoKanban*` (`acoes.py`); classes `AcaoKanbanCard`/`Column`/`Response`
  (`schemas/acao.py`). Docstrings de módulo atualizadas.
- **Testes:** `test_kanban_*` removidos; a asserção de isolamento de tenant da
  **lista do caso** (endpoint que fica) foi preservada como
  `test_list_acoes_tenant_isolation` (sem perda de cobertura).
- **Docs:** linha `/acoes/kanban` em `API_v1.md` e a descrição do quadro global
  em `ficha07_acoes.md` atualizadas.

### Capitalização normalizada
- Sidebar **e** h1 agora "Quadro de Ações" (A maiúsculo) — rótulo único e
  coerente. (A inconsistência pré-#74 some.)

### Preservado (compartilhado / em uso — confirmado por grep)
- `lib/acoes/hooks.ts`/`types.ts` (resto), `AcoesTab`, `AcaoCard`,
  `ACAO_STATUS_ORDER`/`*_LABELS`, e todo o backend Ficha 07 menos o kanban
  (model `Acao`, migration, `/processes/{id}/acoes*`).

**Resultado:** zero código órfão, zero dívida pendente. `REGISTRO_DIVIDAS` não
ganha item — a dívida foi resolvida, não registrada.

---

## VALIDAÇÃO
- `npx tsc --noEmit` → **verde** (exit 0).
- `npm run build` → **verde** (exit 0).
- `pytest tests/api/test_acoes.py` → **verde** (ver status no PR).
- Nenhuma referência de código a `QuadroAcoesGlobal`, `/acoes/kanban`,
  `useAcoesKanban`, `useMoveAcaoStatus` ou `AcaoKanban*` (grep = 0; só docs).
- Sidebar com item único **"Quadro de Ações" → /processes**; a aba nova sumiu.
  Nada fora do escopo do sidebar/rename/limpeza-órfã foi tocado.
