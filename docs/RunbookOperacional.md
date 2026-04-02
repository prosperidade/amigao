# Runbook Operacional

Documento vivo de operacao e homologacao. A cada passada relevante, este arquivo e `docs/progresso3.md` devem ser atualizados juntos.

Funcao deste arquivo:

- linguagem operacional e prescritiva
- foco em comando, validacao, pre-requisito, evidência e resposta operacional
- evitar narrativa historica longa; isso pertence ao `progresso3.md`

## Padrao de fechamento

Ao final de cada rodada:

1. registrar o que mudou em `docs/progresso3.md`
2. atualizar este runbook com:
   - estado operacional atual
   - comandos de validacao usados
   - riscos ou pendencias remanescentes
3. registrar testes executados e resultado
4. registrar qualquer workaround temporario ativo

## Credenciais seed locais

No ambiente local Docker, o seed agora sincroniza as senhas quando `SEED_*_PASSWORD` estiver definido.

Usuarios seed atuais do stack local:

- `admin@amigao.com`
- `consultor@amigao.com`
- `cliente@amigao.com`
- `campo@amigao.com`

Senha de homologacao local atual:

- `Seed@2026`

Variaveis relevantes:

- `SEED_ADMIN_PASSWORD`
- `SEED_CONSULTANT_PASSWORD`
- `SEED_CLIENT_PASSWORD`
- `SEED_FIELD_PASSWORD`
- `SEED_RESET_PASSWORDS`

Regra operacional:

- se `SEED_*_PASSWORD` estiver definido, o startup sincroniza a senha do usuario correspondente
- `SEED_RESET_PASSWORDS=true` continua forcando rotacao geral das senhas derivadas

## Provisionamento de tenant controlado

Para homologacoes reais sem interferir no tenant seed principal:

```powershell
.\venv\Scripts\python.exe ops\provision_homologation_tenant.py `
  --internal-email seu+interno@gmail.com `
  --portal-email seu+portal@gmail.com `
  --password Seed@2026
```

Resultado esperado:

- tenant isolado para homologacao
- usuario interno real para receber notificacoes
- usuario do portal vinculado ao cliente
- processo inicial em `triagem`

## Endpoints e servicos operacionais

- API: `http://localhost:8000`
- Health: `GET /health`
- Metrics: `GET /metrics`
- Portal do cliente: `http://localhost:3000/login`
- MinIO API: `http://localhost:9000`
- MinIO Console: `http://localhost:9001`

## Subida rapida para demonstracao

Stack principal:

```powershell
docker compose up --build -d api worker client-portal
```

Conferencia rapida:

```powershell
(Invoke-WebRequest -UseBasicParsing http://localhost:8000/health).StatusCode
```

```powershell
(Invoke-WebRequest -UseBasicParsing http://localhost:3000/login).StatusCode
```

## SMTP

Validacao de conectividade:

```powershell
.\venv\Scripts\python.exe ops\check_smtp.py
```

Estado atual:

- autenticacao SMTP real validada com sucesso
- `api` e `worker` ja rodam com SMTP real carregado via `.env`

## Webhook de alertas

Sink local para smoke:

```powershell
.\venv\Scripts\python.exe ops\alert_webhook_sink.py `
  --host 0.0.0.0 `
  --port 8011 `
  --auth-header Authorization `
  --auth-token "Bearer sink-local-token" `
  --signing-secret "sink-local-signing-secret"
```

Configuracao local:

- `ALERT_WEBHOOK_URL=http://host.docker.internal:8011/alerts`
- `ALERT_WEBHOOK_AUTH_HEADER=Authorization`
- `ALERT_WEBHOOK_AUTH_TOKEN=Bearer sink-local-token`
- `ALERT_WEBHOOK_SIGNING_SECRET=sink-local-signing-secret`
- `ALERT_WEBHOOK_MIN_SEVERITY=warning`

Validacao controlada:

```powershell
docker compose exec -T api python -c "from app.core.alerts import emit_operational_alert; emit_operational_alert(category='smoke_test', severity='warning', message='Webhook smoke test', metadata={'source':'api_container'})"
```

Artefato local:

