# Plano de Sprints — MVP 1 — Amigão do Meio Ambiente

> **Período:** 4 semanas (4 sprints de 1 semana)
> **Decisão de IA:** MVP 1 usa **regras estáticas + templates configuráveis** (sem LLM). LLM entra na Wave 2 (Sprint 5+). Isso derruba o esforço das tarefas 2 e 4 de 6–8 dias para 2–3 dias.
> **Stack:** FastAPI (backend) + React/Vite/Tailwind (frontend) — stack atual

---

## Fundação já pronta (não entra no esforço)

| O que já existe | Onde |
|----------------|------|
| Auth + RBAC + multi-tenant | `app/api/v1/auth.py` |
| CRUD Clients | `app/api/v1/clients.py` + model/schema |
| CRUD Properties | `app/api/v1/properties.py` |
| CRUD Processes + máquina de estados + timeline | `app/api/v1/processes.py` |
| CRUD Tasks + Kanban | `app/api/v1/tasks.py` |
| Upload/download documentos (MinIO presigned) | `app/api/v1/documents.py` |
| Worker Celery + notificações e-mail | `app/workers/` |
| Portal do cliente (Next.js) | `client-portal/` |
| Frontend: Auth, Dashboard, Clients, Processes, Properties | `frontend/src/pages/` |

---

## Sprint 1 — Intake Inteligente + Diagnóstico Inicial
**Semana 1 | Tarefas MVP: 1 e 2**

### Objetivo
Substituir a tela genérica de "criar processo" por um **wizard de intake guiado** que classifica o caso automaticamente por tipo de demanda usando regras, e sugere qual documentação coletar.

---

### Backend — Sprint 1

#### [MODIFY] `app/models/process.py`
- Adicionar campo `intake_source` (whatsapp / email / presencial / banco / cooperativa / parceiro)
- Adicionar campo `demand_type` (enum: car, licenciamento, regularizacao_fundiaria, outorga, defesa, compensacao, exigencia_bancaria, misto)
- Adicionar campo `initial_diagnosis` (Text — pré-diagnóstico gerado por regras)
- Adicionar campo `suggested_checklist_template` (String — ID do template de checklist sugerido)

#### [NEW] `app/models/checklist_template.py`
- Tabela `checklist_templates`: id, tenant_id (nullable = template global), demand_type, name, items (JSONB)
- Seed de templates padrão por tipo de demanda

#### [NEW] `app/models/process_checklist.py`
- Tabela `process_checklists`: id, process_id, template_id, items (JSONB com status por item), completed_at

#### [NEW] `app/services/intake_classifier.py`
- `classify_demand(process_type, description, urgency, source_channel) -> DemandClassification`
- Retorna: `demand_type`, `initial_diagnosis` (texto estruturado), `suggested_checklist_template_id`, `suggested_next_steps[]`
- Implementação: **regras estáticas** (tabela de mapeamento por tipo)

#### [NEW] `app/api/v1/intake.py`
- `POST /intake/classify` — recebe descrição livre e retorna classificação + diagnóstico + próximos passos
- `POST /intake/create-case` — cria cliente + processo + imóvel em uma transação (intake completo)
- `GET /intake/templates` — lista templates de checklist por tipo de demanda

#### [MODIFY] `app/api/v1/processes.py`
- `POST /processes/` agora aceita `intake_source` e `demand_type`
- `GET /processes/{id}` inclui `initial_diagnosis` e `suggested_next_steps`

#### [NEW] `alembic/versions/xxxx_intake_fields.py`
- Migration para novos campos e tabelas

---

### Frontend — Sprint 1

#### [NEW] `frontend/src/pages/Intake/IntakeWizard.tsx`
Wizard em 4 etapas:
1. **"Quem é o cliente?"** — busca cliente existente ou cria novo (nome, telefone, canal de origem)
2. **"Qual é a demanda?"** — campo de texto livre + seleção de urgência + tipo inicial → chama `POST /intake/classify` → exibe diagnóstico automático
3. **"O imóvel"** — vincula imóvel existente ou cadastra novo (nome, município, CAR básico)
4. **"Confirmar e abrir caso"** — resumo + `POST /intake/create-case`

#### [NEW] `frontend/src/pages/Intake/DiagnosisPanel.tsx`
- Componente que exibe: tipo de demanda classificado, diagnóstico inicial, documentos solicitados, próximos passos sugeridos

