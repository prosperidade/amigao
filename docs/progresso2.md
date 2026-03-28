# 📋 Progresso Consolidado — MVP Portal do Cliente & Automações

## Projeto: Amigão do Meio Ambiente
## Sprint Atual: Sprint 5

---

## ✅ O que foi feito hoje

### Sessão — Portal do Cliente & IA (Sprint 5)
| Item | Status |
|------|--------|
| Inicialização Next.js 15 em `/client-portal` (App Router) | ✅ |
| Store de Autenticação Zustand + Interceptors Axios | ✅ |
| Login Page Premium (Emerald Theme) para Clientes | ✅ |
| Dashboard do Cliente: Listagem de Processos do Imóvel | ✅ |
| Timeline Pública: Histórico de status filtrado para o cliente | ✅ |
| Gestão de Docs: Download e Upload (Presigned URL) para o cliente | ✅ |
| Gerador de PDF: Task Celery com `fpdf2` para Ficha de Visita | ✅ |
| Motor de IA: Integração `LiteLLM` para Resumos Semanais | ✅ |
| Gatilho: Geração automática de PDF ao concluir processo ('done') | ✅ |

### Sessão — Correções de Integração, Validação e Git
| Item | Status |
|------|--------|
| Alinhamento do `client-portal` com o contrato real da API (`title`, status, timeline e documentos) | ✅ |
| Correção do fluxo de upload/download com URLs presignadas | ✅ |
| Correção da guarda de autenticação para esperar a hidratação do Zustand persistido | ✅ |
| Ajuste visual global do portal (`globals.css` + fonte `Inter`) | ✅ |
| Registro de evento `created` na timeline do processo | ✅ |
| Correção do gatilho de PDF para status real `concluido` no backend | ✅ |
| Validação estática do portal com TypeScript (`tsc --noEmit`) | ✅ |
| Validação sintática do backend ajustado (`app/api/v1/processes.py`) | ✅ |
| Inicialização do repositório raiz Git e push para GitHub | ✅ |
| Publicação em `https://github.com/prosperidade/amigao` na branch `main` | ✅ |

---

## 🗂️ Arquivos criados/modificados (Sprint 5)

```
client-portal/
├── src/
│   ├── app/
│   │   ├── login/page.tsx          [NOVO] — Tela de acesso
│   │   ├── dashboard/
│   │   │   ├── layout.tsx          [NOVO] — Layout com Sidebar
│   │   │   ├── page.tsx            [NOVO] — Lista de processos
│   │   │   └── process/[id]/page.tsx [NOVO] — Timeline + Docs
│   ├── store/auth.ts               [NOVO] — Estado global
│   └── lib/
│       ├── api.ts                  [NOVO] — Conexão Backend
│       └── process-status.ts       [NOVO] — Mapeamento de status do processo
app/
├── api/
│   └── v1/
│       └── processes.py            [MODIFICADO] — Timeline de criação + trigger de PDF em `concluido`
├── workers/
│   ├── tasks.py                    [MODIFICADO] — Novas tasks registradas
│   ├── pdf_generator.py            [NOVO] — Lógica FPDF
│   └── ai_summarizer.py            [NOVO] — Lógica LiteLLM
docs/
└── progresso2.md                   [MODIFICADO] — Registro consolidado da sessão
raiz/
├── .gitignore                      [MODIFICADO] — Ignore de artefatos Node/Next/Expo
└── .git                            [NOVO] — Repositório principal inicializado
```

### Observações operacionais da sessão
- Os `.git` internos antigos de `client-portal` e `mobile` foram preservados em backup local para evitar submódulos acidentais.
- Commit publicado no GitHub: `fb3895b26a526a1d287549d97fce29c5d84dd9e1`.

---

## ⚡ Como rodar os serviços da Sprint 5

### 1. Backend & Workers (Obrigatório para o Portal funcionar)
```bash
# Terminal 1: API
.\venv\Scripts\uvicorn.exe app.main:app --reload

# Terminal 2: Celery Worker
.\venv\Scripts\celery.exe -A app.core.celery_app worker --loglevel=info --pool=solo
```

