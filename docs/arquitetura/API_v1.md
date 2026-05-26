# API v1

**Documento:** Arquitetura · referência viva
**Estado:** atualizar a cada novo router ou mudança de contrato
**Última revisão:** 2026-05-15
**Verificado em:** `app/main.py:134-161` (28 routers + WebSocket)

---

Superfície REST do Regente Ambiental. Para spec interativa com schemas, abra `http://localhost:8000/docs` (OpenAPI). Este documento explica padrões, autenticação, organização — não substitui o OpenAPI.

## Convenções globais

- **Prefixo:** `/api/v1` (configurável via `API_V1_STR`). Único endpoint sem prefixo é infraestrutura: `/`, `/health`, `/metrics`.
- **Autenticação:** JWT Bearer no header `Authorization`. Login retorna `access_token`.
- **Perfil:** header `X-Auth-Profile: internal` ou `X-Auth-Profile: client_portal` (define qual `get_current_*_user` valida o token).
- **Tenant:** isolamento por `tenant_id` extraído do JWT. Não há header `X-Tenant-Id` (anti-padrão — tenant vem do token, sempre).
- **Formato:** JSON. Pydantic v2 valida request/response.
- **Erros:** `{"detail": "..."}` padrão FastAPI. Códigos: 400, 401, 403, 404, 409, 422, 429, 500.
- **Versionamento:** versão major por prefixo (`/api/v1`, `/api/v2` no futuro). Estratégia em [`../adr/`](../adr/) (a formalizar).

## Mapa de routers (28)

| Tag (OpenAPI) | Prefixo | Arquivo | Resumo |
|---|---|---|---|
| Autenticação | `/api/v1/auth` | `app/api/v1/auth.py` | Login (2 perfis), refresh, signup interno |
| Clientes | `/api/v1/clients` | `app/api/v1/clients.py` | CRUD de cliente + Cliente Hub |
| Processos | `/api/v1/processes` | `app/api/v1/processes.py` | CRUD de processo + transições de estado |
| Documentos | `/api/v1/documents` | `app/api/v1/documents.py` | Upload presigned, confirmação, listagem, OCR async |
| Propriedades | `/api/v1/properties` | `app/api/v1/properties.py` | CRUD de imóvel + Imóvel Hub |
| Tarefas | `/api/v1/tasks` | `app/api/v1/tasks.py` | CRUD + Kanban + transições |
| Comunicação | `/api/v1/threads` | `app/api/v1/threads.py` | Threads, mensagens, anexos |
| Intake | `/api/v1/intake` | `app/api/v1/intake.py` | Wizard de 5 passos, drafts, commit, import documental |
| Intake Feedback | `/api/v1/processes/{id}/classify` + `/admin/intake-feedback` | `app/api/v1/intake_feedback.py` | Promoção de `demand_type` + métricas de divergência |
| Checklists | `/api/v1/processes` | `app/api/v1/checklists.py` | Checklist documental por processo |
| Trilha Regulatória | `/api/v1/workflows` + `/api/v1/processes` | `app/api/v1/workflows.py` | Workflow templates, gates de macroetapa |
| Dossiê | `/api/v1/processes` | `app/api/v1/dossier.py` | Dossier técnico do caso |
| Decisões | `/api/v1/processes` | `app/api/v1/decisions.py` | Process decisions (mudança de rota regulatória) |
| Diagnóstico Regulatório | `/api/v1/processes` + `/api/v1/properties` | `app/api/v1/regulatory.py` | `RegulatoryDiagnosis` + `RegulatoryIssue` (sprint A1) |
| Propostas | `/api/v1/proposals` | `app/api/v1/proposals.py` | Geração de proposta + revisão + aceite |
| Contratos | `/api/v1/contracts` | `app/api/v1/contracts.py` | Geração de contrato + assinatura + versionamento |
| IA | `/api/v1` | `app/api/v1/ai.py` | classify, extract, jobs list/get/status (síncrono + async) |
| Agentes IA | `/api/v1/agents` | `app/api/v1/agents.py` | Listar agentes, executar agente isolado, ver orçamento |
| Dashboard | `/api/v1/dashboard` | `app/api/v1/dashboard.py` | Métricas operacionais para o painel |
| Base Legislativa | `/api/v1/legislation` | `app/api/v1/legislation.py` | Listar diplomas, buscar |
| Alertas Legislativos | `/api/v1/legislation` | `app/api/v1/legislation_alerts.py` | CRUD de alertas, ack |
| Knowledge Catalog (RAG) | `/api/v1/knowledge` | `app/api/v1/knowledge.py` | `GET /search`, `POST /index`, `POST /reindex-legislation` |
| Waitlist (Regente) | `/api/v1/waitlist` | `app/api/v1/waitlist.py` | `POST /` público (lead anônimo, rate-limited) |
| Tempo Real | (raiz) | `app/api/websockets.py` | WebSocket router para eventos do tenant |
| Admin / Métricas | `/api/v1/admin` | `app/api/v1/intake_feedback.py` | Estatísticas tenant-scoped |

