# Runbook Ops

**Documento:** Operação · como operar produção
**Estado:** vivo · atualizar a cada incidente que ensine algo novo
**Última revisão:** 2026-05-15
**Para:** ops, SRE, dev de plantão

---

Guia objetivo para operar o Regente Ambiental em produção. Decisões aqui são opinionated — quando você precisa agir rápido, não tem tempo para debate.

## Stack de produção (recomendada)

| Componente | Recomendação | Por quê |
|---|---|---|
| Compute | VPS x86_64 ≥ 4 vCPU + 8 GB RAM | API + worker + db em uma máquina cabe até dezenas de tenants |
| Postgres | Managed (RDS, Neon, Supabase) ou single dedicada com backup automático | Banco é o ativo mais crítico — vale terceirizar |
| Redis | Managed simples (Upstash, ElastiCache nível básico) ou compose local | Não precisa cluster |
| MinIO ou S3 | S3 real em produção; MinIO para staging | S3 escala sem ops |
| Reverse proxy | Caddy (auto-TLS) ou Traefik | Let's Encrypt sem dor |
| Observabilidade | Prometheus + Grafana + Alertmanager | `/metrics` já existe |
| Logs | stdout → coletor (Loki, Cloudwatch, etc.) | JSON estruturado |
| Alertas | Webhook → Slack/Discord/PagerDuty | `ALERT_WEBHOOK_URL` |

## Checklist pré-deploy

Antes do primeiro deploy em produção:

### Segurança

- [ ] `SECRET_KEY` ≥ 32 chars (`openssl rand -hex 32`), **diferente** do default
- [ ] `CREDENTIAL_ENCRYPTION_KEY` gerada com `python tools/gen_encryption_key.py` e configurada (Render: env var `sync: false`). **Obrigatória** — a app falha no startup sem ela. **Separada** do `SECRET_KEY` (ADR-014). Guardar backup seguro fora do banco: perda da chave = perda dos segredos
- [ ] `POSTGRES_PASSWORD` forte, não-default
- [ ] `REDIS_PASSWORD` configurado (não default)
- [ ] `MINIO_ACCESS_KEY` e `MINIO_SECRET_KEY` **não** podem ser `minioadmin` em prod (backend valida)
- [ ] `MINIO_PUBLIC_URL` apontando para domínio real (não localhost)
- [ ] `BACKEND_CORS_ORIGINS` apenas com domínios de produção (sem localhost)
- [ ] `CLIENT_PORTAL_URL` com URL final
- [ ] `ENVIRONMENT=production` (desabilita `/docs` automaticamente)

### E-mail

- [ ] `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` reais (não Mailtrap)
- [ ] `EMAILS_FROM_EMAIL` no domínio configurado (SPF/DKIM/DMARC OK no DNS)
- [ ] `EMAILS_FROM_NAME` preenchido (`Regente Ambiental`)
- [ ] Para waitlist: `RESEND_API_KEY`, `RESEND_AUDIENCE_ID`, `RESEND_FROM_EMAIL=contato@regenteambiental.com.br`
- [ ] Teste de envio: `python ops/check_smtp.py`

### IA

- [ ] `AI_ENABLED=true`
- [ ] `OPENAI_API_KEY` (e Gemini se `LEGISLATION_USE_GEMINI_DEFAULT=true`)
- [ ] `AI_MAX_COST_PER_JOB_USD` calibrado (default $0.10; subir só com motivo)
- [ ] `AI_BUDGET_USD_MONTHLY_PER_TENANT_DEFAULT` definido

### Banco

- [ ] Backup automático configurado (idealmente: diário cheio + WAL contínuo)
- [ ] Snapshot pré-deploy tirado
- [ ] PostGIS e pgvector instalados na imagem (a imagem custom em `docker/db/Dockerfile` já cuida)

### Observabilidade

- [ ] `ALERT_WEBHOOK_URL` apontando para sink real
- [ ] Prometheus scraping `/metrics` do API
- [ ] Alertmanager configurado com regras de `ops/prometheus-alerts.yml`
- [ ] Dashboards Grafana versionados (TODO — hoje ad-hoc)

### Rede

- [ ] HTTPS na frente (Caddy/Traefik/Cloudflare)
- [ ] Acesso ao Postgres restrito ao API/worker (security group ou firewall)
- [ ] Acesso ao Redis restrito ao API/worker
- [ ] MinIO console (porta 9001) bloqueado externamente ou com auth

### App

