# Plano Executivo — Execução do Dia

## Projeto: Amigão do Meio Ambiente
## Referência: Auditoria + Continuidade da Sprint 5

---

## Objetivo do dia

Fechar os riscos operacionais mais críticos do ambiente atual antes de abrir novas frentes funcionais, com foco em homologação integrada, segurança operacional mínima e consistência de banco de dados.

---

## Plano Executivo

### 1. Homologação integrada da stack
**Objetivo:** validar a operação fim a fim da aplicação em ambiente integrado.

**Escopo:**
- subir a stack completa com `docker compose up --build`
- validar comunicação entre `api`, `worker`, `db`, `redis`, `minio` e `client-portal`
- executar o fluxo principal do portal do cliente

**Entregáveis:**
- stack operacional sem falha crítica de inicialização
- checklist funcional executado
- registro dos erros reais encontrados na integração

**Critério de aceite:**
- portal autentica corretamente
- API responde sem erro nas rotas principais
- upload/download de documentos funciona
- mudança de status dispara automações esperadas
- PDF e notificações executam no fluxo integrado

### 2. Parametrização de produção e hardening mínimo
**Objetivo:** remover configurações inseguras e evitar falso positivo operacional.

**Escopo:**
- revisar `SECRET_KEY`, SMTP e domínios finais
- definir variáveis obrigatórias por ambiente
- garantir comportamento fail-fast para produção

**Entregáveis:**
- mapa de variáveis críticas do ambiente
- configuração separada para `dev` e `prod`
- erro explícito para segredo crítico ausente ou inválido

**Critério de aceite:**
- produção não opera com `SECRET_KEY` insegura
- SMTP inválido não retorna sucesso falso
- URLs principais do portal e da API ficam parametrizadas

### 3. Consistência de banco e migrations
**Objetivo:** eliminar risco de drift de schema entre ambientes.

**Escopo:**
- confirmar Alembic como estratégia única de schema
- revisar `init_db` e remover dependência indevida de `create_all` fora de teste
- validar fluxo de bootstrap e atualização do banco

**Entregáveis:**
- estratégia única de schema formalizada
- setup de banco revisado
- fluxo de migration validado por smoke test

**Critério de aceite:**
- schema sobe por migrations versionadas
- não existe caminho paralelo conflitante para criação de estrutura
- setup fica reproduzível entre ambientes

---

## Sequência de Execução

### Etapa 1 — Homologação integrada
1. Validar arquivos de ambiente e pré-requisitos da stack.
2. Subir os serviços com `docker compose up --build`.
3. Confirmar saúde dos containers principais.
4. Testar autenticação do portal do cliente.
5. Testar listagem de processos, timeline e documentos.
6. Validar upload, download, mudança de status e geração de PDF.
7. Registrar falhas reais encontradas na integração.

### Etapa 2 — Correção de configuração e segurança mínima
1. Revisar defaults sensíveis no backend.
2. Parametrizar `SECRET_KEY`, SMTP e domínios do portal/API.
3. Ajustar validações para falhar explicitamente em produção.
4. Revisar o comportamento do serviço de e-mail para impedir sucesso simulado indevido.
5. Reexecutar a subida da stack após os ajustes.

### Etapa 3 — Banco e migrations
1. Inspecionar o uso atual de Alembic e `init_db`.
2. Identificar pontos em que `create_all` pode conflitar com migrations.
3. Consolidar a estratégia oficial de bootstrap do banco.
4. Validar `upgrade` da migration em ambiente limpo.
5. Registrar pendências ou correções adicionais de schema.

### Etapa 4 — Fechamento do dia
1. Reexecutar o checklist funcional principal.
2. Atualizar o status do progresso com os resultados reais.
3. Separar o que foi concluído, o que foi corrigido e o que ficou pendente.
4. Preparar a próxima frente: observabilidade e integridade de regras de negócio.

---

## Resultado esperado ao final do dia

- stack integrada validada
- configuração crítica revisada
- riscos imediatos de produção reduzidos
- estratégia de banco mais consistente
- base pronta para a próxima frente de observabilidade e endurecimento operacional

---

## Execução realizada em 29/03/2026

### Itens validados
- `docker compose up --build -d` executado com sucesso para `api`, `worker`, `db`, `redis`, `minio` e `client-portal`
- `GET /health` retornando `200` na API
- `http://localhost:3000/login` respondendo `200` no portal
- autenticação real do cliente validada com `cliente@amigao.com`
- listagem de processos do portal validada com escopo por `client_id`
- fluxo documental fim a fim validado: presigned upload, `PUT` no MinIO, confirmação no backend e URL de download
- worker consumindo a task `workers.notify_document_uploaded` com sucesso

