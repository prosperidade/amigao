# PROGRESSO — Sprint Waitlist (Regente Ambiental)

**Última atualização:** 2026-05-14 (noite) · **Próxima retomada:** amanhã
**Status:** ⏸️ **PAUSE após PR 2 — aguardando validação manual via curl**

Documentos da sprint:
- [RELATORIO_WAITLIST.md](RELATORIO_WAITLIST.md) — Fase 0, divergências, riscos, proposta
- **PROGRESSO_WAITLIST.md** (este arquivo) — onde paramos e o que vem amanhã

---

## TL;DR pra retomar amanhã

1. ☕ Rodar `alembic upgrade head` + subir API (`uvicorn` ou `docker compose up api`)
2. 🧪 Fazer o curl do happy path em `POST /api/v1/waitlist` (comandos no fim deste doc)
3. ✅ Se response shape OK → dar green-light pro **PR 3** (drip + templates)
4. 🌐 Em paralelo, criar conta Resend + Zoho Mail (extra-código, ver pendências)

---

## ✅ Concluído (2026-05-14)

### Fase 0 — RELATORIO_WAITLIST.md
- 18 divergências mapeadas, 12 riscos arquiteturais, proposta de 4 PRs
- Decisões alinhadas com o usuário (ver seção "Decisões registradas")

### PR 1 — Foundation (F1 + F2)
**Arquivos:**
- `app/models/pre_cadastro.py` — ORM com 24 campos (sem `tenant_id`, lead anônimo)
- `app/schemas/pre_cadastro.py` — `PreCadastroIn`, `PreCadastroOut`, `PrecoVanWestendorp`
- `alembic/versions/b1a2c3d4e5f6_sprint_b1_pre_cadastros.py` — migration + 7 índices + UNIQUE email
- `app/models/__init__.py` — registra `PreCadastro` (alfabético entre macroetapa e process)

**Validações Pydantic implementadas:**
- email → lowercase automático (idempotência case-insensitive)
- estado → uppercase + whitelist 27 UFs BR
- telefone → strip pra dígitos, 10-13 chars
- consentimento → bloqueante (False rejeita 422)
- preco_aceito → ordem coerente (barato_demais ≤ barato ≤ caro ≤ caro_demais)
- `extra="forbid"` → rejeita campos desconhecidos

### PR 2 — Endpoint + Resend client (F3 + F5 + F4)
**Arquivos novos:**
- `app/services/resend_client.py` — httpx síncrono, `send_email` + `upsert_audience_contact` (POST→PATCH fallback), `ResendAPIError` para autoretry, métricas/alertas alinhados com `EmailService` SMTP
- `app/api/v1/waitlist.py` — `POST /api/v1/waitlist`, slowapi 10/min, idempotência 200, bloqueio soft-deleted
- `app/workers/waitlist_tasks.py` — `sync_resend_audience` + `send_welcome_email`, autoretry 3× backoff exponencial até 10min
- `tests/test_waitlist_endpoint.py` — 13 testes (happy path, idempotência, validações, rate limit 429 no 11º)

**Edits:**
- `app/main.py` — import + `app.include_router(waitlist.router, prefix=f"{settings.API_V1_STR}/waitlist", tags=["Waitlist (Regente)"])`
- `app/core/config.py` — `RESEND_API_KEY`, `RESEND_AUDIENCE_ID`, `RESEND_FROM_EMAIL=contato@regenteambiental.com.br`, `RESEND_FROM_NAME="Regente Ambiental"` + validator fail-fast em prod
- `requirements.txt` — `pytest-httpx>=0.30`, `pytest-celery>=1.0` (para PR 3)
- `.env.example` — bloco Resend documentado + nota CORS para landing

---

## ⏳ Pendente amanhã

### 0. Smoke test PR 2 (você, antes do PR 3) — **BLOQUEANTE**

Comandos no final deste doc (seção "Comandos pra retomar"). Validar:
- [ ] Migration aplica sem erro (`alembic upgrade head`)
- [ ] Health check responde 200 (`GET /health`)
- [ ] Tag "Waitlist (Regente)" aparece em `GET /docs`
- [ ] Happy path retorna 200 com body `{"ok": true, "mensagem": "..."}`
- [ ] Idempotência: segundo POST mesmo email retorna mesma resposta
- [ ] Consentimento false retorna 422
- [ ] `SELECT * FROM pre_cadastros` mostra lead com `estado=SP` (uppercase) e `telefone=11987654321` (só dígitos)
- [ ] `pytest tests/test_waitlist_endpoint.py -q` passa (13 testes)

Se algum falhar → me passa o output exato, eu corrijo antes do PR 3.

