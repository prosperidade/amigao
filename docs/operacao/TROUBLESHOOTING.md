# Troubleshooting

**Documento:** Operação · playbooks de incidente
**Estado:** vivo · adicionar nova entrada cada vez que algo dói duas vezes
**Última revisão:** 2026-05-15

---

Playbooks para quando algo quebra. Organizado por sintoma (o que você vê primeiro), com causa provável e ação imediata.

## Categoria 1 — Setup local (dev)

### `docker compose up` falha em `db` com "extension postgis does not exist"

**Causa:** rodando imagem oficial `postgres:15` em vez da imagem custom do projeto.

**Solução:**

```bash
docker compose down -v   # remove volume velho
docker compose build db
docker compose up -d
```

A imagem `amigao_do_meio_ambiente-db` é buildada de `docker/db/Dockerfile` e adiciona PostGIS + pgvector.

---

### Porta 5432 já em uso (host)

**Causa:** outro Postgres rodando no host.

**Solução:** o `docker-compose.yml` já expõe `${HOST_DB_PORT:-55432}:5432` — host port default é **55432**, não 5432. Não conflita.

Se quiser mudar: `HOST_DB_PORT=55433` no `.env`.

---

### `SECRET_KEY must be set in .env or shell`

**Causa:** `.env` não tem `SECRET_KEY` ou é menor que 32 chars.

**Solução:**

```bash
echo "SECRET_KEY=$(openssl rand -hex 32)" >> .env
docker compose up -d api worker
```

---

### Backend não acha módulo `app.xxx` após git pull

**Causa:** novo arquivo Python adicionado, mas o worker (sem hot-reload) precisa restart.

**Solução:**

```bash
docker compose restart worker
```

API em dev tem hot-reload — só worker precisa.

---

### `alembic upgrade head` falha com "Can't locate revision identified by..."

**Causa:** branch teve migration deletada ou renomeada; ambiente local está em estado intermediário.

**Solução:**

```bash
# 1. Ver onde está
docker compose exec api alembic current

# 2. Ver heads do código
docker compose exec api alembic heads

# 3. Se houver duplicação (heads múltiplos):
docker compose exec api alembic merge -m "merge heads" <head1> <head2>
docker compose exec api alembic upgrade head
```

Em último caso, sobrescrever versão local:

```bash
docker compose exec api alembic stamp <revision-conhecida-boa>
docker compose exec api alembic upgrade head
```

⚠️ `stamp` **não roda DDL** — só atualiza o ponteiro. Use só se você sabe que o schema bate com a revision marcada.

---

### Frontend não compila com erro de TypeScript `any` ou `noUnusedLocals`

**Causa:** import não usado, tipo `any` explícito, ou variável local sem uso.

**Solução:** corrigir. Strict mode é princípio inegociável ([`../manifesto/03-PRINCIPIOS.md`](../manifesto/03-PRINCIPIOS.md) §9). Não desabilitar a regra.

```bash
cd frontend
npm run lint   # achata erros
```

---

### `pytest` falha em "could not connect to PostgreSQL"

**Causa:** Testcontainers não conseguiu subir o container do Postgres (Docker não rodando ou rede restrita).

**Solução:**

```bash
# 1. Confirmar Docker rodando
docker ps

# 2. Confirmar imagem disponível
docker pull postgis/postgis:15-3.3

# 3. Rodar de novo
pytest tests/ -q
```

Em CI: garantir runner com privilégios de Docker.

## Categoria 2 — Backend / API

### Endpoint retorna 401 mesmo com token

**Causa provável:** token expirado, ou `X-Auth-Profile` errado.

**Diagnóstico:**

```bash
# Decodificar JWT (sem validar assinatura) para ver expiração
# Cole o token em https://jwt.io
```

**Solução:**

- Token expirado → fazer login de novo
- Profile errado → confirmar header `X-Auth-Profile: internal` em endpoints do painel

---

### Endpoint retorna 403 ao tentar acessar entidade

**Causa provável:** entidade pertence a outro tenant.

**Diagnóstico:**

```sql
SELECT tenant_id FROM <tabela> WHERE id = <X>;
SELECT tenant_id FROM users WHERE email = '<user>';
```

Se os `tenant_id` diferem → 403 é correto (multi-tenant funcionando).

