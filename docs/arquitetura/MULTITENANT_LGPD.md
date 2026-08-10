# Multi-tenant e LGPD

**Documento:** Arquitetura · referência viva
**Estado:** atualizar quando política de retenção ou isolamento mudar
**Última revisão:** 2026-05-15
**Base legal:** Lei 13.709/2018 (LGPD)

---

Política completa de isolamento entre tenants e conformidade LGPD aplicada no Regente Ambiental.

## Modelo de tenancy

### Tipo: Multi-tenant por linha (row-level)

Toda tabela transacional tem `tenant_id INT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT`. Não há separação por schema, banco, ou container. **Isolamento é lógico**, garantido por filtro de aplicação em toda query.

### Por que não outros modelos

| Modelo | Por que não |
|---|---|
| Schema por tenant | Migrations × 100 tenants vira pesadelo operacional |
| Banco por tenant | Idem. Custo de infra explode. |
| Container por tenant | Idem. Não escala para o tipo de cliente do Regente. |

Row-level com filtro em aplicação é o padrão da maioria dos SaaS B2B que servem PMEs. Tem custo (toda query precisa lembrar de filtrar; bug pode vazar dados), mas é o que escala dentro do orçamento de operação esperado.

### Exceções ao multi-tenant

| Entidade | Por quê sem `tenant_id` |
|---|---|
| `tenants` | É a própria entidade-raiz |
| `pre_cadastros` | Lead anônimo pré-conta (waitlist) |
| `knowledge_catalog` (chunks de fonte global) | Conhecimento compartilhado entre tenants (legislação federal/estadual, manuais públicos) |
| `audit_logs` | Tem `tenant_id` mas alguns eventos infraestruturais persistem com NULL (alertas operacionais do sistema) |

`knowledge_catalog` tem comportamento dual: pode ter `tenant_id = NULL` (global, visível para todos) ou `tenant_id = X` (privado do tenant X). Busca semântica filtra: `WHERE tenant_id IS NULL OR tenant_id = :current`.

## Como o isolamento é garantido

### Camada 1 — JWT carrega `tenant_id`

Login resolve qual tenant pertence ao usuário (via `User.tenant_id`) e embute no JWT. Toda requisição autenticada extrai `tenant_id` do token. **Não há header `X-Tenant-Id`** — anti-padrão, abre porta para troca de tenant pela aplicação cliente.

### Camada 2 — Dependency injection

`app/api/deps.py` tem dependencies que retornam:
- `current_user` (extraído do JWT)
- `current_tenant` (derivado de `current_user.tenant_id`)
- `db_session` (sessão SQLAlchemy)

Toda função de router que precisa de dados do tenant injeta `current_user` ou `current_tenant`. Sem injeção, o endpoint não roda.

### Camada 3 — Filtro em toda query

Convenção: todo `db.query(Entidade).filter(Entidade.tenant_id == current_user.tenant_id)`. Quebrar essa convenção em um router vira bug de segurança.

**Auditoria periódica** dessa convenção: entregue como **teste de fumaça** em
`tests/api/test_tenant_smoke_escrita.py` (2026-08-10) — dois tenants reais, e cada endpoint
de escrita que aceita FK no corpo é exercitado com id do outro tenant, exigindo 404. Lint
estático de `ruff` continua não existindo: uma regra que detectasse `query()` sem filtro
teria falso positivo demais (query global legítima do corpus, agregação por tenant já
escopada). O teste roda o caminho real e não depende de heurística sobre o código.

### Camada 4 — Validação na escrita: o `tenant_id` da linha **e** as relações que ela aponta

São duas coisas distintas, e por muito tempo só a primeira existia:

1. **O `tenant_id` da própria entidade** vem sempre do JWT, nunca do corpo.
   `BaseRepository.create` (`app/repositories/base.py`) injeta `tenant_id=self.tenant_id`;
   os routers que montam o ORM à mão passam `tenant_id=current_user.tenant_id`. Um
   `tenant_id` forjado no corpo é ignorado, não copiado.