### 1. PR 3 — Drip system + templates Jinja (V1 + V2)

**Modelo novo:** `app/models/pre_cadastro_drip_log.py`
- Tabela `pre_cadastros_drip_log(id, lead_id FK, step ENUM('welcome'|'d7'|'d14'|'d21'), status, sent_at, resend_message_id, error)`
- UNIQUE (lead_id, step) — idempotência garantida (Risco R8 do RELATORIO)
- Migration `<hash>_sprint_b2_drip_log.py`

**Tasks Celery:** `app/workers/waitlist_tasks.py` (incrementa o módulo já criado)
- `send_drip_d7(lead_id)` — corpo "educativo"
- `send_drip_d14(lead_id)` — corpo "bastidor"
- `send_drip_d21(lead_id)` — corpo "convite beta"
- Cada uma: `INSERT INTO pre_cadastros_drip_log ON CONFLICT DO NOTHING` → call Resend → UPDATE com resend_message_id

**Beat-scan task:** `scan_due_drip_emails` (rodando a cada 15min via `celery_app.conf.beat_schedule`)
- Query: `SELECT id FROM pre_cadastros WHERE deleted_at IS NULL AND created_at <= now() - interval 'X days' AND NOT EXISTS (SELECT 1 FROM pre_cadastros_drip_log WHERE lead_id=p.id AND step='dX')` para cada step
- Para cada lead → `send_drip_dX.delay(lead_id)`

**Refatorar:** `send_welcome_email` (já implementado) também grava em `drip_log` com `step='welcome'` para auditabilidade.