### 2. Portal do Cliente (Nova Interface)
```bash
cd client-portal
npm run dev
```
> O portal estará disponível em: `http://localhost:3000` (ou a porta indicada no terminal).

---

### Sessão — Segurança do Portal & Estabilização
| Item | Status |
|------|--------|
| Recorte de segurança do Portal do Cliente por `client_id` no backend | ✅ |
| Bloqueio de rotas internas para tokens escopados de cliente | ✅ |
| Vínculo automático de documentos do portal ao `client_id` correto | ✅ |
| Correção da task de resumo IA para executar de fato o summarizer | ✅ |
| Correção do gerador de PDF para o modelo real de `Process`/`Document` | ✅ |
| Ajuste da suíte de testes de API para ambiente local sem PostGIS/Redis | ✅ |

---

### Sessão — Notificações Reais, WebSocket & Auditoria
| Item | Status |
|------|--------|
| Gatilho Celery para notificação de mudança de status do processo | ✅ |
| Template de e-mail dedicado para atualização de status ao cliente | ✅ |
| Publicação de eventos em Redis/WebSocket com escopo por `tenant_id` e `client_id` | ✅ |
| Alerta interno por e-mail para documento enviado via Portal do Cliente | ✅ |
| Registro de auditoria para notificações e upload confirmado | ✅ |
| Startup do listener Redis protegido contra indisponibilidade do broker | ✅ |
| Cobertura de testes para upload do portal e troca de status | ✅ |

### Sessão — Homologação do PDF de Visita
| Item | Status |
|------|--------|
| Refino do layout com cabeçalho, rodapé e seções legíveis | ✅ |
| Suporte a logomarca real do tenant com fallback `png/jpg/jpeg` | ✅ |
| Inclusão de resumo executivo, protocolo, prazos e checklist de campo | ✅ |
| Persistência do relatório como `Document` com metadados válidos | ✅ |
| Cobertura automatizada do gerador de PDF em ambiente local | ✅ |

### Sessão — Deploy Containerizado do Portal e Backend
| Item | Status |
|------|--------|
| Dockerfile raiz para API FastAPI e worker Celery | ✅ |
| Atualização do Docker do `client-portal` para Node 20 compatível com Next 16 | ✅ |
| `docker-compose.yml` integrado com `api`, `worker`, `db`, `redis`, `minio` e `client-portal` | ✅ |
| Healthchecks básicos para PostgreSQL e Redis | ✅ |
| Rewrite do portal ajustado para falar com `api:8000` dentro da rede Docker | ✅ |
| CORS do backend tornado configurável por ambiente | ✅ |
| README do portal reescrito com fluxo real de dev/build/deploy | ✅ |
| Validação de build do portal e parsing do compose | ✅ |

### Sessão — Limpeza Técnica & Compatibilidade
| Item | Status |
|------|--------|
| Migração de `BaseSettings` para `SettingsConfigDict` no backend | ✅ |
| Migração de schemas Pydantic para `ConfigDict(from_attributes=True)` | ✅ |
| Atualização de `declarative_base()` para `sqlalchemy.orm.declarative_base` | ✅ |
| Startup do WebSocket movido para `lifespan` com encerramento limpo do Redis PubSub | ✅ |
| Perfil explícito `client_portal` consolidado no JWT e no `AccessContext` | ✅ |
| Remoção das deprecações do `fpdf2` no gerador de PDF | ✅ |
| Suíte principal sem warnings remanescentes | ✅ |

