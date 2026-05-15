# Diagnóstico MVP 1 — Amigão do Meio Ambiente
**Data:** 01/04/2026 | **Status:** Análise de lacunas vs. entrega

---

## O que o MVP 1 exige (7 tarefas do usuário)

| # | Tarefa | O que o sistema precisa entregar |
|---|--------|----------------------------------|
| 1 | Entrada da demanda | Formulário inteligente, intake estruturado de WhatsApp/e-mail, caso vinculado a cliente + imóvel + urgência + tipo |
| 2 | Diagnóstico inicial | Classificação automática, pré-diagnóstico IA, triagem por tipo de problema, sugestão de próximos passos |
| 3 | Coleta documental | Checklist por tipo de caso, central de documentos, leitura de anexos, alertas de docs faltantes/vencidos |
| 4 | Diagnóstico técnico | Dossiê automático imóvel/cliente, leitura CAR/matrícula/CCIR, checklist técnico, alerta de inconsistências |
| 5 | Caminho regulatório | Motor de workflow por tipo de caso, trilha sugerida, dependências, ordem de etapas |
| 6 | Orçamento e negociação | Geração assistida de proposta, precificação por complexidade, comunicação clara |
| 7 | Contrato e formalização | Modelos de contrato por serviço, preenchimento semiautomático |

---

## O que o sistema JÁ TEM (stack atual)

### ✅ Infraestrutura e Fundação (100% pronta)
- FastAPI + PostgreSQL/PostGIS + Redis + MinIO + Celery — stack integrada e homologada
- Multi-tenant com isolamento por `tenant_id`
- JWT + RBAC operacional
- Alembic migrations validadas (smoke com rollback completo)
- Worker assíncrono operacional com observabilidade Prometheus
- SMTP real homologado (Gmail TLS)
- Upload/download de documentos via presigned URL — validado ponta a ponta
- Portal do cliente (Next.js) — autenticação e timeline funcionando
- App mobile offline (React Native + SQLite + sync queue)
- 25+ testes passando na suíte

### ✅ Modelos de Dados já existentes
- `Client`, `Property`, `Process`, `Task`, `Document`, `AuditLog`, `Communication`, `Tenant`, `User`

### ✅ Endpoints já implementados

| Domínio | Endpoints |
|---------|-----------|
| Auth | login, refresh, logout, me |
| Clients | CRUD completo |
| Properties | CRUD + geometry |
| Processes | CRUD + status + timeline + tarefas + documentos |
| Tasks | CRUD + kanban + move + assign + complete |
| Documents | upload-url, confirm-upload, GET, download-url |
| Threads | CRUD básico |

### ✅ Frontend já implementado
- Páginas: Auth, Dashboard, Clients, Processes, Properties

---

## Gap Analysis por Tarefa do MVP 1

### Tarefa 1 — Entrada da Demanda
> **Status: 🟡 Parcialmente pronto**

| Componente | Status | O que falta |
|------------|--------|-------------|
| Cadastro de cliente | ✅ API pronta | Formulário guiado com roteiro por tipo de demanda |
| Cadastro de processo | ✅ API pronta | Wizard de intake inteligente (não é apenas um form CRUD) |
| Vinculação cliente/imóvel/processo | ✅ Modelo pronto | UI de criação conectada e com seleção guiada |
| Intake via WhatsApp/e-mail | ❌ Não existe | Parser de conversa → caso estruturado (IA) |
| Campo "urgência" e "origem" no processo | ⚠️ Verificar | urgency no modelo; campo origem do cliente |

**Esforço para fechar:** 3–5 dias (wizard de intake no frontend + campo origem melhorado)

---

### Tarefa 2 — Diagnóstico Inicial Preliminar
> **Status: 🔴 Não implementado**

| Componente | Status | O que falta |
|------------|--------|-------------|
| Classificação automática do caso | ❌ | Integração com LLM para classificar tipo de problema |
| Pré-diagnóstico IA | ❌ | Agente classificador (worker Celery + LLM) |
| Sugestão de próximos passos | ❌ | Motor de regras ou LLM para sugerir ações |
| Triagem por tipo (ambiental/fundiário/hídrico/bancário/misto) | ❌ | Enum e lógica de classificação |
| Sinalização de coleta documental necessária | ❌ | Regras por tipo de processo |

**Esforço para fechar:** 5–7 dias (worker IA + LLM + UI de resultado do diagnóstico)

---

### Tarefa 3 — Coleta Documental
> **Status: 🟡 Base pronta, lógica inteligente faltando**

| Componente | Status | O que falta |
|------------|--------|-------------|
| Recebimento de documentos | ✅ | Upload presigned URL funcional |
| Categorização de documentos | ⚠️ | Campo `document_type` existe mas sem categorias padronizadas por tipo de caso |
| Checklist de documentos por tipo de caso | ❌ | Não existe — precisa de tabela de templates de checklist |
| Alerta de documentos faltantes | ❌ | Lógica de comparação checklist vs. documentos enviados |
| Alerta de documentos vencidos | ❌ | Campo de validade + worker de verificação |
| Leitura automática de anexos (OCR) | ❌ | OCR ainda não implementado (previsto no backlog) |
| Central de recebimento organizada na UI | ⚠️ | Tela de documentos existe mas sem visão de checklist |

**Esforço para fechar:** 4–6 dias (checklist engine + alertas + UI melhorada)

---

