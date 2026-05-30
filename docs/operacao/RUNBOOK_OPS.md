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