### Arquivos consolidados na continuidade
```
./
├── .dockerignore                    [NOVO] — Redução de contexto do build Docker
├── Dockerfile                       [NOVO] — Imagem base da API/worker
├── docker-compose.yml               [MODIFICADO] — Stack integrada para deploy local
app/
├── api/
│   ├── deps.py                       [MODIFICADO] — Contexto de acesso centralizado + perfil explícito
│   ├── websockets.py                 [MODIFICADO] — Canais escopados + lifespan/encerramento do Redis
│   ├── v1/
│   │   ├── auth.py                   [MODIFICADO] — Token com escopo `client_id` e perfil explícito
│   │   ├── clients.py                [MODIFICADO] — Bloqueio de rotas internas para portal
│   │   ├── documents.py              [MODIFICADO] — Upload confirmado + auditoria + task de notificação
│   │   ├── processes.py              [MODIFICADO] — Escopo por cliente + task de status + trigger de PDF
│   │   ├── properties.py             [MODIFICADO] — Bloqueio para token do portal
│   │   ├── tasks.py                  [MODIFICADO] — Bloqueio para token do portal
│   │   └── threads.py                [MODIFICADO] — Bloqueio para token do portal
├── core/
│   ├── config.py                     [MODIFICADO] — Canais realtime, CORS e URL do portal
│   ├── logging.py                    [MODIFICADO] — Helper `get_logger`
│   └── security.py                   [MODIFICADO] — Claims com `client_id` e perfil explícito
├── main.py                           [MODIFICADO] — Lifespan centralizado da aplicação
├── models/
│   └── base.py                       [MODIFICADO] — `declarative_base` no padrão SQLAlchemy 2
├── schemas/
│   ├── communication.py              [MODIFICADO] — `ConfigDict` no padrão Pydantic 2
│   ├── document.py                   [MODIFICADO] — `ConfigDict` no padrão Pydantic 2
│   ├── property.py                   [MODIFICADO] — `ConfigDict` no padrão Pydantic 2
│   ├── task.py                       [MODIFICADO] — `ConfigDict` no padrão Pydantic 2
│   └── token.py                      [MODIFICADO] — Schema do token expandido
├── services/
│   ├── email.py                      [MODIFICADO] — Templates reais de status/documento
│   └── notifications.py              [NOVO] — Redis pub/sub + auditoria
└── workers/
    ├── __init__.py                   [MODIFICADO] — Registro correto das tasks
    ├── ai_summarizer.py              [MODIFICADO] — Persistência em `ai_summary`
    ├── pdf_generator.py              [MODIFICADO] — Layout final e persistência correta
    └── tasks.py                      [MODIFICADO] — Notificações reais + retries
tests/
├── api/
│   ├── test_auth.py                  [MODIFICADO] — Cobertura do token do portal
│   ├── test_clients.py               [MODIFICADO] — Cobertura de bloqueio interno
│   ├── test_documents.py             [NOVO] — Upload do portal dispara notificação
│   └── test_processes.py             [MODIFICADO] — Mudança de status dispara task
├── conftest.py                       [MODIFICADO] — Harness local sem PostGIS/Redis
└── test_pdf_generator.py             [NOVO] — Cobertura do gerador de PDF
client-portal/
├── Dockerfile                        [MODIFICADO] — Base Node 20 para produção
└── README.md                         [MODIFICADO] — Guia real de operação e Docker
docs/
└── progresso2.md                     [MODIFICADO] — Registro consolidado da continuidade
```

### Validação executada nesta continuidade
- `.\venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/api/test_auth.py tests/api/test_clients.py tests/api/test_processes.py tests/api/test_documents.py tests/test_pdf_generator.py -q` → `13 passed`, sem warnings
- `docker compose config` → configuração resolvida sem erros
- `npm run build` em `client-portal/` → build de produção concluída com sucesso em Next.js 16.2.1

---

## 🎯 Próximos passos — Sugestões
- [x] Implementar notificações Push/Email reais no Celery.
- [x] Homologar o PDF com logomarca real do Tenant e revisar layout final.
- [x] Preparação para Deploy (Dockerização do Portal Next.js).
- [x] Limpeza técnica: warnings de deprecação, startup WebSocket/Redis e consolidação final do perfil `cliente_portal`.
- [ ] Subida homologada da stack com `docker compose up --build` e checklist funcional em ambiente integrado.
- [ ] Parametrização de segredos reais de produção (`SECRET_KEY`, SMTP e domínios finais do portal/API).

---
*Documento criado em 27/03/2026 e atualizado em 01/04/2026 — Status: Fase 3 (Portal do Cliente) funcional, com recorte de segurança por cliente validado, notificações reais entregues, PDF homologado, stack containerizada e limpeza técnica concluída para a próxima homologação integrada.*