## Autenticação em detalhe

### Login (`POST /api/v1/auth/login`)

Recebe:
```
POST /api/v1/auth/login
X-Auth-Profile: internal
Content-Type: application/x-www-form-urlencoded

username=consultor@regenteambiental.com.br&password=...
```

(Form-data porque é compatível com OAuth2PasswordBearer do FastAPI.)

Responde:
```json
{
  "access_token": "<JWT>",
  "token_type": "bearer",
  "expires_in": 86400
}
```

JWT contém:
- `sub` (user_id, str)
- `tenant_id` (int)
- `profile` ("internal" | "client_portal")
- `client_id` (apenas quando profile = client_portal)
- `exp` (timestamp)

### Guardas

| Guarda | Aceita | Rejeita |
|---|---|---|
| `get_current_user` | qualquer token válido | token inválido/expirado (401) |
| `get_current_internal_user` | profile = internal | profile = client_portal (403) |
| `get_current_portal_user` | profile = client_portal | profile = internal (403) |
| `get_current_active_user` | usuário com `is_active = true` | desativado (403) |
| `require_superuser` | `is_superuser = true` | comum (403) |

Tenant guard implícito: toda dependency que devolve usuário também exige que `tenant_id` do JWT exista. Tentativa de manipular entidade de outro tenant retorna 403 em deep check no service layer.

## Rate limiting

- Implementação: `slowapi` (`app/core/rate_limit.py`)
- Estratégia: per-IP por padrão
- Endpoints com limites específicos:
  - `POST /api/v1/auth/login` — limite documentado em `.env.example` (recomendado em produção)
  - `POST /api/v1/waitlist` — `10/min` por IP
- Resposta quando excede: `429 Too Many Requests`

## Padrões REST aplicados

### Idempotência

`POST` de criação **não é** garantidamente idempotente. Quando idempotência importa (signup, waitlist), o endpoint usa estratégia explícita:

- `POST /api/v1/waitlist` — segundo POST com mesmo email retorna 200 com o lead existente (não 409, decisão de produto registrada no `RELATORIO_WAITLIST.md`).

### Soft delete

Endpoints de DELETE em tabelas críticas (`Process`, `Client`, `Document`) fazem soft delete (`deleted_at`). Restauração via endpoint específico de undo onde aplicável.

### Paginação

Listagens usam query params `?skip=0&limit=100` (FastAPI default). Soma máxima `limit=200`. Endpoints com volume relevante (logs, ai_jobs, knowledge_catalog) limitam `limit` ainda mais.

### Listagem com filtro

Convenção: query string aceita filtros simples (`?status=execucao&demand_type=car`). Filtros complexos (full-text, semântico) usam endpoint dedicado (`GET /knowledge/search`).

### Endpoints regulatórios (`/processes/{id}/diagnoses`, `/properties/{id}/issues`)

