# Auditoria — UI de Credenciais + UI do Intake + Design System

> Data: 2026-05-31
> Branch: `audit/ui-credenciais-intake-design` (base `main`)
> Modo: read-only. Nenhuma mudança em código de aplicação.
> Escopo: confrontar o que o chat/agente afirmou contra o estado real do `frontend/`.

---

## Frente A — UI de Credenciais (estado real)

Backend de referência: `app/api/v1/credentials.py`, montado em
`app/main.py:140` com prefixo **`/api/v1/credentials`** e tag `"Credenciais de Portal"`.
Entidade: `Credential` (portal, label, login, password_encrypted, url, notes) por cliente, com tenant isolation.

| # | O que checa | Status | Onde no código | Observação factual |
|---|---|---|---|---|
| A1 | Existe UI de credenciais de portal em `frontend/src`? | **FALTA** | — | `grep` por `credential\|credenciai\|login_username\|has_password` em `frontend/src` → **0 arquivos**. Nenhum componente, página ou hook. |
| A2 | A UI de Configurações cobre credenciais de portal? | **FALTA** | `frontend/src/pages/Settings/index.tsx` (735 linhas) | Settings tem 6 abas (`profile, billing, notifications, operational, ai, security`). A aba `security` (`SecurityTab`, linha 651) só tem **"Trocar senha"** do próprio usuário (`POST /auth/password-change`). Não há CRUD de credenciais de portal de cliente. |
| A3 | Há UI de credenciais no Cliente Hub / páginas de cliente? | **FALTA** | `frontend/src/pages/Clients/ClientHub.tsx`, `Clients/index.tsx` | `grep` por `credencial/credential/portal/senha do portal` nas páginas de Clients → 0 ocorrências. |
| A4 | Algum lugar do frontend consome os endpoints `/credentials`? | **FALTA** | — | `grep -rn "credentials" frontend/src` → **0 ocorrências**. Os 5 endpoints do backend não são chamados por nenhum código de frontend. |
| A5 | POST `/api/v1/credentials` (criar) | EXISTE (backend) / **sem UI** | `credentials.py:70` | `client_id` vai no body (`CredentialCreate`), não no path. Spec da auditoria citava `POST /clients/{client_id}/credentials` — o path real é outro. |
| A6 | GET `/api/v1/credentials?client_id=` (listar) | EXISTE (backend) / **sem UI** | `credentials.py:104` | Filtro opcional por `client_id` via query string. |
| A7 | GET `/api/v1/credentials/{cred_id}` | EXISTE (backend) / **sem UI** | `credentials.py:119` | — |
| A8 | PATCH `/api/v1/credentials/{cred_id}` | EXISTE (backend) / **sem UI** | `credentials.py:128` | Senha só atualiza se vier não-vazia; ausente/vazia preserva a atual. |
| A9 | DELETE `/api/v1/credentials/{cred_id}` | EXISTE (backend) / **sem UI** | `credentials.py:150` | Soft delete (`deleted_at`). |
| A10 | UI exibe `has_password` ou tenta revelar a senha? | **N/A — sem UI** | `credentials.py:26-35` | O serializer `_to_response` expõe `has_password=bool(cred.password_encrypted)` e **nunca** a senha. Não há endpoint de revelação. Como não há UI, não há consumo de algo inexistente. |
| A11 | Mudanças não-commitadas relacionadas a credenciais no worktree | **FALTA** | — | `git status` no início: worktree limpo em `main`. Nenhuma alteração em curso no disco. |

**Constatação A:** A afirmação do chat de que "a UI de credenciais não existe" está **correta para o frontend**. A afirmação do André de que "ela JÁ EXISTE em Configurações" não se confirma no código: o que existe em Configurações é **troca da própria senha do usuário** (`SecurityTab` → `/auth/password-change`), que é coisa diferente de gerenciar credenciais de portal de cliente. O backend completo existe; o frontend correspondente não. Não há mudança não-commitada em curso no worktree.

---

## Frente B — UI do Intake (estado real × especificação Isis)

Componente renderizado na rota real: `App.tsx:53` →
`<Route path="/intake" element={<IntakeWizard />} />` →
`frontend/src/pages/Intake/IntakeWizard.tsx` (909 linhas). **Há um único wizard de intake**; não foi encontrada rota/página alternativa concorrente.

