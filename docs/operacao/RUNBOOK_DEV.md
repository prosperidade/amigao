# Runbook Dev

**Documento:** Operação · como rodar o Regente localmente
**Estado:** vivo · atualizar quando o setup de dev mudar
**Última revisão:** 2026-05-15
**Para:** dev que vai mexer no código

---

Guia objetivo para subir o Regente Ambiental em máquina de desenvolvimento. Se você só leu o README e quer começar a programar, é aqui.

## Pré-requisitos

| Ferramenta | Versão | Por quê |
|---|---|---|
| Docker Desktop | 4.x+ | Stack tudo via compose |
| Docker Compose | v2 (embutido) | Orquestração |
| Python | 3.11 | Backend e scripts (opcional se rodar 100% docker) |
| Node.js | 20+ | Frontend (painel consultor) |
| Git | qualquer atual | Versionamento |

Plataformas suportadas: Linux, macOS, Windows (com Docker Desktop + WSL2 recomendado).

## Setup inicial (uma vez)

### 1. Clonar e entrar no repo

```bash
git clone git@github.com:<org>/regente-ambiental.git
cd regente-ambiental
```

> Se o repo ainda estiver com nome antigo (`Amigao_do_Meio_Ambiente`), funciona — GitHub redireciona após rename. Atualizar o origin é opcional: `git remote set-url origin <novo>`.

### 2. Configurar `.env`

```bash
cp .env.example .env
```

Edite `.env` e configure no mínimo:

```bash
SECRET_KEY=<rodar: openssl rand -hex 32>
# Para IA (opcional em dev):
AI_ENABLED=true
OPENAI_API_KEY=sk-proj-...
GEMINI_API_KEY=AIza...      # obrigatório se LEGISLATION_USE_GEMINI_DEFAULT=true
ANTHROPIC_API_KEY=          # opcional, fallback secundário
```

Todas as outras variáveis têm default razoável para dev. Detalhes em `.env.example`.

### 3. Subir tudo via Docker

```bash
docker compose up --build -d
```

Isso sobe 5 serviços: `db`, `redis`, `minio`, `api`, `worker`. (O serviço `client-portal` está declarado mas o código está congelado; comente em `docker-compose.yml` se reclamar.)

O `docker-compose.override.yml` aplica overrides de dev automaticamente:
- Hot-reload do API em mudanças de `.py` (uvicorn `--reload`)
- Volume montado `./app:/app/app` (mudança no host reflete no container)
- Worker **não tem** reload — exige `docker compose restart worker` quando mexer em `app/workers/` ou `app/agents/`

### 4. Verificar saúde

```bash
# API responde 200
curl http://localhost:8000/health

# Métricas Prometheus
curl http://localhost:8000/metrics

# OpenAPI
open http://localhost:8000/docs
```

### 5. Subir o frontend (painel consultor)

```bash
cd frontend
npm install
npm run dev
```

Painel em `http://localhost:5173`.

### 6. Login com seed

Credenciais padrão (`.env` `SEED_*_PASSWORD` ou hash determinístico se não definir):

| Email | Perfil | Senha (se `SEED_*=Seed@2026`) |
|---|---|---|
| `admin@regenteambiental.com.br` | superuser | `Seed@2026` |
| `consultor@regenteambiental.com.br` | consultor | `Seed@2026` |
| `cliente@regenteambiental.com.br` | cliente final | `Seed@2026` |
| `campo@regenteambiental.com.br` | equipe de campo | `Seed@2026` |

> O seed roda automaticamente no boot do `api` (script `seed.py` em `docker-compose.yml`). Detalhes em [`SEED_DADOS.md`](./SEED_DADOS.md).

## Comandos do dia a dia

### Logs

```bash
# Todos
docker compose logs -f

# Só API
docker compose logs -f api

# Só worker
docker compose logs -f worker

# Últimas 200 linhas + acompanhar
docker compose logs --tail=200 -f api
```

### Restart de um serviço

```bash
# Restart API
docker compose restart api

# Restart worker (necessário após mudar app/workers/ ou app/agents/)
docker compose restart worker
```

### Rebuild quando muda Dockerfile, requirements.txt, ou pyproject.toml

```bash
docker compose build api worker
docker compose up -d
```

### Migrations Alembic

```bash
# Criar nova migration (auto-gerada)
docker compose exec api alembic revision --autogenerate -m "sprint_X_descricao"

# Aplicar migrations pendentes
docker compose exec api alembic upgrade head

# Reverter última migration
docker compose exec api alembic downgrade -1

# Ver migration corrente
docker compose exec api alembic current
```

