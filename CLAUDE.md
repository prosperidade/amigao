# CLAUDE.md — Regente Ambiental

> Sistema operacional da consultoria ambiental brasileira.
> Potencializa o consultor — não substitui.

**Nome do produto:** Regente Ambiental
**Codinome técnico interno:** `amigao` (em identificadores de infraestrutura — ver `docs/adr/004-regente-vs-amigao.md`)

---

## Projeto

SaaS multi-tenant de consultoria ambiental brasileira. Materializa em software o método de quem opera consultoria com profundidade no campo regulatório (sócia ambientalista com anos de campo + tecnologia). Atende três audiências em papéis distintos:

- **Consultorias ambientais** (quem paga) — frente comercial principal
- **Órgãos públicos** (quem valida) — chancela institucional
- **Bancos e cooperativas** (quem distribui) — canal comercial

CAR (Cadastro Ambiental Rural) é o ângulo natural de entrada nos órgãos públicos — dor compartilhada e transversal.

Para o "porquê" completo: `docs/manifesto/01-VISAO_PRODUTO.md`.

## Stack

- **Backend:** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Celery
- **Banco:** PostgreSQL 15 + PostGIS 3.3 + pgvector 0.8, Redis 7
- **Storage:** MinIO (S3-compatible)
- **Frontend (consultor — ativo):** React 18 + Vite + TypeScript + TailwindCSS + React Query + Zustand
- **Frontend (cliente — congelado):** Next.js 16 (App Router) + TypeScript + TailwindCSS
- **Mobile (campo — congelado):** Expo (React Native) com SQLite offline-first
- **IA:** LiteLLM (multi-provider: OpenAI, Gemini, Anthropic)
- **Infra:** Docker Compose (db, redis, minio, api, worker, client-portal)

`client-portal/` e `mobile/` estão congelados até validação do painel consultor. Ver `docs/adr/009-mobile-clientportal-congelados.md`.

## Comandos

### Subir tudo (Docker)

```bash
docker compose up --build -d
```

> **Porta do Postgres no host:** o serviço `db` expõe `55432` no host (não 5433 — conflitava com outros projetos do dev). Dentro do compose, `api`/`worker` conectam via service name `db:5432`. Se rodar `alembic`/`seed.py` do venv host, o `.env` deve apontar `POSTGRES_SERVER=127.0.0.1` e `POSTGRES_PORT=55432`. Override com `HOST_DB_PORT=XXXX` no `.env`.
>
> **Sintoma "could not translate host name 'db'"** dentro do container API significa que o serviço `db` não está up — `docker compose up -d db`. Não é problema de rede; o `db` está no mesmo network e tem `depends_on` correto.

### Subir local (dev sem Docker)

```bash
# Backend API
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Worker Celery
celery -A app.core.celery_app worker --loglevel=info --pool=solo

# Frontend (painel consultor)
cd frontend && npm run dev
```

### Testes

```bash
# Backend (requer PostgreSQL rodando)
pytest tests/ -q

# Frontend typecheck
cd frontend && npx tsc --noEmit

# Frontend build
cd frontend && npm run build
```

> `client-portal/` e `mobile/` não rodam em CI no estado congelado. Buildá-los pode falhar — não tente subir esses serviços sem checar o ADR-009.

### Migrations

```bash
alembic upgrade head
alembic downgrade -1
```

Convenção: `<8-hex>_sprint_<X>_<descricao>.py`. `Base.metadata.create_all()` proibido fora de teste.

## Estrutura do projeto

```
app/
  api/v1/          # Routers FastAPI (28 routers + 1 WebSocket)
  api/deps.py      # Dependency injection (auth, db, tenant)
  api/middleware.py # Request context, tracing, métricas, security headers
  core/            # Config, security, celery, logging, metrics, tracing, alerts, ai_gateway
  models/          # SQLAlchemy ORM (28 entidades)
  schemas/         # Pydantic v2 DTOs (incluindo StageOutputContent + derivados)
  services/        # Lógica de negócio
  agents/          # 10 agentes IA + base + orchestrator
  skills/          # Skills procedurais (Markdown + YAML)
  workers/         # Celery tasks (11 módulos)
  repositories/    # Camada de acesso a dados (parcial)
  db/              # Session factory, init_db
frontend/          # React + Vite (painel consultor — ATIVO)
client-portal/     # Next.js 16 (portal do cliente — CONGELADO)
mobile/            # Expo (app de campo — CONGELADO)
alembic/           # Migrations
docs/              # Documentação (ver docs/README.md)
ops/               # Scripts operacionais
scripts/           # Scripts utilitários
tests/             # pytest + Testcontainers
```

