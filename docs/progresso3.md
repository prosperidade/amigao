# Plano Executivo — Execução do Dia

Padrão deste arquivo:

- linguagem executiva e de histórico de execução
- foco em resultado, decisão, validação, risco e pendência
- evitar instruções operacionais detalhadas; isso pertence ao `RunbookOperacional.md`

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

---

## Execução complementar 6 em 29/03/2026

### Credenciais seed determinísticas
- `seed.py` ajustado para sincronizar senha de usuários seed quando `SEED_*_PASSWORD` estiver definido
- `docker-compose.yml` ajustado para repassar `SEED_ADMIN_PASSWORD`, `SEED_CONSULTANT_PASSWORD`, `SEED_CLIENT_PASSWORD`, `SEED_FIELD_PASSWORD` e `SEED_RESET_PASSWORDS` para a API
- `.env.example` alinhado com senha seed local de homologação `Seed@2026`
- `.env` local atualizado para usar credenciais seed explícitas
- API recriada e logins reais validados com sucesso para:
  - `admin@amigao.com`
  - `cliente@amigao.com`

### Fluxo real de documentos homologado
- criado tenant controlado `Homologacao Documentos SMTP`
- provisionado usuário interno com alias Gmail para receber notificação interna real
- provisionado usuário do portal com alias Gmail distinto e cliente vinculado ao mesmo tenant
- fluxo validado de ponta a ponta:
  - login portal
  - `POST /api/v1/documents/upload-url`
  - `PUT` real no MinIO
  - `POST /api/v1/documents/confirm-upload`
  - consumo da task `workers.notify_document_uploaded`
  - envio de e-mail interno real com sucesso

### Evidências da homologação do fluxo de documentos
- documento real confirmado com `document_id=4` no `process_id=15`
- logs do worker confirmaram:
  - recebimento de `workers.notify_document_uploaded`
  - `Email enviado com sucesso para vovoprogramador2024+interno@gmail.com`
  - task concluída com `channels=['realtime_tenant', 'email_internal']`
- auditoria do documento gravada com:
  - `uploaded`
  - `notification_document_uploaded`
- `/metrics` confirmou:
  - `amigao_celery_tasks_total{service="worker",task_name="workers.notify_document_uploaded",state="success"} 1.0`
  - `amigao_document_uploads_total{service="api",source="client_portal",result="success"} 1.0`
  - `amigao_email_delivery_total{service="worker",result="success"} 3.0`

### Runbook operacional formalizado
- criado `docs/RunbookOperacional.md` como documento vivo de operacao
- a partir desta rodada, `RunbookOperacional.md` e `progresso3.md` passam a ser atualizados juntos ao final de cada passada relevante

### Validação da rodada
- `11 passed` em `tests/test_seed.py` e `tests/test_settings.py`
- `25 passed` na suíte focada de seed, settings, storage, SMTP, observability, processes e documents
- `docker compose config` válido
- `GET /health` retornando `200`

---

## Execução complementar 7 em 29/03/2026

### Seed e documentação alinhados
- `docs/SeedDadosDev.md` atualizado para refletir o estado realmente implementado no repositório
- removido o descompasso entre documentação aspiracional (`seed/main.py`, usuários `@seed.dev`) e a implementação real atual
- documentado que o seed suportado hoje é:
  - `python seed.py`
  - startup da `api` no `docker compose`
  - sincronização opcional via `SEED_*_PASSWORD`

### Provisionamento operacional repetível
- criado `ops/provision_homologation_tenant.py` para provisionar tenant controlado de homologação com:
  - usuário interno real
  - usuário do portal
  - cliente vinculado
  - processo inicial em `triagem`
- script validado com `--help` e execução real idempotente no banco local
- execução validada retornou:
  - `tenant_id=3`
  - `client_id=7`
  - `process_id=15`

### Runbook consolidado
- `docs/RunbookOperacional.md` atualizado para incluir:
  - comando oficial de provisionamento do tenant controlado
  - validação do script operacional
  - remoção da pendência antiga sobre alinhamento do seed

### Situação atual
- seed local, runbook e documentação operacional estão coerentes entre si
- homologações reais de processo e documentos agora podem ser repetidas sem depender de comandos manuais ad hoc

---

## Execução complementar 8 em 29/03/2026