**Templates Jinja:** `app/templates/emails/`
- `_base.html` — layout dark com Verde Maestro (#1E7F55) + Dourado Cerrado (#C9A227) — alinhado com Modelo 3 Técnico da landing
- `welcome.html` — confirmação + próximos passos
- `drip_d7.html` — conteúdo educativo (sugiro: "Por que diagnóstico inicial trava sua consultoria" — caso real, sem hype)
- `drip_d14.html` — bastidor de produto ("Como decidimos o que entra na v0.1")
- `drip_d21.html` — convite ao beta com CTA pro form de aprofundamento
- Cada template tem versão `.txt` plain-text (deliverability)
- Variáveis: `nome`, `unsubscribe_url`, `tracking_pixel_url`

**Service de render:** `app/services/email_templates.py`
- `render_template(name, **ctx) -> tuple[html, text]` usando `jinja2.FileSystemLoader`
- Lazy load, cache em memória

**Settings:** adicionar `WAITLIST_DRIP_BEAT_INTERVAL_MINUTES=15` para tunável

**Tests:**
- `tests/test_waitlist_tasks.py` — happy path + retry + idempotência via drip_log
- `tests/test_drip_beat_scan.py` — seed de leads em datas diferentes, verifica que só dispara as devidas

**Estimativa:** 4-5h focadas.

### 2. PR 4 — README_DNS + páginas estáticas (V3 + V4)

**`README_DNS.md` no repo backend** (arquivo único):
- MX → Zoho (mx.zoho.com, mx2.zoho.com, mx3.zoho.com)
- SPF combinado: `v=spf1 include:zoho.com include:amazonses.com -all`
- DKIM Zoho: `zmail._domainkey` (chave gerada no console Zoho)
- DKIM Resend: `resend._domainkey` (chave gerada no console Resend)
- DMARC: começa `p=none; rua=mailto:dmarc-reports@regenteambiental.com.br`
- CNAME `api` → host do backend no Render
- Notas de propagação (24-48h), TLS auto-LE no Render

**`/lista-de-espera.html`** na landing (repo Netlify, separado):
- Página dedicada (não modal), mesma identidade Modelo 3 dark
- Form com 13 campos:
  - email (required), nome (required)
  - telefone (opcional)
  - perfil_profissional (select: Consultor / Empresa / Produtor / Outro)
  - estado (select 27 UFs)
  - tipo_licenciamento (select ou texto: LO/LP/LI/LAS/Outro)
  - volume_mensal (number 0-999)
  - ferramenta_atual (texto)
  - preco_aceito: 4 inputs lado a lado (Van Westendorp)
  - expectativa (textarea)
  - deal_breaker (textarea)
  - interesse_grupo (checkbox)
  - consentimento (checkbox bloqueante com link pra /privacidade.html)
- UTM params extraídos da URL via JS antes do POST
- States UI: idle → loading → success → error
- Timeout 10s com `AbortController`
- Fallback: se fetch falhar, abre Google Form em nova aba (preserva o que já existe)
- Atualizar os 5 CTAs da home pra apontar `<a href="/lista-de-espera">` em vez do Google Form

**`/privacidade.html`** na landing:
- Placeholder LGPD com texto mínimo viável (~300 palavras):
  - Quem coleta (Regente Ambiental, dados de contato)
  - Finalidade (comunicação de lançamento, validação de produto)
  - Base legal (consentimento, Art. 7º I LGPD)
  - Direitos do titular (acesso, retificação, exclusão — email `contato@regenteambiental.com.br`)
  - Retenção (até opt-out ou 24 meses pós-conversão)
  - Não compartilhamento com terceiros (exceto operadores: Resend, Zoho)
- Mesma identidade visual (dark) mas página leve, sem nav nem footer cheio

**Estimativa:** 3-4h focadas.

### 3. Tarefas extra-código (você, fora do agente)

| Tarefa | Onde | Tempo | Bloqueia |
|---|---|---|---|
| Criar conta Resend + verificar domínio `regenteambiental.com.br` | resend.com/signup | 10min | Envio de email |
| Pegar `RESEND_API_KEY` no console | Resend Settings > API Keys | 2min | `.env` de prod |
| Criar Audience "Regente Waitlist" + pegar `RESEND_AUDIENCE_ID` | Resend > Audiences | 5min | sync de contato |
| Criar conta Zoho Mail free tier (até 5 users) | zoho.com/mail/signup | 15min | Recepção |
| Verificar domínio no Zoho + pegar DKIM key | Zoho Mail Admin Console | 10min | Recepção |
| Adicionar 5 registros DNS no Netlify (MX, SPF, 2× DKIM, DMARC) | app.netlify.com/sites/.../dns | 10min | Envio + recepção |
| Adicionar CNAME `api` → host Render (após Render configurado) | Netlify DNS | 5min | Endpoint público |
| Criar serviço no Render + setar env vars de prod | render.com | 30min | Deploy do backend |
| Aplicar migration em prod (`alembic upgrade head` no Render shell) | Render shell | 5min | API funcional |

**Total estimado:** ~1h30 de trabalho operacional, espalhado conforme dependências.

---

## 📌 Decisões registradas (não revisitar)

| Decisão | Status |
|---|---|
| **Stack email:** Resend (envio) + Zoho Mail (recepção) | ✅ confirmado |
| **EmailService SMTP:** coexistência, NÃO migrar agora | ✅ confirmado |
| **Path endpoint:** `/api/v1/waitlist` (segue convenção) | ✅ confirmado |
| **Drip:** beat-scan da tabela (opção B), não `eta` Redis | ✅ confirmado |
| **Form:** página dedicada `/lista-de-espera.html` | ✅ confirmado |
| **Idempotência:** 200 silencioso (anti-enumeração) | ✅ confirmado |
| **Remetente waitlist:** `contato@regenteambiental.com.br` único, sem `EMAILS_FROM_WAITLIST` separado | ✅ confirmado |
| **PROJECT_NAME:** mantém "Amigão do Meio Ambiente" (rebrand é sprint separada) | ✅ confirmado |
| **Strings user-facing waitlist:** "Regente Ambiental" (escopo só dessa sprint) | ✅ confirmado |
| **Backend prod:** Render (Let's Encrypt auto) | ✅ confirmado |
| **interesse_grupo:** boolean | ✅ confirmado |
| **LGPD:** `consentimento` obrigatório no payload + `/privacidade.html` placeholder | ✅ confirmado |
| **Rate limit:** 10/min/IP (recalibrado de 3/min do brief — false-positives em CGNAT) | ✅ confirmado |
| **Anti-enumeração soft-delete:** lead deletado NÃO reativa, devolve mesma resposta | ✅ confirmado |
| **pytest-httpx + pytest-celery:** adicionados ao requirements | ✅ confirmado |

---

## 🚨 Riscos / follow-ups parqueados

Estes não bloqueiam a sprint, mas registro pra não perder:

1. **Rate limit storage em prod** — slowapi default é in-memory por processo. Múltiplos workers Gunicorn = limite por-worker, não global. Configurar `RATELIMIT_STORAGE_URL=redis://...` no `Limiter` quando subir mais workers.
2. **Resend domain warming** — primeiras 2 semanas, manter volume baixo (50 leads/dia) e DMARC `p=none`. Subir pra `p=quarantine` só após confirmar deliverability ≥95% via dashboard Resend.
3. **AuditLog requer tenant_id** — leads anônimos não cabem lá. Trilha LGPD fica em `pre_cadastros.consentimento_dado_em` + `created_at` + futuro `pre_cadastros_drip_log`. Suficiente.
4. **Rebrand completo Amigão→Regente** — sprint separada, depois desta. Hoje só strings user-facing da waitlist.
5. **Endpoint de unsubscribe próprio** — todo email Resend tem `unsubscribe` nativo (link no rodapé via Resend Audience). Mas se quiser opt-out direto via API (não só por click), criar `POST /api/v1/waitlist/{token}/unsubscribe` em sprint futura.
6. **Hard-delete via beat-scan** — `purge_after` precisa de task `purge_pre_cadastros_deleted` rodando diário. Não está no PR 3 (que cobre só drip de envio). Adicionar em PR 3 ou separar em PR mini.
7. **Admin endpoint pra leads** — fora do escopo. `PreCadastroAdmin` schema já criado pra quando for hora.

---

## 🔧 Comandos pra retomar amanhã

### Subir tudo

```bash
cd \\DESKTOP-L0VOP07\Users\Administrador\Desktop\Amigao_do_Meio_Ambiente

# Opção A: Docker (recomendado)
docker compose up -d
docker compose exec api alembic upgrade head

# Opção B: Local
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
celery -A app.core.celery_app worker --loglevel=info --pool=solo &
```

### Smoke test mínimo (3 comandos)

```bash
# 1. Health
curl -s http://localhost:8000/health

# 2. Happy path
curl -i -X POST http://localhost:8000/api/v1/waitlist \
  -H "Content-Type: application/json" \
  -d '{"email":"teste@example.com","nome":"Fulano Teste","consentimento":true}'

# 3. Conferir no banco
docker compose exec db psql -U postgres -d amigao_db -c \
  "SELECT id, email, nome, telefone, estado, utm_source, consentimento_dado_em FROM pre_cadastros;"
```

**Esperado:** primeiro retorna `{"status":"ok",...}`; segundo retorna `HTTP/1.1 200 OK` com body `{"ok": true, "mensagem": "Você está na lista..."}`; terceiro mostra 1 linha.

### Suite de testes

```bash
docker compose exec api pytest tests/test_waitlist_endpoint.py -q
# Esperado: 13 passed
```

### Payload completo (opcional, valida tudo de uma vez)

```bash
curl -i -X POST http://localhost:8000/api/v1/waitlist \
  -H "Content-Type: application/json" \
  -d '{
    "email": "consultor@example.com",
    "nome": "Maria Consultora",
    "telefone": "(11) 98765-4321",
    "perfil_profissional": "Consultor ambiental",
    "estado": "sp",
    "tipo_licenciamento": "LO + LP",
    "volume_mensal": 10,
    "ferramenta_atual": "Trello",
    "preco_aceito": {"barato_demais": 49, "barato": 99, "caro": 299, "caro_demais": 499},
    "expectativa": "Economizar tempo no diagnóstico inicial",
    "deal_breaker": "Preço acima de R$500/mês",
    "interesse_grupo": true,
    "consentimento": true,
    "utm_source": "instagram",
    "utm_campaign": "lancamento_beta"
  }'
```

### Rollback se algo der ruim

```bash
# Desfaz a migration desta sprint
docker compose exec api alembic downgrade -1

# Confirma que voltou para a head anterior (b9d2e5a8f4c1)
docker compose exec api alembic current
```

---

## 📂 Onde tudo vive

```
\\DESKTOP-L0VOP07\Users\Administrador\Desktop\Amigao_do_Meio_Ambiente\
├── RELATORIO_WAITLIST.md          ← Fase 0 (este doc complementa)
├── PROGRESSO_WAITLIST.md          ← VOCÊ ESTÁ AQUI
├── alembic/versions/
│   └── b1a2c3d4e5f6_sprint_b1_pre_cadastros.py    ← migration
├── app/
│   ├── api/v1/
│   │   └── waitlist.py            ← router POST /api/v1/waitlist
│   ├── models/
│   │   ├── pre_cadastro.py        ← ORM
│   │   └── __init__.py            ← registro do model
│   ├── schemas/
│   │   └── pre_cadastro.py        ← Pydantic v2
│   ├── services/
│   │   ├── resend_client.py       ← cliente HTTP Resend
│   │   └── email.py               ← SMTP antigo (intacto, coexiste)
│   ├── workers/
│   │   └── waitlist_tasks.py      ← Celery sync + welcome
│   ├── core/config.py             ← RESEND_* settings + validator
│   └── main.py                    ← router registrado
├── tests/
│   └── test_waitlist_endpoint.py  ← 13 testes
├── requirements.txt               ← +pytest-httpx, +pytest-celery
└── .env.example                   ← Resend block + CORS doc
```

---

**Boa noite. Amanhã a gente segue.**
