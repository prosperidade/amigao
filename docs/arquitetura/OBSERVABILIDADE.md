# Observabilidade

**Documento:** Arquitetura · referência viva
**Estado:** atualizar a cada nova métrica ou alerta
**Última revisão:** 2026-05-15

---

Logs, métricas, tracing e alertas do Regente Ambiental. O sistema é monitorável e previsível por design — qualquer pessoa de ops deve conseguir responder "está saudável?" e "onde dói?" em segundos.

## Logs

### Formato

- **Estruturado em JSON** em produção (LOG_FORMAT=json default em prod)
- **Texto colorido** em dev (LOG_FORMAT=text)
- Helper: `app.core.logging.get_logger(__name__)`

### Campos padrão (sempre presentes)

| Campo | Origem | Uso |
|---|---|---|
| `timestamp` | sistema | quando |
| `level` | logger | severidade |
| `logger` | módulo | onde |
| `message` | call site | o quê |
| `request_id` | middleware | correlaciona requisição HTTP |
| `tenant_id` | middleware | qual cliente |
| `user_id` | middleware | qual usuário |
| `trace_id` | middleware | rastreio distribuído |
| `span_id` | middleware | passo dentro do trace |

### Campos contextuais (quando aplicável)

| Campo | Aparece em |
|---|---|
| `agent_name` | logs de execução de agente IA |
| `ai_job_id` | logs do ciclo de vida de chamada LLM |
| `cost_usd` | logs de finalização de AIJob |
| `tokens_in` / `tokens_out` | idem |
| `model_used` | idem |
| `duration_ms` | logs de slow requests |
| `chain_trace_id` | logs de chains de agentes |

### Propagação entre processos

API e Worker propagam `trace_id` via:
- HTTP: header `traceparent`
- Celery: kwargs da task

Permite seguir uma requisição que entra no API → enfileira no Celery → executa no worker → emite evento WebSocket.

## Métricas Prometheus

### Endpoint

`GET /metrics` retorna formato Prometheus puro (text). Em produção, proteger por rede (não por auth — Prometheus não tem JWT).

### Métricas HTTP

| Métrica | Tipo | Labels |
|---|---|---|
| `amigao_http_requests_total` | Counter | `method`, `route`, `status` |
| `amigao_http_request_duration_seconds` | Histogram | `method`, `route` |
| `amigao_http_requests_in_progress` | Gauge | `method`, `route` |

### Métricas Celery

| Métrica | Tipo | Labels |
|---|---|---|
| `amigao_celery_tasks_total` | Counter | `task`, `status` |
| `amigao_celery_task_duration_seconds` | Histogram | `task` |
| `amigao_celery_queue_depth` | Gauge | `queue` |

Métricas de worker são persistidas em Redis (chave `amigao:metrics:worker`) para consolidação no `/metrics` do API.

### Métricas de IA

| Métrica | Tipo | Labels |
|---|---|---|
| `amigao_agent_executions_total` | Counter | `agent`, `status` |
| `amigao_agent_execution_duration_seconds` | Histogram | `agent` |
| `amigao_agent_execution_cost_usd` | Counter | `agent`, `provider`, `model` |
| `amigao_ai_summaries_total` | Counter | `status` |
| `amigao_ai_summary_duration_seconds` | Histogram | — |

### Métricas operacionais

| Métrica | Tipo | Labels |
|---|---|---|
| `amigao_alerts_total` | Counter | `category`, `severity` |
| `amigao_email_delivery_total` | Counter | `status` (sent, failed, skipped) |
| `amigao_realtime_events_total` | Counter | `event_type` |
| `amigao_websocket_connections` | Gauge | — |
| `amigao_document_uploads_total` | Counter | `status` |
| `amigao_task_transitions_total` | Counter | `from`, `to` |

> Prefixo `amigao_` é codinome técnico ([`../adr/004-regente-vs-amigao.md`](../adr/004-regente-vs-amigao.md)). Renomeação para `regente_*` quebra dashboards e alertas existentes — fica para sprint dedicada.

## Tracing distribuído

- Header: `traceparent` (W3C Trace Context)
- Geração: `RequestContextMiddleware` gera `trace_id` (UUID v4) se não existir, propaga adiante
- Span por dependência: criar span ao chamar DB, MinIO, LiteLLM, Celery
- Backend opcional: OpenTelemetry collector (configurável via env)

Em dev, o `trace_id` aparece em todo log e na resposta HTTP via header `X-Trace-Id`. Em produção, exportar para Jaeger/Tempo é o caminho recomendado.

## Slow requests

- Threshold default: `SLOW_REQUEST_THRESHOLD_MS = 500ms`
- Overrides por endpoint em `SLOW_REQUEST_THRESHOLD_OVERRIDES`:
  - `/api/v1/auth/login` → 2000ms (bcrypt é caro)
  - `/api/v1/documents/upload-url` → 800ms (presigned URL + verificação MinIO)
  - `/api/v1/documents/confirm-upload` → 900ms
