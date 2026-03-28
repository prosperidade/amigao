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

## 🎯 Próximos passos — Sugestões
- [ ] Implementar notificações Push/Email reais no Celery.
- [ ] Refinar o PDF com a logomarca customizada do Tenant (MinIO).
- [ ] Concluir o recorte de segurança do Portal do Cliente por `client_id` em vez de apenas `tenant_id`.
- [ ] Preparação para Deploy (Dockerização do Portal Next.js).

---
*Documento criado em 27/03/2026 e atualizado em 27/03/2026 — Status: Fase 3 (Portal do Cliente) funcional, com integração corrigida e projeto publicado no GitHub.*