`app/api/v1/regulatory.py` — versionamento de `RegulatoryDiagnosis` por processo +
assinatura humana.

| Endpoint | Função |
|---|---|
| `GET   /api/v1/processes/{id}/diagnoses` | Lista versões do `RegulatoryDiagnosis`, mais nova primeiro |
| `GET   /api/v1/processes/{id}/diagnoses/{version}` | Versão específica |
| `POST  /api/v1/processes/{id}/diagnoses` | Cria versão nova (gate Pydantic↔JSONB via `validate_diagnostic_content`) — 422 se `content` não respeita `DiagnosticoPreliminarContent`. Versão é `MAX(version)+1` server-side. |
| `PATCH /api/v1/processes/{id}/diagnoses/{version}/validate` | **Camada 1 + 2 do Princípio 1.** Grava `validated_by_user_id` + `validated_at` + AuditLog hash chain. **409** se já validada. **422** (PROMPT_6) com lista de `alertas_pendentes` se houver `RegulatoryIssue` com `severity=critico` + `decisao_consultor IS NULL` + `resolved_at IS NULL` no imóvel do processo. Críticas RESOLVIDAS e não-críticas não bloqueiam. Quando 422 rejeita, NADA é gravado (`validated_*` continua None). |
| `GET   /api/v1/properties/{id}/issues?status=open\|resolved\|all` | Lista `RegulatoryIssue` do imóvel |
| `PATCH /api/v1/properties/{prop_id}/issues/{issue_id}` | **PROMPT_6 — consultor edita os 3 status + decisão.** Body parcial via `RegulatoryIssueUpdate` (`extra="forbid"`): `status_achado`, `decisao_consultor`, `decisao_consultor_justificativa`, `status_saneamento`. **AuditLog granular por campo** (`<campo>_changed`) com hash chain SHA-256. Mesmo valor (no-op por campo) NÃO gera AuditLog. `decisao_consultor_at` é gerenciado server-side em qualquer mudança de `decisao_consultor`. 404 se issue não pertence à property/tenant. |

**Princípio 1 fechado em 2 camadas:**
- **Camada 1** (PROMPT_4 Onda B): consultor assina o `RegulatoryDiagnosis` como um todo via `PATCH /validate`.
- **Camada 2** (PROMPT_6): o gate de `PATCH /validate` exige `decisao_consultor` preenchido em **toda** issue crítica do imóvel. Os 5 valores do enum (`corrigir_antes` / `seguir_com_ressalva` / `solicitar_doc` / `fora_escopo` / `ignorar_justificado`) são **todos** decisões válidas que liberam o gate — o princípio é "obrigar a decidir", não "obrigar a corrigir" (radar-não-cancela preservado).

#### Shape do 422 do gate (camada 2)

```json
{
  "detail": {
    "message": "3 alerta(s) crítico(s) sem decisão do consultor — camada 2 do Princípio 1 exige decisão alerta por alerta antes da assinatura do diagnóstico",
    "alertas_pendentes": [
      {"id": 42, "codigo_alerta": "GEO_AUSENTE", "familia": "geo_incra", "severity": "critico"},
      {"id": 43, "codigo_alerta": "EMBARGO_NAO_INFORMADO", "familia": "restricao_risco", "severity": "critico"},
      {"id": 44, "codigo_alerta": "RL_CAR_X_REALIDADE", "familia": "ambiental", "severity": "critico"}
    ]
  }
}
```

A UI consome esse shape para mostrar cada alerta pendente e levar o consultor à tela de decisão.

### Webhooks / async

Endpoints assíncronos que dependem de Celery retornam 202 com `job_id`:

```json
POST /api/v1/ai/classify-async
→ 202 Accepted
{
  "job_id": 187,
  "status": "queued",
  "poll_url": "/api/v1/ai/jobs/187"
}
```

Cliente faz polling em `GET /api/v1/ai/jobs/{job_id}` ou recebe via WebSocket (`event_type = "ai_job_completed"`).