#### [MODIFY] `frontend/src/App.tsx`
- Rota `/intake` para o wizard
- Botão "Nova Demanda" no dashboard aponta para `/intake`

---

### Critério de aceite — Sprint 1
- [ ] Consultor abre `/intake`, preenche dados do cliente e descrição da demanda
- [ ] Sistema retorna classificação automática (tipo, diagnóstico, docs necessários)
- [ ] Caso é criado com cliente + imóvel + processo vinculados em uma ação
- [ ] Process criado já mostra `demand_type` e `initial_diagnosis` na tela de detalhe

---

## Sprint 2 — Checklist Documental + Central de Documentos
**Semana 2 | Tarefa MVP: 3**

### Objetivo
Criar o motor de checklist documental por tipo de caso: quando um processo é aberto, um checklist de documentos esperados é gerado automaticamente. O consultor vê o que falta, o cliente é alertado.

---

### Backend — Sprint 2

#### [NEW] `app/api/v1/checklists.py`
- `GET /processes/{id}/checklist` — retorna checklist atual do processo com status por item
- `POST /processes/{id}/checklist/generate` — gera/regenera checklist baseado no `demand_type`
- `PATCH /processes/{id}/checklist/items/{item_id}` — marca item como recebido / pendente / dispensado
- `GET /processes/{id}/checklist/gaps` — retorna documentos faltantes e alertas de prazo

#### [MODIFY] `app/models/document.py`
- Adicionar campo `checklist_item_id` (FK para o item do checklist que este documento satisfaz)
- Adicionar campo `expires_at` (DateTime — validade do documento)
- Adicionar campo `is_expired` (Boolean computed ou field)

#### [NEW] `app/workers/tasks.py` — nova task
- `check_document_expiry(process_id)` — verifica documentos próximos de vencer e emite alerta
- Agendada via Celery Beat para rodar diariamente

#### [NEW] `app/services/checklist_engine.py`
- `generate_checklist(process_id, demand_type) -> ProcessChecklist`
- `get_checklist_gaps(process_id) -> List[ChecklistGap]`
- `mark_item_satisfied(checklist_item_id, document_id)`

#### [MODIFY] `app/api/v1/documents.py`
- `POST /documents/confirm-upload` agora vincula automaticamente ao item de checklist correspondente (por `document_type`)
- `GET /documents?process_id=X` retorna documentos com status de checklist

---

### Frontend — Sprint 2

#### [NEW] `frontend/src/pages/Processes/ProcessChecklist.tsx`
- Painel lateral na tela de processo com checklist visual:
  - ✅ Recebido | ⏳ Pendente | ❌ Faltando | ⚠️ Vencendo
  - Botão "Solicitar ao cliente" por item (envia e-mail)
  - Upload direto por item do checklist

#### [MODIFY] `frontend/src/pages/Processes/ProcessDetail.tsx`
- Nova aba "Documentos" com checklist integrado
- Badge de gaps no header do processo ("3 documentos pendentes")

#### [NEW] `frontend/src/components/DocumentUploadZone.tsx`
- Componente de upload com drag-and-drop
- Categorização rápida por tipo (matrícula, CAR, CCIR, procuração, etc.)
- Vinculação automática ao item de checklist aberto

---

### Critério de aceite — Sprint 2
- [ ] Processo aberto com `demand_type = "car"` gera automaticamente checklist com itens esperados para CAR
- [ ] Upload de "matrícula.pdf" vincula automaticamente ao item "Matrícula do Imóvel"
- [ ] Dashboard mostra alerta quando processo tem documentos faltantes há mais de 5 dias
- [ ] Consultor consegue marcar item como "dispensado" com justificativa

---

## Sprint 3 — Diagnóstico Técnico + Caminho Regulatório
**Semana 3 | Tarefas MVP: 4 e 5**

### Objetivo
Criar o **dossiê automático do processo** (agregação de dados do imóvel + cliente + documentos) e o **motor de trilha regulatória** (sequência de etapas recomendadas por tipo de demanda).

---

### Backend — Sprint 3

#### [NEW] `app/models/workflow_template.py`
- Tabela `workflow_templates`: id, demand_type, name, steps (JSONB)
- Cada step: `{order, title, description, task_type, estimated_days, depends_on[]}`
- Seed de templates para: CAR, licenciamento, regularizacao_fundiaria, outorga, defesa, compensacao

