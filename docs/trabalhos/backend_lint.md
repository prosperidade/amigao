# Trabalho — Backend Lint verde (diagnóstico antes de corrigir)

> Arquivo único de trabalho. Diagnóstico → o que foi feito → validação → status.
> Branch: `fix/backend-lint` (base `main`). Data: 2026-06-03.
> Escopo: só lint/CI. Sem mudar OCR/chain/storage/lógica de negócio.

## Diagnóstico — era (A) infra **E** (B) código

O job `backend-lint` tem dois passos: `ruff check app/ tests/` e `mypy app/`.

### (A) Infra — a ferramenta nunca foi instalada
O CI instalava só `requirements.txt`, mas `ruff`/`mypy` estão em
`requirements-dev.txt`. Log real do CI (run #55):

```
/home/runner/.../sh: line 1: ruff: command not found
##[error]Process completed with exit code 127.
```

Ou seja: o lint **nunca rodou** — morria no passo do ruff por ausência da
ferramenta, antes de chegar no mypy. Por isso ficou vermelho desde #52.

### (B) Código — erros reais escondidos atrás do (A)
Rodando ruff localmente (0.15.13): **77 erros** (62 autofix + 15 manuais).
Rodando mypy localmente (2.1.0): **~495 erros em 77 arquivos** — quase todos
`Column[int]` vs `int` do SQLAlchemy. Pré-existentes (memória de Abr/26 já
registrava "523 mypy errors"), nunca enforçados.

## O que foi feito

### 1. CI (`.github/workflows/ci.yml`)
- `backend-lint` e `backend-test` passam a instalar **`requirements-dev.txt`**
  (puxa runtime via `-r` + ruff/mypy/pytest/testcontainers). Sem isso, ao deixar
  o lint verde, o `backend-test` (que tem `needs: backend-lint` e estava
  *skipping*) rodaria pela 1ª vez e quebraria por falta de pytest.
- **`backend-test` roda `python -m pytest` (não `pytest` cru).** Ao destravar, o
  job falhou em 41s com `ModuleNotFoundError: No module named 'app'` no import do
  `conftest`: `pytest` cru **não** insere o cwd no `sys.path`; o `-m` insere a raiz
  do repo. Reproduzido local: bare `pytest` falha igual, `python -m pytest` coleta 753.
- **Imagem PostGIS + pgvector buildada nos jobs `backend-test` e `backend-migrations`.**
  A cascata expôs que esses dois jobs **nunca rodaram com sucesso no CI** (ficavam
  *skipping* atrás do lint vermelho) e dependem da imagem custom do projeto
  (`docker/db/Dockerfile` = postgis/postgis:15-3.3 + `postgresql-15-pgvector`):
  - `backend-test`: o fixture do `conftest` sobe Postgres via Testcontainers e usa
    `amigao_do_meio_ambiente-db:latest`; sem ela, o fallback `pgvector/pgvector:pg15`
    **não tem PostGIS** → `CREATE EXTENSION postgis` quebra. Fix: passo
    `docker build -t amigao_do_meio_ambiente-db:latest -f docker/db/Dockerfile .`
    antes do pytest (a tag é a que o fixture procura).
  - `backend-migrations`: as migrations criam `postgis` **E** `vector`; o `services:`
    era `postgis/postgis:15-3.3` (sem pgvector) → `CREATE EXTENSION vector` quebraria.
    Fix: trocado o `services:` por build da imagem custom + `docker run` (mesma imagem
    com as duas extensões).
- **`CREDENTIAL_ENCRYPTION_KEY` + `AI_ENABLED`/`OPENAI_API_KEY` no env dos jobs.**
  `Settings()` exige `CREDENTIAL_ENCRYPTION_KEY` (ADR-014, sem fallback) — falha no
  boot sem ela; chave Fernet descartável de CI. E 18 testes do caminho IA mockam
  `app.agents.base.complete` mas só tomam o caminho IA se `settings.ai_configured`
  (precisa `AI_ENABLED` + chave não-placeholder len>10) — chave **fake**, o `complete`
  é mockado, sem chamada real. Ambos espelham o `.env` local.
- **Gate de cobertura informativo (`--cov-fail-under=0`).** Os 753 testes passam; o
  job falhava só no `fail_under = 70` do `pyproject` (cobertura real 63%). O próprio
  workflow já dizia (TODO) pra não enforçar 70% ainda — o override deixa o relatório
  visível sem o gate. Meta 70% mantida no `pyproject`.
- **Bug de migration `UnsafeNewEnumValueUsage` (enum `lead`).** Decisão do André:
  corrigir neste PR. A migration `afcea9834c04` fazia `ALTER TYPE processstatus ADD
  VALUE 'lead'` (+10 valores) e usava os novos valores na **mesma transação** →
  `UnsafeNewEnumValueUsage` num `upgrade head` do zero (CI / deploy novo; invisível em
  prod incremental e nos testes que usam `create_all`). Fix: ADD VALUE envoltos em
  `op.get_context().autocommit_block()` — mesmo padrão de `b3d5c7e9f1a2`. **Validado
  local:** `upgrade head` do zero contra a imagem custom roda sem o erro.
- Passo mypy → **`continue-on-error: true`** (advisory) com comentário + dívida
  **#46**. Decisão do André: ruff é o gate real; mypy roda e reporta, mas não
  derruba o check. Corrigir 495 erros de tipagem é refactor de assinaturas/lógica,
  fora do escopo de um PR de lint.
- `ruff==0.15.13` / `mypy==2.1.0` **pinados** em `requirements-dev.txt` — o gate
  ruff não pode mudar de comportamento por upgrade silencioso.

### 2. Ruff — 77 erros → 0

| Regra | Qtd | Tratamento |
|---|---|---|
| I001 unsorted-imports | 31 | autofix |
| F401 unused-import | 13 | autofix (verificado: nenhum era re-export/side-effect; `__init__`/api legados já em per-file-ignores) |
| UP017 datetime.UTC | 9 | autofix |
| UP037 quoted-annotation | 6 | autofix |
| F541 f-string sem placeholder | 1 | autofix |
| SIM117 nested-with | 4 | 2 autofix + 2 manual (combinar `with`) |
| SIM118 in-dict-keys | 1 | manual (`k in dumped`) |
| **B027** empty-method-abc | 1 | **`# noqa: B027` justificado** — `BaseAgent.validate_preconditions` é hook opcional (no-op de propósito; não pode virar `@abstractmethod` sem forçar todas as subclasses) |
| **B017** blind-except | 1 | **`# noqa: B017` justificado** — teste de WS: a rejeição aflora como tipos diferentes por versão do starlette; o teste só garante que a conexão não sobe |
| E402 import-not-at-top | 3 | manual (reordenar imports — `agents.py`, `intake_draft.py`) |
| B905 zip-sem-strict | 2 | manual (`strict=False` — preserva comportamento atual exato) |
| SIM105 suppressible-except | 2 | manual (`contextlib.suppress` — equivalente; `intake.py`, `conftest.py`) |
| SIM102 collapsible-if | 1 | manual (combinar `if`) |
| SIM108 if-else→ternário | 1 | manual |
| UP007 Union→`X \| Y` | 1 | manual (+ remoção do `Union` que ficou órfão em `dashboard.py`) |

- **Nenhuma regra foi afrouxada** para mascarar erro. Só 2 `# noqa`, ambos por
  caso e justificados no código.
- B905 usou `strict=False` (não `True`) de propósito: mantém o comportamento atual
  (parar no menor) — não introduz exceção nova em produção.

## Validação

- `python -m ruff check app/ tests/` → **All checks passed!** (0).
- `pytest --collect-only` → 753 coletados, **sem erro de import** (sanidade pós-fixes).
- Suíte backend: **baseline 753 passed** (antes dos fixes) e **753 passed** (após
  os fixes) — lint **não mudou comportamento**. (Testcontainers + Postgres real.)
- mypy roda e reporta os ~495 (advisory) — não derruba o job.
- Cascata do CI conferida: `backend-test`/`backend-migrations` (que destravam ao
  lint ficar verde) agora instalam deps corretas.

## Status

**Concluído.** Backend Lint deve ficar verde no CI (ruff 0 + tool instalada +
mypy advisory). Suíte 753/753. Sem afrouxar regra; 2 `# noqa` justificados.
mypy registrado como dívida **#46** (correção incremental). RUNBOOK_DEV atualizado
com a seção de lint/tipagem.
