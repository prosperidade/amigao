# Testing

**Documento:** Operação · estratégia de testes
**Estado:** vivo
**Última revisão:** 2026-05-17
**Estado atual:** 102 arquivos de teste · cobertura mínima `fail_under=70` · **339 testes passando no host**

---

Estratégia de testes do Regente Ambiental: o que testamos, como testamos, e como manter a suíte saudável.

## Filosofia

1. **Testes existem para dar coragem de mudar.** Se o teste não te dá coragem de tocar o código, ele é peso.
2. **Pirâmide invertida não.** A maioria dos testes é de unidade/serviço — rápidos. Testes E2E são poucos, caros, e cobrem o fluxo crítico.
3. **PostgreSQL real, não mock.** Mocks de banco mentem. Testcontainers garante que o teste roda no mesmo Postgres da produção.
4. **Test trumps doc.** Quando o teste diverge da doc, é a doc que está errada (na maioria dos casos).

## Stack de teste

| Item | Ferramenta |
|---|---|
| Framework | pytest |
| Banco em teste | Testcontainers `amigao_do_meio_ambiente-db:latest` (postgis + pgvector) — fallback `pgvector/pgvector:pg15` |
| Onde roda | **Host com venv local** (não dentro do container `api`) — Testcontainers usa Docker do host, sem Docker-in-Docker |
| Cobertura | pytest-cov com `fail_under = 70` |
| HTTP test client | `fastapi.testclient.TestClient` |
| Fixtures | `tests/conftest.py` + arquivos por pasta |
| Mock | unittest.mock (padrão) — uso parcimonioso |

## Setup do venv local (uma vez por máquina)

Pré-requisitos: Python ≥ 3.11, Docker Desktop rodando.

```powershell
# Windows
.\scripts\setup-dev.ps1
```

```bash
# Linux / Mac / Git Bash
./scripts/setup-dev.sh
```

O script:
1. Apaga `.venv` antigo se existir
2. Cria novo `.venv` com Python do host
3. Atualiza pip
4. Instala `requirements-dev.txt` (puxa runtime via `-r requirements.txt`)

Depois:

```powershell
.\.venv\Scripts\Activate.ps1     # PowerShell
.venv\Scripts\activate.bat       # cmd
source .venv/Scripts/activate    # Git Bash (Windows) / bash (Linux/Mac)
```

E uma vez antes do primeiro pytest (gera a imagem com postgis + pgvector):

```bash
docker compose build db
```

## Por que no host e não no container `api`?

Testcontainers precisa **acessar o Docker daemon** pra subir o Postgres efêmero. Duas formas:

| Opção | Tradeoff |
|---|---|
| **No host** (atual) | Docker do host é usado; sem Docker-in-Docker; sem mount de socket no container; mesmo caminho de CI (GitHub Actions runner com Docker preinstalado). **Padrão senior.** |
| Dentro do container `api` com `/var/run/docker.sock:/var/run/docker.sock` | Container HTTP ganha acesso ao Docker daemon = acesso root ao host. Antipadrão de segurança. Rejeitado. |

## Estrutura

```
tests/
├── conftest.py             ← fixtures de sessão (Postgres container, db_session, client)
├── agents/                 11 testes — agentes IA
├── api/                    12 testes — endpoints REST
├── core/                   testes do core (config, security, ai_gateway, etc.)
├── e2e/                    2 testes — fluxos completos (intake, document)
├── models/                 testes de modelo (validação, transições)
├── schemas/                testes de Pydantic
├── services/               testes de serviços
├── skills/                 testes de carregamento de skills
└── test_*.py               testes soltos (alerts, email, pdf, seed, etc.)
```

102 arquivos no total. Cobertura mínima exigida: **70%** (`pytest-cov`, configurada em `pyproject.toml`).

## Como o banco de teste funciona

Estratégia em `tests/conftest.py`:

```python
@pytest.fixture(scope="session")
def _pg_container():
    # Imagem customizada do projeto (postgis + pgvector) — built via docker/db/Dockerfile.
    # Fallback pra pgvector/pgvector:pg15 se a imagem custom não estiver presente.
    image = "amigao_do_meio_ambiente-db:latest"
    try:
        docker.from_env().images.get(image)
    except Exception:
        image = "pgvector/pgvector:pg15"
    with PostgresContainer(image, driver="psycopg2") as pg:
        yield pg
```