Se forem iguais e ainda 403 → bug. Olhar logs com `trace_id` da requisição.

---

### `POST /api/v1/waitlist` retorna 429

**Causa:** rate limit de 10 requests/min/IP foi atingido.

**Solução:** esperar 1 min ou trocar IP. Em produção, esse limite protege contra abuse — não aumentar levianamente.

---

### `POST /api/v1/ai/*` retorna 429 "Limite de custo de IA excedido"

**Causa:** tenant atingiu `$5/hora` (default `AI_HOURLY_COST_LIMIT_USD`) **ou** orçamento mensal.

**Diagnóstico:**

```sql
SELECT SUM(cost_usd)
FROM ai_jobs
WHERE tenant_id = X
  AND created_at >= now() - interval '1 hour';
```

**Solução:**

- Esperar 1 hora (limite por hora) ou virar o mês (limite mensal)
- Aumentar `Tenant.ai_monthly_budget_usd` se for tenant legítimo com necessidade real
- Investigar se há agente em loop (revisar prompt + contexto)

---

### Agente retorna `requires_review=True` em **tudo**

**Causa:** comportamento correto. Peças formais (PRAD, ofícios, memoriais, contratos, propostas) **sempre** exigem revisão humana — é Princípio 1 do manifesto.

**Solução:** o consultor revisa e marca `requires_review=False` via `PATCH /api/v1/ai/jobs/{id}`.

---

### Citação inventada pela IA passou despercebida

**Causa:** `citation_evaluator` não pegou ou a base regulatória não cobre a norma.

**Diagnóstico:**

```sql
SELECT result->'citation_issues' FROM ai_jobs WHERE id = X;
SELECT * FROM knowledge_catalog WHERE identifier = '<lei citada>';
```

**Solução:**

- Norma de fato não existe → ajustar prompt; reportar como bug do agente
- Norma existe mas não está no `knowledge_catalog` → ingerir (`scripts/ingest_*`)
- Citação válida marcada como suspeita → bug do regex extractor; abrir ticket

---

### OCR retorna texto vazio ou ruim

**Causa:** PDF escaneado mal escaneado (foto/ruído alto), ou tentativa A do pipeline (pypdf) extraiu só pontuação.

**Diagnóstico:** ver `AIJob.result` do job de OCR.

**Solução:**

- Forçar re-OCR com Vision: endpoint suporta `?force=true` na re-extração
- Documento ilegível → pedir ao cliente upload de melhor qualidade

---

### `AIJob.status = 'failed'` em massa de uma vez

**Causa provável:** provider IA fora (rate limit do OpenAI, problema no Gemini).

**Diagnóstico:**

```sql
SELECT model_used, status, COUNT(*)
FROM ai_jobs
WHERE created_at > now() - interval '15 min'
GROUP BY model_used, status;
```

**Solução:**

- Confirmar status do provider (status.openai.com, etc.)
- Fallback automático já deveria ter pegado — se não pegou, checar se outras keys estão configuradas
- Pico transitório → retry manual dos jobs falhos

---

### Worker Celery não pega novas tasks

**Diagnóstico:**

```bash
docker compose exec worker celery -A app.core.celery_app inspect ping
docker compose exec redis redis-cli -a <pwd> LLEN celery
```

**Solução:**

```bash
docker compose restart worker
```

Se persistir: ver logs do worker (`docker compose logs --tail=300 worker`).

## Categoria 3 — Banco

### Migration trava no boot

**Sintoma:** API não sobe; logs mostram `alembic` rodando indefinidamente.

**Causa provável:** migration aplica lock pesado em tabela grande.

**Solução:**

- Em produção, **separar** boot do app de aplicação de migration:
  - Rodar `alembic upgrade head` manualmente antes do deploy
  - Boot do app só faz `alembic current` para confirmar
- Em dev, esperar (geralmente termina)

---

### `psycopg2.errors.UniqueViolation` no seed

**Causa:** seed rodando em base que já tem dados; conflito em UNIQUE.

**Solução:** seed é idempotente para entidades-chave (User, Tenant). Verifique se a migration mais recente adicionou nova UNIQUE constraint e o seed não foi atualizado.

---

### `Property.geom` está vazio em todas as propriedades