## Endpoints de IA detalhados

### Síncronos (`/api/v1/ai/...`)

| Endpoint | Função |
|---|---|
| `POST /api/v1/ai/classify` | Classifica demanda a partir de texto |
| `POST /api/v1/ai/extract` | Extrai campos de documento (passa `document_id`) |

### Assíncronos (mesma família + `-async`)

| Endpoint | Função |
|---|---|
| `POST /api/v1/ai/classify-async` | Mesma classificação, retorna `job_id` |
| `POST /api/v1/ai/extract-async` | Idem extração |

### Jobs

| Endpoint | Função |
|---|---|
| `GET /api/v1/ai/jobs` | Lista AI Jobs do tenant (paginação, filtro por agente/status) |
| `GET /api/v1/ai/jobs/{id}` | Detalhe de um job |
| `GET /api/v1/ai/jobs/{id}/status` | Polling leve (só status + progress) |

### Agentes individuais

| Endpoint | Função |
|---|---|
| `GET /api/v1/agents` | Lista os 10 agentes registrados |
| `POST /api/v1/agents/{name}/run` | Executa agente específico com metadata |
| `GET /api/v1/agents/budget` | Orçamento mensal de IA do tenant (Sprint R) |

## WebSocket

- Endpoint: `ws://localhost:8000/ws?token=<JWT>`
- Autenticação: token JWT na query string (não cabe header em WebSocket nativo do browser)
- Canais: por `tenant_id` (via Redis pubsub no canal `amigao_events`)
- Eventos emitidos:
  - `ai_job_completed` — quando um job assíncrono termina
  - `process_status_changed` — quando processo muda de estado
  - `task_assigned` — quando tarefa é atribuída
  - `document_processed` — quando OCR + extração terminam
  - `notification` — notificação genérica do tenant

## Headers de resposta importantes

| Header | Significado |
|---|---|
| `X-Trace-Id` | ID propagado por toda a requisição. Usar em troubleshooting. |
| `X-Request-Duration-Ms` | Latência da requisição (debug). |
| `X-RateLimit-Remaining` | Quantas requisições restam na janela atual (quando rate limit ativo). |
| Headers de segurança | `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`, etc. (via `SecurityHeadersMiddleware`). |

## Endpoints públicos (sem auth)

| Endpoint | Função |
|---|---|
| `GET /` | Identidade da API |
| `GET /health` | Health check (200 OK quando saudável) |
| `GET /metrics` | Métricas Prometheus (proteger por rede no prod, não por auth) |
| `POST /api/v1/waitlist` | Lead anônimo (rate-limited 10/min) |

Nenhum outro endpoint é público. Todos os demais exigem JWT válido.

## Pendências e dívidas

1. **Documentar estratégia de versionamento como ADR formal.** Hoje apenas mencionado em docs antigos.
2. **Padronizar paginação** — alguns endpoints usam `skip/limit`, outros não paginam. Auditar.
3. **OpenAPI tags inconsistentes** — alguns prefixos repetem (`/api/v1/processes` aparece em 7 routers diferentes). Funciona, mas dificulta navegação no `/docs`. Avaliar consolidação em sprint dedicada.
4. **CORS** — em `BACKEND_CORS_ORIGINS` no `.env.example`. Em prod, incluir `https://regenteambiental.com.br` e `https://www.regenteambiental.com.br`.
5. **Swagger desabilitado em prod** — checklist em `ops/production-secrets-checklist.md` exige `ENVIRONMENT=production` resultar em `/docs` desabilitado.

## Próximas leituras

- [`GOVERNANCA_IA.md`](./GOVERNANCA_IA.md) — política aplicada nos endpoints de IA
- [`OBSERVABILIDADE.md`](./OBSERVABILIDADE.md) — trace_id e métricas
- [`MULTITENANT_LGPD.md`](./MULTITENANT_LGPD.md) — isolamento aplicado na camada API
