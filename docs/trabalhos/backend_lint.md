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
  do repo. (O `backend-migrations` já resolvia via `prepend_sys_path = .` no
  `alembic.ini`.) Reproduzido local: bare `pytest` falha igual, `python -m pytest`
  coleta 753.
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