E o `db_engine` cria as 2 extensões antes do schema:

```python
with engine.begin() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))  # knowledge_catalog usa vector(768)
Base.metadata.create_all(bind=engine)
```

**Uma única container** sobe no início da sessão de testes. Permanece viva até o fim. Cada teste recebe uma **session SQLAlchemy** dentro de uma **transação que rolla back** ao final:

```python
@pytest.fixture(scope="function")
def db_session(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()   # ← isso aqui apaga tudo
    connection.close()
```

Vantagens:
- Sem custo de recriar schema entre testes
- Isolamento total entre testes
- Roda em qualquer máquina com Docker

Desvantagem:
- Cada teste só "vê" o que ele mesmo criou ou fixtures setadas para a session

## Categorias de teste

### 1. Unitário (serviço, modelo, schema)

Roda em milissegundos. Testa função pura ou método com poucos colaboradores. Não toca banco a menos que precise.

Exemplo: `tests/schemas/test_stage_output.py` valida que `PecaJuridicaContent` rejeita `template="oficio"` sem `addressee`.

### 2. Integração (com banco)

Testa interação entre service e banco. Usa `db_session` fixture. Cobertura média.

Exemplo: `tests/services/test_knowledge_catalog.py` ingere chunks fake, faz query semântica, valida ordenação por similaridade.

### 3. API (com TestClient)

Testa endpoint via TestClient (request real, com JWT). Usa `client` fixture (cliente HTTP).

Exemplo: `tests/api/test_intake.py` faz POST de draft, GET, PATCH, commit, valida 201/200/403 conforme cenário.

### 4. End-to-end

Fluxo completo do usuário. Mais lentos, mais frágeis. Mantemos poucos — 2 hoje:

- `tests/e2e/test_intake_flow.py` — wizard 5 passos → commit → Process criado
- `tests/e2e/test_document_flow.py` — upload → OCR → extração → preenchimento de Hub

### 5. Skills

Testa que o registry de skills (`app/skills/registry.py`) carrega corretamente, que o matching `applies_to` funciona, e que skills são injetadas no system prompt.

Exemplo: `tests/skills/test_loader.py` cria SKILL.md fake com YAML, carrega via registry, valida que matching com `demand_type=car`, `doc_type=oficio` retorna a skill.

### 6. Agentes

Testa o lifecycle do `BaseAgent` e dos agentes específicos. Geralmente com `ai_gateway` mockado para não chamar IA real.

Exemplo: `tests/agents/test_redator_a2.py` valida que `RedatorAgent` emite `PecaJuridicaContent` correto com `requires_review=True`.

## Smoke tests (não-pytest)

Além da suíte automatizada, há **smoke tests manuais** que chamam IA real:

- `scripts/smoke_a2_redator.py` — gera 7 templates de peça com gpt-4o-mini
- `scripts/smoke_a2_diagnostico.py` — gera diagnóstico preliminar
- `ops/run_homologation_smoke.py` — smoke fim a fim em homologação

Esses **custam dinheiro** (IA real) e não rodam em CI por padrão. Rodam:

- Manualmente antes de release importante
- Como parte do checklist de hardening de produção
- Quando o agente sofre mudança significativa de prompt/lógica

Custo histórico observado: `$0.0030` para 7 templates do Redator.

## Comandos do dia a dia

> Antes: `.\.venv\Scripts\Activate.ps1` (Windows) ou `source .venv/bin/activate` (Linux/Mac).

### Rodar tudo (sem cobertura — mais rápido)

```bash
pytest tests/ -q --no-cov
```

### Rodar tudo com cobertura

```bash
pytest tests/ --cov=app --cov-report=term-missing
```

### Rodar uma pasta

```bash
pytest tests/api -q --no-cov
```

### Rodar um arquivo

```bash
pytest tests/api/test_intake.py -q --no-cov
```

### Rodar um teste específico