- [ ] `alembic upgrade head` aplicou todas as 40+ migrations
- [ ] Health check `/health` responde 200 com todos os componentes verdes
- [ ] Métricas `/metrics` populadas
- [ ] Smoke test: `python ops/run_homologation_smoke.py` (em staging primeiro)

Lista canônica também em `ops/production-secrets-checklist.md`.

## Deploy

### Por SSH em VPS (modelo provável dos primeiros tenants)

```bash
# Na máquina de prod
cd /opt/regente
git pull
cp .env.prod .env

# Build + up
docker compose -f docker-compose.yml up -d --build

# Verificar migrations
docker compose exec api alembic current
docker compose exec api alembic upgrade head

# Health
curl https://api.regenteambiental.com.br/health
```

> Sempre use `-f docker-compose.yml` em prod — assim **não carrega** o `docker-compose.override.yml` (que é só de dev).

### Rollback rápido

```bash
# Reverter código
git checkout <commit-anterior>

# Restart sem rebuild (se nada mudou em dependências)
docker compose restart api worker

# OU rebuild se mudou Dockerfile/requirements
docker compose up -d --build
```

> **Cuidado com migrations:** se a versão anterior usa schema antigo, rodar `alembic downgrade` antes de subir. Migration sem reversa é dívida operacional — evitar.

## Migrations em produção

> **Lição (incidente 2026-06-06):** *deploy de código ≠ migration aplicada.* As Fases 1-4 subiram em prod mas a migration do `extracted_field_staging` não foi aplicada (o Render só deploya código). O extrator explodia ao gravar (`UndefinedTable`) e a chain entrava em retry storm — a sócia validou sobre um sistema quebrado. **Validação de fase inclui o banco de prod.**

### O que acontece no deploy (automático desde 2026-06-06)

- **Render (prod):** o serviço **`regente-api`** tem `preDeployCommand: alembic upgrade head` (em `render.yaml`). Roda na imagem recém-buildada, **antes** da nova versão entrar no ar — então o schema já está migrado quando API e worker sobem. **Só a API** roda migration (o worker não — evita corrida entre serviços). Idempotente (no-op quando já está em `head`). Usa `MIGRATE_DATABASE_URL` (conexão direta, porta 5432) via `alembic/env.py`.
- **Dev (docker-compose):** o serviço `api` roda `python -m app.db.init_db` no boot, que aplica `alembic upgrade head`. Paridade com prod garantida.

### Como verificar (pós-deploy)

```bash
# No Render Shell do serviço regente-api:
alembic current        # deve mostrar a revisão = head
alembic heads          # exatamente 1 head (sem branches divergentes)
```

Ou pela aplicação: `GET /health` deve responder 200 com os componentes verdes (uma tabela ausente derruba endpoints que a usam).

### Aplicar manualmente em emergência

Se um deploy falhou no `preDeployCommand` (a release não entra no ar — o deploy aborta) ou se for preciso aplicar fora de um deploy:

```bash
# Render Shell do regente-api (a imagem tem alembic + app + MIGRATE_DATABASE_URL):
alembic current        # ver onde está
alembic upgrade head   # aplicar pendentes (idempotente)
# Em rollback de schema (raro, com migration reversível):
alembic downgrade -1
```

> Se o `preDeployCommand` falhar, o Render **aborta o deploy** e mantém a versão anterior no ar — o sintoma vira "deploy não promove", não "sistema quebrado silenciosamente". É o comportamento desejado.

## Operação diária

### Verificar saúde geral

```bash
curl https://api.regenteambiental.com.br/health
# 200 + JSON com db, redis, minio: OK
```

Olhar Grafana (quando estiver configurado):
- Taxa de erros 5xx < 1%
- Latência P95 < 1.5s
- Fila Celery < 50 jobs
- Custo IA do mês × orçamento

### Verificar backup

Diário: confirmar que o último snapshot do Postgres é recente. Falha de backup é alerta crítico.

### Rotação de logs

Logs em JSON via stdout são coletados pelo runtime (Docker / coletor externo). Configurar rotação no nível de coletor — não dentro do container.

### Crawlers (quando ativados)

```bash
# Forçar uma execução
docker compose exec worker celery -A app.core.celery_app call workers.monitor_legislation_dou

# Ver Beat schedule
docker compose exec worker celery -A app.core.celery_app inspect scheduled
```

## Operação em emergência

### "Tudo está fora"

1. `curl /health` → componente fora?
2. `docker compose ps` → algum serviço down?
3. `docker compose logs --tail=200 api worker` → erro recente?
4. `docker compose restart api worker` (na maioria dos casos resolve)

### "API saudável mas tarefas Celery não processam"

