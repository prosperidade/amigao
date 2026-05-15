# Sprint Waitlist — Fase 0 (PARE E PERGUNTE) — Report estruturado

**Data:** 2026-05-13
**Branch:** `main` (head SHA não verificado — acesso via UNC, sem `git` disponível na sessão)
**Prompt:** "PROJETO: Regente Ambiental — captura de waitlist + Resend + drip"
**Repo analisado:** `\\DESKTOP-L0VOP07\...\Amigao_do_Meio_Ambiente`
**Landing:** estática em HTML/CSS/JS puro (Modelo 3 Técnico), hospedada em Netlify Drop, domínio `regenteambiental.com.br` — **não migrar**.
**Status:** aguardando sinal verde explícito antes de qualquer commit em código de produção.

---

## Step 1 — Arquivos lidos (Fase 0 sem código)

Lidos integralmente:

- `CLAUDE.md` (regras de código, estrutura, comandos)
- `requirements.txt` + `pyproject.toml` (stack confirmado)
- `app/main.py` (mount de routers, CORS, middlewares, lifespan)
- `app/core/config.py` (Settings, validators, smtp_configured property)
- `app/core/celery_app.py` (broker, beat schedule, signals)
- `app/core/rate_limit.py` (slowapi Limiter por IP)
- `app/services/email.py` (EmailService SMTP atual + templates HTML inline)
- `app/services/notifications.py` (realtime via Redis pubsub + audit_log helper)
- `SPRINT_A1_FASE0_REPORT.md` (template seguido aqui)

Listados (sem leitura integral, só inventário):

- `app/api/v1/*.py` — 22 routers existentes (auth, clients, processes, intake, documents, properties, tasks, threads, regulatory, ai, agents, knowledge, legislation, etc.)
- `app/models/*.py` — 28 entidades (user, tenant, client, process, ai_job, audit_log, etc.) — **nenhuma menção a waitlist, pre_cadastro, lead ou resend**
- `app/services/*.py` — 22 serviços — **nenhum cliente Resend; email.py é SMTP via smtplib**
- `app/workers/*.py` — 10 módulos de tasks Celery — **nenhuma task de drip/welcome de waitlist**
- `app/schemas/*.py` — 24 schemas Pydantic
- `alembic/versions/` — convenção `<8-hex>_sprint_<X>_<descricao>.py`; última migration relevante `b9d2e5a8f4c1_sprint_a1_intake_classification_feedback.py`

Stack **real em runtime** (do `requirements.txt` + report A1 anterior):

| Dependência | Versão | Observação |
|---|---|---|
| Python | 3.11 | `requires-python = ">=3.11"` em pyproject |
| FastAPI | 0.136.1 | confirmado no report A1 |
| Pydantic | 2.12.5 | v2 obrigatório |
| SQLAlchemy | 2.0.49 | `declarative_base` em `sqlalchemy.orm` |
| Alembic | 1.18.4 | versões em `alembic/versions/` |
| Celery | — | broker Redis, autodiscover em `app.workers` |
| slowapi | >=0.1.9 | **já instalado**; limiter em `app.core.rate_limit` |
| httpx | — | **já instalado** (uso ideal pro cliente Resend) |
| email-validator | — | já instalado (Pydantic `EmailStr` funciona) |

---

## (a) Divergências encontradas entre proposta × código real

### 1. Path `POST /waitlist` quebra a convenção `API_V1_STR`

Brief afirma "Backend deve expor endpoint público em `api.regenteambiental.com.br`" e lista `POST /waitlist` (sem prefixo). Mas **todos os 22 routers existentes** em `app/main.py:134-158` são montados com `prefix=f"{settings.API_V1_STR}/..."` onde `API_V1_STR = "/api/v1"`. Os únicos endpoints fora desse prefixo são `/`, `/health`, `/metrics` — todos infraestruturais.

**Impacto:** Se `/waitlist` for root-level, é o primeiro endpoint funcional fora do versionamento. Cria precedente ambíguo.

**Caminhos:**
- **(a) `/api/v1/waitlist`** — segue convenção; URL final fica `https://api.regenteambiental.com.br/api/v1/waitlist`. Verbose mas consistente.
- **(b) `/waitlist`** — quebra convenção mas casa com o discurso "endpoint público marketing". URL fica `https://api.regenteambiental.com.br/waitlist`.

Minha recomendação: **(a)**. O custo cognitivo de URL mais longa é zero (snippet JS é dev-only); o ganho de manter convenção é alto.

### 2. `app/services/email.py` é SMTP, não tem cliente Resend

Brief F5 diz "Resend client: módulo `app/services/resend_client.py`". Mas existe **`app/services/email.py:11-79`** com `EmailService` usando `smtplib` puro:

- `EmailService.send_email(email_to, subject, html_content) -> bool` — sync, retorna bool
- Templates inline em [app/services/email.py:82-137](app/services/email.py#L82) (`_base_template`, `format_process_status_email`, `format_internal_document_uploaded_email`, `format_notification_template`)
- Métricas: `record_email_delivery("success"/"failed"/"skipped")` em `app/core/metrics.py`
- Alertas: `emit_operational_alert(category="email_delivery", severity="error", ...)` em falha
- Settings: `SMTP_HOST/PORT/USER/PASSWORD/TLS`, `EMAILS_FROM_EMAIL`, `EMAILS_FROM_NAME`
- Validator: `settings.smtp_configured` property; falha-rápido em prod ([config.py:250](app/core/config.py#L250)); warn+skip em dev

**Você confirmou (2026-05-13)** que quer **migração total** do EmailService para Resend, não coexistência. Implicações:

- `app/services/email.py` é refatorado: `EmailService` passa a delegar para `resend_client.py` (driver único). Pode-se renomear pra `EmailService` → `MailService` ou manter o nome (menos churn nos callers).
- Os 4 callers atuais (`process_status_email`, `internal_document_uploaded_email`, `notification_template`, e os pontos que chamam `EmailService().send_email(...)`) **precisam continuar funcionando** — não dá pra quebrar o portal interno.
- Settings `SMTP_*` deixam de ser obrigatórios em prod. Validator em [config.py:250](app/core/config.py#L250) precisa virar `resend_configured` (`RESEND_API_KEY` set).
- `settings.smtp_configured` continua existindo como property (deprecated) ou é removida. Recomendo remover na mesma sprint.
- Mailtrap dev (linha 86 da config) some ou vira um "Resend test mode" (Resend tem sandbox via `from: "onboarding@resend.dev"`).

### 3. `EMAILS_FROM_EMAIL = "noreply@amigao.com"` ≠ `contato@regenteambiental.com.br`

Brief assumption E: "Email remetente: `contato@regenteambiental.com.br`". Config atual aponta `noreply@amigao.com`.

**Decisão necessária:**
- Domínio remetente único: trocar `EMAILS_FROM_EMAIL` para `contato@regenteambiental.com.br`. Todos os emails (waitlist E portal interno) saem desse remetente.
- Domínio por contexto: introduzir `EMAILS_FROM_WAITLIST = "contato@regenteambiental.com.br"` separado do `EMAILS_FROM_TRANSACTIONAL = "noreply@amigao.com"`. Mais flexível mas dobra config.

Se o produto-mãe ainda é "Amigão" e Regente é submarca lançando standalone, recomendo **dois domínios** (e dois remetentes). Ver divergência #4.

### 4. Confusão entre "Regente" e "Amigão do Meio Ambiente"

O repo se chama `Amigao_do_Meio_Ambiente`. `PROJECT_NAME = "Amigão do Meio Ambiente"`. Mas existem pastas `regente_sass/` e `amigao_regente/` no root, e o landing usa `regenteambiental.com.br` com identidade visual própria ("Do caos ao compasso", paleta Verde Maestro / Dourado Cerrado).

**Questão arquitetural:** O Regente é um produto separado, uma submarca, ou uma fase do Amigão? Isso decide:
- Se o `pre_cadastros` é tenant-bound (`tenant_id` do Regente como tenant especial) ou cross-tenant
- Se o welcome email diz "Bem-vindo ao Amigão" ou "Bem-vindo ao Regente"
- Se o subdomínio `api.regenteambiental.com.br` é a mesma app FastAPI servindo `api.amigaoambiental.com.br` (vhosts diferentes, mesma binário) ou app separada

Brief silencia sobre isso. **Default que vou assumir se não houver correção:** Regente é uma submarca do Amigão; mesma API; `pre_cadastros` não tem `tenant_id` (lead anônimo, vira `usuario` num tenant Regente após onboarding manual).

### 5. Multi-tenant: `pre_cadastros` SEM `tenant_id`

CLAUDE.md regra 9: "Tenant isolation: toda query deve filtrar por `tenant_id`." Mas waitlist é PRE-conta — não há tenant. A tabela `pre_cadastros` precisa **não ter** coluna `tenant_id` (lead anônimo). Após conversão, `converted_user_id` aponta pro `User` (que carrega `tenant_id` próprio).

**Sub-implicações:**
- O `AuditLog` ([app/models/audit_log.py]) provavelmente tem `tenant_id NOT NULL` — **não posso usar AuditLog pra registrar evento de signup de waitlist**. Solução: log estruturado em JSON (`app.core.logging.get_logger`) só, sem trilha de auditoria. Aceitável pra lead pré-conversão.
- Eventual `notifications.publish_realtime_event` em [notifications.py:34](app/services/notifications.py#L34) também exige `tenant_id` — não dá pra notificar admin via WebSocket quando lead entra. Solução: notificação por email pro admin (separada do drip) ou panel batch.

### 6. Naming Portuguese vs English nos modelos

Brief usa **Portuguese** pra campos: `nome`, `telefone`, `perfil_profissional`, `tipo_licenciamento`, `volume_mensal`, `ferramenta_atual`, `preco_aceito`, `expectativa`, `deal_breaker`, `interesse_grupo`. Mas o repo mistura:
- Tabelas Portuguese: `usuarios` (presumível, mas modelo se chama `user.py`), `clientes` (model `client.py`), `processos` (model `process.py`)
- Colunas English na maioria: `User.email`, `Process.demand_type`, `Process.initial_diagnosis`, `Client.tenant_id`
- Colunas Portuguese em alguns: `Process.demanda` (verificar)

**Recomendação:** seguir o padrão do **modelo dominante**. Verei `app/models/user.py` no início da execução para decidir. Default que vou assumir: **manter os nomes do brief em Portuguese** (`nome`, `telefone`, `perfil_profissional`...) já que o domínio é PT-BR e brief foi explícito. Trade-off: leve inconsistência com `User.email` (English).

### 7. `preco_aceito (json: faixas Van Westendorp)` — schema interno do JSONB

Brief F1 lista `preco_aceito (json: faixas Van Westendorp)`. Van Westendorp PSM (Price Sensitivity Meter) tem 4 perguntas canônicas: barato_demais, barato, caro, caro_demais (cada uma um valor numérico em R$). O JSONB precisa de schema explícito pra validação.

**Default:**
```json
{
  "barato_demais": 49,
  "barato": 99,
  "caro": 299,
  "caro_demais": 499
}
```
Validar via Pydantic schema interno (`PrecoVanWestendorp(BaseModel)`) antes de gravar no JSONB. Documentar que valores são inteiros em BRL.

### 8. UTM fields: explodir em colunas ou JSONB?

Brief F1 lista `utm_*` sem detalhar. Convenção UTM tem 5 campos: `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`. Padrões:

- **(a) 5 colunas separadas** — mais query-friendly (filtrar por campaign no BI direto)
- **(b) Coluna `utm` JSONB** — mais flexível (campos novos sem migration)

Convenção do repo: padrão de "metadata_jsonb" aparece em `IntakeDraft.form_data` e similares. Mas pra analytics, colunas indexáveis são melhores. Recomendo **(a) 5 colunas separadas + 1 índice composto em `utm_source, utm_campaign`**.

### 9. `interesse_grupo` ambíguo

Brief F1 lista `interesse_grupo` sem tipo. Boolean (sim/não)? Array de IDs de grupo? Texto livre? Default que vou assumir: **boolean** (`interesse_grupo: bool` = "tem interesse em participar de grupo de discussão de fundadores"). Trivial mudar se for outra coisa.

### 10. Drip via `eta` em Redis é frágil pra D+21

Brief V1: "Celery tasks: 4 tasks (welcome + 3 drip) com schedule via eta". Implementação direta: `send_drip_d7.apply_async(args=[lead_id], eta=now + 7d)`.

**Risco:** Celery armazena tasks programadas no broker (Redis). Redis padrão em prod é configurado como **broker** sem persistência forte (`appendonly no` em muitos setups). Se Redis reiniciar entre D+0 e D+21, **todas as tasks programadas se perdem**. Padrão production-grade é:

- **Opção A (brief literal):** `eta` em Redis. Funciona se Redis persiste (`appendonly yes`, RDB snapshot). Frágil sem isso.
- **Opção B (recomendada):** Celery beat scan periódico de tabela `pre_cadastros`. A cada 5min/15min, busca leads com `D+N` vencendo e dispara. Recuperável após reboot; idempotência via `drip_step_sent_at` na tabela.
- **Opção C:** Worker de drip dedicado lendo do DB direto, sem Celery. Overkill.

Recomendo **B** com tabela auxiliar `pre_cadastros_drip_log(lead_id, step, sent_at, status)` pra idempotência. Brief diz `eta` — vou assumir **A** com config Redis persistente, mas **flag escalado pro `risco 7`**.

### 11. `Idempotência por email` — silent 200 vs explícito 409

Brief F3: "Retorna 201 com id ou 409 se já cadastrado". Mas waitlist landing pages **best-practice** retornam silent 200 ("Você está na lista!") mesmo se já existir, pra evitar **enumeração de emails** (atacante consegue saber quem está cadastrado). Brief implicitamente pede a opção menos segura.

Trade-off:
- **(a) 409 explícito** — UX mais honesta ("você já está cadastrado"); abre enumeração.
- **(b) 200 idempotente** — UX uniforme; protege contra enumeração. Padrão de waitlists modernas (Linear, Notion).

Recomendo **(b)** com nota no doc da API: "POST /waitlist é idempotente por email, sempre retorna 200/201; cliente não consegue distinguir signup novo de existente."

### 12. Resend Audience custom properties — capacidade não verificada

Brief F3: "Cria/atualiza contato no Resend Audience (custom properties)". Resend Audience API (v1, 2026) suporta:
- Campos padrão: `email`, `first_name`, `last_name`, `unsubscribed`
- **Custom properties** sim, via campo `data` (JSONB). Verificado en `https://resend.com/docs/api-reference/contacts/create-contact`.

Não é divergência real, só uma verificação. Sigo com Audience + `data: {nome, telefone, perfil_profissional, ...}`.

### 13. F4 CORS: precisa de TODAS as origens da landing + dev

Brief F4: "CORS configurado pra `regenteambiental.com.br` e `www.regenteambiental.com.br`". Config atual em [config.py:92](app/core/config.py#L92): `BACKEND_CORS_ORIGINS` comma-separated. Atualmente: `http://localhost:3000,http://127.0.0.1:3000,http://172.31.32.1:3000` (portal interno dev).

**Origens a adicionar:**
- `https://regenteambiental.com.br`
- `https://www.regenteambiental.com.br`
- `https://regente-tecnico.netlify.app` (ou nome final do site Netlify, **enquanto domínio próprio não está propagado**)
- `http://localhost:5500` (dev local da landing)

Mudança é só na env var `BACKEND_CORS_ORIGINS` em produção. Zero código. Mas: `allow_credentials=True` no main.py exige origens explícitas (não pode usar `*`). Já está consistente.

### 14. F4 + V4: snippet JS para landing — landing não tem `<form>` hoje

Brief V4: "Snippet JS standalone (15-30 linhas) pra substituir o action do form na landing". Mas a landing atual **não tem `<form>` element** — os 5 CTAs ("Lista de espera", "Entrar como consultor fundador", "Acesso antecipado", etc.) são `<a href="https://docs.google.com/forms/...">` apontando direto pro Google Forms.

**Implicação:** V4 não é só "trocar action"; é **construir o formulário** com os campos do F1 (nome, email, telefone, perfil, estado, tipo de licenciamento, volume mensal, ferramenta atual, Van Westendorp 4 perguntas, expectativa, deal_breaker, interesse_grupo).

Isso é 80+ linhas de HTML/CSS + 30 de JS — não cabe na "15-30 linhas". Caminhos:

- **(a) Modal in-page** — clique no CTA abre modal com form completo. Mais código, mais design (estilo dark do Modelo 3).
- **(b) Página dedicada `lista-de-espera.html`** — CTAs viram `<a href="/lista-de-espera">`, página separada com form. Mais simples; quebra single-page.
- **(c) Form embutido na seção 09 (lista de espera)** — substitui os dois botões "Quero entrar como consultor fundador / acesso antecipado" pelo form expandido. Mais natural; CTAs do topo continuam abrindo Google Form como fallback (ou rolam pra seção 09).

Recomendo **(c)** — força a maior parte do tráfego pro form completo enquanto preserva os CTAs do topo como atalho. Mas isso é decisão de produto/design — flag pra você.

### 15. Resend não bloqueia request — async via Celery

Brief F3 lista 4 ações no endpoint:
1. Validação Pydantic + email
2. Rate limit (IP)
3. Idempotência por email
4. Persistência Postgres
5. **Cria/atualiza contato no Resend Audience**
6. **Dispara Celery task de welcome email**
7. Retorna 201

Brief explicitamente diz que (6) é async ("não bloqueia response"). Mas **não diz se (5) é inline ou async**. Inline = lead criado no DB depende de Resend respondendo (latência +200–500ms; bloqueia response). Async = lead criado, sync com Resend é uma task à parte.

Recomendo **async para (5)** também: `sync_resend_audience.delay(lead_id)`. Mesmo padrão da task de welcome. Lead em estado `resend_contact_id IS NULL` até a task rodar. Trade-off: se Resend falha, lead fica eternamente sem contact_id; precisa de retry policy + DLQ.

### 16. Tests pattern — Testcontainers PostgreSQL+PostGIS

Conftest do projeto (do report A1: [tests/conftest.py:25](tests/conftest.py#L25)) usa **Testcontainers PG+PostGIS 15-3.3**, function-scoped, transação rollback, `Base.metadata.create_all` direto (não Alembic). O endpoint `/waitlist`:

- **Não precisa de PostGIS** — `pre_cadastros` não tem coluna geográfica
- **Não precisa de fixture de tenant/user** — é público
- **Precisa de mock do Resend** — `httpx_mock` (já temos httpx; precisa adicionar pytest-httpx em requirements? não vi)
- **Precisa de mock do Celery** — padrão é `celery_app.conf.update(task_always_eager=True)` em conftest, ou `pytest-celery`. **Não vi se já tem configurado.** Verificar antes da implementação.

### 17. LGPD: PII pré-consentimento

Brief mencona LGPD só em "Critérios de aceite" (purge) e "Riscos" (LGPD do pre-cadastro). Mas o form coleta nome+email+telefone — **PII de pessoa identificada** — antes de qualquer relação contratual. Pra LGPD compliance:

- **Base legal:** consentimento (art. 7º I) ou legítimo interesse (art. 7º IX). Recomendo **consentimento** explícito (checkbox "Aceito receber comunicações do Regente sobre o lançamento") — fica como `consentimento_dado_em: timestamp` na tabela.
- **Direito de exclusão (art. 18 VI):** brief pede "campo soft-delete". Recomendo:
  - `deleted_at: timestamp nullable` — soft-delete
  - `purge_after: timestamp nullable` — hard-delete agendado para X dias após `deleted_at`
  - Task Celery `purge_pre_cadastros_deleted` rodando diário
- **Política de privacidade:** link obrigatório no form. Brief silencioso — flagar.
- **Endpoint de unsubscribe:** todo email do drip precisa de link "cancelar inscrição" (também exigência do Resend pra entrega). Brief silencioso — adicionar `POST /waitlist/{token}/unsubscribe` ou usar o link nativo do Resend.

### 18. Domínio remetente e DNS — Zoho recebe, Resend envia

Decisão do usuário (2026-05-13): **Zoho Mail recepção + Resend envio** no mesmo domínio `regenteambiental.com.br`.

Configuração DNS (vai pra V3 / README_DNS.md):

```
# MX — Zoho Mail recebe
MX 10 mx.zoho.com.
MX 20 mx2.zoho.com.
MX 50 mx3.zoho.com.

# SPF — combinado: Zoho recebe + Resend envia (via AWS SES por baixo)
TXT @ "v=spf1 include:zoho.com include:amazonses.com -all"

# DKIM — seletores diferentes, não conflitam
TXT zmail._domainkey "v=DKIM1; k=rsa; p=<chave-do-zoho>"
TXT resend._domainkey "v=DKIM1; k=rsa; p=<chave-do-resend>"

# DMARC — começar permissivo, subir depois de 2 semanas
TXT _dmarc "v=DMARC1; p=none; rua=mailto:dmarc-reports@regenteambiental.com.br; ruf=mailto:dmarc-reports@regenteambiental.com.br; pct=100"

# CNAME — subdomínio da API
CNAME api <host-do-backend>
```

**Atenção:** Zoho usa `include:zoho.com` no SPF (não `_spf.google.com`). Resend internamente usa AWS SES (`include:amazonses.com`). Ambos somam ≤10 lookups DNS (limite SPF). OK.

**Atenção 2:** Resend pode pedir **domínio dedicado** ou **subdomínio dedicado** (`send.regenteambiental.com.br`). Se subdomínio dedicado, SPF muda. Confirmar no console da Resend após criar o domain.

---

## (b) Confirmação / correção de suposições (A-E + decisões técnicas)

| Assumption do brief | Validação |
|---|---|
| **A.** Subdomínio dedicado `api.regenteambiental.com.br` | ✅ Confirmado. CNAME no DNS aponta pro host do backend. Mesma binário FastAPI; sem vhosts necessários (a menos que decisão #4 sobre Regente vs Amigão mude). |
| **B.** Tabela nova `pre_cadastros` (não misturar com `usuarios`) | ✅ Confirmado. Sem `tenant_id`. FK opcional `converted_user_id → users.id` (nullable) para link pós-conversão. |
| **C.** Resend send-only por enquanto (inbound depois) | ✅ Confirmado. Zoho Mail cobre recepção (decisão 2026-05-13). |
| **D.** Drip D+0 / D+7 / D+14 / D+21 | ⚠️ Confirmado conceitualmente. Implementação `eta` vs beat-scan: ver divergência #10. **Default vou com `eta` + Redis persistente; flag pra você se quiser beat-scan**. |
| **E.** Remetente `contato@regenteambiental.com.br` | ⚠️ Conflita com `EMAILS_FROM_EMAIL = "noreply@amigao.com"` atual. Ver divergência #3. |
| **Decisão extra 1.** Stack: Resend (envio) + Zoho Mail (recepção) | ✅ Confirmado 2026-05-13. |
| **Decisão extra 2.** Migração total do EmailService SMTP → Resend | ✅ Confirmado 2026-05-13. Expande escopo: refactor de `app/services/email.py` + atualização dos 3+ callers existentes. |

### Stack runtime (confirmado)

| Item | Estado real |
|---|---|
| Python | 3.11 (`requires-python = ">=3.11"`) |
| FastAPI | 0.136.1 — `app/main.py` usa `lifespan` async + middlewares Security/Context/CORS |
| Pydantic | v2.12.5 — `model_config = ConfigDict()`, `EmailStr`, `model_validator` |
| SQLAlchemy | 2.0.49 — `declarative_base` em `app/models/base.py` (verificar) |
| Alembic | 1.18.4 — versões em `alembic/versions/`; convenção `<8-hex>_sprint_<X>_<descricao>.py` |
| Celery | broker Redis `REDIS_URL`; autodiscover `app.workers`; signals injetam trace_id |
| slowapi | já instalado; limiter em `app.core.rate_limit.limiter` (key=remote_address) |
| httpx | já instalado — uso natural pro cliente Resend |
| email-validator | já instalado |
| pytest-httpx | **NÃO está em requirements** — adicionar pra mockar Resend nos tests |
| pytest-celery | **NÃO confirmado em requirements** — verificar antes da implementação |

### Padrões do projeto (confirmados via leitura)

- **Imports:** absolute, `from app.x import Y`; lazy imports com `noqa: PLC0415` aceitáveis
- **Lint:** Ruff line-length 120, ignores específicos por arquivo em [pyproject.toml:31](pyproject.toml#L31)
- **Logs:** `from app.core.logging import setup_logging` (JSON em prod)
- **Métricas:** `from app.core.metrics import record_email_delivery`, etc.; endpoint `/metrics` Prometheus
- **Settings:** `from app.core.config import settings`; **NÃO** reimportar `Settings()` direto
- **Validator de settings:** `validate_security` em [config.py:217](app/core/config.py#L217) — adicionar regra `RESEND_API_KEY required em prod`
- **Mensagens de erro:** Portuguese ("E-mail enviado com sucesso", "Falha ao enviar..."), Logger em inglês ok
- **Celery tasks:** `@celery_app.task` com `max_retries=3, retry_backoff=True` (CLAUDE.md regra)
- **Alertas operacionais:** `emit_operational_alert(category, severity, message, metadata)` em falhas críticas

---

## (c) Riscos arquiteturais não cobertos pelo prompt

### R1. CORS misconfig em produção → form silenciosamente quebra

`BACKEND_CORS_ORIGINS` default é localhost-only. Se deploy em produção esquecer de setar a env var, preflight `OPTIONS /api/v1/waitlist` retorna 400 e o `fetch` da landing falha **silenciosamente** (browser bloqueia, mas mostra erro só no DevTools — UX-side parece "carregando pra sempre"). Mitigação: adicionar smoke-test CI que verifica `OPTIONS` em prod, ou logar warning ao subir em prod com CORS lista vazia.

### R2. Rate limit 3/min/IP gera false-positives em NAT corporativo

3 requests/min por IP é agressivo. ISPs CGNAT (Vivo Fibra, Claro Net) compartilham IP entre milhares de usuários — 3 leads consecutivos do mesmo ISP em 1 minuto e o 4º cai. Empresa de consultoria com 10 funcionários no mesmo proxy também. Mitigação: aumentar pra **10/min/IP** + **30/dia/IP** (limite duplo). Considerar Captcha leve (hCaptcha invisible) se vier abuse real — fora de escopo agora.

### R3. Anti-enumeração: brief pede 409 explícito (vaza estado)

Já tratado em divergência #11. Risco: atacante pode descobrir se email X está cadastrado consultando o endpoint. Para waitlist, baixo impacto. Para form com pré-validação de "já é cliente", alto impacto. Recomendo 200 idempotente.

### R4. LGPD: PII coletada sem checkbox de consentimento + sem política de privacidade publicada

Ver divergência #17. **Bloqueante pra compliance** caso ANPD audite. Mitigação:
- Checkbox "Aceito a política de privacidade" obrigatório no form
- Link pra `https://regenteambiental.com.br/privacidade` (página a criar)
- Campo `consentimento_dado_em` na tabela
- Endpoint `/waitlist/exclusao` (público, recebe email + token de confirmação) para Art. 18

### R5. Rotação da Resend API key

Brief lista como risco. Mitigação:
- `RESEND_API_KEY` em env var, nunca em código. `.env.example` documenta.
- Validator `validate_security` em [config.py:217](app/core/config.py#L217) ensure em prod: `RESEND_API_KEY` presente e ≥10 chars.
- Em incidente: girar key no console Resend, redeploy backend com novo .env. Down time ~30s.
- Não há rotação automática (Resend não oferece). Documentar runbook em `docs/RunbookOperacional.md`.

### R6. Email deliverability — domínio novo "warming"

Domínio `regenteambiental.com.br` é novo do ponto de vista do ecossistema email (sem histórico de envio). Mesmo com SPF/DKIM/DMARC válidos, inbox providers (Gmail/Outlook) podem mandar pro spam nas primeiras semanas. Mitigação:
- Começar com volume baixo (50 leads/dia primeiros 14 dias)
- Welcome email tem que ser **bom** (texto plain + HTML; alta razão texto/imagem; sem links suspeitos)
- DMARC `p=none` por 2 semanas, depois `p=quarantine`, depois `p=reject`
- Monitorar bounce rate (Resend dashboard); pausar drip se >5% bounces

### R7. Drip `eta` longo (D+21) vs persistência do Redis broker

Ver divergência #10. Se Redis broker reinicia entre signup e D+21, task se perde silenciosamente. Mitigação curta (se ficarmos com `eta`): configurar Redis com `appendonly yes` + RDB snapshot a cada 1min. Mitigação real: migrar pra beat-scan da tabela (#10 opção B). **Decisão sua antes de implementar V1**.

### R8. Idempotência das drip tasks em retry

Se uma drip task falha (Resend timeout) e Celery faz retry com `retry_backoff=True`, o lead pode receber o email **duplicado** se o retry rodar APÓS o primeiro envio ter passado. Mitigação:
- Tabela auxiliar `pre_cadastros_drip_log(lead_id, step, status, sent_at, resend_message_id)` UNIQUE em (lead_id, step)
- Task chama `INSERT ... ON CONFLICT DO NOTHING` antes de chamar Resend. Se conflito, skip.
- Garantia: at-most-once envio por (lead, step), mesmo com retry.

### R9. AuditLog requer tenant_id; lead anônimo não pode auditar lá

Ver divergência #5. Mitigação: tabela `pre_cadastros` JÁ tem `created_at`, `deleted_at`, `consentimento_dado_em` — suficiente pra trilha LGPD. Drip log (R8) cobre eventos pós-signup. AuditLog fica fora.

### R10. Resend Audience custom properties → schema drift

Custom properties no `data` JSONB do Resend Audience são strings/numbers/booleans simples. Se schema do form mudar (campo novo, ex: `cargo_atual`), precisa **(a)** adicionar coluna em `pre_cadastros` E **(b)** atualizar `sync_resend_audience` pra incluir o campo novo. Esquecer de (b) faz divergência DB ↔ Resend silenciosa. Mitigação:
- Função única `lead_to_resend_data(lead: PreCadastro) -> dict` que reflete TODOS os campos relevantes
- Teste que verifica que cada novo campo aparece nessa função

### R11. Falha do snippet JS em browsers antigos

`fetch` é universal hoje, mas tratamento de erro (offline, CORS, 500) varia. Mitigação:
- States UI: idle / loading / success / error (com mensagem clara)
- Timeout cliente (`AbortController` 10s)
- Fallback: se fetch falhar, abrir Google Form em nova aba (preserva o que já temos)

### R12. Subdomain api.regenteambiental.com.br precisa TLS

Netlify gerencia TLS no domínio raiz. O subdomínio `api.` aponta CNAME pro backend — TLS é responsabilidade do **backend host**. Se backend é Fly.io / Render / Railway, eles auto-provisionam Let's Encrypt. Se é VPS bare com nginx, preciso de cert manager. **Não sei onde o backend roda em prod** — flag.

---

## (d) Proposta de execução

### Ordem recomendada e justificativa

**Fase 0** (este documento) → **Foundation F1-F5** → **Pause manual** → **Value V1-V4** → **Critérios de aceite + deploy**

Brief sugere V1-V4 em paralelo ao Foundation. Discordo parcialmente: V2 (templates) e V3 (DNS doc) podem rodar em paralelo, mas **V1 (Celery tasks) depende fortemente de F1 (modelo) e F5 (resend client)** — não compensa o paralelismo. Proposta refinada:

```
F1 (migration)
  → F2 (schemas Pydantic)
    → F5 (resend client) ──────────── V2 (templates) [paralelo]
      → F3 (endpoint POST /waitlist)  V3 (README_DNS) [paralelo]
        → [PAUSE manual: validar endpoint com curl]
          → V1 (Celery drip tasks)
            → F4 (CORS update — só env var) [paralelo]
              → V4 (snippet JS landing)
                → [PAUSE: DNS por sua conta]
                  → Smoke tests fim-a-fim
```

### Tabela de tarefas (estimativa em "T-shirt sizes")

| Tarefa | Esforço | Bloqueia | Notas |
|---|---|---|---|
| **F1** Alembic migration `pre_cadastros` + indexes | S | F2, F3 | ~25 colunas; 2 indexes (email UNIQUE, utm composto) |
| **F2** Schemas Pydantic `PreCadastroIn/Out` + nested `PrecoVanWestendorp` | S | F3 | Inclui regex telefone BR, EmailStr, length limits |
| **F5** `app/services/resend_client.py` + **refactor de email.py** | **M/L** | F3, V1, V2 | **Escopo expandido pela decisão de migração total**. Inclui driver Resend, fallback graceful, métricas, retry, atualização dos 4+ callers de EmailService |
| **F3** Router `app/api/v1/waitlist.py` + `POST /api/v1/waitlist` | M | V1, V4 | Pydantic + rate_limit + idempotência + persist + enqueue tasks |
| **F4** CORS update — env var `BACKEND_CORS_ORIGINS` | XS | nada | Zero código; só doc + .env.example |
| **V1** 4 Celery tasks (welcome, drip D+7, D+14, D+21) + drip_log table | M | smoke tests | Inclui idempotência (R8) e retry policy |
| **V2** 4 templates Jinja (welcome + 3 drip) em `app/templates/emails/` | M | V1 | HTML responsivo, plain-text alternativo, unsubscribe link |
| **V3** `README_DNS.md` com SPF/DKIM/DMARC/MX/CNAME | S | DNS manual | Inclui screenshots do console Resend + Zoho |
| **V4** Snippet JS + form HTML completo na seção 09 da landing | M | nada | Cresceu pra além de "15-30 linhas"; ver divergência #14 |

**Total estimado:** ~10-14h focadas, podendo ser dividido em PRs pequenas.

### Sequenciamento prático sugerido

**PR 1 — Foundation read-only** (F1+F2): só estruturas, sem endpoint. Mergeia rápido, baixo risco.
**PR 2 — Resend client + refactor email** (F5): inclui testes dos callers existentes pra garantir zero regressão no portal interno.
**PR 3 — Endpoint público** (F3+F4): com testes de rate-limit, idempotência, CORS preflight. **Aqui você valida com curl antes de ir pro V1.**
**PR 4 — Drip system** (V1+V2): tasks + templates + drip_log. Testar com `countdown=10s` em dev.
**PR 5 — DNS + Landing wire** (V3+V4): doc + form na landing. **Você faz o DNS manualmente entre V3 e o smoke test final.**

---

## Step 3 — Perguntas em aberto (impacto explícito)

Em ordem decrescente de urgência:

1. **Regente vs Amigão (divergência #4):** É submarca? Produto separado? Mesma app, ou backend dedicado? Resposta muda o `PROJECT_NAME` na config, o `EMAILS_FROM_NAME`, e se `pre_cadastros` tem `tenant_id` (caso Regente seja "tenant fixo"). **Impacto: alto.**

2. **Path do endpoint (divergência #1):** `/api/v1/waitlist` (recomendado, segue convenção) ou `/waitlist` (root, casa com brief literal)? **Impacto: médio — só URL final, sem reescrita posterior.**

3. **Idempotência: 200 silencioso ou 409 explícito (divergência #11 + R3)?** Recomendo 200; brief pede 409. Confirma. **Impacto: pequeno — 5 linhas.**

4. **Drip: `eta` em Redis ou beat-scan na tabela (divergência #10 + R7)?** Brief diz `eta`; recomendo beat-scan. Trade-off documentado. **Impacto: alto — beat-scan exige tabela `drip_log` + task agendada, eta é mais direto.**

5. **Remetente: trocar `EMAILS_FROM_EMAIL = noreply@amigao.com` por `contato@regenteambiental.com.br` global, ou separar por contexto (divergência #3)?** Resposta depende de #1. Recomendo separar via `EMAILS_FROM_WAITLIST` env var dedicada. **Impacto: pequeno — 1 setting.**

6. **Form: modal, página dedicada, ou expand seção 09 da landing (divergência #14)?** Recomendo expand seção 09. **Impacto: alto pro escopo de V4 (HTML+CSS+JS de form completo, não 15 linhas).**

7. **LGPD: política de privacidade publicada? (R4)** Recomendo bloqueante. Posso esqueletar `/privacidade.html` na landing como entregável extra, ou você já tem? **Impacto: regulatório.**

8. **Onde o backend roda em prod (R12)?** Precisa pra orientar TLS do subdomínio api.. Fly.io / Render / Railway / VPS? Brief silencia.

9. **`pytest-httpx` e `pytest-celery` em requirements?** Posso adicionar; só verificar se você já tem versão pinada em outro lugar.

10. **`interesse_grupo` é boolean ou outro tipo (divergência #9)?**

---

## Step 4 — PARO aqui

Não vou tocar em código de produção até receber sinal verde explícito.

**Mínimo que preciso pra começar:** respostas para perguntas **1, 2, 4, 6** (alto impacto).

**Defaults razoáveis** que vou assumir se não houver correção em **3, 5, 7-10:**
- Idempotência → 200 silencioso (resposta uniforme)
- Remetente → setting separado `EMAILS_FROM_WAITLIST = "contato@regenteambiental.com.br"`
- LGPD → tabela com `consentimento_dado_em` + `deleted_at`; form com checkbox + link placeholder pra `/privacidade.html`
- Backend prod → assumo Fly.io ou similar (Let's Encrypt auto) até você confirmar
- Tests → adiciono `pytest-httpx>=0.30` em requirements; assumo `task_always_eager=True` em conftest (vou verificar antes)
- `interesse_grupo` → boolean
