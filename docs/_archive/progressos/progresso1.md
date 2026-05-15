# 📋 Progresso — 26/03/2026

## Projeto: Amigão do Meio Ambiente
## Sprint: Sprint 1 — Fundação Executável + Fase 1 MVP Operacional

---

## ✅ O que foi feito hoje

### Sessão 1 — Implementação da Fundação (manhã)
> Conversa: `1ea3ced9-8a58-472a-b1a7-317cfc81c2c4`

| Item | Status |
|------|--------|
| Setup FastAPI + estrutura modular (`/api`, `/core`, `/models`, `/schemas`, `/services`, `/workers`) | ✅ |
| Docker Compose: PostgreSQL/PostGIS, Redis, MinIO | ✅ |
| Configuração do ambiente via `.env` + `app/core/config.py` | ✅ |
| Modelos SQLAlchemy: `Tenant`, `User`, `Client`, `Process` | ✅ |
| Autenticação JWT: `POST /auth/login`, `GET /auth/me` | ✅ |
| Multi-tenancy via `X-Tenant-Id` header + middleware de deps | ✅ |
| CRUD Clientes: `GET/POST /api/v1/clients` | ✅ |
| CRUD Processos: `GET/POST/GET{id} /api/v1/processes` | ✅ |
| Migrations Alembic aplicadas com sucesso | ✅ |

---

### Sessão 2 — Storage e Workers (tarde)
> Conversa: `98a57102-784b-4536-9f19-1cdff9ce9d7d`

| Item | Status |
|------|--------|
| Modelo `Document` (SQLAlchemy) e Schemas | ✅ |
| `StorageService` (boto3 + MinIO) em `app/services/storage.py` | ✅ |
| Endpoint estático `POST /api/v1/documents/upload` | ✅ |
| Logging estruturado e `RequestContextMiddleware` | ✅ |
| Celery app configurado e Tasks base (test_job, log_upload) | ✅ |

---

### Sessão 3 — Auditoria e Alinhamento de Modelos (fim de tarde)
> Conversa Atual

Após auditoria completa da documentação atualizada, foram aplicadas as seguintes **Correções Críticas**:

| Item de Correção | Status |
|------|--------|
| Novo modelo `Property` e relacionamentos atualizados | ✅ |
| Máquina de estados `ProcessStatus` expandida de 7 para 11 estados e campos faltantes em `Process`  | ✅ |
| Enum `ClientType`, `ClientStatus` e CRM fields adicionados a `Client` | ✅ |
| Refatoração de `Document` com suporte a pipeline OCR (status, origin) | ✅ |
| Refatoração Storage: Endpoint passou para fluxo com **Presigned URLs** (`upload-url` e `confirm-upload`) | ✅ |
| Migration limpa do PostGIS gerada (`afcea9834c04`) e aplicada com sucesso | ✅ |

---

### Sessão 4 — Fase 1 MVP Operacional Construída (noite)
> Conversa Atual (Continuação)

Todos os itens da Fase 1 foram finalizados e integrados.

| Item | Status |
|------|--------|
| **Imóveis (Properties):** Modelos e API CRUD criados para propriedades rurais | ✅ |
| **Gestão de Tarefas (Tasks):** Modelos, API CRUD e endpoint Board/Kanban (`todo`, `in_progress`, `review`, `done`) | ✅ |
| **Máquina de Estados:** Regras de negócio restritas no avanço de status de `Process` via endpoint dedicado (`POST /processes/{id}/status`) | ✅ |
| **Log de Auditoria:** Tabela genérica `AuditLog` e geração automática em transições de processos e tarefas | ✅ |
| **Auth & Swagger:** Adicionado `POST /auth/logout` stateless e Swagger documentado | ✅ |

---

## 📦 Entregáveis da Fase 1 MVP Operacional — Status Final