1. `docker compose logs --tail=200 worker`
2. `docker compose exec worker celery -A app.core.celery_app inspect ping`
3. `docker compose exec redis redis-cli -a <pwd> LLEN celery`  ← profundidade da fila
4. Se fila gigante → worker dimensionado pra baixo, ou job preso → matar e investigar
5. Restart: `docker compose restart worker`

### "Banco lento"

1. `docker compose exec db psql -U postgres -d amigao_db -c "SELECT * FROM pg_stat_activity WHERE state != 'idle';"`
2. Identificar queries longas
3. Se for query da app → identificar o endpoint via `trace_id` no log
4. Bloqueio crítico → matar conexão problemática: `SELECT pg_terminate_backend(<pid>)`

### "IA está caríssima"

1. `SELECT agent_name, SUM(cost_usd), COUNT(*) FROM ai_jobs WHERE created_at > now() - interval '1 hour' GROUP BY agent_name ORDER BY 2 DESC;`
2. Identificar agente custoso
3. Olhar prompts/contexto (logs) — tem loop? Documento gigante?
4. Cost cap deve estar enforced; se passou, é bug — abrir ticket
5. Emergência: zerar `AI_ENABLED=false` e restart (desliga toda IA do sistema)

### "MinIO cheio"

1. Console em `https://minio.regenteambiental.com.br:9001`
2. Bucket `amigao-docs` → espaço usado
3. Limpeza: identificar docs de tenants arquivados há > 1 ano → revisar política de retenção em [`../arquitetura/MULTITENANT_LGPD.md`](../arquitetura/MULTITENANT_LGPD.md)
4. Aumentar disco antes de deletar nada

### "Alguém vazou .env"

1. **Trocar imediatamente:** `SECRET_KEY`, `CREDENTIAL_ENCRYPTION_KEY` (ver "Rotação de chave de criptografia" abaixo — exige re-encrypt, não é troca seca), `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `SMTP_PASSWORD`, `RESEND_API_KEY`, senhas do banco e MinIO
2. Trocar `SECRET_KEY` **força logout de todos** (JWTs antigos não validam mais) — isso é desejável em vazamento
3. Comunicar tenants impactados (LGPD art. 48 — se houve incidente com dados pessoais, comunicar ANPD e titulares em prazo razoável)
4. Auditar `AuditLog` no período possível do vazamento
5. Postmortem: como aconteceu, prevenção

## WhatsApp / Evolution (fora do boot desde 2026-06-01)

O canal WhatsApp (Evolution API) foi **desacoplado do boot** em 2026-06-01 (decisão do André)
para destravar `docker compose up -d` — a definição do serviço `evolution` no compose exigia
`EVOLUTION_API_KEY` (`${EVOLUTION_API_KEY:?...}`) e abortava o startup do core inteiro, mesmo
com a Evolution dormente. O **código permanece**: provider em `app/services/messaging/` e webhook
em `/api/v1/messaging/whatsapp/webhook`.

- **Estado atual:** sem `EVOLUTION_API_URL`/`EVOLUTION_API_KEY` no `.env`, o webhook responde
  **503 "WhatsApp não configurado"**. O boot do core (api, worker, db, redis, minio) **não depende**
  da Evolution. Ver dívida #37 em [`../REGISTRO_DIVIDAS.md`](../REGISTRO_DIVIDAS.md).
- **Para reativar o canal WhatsApp:**
  1. Repor o serviço `evolution` no `docker-compose.yml` (a definição antiga está no git — PR 2.1, #38)
     sob o profile `whatsapp`, e criar o database `evolution` no Postgres.
  2. Preencher no `.env`: `EVOLUTION_API_URL`, `EVOLUTION_API_KEY`, `EVOLUTION_WEBHOOK_SECRET`
     (e `WHATSAPP_PROVIDER=evolution`, default).
  3. Subir a instância: `docker compose --profile whatsapp up -d evolution` e parear o número
     (QR no Manager da Evolution).
  4. Conferir: o webhook deixa de responder 503 quando as envs estão presentes.

## WebSocket e CORS em produção (mergulho 2026-06-01)

### WebSocket (tempo real / toasts de agentes)
- A rota é `@router.websocket("/ws")` com token por query param `?token=<jwt>`.
  Desde 2026-06-01 está montada **nos dois caminhos**: `/ws` (dev) e
  `/api/v1/ws` (produção — o front deriva a URL de `VITE_API_URL`, que inclui
  `/api/v1`). Antes, produção batia em `/api/v1/ws` → 403.
- **Cloudflare:** Network → **WebSockets = ON** (padrão; confirmar que não foi
  desligado). Com proxy laranja em `api.regenteambiental.com.br`, o upgrade passa.
- **Render:** Web Service suporta WS nativamente — nada a configurar além do
  deploy.
- **Recomendado (limpo):** setar no build do front
  `VITE_WS_URL=wss://api.regenteambiental.com.br` (SEM `/api/v1`). Com o fix de
  path, `/api/v1/ws` também funciona sem essa env.
