# Observabilidade Operacional

## O que foi entregue

- Logs estruturados em JSON com `request_id`, `tenant_id`, `user_id`, `trace_id` e `span_id`
- Endpoint `/metrics` em formato Prometheus
- Propagacao de tracing via `traceparent` entre API e worker
- Alertas operacionais com contador Prometheus e envio opcional para webhook
- Regras de alerta Prometheus em `ops/prometheus-alerts.yml`

## Variaveis de ambiente

- `SERVICE_NAME`: nome do servico exportado nas metricas
- `LOG_LEVEL`: nivel de log
- `SLOW_REQUEST_THRESHOLD_MS`: limite de latencia para alerta
- `PROMETHEUS_QUEUE_NAMES`: filas Celery monitoradas, separadas por virgula
- `ALERT_WEBHOOK_URL`: webhook opcional para alertas
- `ALERT_WEBHOOK_MIN_SEVERITY`: severidade minima enviada ao webhook
- `ALERT_WEBHOOK_TIMEOUT_SECONDS`: timeout do webhook

## SLOs minimos sugeridos

- API disponibilidade: erro 5xx abaixo de 5% em 5 minutos
- API latencia: p95 abaixo de 800ms em 5 minutos
- Worker confiabilidade: zero falhas repetidas em 10 minutos
- Worker fila: backlog abaixo de 20 itens por 10 minutos
- Upload: zero falhas de confirmacao em 15 minutos

## Consultas Prometheus

```promql
sum(rate(amigao_http_requests_total{service="api"}[5m]))
```

```promql
histogram_quantile(0.95, sum(rate(amigao_http_request_duration_seconds_bucket{service="api"}[5m])) by (le))
```

```promql
sum(rate(amigao_celery_tasks_total{service="worker",state="failure"}[10m]))
```

```promql
max(amigao_celery_queue_depth{service="worker"})
```

```promql
increase(amigao_document_uploads_total{result="failed"}[15m])
```

## Painel minimo

- API requests por status
- API latencia p50/p95
- Requests em andamento
- Tasks Celery por estado
- Duracao de tasks Celery
- Profundidade da fila Celery
- Uploads de documento por resultado
- Alertas operacionais por categoria e severidade