| Entregável | Status |
|-----------|--------|
| 👉 Operação de Clientes (CRUD + Tipos PF/PJ) | ✅ |
| 👉 Operação de Imóveis (Properties) | ✅ |
| 👉 Operação de Processos (Máquina de 11 estados + Timelines) | ✅ |
| 👉 Operação de Tarefas (Kanban Boards + Status) | ✅ |
| 👉 Upload 2-steps de Documentos (Presigned URL) | ✅ |
| 👉 Observabilidade de Mudanças (Audit Logs automáticos) | ✅ |

**Fase 1 MVP Operacional encerrada com sucesso. A fundação de domínios core está pronta para frontend.**

---

## 🗂️ Arquivos criados/modificados hoje (Sessões 3 e 4)

```
app/
├── main.py                         [MODIFICADO] — inclusão router properties e tasks
├── models/
│   ├── client.py                   [MODIFICADO] — novos enum/CRM
│   ├── process.py                  [MODIFICADO] — enum 11 states, validação graph
│   ├── document.py                 [MODIFICADO] — metadados completos
│   ├── property.py                 [NOVO]
│   ├── task.py                     [NOVO]
│   └── audit_log.py                [NOVO]
├── schemas/
│   ├── process.py                  [MODIFICADO] — include ProcessStatusUpdate
│   ├── property.py                 [NOVO]
│   └── task.py                     [NOVO]
├── services/
│   └── storage.py                  [MODIFICADO] — presigned urls
└── api/v1/
    ├── documents.py                [MODIFICADO] — presigned flow
    ├── processes.py                [MODIFICADO] — status_update webhook handler
    ├── properties.py               [NOVO]
    ├── tasks.py                    [NOVO]
    └── auth.py                     [MODIFICADO] — post /logout
alembic/versions/
├── afcea9834c04_correct_models...  [NOVO] — refactor de toda fundação
├── d7515c8f0c3b_add_task_model.py  [NOVO]
└── ca481d367022_add_auditlog_...   [NOVO]
```

---

## ⚡ Para iniciar o servidor e workers localmente

```bash
# Iniciar API FastAPI
.\venv\Scripts\uvicorn.exe app.main:app --reload

# Iniciar Celery Worker (em outro terminal)
.\venv\Scripts\celery.exe -A app.core.celery_app worker --loglevel=info --pool=solo
```

> **Nota:** `--pool=solo` é necessário no Windows (não há suporte a `fork`).

---

## 🎯 Próximos passos — Fase 2 (Campo Offline + Evidência)

**Mobile (React Native) / Frontend (React)**
- [ ] Setup do app mobile (Expo/React Native) e projeto React web (Vite)
- [ ] Login e sincronização inicial
- [ ] SQLite local e estrutura "Trust-List" base
- [ ] Listagem offline de Imóveis, Processos e Tarefas
- [ ] Captura de evidências fotográficas offline
- [ ] Integração do painel Web com os novos endpoints (Properties, Kanban, Status Board)

**Backend / API (Fase 2 Support)**
- [ ] Endpoints de "Dump" para sincronização offline robusta (`GET /sync/dump`)
- [ ] Fila de sincronização / resolução de conflitos (`POST /sync/push`)

**O que NÃO entra na Fase 2**
- ❌ Integração com GovTech / APIs governamentais (Fase 5/6)
- ❌ Agentes de IA funcionais - exceto OCR se necessário no mobile (Fase 3)
- ❌ Assinatura eletrônica E2E (Fase 4)
- ❌ RAG e Busca em base regulatória (Fase 3)

---

## 📌 Decisões técnicas travadas (não reabrir)

| Decisão | Escolha |
|---------|---------|
| Backend principal | FastAPI (Python) |
| Banco de dados | PostgreSQL 16 + PostGIS + pgvector |
| Storage | MinIO local → S3/R2 em produção (Presigned via Boto3) |
| Fila | Redis + Celery |
| Frontend web | React + Vite / Next.js |
| Mobile | React Native (Offline-first) |
| IA Routing | Gateway customizado no Python abstraindo SDKs diretos |
| Multi-tenant | Coluna `tenant_id` em todas as tabelas de negócio e models |

---

*Documento atualizado em 26/03/2026 — Revisão: Padronização completa e marco zero da Fase 2 de execução.*