- **Degradação:** se o WS cai, a UI **não** quebra — o `onerror` é silencioso
  (só não chegam os toasts em tempo real). WS **não** é causa do Error Boundary.

### CORS — "bloqueado por CORS" pode ser um 500 mascarado
- `BACKEND_CORS_ORIGINS` de produção (`render.yaml`) já inclui os 3 domínios
  (`app.`, raiz e `www.regenteambiental.com.br`). CORS de config está OK.
- **Importante:** uma resposta **500** carregava antes resposta SEM
  `Access-Control-Allow-Origin` (o `ServerErrorMiddleware` fica acima do
  `CORSMiddleware`) → o navegador reportava como "bloqueado por CORS",
  **mascarando o erro real**. Desde 2026-06-01 um handler global reanexa os
  cabeçalhos CORS + `request_id` na resposta 500.
- **Diagnóstico:** se um endpoint "der CORS" no navegador mas `/clients` e
  `/properties` não derem, é quase certo um **500 no endpoint**. Agora o corpo do
  500 traz `request_id` — cruze no log do `regente-api` (Render) para a
  stacktrace. Sempre `curl` direto o endpoint com `Origin` + `Authorization`
  antes de mexer em CORS (ver também `feedback_cors_error_can_mask_4xx`).

## Storage (Cloudflare R2) e Redis (Upstash) em produção (2026-06-01)

### R2 exige `region="auto"`
- O cliente S3 (`app/services/storage.py`) usa `region_name=settings.S3_REGION`,
  **default `"auto"`**. Cloudflare R2 **exige** `auto`: com `us-east-1` o scope da
  assinatura SigV4 não bate no **GET server-side** → `SignatureDoesNotMatch`. O
  upload presigned tolera (o arquivo sobe), mas o **download nunca lê** — sintoma
  clássico de "OCR não extrai nada".
- `render.yaml` seta `S3_REGION=auto` explícito. Não precisa mexer — o default já
  cobre R2 e MinIO (o MinIO ignora region).
- **Diagnóstico no Render Shell (worker):**
  ```bash
  python -c "
  from app.services.storage import get_storage_service
  s = get_storage_service()
  print('region:', s.s3_client.meta.region_name)          # tem que ser 'auto'
  print(len(s.download_bytes('<storage_key_real>')), 'bytes')   # > 0 = OK
  "
  ```
  `SignatureDoesNotMatch` ou `0 bytes` com objeto existente = region/credencial
  errada. **`download_bytes` agora LEVANTA** `StorageDownloadError(code)` nesse
  caso (antes engolia e retornava vazio) — a causa aparece no log do worker e no
  evento `storage_error:<code>`, não mais como `no_bytes` cego.

### `MINIO_SECURE` é respeitado (sem scheme na env)
- A env do R2 chega como `<acct>.r2.cloudflarestorage.com` (sem `http(s)://`).
  Os endpoints (`minio_internal_endpoint`/`minio_public_endpoint`) agora usam
  `https://` quando `MINIO_SECURE=True` e a env não traz scheme (antes forçavam
  `http://`). Em prod, `MINIO_SECURE=True`.

### Redis `rediss://` (Upstash) e o `ssl_cert_reqs`
- O app usa `settings.redis_url_safe`, que **normaliza** o param `ssl_cert_reqs`
  para o token que o redis-py aceita (`none`/`optional`/`required`). Uma env com
  `?ssl_cert_reqs=CERT_REQUIRED` (nome da constante Python) quebrava com
  *"Invalid SSL Certificate Requirements Flag: CERT_REQUIRED"* — derrubava o
  evento realtime (preview ao vivo do OCR). Não precisa anexar nada à URL; a
  normalização cobre qualquer forma.
- Celery (`app/core/celery_app.py`) seta `broker_use_ssl`/`redis_backend_use_ssl`
  **só** quando o URL é `rediss://`. Em `redis://` local não seta (setar num
  não-SSL faz o Celery abortar).