### Padrão documental consolidado
- `progresso3.md` passou a explicitar linguagem de histórico executivo
- `RunbookOperacional.md` passou a explicitar linguagem operacional e prescritiva
- a separação de função entre os dois documentos ficou formalizada no próprio conteúdo

### Smoke operacional automatizado
- criado `ops/run_homologation_smoke.py` para automatizar o smoke real fim a fim da stack
- o script cobre em uma execução:
  - `health`
  - login interno e portal
  - criação de processo real
  - mudança de status com notificação ao cliente
  - upload real de documento no MinIO
  - confirmação de upload
  - notificação interna por e-mail
  - auditoria de processo e documento
  - leitura de métricas no `/metrics`

### Validação real do smoke automatizado
- `ops/run_homologation_smoke.py --help` validado
- execução real concluída com sucesso na stack local
- evidências retornadas pelo smoke:
  - `tenant_id=3`
  - `process_id=16`
  - `document_id=5`
  - auditoria do processo com `created`, `status_changed` e `notification_process_status_changed`
  - auditoria do documento com `uploaded` e `notification_document_uploaded`
  - métricas confirmando sucesso para:
    - `workers.notify_process_status_changed`
    - `workers.notify_document_uploaded`
    - `amigao_email_delivery_total`
    - `amigao_document_uploads_total`

### Runbook atualizado
- `RunbookOperacional.md` atualizado para usar o smoke automatizado como caminho principal de validação operacional

### Situação atual
- a homologação crítica da stack agora está automatizada em script operacional reproduzível
- próximas frentes ficam mais baratas de validar porque processo, documento, auditoria e métricas já têm smoke único

---

## Execução complementar 9 em 29/03/2026

### Webhook operacional endurecido
- o envio de alertas para webhook passou a usar contrato explícito de entrega
- o payload agora inclui `alert_id` para rastreabilidade ponta a ponta
- o envio agora propaga `traceparent`, além de manter `request_id`, `trace_id` e `span_id` no corpo
- o destino pode exigir autenticação por header configurável via:
  - `ALERT_WEBHOOK_AUTH_HEADER`
  - `ALERT_WEBHOOK_AUTH_TOKEN`
- o corpo pode sair assinado com HMAC SHA-256 via `ALERT_WEBHOOK_SIGNING_SECRET`

### Validação operacional do sink local
- `ops/alert_webhook_sink.py` passou a validar opcionalmente autenticação e assinatura
- o artefato local agora registra:
  - `status_code`
  - `headers`
  - `validation`
  - `payload`
- isso fecha um caminho de homologação local mais próximo do comportamento de um destino externo real

### Cobertura e hardening de configuração
- criada a suíte `tests/test_alerts.py` para validar:
  - filtro por severidade
  - envio de `traceparent`
  - envio de autenticação por header
  - assinatura HMAC SHA-256
  - log estruturado de falha em `operational.alert.webhook_failed`
- `tests/test_settings.py` ampliado para cobrir:
  - bloqueio de `ALERT_WEBHOOK_URL` local em produção
  - consistência entre `ALERT_WEBHOOK_AUTH_TOKEN` e `ALERT_WEBHOOK_AUTH_HEADER`
- `.env.example`, `.env.production.example`, `docker-compose.yml` e `docs/ObservabilidadeOperacional.md` foram alinhados ao novo contrato

### Validações executadas
- `python ops/alert_webhook_sink.py --help` validado com os novos parâmetros
- `docker compose config` validado após inclusão das variáveis de autenticação e assinatura do webhook
- `.\venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\test_alerts.py tests\test_settings.py tests\api\test_observability.py -q` -> `16 passed`
- `docker compose up --build -d api worker client-portal` executado com sucesso para preparar a demonstração
- `GET /health` retornando `200` após estabilização do rebuild
- `http://localhost:3000/login` retornando `200` após estabilização do rebuild

### Situação atual
- a stack já suporta um webhook externo de alertas com autenticação, assinatura e correlação distribuída
- o destino externo definitivo ainda depende apenas do endpoint real para substituir o sink local

---

## Execução em 03/04/2026

### Contexto

Execução baseada no Plano Mestre de Correções (`docs/PLANO_MESTRE_CORRECOES.md`), resultado de auditoria por 5 agentes especializados. Ordem de execução: Backend P0 -> Backend P1.

### Backend P0 — Bugs críticos corrigidos

