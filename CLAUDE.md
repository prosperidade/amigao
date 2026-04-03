# CLAUDE.md -- Amigao do Meio Ambiente

## Projeto

SaaS de consultoria ambiental brasileira. Multi-tenant, voltado para fazendas e cooperativas agropecuarias.

## Stack

- **Backend:** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Celery
- **Banco:** PostgreSQL 15 + PostGIS 3.3, Redis 7
- **Storage:** MinIO (S3-compatible)
- **Frontend interno:** React 18 + Vite + TypeScript + TailwindCSS + React Query + Zustand
- **Portal cliente:** Next.js 16 (App Router) + TypeScript + TailwindCSS
- **Mobile:** Expo (React Native) com SQLite offline-first
- **IA:** LiteLLM (multi-provider: OpenAI, Gemini, Anthropic)
- **Infra:** Docker Compose (db, redis, minio, api, worker, client-portal)

## Comandos

### Subir tudo (Docker)

```bash
docker compose up --build -d
```

### Subir local (dev sem Docker)

```bash
# Backend API
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Worker Celery
celery -A app.core.celery_app worker --loglevel=info --pool=solo

# Frontend interno
cd frontend && npm run dev

# Portal cliente
cd client-portal && npm run dev
```

### Testes

```bash
# Backend (requer PostgreSQL rodando)
pytest tests/ -q

# Frontend typecheck
cd frontend && npx tsc --noEmit

# Frontend build
cd frontend && npm run build

# Portal typecheck + build
cd client-portal && npx tsc --noEmit && npm run build
```

### Migrations

```bash
alembic upgrade head
alembic downgrade -1
```

## Estrutura do projeto

```
app/
  api/v1/          # Routers FastAPI (14 routers)
  api/deps.py      # Dependency injection (auth, db, tenant)
  api/middleware.py # Request context, tracing, metricas
  core/            # Config, security, celery, logging, metrics, tracing, alerts, ai_gateway
  models/          # SQLAlchemy ORM (16 entidades)
  schemas/         # Pydantic DTOs
  services/        # Logica de negocio
  workers/         # Celery tasks
  db/              # Session factory, init_db
frontend/          # React + Vite (painel interno)
client-portal/     # Next.js 16 (portal do cliente)
mobile/            # Expo (app de campo)
tests/             # pytest
docs/              # Documentacao do projeto
ops/               # Scripts operacionais
alembic/           # Migrations
```

## Regras de codigo

### Python (Backend)

- Pydantic v2: usar `model_config = ConfigDict(...)` e `.model_dump()`. NUNCA usar `class Config` ou `.dict()`.
- SQLAlchemy 2: usar `sqlalchemy.orm.declarative_base`.
- Tipos PostgreSQL-only (JSONB, Geometry): se for necessario compatibilidade com SQLite em testes, usar type decorator portavel em `app/models/types.py`.
- Settings via `from app.core.config import settings` (singleton).
- SECRET_KEY obrigatoria com >= 32 caracteres.
- Tenant isolation: toda query deve filtrar por `tenant_id`.
- Logs: usar `app.core.logging.get_logger(__name__)`. Formato JSON em producao.
- Metricas: registrar em `app/core/metrics.py`. Endpoint `/metrics`.
- Alembic: NUNCA usar `create_all` fora de teste. Schema evolui exclusivamente por migrations.
- Workers: usar `@celery_app.task` com `max_retries=3` e `retry_backoff=True`.

### TypeScript (Frontend Vite)

- Strict mode: `"strict": true`, `"noUnusedLocals": true`, `"noUnusedParameters": true`.
- Imports: NUNCA importar simbolos nao usados. Remover imediatamente.
- Tipagem: NUNCA usar `any` explicito. Usar tipos concretos ou `typeof` de valores existentes.
- Mutations: `mutationFn` deve retornar tipo consistente (usar `async/await` para uniformizar).
- API client: `frontend/src/lib/api.ts` com interceptors para auth (401 e 403 fazem logout).
- State: Zustand com persist para auth. React Query para server state.
- Styling: TailwindCSS. Sem CSS modules.

### TypeScript (Client Portal Next.js)

- App Router (Next.js 16). Verificar docs em `node_modules/next/dist/docs/` antes de usar APIs.
- Fontes: usar `next/font/local` com arquivos em `public/fonts/`. NUNCA usar `next/font/google` (quebra build offline).
- Upload para MinIO: usar `fetch()` diretamente. NUNCA usar `axios` direto (bypass do interceptor de auth).
- SSR safety: `localStorage` nao existe no servidor. Proteger acessos com `typeof window !== 'undefined'`.

### TypeScript (Mobile Expo)

- Token em `expo-secure-store`. NUNCA em AsyncStorage.
- URL da API via variavel de ambiente `EXPO_PUBLIC_API_URL`. NUNCA hardcodar IP.
- Offline-first: SQLite local com fila de sincronizacao.

## Autenticacao

- JWT com dois perfis: `internal` (painel) e `client_portal` (portal do cliente).
- Login envia header `X-Auth-Profile: internal` ou `X-Auth-Profile: client_portal`.
- Token contem: `sub` (user_id), `tenant_id`, `profile`, `client_id` (se portal).
- Endpoints internos usam `get_current_internal_user` que rejeita tokens do portal com 403.

## Variaveis de ambiente obrigatorias

- `SECRET_KEY` (>= 32 chars, obrigatoria sempre)
- `POSTGRES_SERVER`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- `REDIS_URL`
- `MINIO_SERVER`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`

## Endpoints principais

- API: `http://localhost:8000`
- Health: `GET /health`
- Metrics: `GET /metrics`
- Portal do cliente: `http://localhost:3000`
- MinIO Console: `http://localhost:9001`
- Frontend interno: `http://localhost:5173` (dev)

## Credenciais seed (dev local)

- `admin@amigao.com` / `Seed@2026` (superuser)
- `consultor@amigao.com` / `Seed@2026`
- `cliente@amigao.com` / `Seed@2026`
- `campo@amigao.com` / `Seed@2026`

## Seguranca

- NUNCA commitar `.env` no Git. O `.gitignore` deve conter `.env`.
- NUNCA expor chaves de API (OpenAI, SMTP) em codigo ou documentacao.
- Em producao: SMTP deve estar configurado (fail-fast). Em dev: warning + skip.
- Rate limiting recomendado no `/auth/login`.

## Documentacao de referencia

- Regras de negocio: `docs/DocumentodeRegrasdeNegocio.md`
- Arquitetura: `docs/Arquiteturadetalhada.md`
- API spec: `docs/EspecificacaodaAPIv1.md`
- Observabilidade: `docs/ObservabilidadeOperacional.md`
- Runbook: `docs/RunbookOperacional.md`
- Progresso: `docs/progresso2.md`, `docs/progresso3.md`
- Plano mestre: `docs/PLANO_MESTRE_CORRECOES.md`