## Princípios inegociáveis

Os 10 princípios do produto vivem em `docs/manifesto/03-PRINCIPIOS.md`. Os mais ativados em decisões diárias:

1. **A IA propõe; o humano decide e assina.** Peças formais sempre com `requires_review=True`. Sem exceção.
2. **Tudo é auditável.** Hash chain SHA-256, citation evaluator, origem de campo rastreável, custo/tokens/modelo persistidos.
3. **Cadastro / Diagnóstico / Coleta são camadas separadas.** Não misturar.
4. **Multi-tenant desde o dia 1.** Toda query filtra por `tenant_id`.
5. **Multi-provider IA.** LiteLLM com fallback. Nenhum serviço chama provider direto.
6. **Schema antes de escala.** Saídas de agente passam por `StageOutputContent` validado.
7. **Cost cap é hard limit.** `AI_MAX_COST_PER_JOB_USD` enforced no `ai_gateway.complete()`.

## Regras de código

### Python (Backend)

- **Pydantic v2:** usar `model_config = ConfigDict(...)` e `.model_dump()`. NUNCA usar `class Config` ou `.dict()`.
- **SQLAlchemy 2:** usar `sqlalchemy.orm.declarative_base`.
- **Tipos PostgreSQL-only** (JSONB, Geometry, Vector): se for necessária compatibilidade com SQLite em testes, usar type decorator portável em `app/models/types.py`.
- **Settings via** `from app.core.config import settings` (singleton).
- **SECRET_KEY** obrigatória com ≥ 32 caracteres.
- **Tenant isolation:** toda query deve filtrar por `tenant_id`. Validar na escrita.
- **Logs:** usar `app.core.logging.get_logger(__name__)`. Formato JSON em produção.
- **Métricas:** registrar em `app/core/metrics.py`. Endpoint `/metrics`.
- **Alembic:** NUNCA usar `create_all` fora de teste. Schema evolui exclusivamente por migrations.
- **Workers:** usar `@celery_app.task` com `max_retries=3` e `retry_backoff=True`.
- **AI Gateway:** NUNCA chamar provider diretamente. Sempre via `app/core/ai_gateway.py:complete()`.
- **Agentes:** novos agentes herdam de `BaseAgent` e emitem `StageOutputContent` (ou derivado) quando a saída é consumida por outro agente/frontend.

### TypeScript (Frontend Vite — painel consultor)

- **Strict mode:** `"strict": true`, `"noUnusedLocals": true`, `"noUnusedParameters": true`.
- **Imports:** NUNCA importar símbolos não usados. Remover imediatamente.
- **Tipagem:** NUNCA usar `any` explícito. Usar tipos concretos ou `typeof` de valores existentes.
- **Mutations:** `mutationFn` deve retornar tipo consistente (usar `async/await` para uniformizar).
- **API client:** `frontend/src/lib/api.ts` com interceptors para auth (401 e 403 fazem logout).
- **State:** Zustand com persist para auth. React Query para server state.
- **Styling:** TailwindCSS. Sem CSS modules.

### TypeScript (Client Portal Next.js — CONGELADO)

Não receber commits funcionais. Mudanças só correções triviais. Se descongelar (ADR-009 será revisado), as regras abaixo se aplicam:

- App Router (Next.js 16).
- Fontes: usar `next/font/local` com arquivos em `public/fonts/`. NUNCA usar `next/font/google` (quebra build offline).
- Upload para MinIO: usar `fetch()` diretamente. NUNCA usar `axios` direto (bypass do interceptor de auth).
- SSR safety: `localStorage` não existe no servidor. Proteger com `typeof window !== 'undefined'`.

### TypeScript (Mobile Expo — CONGELADO)

Mesma política do client-portal. Quando descongelar:

- Token em `expo-secure-store`. NUNCA em AsyncStorage.
- URL da API via `EXPO_PUBLIC_API_URL`. NUNCA hardcodar IP.
- Offline-first: SQLite local com fila de sincronização.

## Autenticação

- JWT com dois perfis: `internal` (painel consultor) e `client_portal` (portal do cliente — congelado).
- Login envia header `X-Auth-Profile: internal` ou `X-Auth-Profile: client_portal`.
- Token contém: `sub` (user_id), `tenant_id`, `profile`, `client_id` (se portal).
- Endpoints internos usam `get_current_internal_user` que rejeita tokens do portal com 403.
- **Não usar header `X-Tenant-Id`** — tenant vem sempre do JWT.

## Variáveis de ambiente obrigatórias