### Correções aplicadas durante a execução
- `docker-compose.yml` passou a consumir variáveis de ambiente em vez de segredos hard-coded
- bootstrap da API alinhado com `python -m app.db.init_db` como fluxo oficial de schema
- `app/core/config.py` endurecido para produção:
  - `SECRET_KEY` mínima de 32 caracteres
  - bloqueio de chave insegura
  - bloqueio de credenciais default do MinIO
  - bloqueio de URLs locais em produção
  - exigência de SMTP configurado em produção
- `app/services/storage.py` corrigido para usar endpoint interno do MinIO no backend e endpoint público nas URLs assinadas
- imagem base da API/worker ajustada para rodar com usuário não privilegiado

### Bug real encontrado e corrigido
- as URLs assinadas de upload/download estavam sendo geradas com host interno `minio:9000`
- isso quebrava o upload real no navegador/host, embora o backend ainda confirmasse o documento
- a correção introduziu `MINIO_PUBLIC_URL` para emissão de URLs públicas acessíveis fora da rede Docker

### Validações executadas
- `.\venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\test_settings.py tests\test_storage_service.py -q` -> `9 passed`
- `docker compose config` -> configuração resolvida sem erros
- `docker compose up --build -d` -> stack integrada operacional
- upload real homologado via URL assinada com `PUT 200` no MinIO

### Pendências que seguem abertas
- parametrizar SMTP real de produção para substituir o modo sem envio em `development`
- evoluir a frente de observabilidade com alertas e métricas de operação mais acionáveis

---

## Execução complementar em 29/03/2026

### SMTP e segredos de produção
- criado o template [`.env.production.example`](/c:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/.env.production.example) com os valores obrigatórios para produção
- criado o checklist operacional [`ops/production-secrets-checklist.md`](/c:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/ops/production-secrets-checklist.md)
- `app/core/config.py` endurecido para exigir também `EMAILS_FROM_NAME` válido em produção
- suíte local atualizada e validada com `10 passed`

### Smoke de migrations
- smoke executado em banco temporário `amigao_migration_smoke`
- ciclo validado com sucesso:
  - `upgrade head`
  - `downgrade base`
  - `upgrade head`

### Bugs reais encontrados e corrigidos no fluxo de migrations
- `e91d20acba9c` não garantia `CREATE EXTENSION IF NOT EXISTS postgis` antes da coluna `geometry`
- `d7515c8f0c3b` tinha `downgrade()` vazio e não removia `tasks` nem enums associados
- `afcea9834c04` tinha `downgrade()` vazio e não revertia colunas, tabela `properties` e enum `processstatus`
- `b69a429faaa4` não removia o enum `processstatus` ao voltar para a revisão anterior

### Situação atual após a sequência
- frente de produção: template e validações prontos, faltando apenas preencher credenciais reais fora do repositório
- frente de migrations: smoke fechado com rollback e reaplicação bem-sucedidos
- próximas pendências concentradas em latência, SMTP real e observabilidade

---

## Execução complementar 2 em 29/03/2026

### Latência operacional
- cacheado o `StorageService` para reuso no processo
- removido o `head_bucket` redundante em toda requisição após a primeira inicialização
- adicionado warm-up de runtime no startup da API para:
  - conexão simples com banco
  - aquecimento de `bcrypt`/JWT
  - inicialização do storage
- criado threshold de latência por rota em `app/core/config.py`
- login passou a usar lookup indexado por e-mail antes do fallback normalizado

### Resultado medido após os ajustes
- primeiro `POST /api/v1/auth/login` após restart: `1208,64 ms`
- primeiro `POST /api/v1/documents/upload-url` após restart: `54,09 ms`
- leitura final dos logs:
  - `POST /api/v1/auth/login` concluído em `704,34 ms`
  - `POST /api/v1/documents/upload-url` concluído em `42,58 ms`
  - sem alerta `operational.alert` remanescente nessas rotas após os ajustes finais

### SMTP
- criado o script `ops/check_smtp.py` para validar autenticação SMTP real sem disparar e-mail
- `EmailService` ganhou `check_connection()`
- ambiente atual continua sem credenciais SMTP reais configuradas
- execução local do check retornou: `SMTP não configurado no ambiente atual.`

### Pendência objetiva para fechar SMTP real
- preencher no ambiente real:
  - `SMTP_HOST`
  - `SMTP_USER`
  - `SMTP_PASSWORD`
  - `EMAILS_FROM_EMAIL`
  - `EMAILS_FROM_NAME`
- após preencher, rodar `python ops/check_smtp.py`

---

## Execução complementar 3 em 29/03/2026

