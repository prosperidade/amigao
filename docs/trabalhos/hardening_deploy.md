# Hardening pós-deploy — migration automática + rota + retry determinístico

> PR `fix/hardening-deploy-rotas` (base `main`). Origem: incidente de produção
> 2026-06-06 — as Fases 1-4 deployaram mas a migration não foi aplicada; a sócia
> validou sobre um sistema quebrado. Três itens, cada um medido contra o código real.

## Item A — Migration automática no deploy

**Causa:** o Render só deploya **código**; migrations eram **manuais** (Render Shell).
A Fase 1-4 subiu sem a tabela `extracted_field_staging` → o extrator explodia ao gravar.

**Fix:** `render.yaml` — `preDeployCommand: alembic upgrade head` no serviço
**`regente-api`** (não no worker). Roda na imagem recém-buildada, **antes** da nova
versão entrar no ar → schema migrado quando API e worker sobem (sem corrida entre
serviços). Idempotente (no-op em `head`). Usa `MIGRATE_DATABASE_URL` (conexão direta)
via `alembic/env.py`. Se falhar, o Render **aborta o deploy** e mantém a versão
anterior — o sintoma vira "deploy não promove", não "sistema quebrado silencioso".

- **Dev (docker-compose):** paridade **já existente** — o serviço `api` roda
  `python -m app.db.init_db` no boot, que aplica `alembic upgrade head`. Sem mudança.
- **Runbook:** nova seção "Migrations em produção" em `docs/operacao/RUNBOOK_OPS.md`
  (o que acontece no deploy, como verificar `alembic current`, como aplicar manual).

**Evidência:** `render.yaml` parseia (YAML válido); `preDeployCommand` presente só na
API (worker = `None`); `init_db.py:39` chama `command.upgrade(cfg, "head")`.

## Item B — "Rota fantasma" /processes/{id}/extract

**Premissa do prompt corrigida pela medição:** a rota **EXISTE e está registrada** —
`POST /api/v1/processes/{process_id}/extract` (`processes.py:455`, adicionada no #25
`f9f48cb`). Verificado inspecionando as rotas reais do app FastAPI. **Não é 404 em
`main`.** O que travou a UI no incidente foi a combinação Item A (tabela ausente →
extrator crasha) + Item C (retry storm → job preso → UI "aguardando" eterna), **não**
um 404.

**Mapa dos disparos (todos verificados no front):**
- `AgentsPage.tsx` (botão do card do extrator) → `POST /processes/{id}/extract` ✅ rota correta.
- `AIPanel.tsx` (aba IA do workflow) → `POST /agents/run-async` / `chain-async` ✅ funciona.
- `WorkspaceRightPanel.tsx` → `run-async` ✅ (já tinha `onError`).

**Decisão:** manter a rota `/extract` (é proposital — itera todos os docs, OCR fallback);
**não** criar alias nem repontar. O gap real era a UI **não mostrar erro de disparo**:
`AgentsPage` (3 mutations) e `AIPanel` (2 mutations) **não tinham `onError`** → falha de
disparo sumia e o card ficava girando. Adicionado `toast.error` (padrão do
`WorkspaceRightPanel`) nas 5 mutations.

**Evidência:** `tsc --noEmit` e `npm run build` verdes.

## Item C — Retry de erro determinístico na chain

**Causa (mecanismo medido):** `BaseAgent.run()` captura toda exceção, marca o job
`failed` via `_fail_job` (que faz `flush()` com try/except que **engole** o erro) e
retorna `success=False` — não re-levanta. Com `UndefinedTable`, a sessão fica
**abortada**; o `run_agent` então faz `db.commit()` → **levanta** `PendingRollbackError`
→ cai no `except Exception → self.retry` → **retry storm** (60s sem fim). O
`run_agent_chain` não tinha guarda nenhuma. `_create_running_job` só faz `flush`
(sem commit) → no rollback o job "running" some do histórico.

**Fix:** `app/workers/agent_tasks.py` — constante `_DETERMINISTIC_ERRORS` = `(ValueError,
ProgrammingError, IntegrityError, DataError, PendingRollbackError)`. Em `run_agent` e
`run_agent_chain`, um `except _DETERMINISTIC_ERRORS` **antes** do `except Exception`:
faz `rollback`, loga, **NÃO faz retry**, marca o job `failed`. `OperationalError`
**fica de fora** de propósito — é a classe transitória (conexão, deadlock) → mantém
retry. `run_agent` recria o job `failed` numa sessão limpa (`_persist_failed_job`,
best-effort) para a execução não sumir do histórico.

**Evidência:** `tests/workers/test_agent_tasks_retry.py` (6 testes): UndefinedTable e
IntegrityError → failed sem retry; OperationalError → retry mantido; idem chain.
ruff + mypy limpos.

## Decisões e fora de escopo

- **Premissa do Item B estava stale** (rota existe) — reportado em vez de "criar a rota".
  Princípio: verificar contra código real, não contra a representação do incidente.
- Não toquei nas Fases 1-4 nem em `BaseAgent` (a robustez do `_fail_job` em sessão
  envenenada é dívida separada — o Item C resolve o sintoma no worker sem mexer no core).
- Lição registrada em `LICOES_APRENDIDAS`: *deploy de código ≠ migration aplicada;
  validação de fase inclui o banco de prod.*
