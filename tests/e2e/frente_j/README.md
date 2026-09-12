# Gate E2E — Frente J (fechamento de contrato)

O que nunca tinha sido feito nas Frentes C–I: atravessar o fluxo inteiro
**num ambiente autenticado** — login real, frontend real, API real, worker
real, banco descartável — como UM gate, e colar a sequência com prints e
payloads. Exigência da reauditoria Codex (`docs/auditoria/REAUDITORIA_CODEX_11-09.md`).

Duas camadas, a mesma sequência:

| camada | arquivo | prova |
|---|---|---|
| API (payloads) | `tests/e2e/frente_j/gate_api.py` | 6 docs → extração real → decisões → 3 decididas (uma com `reclassificar`) → consolidar → recarregar → logout/login → as 6 telas comparadas campo a campo; doc novo → diagnóstico/rota/proposta desatualizados → aceite recusado 422 |
| UI (gesto humano, prints) | `frontend/e2e/frente-j.spec.ts` (Playwright) | o mesmo, clicando: input de arquivo real, "Aceitar", "Editar tipo", "Gravar na base", F5, "Sair do sistema", banner e botão bloqueado na proposta |

Nenhuma das duas roda no CI (exige a pilha inteira e uma chave de LLM). O
resultado é colado em `docs/trabalhos/fechamento_contrato.md`.

## Pré-requisitos

- Docker Desktop de pé: `docker compose up -d db redis minio` (Postgres em
  `127.0.0.1:${HOST_DB_PORT}`, Redis `6379`, MinIO `9000`).
- `.env` da raiz com `OPENAI_API_KEY` válida e `AI_ENABLED=true` (a extração
  é real, como em produção; custo medido em `docs/trabalhos/fechamento_contrato.md`).
- Os 6 PDFs de texto gerados a partir do `extracted_text` REAL de produção
  dos docs 546–551 (md5 conferido) — não versionados (dado de produção);
  gerados por `scripts`-de-sessão a partir do Supabase MCP (só leitura).
- `frontend/node_modules` com `@playwright/test` + `npx playwright install chromium`.

## Passos

```bash
# 1. banco descartável + seed (imprime o JSON com ids/credenciais)
E2E_PG_HOST=127.0.0.1 E2E_PG_PORT=15432 E2E_PG_USER=postgres E2E_PG_PASSWORD=<do .env> \
E2E_DB_NAME=amigao_e2e_frente_j python tests/e2e/frente_j/setup_db.py > /tmp/e2e_seed.json

# 2. API e worker apontando para o banco descartável e um Redis DB próprio
#    (índice 5: nenhum worker de dev pode consumir as tarefas do gate)
POSTGRES_DB=amigao_e2e_frente_j POSTGRES_PORT=15432 REDIS_URL=redis://localhost:6379/5 \
  python -m uvicorn app.main:app --port 8000
POSTGRES_DB=amigao_e2e_frente_j POSTGRES_PORT=15432 REDIS_URL=redis://localhost:6379/5 \
  python -m celery -A app.core.celery_app worker --loglevel=info --pool=solo

# 3. camada API
python tests/e2e/frente_j/gate_api.py --base http://127.0.0.1:8000 \
  --seed /tmp/e2e_seed.json --pdfs <pasta dos PDFs> --out docs/trabalhos/fechamento_contrato/gate_api

# 4. camada UI (novo seed, para a UI subir os documentos ela mesma)
cd frontend && npm run dev   # 5173
E2E_SEED_JSON=/tmp/e2e_seed_ui.json E2E_PDFS_DIR=<pasta> E2E_API_URL=http://127.0.0.1:8000 \
E2E_PRINTS_DIR=../docs/trabalhos/fechamento_contrato/prints npx playwright test
```

## Gate de navegador único (Frente K)

`frontend/e2e/frente-k.spec.ts` é UM teste, UMA sessão, e **não** trabalha
sobre estado pré-produzido pela API: login → "Gerar Checklist" → os 6
documentos pelo input real → extração → decisões (com reclassificação) →
"Gravar na base" → F5 → logout/login → rota → documento novo → rota
desatualizada. Os seis números são lidos do DOM.

Precisa de um banco descartável **virgem** (o mesmo `setup_db.py`, com outro
`E2E_DB_NAME`) e do Vite apontado para a API do gate:

```bash
# banco próprio do gate de navegador
E2E_DB_NAME=amigao_e2e_frente_k_ui python tests/e2e/frente_j/setup_db.py > /tmp/seed_kui.json
# API + worker apontados para ele (Redis num índice só dele)
POSTGRES_DB=amigao_e2e_frente_k_ui REDIS_URL=redis://localhost:6379/7 python -m uvicorn app.main:app --port 8010
POSTGRES_DB=amigao_e2e_frente_k_ui REDIS_URL=redis://localhost:6379/7 python -m celery -A app.core.celery_app worker --pool=solo
# Vite com proxy para a API do gate
cd frontend && VITE_API_PROXY_TARGET=http://127.0.0.1:8010 npm run dev
# o gate
cd frontend && E2E_FRONTEND_URL=http://localhost:5173 E2E_SEED_JSON=/tmp/seed_kui.json   E2E_API_URL=http://127.0.0.1:8010 E2E_PDFS_DIR=<pasta dos PDFs>   E2E_PRINTS_DIR=<pasta de prints> npx playwright test frente-k.spec.ts
```

> `E2E_FRONTEND_URL` importa: o Vite escuta em `localhost` (IPv6), e o default
> `127.0.0.1:5173` do `playwright.config.ts` dá `ERR_CONNECTION_REFUSED`.

Resultado colado em `docs/trabalhos/consolidacao_real/CONSOLIDACAO_REAL.md`.

`setup_db.py` recusa qualquer nome de banco que não comece com `amigao_e2e`
e aplica o schema por `create_all` (mesmo caminho do `conftest.py`) — nunca
`alembic` fora do banco de desenvolvimento (CLAUDE.md).
