# Isolamento — Redesign do Dashboard

Branch dedicada: `feat/dashboard-redesign-v2`

Esta branch existe pra que o trabalho de redesign do dashboard
NÃO conflite com outros agentes/sprints rodando em paralelo no
mesmo repo (ex: auditoria K3, ondas A4, normas SEMAD).

## ✅ Escopo do redesign (mexe AQUI)

Arquivos que o redesign pode tocar:

- `frontend/src/pages/Dashboard/index.tsx`
- `frontend/src/pages/Dashboard/DashboardRegente.tsx`
- `frontend/src/pages/Dashboard/DashboardOperacionalRegente.tsx`
- `frontend/src/pages/Dashboard/components/` (novos componentes
  extraídos durante o refactor)
- `frontend/src/layouts/PrivateLayout.tsx` (apenas pra adicionar
  toggle dark/light no header)
- `frontend/src/store/` (apenas se criar `theme.ts` store novo)
- `frontend/tailwind.config.js` (apenas se precisar tokens novos)
- `frontend/package.json` (apenas se adicionar `framer-motion`,
  `recharts`, etc.)
- `docs/redesign/` (toda esta pasta)
- `scripts/screenshot_dashboard.mjs` (utilitário do redesign)

## ❌ Fora do escopo (NÃO mexer — território de outros agentes)

- `app/` inteiro (backend Python) — exceto se descobrir bug
  específico que afete o dashboard; nesse caso, abrir issue
  separado em vez de corrigir aqui
- `frontend/src/pages/Processes/`, `Clients/`, `Properties/`,
  `Proposals/`, `Intake/`, `AI/`, `Auth/`, `Settings/`
- `frontend/src/lib/api.ts` — cliente HTTP é compartilhado
- `frontend/src/store/auth.ts` — store de autenticação
- Migrations Alembic, modelos SQLAlchemy, agentes IA, skills
- Arquivos do trabalho paralelo de auditoria:
  - `AUDITORIA_DOCUMENTAL_*.md`
  - `BRIEFING_OPUS_SKILLS_DIAGNOSTICO.md`
  - `MANIFESTO_NORMAS.md`
  - `PROMPT_1_fase0_*.md`, `PROMPT_2_implementacao_*.md`
  - `SKILL.md`
  - `normas_k3/`, `Licenciamento (SEMAD)/`, `Manuais (SEMAD)/`
  - `010-loop-aprendizado-consultores.md`

## 🧩 Dados e contratos (intocáveis)

Os endpoints abaixo são consumidos pelo dashboard mas
mantidos pelo backend (outro agente / sprint):

- `GET /dashboard/summary`
- `GET /dashboard/stages`
- `GET /dashboard/alerts`
- `GET /dashboard/priority-cases`
- `GET /dashboard/ai-summary`
- `GET /dashboard/kpis`
- `GET /ai/jobs`

Se um endpoint precisar ser alterado pra suportar o novo
visual, é tarefa SEPARADA — abrir issue específica.

## 🔀 Fluxo de merge

1. Refactor todo nesta branch
2. PR pra `main` quando completo (testar typecheck + build)
3. Squash merge pra histórico limpo
4. Antes do merge: rebase em `main` pra incorporar mudanças
   paralelas (auditoria, normas, etc.)

## 📋 Estado atual

- [x] Briefing v2 escrito (`PROMPT_CLAUDE_DESIGN_V2.md`)
- [x] Screenshots do "antes" capturados (anti-referência)
- [x] Branch isolada criada
- [ ] Mockups do Claude Design recebidos
- [ ] Componentes refatorados
- [ ] Toggle dark/light implementado
- [ ] Build + typecheck OK
- [ ] PR aberto pra main