### Modelo de OCR (Gemini) é env — `GEMINI_OCR_MODEL`
- O modelo Gemini Vision do OCR (`app/services/ocr_pdf.py`) vem de
  `settings.GEMINI_OCR_MODEL` (default `gemini/gemini-2.5-flash`). **Quando o
  Google descontinuar um modelo, atualizar a env `GEMINI_OCR_MODEL` — NÃO o
  código.** Em 2026-06-02 o worker quebrou com `404 models/gemini-2.0-flash is no
  longer available` justamente porque o modelo estava hardcoded no código.
- Sintoma do modelo morto: doc escaneado fica `ocr_failed`/`chars=0`; no log do
  worker `ocr_pdf.gemini falhou: ... is no longer available`.
- O fallback OpenAI Vision (`gpt-4o-mini`) tem timeout próprio
  (`OPENAI_VISION_TIMEOUT_SECONDS=75`) e `num_retries=0` para **não pendurar** a
  fila do worker (`pool=solo`); antes pendurava ~272s antes de desistir.
- **Diagnóstico no Render Shell (worker)** — roda o OCR no último doc real:
  ```bash
  python -c "
  from app.db.session import SessionLocal
  from app.models.document import Document
  from app.workers.ocr_tasks import ocr_then_extract
  db = SessionLocal(); doc = db.query(Document).order_by(Document.id.desc()).first(); db.close()
  print(ocr_then_extract(doc_id=doc.id, tenant_id=1, user_id=1, force=True))
  "   # esperado: status='ocr_ok', chars>0
  ```

## Backups e recuperação

### Estratégia recomendada

- **Postgres:** dump diário cheio + WAL contínuo (point-in-time recovery)
- **MinIO:** replicação para bucket secundário em provider/região diferente
- **`.env` de prod:** versionado em vault (HashiCorp Vault, 1Password, AWS Secrets Manager) — **nunca** em git

### Teste de restore (a fazer)

Periodicamente (mensal recomendado): restaurar backup em ambiente isolado e validar que aplicação sobe.

## Updates de dependências

### Python

```bash
# Em dev, atualizar requirements.txt
# Subir uma versão por vez quando possível

# Rebuild com novo requirements
docker compose build api worker
```

### Node (frontend)

```bash
cd frontend
npm outdated
npm update <pkg>
npm run build  # se passar, está OK
```

### Postgres major version

Migração de versão major (15 → 16) exige planning:
- Snapshot completo antes
- Testar em staging com dump da prod
- pg_dump + pg_restore (não basta trocar imagem com volume antigo)
- Verificar compatibilidade de PostGIS e pgvector

## Rotação de chave de criptografia

Aplica-se à `CREDENTIAL_ENCRYPTION_KEY` (cripto de segredos de portal/LLM — ADR-014). Diferente do
`SECRET_KEY` do JWT, **não dá pra trocar a seco**: o ciphertext no banco foi escrito com a chave
antiga. A rotação usa `MultiFernet` para conviver com as duas chaves durante a transição.

Esboço do processo (script de re-encrypt será criado na **primeira rotação real**):

1. Gerar a chave nova: `python tools/gen_encryption_key.py`.
2. Setar `CREDENTIAL_ENCRYPTION_KEY_OLD` = chave **antiga** (a que está em uso hoje).
3. Atualizar `CREDENTIAL_ENCRYPTION_KEY` = chave **nova**. Reiniciar a app.
   - A partir daqui, `MultiFernet` **decripta** com qualquer das duas e **encripta** com a nova.
   - Dados antigos continuam legíveis; dados novos já saem na chave nova.
4. Rodar o script de re-encrypt (relê e regrava cada segredo, migrando o ciphertext para a chave
   nova). Enquanto não existir, este passo é manual/indisponível — só há segredo real no banco a
   partir da PR 2.3 / PR LLM.
5. Quando todos os segredos estiverem reescritos, **remover** `CREDENTIAL_ENCRYPTION_KEY_OLD` e
   reiniciar. A chave antiga pode então ser descartada do vault.

> ⚠ Nunca perder a chave em uso antes de re-encriptar: sem ela, os segredos são irrecuperáveis.

## Pendências e dívidas

1. **Dashboards Grafana não versionados** — hoje cada um cria os seus
2. **Alertmanager rules incompletas** — só algumas categorias cobertas
3. **Teste de restore** não rotinado
4. **PITR (point-in-time recovery)** não documentado caso a caso
5. **Procedimento de scaling horizontal** não documentado — ainda monolito single-node

## Próximas leituras

- [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md) — playbooks de incidentes
- [`SEED_DADOS.md`](./SEED_DADOS.md) — quando precisar repopular ambientes
- [`../arquitetura/OBSERVABILIDADE.md`](../arquitetura/OBSERVABILIDADE.md) — métricas e alertas em detalhe