2. **As FKs que chegam no corpo** (`client_id`, `process_id`, `property_id`, `proposal_id`,
   `responsible_user_id`, …) são resolvidas **dentro do tenant** antes de qualquer escrita,
   por `app/services/tenant_guard.py`. Entidade que não pertence ao tenant do requisitante
   responde **404**.

> **Por que 404 e não 403** (decisão de 2026-08-10): um 403 confirma que a entidade existe.
> O endpoint vira oráculo de enumeração — o atacante varre ids e aprende o tamanho e o mapa
> do outro tenant sem ler um único byte de dado. "Não existe para você" é a semântica
> correta, e é a que `BaseRepository.get_or_404` já praticava para a entidade principal.
>
> *Histórico: até 2026-08-10 este documento afirmava que a Camada 4 rejeitava relação
> cross-tenant com 403. Era falso nos dois sentidos — não havia validação de relação, e a
> resposta pretendida estava errada. A auditoria Codex (AUD-04-01/02) mediu, a triagem
> (PR #146, achados D1-D3) confirmou, e a Frente 1 corrigiu código e documento juntos.*

### Camada 5 — Tests de isolamento

`tests/api/test_tenant_isolation.py` cobre leitura e edição de entidade de outro tenant;
`tests/api/test_tenant_smoke_escrita.py` cobre a criação com FK de outro tenant. Cenários:
- Usuário do tenant A tenta ler entidade do tenant B → **404** (não vaza existência)
- Usuário do tenant A tenta editar entidade do tenant B → **404**
- Usuário do tenant A cria entidade referenciando FK de B → **404**
- Usuário do tenant A confirma upload com `storage_key` de B → **400** (a chave não é
  entidade cuja existência se possa vazar; é campo malformado do próprio payload)
- Lista de recursos só retorna entidades do tenant do usuário

## Cost cap por tenant

`Tenant.ai_monthly_budget_usd` permite teto personalizado de gasto com IA por tenant. NULL = usa default global (`AI_BUDGET_USD_MONTHLY_PER_TENANT_DEFAULT`). `0` = ilimitado.

Endpoint `GET /api/v1/agents/budget` retorna estado atual:

```json
{
  "month_start_utc": "2026-05-01T00:00:00Z",
  "spent_usd": 12.34,
  "budget_usd": 50.00,
  "remaining_usd": 37.66,
  "percent_used": 24.68
}
```

Tarefa Celery que estouraria orçamento marca como `skipped_budget` e emite alerta operacional.

## White-label (resumo)

Tenants em modo white-label podem ter:

- Domínio próprio (subdomínio CNAME apontando para Regente)
- Logotipo/cor próprios no painel e em PDFs gerados
- Credenciais próprias de IA (OpenAI/Gemini próprias) — o gateway honra `Tenant.openai_api_key` quando configurado
- Templates de contrato próprios (`ContractTemplate.tenant_id`)
- Prompts próprios (`PromptTemplate.tenant_id`)

Detalhes em [`WHITELABEL.md`](./WHITELABEL.md).

## LGPD — base legal

### Bases de tratamento aplicáveis

| Dado | Base legal | Onde aplicada |
|---|---|---|
| Dados do consultor (User) | Execução de contrato com o tenant | App inteira |
| Dados do cliente final (Client) | Tenant é controlador; Regente é operador | Cliente Hub |
| Dados de imóvel (Property) | Idem | Imóvel Hub |
| Documentos (CPF, CNPJ, matrículas) | Idem | Storage |
| Dados de lead na waitlist (PreCadastro) | Consentimento explícito (campo `consentimento` bloqueante) | `pre_cadastros` |
| Comunicações (Communication) | Idem cliente | Threads |

### Papéis LGPD

- **Tenant (consultoria)** é **controlador** dos dados dos seus clientes finais. Decide para que serve, com quem compartilha, etc.
- **Regente Ambiental** é **operador**: trata dados sob instrução do controlador. Acordo de operador documentado em [contrato de adesão do tenant — TODO formalizar].

## Retenção de dados

| Tipo de dado | Política de retenção |
|---|---|
| `User` | Mantido enquanto o tenant existir. Soft delete (`deleted_at`) preserva por 5 anos para auditoria. |
| `Client` | Mantido enquanto o tenant existir. Soft delete por 5 anos. |
| `Process` arquivado | Mantido 7 anos (boa prática contábil + ambiental). |
| `Document` | Mantido 7 anos. MinIO replica para storage frio após arquivamento do processo. |
| `AuditLog` | Mantido 10 anos. Hash chain impede edição. |
| `AIJob` | Mantido 2 anos (operacional + análise de qualidade). Após, agregado e anonimizado para métricas. |
| `PreCadastro` (waitlist) | Mantido enquanto o lead não pedir exclusão. Soft delete (`deleted_at`) bloqueia novos contatos. |
| Logs de requisição (HTTP) | 90 dias (rotação automática). |
| Backups completos do DB | 30 dias. |

## Direitos do titular (LGPD art. 18)

| Direito | Como atende |
|---|---|
| Confirmação de existência | Endpoint `GET /api/v1/clients/me` (futuro — TODO) |
| Acesso aos dados | Endpoint de export do `Client` por `tenant + client` (futuro — TODO) |
| Correção | Edição via API/UI ou pedido formal ao controlador (tenant) |
| Anonimização | Soft delete + sobrescrita de campos sensíveis após X dias |
| Eliminação | Pedido formal ao tenant; Regente executa quando autorizado |
| Portabilidade | Export JSON dos dados do cliente (futuro — TODO) |
| Revogação de consentimento | Para waitlist: link `unsubscribe_url` em todo e-mail. Para cliente final: pedido ao tenant. |

## Pendências LGPD (a formalizar)

1. **Política de privacidade pública** — landing precisa ter `/privacidade.html` antes da waitlist escalar (Sprint Waitlist R4).
2. **Acordo de operador formal** com o tenant — documento jurídico padrão.
3. **Endpoints de exercício de direitos** — `GET /api/v1/clients/me/export`, `POST /api/v1/clients/me/delete-request`.
4. **DPO formalmente designado** — exigência LGPD para tenant que processa volume relevante.
5. **Mapa de dados (RIPD/RoPA)** — registro de operações de tratamento (art. 37 LGPD).

## Auditoria de acesso

`AuditLog` registra:
- Quem acessou (`user_id` + `ip_address` + `user_agent`)
- O que acessou (`entity_type` + `entity_id`)
- Quando (`created_at`)
- Em que tenant (`tenant_id`)
- Encadeamento de integridade (`hash_previous` + `hash_sha256`)

Para investigação de incidente, query simples por `tenant_id + entity_id` reconstrói toda a trilha.

## Segregação de credenciais

- **Senhas:** hash bcrypt (custo configurável, default 12)
- **JWT secret:** `SECRET_KEY` em `.env`, mínimo 32 chars, validado em boot
- **Credenciais IA:** opcionalmente por tenant (`Tenant.openai_api_key`, etc.) com criptografia em repouso (TODO — hoje em texto puro no campo, validar antes de produção)
- **Credenciais MinIO/Postgres:** apenas via env, nunca em código
- **Credenciais SMTP/Resend:** idem
- `app/core/security.py:warm_up_security` valida no boot que `SECRET_KEY` não é default e que em produção `RESEND_API_KEY` está configurada

## Próximas leituras

- [`WHITELABEL.md`](./WHITELABEL.md) — política white-label completa
- [`OBSERVABILIDADE.md`](./OBSERVABILIDADE.md) — onde os logs vivem
- [`MODELO_DE_DADOS.md`](./MODELO_DE_DADOS.md) — schema das tabelas com `tenant_id`