Convenção: nome de migration `<8-hex>_sprint_<X>_<descricao>.py`. Editar o arquivo gerado se precisar — autogenerate não pega tudo.

### Console de banco

```bash
# Postgres CLI
docker compose exec db psql -U postgres -d amigao_db

# Query rápida
docker compose exec db psql -U postgres -d amigao_db -c "SELECT count(*) FROM users;"
```

> O banco se chama `amigao_db` (codinome técnico, ver [`../adr/004-regente-vs-amigao.md`](../adr/004-regente-vs-amigao.md)).

### Console Redis

```bash
docker compose exec redis redis-cli -a redispass2026
> KEYS *
> FLUSHDB  # cuidado — limpa todo o banco 0
```

### MinIO Console

`http://localhost:9001` (login: `minioadmin` / `minioadmin` em dev).

## Rodar sem Docker (modo nativo)

Mais rápido para iterar em Python mas exige instalar Postgres/Redis/MinIO local. Geralmente vale a pena só se Docker estiver lento na sua máquina.

### Backend

```bash
# Postgres + Redis + MinIO precisam estar rodando localmente
# Aponte .env para localhost (POSTGRES_SERVER=localhost, REDIS_URL=redis://localhost:6379/0, etc.)

# Setup env Python
python -m venv venv
source venv/bin/activate         # Linux/macOS
# .\venv\Scripts\activate         # Windows
pip install -r requirements.txt

# Inicializar banco + seed
python -m app.db.init_db
python seed.py

# Subir API
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Em outro terminal: subir worker
celery -A app.core.celery_app worker --loglevel=info --pool=solo

# Em outro terminal: subir frontend (igual ao docker)
cd frontend && npm run dev
```

## Tarefas comuns

### Rodar um script de ingestão de legislação

```bash
# Federal canônicos
docker compose exec api python scripts/ingest_federais_canonicos.py

# Estadual
docker compose exec api python scripts/ingest_legislacao_estadual.py --uf GO

# Da pasta da sócia (curadoria interna)
docker compose exec api python scripts/ingest_pasta_socia.py /app/legislacao_estadual/MS
```

### Smoke real de agente

```bash
# Redator
docker compose exec api python scripts/smoke_a2_redator.py

# Diagnostico
docker compose exec api python scripts/smoke_a2_diagnostico.py
```

Custo histórico observado: $0.0030 para 7 templates do Redator em gpt-4o-mini.

### Reindex de knowledge_catalog

```bash
docker compose exec api python scripts/reindex_sync.py
```

## Padrões de código

- **Python:** Pydantic v2 (`model_config = ConfigDict(...)`, `.model_dump()`), SQLAlchemy 2 (`sqlalchemy.orm.declarative_base`), tipos PostgreSQL-only quando precisar (JSONB, Geometry).
- **TypeScript frontend:** strict mode obrigatório, **zero `any` explícito**, mutations retornam tipo consistente (async/await).
- **Migrations:** convenção `<8-hex>_sprint_<X>_<descricao>.py`.
- **Imports:** **nunca** importar símbolos não usados (TypeScript strict pega; Python aceita mas é proibido).

Detalhes completos em `CLAUDE.md` na raiz.

## Pendências e dívidas operacionais

1. **`client-portal/` e `mobile/` congelados** — ver [`../adr/009-mobile-clientportal-congelados.md`](../adr/009-mobile-clientportal-congelados.md). Não tente subir esses serviços; podem não buildar.
2. **Variáveis `AMIGAO_*` em métricas e identificadores** — não tente renomear sozinho; ver [`../adr/004-regente-vs-amigao.md`](../adr/004-regente-vs-amigao.md).
3. **Sem hot-reload no worker** — `docker compose restart worker` é o caminho.
4. **Pasta `legislação ms/` e `legislação mt/` com nomes com acento** — montadas no docker-compose como ASCII (`/app/legislacao_estadual/MS`, `/MT`). Não renomear no host sem atualizar o compose.

## Próximas leituras

- [`SEED_DADOS.md`](./SEED_DADOS.md) — detalhes do seed local
- [`TESTING.md`](./TESTING.md) — como rodar e escrever testes
- [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md) — quando algo não sobe
- [`RUNBOOK_OPS.md`](./RUNBOOK_OPS.md) — como operar em produção