| # | Item da spec Isis | Status | Onde no código | Observação factual |
|---|---|---|---|---|
| B1 | Wizard em 2 colunas | **PARCIAL** | `IntakeWizard.tsx:441`, `898-903` | Grid `lg:grid-cols-[1fr_360px]` aplicado **somente quando `draftId` existe** (`${draftId ? 'lg:grid-cols-[1fr_360px]' : ''}`). A 2ª coluna (`PreviewPanel`) só renderiza com `draftId` (linha 899). Nos Steps 0–3 de fluxos sem rascunho salvo, a tela é **uma coluna**. O draft é auto-salvo ao entrar no Step 4 (`ensureDraftBeforeStep4`, linha 885). |
| B2 | `PreviewPanel` importado e renderizado | **EXISTE** | import `IntakeWizard.tsx:7`; render `:901` | `<PreviewPanel draftId={draftId} manualValues={previewManualValues} />`. Arquivo: `frontend/src/components/IntakeWizard/PreviewPanel.tsx` (162 linhas). |
| B3 | Confidence score por campo + badge colorido | **EXISTE** | `PreviewPanel.tsx:56-63, 115, 127` | `confidenceBadge()`: `>0.9` → emerald; `>=0.7` → yellow; `<0.7` → red. Mostra % (`Math.round(confidence*100)`). |
| B4 | Documento de origem por campo | **EXISTE** | `PreviewPanel.tsx:18, 132-133` | `source_document_name` exibido com prefixo 📄. |
| B5 | Reconciliação manual×IA via modal (Opção A) | **EXISTE** | `PreviewPanel.tsx:11, 150-157`; `ReconcileModal.tsx` (102 linhas) | `ReconcileModal` **não** é importado pelo `IntakeWizard` diretamente — é importado e renderizado **dentro do `PreviewPanel`** (`import` linha 11, render linha 150), aberto quando `f.diverges_from_manual` (linha 135). Logo, está wired pela cadeia Wizard→PreviewPanel→ReconcileModal. |
| B6 | `PriorityStep` — 2 eixos independentes | **EXISTE** | import `IntakeWizard.tsx:6`; render `:578`; `PriorityStep.tsx` (90 linhas) | Exporta `URGENCIA_OPTIONS` e `VALOR_ESTRATEGICO_OPTIONS`. FormState tem `urgency` e `valor_estrategico` separados (`:58-59`). Comentário no código: "decisão Isis 2026-05-28". |
| B7 | E-mail obrigatório (validação) | **EXISTE** | `IntakeWizard.tsx:387`, campo `:530` | `canGoNext()` no Step 1 (cliente novo) exige `!!form.client_email.trim()` além de nome+telefone+tipo. Campo `<Input label="E-mail" type="email" required-by-gate>`. |
| B8 | Áudio anexável (presigned upload → audio_url) | **EXISTE** | `IntakeWizard.tsx:62, 146, 355-367, 730-754` | Input `accept="audio/*"` (linha 744); presign + `PUT` direto ao storage; `setForm(... audio_url: presign.storage_key)` (linha 367); `document_type: 'audio_entrevista'`. Anexado no Step 4 (Documentos). |
| B9 | Remoção do campo "Sintoma" | **EXISTE (removido)** | — | `grep -i "sintoma"` no wizard → 0 ocorrências. |
| B10 | Remoção do campo "Dor" | **EXISTE (removido)** | — | `grep -i "\bdor\b"` no wizard → 0 ocorrências. |
| B11 | Remoção de "Possui arquivo do CAR" | **EXISTE (removido)** | `IntakeWizard.tsx:70` | Não há checkbox "possui arquivo do CAR". Existe `property_car` (número/código do CAR do imóvel), que é dado de imóvel, não o flag removido. |
| B12 | 5 fluxos de cadastro (IntakeSource) preservados | **EXISTE** | `IntakeWizard.tsx:14-19, 76-112` | `ENTRY_TYPE_OPTIONS` com 5 valores, todos `available: true`. |

**Constatação B:** A UI do intake **na rota real (`/intake`)** contém praticamente todos os itens da spec Isis: PreviewPanel com confidence/origem, ReconcileModal (via PreviewPanel), PriorityStep de 2 eixos, e-mail obrigatório, áudio com presigned upload, e os 3 campos antigos removidos. O relato do agente de que o PR foi mergeado com essas peças **bate com o código presente em `main`**.

O único item **PARCIAL** é o layout de 2 colunas: o preview lateral só aparece **depois** que existe um `draftId` (auto-salvo ao entrar no Step 4, ou no fluxo "Importar documentos"). Nos primeiros passos de um cadastro novo a tela é de coluna única — o que é consistente com um usuário relatar "não vejo o preview lateral" se observou apenas as etapas iniciais.

> Nota factual (fora do código, não verificável neste worktree): o código auditado é o estado de `main`. A divergência entre "código tem" e "André não vê na UI" não tem causa no código-fonte do wizard — recai sobre o que está sendo efetivamente servido/buildado/cacheado no ambiente que o André observou. Isto é constatação, não solução.

---

## Frente C — Sistema de Design (cores, tokens)

Sistema de design declarado: `frontend/tailwind.config.js` (linhas 18-43) define tokens
estilo shadcn via CSS vars HSL — `primary`, `secondary`, `accent`, etc. Os valores estão em
`frontend/src/index.css`: `:root` (tema **claro**: `--background 0 0% 100%`, `--primary 142.1 76.2% 36.3%` "Verde Premium Regente") e `.dark` (tema escuro).

