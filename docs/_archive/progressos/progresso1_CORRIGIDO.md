# 📋 Progresso Consolidado — MVP Operacional Web + Mobile

## Projeto: Amigão do Meio Ambiente
## Sprints Concluídas: Sprint 1, Sprint 2, Sprint 3 e Sprint 4

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

### Sessão 2 — Finalizando Sprint 1 (tarde)
> Conversa: `98a57102-784b-4536-9f19-1cdff9ce9d7d`

| Item | Status |
|------|--------|
| Modelo `Document` (SQLAlchemy) | ✅ |
| Schemas Pydantic para `Document` | ✅ |
| `StorageService` (boto3 + MinIO) em `app/services/storage.py` | ✅ |
| Endpoint `POST /api/v1/documents/upload` | ✅ |
| Migration do modelo `Document` gerada e aplicada ao banco | ✅ |
| Logging estruturado com `request_id` e `tenant_id` em `app/core/logging.py` | ✅ |
| `RequestContextMiddleware` em `app/api/middleware.py` | ✅ |
| Celery app configurado com Redis broker em `app/core/celery_app.py` | ✅ |
| Tasks base `test_job` e `log_document_uploaded` em `app/workers/tasks.py` | ✅ |
| `main.py` atualizado: logging + middleware + rota de documentos registrados | ✅ |

---

## 📦 Entregáveis da Sprint 1 — Status Final

| Entregável | Status |
|-----------|--------|
| 👉 Logar (POST /auth/login) | ✅ |
| 👉 Criar cliente | ✅ |
| 👉 Criar processo | ✅ |
| 👉 Subir documento (MinIO) | ✅ |
| 👉 Ver logs (estruturado com tenant_id) | ✅ |
| 👉 Rodar worker (Celery + Redis) | ✅ |

**Sprint 1 encerrada com sucesso. Todos os entregáveis entregues.**

---

## 🗂️ Arquivos criados/modificados hoje (Sessão 2)

```
app/
├── main.py                         [MODIFICADO] — logging + middleware + rota docs
├── models/
│   └── document.py                 [NOVO]
├── schemas/
│   └── document.py                 [NOVO]
├── services/
│   └── storage.py                  [NOVO] — cliente MinIO via boto3
├── api/
│   ├── middleware.py               [NOVO] — RequestContextMiddleware
│   └── v1/
│       └── documents.py            [NOVO] — POST /documents/upload
├── core/
│   ├── logging.py                  [NOVO] — setup_logging + context vars
│   └── celery_app.py               [NOVO] — Celery + Redis broker
└── workers/
    ├── __init__.py                 [NOVO]
    └── tasks.py                    [NOVO] — test_job + log_document_uploaded
alembic/versions/
└── b69a429faaa4_add_document_model.py  [NOVO + CORRIGIDO]
```

---

## ⚡ Para iniciar o worker na próxima sessão

```bash
# Iniciar API
.\venv\Scripts\uvicorn.exe app.main:app --reload

# Iniciar Celery Worker (em outro terminal)
.\venv\Scripts\celery.exe -A app.core.celery_app worker --loglevel=info --pool=solo
```

> **Nota:** `--pool=solo` é necessário no Windows (não há suporte a `fork`).

---

## 🎯 Próximos passos — O que já foi concluído

### ✅ Sprint 2 — MVP Operacional (Backend & Frontend Base)

**Backend e Banco:**
- [x] Testes automatizados com `pytest` para auth, clientes e processos
- [x] CRUD completo de Imóveis (`/api/v1/properties`) com PostGIS
- [x] Máquina de estados de Processo (validação de transições em `update_process_status`)
- [x] CRUD de Tarefas (`/api/v1/tasks`) com dependências
- [x] Threads de comunicação interna (`/api/v1/threads` e `messages`)
- [x] Endpoint de timeline por processo (`/api/v1/processes/{id}/timeline`)
- [x] Adição de `hash_sha256` em `core.audit_log` para cadeia de custódia

**Frontend (React + Vite):**
- [x] Setup React + Vite, TailwindCSS, Axios interceptors e Zustand para Auth
- [x] Tela de Login reativa e persistência JWT
- [x] Layout Privado + Sidebar de navegação
- [x] Tela de Clientes (CRUD completo com modais)
- [x] Tela de Processos (Kanban Board com Drag and Drop interativo)

**Infra / DevOps:**
- [x] WebSocket (FastAPI + Redis pub/sub para Tenant isolado)

---

### ✅ Sprint 3 — Conclusão do MVP Web (Fase 1 do roadmap)

**Tarefas & Timeline:**
- [x] Expansão do Modal de Processos num Painel Lateral (Drawer).
- [x] Integração da aba `Timeline` com o endpoint de logs imutáveis.
- [x] Criação e Toggle de `Tarefas` filhas alocadas dinamicamente dentro do modal do processo.