- Toda requisição lenta → log `WARNING` com `request_duration_ms`

## Alertas operacionais

### Sistema de alertas

`app/core/alerts.py` emite alertas via webhook. Categorias atuais:

| Categoria | Quando dispara | Severidade default |
|---|---|---|
| `email_delivery` | Falha de envio (SMTP/Resend) | error |
| `ai_cost_exceeded` | Job bloqueado por cost cap | warning |
| `ai_budget_warning` | Tenant atingiu 80% do orçamento mensal | warning |
| `ai_budget_exhausted` | Tenant atingiu 100% do orçamento | error |
| `worker_task_failed` | Task Celery falhou após esgotar retries | error |
| `migration_pending` | Boot detecta migrations pendentes | critical |
| `provider_fallback` | Fallback de provider IA acionado | info |
| `database_health` | Health check de DB falhou | critical |

### Webhook

- `ALERT_WEBHOOK_URL` em `.env`
- Timeout: `ALERT_WEBHOOK_TIMEOUT_SECONDS=2.0` (não bloqueia request)
- Auth: header configurável (`ALERT_WEBHOOK_AUTH_HEADER` + `_TOKEN`)
- Assinatura HMAC: `ALERT_WEBHOOK_SIGNING_SECRET` (validação no destino)
- Filtro: `ALERT_WEBHOOK_MIN_SEVERITY` (default `error`)
- Sink local (debug): `ops/alert_webhook_sink.py` salva em `alert-webhook-capture.jsonl`

### Alertas Prometheus

`ops/prometheus-alerts.yml` define regras de alerta para Alertmanager:

```yaml
# Exemplo (real, ver arquivo)
- alert: APIHighErrorRate
  expr: rate(amigao_http_requests_total{status=~"5.."}[5m]) > 0.05
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "API com >5% de erros 5xx nos últimos 5min"
```

Adicionar nova regra: editar `prometheus-alerts.yml` + recarregar Prometheus.

## Health checks

### `/health`

Verifica:
- DB acessível (`SELECT 1`)
- Redis acessível (`PING`)
- MinIO acessível (verificação de bucket)

Retorna 200 + JSON com cada componente OK, ou 503 + JSON com componente falhando.

### Boot-time validations

`app/core/security.py:warm_up_security` valida no boot:
- `SECRET_KEY` ≥ 32 chars e não-default
- Em produção: SMTP configurado, RESEND_API_KEY presente
- Em dev: warning + skip

Falha bloqueia o start em produção (fail-fast). Em dev, loga e segue.

## Como investigar incidentes

### "API está lenta"

1. Olha `/metrics` para `http_request_duration_seconds` por route
2. Filtra route mais lenta
3. Grep logs por `request_duration_ms > 500` no período
4. Pega `request_id` ou `trace_id` de uma requisição lenta
5. Reconstrói toda a história: HTTP → DB queries → workers acionados
6. Identifica gargalo (query, IA, MinIO, etc.)

### "Cliente reclama que não recebeu e-mail"

1. Filtra logs por `tenant_id` e categoria `email_delivery`
2. Olha métrica `amigao_email_delivery_total{status="failed"}` e `="sent"`
3. Se Resend: olha `resend_message_id` no log → consulta dashboard Resend
4. Se SMTP: olha alertas operacionais do período

### "Agente está caro"

1. `GET /api/v1/agents/budget` para o tenant — mostra spent vs budget
2. `SELECT agent_name, SUM(cost_usd), COUNT(*) FROM ai_jobs WHERE tenant_id = X AND created_at > now() - interval '7 days' GROUP BY agent_name`
3. Identifica agente custoso
4. Olha distribuição: caso patológico (1 job gigante) ou volume alto?
5. Investiga prompt (PromptTemplate) e contexto (logs)

### "Algo quebrou em produção, não sei o quê"

1. `/health` → componente fora?
2. Métricas `amigao_alerts_total` → quais alertas dispararam?
3. Logs nas últimas 15min com `level >= ERROR`
4. `amigao_celery_tasks_total{status="failed"}` aumentou?
5. Se nada apareceu → bug silencioso (lateral). Olha métricas de negócio.

## Pendências e dívidas

1. **Métricas com prefixo `amigao_`** — codinome técnico, renomear quebra dashboards. Sprint dedicada futura.
2. **OpenTelemetry collector não configurado em prod** — tracing fica só nos logs hoje.
3. **Dashboards Grafana** — não há repositório de dashboards versionados. Ad-hoc por pessoa.
4. **Alertmanager rules** — só algumas regras hoje. Cobertura precisa aumentar.
5. **Log retention** — sem rotação automática formalizada para logs em prod.

## Próximas leituras

- [`../operacao/RUNBOOK_OPS.md`](../operacao/RUNBOOK_OPS.md) — runbook usando estas métricas
- [`../operacao/TROUBLESHOOTING.md`](../operacao/TROUBLESHOOTING.md) — playbooks de incidente
- [`GOVERNANCA_IA.md`](./GOVERNANCA_IA.md) — métricas de IA detalhadas