| # | O que checa | Status | Onde no código | Observação factual |
|---|---|---|---|---|
| C1 | Existe paleta/tokens central | **EXISTE** | `tailwind.config.js:18-43`, `index.css:6-58` | Tokens `primary/secondary/accent/background/foreground/card/...` definidos (HSL var). "Verde Premium" = `142 76% 36%`. |
| C2 | O Intake usa os tokens do design system | **FALTA** | `IntakeWizard.tsx` (todo) | Zero uso de `bg-primary/text-foreground/bg-card/bg-background`. Usa classes cruas do Tailwind. |
| C3 | Fundo do Intake | inconsistente | `IntakeWizard.tsx:404` | `bg-gradient-to-br from-slate-900 via-slate-800 to-emerald-950` — **gradiente escuro slate→emerald em tela cheia**. |
| C4 | Fundo do Dashboard (referência "padrão") | inconsistente | `Dashboard/index.tsx` | Tema **claro**: predominam `bg-gray-50`, `bg-white`, `text-gray-900`, `text-emerald-600`. |
| C5 | Fundo/cards do Settings | inconsistente | `Settings/index.tsx` | Mistura: `bg-zinc-800`, `text-zinc-200` (cards escuros) + `text-gray-900/gray-500`. |
| C6 | Família de neutros consistente entre telas | **FALTA** | vários | **Três famílias diferentes**: Intake usa `slate-*`; Settings usa `zinc-*`; Dashboard usa `gray-*`. |
| C7 | Verde do produto consistente | **PARCIAL** | `index.css:16` vs uso | Token `--primary` = `142 76% 36%` (verde fechado). Telas hardcodam `emerald-500/400/600` (verde mais claro/saturado), nunca o token. |

**Inconsistências visuais concretas (o que o André pode estar lendo como "feio"):**

1. **Tema do Intake destoa do resto do painel.** O Intake é uma tela **escura** (gradiente `from-slate-900 via-slate-800 to-emerald-950`, `IntakeWizard.tsx:404`) enquanto o Dashboard é **claro** (`bg-gray-50`/`bg-white`/`text-gray-900`). Trocar de Dashboard para Cadastro muda o tema da aplicação inteira.
2. **Glassmorphism só no Intake.** `bg-white/5` (15×) e `border-white/10` (17×) aparecem no wizard e em nenhuma das telas de referência — efeito de "vidro" sobre fundo escuro que não existe no padrão claro do sistema.
3. **Três famílias de cinza misturadas no app.** Intake=`slate-*`, Settings=`zinc-*`, Dashboard=`gray-*`. São tonalidades de neutro diferentes; lado a lado parecem "fora de paleta".
4. **Verde fora do token.** O Intake usa `emerald-500/400` como cor de ação (botões, badges) em vez do "Verde Premium Regente" definido em `--primary` (`142 76% 36%`). O verde do botão "Próximo" (`bg-emerald-500`, `:890`) não é o verde da marca.
5. **Tokens do design system essencialmente não usados.** Nenhuma das três telas auditadas usa `bg-primary/bg-card/text-foreground`; todas hardcodam classes cruas do Tailwind. O sistema de tokens existe mas está ocioso, então não há nada forçando consistência visual entre telas.

---

## Resumo factual

**Frente A — UI de credenciais.** Não existe no frontend (0 arquivos, 0 chamadas aos endpoints). O que existe em Configurações → Segurança é **troca da própria senha** (`/auth/password-change`), não gerenciamento de credenciais de portal de cliente. Backend completo (5 endpoints em `app/api/v1/credentials.py`, prefixo real `/api/v1/credentials`, senha nunca revelada, só `has_password`). Nenhuma mudança em curso no worktree (limpo em `main`).

**Frente B — UI do intake × spec Isis.** A rota real (`/intake` → `pages/Intake/IntakeWizard.tsx`) **contém quase toda a spec**: PreviewPanel (confidence + origem), ReconcileModal (via PreviewPanel), PriorityStep de 2 eixos, e-mail obrigatório, áudio com presigned upload, e remoção de Sintoma/Dor/"Possui CAR". Itens da spec que **não** batem com o wizard principal:
- **2 colunas: PARCIAL** — o preview lateral só aparece quando há `draftId` (auto-salvo ao entrar no Step 4 / fluxo "importar documentos"); nas etapas iniciais de cadastro novo a tela é de coluna única.
- Nenhum outro item da spec está ausente do código.
- A divergência "código tem × André não vê" não tem origem no código do wizard (é build/cache/ambiente servido) — constatado, não resolvido.

**Frente C — design system.** Tokens existem (`tailwind.config.js` + `index.css`, "Verde Premium" `142 76% 36%`) mas estão ociosos. Inconsistências concretas: (1) Intake é tema **escuro** (gradiente slate→emerald) enquanto Dashboard é **claro**; (2) glassmorphism `bg-white/5`/`border-white/10` só no Intake; (3) três famílias de neutro no app (Intake=slate, Settings=zinc, Dashboard=gray); (4) Intake usa `emerald-500` em vez do verde-marca do token; (5) nenhuma tela usa os tokens do design system.
