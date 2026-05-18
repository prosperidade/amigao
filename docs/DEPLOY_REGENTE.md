# Deploy Regente Ambiental — Runbook

> Status: piloto SEMAD (maio/2026). Stack final aprovada por revisão Opus.
> Para o porquê das escolhas de stack, ver [VALIDACAO_DEPLOY.md](../VALIDACAO_DEPLOY.md).

---

## Stack alvo

| Camada | Provider | Plano | Custo/mês | Observação |
|---|---|---|---|---|
| Compute API | Render Web Service (Virginia) | Starter | $7 | 512 MB, always-on, $PORT |
| Compute Worker | Render Background Worker (Virginia) | Standard | $25 | 2 GB, `-B` beat embarcado |
| Banco | Supabase (us-east-1 Virginia) | Pro | $25 | Postgres 15 + pgvector + PostGIS |
| Redis | Upstash (us-east-1) | Free | $0 | TLS (`rediss://`), 10k cmds/dia |
| Storage | Cloudflare R2 | Pay-as-you-go | ~$0-2 | S3-compat, zero egress |
| Email | Resend | já contratado | — | SPF/DKIM no domínio |
| **Total** | | | **~$57-60** | |

---

## Passo 0 — Gitleaks (BLOQUEANTE)

Antes de qualquer provisionamento, verificar que não há credenciais vazadas no histórico:

```bash
# Instale: https://github.com/gitleaks/gitleaks
gitleaks detect --source . --no-banner --verbose
```

**Se houver match: ABORTAR o deploy** e investigar antes de prosseguir.
Lembre que vazamento de chave OpenAI/Gemini/Anthropic vira fatura inflada em horas,
não dias. Rotacione a chave comprometida ANTES de qualquer outra ação.

---

## Passo (a) — Supabase: criar projeto

1. Acesse https://supabase.com e crie novo projeto.
   - **Nome:** `regente-ambiental-prod`
   - **Organização:** sua org pessoal (ou criar uma nova "Regente")
   - **Senha do banco:** gerar 32 chars random e guardar no password manager
   - **Região:** **`East US (North Virginia) — us-east-1`** (alinhada com Render Virginia, mesma AZ AWS → latência API↔DB <5ms vs. ~180ms transcontinental se fôssemos pra `sa-east-1`).
   - **Justificativa LGPD:** o piloto é B2B com consultor ambiental, sem exigência contratual escrita de residência de dados no Brasil. Transferência internacional coberta por DPA + **Cláusulas-Padrão Contratuais ANPD (Resolução CD/ANPD nº 19/2024)**. Migração futura para `sa-east-1` São Paulo fica como item de revisão quando aparecer cliente govtech com exigência contratual de soberania de dados. Checklist completo na seção "Compliance LGPD — pré-primeiro cliente real" no final deste documento.
   - **Plan:** Pro ($25/mês).

2. Aguarde provisionamento (~2-3 min).

3. Copie 2 connection strings do dashboard (`Project Settings → Database → Connection string`):
   - **Transaction pooler** (porta 6543) → será `DATABASE_URL` do app
   - **Direct connection** (porta 5432) → será `MIGRATE_DATABASE_URL` do alembic

   Formato:
   ```
   DATABASE_URL = postgresql://postgres.<projref>:<senha>@<region>.pooler.supabase.com:6543/postgres
   MIGRATE_DATABASE_URL = postgresql://postgres:<senha>@db.<projref>.supabase.co:5432/postgres
   ```

---

## Passo (b) — Supabase: habilitar extensions

No dashboard `Database → Extensions`:

1. Buscar `vector` → **Enable** (Sprint U / pgvector @ 768d).
2. Buscar `postgis` → confirmar que está habilitada (vem por padrão no Supabase, mas validar).

Confirmação via SQL Editor:
```sql
SELECT extname, extversion FROM pg_extension
WHERE extname IN ('vector', 'postgis');
```

Deve retornar 2 linhas. Se `vector` faltar, o alembic vai falhar na migration `f9d2e8c1a4b3_sprint_u_knowledge_catalog`.