- capturas do sink ficam em `ops/runtime/`
- `ops/runtime/` deve permanecer fora do Git
- cada captura agora registra `headers`, `validation`, `status_code` e `payload`

Contrato atual do webhook:

- payload inclui `alert_id`, `service`, `environment`, `request_id`, `trace_id`, `span_id`, `category`, `severity`, `message` e `metadata`
- headers incluem `X-Amigao-Alert-Id`, `X-Amigao-Service`, `X-Amigao-Environment` e `traceparent`
- quando configurado, o destino tambem recebe autenticacao no header definido por `ALERT_WEBHOOK_AUTH_HEADER`
- quando configurado, o corpo sai assinado em `X-Amigao-Signature-256` com HMAC SHA-256

## Smokes obrigatorios

### Smoke automatizado principal

Executar:

```powershell
.\venv\Scripts\python.exe ops\run_homologation_smoke.py `
  --internal-email seu+interno@gmail.com `
  --portal-email seu+portal@gmail.com `
  --password Seed@2026
```

Validacoes cobertas:

- `health`
- login interno
- login portal
- criacao de processo real
- mudanca de status com notificacao ao cliente
- upload real de documento no MinIO
- confirmacao de upload
- notificacao interna por e-mail
- auditoria de processo e documento
- metricas consolidadas no `/metrics`

### 1. Health e login

```powershell
(Invoke-WebRequest -UseBasicParsing http://localhost:8000/health).StatusCode
```

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/api/v1/auth/login' -Body @{ username='admin@amigao.com'; password='Seed@2026' } -ContentType 'application/x-www-form-urlencoded'
```

### 2. Mudanca real de status de processo

Objetivo:

- validar `notify_process_status_changed`
- validar email ao cliente
- validar auditoria
- validar metricas do worker

Sinais esperados:

- task `workers.notify_process_status_changed` com `success`
- `amigao_email_delivery_total{service="worker",result="success"}` incrementado
- timeline do processo contendo `created`, `status_changed` e `notification_process_status_changed`

### 3. Upload real de documento pelo portal

Objetivo:

- validar `upload-url -> PUT MinIO -> confirm-upload -> notify_document_uploaded`
- validar email interno
- validar auditoria
- validar metricas do worker e API

Sinais esperados:

- task `workers.notify_document_uploaded` com `success`
- auditoria com `notification_document_uploaded`
- `channels` contendo `realtime_tenant` e `email_internal`
- `amigao_document_uploads_total{service="api",source="client_portal",result="success"}`

## Ultima validacao registrada

Data de referencia:

- `29/03/2026`

Validado nesta rodada:

- login real de `admin@amigao.com` com `Seed@2026`
- login real de `cliente@amigao.com` com `Seed@2026`
- script `ops/provision_homologation_tenant.py` validado de forma idempotente no banco local
- script `ops/run_homologation_smoke.py` validado de ponta a ponta na stack local
- webhook local de alertas recebendo payload real da API
- evento real de mudanca de status com email ao cliente e auditoria confirmada
- evento real de upload de documento pelo portal com email interno e auditoria confirmada
- `/metrics` expondo series de `worker` para `notify_process_status_changed` e `notify_document_uploaded`
- timeline do processo real respondendo sem erro apos correcao de serializacao de `AuditLog`
- contrato do webhook endurecido com autenticacao por header configuravel, assinatura HMAC SHA-256 e `traceparent`
- `ops/alert_webhook_sink.py --help` validado com os novos parametros operacionais
- suite focada de observabilidade/configuracao validada apos o endurecimento do webhook
- `docker compose config` validado apos inclusao das novas variaveis de webhook
- `docker compose up --build -d api worker client-portal` executado com sucesso para preparar a demonstracao
- `GET /health` estabilizado em `200` apos o rebuild
- `http://localhost:3000/login` respondendo `200` apos o rebuild

Suite focada mais recente:

- `16 passed`

## Pendencias atuais

- substituir o sink local por destino externo real de webhook quando houver endpoint definitivo
- modularizar o seed atual se o repositorio realmente migrar para a estrutura `seed/main.py`
- revisar referencias antigas a credenciais seed em documentacao fora do runbook principal, se surgirem novas divergencias
