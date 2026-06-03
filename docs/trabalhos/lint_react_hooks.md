# Trabalho — zerar os erros de lint react-hooks (CI verde)

> Arquivo único de trabalho. Erro → classificação → decisão → validação → status.
> Branch: `fix/lint-react-hooks` (base `main`). Data: 2026-06-03.
> Escopo: só a camada de hooks/apresentação. Backend/OCR/chain/storage intactos.
> **Backend Lint não é deste PR** (dívida separada).

## Problema

O CI **Frontend — Lint + Typecheck + Build** estava cronicamente vermelho com
6 problemas (5 erros + 1 warning) — `npm run lint` roda com `--max-warnings=0`,
então o warning também quebra. Pré-existiam desde antes dos PRs #52/#53/#54 e
mascaravam erros novos de verdade.

## Os 5 pontos, classificação e decisão

| # | Arquivo:linha | Regra | Classe | Decisão |
|---|---|---|---|---|
| 1 | `IntakeWizard.tsx:1137` | `react-hooks/purity` | impureza no render | **corrigir estrutura** |
| 2 | `AlertaCard.tsx:106` | `react-hooks/set-state-in-effect` | setState em effect | **corrigir estrutura** |
| 3 | `QuadroAcoes.tsx:65` | `react-hooks/exhaustive-deps` | ref instável | **estabilizar** |
| 4 | `CredentialModal.tsx:45` | `react-hooks/set-state-in-effect` | setState em effect | **corrigir estrutura** |
| 5 | `PriorityStep.tsx:9,16` | `react-refresh/only-export-components` | export não-componente | **mover constantes** |

Nenhum exigiu `eslint-disable`. Nenhuma dep foi adicionada cegamente.

### 1. IntakeWizard — `DraftExpirationBadge` lia `Date.now()` no render
`const diffMs = new Date(expiresAt).getTime() - Date.now()` — chamar `Date.now()`
direto no corpo do componente é impuro (resultado muda a cada render).
**Fix:** capturar "agora" uma vez no mount com lazy init
`const [now] = useState(() => Date.now())`. O badge é estático (não tica), então
ler o tempo uma vez no mount é correto e suficiente. Sem loop (one-shot).

### 2. AlertaCard — sync server→form via `useEffect` + setState
O effect populava o form (`decisaoSelecionada`, `justificativa`) a partir de
`decisionQuery.data`. **Fix estrutural (sem effect):** padrão React documentado
de "ajustar estado durante o render quando dados externos mudam" — sentinela
`syncedData` comparada a `decisionQuery.data`; ao diferir, sincroniza e atualiza
o sentinela. Sentinela inicia em `undefined`: enquanto carrega
(`data === undefined`) nada sincroniza; quando chega objeto (inclusive **cache no
1º render**) popula; quando vem `null` limpa. **Sem loop:** após igualar
`syncedData` a `data`, a condição fica falsa. Semântica idêntica à do effect
antigo (loading/cache/null cobertos).

### 3. QuadroAcoes — `columns` recriava array a cada render
`const columns = kanbanData?.columns ?? []` cria um `[]` novo a cada render
quando `kanbanData` é undefined → o `useMemo` dependente (`[columns]`, opções de
filtro) recalcula sempre. **Fix:** `useMemo(() => kanbanData?.columns ?? [], [kanbanData])`.
Estabiliza a referência; recomputa só quando `kanbanData` muda. **Sem loop**
(useMemo, não setState).

### 4. CredentialModal — init do form via `useEffect` + setState
O effect preenchia o form quando `credential`/`mode` mudavam. **Fix estrutural
(sem effect):** lazy init `useState(() => ...)` a partir das props **+** o pai
passa `key={mode==='edit' ? 'edit-'+id : 'create'}`. Ao abrir outra credencial o
modal **remonta**, o initializer roda de novo e reseta o form — solução canônica
React para "resetar estado de form quando a entidade muda". Comportamento
preservado, inclusive trocar de credencial sem fechar.

### 5. PriorityStep — exportava constantes junto do componente
`react-refresh/only-export-components`: um arquivo de componente não pode exportar
valores não-componente (quebra o Fast Refresh). **Fix:** `URGENCIA_OPTIONS` e
`VALOR_ESTRATEGICO_OPTIONS` movidas para `priorityOptions.ts`; `PriorityStep.tsx`
e `IntakeWizard.tsx` passam a importar de lá. Sem mudança de comportamento.

## Validação (real)

- `./node_modules/.bin/eslint` nos 7 arquivos tocados → **0** problemas.
- `npm run lint` (projeto, `--max-warnings=0`) → **verde**.
- `npx tsc --noEmit` → **verde**. `npm run build` → **verde** (1913 módulos).
- Suite completa: **48/48** verde (sem regressão).
- **Anti-loop** nas duas telas que mexem em setState (maior risco): testes
  `AlertaCard.test.tsx` + `CredentialsTab/index.test.tsx` → **11/11** sem
  `Maximum update depth exceeded` / `too many re-renders`. As outras três
  mudanças são estruturalmente incapazes de loop (useMemo reduz renders; lazy
  init é one-shot; PriorityStep só moveu constantes).

## Status

**Concluído.** 0 erros react-hooks/react-refresh; CI frontend deve ficar verde.
tsc + build + 48/48 testes verdes; nenhuma tela em loop. Nenhum `eslint-disable`
usado. **Backend Lint segue como dívida separada** (fora deste PR).
