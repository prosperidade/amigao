# ADR-001 · Multi-tenant por linha (`tenant_id`)

**Status:** Aceito
**Data:** 2026-03-26 (decisão original); formalizada como ADR em 2026-05-15
**Decisores:** sócia + tecnologia

---

## Contexto

O Regente Ambiental nasceu como SaaS multi-cliente desde o dia 1. A primeira decisão de modelagem foi sobre **como isolar dados entre consultorias** (tenants) na mesma instância da plataforma.

Três modelos de tenancy existem na indústria:

1. **Banco por tenant** — cada cliente tem seu Postgres
2. **Schema por tenant** — cada cliente tem seu schema dentro do mesmo Postgres
3. **Row-level (`tenant_id` em toda tabela)** — todos os clientes dividem o mesmo schema, isolados por filtro de aplicação

O Regente atende consultorias ambientais brasileiras — perfil PME típico (5-50 funcionários). Volume esperado: dezenas a baixas centenas de tenants. Cada tenant tem milhares de entidades transacionais.

## Decisão

**Multi-tenant por linha.** Toda tabela transacional tem `tenant_id INT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT`. Isolamento é **lógico**, garantido por:

1. JWT carrega `tenant_id` extraído do `User.tenant_id` no login
2. Toda dependency injection (`app/api/deps.py`) extrai `current_tenant` do JWT
3. Toda query filtra explicitamente: `WHERE tenant_id = current_tenant.id`
4. Toda escrita valida que o `tenant_id` do payload bate com o do JWT (rejeita 403 se diferir)

Exceções deliberadas ao isolamento por tenant:
- `tenants` (entidade-raiz)
- `pre_cadastros` (lead anônimo da waitlist, pré-conta)
- `knowledge_catalog` (chunks globais com `tenant_id IS NULL`, compartilhados; tenants podem ter chunks privados)

## Consequências

**Positivas:**
- Migrations rodam **uma vez** por release, não N vezes por tenant
- Onboarding de novo tenant é `INSERT INTO tenants ...` + criação de usuário admin — segundos, não horas
- Custo de infra escala suavemente com volume, não com número de clientes
- Análise cross-tenant (anonimizada) é trivial — agregações Prometheus, métricas de produto
- Padrão dominante em SaaS B2B brasileiro PME (mercado entende)

**Negativas:**
- Bug de query sem `WHERE tenant_id = X` vaza dados entre clientes — risco inegociável
- Performance de tabela única cresce com soma de todos os tenants (precisa indexar bem `tenant_id`)
- Backup/restore por cliente é mais complexo que `pg_dump <db-do-tenant>`
- Dificuldade para residência de dados (cliente que exija "meus dados em outro país") — sem alternativa no row-level

**Mitigações:**
- Convenção rígida: toda query filtra por tenant (auditoria periódica recomendada)
- Todas as FKs com `tenant_id` indexadas (auditar com `pg_stat_user_indexes`)
- Testes de isolamento (`tests/api/test_tenant_isolation.py`) cobrem cenários cross-tenant
- Para residência de dados: encaminhar para plano white-label com instância dedicada (futuro, [`./004-regente-vs-amigao.md`](./004-regente-vs-amigao.md) e capacidade arquitetural em [`../arquitetura/WHITELABEL.md`](../arquitetura/WHITELABEL.md))

## Alternativas consideradas

**Schema por tenant.** Migrations × N tenants viram operação cara — qualquer alteração de schema (novo `Sprint X`) exigiria N execuções. Em PG, schemas separados não isolam tanto quanto parece (recursos compartilhados, conexões, locks).

**Banco por tenant.** Custos de infraestrutura proibitivos para PME. Backup, monitoramento e operação multiplicados por N. Permite isolamento físico perfeito — quando o cliente exige (legal/setorial), entra como exceção via white-label dedicado, não como padrão.

**Híbrido (row-level + opcionalmente banco dedicado).** Considerado para o futuro. Hoje row-level cobre 100% dos casos.

## Status de execução

| Item | Estado |
|---|---|
| `tenant_id` em todas as tabelas transacionais | ✅ |
| Dependency injection extraindo `tenant_id` do JWT | ✅ `app/api/deps.py` |
| Validação de tenant na escrita — `tenant_id` da própria linha | ✅ Service layer |
| Validação de tenant na escrita — **FKs recebidas no payload** | ✅ `app/services/tenant_guard.py` (10/08) |
| Tests de isolamento (leitura e edição) | ✅ `tests/api/test_tenant_isolation.py` |
| **Fumaça cross-tenant na escrita** | ✅ `tests/api/test_tenant_smoke_escrita.py` (10/08) |
| FK composta `(tenant_id, id)` no banco | ❌ Dívida #128 |
| `Tenant.ai_monthly_budget_usd` (cost cap por tenant) | ✅ Sprint R |

> **Nota de execução — 2026-08-10 (`fix/tenant-integridade-escrita`).** A linha
> "lint automático que detecte query sem filtro" estava ❌ Pendente desde a
> abertura deste ADR, em 26/03/2026. Foi **entregue como teste de fumaça**, não
> como lint: uma regra estática que procurasse `query()` sem filtro de tenant
> teria falso positivo demais (busca global legítima no corpus legislativo,
> agregação já escopada uma camada acima) e nenhum poder sobre o caso que de
> fato causou dano — a FK que **chega no corpo da requisição** e nunca era
> olhada. O teste exercita o caminho real com dois tenants.
>
> Os quatro meses e meio de pendência não foram inócuos: nesse intervalo
> nasceram os achados AUD-04-01/02/04/07 da auditoria Codex — seis endpoints
> aceitando FK alheia, um deles **gravando** `closed_at` em processo de outro
> tenant. A mitigação prevista aqui teria pegado todos.

## Relação com outros ADRs

- [`004-regente-vs-amigao.md`](./004-regente-vs-amigao.md) — identidade do produto que opera no modelo multi-tenant
- [`009-mobile-clientportal-congelados.md`](./009-mobile-clientportal-congelados.md) — frentes secundárias que herdam o mesmo modelo quando descongeladas
