# Auditoria — Fronteira do MVP (workflow_regente.xlsx · MacroWorkflow)

> Auditoria **read-only** das 23 macroetapas da aba `MacroWorkflow` do gabarito,
> cruzando cada uma com a prioridade declarada (MVP1 / MVP2 / Fase 2 / Fase 3)
> e o estado atual do código. Apenas constatação — sem opinião, proposta ou
> priorização própria.
>
> - **Working dir:** `c:\Users\Administrador\Desktop\Amigao_do_Meio_Ambiente`
> - **Branch:** `feat/dashboard-redesign-v2`
> - **Gabarito:** `c:\Users\Administrador\Desktop\workflow_regente.xlsx`, aba `MacroWorkflow` (fora do repo, lido só p/ referência)
> - **Data:** 2026-05-28
>
> Legenda de status: **EXISTE** = funcionalidade do gabarito presente e aderente · **PARCIAL** = presente com escopo menor que o gabarito · **FALTA** = ausente.

---

## Seção 1 — Tabela mestra (23 macroetapas)

| # | Macroetapa | Prioridade gabarito | Funcionalidade declarada (col D) | Status no código | Onde |
|---|---|---|---|---|---|
| 1 | Entrada da demanda | MVP 1 | Formulário inteligente de entrada, roteiro por tipo de demanda, intake que transforma conversa de WhatsApp/e-mail em caso estruturado (cliente, imóvel, urgência, tipo). | PARCIAL | IntakeWizard 6 passos + 5 EntryType: [frontend/src/pages/Intake/](frontend/src/pages/Intake/), [app/models/process.py:59-65](app/models/process.py#L59), [app/api/v1/intake.py:215-226](app/api/v1/intake.py#L215). Falta ingestão real de WhatsApp/e-mail (canal é só rótulo enum). |
| 2 | Diagnóstico inicial preliminar | MVP 1 *(anotação extra: "MVP 2")* | Classificação automática do caso, pré-diagnóstico, triagem por tipo de problema, sugestão de próximos passos, sinalização de coleta documental. | EXISTE | `intake_classifier`, `AtendimentoAgent` [app/agents/atendimento.py:18](app/agents/atendimento.py#L18), `RegulatoryDiagnosis` versionado [app/models/regulatory.py:182](app/models/regulatory.py#L182), `DemandType` enum + `urgency`, `ProcessChecklist` gerado por template de demand_type. |
| 3 | Coleta documental | MVP 1 | Checklist documental por tipo de caso, central de recebimento, leitura automática de anexos, alerta de documentos faltantes/vencidos/inconsistentes. | EXISTE | `ProcessChecklist` + [app/models/checklist_template.py](app/models/checklist_template.py); `Document` [app/models/document.py:32](app/models/document.py#L32) com `expires_at`/`ocr_status`; OCR pipeline + `ExtratorAgent` [app/agents/extrator.py:17](app/agents/extrator.py#L17); blockers em `can_advance_macroetapa` [app/models/macroetapa.py:415](app/models/macroetapa.py#L415); `RegulatoryIssue` catálogo [app/models/regulatory.py:298](app/models/regulatory.py#L298). |
| 4 | Diagnóstico técnico consolidado | MVP 1 | Dossiê automático do imóvel/cliente, leitura de matrícula/CCIR/CAR/laudos/histórico, checklist técnico por tipo, alerta de inconsistências. | EXISTE | `PropertyHub`/`ClientHub` (back+front); `DiagnosticoAgent` [app/agents/diagnostico.py:113](app/agents/diagnostico.py#L113) + `LegislacaoAgent` + `AuditorImovelAgent`; `RegulatoryIssue`/`RegulatoryIssueCatalog`; `RegulatoryDiagnosis.content` JSONB versionado. |
| 5 | Definição do caminho regulatório | MVP 1 | Motor de workflow por tipo de caso, com trilha sugerida, checklist, dependências e ordem recomendada de etapas. | PARCIAL | `LegislacaoAgent` produz `caminho_regulatorio` + etapas regulatórias [app/agents/legislacao.py:226](app/agents/legislacao.py#L226); `ProcessDecision` versiona decisão [app/models/process_decision.py:71](app/models/process_decision.py#L71); `MACROETAPA_TRANSITIONS` sequencia as 7 macroetapas globais. As 7 macroetapas são **fixas** para todos os `demand_type`s — não há trilha de execução variando por tipo de caso (apenas `ProcessChecklist` varia por template de demand_type). |
| 6 | Orçamento e negociação | MVP 1 | Geração assistida de proposta, estrutura de escopo por tipo de caso, precificação por complexidade, modelo de comunicação clara. | EXISTE | `OrcamentoAgent` [app/agents/orcamento.py:20](app/agents/orcamento.py#L20); `Proposal.scope_items`/`complexity`/`payment_terms` [app/models/proposal.py:22](app/models/proposal.py#L22); UI `ProposalEditor.tsx`/`ProposalList.tsx`; PDF generator. |
| 7 | Contrato e formalização | MVP 1 | Modelos inteligentes de contrato por tipo de serviço, preenchimento semiautomático com dados do cliente e escopo aprovado. | EXISTE | `ContractTemplate` [app/models/contract_template.py](app/models/contract_template.py); `Contract` [app/models/contract.py:21](app/models/contract.py#L21); `RedatorAgent` [app/agents/redator.py:42](app/agents/redator.py#L42); UI `ContractEditor.tsx`. |
| 8 | Estruturação da base de dados | MVP (sem variação) | Central documental única por cliente/imóvel/processo, classificação automática de documentos, cadastro estruturado de cliente, imóvel, credenciais e histórico. | PARCIAL | `Client`/`Property`/`Document` com FKs cruzadas e `field_sources` JSONB [app/models/property.py:38](app/models/property.py#L38); `AuditLog` hash-chained [app/models/audit_log.py:8](app/models/audit_log.py#L8). **Ausente:** modelo de "credenciais" (logins do cliente em portais de órgão). |
| 9 | Planejamento operacional, agenda e distribuição de tarefas | MVP 2 | Painel de tarefas (responsáveis, prazo, prioridade, status, **dependências**), alertas WhatsApp/e-mail e criação de tarefa com 1 clique a partir de nova informação. | PARCIAL | `Task` [app/models/task.py](app/models/task.py); `TasksTab.tsx` + `/api/v1/tasks`. **Ausentes:** dependências entre tarefas, alertas WhatsApp/e-mail, fluxo "1 clique a partir de nova informação", agenda/calendário. |
| 10 | Interação com parceiros | Fase 2 | Tarefas externas com prazo, checklist, entrega esperada, status por parceiro, vínculo com o processo principal. | FALTA | Sem entidade de parceiro/terceirizado, sem tarefa externa modelada com status por parceiro. |
| 11 | Campo e coleta in loco | MVP 2 | Modo offline para campo, sincronização posterior, upload automático de fotos/áudios/pontos/checklists. | PARCIAL | `mobile/` (Expo, SQLite offline-first) existe como código mas está **CONGELADO** por ADR-009. Sincronização e fluxo de upload não ativos. |
| 12 | Execução técnica | Fase 2 | Modelos inteligentes, pré-preenchimento com base nos dados cadastrados, apoio de IA para estrutura/revisão/organização técnica. | PARCIAL | `RedatorAgent` + `StageOutput` [app/models/stage_output.py:29](app/models/stage_output.py#L29); aba `SaidasTab.tsx`. **Ausente:** módulo dedicado de relatório/memorial/PRAD/petição com pré-preenchimento estruturado por tipo de peça. |
| 13 | Protocolo e submissão | MVP 2 | Checklist final de protocolo, conferência pré-envio, rastreabilidade dos documentos enviados, registro de data/protocolo, vínculo automático com a etapa. | PARCIAL | `ProcessStatus.protocolo`/`aguardando_orgao` + `destination_agency`/`external_protocol_number` [app/models/process.py:110-112](app/models/process.py#L110). **Ausentes:** checklist específico de protocolo, conferência pré-envio, módulo de rastreabilidade do envio. |
| 14 | Acompanhamento do processo | MVP 2 *(anotação extra: "Agente de monitoramento ativo de processo")* | Leitura automática de e-mails e retornos, vinculação ao cliente/processo correto, dashboard de status, fila do "o que mudou hoje", alertas ativos. | PARCIAL | `VigiaAgent` [app/agents/vigia.py:19](app/agents/vigia.py#L19) + `AcompanhamentoAgent` + Celery beat [app/core/celery_app.py](app/core/celery_app.py); dashboard de status; alertas em `Communication`. **Ausente:** leitura automática de e-mails do órgão (somente `intake_classifier` cita `whatsapp`/`email` como rótulo de canal). |
| 15 | Atendimento de pendências | MVP 2 | Resumo automático da notificação, quebra em subtarefas, responsáveis, prazo, lista de documentos, histórico de pendências parecidas. | PARCIAL | `ProcessStatus.pendencia_orgao`; `AcompanhamentoAgent`. **Ausentes:** quebra automática da pendência em subtarefas, histórico de "pendências similares". |
| 16 | Licença emitida e gestão de condicionantes | MVP 2 | Módulo de gestão de condicionantes/recorrências com calendário, alertas escalonados, responsáveis, prova de cumprimento, histórico. | FALTA | Texto "condicionantes" aparece em comentários ([app/agents/acompanhamento.py](app/agents/acompanhamento.py), [app/services/document_extractor.py](app/services/document_extractor.py), skill MD), sem modelo/módulo dedicado, sem calendário, sem alertas escalonados. |
| 17 | Renovação e recorrência | Fase 2 | Base histórica única com timeline, processos anteriores, documentos, credenciais, propriedades associadas, relacionamento com órgãos e parceiros. | PARCIAL | Timeline via `AuditLog`; `ClientHub`/`PropertyHub` mostram processos/documentos. **Ausentes:** workflow de renovação propriamente dito, modelo de credenciais, modelo de parceiros, modelo de relacionamento com órgão. |
| 18 | Comunicação com cliente | MVP 2 / Fase 2 *(anotação extra: "Portal do cliente desde o início")* | Relatório simples de status (andamento, pendências, próximos passos, pontos de atenção) para envio ao cliente. | PARCIAL | `client-portal/` (Next.js 16) existe como código mas está **CONGELADO** por ADR-009; modelo `Communication` [app/models/communication.py](app/models/communication.py) existe. **Ausente (ativo):** gerador de relatório de status estruturado para o cliente. |
| 19 | Inteligência regulatória | Fase 2 | Base regulatória inteligente com resumos, checklists por órgão/tipo de processo, alertas de atualização normativa. | PARCIAL | `LegislacaoAgent` + RAG `knowledge_catalog` [app/models/knowledge_catalog.py](app/models/knowledge_catalog.py) (Sprint W: 22.573 chunks MS/MT/GO/Federal); `LegislationAlert` [app/models/legislation_alert.py](app/models/legislation_alert.py). **Ausentes:** resumos e checklists estruturados por órgão+tipo de processo; loop de "alerta de atualização normativa" ativo. |
| 20 | Padronização por órgão/município | Fase 2 | Biblioteca de fluxos por órgão, município e tipo de licença, com histórico de prática operacional. | PARCIAL | Corpus SEMAD (282/283 PDFs) ingerido em `knowledge_catalog`. **Ausente:** biblioteca *de fluxos* (rito + checklist) estruturada por órgão+município+tipo de licença. |
| 21 | Aprendizado de precedentes | Fase 3 | Registro de precedentes internos ("como resolvemos antes"), vinculado a tipo de pendência, órgão e solução. | FALTA | Sem modelo de precedente nem vínculo pendência→solução. |
| 22 | Inteligência preditiva | Fase 3 | IA preditiva de próximo passo, risco de pendência, prazo provável e rota recomendada. | FALTA | `Process.risk_score` coluna existe [app/models/process.py:137](app/models/process.py#L137), sem motor preditivo. |
| 23 | Integrações externas | MVP no básico / Fase 3 no avançado | Integração com e-mail, Drive e WhatsApp no MVP; sistemas públicos e bases externas na Fase 3. | FALTA | `source_channel` é apenas rótulo enum (não ingestão integrada); sem cliente IMAP/Gmail/WhatsApp/Drive; sem integração ativa com SIGEF/SiCAR/MapBiomas no fluxo. |

---

## Seção 2 — Dentro do MVP1, o que falta

Macroetapas com prioridade **MVP1** (itens 1–8, sendo #8 como "MVP" sem número) cujo status no código é **PARCIAL** ou **FALTA**:

### Item 1 — Entrada da demanda (PARCIAL)

- **Existe:** Wizard de 6 passos com 5 cenários de `EntryType` ([frontend/src/pages/Intake/](frontend/src/pages/Intake/)); abertura de caso ([app/api/v1/intake.py:215-226](app/api/v1/intake.py#L215)) já com `client`, `property`, `urgency`, `demand_type` e macroetapa inicial `entrada_demanda`; roteiro de perguntas guiado pelo wizard.
- **Não existe:** ingestão real de WhatsApp/e-mail "transformando conversa em caso". O valor `whatsapp`/`email` aparece apenas como rótulo do enum `IntakeSource` ([app/models/process.py](app/models/process.py)) — não há cliente IMAP/WhatsApp Business API/webhook que receba mensagem e abra caso automaticamente.

### Item 5 — Definição do caminho regulatório (PARCIAL)

- **Existe:** geração do caminho regulatório pelo `LegislacaoAgent` ([app/agents/legislacao.py:226](app/agents/legislacao.py#L226)) com `etapas` regulatórias; versionamento da decisão via `ProcessDecision` ([app/models/process_decision.py:71](app/models/process_decision.py#L71)) com `supersedes_decision_id`; macroetapa `caminho_regulatorio` no enum; `MACROETAPA_TRANSITIONS` ordena as 7 macroetapas; `ProcessChecklist` é gerado por template de `demand_type`.
- **Não existe:** "motor de workflow por tipo de caso" como o gabarito descreve — as 7 macroetapas são **invariantes** para todos os `demand_type`s. Não há trilha de execução que mude por tipo de caso (CAR vs. licenciamento vs. PRAD vs. outorga vs. defesa têm a mesma sequência de macroetapas). A variação por `demand_type` cobre apenas o *conteúdo* do checklist documental, não o *fluxo* de etapas.

### Item 8 — Estruturação da base de dados (PARCIAL)

- **Existe:** central documental única por cliente/imóvel/processo ([app/models/document.py:32](app/models/document.py#L32) com FKs `client_id`/`property_id`/`process_id`); classificação automática (`document_type`/`document_category` via `ExtratorAgent`); cadastro estruturado de cliente ([app/models/client.py:24](app/models/client.py#L24)) e imóvel ([app/models/property.py:10](app/models/property.py#L10)); histórico em `AuditLog` com hash chain SHA-256.
- **Não existe:** modelo dedicado de **credenciais** (logins do cliente em portais de órgão — SEMAD, IBAMA, INCRA etc.) que o gabarito menciona explicitamente como parte da base estruturada.

> Itens MVP1 sem ressalva (status **EXISTE**): #2 Diagnóstico preliminar, #3 Coleta documental, #4 Diagnóstico técnico consolidado, #6 Orçamento, #7 Contrato.

---

## Seção 3 — Código que extrapola o MVP1

Funcionalidades **EXISTE** ou **PARCIAL** no código cuja prioridade no gabarito é MVP2, Fase 2 ou Fase 3 (esforço já realizado fora do recorte MVP1):

| # | Macroetapa | Prioridade gabarito | O que já está no código |
|---|---|---|---|
| 9 | Planejamento operacional / agenda / tarefas | MVP 2 | Modelo `Task` completo (responsável, prazo, prioridade, status), API `/tasks`, aba `TasksTab.tsx` no workspace. |
| 11 | Campo e coleta in loco | MVP 2 | `mobile/` (Expo + React Native + SQLite) existe como projeto, congelado por ADR-009. |
| 12 | Execução técnica (relatórios/peças) | Fase 2 | `RedatorAgent` ([app/agents/redator.py:42](app/agents/redator.py#L42)) gera peças textuais; `StageOutput` persiste saídas estruturadas; aba `SaidasTab.tsx` lista produtos por macroetapa. |
| 13 | Protocolo e submissão | MVP 2 | Estados `protocolo`/`aguardando_orgao` na `VALID_TRANSITIONS`; colunas `destination_agency` e `external_protocol_number` no modelo `Process` ([app/models/process.py:110-112](app/models/process.py#L110)). |
| 14 | Acompanhamento do processo | MVP 2 | `VigiaAgent` ([app/agents/vigia.py:19](app/agents/vigia.py#L19)) + `AcompanhamentoAgent`; Celery beat configurado; dashboard de status; modelo `Communication`; modelo `LegislationAlert`. |
| 15 | Atendimento de pendências | MVP 2 | Estado `pendencia_orgao` na máquina de estados; `AcompanhamentoAgent` registrado no chain de macroetapas. |
| 17 | Renovação e recorrência | Fase 2 | Timeline via `AuditLog` hash-chained; `ClientHub`/`PropertyHub` consolidam processos/documentos anteriores. |
| 18 | Comunicação com cliente | MVP 2 / Fase 2 | `client-portal/` (Next.js 16) existe como projeto, congelado por ADR-009; modelo `Communication` ativo. |
| 19 | Inteligência regulatória | Fase 2 | `LegislacaoAgent` + RAG sobre `knowledge_catalog` (Sprint W: 22.573 chunks MS/MT/GO/Federal embedados via OpenAI 768d); `LegislationAlert`; `legislation_monitor` ([app/services/legislation_monitor.py](app/services/legislation_monitor.py)). |
| 20 | Padronização por órgão/município | Fase 2 | Corpus SEMAD (282/283 PDFs) ingerido em `knowledge_catalog` com classify Gemini Flash; sub-pasta `legislacao/` com manuais SEMAD. |

> Itens **FALTA** cuja prioridade é MVP2/Fase 2/Fase 3 ficam fora desta seção (não há esforço a registrar): #10 parceiros, #16 condicionantes, #21 precedentes, #22 preditiva, #23 integrações.

---

## Seção 4 — Itens fora do gabarito

Funcionalidades encontradas no código que não correspondem a nenhuma macroetapa da aba `MacroWorkflow`:

| Item | Onde no código | Observação factual |
|---|---|---|
| Agente `auditor_imovel` | [app/agents/auditor_imovel.py:38](app/agents/auditor_imovel.py#L38) (`name="auditor_imovel"`) | Registrado no `AgentRegistry`; não consta nem na lista de 10 agentes da aba "Agentes" nem nos agentes esperados por macroetapa em `MACROETAPA_AGENTS`. |
| Catálogo evolutivo de issues regulatórias (matriz IPE) | `RegulatoryIssueCatalog` [app/models/regulatory.py:237](app/models/regulatory.py#L237) + `RegulatoryIssue` [app/models/regulatory.py:298](app/models/regulatory.py#L298) com `codigo_alerta`/`familia`/`severity`/`muda_rota_regulatoria`/`muda_escopo_preco_prazo`/`status_saneamento`/`decisao_consultor` | Taxonomia rica de achados regulatórios (com decisão contextual do consultor por achado, ADR-012). O gabarito menciona "alerta de inconsistências" e "leitura regulatória aplicada" como funcionalidade, mas não modela essa estrutura taxonômica com `codigo_alerta` + `familia` + 4 níveis de severidade. |
| Sistema de skills procedurais | [app/skills/](app/skills/) (Markdown + YAML compilados no system prompt — Forma A, ADR-006) | Templates procedurais por etapa/agente que vivem como arquivos `.md` no repo. A aba "Input" do gabarito descreve uma *metodologia* parecida, mas o sistema de skills materializado no código não está mapeado a nenhuma macroetapa específica. |
| Pré-cadastro / waitlist | [app/models/pre_cadastro.py](app/models/pre_cadastro.py); `/api/v1/waitlist` | Fila de espera pré-produto com integração Resend. Fora do fluxo das 23 macroetapas (pré-aquisição comercial). |
| Tenancy / multi-tenant | `Tenant` [app/models/tenant.py](app/models/tenant.py); `tenant_id` em toda query | Isolamento multi-tenant não é macroetapa do workflow operacional — é capacidade de stack. |
| Duplicidade `Process.status` × `Process.macroetapa` | Enum `ProcessStatus` 11 estados [app/models/process.py:10](app/models/process.py#L10) + coluna `macroetapa` String [app/models/process.py:133](app/models/process.py#L133) | O gabarito modela o fluxo como 23 macroetapas. O código carrega **dois eixos de estado** em paralelo no mesmo registro de `Process` — auditado em `docs/arquivo/auditorias/2026-05-27_auditoria_workflow.md` e em [`/tmp/impacto_pr3.md`] (PR-3 de unificação). |
| Pipeline OCR pilot-grade | [app/services/document_extractor.py](app/services/document_extractor.py); `app/workers/ocr_tasks.py` | pypdf + Gemini + OpenAI Vision com `AIJob` audit, cache SHA-256 e budget guard ($0.085/caso 8 PDFs). O gabarito cita "leitura automática de anexos" como funcionalidade mas não detalha o pipeline; o código tem profundidade própria aqui. |
| Aba `Decisões` do workspace | `ProcessDecision` [app/models/process_decision.py:71](app/models/process_decision.py#L71); `DecisionsTab.tsx` | Decisão contextual do consultor por macroetapa, com versionamento (`supersedes_decision_id`) e justificativa estruturada. ADR-012. Não é macroetapa do gabarito — é capacidade transversal de governança. |