#### [NEW] `app/services/workflow_engine.py`
- `apply_workflow_template(process_id, demand_type) -> List[Task]`
- Cria automaticamente as tarefas do processo na ordem correta, com dependências
- `get_recommended_path(process_id) -> WorkflowPath`

#### [NEW] `app/api/v1/workflows.py`
- `GET /workflows/templates` — lista templates disponíveis
- `GET /workflows/templates/{demand_type}` — detalhe do template
- `POST /processes/{id}/apply-workflow` — aplica trilha ao processo (cria tarefas)
- `GET /processes/{id}/workflow-status` — status da trilha atual (etapas concluídas, etapa atual, próximas)

#### [NEW] `app/services/dossier.py`
- `generate_dossier(process_id) -> ProcessDossier`
- Agrega: dados do cliente, dados do imóvel (CAR, CCIR, etc.), documentos recebidos, status do checklist, passivos identificados, histórico de processos anteriores
- `validate_technical_consistency(process_id) -> List[Inconsistency]`
- Regras básicas: CAR sem matrícula → alerta; imóvel sem georreferenciamento → alerta

#### [NEW] `app/api/v1/dossier.py`
- `GET /processes/{id}/dossier` — retorna dossiê agregado
- `GET /processes/{id}/inconsistencies` — lista inconsistências detectadas
- `POST /processes/{id}/dossier/refresh` — força re-análise

---

### Frontend — Sprint 3

#### [NEW] `frontend/src/pages/Processes/ProcessDossier.tsx`
- Aba "Diagnóstico" no detalhe do processo
- Seções: Dados do imóvel, Dados do cliente, Documentos recebidos (con status), Inconsistências detectadas (alertas visuais), Caminho regulatório sugerido

#### [NEW] `frontend/src/pages/Processes/WorkflowTimeline.tsx`
- Visualização da trilha regulatória: etapas em linha do tempo
- Etapa atual destacada, próximas etapas visíveis, concluídas marcadas
- Botão "Aplicar trilha" para invocar `POST /processes/{id}/apply-workflow`

#### [MODIFY] `frontend/src/pages/Processes/ProcessDetail.tsx`
- Nova aba "Diagnóstico" com dossiê + inconsistências
- Nova aba "Trilha" com workflow timeline

---

### Critério de aceite — Sprint 3
- [ ] Processo de tipo "CAR" exibe dossiê com todos os dados do imóvel e cliente agregados
- [ ] Inconsistência "matrícula ausente" aparece como alerta vermelho no diagnóstico
- [ ] Botão "Aplicar trilha CAR" cria automaticamente 6–8 tarefas na ordem correta
- [ ] WorkflowTimeline mostra etapa atual e próximas com prazos estimados

---

## Sprint 4 — Proposta Comercial + Contrato
**Semana 4 | Tarefas MVP: 6 e 7**

### Objetivo
Fechar o ciclo commercial: geração de proposta baseada no diagnóstico + geração de contrato com preenchimento semiautomático.

---

### Backend — Sprint 4

#### [NEW] `app/models/proposal.py`
- Tabela `proposals`: id, tenant_id, process_id, client_id, status (draft/sent/accepted/rejected/expired)
- Campos: `scope_items` (JSONB), `total_value`, `validity_days`, `payment_terms`, `notes`
- `version_number`, histórico de versões

#### [NEW] `app/models/contract.py`
- Tabela `contracts`: id, tenant_id, proposal_id, process_id, client_id
- Campos: `template_id`, `content` (TEXT preenchido), `status` (draft/sent/signed/cancelled)
- `signed_at`, `signed_by_client`, `pdf_storage_key`

#### [NEW] `app/models/contract_template.py`
- Tabela `contract_templates`: id, tenant_id (nullable = global), demand_type, name, content_template (TEXT com variáveis `{{cliente.nome}}`, etc.)
- Seed de templates para: CAR, licenciamento, regularizacao_fundiaria, consultoria_ambiental

#### [NEW] `app/services/proposal_generator.py`
- `generate_proposal_draft(process_id) -> ProposalDraft`
- Baseado em: `demand_type`, complexidade (nº de documentos, nº de etapas da trilha), urgência
- Retorna: itens de escopo sugeridos, valor estimado por faixa, prazo estimado

#### [NEW] `app/services/contract_generator.py`
- `generate_contract(proposal_id, template_id) -> Contract`
- Substitui variáveis no template com dados reais do cliente/processo/proposta
- `render_pdf(contract_id) -> storage_key` — gera PDF via ReportLab ou WeasyPrint

