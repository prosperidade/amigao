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
│   └── lib/api.ts                  [NOVO] — Conexão Backend
app/
├── workers/
│   ├── tasks.py                    [MODIFICADO] — Novas tasks registradas
│   ├── pdf_generator.py            [NOVO] — Lógica FPDF
│   └── ai_summarizer.py            [NOVO] — Lógica LiteLLM
services/
└── storage.py                      [MODIFICADO] — upload_bytes para Workers
api/v1/
└── processes.py                    [MODIFICADO] — Trigger de PDF no status 'done'
```

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
- [ ] Preparação para Deploy (Dockerização do Portal Next.js).

---
*Documento criado em 27/03/2026 — Status: Fase 3 (Portal do Cliente) 100% Funcional.*