**Causa:** pendência conhecida. Parser de shapefile/KML ainda não existe.

**Solução:** popular manualmente via SQL para casos de teste:

```sql
UPDATE properties
SET geom = ST_GeomFromText('POLYGON((...))', 4674)
WHERE id = X;
```

Roadmap: parser na janela 2 ([`../manifesto/04-ROADMAP.md`](../manifesto/04-ROADMAP.md)).

## Categoria 4 — Frontend

### Login não persiste após reload

**Causa:** Zustand persist não está salvando, ou storage limpa após cada sessão.

**Diagnóstico:** abrir DevTools → Application → Local Storage → procurar chave do Zustand.

**Solução:**

- Limpar local storage e logar de novo
- Se `localStorage` está bloqueado (modo anônimo, política do navegador) → não há solução; trocar de janela

---

### Página em branco depois do build

**Causa:** erro de runtime que o dev server pegava mas o build não. Geralmente import quebrado ou variável de ambiente faltando.

**Diagnóstico:** abrir DevTools → Console.

---

### Frontend não conecta no backend

**Causa:** CORS, URL errada, ou backend offline.

**Diagnóstico:**

- DevTools → Network → procurar request com 0/CORS error
- Conferir `frontend/src/lib/api.ts` ou `.env` do frontend
- Conferir `BACKEND_CORS_ORIGINS` no backend

## Categoria 5 — E-mail

### E-mail não chega (SMTP)

**Diagnóstico:**

```bash
docker compose exec api python ops/check_smtp.py
```

Cenários:
- Auth falha → senha errada ou conta bloqueada
- TLS falha → conferir `SMTP_TLS`, `SMTP_PORT`
- Timeout → firewall do provedor bloqueando porta

---

### Waitlist e-mail não chega (Resend)

**Diagnóstico:**

```sql
SELECT id, email, welcome_email_sent_at, welcome_email_resend_id
FROM pre_cadastros
WHERE email = '<email>';
```

- `welcome_email_sent_at IS NULL` → task ainda não rodou ou falhou
- `welcome_email_resend_id` populado → enviado, conferir dashboard Resend

**Solução:**

```bash
# Forçar task
docker compose exec worker celery -A app.core.celery_app call workers.send_welcome_email -- <pre_cadastro_id>
```

## Categoria 6 — Realtime / WebSocket

### Frontend não recebe eventos em tempo real

**Diagnóstico:**

- DevTools → Network → WS → conferir conexão estabelecida e mensagens chegando
- Conferir token na query string da URL do WebSocket

**Causa comum:** proxy/CDN sem suporte a upgrade WebSocket. Soluções: Caddy/Traefik têm suporte nativo; Cloudflare exige plano Pro+; Nginx exige config explícita.

## Categoria 7 — Identidade & repo

### `git push` reclama de remote antigo após rename

**Causa:** repo foi renomeado de `Amigao_do_Meio_Ambiente` para `regente-ambiental`; remote local ainda aponta para o nome antigo.

**Solução:**

```bash
git remote set-url origin git@github.com:<org>/regente-ambiental.git
```

> GitHub redireciona automaticamente, então o push antigo **funciona** mesmo sem essa correção — mas é boa prática atualizar.

---

### Vejo `amigao_*` em métricas / banco / bucket — bug?

**Não.** É codinome técnico interno, decisão documentada em [`../adr/004-regente-vs-amigao.md`](../adr/004-regente-vs-amigao.md). Branding visível é Regente Ambiental; identificadores internos seguem com `amigao_*` até sprint dedicada de reidentificação.

## Como adicionar novo playbook

Quando você resolver um incidente novo, adicione aqui:

```markdown
### <Sintoma em uma frase>

**Causa:** <descrição curta>

**Diagnóstico:** <comandos / queries>

**Solução:** <passos>
```

Categoria existente ou nova — escolha onde encaixa. Quanto mais cedo registrar, mais útil.

## Próximas leituras

- [`RUNBOOK_DEV.md`](./RUNBOOK_DEV.md) — operação local
- [`RUNBOOK_OPS.md`](./RUNBOOK_OPS.md) — operação prod
- [`../arquitetura/OBSERVABILIDADE.md`](../arquitetura/OBSERVABILIDADE.md) — onde os sinais vivem
