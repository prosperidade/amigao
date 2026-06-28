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

### Dívida reportada (decisão posterior — NÃO executada)
1. `useAcoesKanban` / `useMoveAcaoStatus` em `lib/acoes/hooks.ts` ficaram sem
   consumidor de UI. Mantidos (arquivo compartilhado). Decidir se viram lixo a
   limpar ou se a aba global volta noutro formato.
2. Endpoint `GET /acoes/kanban` (backend) fica sem chamador de UI. Vivo e
   testado (`test_acoes.py`). Decidir destino numa tarefa de backend.
3. **Inconsistência de capitalização pré-existente** (não introduzida aqui): o
   sidebar usa "Quadro de ações" (a minúsculo) e o h1 da página "Quadro de Ações"
   (A maiúsculo) — assim era antes do #74. Mantido como estava; normalizar é
   decisão sua.

---

## VALIDAÇÃO
- `npx tsc --noEmit` → **verde** (exit 0).
- `npm run build` → ver status no PR (build lento na máquina; tsc é o gate de
  tipo/import e passou).
- Nenhuma referência pendente a `QuadroAcoesGlobal` ou rota `/acoes` (grep = 0).
- Sidebar com item único **"Quadro de ações" → /processes** (estado pré-#74); a
  aba nova sumiu. Nada fora do escopo do sidebar/rename foi tocado.