#### [NEW] `app/api/v1/proposals.py`
- `GET /proposals` — lista por tenant
- `POST /proposals` — criar proposta
- `GET /proposals/{id}` — detalhe
- `PATCH /proposals/{id}` — atualizar
- `POST /proposals/{id}/send` — marca como enviada (envia e-mail ao cliente)
- `POST /proposals/{id}/accept` / `/reject`
- `GET /proposals/generate-draft?process_id=X` — gera rascunho automático

#### [NEW] `app/api/v1/contracts.py`
- `GET /contracts` — lista
- `POST /contracts` — criar a partir de proposta aceita
- `GET /contracts/{id}` — detalhe
- `POST /contracts/{id}/generate-pdf` — gera/regenera PDF
- `GET /contracts/{id}/download` — URL de download do PDF

#### [NEW] `alembic/versions/xxxx_proposals_contracts.py`
- Migration para proposals, contracts, contract_templates

---

### Frontend — Sprint 4

#### [NEW] `frontend/src/pages/Proposals/ProposalList.tsx`
- Lista de propostas com status visual (rascunho / enviada / aceita / recusada)

#### [NEW] `frontend/src/pages/Proposals/ProposalEditor.tsx`
- Editor de proposta: itens de escopo, valores, prazo, condições
- Botão "Gerar rascunho automático" (chama o generator)
- Preview da proposta formatada

#### [NEW] `frontend/src/pages/Contracts/ContractEditor.tsx`
- Seleção de template, preview preenchido
- Botão "Gerar PDF" e "Enviar para cliente"

#### [MODIFY] `frontend/src/pages/Processes/ProcessDetail.tsx`
- Nova aba "Comercial" com acesso a propostas e contratos do processo

---

### Critério de aceite — Sprint 4
- [ ] Consultor abre processo e clica "Gerar proposta" → sistema sugere escopo e valor estimado
- [ ] Consultor edita e envia proposta → cliente recebe e-mail com link
- [ ] Proposta aceita → consultor clica "Gerar contrato" → sistema preenche template com dados reais
- [ ] PDF do contrato é gerado e disponível para download

---

## Sequência de execução por sprint

```
Semana 1 (Sprint 1):
  Backend:  intake classifier + create-case endpoint + migrations
  Frontend: IntakeWizard (4 etapas) + DiagnosisPanel

Semana 2 (Sprint 2):
  Backend:  checklist engine + document expiry worker + gaps API
  Frontend: ProcessChecklist + DocumentUploadZone

Semana 3 (Sprint 3):
  Backend:  workflow engine + dossier service + templates seed
  Frontend: ProcessDossier + WorkflowTimeline

Semana 4 (Sprint 4):
  Backend:  proposals + contracts + PDF generator
  Frontend: ProposalEditor + ContractEditor
```

---

## Decisões de arquitetura

> [!IMPORTANT]
> **IA no MVP 1:** Regras estáticas. O `intake_classifier.py` usa uma tabela de mapeamento Python, não LLM. O `proposal_generator.py` usa faixas de preço por tipo de demanda. Isso torna o MVP previsível, auditável e sem custo de token.

> [!NOTE]
> **LLM entra na Wave 2 (Sprint 5+):** classificação semântica de texto livre, extração de CAR/matrícula via OCR+LLM, geração de proposta por IA, agente atendente.

> [!NOTE]
> **PDF:** usar `weasyprint` (HTML→PDF) ou `reportlab`. WeasyPrint é mais simples para templates HTML. Adicionar ao `requirements.txt`.

> [!WARNING]
> **Assinatura eletrônica:** fora do MVP 1. Contrato é gerado como PDF, enviado por e-mail. Integração com DocuSign/D4Sign entra na Wave 2.

---

## Open Questions para aprovação

1. **Precificação da proposta:** quer que o sistema sugira valores por faixa (baixa/média/alta complexidade) ou que o consultor preencha do zero?
2. **Templates de contrato:** vou criar 4 templates genéricos (CAR, licenciamento, fundiário, consultoria). Quer revisar/aprovar os templates antes de eu codificar?
3. **Checklist de documentos por tipo:** vou sedar checklists para os 7 tipos de demanda. Quer validar a lista de documentos antes?
4. **Portal do cliente:** o cliente vai acessar propostas pelo portal já na sprint 4 ou só na Wave 2?