### Tarefa 4 — Diagnóstico Técnico Consolidado
> **Status: 🔴 Não implementado**

| Componente | Status | O que falta |
|------------|--------|-------------|
| Dossiê automático do imóvel/cliente | ❌ | Agregação automática de dados do processo |
| Leitura de matrícula, CAR, CCIR por IA | ❌ | OCR + LLM extrator de documentos fundiários |
| Checklist técnico por tipo de caso | ❌ | Templates de análise técnica |
| Alerta de inconsistências | ❌ | Motor de validação cruzada |
| Cruzamento com Prodes/MapBiomas | ❌ | Integração futura (não é MVP 1 estrito) |

**Esforço para fechar (versão MVP, sem integrações gov):** 6–8 dias (extrator IA + dossiê UI)

---

### Tarefa 5 — Definição do Caminho Regulatório
> **Status: 🔴 Não implementado**

| Componente | Status | O que falta |
|------------|--------|-------------|
| Motor de workflow por tipo de caso | ❌ | Engine de trilha = regras + tipo de processo |
| Trilha sugerida com dependências | ❌ | Modelo de template de trilha por tipo |
| Checklist de etapas | ⚠️ | Tasks existem, mas sem trilha pré-definida por tipo |
| Ordem recomendada de etapas | ❌ | Sequenciamento automático de tarefas |

**Esforço para fechar:** 4–5 dias (workflow engine baseado em templates de trilha)

---

### Tarefa 6 — Orçamento e Negociação
> **Status: 🔴 Não implementado (modelo existe no backlog)**

| Componente | Status | O que falta |
|------------|--------|-------------|
| Geração de proposta | ❌ | Endpoints /proposals ainda não implementados |
| Precificação por complexidade | ❌ | Lógica de estimativa de custo por tipo/escopo |
| Comunicação clara para agricultor | ❌ | Template de proposta simplificado |
| Geração assistida por IA | ❌ | Agente redator (fase posterior) |

**Esforço para fechar (versão manual, sem IA full):** 4–5 dias (CRUD proposta + UI de geração)

---

### Tarefa 7 — Contrato e Formalização
> **Status: 🔴 Não implementado**

| Componente | Status | O que falta |
|------------|--------|-------------|
| Modelos de contrato por tipo de serviço | ❌ | Templates de contrato em banco/storage |
| Preenchimento semiautomático | ❌ | Substituição de variáveis com dados do cliente/processo |
| Envio para assinatura | ❌ | Integração com provedor de assinatura eletrônica |
| Controle de status e versões | ❌ | Endpoint /contracts + workflow de aprovação |

**Esforço para fechar (versão sem assinatura eletrônica integrada):** 4–5 dias (CRUD contrato + templates + UI de geração PDF)

---

## Resumo Executivo de Gaps

| Tarefa | Status | Esforço estimado |
|--------|--------|-----------------|
| 1. Entrada da demanda | 🟡 60% pronto | 3–5 dias |
| 2. Diagnóstico inicial IA | 🔴 10% pronto | 5–7 dias |
| 3. Coleta documental | 🟡 40% pronto | 4–6 dias |
| 4. Diagnóstico técnico IA | 🔴 5% pronto | 6–8 dias |
| 5. Caminho regulatório | 🔴 15% pronto | 4–5 dias |
| 6. Orçamento/proposta | 🔴 0% pronto | 4–5 dias |
| 7. Contrato | 🔴 0% pronto | 4–5 dias |

**Total de esforço:** ~30–41 dias de desenvolvimento efetivo

---

## Premissas e Riscos

> [!IMPORTANT]
> As tarefas 2 e 4 dependem de integração com LLM (OpenAI/Gemini). Para MVP 1, é possível fazer versões simplificadas com **regras estáticas** (sem IA) que reduzem o esforço para ~3 dias cada.

> [!WARNING]
> A tarefa 7 (contrato) incluindo assinatura eletrônica integrada adiciona 3–5 dias extras. No MVP 1 pode-se gerar PDF assinável manualmente.

> [!NOTE]
> A infraestrutura (banco, worker, storage, auth) está 100% sólida. Todo o esforço restante é de **produto/feature**, não de infra.

---

## Plano de Entrega Sugerido — MVP 1

### Com apenas 1 desenvolvedor full-time
**Prazo realista: 8–10 semanas** (assumindo IA simplificada/regras)

### Com 2 desenvolvedores (1 backend + 1 frontend)
**Prazo realista: 5–6 semanas**

### Versão "MVP 1 Lite" (IA como regras, sem assinatura eletrônica)
**Prazo realista: 3–4 semanas** com 2 desenvolvedores focados

---

## Sequência de Execução Recomendada

```
Semana 1–2:
  - Wizard de intake (Tarefa 1) — frontend + pequenos ajustes no backend
  - Checklist documental + alertas (Tarefa 3) — backend engine

Semana 3–4:
  - Classificador de caso (Tarefa 2) — versão com regras estáticas primeiro
  - Motor de trilha regulatória (Tarefa 5) — templates de workflow por tipo

Semana 5–6:
  - Dossiê técnico (Tarefa 4) — agregação + UI de diagnóstico
  - CRUD de proposta (Tarefa 6) — backend + UI

Semana 7–8 (se necessário):
  - Contrato e geração de PDF (Tarefa 7)
  - Integração LLM para diagnóstico assistido (Tarefas 2 e 4)
  - Testes integrados + ajustes finais
```