---

## Passo (c) — Cloudflare R2: bucket + IAM

1. Acesse https://dash.cloudflare.com → R2 (sidebar esquerda).
2. **Create bucket:**
   - Nome: `regente-docs` (alinhado com `BUCKET_NAME` em [app/services/storage.py:15](../app/services/storage.py#L15) — consistência com a renomeação Amigão→Regente).
   - Localização: `Automatic` (R2 é multi-região por padrão, sem cost penalty).

3. **Manage R2 API Tokens → Create API Token:**
   - Nome: `regente-prod-rw`
   - Permissões: `Object Read & Write` (NÃO dar `Admin`)
   - Specify bucket: `regente-docs` (ou o nome que escolheu)
   - TTL: `Forever` (ou rotacionar a cada 90 dias se preferir)

4. Anote 3 valores:
   - **Access Key ID** → `MINIO_ACCESS_KEY`
   - **Secret Access Key** → `MINIO_SECRET_KEY`
   - **Endpoint (jurisdiction-specific)** → `MINIO_SERVER` e `MINIO_PUBLIC_URL`
     - Formato: `https://<account_id>.r2.cloudflarestorage.com`

5. **NÃO** dar permissão `s3:CreateBucket` — o [`StorageService._ensure_bucket_exists`](../app/services/storage.py#L48) faz `head_bucket` primeiro e cacheia. Como o bucket já existe, never tenta criar.

---

## Passo (d) — Upstash Redis

1. Acesse https://console.upstash.com → Create Database.
   - Nome: `regente-prod`
   - Type: `Regional` (não Global — não precisamos do extra cost).
   - Region: `us-east-1` (alinhar com Render Virginia + Supabase us-east-1 — mesma AZ AWS, latência <2ms).
   - **TLS: enabled** (obrigatório — Celery vai usar `rediss://`).

2. Copie a **TLS connection string** (não a non-TLS):
   ```
   rediss://default:<password>@<region>.upstash.io:6379
   ```

   Esse é o `REDIS_URL` do app.

3. **Atenção sobre quotas Upstash Free:**
   - 10.000 comandos/dia
   - Auditoria do piloto SEMAD estimou ~800 comandos/dia ([VALIDACAO_DEPLOY.md item 3](../VALIDACAO_DEPLOY.md)). Folga ~12x. Se passar 5.000/dia, migrar para Upstash Pay-as-you-go ($0.2 por 100k cmds).

---

## Passo (e) — Commit render.yaml + push main

```bash
# Verificar diff
git status
git diff render.yaml .env.example app/core/config.py alembic/env.py \
        app/core/celery_app.py app/db/session.py requirements.txt \
        docs/DEPLOY_REGENTE.md

# Commit
git add render.yaml .env.example app/core/config.py alembic/env.py \
        app/core/celery_app.py app/db/session.py requirements.txt \
        docs/DEPLOY_REGENTE.md
git commit -m "feat(deploy): render.yaml + refactor DATABASE_URL/MIGRATE_DATABASE_URL"
git push origin main
```

No Render Dashboard:

1. **New → Blueprint**
2. Conectar repositório `prosperidade/amigao`
3. Branch `main`
4. Render detecta `render.yaml` e mostra preview dos serviços.
5. **NÃO clique "Apply" ainda** — antes precisa preencher os `sync: false` no envVarGroup `regente-shared`:

| Variável | Valor | Origem |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres.<ref>:<sen>@...pooler.supabase.com:6543/postgres` | Passo (a) |
| `MIGRATE_DATABASE_URL` | `postgresql://postgres:<sen>@db.<ref>.supabase.co:5432/postgres` | Passo (a) |
| `REDIS_URL` | `rediss://default:<pwd>@...upstash.io:6379` | Passo (d) |
| `MINIO_SERVER` | `<account_id>.r2.cloudflarestorage.com` | Passo (c) |
| `MINIO_PUBLIC_URL` | `https://<account_id>.r2.cloudflarestorage.com` | Passo (c) |
| `MINIO_ACCESS_KEY` | (R2 access key) | Passo (c) |
| `MINIO_SECRET_KEY` | (R2 secret key) | Passo (c) |
| `OPENAI_API_KEY` | `sk-proj-...` | sua conta |
| `GEMINI_API_KEY` | `AIza...` | sua conta |
| `ANTHROPIC_API_KEY` | `sk-ant-api03-...` | sua conta |
| `RESEND_API_KEY` | `re_...` | sua conta |
| `RESEND_AUDIENCE_ID` | `<uuid>` | Resend dashboard |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` | Resend SMTP ou outro provider | sua conta |
| `ALERT_WEBHOOK_URL` | (vazio até integrar Slack/PagerDuty) | — |

`SECRET_KEY` é auto-gerada (`generateValue: true`).

6. Agora **Apply**. Render começa o build dos 2 serviços simultaneamente. Vai falhar no primeiro start porque o banco está vazio. Esperado.

---

## Passo (f) — Migrations via Render Shell

**OBRIGATÓRIO: rodar via Render Shell, não local.** Motivos:

1. Env vars já estão injetadas no container → zero risco de digitar senha errada
2. Senha do banco NÃO aparece no shell history da sua máquina
3. Versão do Python e do alembic batem com o que vai rodar em prod

**Procedimento:**

1. No Render Dashboard → serviço `regente-api` → aba **Shell** (botão no topo direito).
2. Aguardar o shell conectar (~5s).
3. Rodar:
   ```bash
   alembic upgrade head
   ```
4. Saída esperada (40 migrations em sequência, ~30-60s):
   ```
   INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
   INFO  [alembic.runtime.migration] Will assume transactional DDL.
   INFO  [alembic.runtime.migration] Running upgrade  -> a8905cb51eb1, initial schema
   ...
   INFO  [alembic.runtime.migration] Running upgrade <prev> -> b1a2c3d4e5f6, sprint1 intake
   ```
5. Confirmar com:
   ```bash
   alembic current
   # Esperado: b1a2c3d4e5f6 (head)
   ```

> **Nota técnica:** o `alembic/env.py` foi refatorado para ler `MIGRATE_DATABASE_URL` (Supabase direct 5432) com fallback para `DATABASE_URL` (pooler 6543). Migrations exigem sessão estável — pooler em transaction mode quebra DDL.

---

## Passo (g) — Deploy api + worker

Após migrations rodadas, fazer **Manual Deploy** dos dois serviços:

1. `regente-api` → **Manual Deploy → Deploy latest commit**
2. `regente-worker` → **Manual Deploy → Deploy latest commit**

Aguardar ambos chegarem em status **Live** (~3-5 min).

**Esperado nos logs do api:**
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:10000 (Press CTRL+C to quit)
```

**Esperado nos logs do worker:**
```
[INFO/MainProcess] celery@... ready.
[INFO/MainProcess] beat: Starting...
[INFO/Beat] beat: Starting...
```

> A linha "beat: Starting" confirma que o `-B` está ativo e o scheduler vai
> disparar as 6 tasks cron (DOU 06h, DOE 06h30, agencies seg 03h, vigia */6h,
> acompanhamento */30min, cleanup 02h30).

---

## Passo (h) — Smoke test em URL temporária

Antes de apontar DNS, validar pelo URL gerado pelo Render (`https://regente-api.onrender.com` ou similar).

**Checklist mínimo:**

```bash
# 1. Health endpoint
curl https://regente-api.onrender.com/health
# Esperado: {"status":"ok","version":"0.1.0","service":"api"}

# 2. OpenAPI carrega (só se ENVIRONMENT ≠ production)
# Em prod, /docs DEVE retornar 404 — security feature, não bug.
curl -I https://regente-api.onrender.com/docs

# 3. Login da seed (NÃO criada automaticamente em prod — seed.py não roda)
# Pular este teste OU criar usuário admin manualmente via Render Shell:
#   python -c "from app.db.session import SessionLocal; ..."
# OU rodar seed.py manualmente:
#   python seed.py
# Em produção, recomendo criar APENAS o superuser e deixar a criação dos
# demais users para o fluxo normal de signup.

# 4. Métricas Prometheus
curl https://regente-api.onrender.com/metrics | grep -E "^http_requests|^celery"

# 5. WebSocket realtime (se tiver wscat instalado)
# wscat -c wss://regente-api.onrender.com/api/v1/ws/realtime?token=<JWT>
```

**Logs do worker (Render Dashboard → Logs):**
- Confirmar que `cleanup-expired-intake-drafts` aparece quando passar das 02h30 BRT
- Ou disparar manualmente via Render Shell:
  ```bash
  celery -A app.core.celery_app call workers.cleanup_expired_intake_drafts
  ```

---

## Passo (i) — Apontar DNS

Apenas depois que (h) passar 100%:

1. **Cloudflare DNS** (assumindo domínio gerenciado lá):
   - Criar CNAME `app.regenteambiental.com.br` → `regente-api.onrender.com`
   - Proxy status: **DNS only** (cinza) por enquanto. Ativar proxy laranja depois que SSL do Render estiver estável (1-2h após o CNAME).

2. **Render Dashboard** → `regente-api` → **Settings → Custom Domain**:
   - Adicionar `app.regenteambiental.com.br`
   - Render emite certificado Let's Encrypt automaticamente (5-15 min após DNS propagar).

3. **CORS já liberado** no `render.yaml`:
   - `https://app.regenteambiental.com.br`
   - `https://regenteambiental.com.br`
   - `https://www.regenteambiental.com.br`

4. **Validar:**
   ```bash
   curl -I https://app.regenteambiental.com.br/health
   # HTTP/2 200 + cabeçalhos Render
   ```

---

## Compliance LGPD — pré-primeiro cliente real

> **Bloqueio:** os 9 itens abaixo são **BLOQUEANTES antes de processar o primeiro
> documento real de cliente** (ofício SEMAD do parceiro, dossiê de propriedade,
> qualquer PDF com dado pessoal/sensível). **NÃO são bloqueantes para subir a
> infraestrutura** — o pipeline pode estar de pé pra testes internos antes desse
> checklist fechar.
>
> Decisão de arquitetura: dados ficam em US (Supabase Virginia, Render Ohio,
> Cloudflare global, OpenAI/Anthropic/Google). Transferência internacional
> coberta por DPA + Cláusulas-Padrão Contratuais (Resolução CD/ANPD 19/2024).

| # | Item | Responsável | Estado |
|---|---|---|---|
| 1 | **Assinar DPA Supabase** (Data Processing Addendum em `supabase.com/legal/dpa`) | sócio | ⬜ |
| 2 | **Assinar DPA Render** (`render.com/security` ou via support) | sócio | ⬜ |
| 3 | **Assinar DPA Cloudflare** (R2 + DNS — `cloudflare.com/cloudflare-customer-dpa/`) | sócio | ⬜ |
| 4 | **Confirmar "no training" + DPA nos providers LLM** (Anthropic, OpenAI, Google). **Bloqueante ABSOLUTO antes de enviar primeiro documento real** — sem opt-out de training, conteúdo do cliente pode ir parar em modelo público | sócio | ⬜ |
| 5 | **Política de Privacidade pública** listando **todos os subprocessadores** (Supabase, Render, Cloudflare R2, Resend, OpenAI, Anthropic, Google) — finalidade, base legal, retenção, direitos do titular, transferência internacional | jurídico/sócio | ⬜ |
| 6 | **Termo Regente↔Consultor B2B** definindo papéis controlador/operador: consultor é Controlador dos dados do cliente final dele; Regente é Operador. Inclui sub-operadores autorizados e fluxo de notificação de incidente | jurídico | ⬜ |
| 7 | **DPO nomeado** + e-mail público `dpo@regenteambiental.com.br` (alias no DNS + caixa monitorada) | sócio | ⬜ |
| 8 | **Endpoint/processo de direitos do titular** (acesso, retificação, anonimização, portabilidade, eliminação). E-mail manual com SLA de 15 dias documentado é suficiente para o MVP — rota REST `/api/v1/lgpd/titular` fica para depois | dev | ⬜ |
| 9 | **Política de retenção** definida + `LGPD_PURGE_ENABLED` replicado do CannabIA (worker periódico que purga documentos/AIJob/logs após o prazo contratado, com hash chain preservada para auditoria) | dev | ⬜ |

**Recomendação de ordem de execução (Sprint LGPD pós go-live infra):**
1. Itens 1-3 (DPAs hosting): assinar numa única sessão jurídica (~2h).
2. **Item 4 isolado e prioritário** — confirmar "no training" via dashboard de cada provider ANTES de qualquer outro item, porque sem isso o piloto não pode receber documento real.
3. Item 5 (política): texto-modelo OAB-SP ou ANPP adaptado, listando explicitamente cada subprocessador.
4. Item 6 (DPA B2B): anexar ao contrato comercial padrão (one-time).
5. Itens 7-8: configurar alias DNS `dpo@` + caixa monitorada + script de resposta padrão.
6. Item 9: portar `LGPD_PURGE_ENABLED` do CannabIA; aproveitar `cleanup-expired-intake-drafts` como template e estender para documentos/AIJob/logs.

**Riscos de não fechar antes do primeiro doc real:**
- ANPD pode aplicar multa (até 2% do faturamento por incidente, limitada a R$50M)
- Cliente consultor pode acionar judicialmente se um vazamento ocorrer sem DPA
- Reputação: se virar caso público, o produto perde a credibilidade institucional que é seu trunfo com órgãos públicos

---

## Débitos técnicos rastreados — Sprint A4/A5

Itens conhecidos mas **não bloqueantes para subir infra**. Anotar e endereçar em sprint dedicada:

1. **`Iterator → Generator` deprecation em [app/core/config.py:297](../app/core/config.py#L297)** — `@contextmanager` anotado com `-> Iterator[Foo]` é deprecated; usar `-> Generator[Foo]`. Não afeta runtime, só warning de typing. Trivial.

2. **`model_registry` unused import em [alembic/env.py:11](../alembic/env.py#L11)** — está com `# noqa: F401` (efeito colateral: força import dos models pra registrar no `Base.metadata`). Avaliar se o noqa ainda é necessário ou se o import pode sumir.

3. **Migrar de Celery `-B` embarcado para `celery-redbeat` OU serviço `regente-beat` dedicado.** **Obrigatório antes do primeiro scale horizontal** — múltiplas instâncias com `-B` disparam tasks cron duplicadas (DOU, DOE, vigia, acompanhamento, cleanup). Triggers: adicionar replica do worker, exigir `concurrency > 1`, volume > ~500 tasks/dia.

4. **Integrar Sentry — obrigatório antes do go-live com cliente real:**
   - `sentry-sdk[fastapi,celery]` no `requirements.txt`
   - Init em [app/main.py](../app/main.py) e [app/core/celery_app.py](../app/core/celery_app.py) lendo `SENTRY_DSN`
   - `SENTRY_DSN` no envVarGroup `regente-shared`
   - `traces_sample_rate=0.1` em prod (10% das requests)

---

## Operação e melhorias futuras (não débito — operação corrente)

1. **Rotacionar `SECRET_KEY`** se houver suspeita de leak. Render permite rotacionar via dashboard; após mudar, todos os JWTs ficam inválidos e usuários precisam relogar.

2. **Configurar backup PITR no Supabase.** Já vem incluído no plano Pro — validar no dashboard `Project Settings → Database → Backups`.

3. **Configurar BetterStack** (uptime + logs). Free tier comporta o piloto, alerta em <30s se `/health` cair.

4. **Migrar de `--pool=solo`** quando volume exigir paralelismo de OCR. `--pool=prefork --concurrency=2` no Standard 2GB cabe; revalidar memória antes.

---

## Apêndice — Template de credenciais externas

> Use este bloco quando estiver coletando os valores dos provedores externos
> (passos `a`, `c`, `d` do runbook). Cola num password manager seguro — **nunca
> commita preenchido**. Quando todos os valores estiverem coletados, transfere
> para o Render Dashboard preenchendo os campos `sync: false` do envVarGroup
> `regente-shared` (passo `e`).

```bash
# Supabase (passo a — Connection strings em Project Settings → Database)
SUPABASE_PROJECT_REF=                                           # informativo, vai pra SUPABASE_REGION docs
DATABASE_URL=postgresql://postgres.PROJECT_REF:PASS@aws-0-us-east-1.pooler.supabase.com:6543/postgres
MIGRATE_DATABASE_URL=postgresql://postgres:PASS@db.PROJECT_REF.supabase.co:5432/postgres

# Upstash Redis (passo d — TLS connection string, NÃO a non-TLS)
REDIS_URL=rediss://default:TOKEN@xxx.upstash.io:6379

# Cloudflare R2 (passo c — Manage R2 API Tokens → Create API Token)
MINIO_ACCESS_KEY=
MINIO_SECRET_KEY=
MINIO_SERVER=https://ACCOUNT_ID.r2.cloudflarestorage.com
MINIO_PUBLIC_URL=https://ACCOUNT_ID.r2.cloudflarestorage.com    # mesmo valor do MINIO_SERVER no R2

# LLM providers
ANTHROPIC_API_KEY=                                              # sk-ant-api03-...
OPENAI_API_KEY=                                                 # sk-proj-...
GEMINI_API_KEY=                                                 # AIza... — NÃO é GOOGLE_API_KEY (Settings espera GEMINI_*)

# Email transacional (Resend SMTP ou outro provider)
SMTP_HOST=
SMTP_USER=
SMTP_PASSWORD=
RESEND_API_KEY=                                                 # re_...
RESEND_AUDIENCE_ID=                                             # uuid do Audience criado no Resend

# Alerts operacionais (deixar vazio até integrar Slack/PagerDuty)
ALERT_WEBHOOK_URL=
```

### Pegadinhas que custam tempo

- **`GEMINI_API_KEY`**, não `GOOGLE_API_KEY`. O Settings tem `extra="ignore"`, então uma var com nome errado é silenciosamente descartada e o agente legislação falha no boot por falta de chave.
- **`MINIO_PUBLIC_URL` separado de `MINIO_SERVER`.** No R2 ambos apontam pro mesmo endpoint, mas o código usa propriedades distintas (`minio_internal_endpoint` para boto3, `minio_public_endpoint` para presigned URLs). Setar só `MINIO_SERVER` funciona via fallback, mas é frágil.
- **`rediss://` (com duplo `s`)** no Upstash — schema TLS. Sem isso o Celery tenta conexão plain e o Upstash rejeita.
- **`MIGRATE_DATABASE_URL` aponta pro Supabase direct (5432), NÃO pooler (6543).** Pooler em transaction mode quebra DDL — alembic precisa de sessão estável.
- **`DATABASE_URL` no Supabase pooler tem prefixo `postgres.<ref>` no user** (`postgres.abcdefg`), não só `postgres`. Esse prefixo é o que faz o pooler identificar o projeto.

### Vars preenchidas automaticamente (não precisa coletar)

- `SECRET_KEY` — Render gera via `generateValue: true` no envVarGroup.
- `ENVIRONMENT`, `LOG_LEVEL`, `SUPABASE_REGION`, `EMAILS_FROM_*`, `RESEND_FROM_*`, `AI_DEFAULT_MODEL`, `AI_FALLBACK_MODEL`, `AI_MAX_COST_PER_JOB_USD`, `LEGISLATION_USE_GEMINI_DEFAULT`, `MINIO_SECURE`, `SMTP_PORT`, `SMTP_TLS`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `ALGORITHM`, `PROMETHEUS_QUEUE_NAMES`, `ALERT_WEBHOOK_MIN_SEVERITY`, `AI_ENABLED`, `EMBEDDING_PROVIDER` — valores literais hardcoded no [render.yaml](../render.yaml).
- `BACKEND_CORS_ORIGINS`, `CLIENT_PORTAL_URL` — hardcoded no service `regente-api` (não no envVarGroup compartilhado).