| # | Correção | Arquivo | Impacto |
|---|----------|---------|---------|
| 1 | Criado `PortableJSON` type (JSONB no Postgres, JSON no SQLite) | `app/models/types.py` | Testes não quebravam mais por incompatibilidade JSONB/SQLite |
| 2 | Substituído `JSONB` direto por `PortableJSON` em `ai_job.py` | `app/models/ai_job.py` | Cobertura de regressão do modelo IA restaurada |
| 3 | Adicionado import `emit_operational_alert` | `app/api/v1/tasks.py` | Fix de NameError em runtime quando tarefa vence |
| 4 | `class Config` → `model_config = ConfigDict(...)` | `app/api/v1/dashboard.py` | Eliminados warnings Pydantic v2 |
| 5 | `.dict()` → `.model_dump()` | `app/api/v1/processes.py`, `app/api/v1/properties.py` | Eliminados warnings Pydantic v2 |
| 6 | Removido `db: DbDep` não usado de 4 endpoints IA | `app/api/v1/ai.py` | Sessões DB não desperdiçadas em endpoints síncronos |

**Itens já OK (sem ação necessária):**
- `redis` e `passlib[bcrypt]` já estavam no `requirements.txt`
- `.env` já estava no `.gitignore` e fora do git tracking

### Backend P1 — Qualidade e contratos

| # | Entrega | Resultado |
|---|---------|-----------|
| 1 | **State machine unificada** | Adicionado `TERMINAL_PROCESS_STATUSES` em `app/models/process.py` para paridade com Task |
| 2 | **64 testes de state machine** | `tests/test_state_machines.py` — transições válidas/inválidas, terminais, happy path, loop de pendência, consistência enum ↔ mapa |
| 3 | **Migration check script** | `ops/check_migrations.sh` — valida head único, upgrade, downgrade, re-upgrade |
| 4 | **`_persist_job` refatorado** | `app/services/ai_job_persistence.py` — helper centralizado que aceita sessão externa, eliminou duplicação entre `llm_classifier.py` e `document_extractor.py` |
| 5 | **Smoke tests dashboard** | `tests/api/test_dashboard.py` — 3 testes (200, contagens tenant-scoped, 401 sem token) |
| 6 | **Smoke tests IA** | `tests/api/test_ai.py` — 6 testes (status, jobs list, job 404, classify, extract 503, 401) |
| 7 | **Conftest expandido** | `tests/conftest.py` — stub de `properties` expandido com todas as colunas do model (exceto Geometry), eliminando falhas de schema em testes |
| 8 | **Cobertura medida** | Models: **100%** (meta 70%) · API: **68%** (meta 60%) |

### Métricas da suíte

- **115 testes** totais coletados
- **114 passando** (todos os novos + todos os existentes)
- **1 falha pré-existente** (`test_pdf_generator` — problema com mock de storage, não relacionado)
- Tempo de execução: ~69s

### Arquivos criados

- `app/models/types.py` — PortableJSON type decorator
- `app/services/ai_job_persistence.py` — helper centralizado de persistência AIJob
- `tests/test_state_machines.py` — 64 testes de contrato para Task e Process
- `tests/api/test_dashboard.py` — smoke tests do dashboard
- `tests/api/test_ai.py` — smoke tests dos endpoints IA
- `ops/check_migrations.sh` — script de validação de migrations

### Arquivos modificados

- `app/models/ai_job.py` — JSONB → PortableJSON
- `app/models/process.py` — adicionado TERMINAL_PROCESS_STATUSES
- `app/api/v1/tasks.py` — import faltante corrigido
- `app/api/v1/dashboard.py` — Pydantic v2 compliance
- `app/api/v1/processes.py` — .dict() → .model_dump()
- `app/api/v1/properties.py` — .dict() → .model_dump()
- `app/api/v1/ai.py` — removido db: DbDep não usado
- `app/services/llm_classifier.py` — _persist_job removido, usa helper centralizado
- `app/services/document_extractor.py` — _persist_job removido, usa helper centralizado
- `tests/conftest.py` — stub de properties expandido

### Pendências remanescentes do P0/P1

- Fix do `test_pdf_generator` pré-existente (mock de storage)
- CORS para porta 5173 (frontend dev)

---

## Execução Sprint 3-4 / 5-6 Backend em 03/04/2026

### Contexto