### SMTP real homologado
- `.env` local ignorado pelo Git atualizado para usar SMTP Gmail com TLS na porta `587`
- remetente alinhado com a conta autenticada para evitar rejeição de envio por política do provedor
- `ops/check_smtp.py` executado com sucesso contra o servidor real

### Aplicação da configuração na stack
- `docker compose up -d api worker` executado para recarregar as variáveis de ambiente
- `api` e `worker` recriados sem erro
- `GET /health` validado com `200` após estabilização do restart

### Situação atual
- autenticação SMTP real validada
- stack integrada em execução com a configuração nova carregada
- próxima frente natural: observabilidade operacional e teste funcional de envio real de notificação por e-mail

---

## Execução complementar 4 em 29/03/2026

### Gap de observabilidade corrigido
- corrigido o problema em que métricas do worker ficavam apenas em memória no processo Celery e não apareciam no endpoint `/metrics` da API
- worker passou a persistir em Redis as séries de:
  - tasks Celery por estado
  - duração de tasks Celery
  - entregas de e-mail
  - alertas operacionais emitidos pelo worker
- API passou a consolidar essas séries compartilhadas no scrape Prometheus

### Validação técnica
- suíte focada executada com sucesso: `16 passed`
- `docker compose up --build -d api worker` executado sem erro
- `GET /health` validado com `200` após estabilização do restart
- endpoint `/metrics` passou a expor amostras `service="worker"` para:
  - `amigao_celery_tasks_total`
  - `amigao_celery_task_duration_seconds`
  - `amigao_email_delivery_total`

### Teste funcional real de e-mail
- disparo real executado via task `workers.send_email_notification`
- retorno da task: `{'status': 'success', 'to': 'vovoprogramador2024@gmail.com'}`
- logs do worker confirmaram:
  - recebimento da task
  - envio SMTP com sucesso
  - conclusão da task em aproximadamente `4,33s`

### Situação atual
- SMTP real homologado em fluxo assíncrono
- observabilidade do worker consolidada no `/metrics`
- próxima frente natural: webhook externo de alertas e teste funcional por evento de negócio real (`status change` ou `document upload`)

---

## Execução complementar 5 em 29/03/2026

### Webhook externo de alertas homologado
- criado o helper operacional `ops/alert_webhook_sink.py` para capturar webhooks localmente em JSONL
- `docker-compose.yml` ajustado para repassar a `api` e `worker` as variáveis:
  - `LOG_LEVEL`
  - `SLOW_REQUEST_THRESHOLD_MS`
  - `SLOW_REQUEST_THRESHOLD_OVERRIDES`
  - `ALERT_WEBHOOK_URL`
  - `ALERT_WEBHOOK_TIMEOUT_SECONDS`
  - `ALERT_WEBHOOK_MIN_SEVERITY`
  - `PROMETHEUS_QUEUE_NAMES`
- exemplos `.env.example` e `.env.production.example` alinhados com essas variáveis
- smoke executado com sink local em `http://host.docker.internal:8011/alerts`
- alerta controlado emitido de dentro do container da API e recebido com sucesso pelo sink

### Evento de negócio real homologado
- criado cliente real de homologação com e-mail `vovoprogramador2024@gmail.com`
- criado processo real de homologação e transição validada de `lead` para `triagem`
- worker consumiu `workers.notify_process_status_changed` com sucesso
- e-mail real de atualização de status enviado com sucesso para o cliente
- auditoria de notificação registrada com canais:
  - `email`
  - `realtime_tenant`
  - `realtime_client`
- `/metrics` confirmou:
  - `amigao_celery_tasks_total{service="worker",task_name="workers.notify_process_status_changed",state="success"} 1.0`
  - `amigao_email_delivery_total{service="worker",result="success"} 2.0`

### Bug real descoberto no fluxo e corrigido
- `GET /api/v1/processes/{id}/timeline` falhava com `500` por ausência de schema serializável para `AuditLog`
- corrigido com schema explícito de leitura em `app/schemas/audit_log.py`
- endpoint passou a responder timeline completa do processo real com:
  - `created`
  - `status_changed`
  - `notification_process_status_changed`
- cobertura adicionada em `tests/api/test_processes.py`

### Validação da rodada
- `docker compose config` válido
- `11 passed` em `tests/test_settings.py` e `tests/api/test_observability.py`
- `8 passed` em `tests/api/test_processes.py` e `tests/api/test_observability.py`
- `GET /health` retornando `200`
- timeline real do processo `14` respondendo com `3` eventos após a correção

### Higiene operacional
- `.gitignore` atualizado para ignorar `ops/runtime/` e evitar versionamento acidental das capturas locais do webhook sink
