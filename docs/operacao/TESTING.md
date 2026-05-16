# Testing

**Documento:** Operação · estratégia de testes
**Estado:** vivo
**Última revisão:** 2026-05-15
**Estado atual:** 102 arquivos de teste · cobertura mínima `fail_under=70`

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
| Banco em teste | Testcontainers `postgis/postgis:15-3.3` |
| Cobertura | pytest-cov com `fail_under = 70` |
| HTTP test client | `fastapi.testclient.TestClient` |
| Fixtures | `tests/conftest.py` + arquivos por pasta |
| Mock | unittest.mock (padrão) — uso parcimonioso |

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
    with PostgresContainer("postgis/postgis:15-3.3", driver="psycopg2") as pg:
        yield pg
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

### Rodar tudo

```bash
docker compose exec api pytest tests/ -q
```

### Rodar uma pasta

```bash
docker compose exec api pytest tests/api -q
```

### Rodar um arquivo

```bash
docker compose exec api pytest tests/api/test_intake.py -q
```

### Rodar um teste específico

```bash
docker compose exec api pytest tests/api/test_intake.py::test_create_draft_success -q
```

### Com cobertura

```bash
docker compose exec api pytest tests/ --cov=app --cov-report=term-missing
```

### Saída detalhada

```bash
docker compose exec api pytest tests/ -vv
```

### Falhar no primeiro erro

```bash
docker compose exec api pytest tests/ -x
```

### Apenas testes que falharam na última execução

```bash
docker compose exec api pytest tests/ --lf
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

1. **CI/CD** — testes rodam local; não há pipeline público de CI rodando a suíte automaticamente em todo PR.
2. **Suite E2E pobre** — só 2 testes. Adicionar pelo menos: criação de proposta, fluxo de contrato, geração de PDF.
3. **Testes de regressão de prompt** — não existem hoje. Quando ajustamos prompt do Redator, não há teste que detecte regressão de qualidade.
4. **Property-based testing** — não usamos. Vale considerar para validações de schema complexas.
5. **Mutation testing** — não usamos. Vale como auditoria pontual da qualidade dos testes.

## Próximas leituras

- [`RUNBOOK_DEV.md`](./RUNBOOK_DEV.md) — setup de dev (necessário para rodar testes)
- [`SEED_DADOS.md`](./SEED_DADOS.md) — seed × fixture (são coisas diferentes)
- [`../arquitetura/GOVERNANCA_IA.md`](../arquitetura/GOVERNANCA_IA.md) — política de IA que os testes validam