```bash
pytest tests/api/test_intake.py::test_create_draft_success -v --no-cov
```

### Saída detalhada com traceback completo

```bash
pytest tests/ -vv --tb=long --no-cov
```

### Falhar no primeiro erro

```bash
pytest tests/ -x --no-cov
```

### Apenas testes que falharam na última execução

```bash
pytest tests/ --lf --no-cov
```

## Boas práticas

### Nomeação

```python
def test_<o_que_acontece>_<em_que_condicao>():
    ...

# bom:
def test_create_draft_returns_400_when_consentimento_missing(): ...
def test_redator_emits_pecajuridicacontent_with_requires_review_true(): ...

# ruim:
def test_draft(): ...     # vago demais
def test_1(): ...         # nunca
```

### Arrange / Act / Assert

```python
def test_classify_returns_demand_type():
    # Arrange
    process = create_process_with_status(ProcessStatus.lead)

    # Act
    result = classify_demand(process)

    # Assert
    assert result.demand_type == DemandType.car
    assert result.confidence >= 0.7
```

### Isolamento

Cada teste cria suas próprias fixtures. Não depende de ordem. Não depende de estado anterior.

### Quando mockar IA, quando não

| Caso | Mockar? |
|---|---|
| Unitário que testa lógica do agente | Sim — mock `ai_gateway.complete` |
| Integração que testa workflow ao redor do agente | Sim — mock o response |
| Smoke test antes de release | Não — IA real, custa $0.003 e vale a pena |
| Teste de regressão de prompt | Não — IA real, mas em script à parte |

Mock de IA é feito retornando `AIResponse(content=..., cost_usd=0.0001, ...)`. Não precisa esquema complexo.

## Cobertura

Atual: ~70% (mínimo enforced via `fail_under=70` em `pyproject.toml`).

Áreas com cobertura alta:
- `app/schemas/` (validação Pydantic é fácil de testar)
- `app/services/audit_hash.py` (lógica pura)
- `app/services/legislation_service.py` (rotinas críticas cobertas)

Áreas com cobertura média/baixa:
- `app/workers/` — celery tasks são mais difíceis de testar isoladamente
- `app/agents/` — depende de mock de IA, alguns agentes têm cobertura parcial
- `app/api/websockets.py` — testar WS é caro

**Não correr atrás de 100%.** Foco em garantir que código crítico está coberto. Cobertura alta de getter/setter trivial é ilusão de segurança.

## Pendências e dívidas

1. **State-leakage entre testes (rate limit slowapi + DB)** — 29 testes que **passam isolados falham na suite completa**. Causas: (a) slowapi mantém rate-limit state em processo, vaza entre testes — ex: `test_intake_full_flow` recebe 429 quando rodado depois de outros testes do mesmo cenário; (b) alguns testes committam transações em vez de usar o `db_session` que faz rollback. Solução prevista: fixture `autouse=True` que reseta `slowapi.Limiter._storage`; auditar testes que committam manualmente. Sprint dedicada de saneamento.
2. **CI/CD** — testes rodam local; não há pipeline público de CI rodando a suíte automaticamente em todo PR. Próximo passo: `.github/workflows/tests.yml` com runner Linux + Docker preinstalado, executando `./scripts/setup-dev.sh && pytest tests/`.
3. **Suite E2E pobre** — só 2 testes. Adicionar pelo menos: criação de proposta, fluxo de contrato, geração de PDF.
4. **Testes de regressão de prompt** — não existem hoje. Quando ajustamos prompt do Redator, não há teste que detecte regressão de qualidade.
5. **Property-based testing** — não usamos. Vale considerar para validações de schema complexas.
6. **Mutation testing** — não usamos. Vale como auditoria pontual da qualidade dos testes.

## Próximas leituras

- [`RUNBOOK_DEV.md`](./RUNBOOK_DEV.md) — setup de dev (necessário para rodar testes)
- [`SEED_DADOS.md`](./SEED_DADOS.md) — seed × fixture (são coisas diferentes)
- [`../arquitetura/GOVERNANCA_IA.md`](../arquitetura/GOVERNANCA_IA.md) — política de IA que os testes validam