- `SECRET_KEY` (≥ 32 chars, obrigatória sempre)
- `POSTGRES_SERVER`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- `REDIS_URL`
- `MINIO_SERVER`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`
- `OPENAI_API_KEY` (e/ou `GEMINI_API_KEY` se `LEGISLATION_USE_GEMINI_DEFAULT=true`)
- Para waitlist: `RESEND_API_KEY`, `RESEND_AUDIENCE_ID`, `RESEND_FROM_EMAIL`

Lista completa em `_env.example`.

## Endpoints principais

- API: `http://localhost:8000`
- OpenAPI: `/docs` (desabilitar em produção via `ENVIRONMENT=production`)
- Health: `GET /health`
- Métricas: `GET /metrics`
- Painel consultor: `http://localhost:5173` (dev)
- Portal cliente: `http://localhost:3000` (congelado)
- MinIO Console: `http://localhost:9001`

## Credenciais seed (dev local)

- `admin@regenteambiental.com.br` / `Seed@2026` (superuser)
- `consultor@regenteambiental.com.br` / `Seed@2026`
- `cliente@regenteambiental.com.br` / `Seed@2026`
- `campo@regenteambiental.com.br` / `Seed@2026`

> Senha pode mudar via `SEED_*_PASSWORD` no `.env`. Detalhes em `docs/operacao/SEED_DADOS.md`.

## Segurança

- NUNCA commitar `.env` no Git. O `.gitignore` deve conter `.env`.
- NUNCA expor chaves de API (OpenAI, SMTP, Resend) em código ou documentação.
- Em produção: SMTP deve estar configurado (fail-fast). Em dev: warning + skip.
- Rate limiting recomendado no `/auth/login`.
- `/api/v1/waitlist` com rate limit fixo de `10/min` por IP.
- Em produção: `/docs` desabilitado, CORS travado em domínios reais, `SECRET_KEY` rotacionada após qualquer suspeita de vazamento.

## Documentação de referência

A documentação viva está em `docs/`, organizada em 5 camadas:

| Camada | Quando consultar |
|---|---|
| `docs/manifesto/` | Visão, identidade, princípios, roadmap |
| `docs/arquitetura/` | Como o sistema é construído (referência técnica viva) |
| `docs/operacao/` | Como rodar, testar, deployar, troubleshootar |
| `docs/estado/` | Onde estamos hoje (atualizado a cada sprint) |
| `docs/adr/` | Decisões arquiteturais (imutáveis após criadas) |

### Atalhos por situação

**Pessoa nova no projeto:**
1. `README.md` (raiz)
2. `docs/manifesto/01-VISAO_PRODUTO.md`
3. `docs/manifesto/02-IDENTIDADE.md`
4. `docs/manifesto/03-PRINCIPIOS.md`
5. `docs/arquitetura/ARQUITETURA_GERAL.md`

**Dev que vai mexer no código:**
1. Este arquivo (`CLAUDE.md`)
2. `docs/arquitetura/ARQUITETURA_GERAL.md`
3. `docs/arquitetura/MODELO_DE_DADOS.md`
4. `docs/operacao/RUNBOOK_DEV.md`
5. `docs/operacao/TESTING.md`

**Vai mexer em IA / agentes:**
1. `docs/arquitetura/GOVERNANCA_IA.md`
2. `docs/adr/002-multi-llm-gateway.md`
3. `docs/adr/006-skills-procedurais.md`
4. `docs/adr/007-stage-output-content.md`

**Vai operar em produção:**
1. `docs/operacao/RUNBOOK_OPS.md`
2. `docs/arquitetura/OBSERVABILIDADE.md`
3. `docs/operacao/TROUBLESHOOTING.md`
4. `ops/production-secrets-checklist.md`

**Estado atual do projeto:** `docs/estado/ESTADO_ATUAL.md`

### Documentação histórica

`docs/_archive/` preserva 62 documentos históricos (sprints fechadas, auditorias, planos antigos, decisões revogadas). **Não usar como fonte de verdade operacional** — está lá para auditoria e contexto histórico apenas.

## Convenções de commit

```
<tipo>(<escopo>): <descrição curta>

<corpo opcional>

<rodapé opcional>
```

Tipos: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `ops`.

## Quando algo neste arquivo divergir da realidade

Este `CLAUDE.md` é a porta de entrada cognitiva do projeto. Se você descobrir que algo aqui está desatualizado:

1. **Não confie no que está aqui** — verifique o código real
2. Abra correção neste arquivo no mesmo PR onde a divergência apareceu
3. Se a divergência for grande, pode justificar ADR novo