Sprint de qualidade e arquitetura conforme Plano Mestre. Foco: eliminar SQLite dos testes, criar camada de repositories, pipeline CI, e refatorar Settings para testabilidade.

### 1. Settings refatorado para `lru_cache` + `override_settings`

- `app/core/config.py` refatorado:
  - `get_settings()` com `@lru_cache` substitui instanciação em import-time
  - `override_settings(**kwargs)` context manager para testes
  - `settings = get_settings()` como alias backward-compatible (20 arquivos continuam importando `settings` sem mudança)
- Validado com teste manual: override funciona, restauração pós-context automática

### 2. Testes migrados para Testcontainers (PostgreSQL real)

- `tests/conftest.py` completamente reescrito:
  - Removido SQLite in-memory e todos os stubs de `properties`
  - Container `postgis/postgis:15-3.3` via Testcontainers (session-scoped)
  - PostGIS habilitado via `CREATE EXTENSION IF NOT EXISTS postgis`
  - `Base.metadata.create_all()` roda no Postgres real (sem gambiarras)
  - Cada teste roda em transação com rollback (isolamento completo)
- `requirements.txt` atualizado com: `pytest-cov`, `testcontainers[postgres]`, `ruff`, `mypy`

### 3. Camada de Repositories implementada

**Base genérica:** `app/repositories/base.py`
- `BaseRepository[ModelT]` com tenant-scoping automático
- Métodos: `list`, `get`, `get_or_404`, `create`, `update`, `delete`

**5 repositories concretos:**

| Repository | Arquivo | Métodos extras |
|------------|---------|----------------|
| `ProcessRepository` | `app/repositories/process_repo.py` | `get_scoped`, `get_scoped_or_404`, `count_incomplete_tasks`, `add_audit`, `get_timeline` |
| `ClientRepository` | `app/repositories/client_repo.py` | (herda base) |
| `TaskRepository` | `app/repositories/task_repo.py` | `list_by_process`, `add_audit` |
| `PropertyRepository` | `app/repositories/property_repo.py` | `list_by_client` |
| `DocumentRepository` | `app/repositories/document_repo.py` | `list_scoped`, `get_scoped`, `add_audit` |

**5 routers refatorados para usar repositories:**
- `app/api/v1/clients.py` — CRUD via `ClientRepository`
- `app/api/v1/properties.py` — CRUD via `PropertyRepository`
- `app/api/v1/processes.py` — state machine + audit via `ProcessRepository`
- `app/api/v1/tasks.py` — state machine + audit via `TaskRepository`
- `app/api/v1/documents.py` — upload/download via `DocumentRepository` + `ProcessRepository`

### 4. Pipeline CI criada

- `pyproject.toml` criado com configuração de `ruff`, `mypy` e `pytest`
- `.github/workflows/ci.yml` com 3 jobs:
  - **lint:** `ruff check` + `mypy`
  - **test:** `pytest` com coverage (depende de lint)
  - **migrations:** `alembic upgrade/downgrade/upgrade` contra PostgreSQL real
- Ruff auto-fix aplicado em 21 arquivos (267 fixes automáticos)
- Per-file-ignores configurados para código legacy fora do escopo desta sprint

### Métricas finais

- **144 testes passando** (114 originais + 30 do Agente 3)
- **1 falha pré-existente** (`test_pdf_generator`)
- **Ruff:** verde (`All checks passed!`)
- Tempo de execução da suíte: ~102s

### Arquivos criados

- `pyproject.toml` — configuração de tooling (ruff, mypy, pytest)
- `.github/workflows/ci.yml` — pipeline CI
- `app/repositories/base.py` — base repository genérico
- `app/repositories/process_repo.py`
- `app/repositories/client_repo.py`
- `app/repositories/task_repo.py`
- `app/repositories/property_repo.py`
- `app/repositories/document_repo.py`
- `app/repositories/__init__.py` — re-exports

### Arquivos modificados

- `app/core/config.py` — `get_settings()` + `override_settings()`
- `tests/conftest.py` — migrado para Testcontainers PostgreSQL
- `app/api/v1/clients.py` — refatorado para repository
- `app/api/v1/properties.py` — refatorado para repository
- `app/api/v1/processes.py` — refatorado para repository
- `app/api/v1/tasks.py` — refatorado para repository
- `app/api/v1/documents.py` — refatorado para repository
- `requirements.txt` — adicionado pytest-cov, testcontainers, ruff, mypy
- 21 arquivos tocados pelo ruff auto-fix (imports, modernização)