**Documentos & Evidências:**
- [x] Endpoint S3/MinIO no backend (`/upload-url`, `/confirm-upload`, `/download-url`).
- [x] Endpoint `GET /api/v1/documents` para listar arquiteturas de um processo.
- [x] Dropzone no Frontend (Upload direto para storage via Presigned URLs, não sobrecarregando o loop do FastAPI).

**Imóveis Rurais:**
- [x] Tela Tabela de `Imóveis` com listagem e filtro de busca.
- [x] Formulário de criação vinculando `Proprietário (Cliente)` e inserindo dados como `CAR` e `Hectares`.

---

## 🎯 Próximos passos reais — Sprint 4 (Mobile & Offline)

Com a Fase 1 (Web Operacional) 100% estabilizada, entramos na **Fase 2 do Roadmap**:

**Mobile (React Native / Expo):**
- [ ] Setup do App Mobile.
- [ ] Login e Auth via token.
- [ ] Download offline de Tarefas/Processos e armazenamento em SQLite local (`expo-sqlite`).
- [ ] Sistema de Checklist / Formulários desativados da rede.
- [ ] Upload Offline-First com `Background Sync` (captura de Fotos, Áudios, GPS com fila de reconexão).

---

## 📌 Decisões técnicas travadas (não reabrir)

| Decisão | Escolha |
|---------|---------|
| Backend principal | FastAPI (Python) |
| Banco de dados | PostgreSQL 16 + PostGIS + pgvector |
| Storage | MinIO local → S3/R2 em produção |
| Fila | Redis + Celery |
| Frontend painel | React + Vite |
| Frontend portal cliente | Next.js |
| Mobile | React Native |
| IA | SDK nativo (sem LangChain) — avaliar LiteLLM para AI Gateway |
| Multi-tenant | Coluna `tenant_id` em todas as tabelas de negócio |

---

*Documento atualizado ao final da Sprint 4 (26/03/2026) — Status: MVP Operacional Web + Aplicativo Mobile Offline-First totalmente funcionais.*

---

## ✅ Sprint 4 — Aplicativo Mobile Offline-First

### Sessão — Mobile App (React Native + Expo)

| Item | Status |
|------|--------|
| Inicialização do projeto Expo SDK 54 na pasta `/mobile` | ✅ |
| Instalação de módulos nativos: `expo-sqlite`, `expo-secure-store`, `expo-camera`, `expo-location`, `expo-image-picker`, `@react-native-community/netinfo` | ✅ |
| Esquema SQLite local: tabelas `processes`, `tasks`, `sync_queue` | ✅ |
| Zustand Auth Store: persistência de token JWT no SecureStore | ✅ |
| Zustand Network Store: escuta real-time de mudanças de conectividade | ✅ |
| Axios com interceptor automático de token | ✅ |
| `SyncService.pullActiveProcesses()`: Download dos processos do Backend para SQLite | ✅ |
| `SyncService.pushPendingMutations()`: Execução da fila de sync quando volta internet | ✅ |
| `SyncService.enqueueMutation()`: Salva ação offline na `sync_queue` e tenta push imediato | ✅ |
| Tela de Login com chamada OAuth FastAPI + pull SQLite pós-login | ✅ |
| Root Layout com Guard de Autenticação automático (Expo Router) | ✅ |
| Tela de Listagem de Processos: leitura 100% offline do SQLite | ✅ |
| Banner de status de rede + Monitor da Sync Queue com botão de force push | ✅ |
| Tela de Detalhes do Processo + Checklist offline com toggle local | ✅ |
| Botão "Evidência" no header de detalhes linkando para câmera | ✅ |
| `EvidenceService`: captura de foto + GPS simultâneos | ✅ |
| `EvidenceService`: salvamento local no `expo-file-system` com metadados na `sync_queue` | ✅ |
| `EvidenceService.uploadPendingEvidences()`: Upload via Presigned URL MinIO quando online | ✅ |
| Tela de Captura de Evidência com preview, metadados GPS e status de upload | ✅ |
| Tela de Configurações com logout seguro | ✅ |

### 🛠️ Correções e Ajustes de Final de Dia (Sessão de Debug)
| Item | Status |
|------|--------|
| Correção do bundle 84% no Expo Go via instalação nativa do `react-native-svg` | ✅ |
| Reconfiguração do `app.json` removendo `newArchEnabled` para compatibidade via LAN no Expo Go | ✅ |
| Adição de fallback rigoroso `?? null` no `SyncService` para evitar Crash silencioso do SQLite | ✅ |
| Correção da captura de Checklists/Tarefas na rotina do motor de sincronização | ✅ |

---

### 📌 Pendências Resolvidas (Início de Dia)
- **[x] Bug Menor Identificado:** Ao clicar no card do processo ("CAR") na lista do App Mobile, agora entra corretamente nos detalhes. O problema estava no `app/_layout.tsx`, onde o Guard de Autenticação avaliava apenas a rota `(tabs)`, interceptando e matando a navegação para `/process/[id]`. O comportamento foi corrigido para validar corretamente sessões ativas com base na exclusão da rota `login`.