### Pendências para próxima sessão

- Fix do `test_pdf_generator` pré-existente (mock de storage)
- CORS para porta 5173 (frontend dev)
- Repositories para routers restantes (checklists, contracts, proposals, dossier, intake, workflows)
- Migrar dashboard.py para usar repositories
- mypy strict mode (atualmente com `ignore_missing_imports`)

---

## Coordenação Multidisciplinar de Agentes (Definição em 03/04/2026)

### Objetivo da Coordenação
Sincronizar o trabalho de 3 agentes de IA especializados (rodando sob demanda), distribuindo e alocando frentes independentes baseadas no `PLANO_MESTRE_CORRECOES.md` para maximizar a aceleração e evitar conflito de merge (merge lock).

### Alocação de Sprints e Escopo Base

**Agente 1: Backend Core & Quality (Status: Ativo / Em Execução)**
- **Sprints:** Sprint 3-4 (Quality Gates) + Sprint 5-6 (Repositories) + P1 de Backend
- **Foco Técnico:**
  - Migrar testes e base para PostgreSQL real via Testcontainers, removendo legados limitantes do SQLite.
  - Implementar camada coesa de `Repositories` (Process, Client, Document, etc) abstraindo os routers.
  - Testes de Contrato de APIs em CI (`.github/workflows/ci.yml`).
  - Refatorar configuração (`lru_cache` para settings e overrides injetáveis em testes).
- **Risco Registrado:** Tocar nos models (`ai_job.py`, `processes.py`) precocemente e travar o Agente 3.

**Agente 2: Frontend & UX (Status: Start Pendente)**
- **Sprints:** Sprint F2 (Testes Vite/Clean) + Sprint F3 (Dashboard Enhancements) e F4
- **Foco Técnico:**
  - Adicionar cobertura rigorosa (Vitest + ESLint strict) sobre o state management e painel React.
  - Modularização pesada em `frontend/src/pages/Processes/ProcessDetail.tsx` (desfazer monolito).
  - Integrar os novos Filtros de Dashboard (Executivo vs Operacional) via React Query.
  - Componentização escalável e padronização visual UI/UX (Skeletons/Waterfalls).
- **Risco Registrado:** Desvio de tipos TypeScript. Sincronizar os hooks com a API via novo OpenAPI fornecido pelo Backend.

**Agente 3: Inteligência Artificial & Engine (Status: Start Pendente)**
- **Sprints:** Sprint IA-1 (Framework Base) + Sprint IA-2 (Classificação V2) + Sprints 5-6 de IA
- **Foco Técnico:**
  - Estruturar novo paradigma de subagentes independentes em `/app/agents/`.
  - Desligar prompts hardcoded implementando o modelo `PromptTemplate` na base de dados (Alembic).
  - Implementar classes modulares: `BaseAgent`, `AgentRegistry` e validação com JSON Schema OOTB.
  - Padronizar chamadas LLM e logs sob o `ai_gateway.py`.
- **Risco Registrado:** Lock no `alembic` e nas migrations. Agente 3 deve isolar suas migrations após o Agente 1 alinhar a branch master de Schema.

### Modelo de Sincronização
- **Fronteira Rígida de Paths**: Agente 1 opera unicamente em `/app/models/`, `/app/api/` e `/tests/`. Agente 2 opera estritamente na root de `/frontend/` e `client-portal`. Agente 3 opera restrito em `/app/agents/`, worker IA e config/banco associado à IA.
- Nenhuma frente finaliza sem atestar os passos de fumaça designados no `RunbookOperacional.md`.

---

## Sprint IA-1 — PromptTemplate (Agente 3, 03/04/2026)

### Objetivo
Migrar prompts hardcoded dos serviços de IA para o banco de dados com versionamento, governança por tenant e validação de schema JSON. Entrega fundacional da Sprint IA-1.

### Entregas realizadas

| # | Entrega | Arquivo(s) | Resultado |
|---|---------|------------|-----------|
| 1 | **Model `PromptTemplate`** | `app/models/prompt_template.py` | Enums `PromptCategory` (classify/extract/summarize/proposal) e `PromptRole` (system/user/few_shot). UniqueConstraint `(slug, version, tenant_id)`. Campos JSONB para `input_schema` e `output_schema`. Override opcional de `model_hint`, `temperature`, `max_tokens`. |
| 2 | **Registro no barrel** | `app/models/__init__.py` | Import adicionado para Alembic autogenerate |
| 3 | **Migration DDL** | `alembic/versions/d7f9a24dd5a7_add_prompt_templates_table.py` | Enum types via `postgresql.ENUM` com `create/drop` explícito. Ciclo `upgrade → downgrade → re-upgrade` validado sem erro. |
| 4 | **Migration de seed** | `alembic/versions/024fe3f5dbeb_seed_prompt_templates_data.py` | 9 prompts globais (tenant_id=NULL) v1 inseridos: 2 do classificador, 6 do extrator + 1 default. Output schemas incluídos. |
| 5 | **Schemas Pydantic** | `app/schemas/prompt_template.py` | `PromptTemplateCreate` com validação de slug regex `^[a-z][a-z0-9_]*$`, bounds de temperature (0-2) e max_tokens (1-32768). `PromptTemplateRead` com `from_attributes=True`. `PromptTemplateUpdate` para criação de nova versão. |
| 6 | **Prompt Service** | `app/services/prompt_service.py` | `get_active_prompt(slug, db, tenant_id)` com prioridade tenant > global + cache in-process TTL 60s. `create_new_version()` com auto-increment e desativação automática da versão anterior. `render_prompt()` para substituição de variáveis. `invalidate_cache()`. |
| 7 | **Refatoração dos serviços** | `app/services/llm_classifier.py`, `app/services/document_extractor.py` | Ambos agora aceitam `db_session` opcional. Carregam prompts do banco via `_load_prompt()`. Fallback ao hardcoded com log de warning se DB indisponível. Corrigido bug: `.format()` → `.replace()` em templates JSON do extrator (evita `KeyError` em braces). |

### Bug corrigido durante a implementação
`document_extractor.py` usava `.format(text=...)` em templates que continham JSON braces (`{"numero_car": null}`), causando `KeyError`. Corrigido para `.replace("{text}", ...)` — afeta tanto fallback hardcoded quanto fluxo via banco.

### Métricas da suíte

- **30 testes novos** em `tests/agents/` (3 arquivos)
- **144 passando** no total da suíte (30 novos + 114 existentes)
- **1 falha pré-existente** (`test_pdf_generator` — mock de storage, fora do escopo IA)
- **Zero consumo de API key** — mocks do `ai_gateway.complete`
- Tempo de execução: ~29s (agents) / ~139s (full)

### Validações de banco executadas
- `alembic heads` → head única, sem conflito com Agente 1
- `alembic upgrade head` → prompt_templates criada + 9 rows seeded
- `alembic downgrade -1` + `upgrade head` → ciclo reversível OK, enum types limpos no downgrade
- 9 prompts verificados no banco com `SELECT slug, category, role, version, is_active, length(content)`

### Arquivos criados
- `app/models/prompt_template.py`
- `app/schemas/prompt_template.py`
- `app/services/prompt_service.py`
- `alembic/versions/d7f9a24dd5a7_add_prompt_templates_table.py`
- `alembic/versions/024fe3f5dbeb_seed_prompt_templates_data.py`
- `tests/agents/__init__.py`
- `tests/agents/test_prompt_template_model.py` (6 testes)
- `tests/agents/test_prompt_service.py` (19 testes)
- `tests/agents/test_classifier_extractor_refactor.py` (5 testes)

### Arquivos modificados
- `app/models/__init__.py` — registro do PromptTemplate
- `app/services/llm_classifier.py` — refatorado para consumir prompts do banco
- `app/services/document_extractor.py` — refatorado para consumir prompts do banco + fix `.replace()`

### Pendências para Sprint IA-2
- Criar framework base de Agentes (`/app/agents/base.py`, `registry.py`)
- Implementar JSON schema estrito para validação de output LLM via Pydantic
- Refatorar chamadas LLM para passar obrigatoriamente pelo logger centralizado do `ai_gateway.py`
- Router CRUD de `PromptTemplate` em `/api/v1/prompts` (gestão pelo painel)

---

## Sprint F2/F3 — Frontend & UX (Agente 2, 03/04/2026)

### Objetivo
Estabelecer infraestrutura de testes rigorosa no frontend Vite, eliminar dívida técnica de tipagem, decompor o monolito ProcessDetail.tsx, e implementar Dashboard com filtros e skeletons modernos.

### Entregas realizadas

| # | Entrega | Arquivo(s) | Resultado |
|---|---------|------------|-----------|
| 1 | **Vitest configurado** | `frontend/vitest.config.ts`, `frontend/src/test/setup.ts` | Environment `node`, globals, alias `@/`, coverage v8. Testes de componente usam directive `// @vitest-environment jsdom`. |
| 2 | **21 testes unitários** | `lib/auth.test.ts` (9), `lib/utils.test.ts` (5), `store/auth.test.ts` (3), `utils/statusUtils.test.ts` (4) | Cobertura dos hooks internos: JWT parsing, token detection, Tailwind merge, Zustand store, status utils. |
| 3 | **ESLint blockante** | `frontend/package.json` | `eslint --max-warnings=0` no script `lint`. Qualquer warning bloqueia CI. |
| 4 | **50 erros de lint eliminados** | 15 arquivos em `frontend/src/` | Todos os `any` substituídos por tipos concretos. `unused-vars` corrigidos. `set-state-in-effect` refatorado com `useMemo`. |
| 5 | **Migração statusUtils.js → .ts** | `frontend/src/utils/statusUtils.ts` | Tipagem com union type `Comparison = "greater" \| "less"`. JS original removido. |
| 6 | **Decomposição do ProcessDetail.tsx** | 6 novos arquivos em `frontend/src/pages/Processes/` | Redução de 565 → 146 linhas no componente principal (74% de redução). |
| 7 | **Dashboard com toggle Executivo/Operacional** | `frontend/src/pages/Dashboard/index.tsx` | Segmented control pill-style com estado via React Query keyed por `viewMode`. |
| 8 | **Skeletons dedicados** | `frontend/src/pages/Dashboard/index.tsx` | `SkeletonStatsCards`, `SkeletonActivities`, `SkeletonTasks` substituindo spinners genéricos. |
| 9 | **useQueries paralelo** | `frontend/src/pages/Dashboard/index.tsx` | 3 queries independentes (stats, activities, tasks) com fallback para `/dashboard/summary`. Sem waterfall. |
| 10 | **Code splitting** | `frontend/vite.config.ts` | `manualChunks` separando vendor (49KB), query (45KB), ui (20KB). Chunk principal caiu de 531KB → 416KB. |

### Subcomponentes extraídos do ProcessDetail

| Componente | Arquivo | Linhas | Responsabilidade |
|---|---|---|---|
| `ProcessDetailTypes` | `ProcessDetailTypes.ts` | ~110 | Interfaces (Process, Task, Document, TimelineEntry) e constantes (STATUS_CONFIG, TABS, etc.) |
| `ProcessHeader` | `ProcessHeader.tsx` | ~68 | Header card com badges de status/urgência/demanda, back button, meta row |
| `DiagnosisTab` | `DiagnosisTab.tsx` | ~75 | Diagnóstico inicial, descrição, notas do intake, metadata grid |
| `TasksTab` | `TasksTab.tsx` | ~90 | Formulário + lista de tarefas com queries e mutations próprias |
| `DocumentsTab` | `DocumentsTab.tsx` | ~79 | Upload, checklist e listagem de documentos com query própria |
| `TimelineTab` | `TimelineTab.tsx` | ~51 | Timeline vertical com query própria |

### Métricas de build

| Métrica | Antes | Depois |
|---|---|---|
| Chunk principal | 531 KB (warning >500KB) | 416 KB (sem warning) |
| Chunks totais | 1 | 4 (vendor, query, ui, app) |
| Build time | ~24s | ~16s |
| Erros de lint | 50 | 0 |
| Testes | 0 | 21 passando |

### Validações executadas
- `npm run build` → `tsc -b && vite build` sem erros nem warnings
- `npm run test` → 21 passed, 4 suites
- `npm run lint` → `eslint --max-warnings=0` → exit 0
- `npx tsc --noEmit` → 0 erros de tipo

### Pendências para Sprint F4
- Testes de componentes React com Testing Library (componentes com JSX, necessitam jsdom compatível)
- Decomposição de `Processes/index.tsx` (segundo maior arquivo)
- Hook customizado `useDashboard` para encapsular queries do Dashboard
- Integração com OpenAPI gerada pelo backend (tipagem end-to-end)
- Acessibilidade: aria-labels nos cards e botões do Dashboard

