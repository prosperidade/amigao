# Auditoria — Código vs. `workflow_regente.xlsx`

> Auditoria **read-only** do código contra o gabarito de 8 abas. Apenas
> constatação (EXISTE / PARCIAL / FALTA), sem opinião, proposta, priorização
> ou comparação externa. Nenhum arquivo/branch/banco foi tocado.
>
> - **Working dir:** `c:\Users\Administrador\Desktop\Amigao_do_Meio_Ambiente`
> - **Branch:** `feat/dashboard-redesign-v2`
> - **Gabarito:** `c:\Users\Administrador\Desktop\workflow_regente.xlsx` (fora do repo, lido só p/ referência)
> - **Data:** 2026-05-27
>
> Legenda: **EXISTE** = presente e aderente · **PARCIAL** = presente com divergência de campo/papel/conteúdo · **FALTA** = ausente.

---

## 1. Entidades (aba "Modelagem de entidades")

| Item | Status | Onde no código | Observação factual |
|---|---|---|---|
| Cliente | EXISTE | [app/models/client.py:24](app/models/client.py#L24) | Campos do gabarito presentes: tipo PF/PJ, nome/razão social (`full_name`/`legal_name`), `cpf_cnpj`, `phone`, `email`, `status`, `created_at`. Falta `endereço` como campo dedicado (existe `notes`/`extra_json`); falta `responsável interno` dedicado. Relações: `1 cliente→N processes` ✓; não há relação direta `cliente→imóveis`/`→contratos`/`→documentos` em `Client` (FK mora no lado filho). |
| Imóvel | EXISTE | [app/models/property.py:10](app/models/property.py#L10) | Presentes: `name`, `registry_number` (matrícula), `car_code`, `total_area_ha`, `municipality`, `state`, `biome`, `geom` (centroide/polígono SRID 4674), `status`, `car_status`/`rl_status` (situação regulatória). Falta `situação fundiária` como campo nomeado (há `tipologia`, `strategic_notes`). Relações: `cliente_id` ✓; relações `imóvel→documentos/casos/diagnósticos/eventos` via FK no lado filho. |
| Caso | EXISTE | [app/models/process.py:91](app/models/process.py#L91) (`Process`) | Presentes: `client_id`, `property_id`, `demand_type`, `status`, `macroetapa` (etapa atual), `responsible_user_id`, `opened_at`, `updated_at`. `objetivo real` → `initial_summary`/`ai_summary` (não há campo "objetivo" nomeado); `urgency` ✓. Tabela chamada `processes`, não "casos". Relações com documentos/propostas/contratos/diagnósticos/AIJob via FK no lado filho. |
| Documento | EXISTE | [app/models/document.py:32](app/models/document.py#L32) | Presentes: `client_id`, `property_id`, `process_id`, `document_type`, `original_file_name`, `source`, `created_at`, `ocr_status`/`extraction_status` (status de leitura), `expires_at`, `version_number`, `extracted_text`. `status de validade` → `expires_at`/`review_required`. Metadados + extração + validação presentes. |
| Diagnóstico | PARCIAL | [app/models/regulatory.py:182](app/models/regulatory.py#L182) (`RegulatoryDiagnosis`) | Versionado (`version`), `process_id`, `content` (JSONB), `validated_by_user_id`/`validated_at`. **Sem** `imovel_id` direto (liga por `process_id`). A distinção gabarito "diagnóstico preliminar × técnico consolidado" não é coluna; ambos cabem no mesmo modelo via `content`/`macroetapa` de origem. |
| Caminho regulatório | PARCIAL | sem entidade dedicada; vive em [app/models/process_decision.py:71](app/models/process_decision.py#L71), [app/models/stage_output.py:29](app/models/stage_output.py#L29), schema [app/schemas/enquadramento.py:39](app/schemas/enquadramento.py#L39) | Não há tabela `caminho_regulatorio` com `caminho_id`/`rota_principal`/`rota_alternativa`/`justificativa`/`versão`. O caminho é produzido pelo `LegislacaoAgent` ([app/agents/legislacao.py:226](app/agents/legislacao.py#L226)) como string `caminho_regulatorio` e persistido como `StageOutput` e/ou `ProcessDecision` (`decision_type`, `decision_text`, `justification`, `next_step`, `supersedes_decision_id` p/ versionamento). Campos "rota principal/alternativa" do gabarito não têm colunas próprias. |
| Proposta | EXISTE | [app/models/proposal.py:22](app/models/proposal.py#L22) | Presentes: `process_id` (caso), `version_number`, `status`, `total_value` (valor), `validity_days` (prazo), `payment_terms` (forma de pagamento), `sent_at`/`accepted_at`. `complexity` ✓. Relação `1 caso→N propostas` ✓. |
| Contrato | EXISTE | [app/models/contract.py:21](app/models/contract.py#L21) | Presentes: `process_id` (caso), `proposal_id` (proposta-base), `status`, `created_at` (geração), `sent_at` (envio), `signed_at` (assinatura). Falta `version` explícita. Relação `contrato→1 proposta` ✓. |
| Histórico / Timeline | PARCIAL | [app/models/audit_log.py:8](app/models/audit_log.py#L8) (`AuditLog`) | Genérico via `entity_type`+`entity_id` (não há colunas dedicadas `cliente_id`/`imovel_id`/`caso_id`). Tem `action`, `old_value`/`new_value`, `details`, `created_at`, `user_id`, e hash chain (`hash_sha256`/`hash_previous`). `origem (humano/IA/sistema)` não é coluna nomeada (inferida por `action`/`user_id`). |
| Execução do Agente de IA | EXISTE | [app/models/ai_job.py:46](app/models/ai_job.py#L46) (`AIJob`) | Presentes: `entity_type`/`entity_id` (caso/imóvel), `agent_name`, `input_payload` (entrada), `result`/`raw_output` (saída), `status`, `model_used`/`provider`/`tokens_in`/`tokens_out`/`cost_usd`, `chain_trace_id`. `score de confiança` e `validação humana` não são colunas próprias do AIJob (confiança vive em saídas estruturadas/StageOutput). |
| Checklist / Ação da etapa | EXISTE | [app/models/macroetapa.py:312](app/models/macroetapa.py#L312) (`MacroetapaChecklist`) | `process_id`, `macroetapa` (etapa), `actions` (JSONB: `id`/`label`/`completed`/`completed_at`/`needs_human_validation`/`validated_at`/`validated_by_user_id`), `completion_pct`, `state`. `origem (manual/IA)` via `agent_suggestion` no item; `responsável`/`data prevista` não são campos nomeados por ação. |
| Campo extraído / dado estruturado | PARCIAL | sem entidade dedicada; `field_sources` JSONB em [app/models/client.py:46](app/models/client.py#L46) e [app/models/property.py:38](app/models/property.py#L38) | Não há tabela `campo_extraido` com `campo_extraido_id`/`documento_id`/`confiança`/`validado por humano`. Procedência de campo é gravada como JSONB `field_sources` em Cliente/Imóvel; texto bruto em `Document.extracted_text`. Rastreabilidade por campo individual não tem modelo próprio. |

---

## 2. Agentes (aba "Agentes")

Registro: `@AgentRegistry.register` em [app/agents/base.py:69](app/agents/base.py#L69); papel principal/secundário por etapa em `MACROETAPA_AGENTS` [app/models/macroetapa.py:209](app/models/macroetapa.py#L209).

| Item | Status | Onde no código | Observação factual |
|---|---|---|---|
| atendimento | PARCIAL | [app/agents/atendimento.py:18](app/agents/atendimento.py#L18) `name="atendimento"` | Gabarito: principal Etapa 1, secundária 2. Código: **primary** tanto em `entrada_demanda`(1) quanto em `diagnostico_preliminar`(2) — na etapa 2 é primary no código, secundária no gabarito. |
| extrator | EXISTE | [app/agents/extrator.py:17](app/agents/extrator.py#L17) | Gabarito: principal 3, sec 1,2,4. Código: primary em `coleta_documental`(3); secondary em entrada_demanda(1), diagnostico_preliminar(2), diagnostico_tecnico(4). Bate. |
| diagnostico | PARCIAL | [app/agents/diagnostico.py:113](app/agents/diagnostico.py#L113) | Gabarito: principal 4, sec 2,5. Código: primary em `diagnostico_tecnico`(4) ✓ e secondary em `caminho_regulatorio`(5) ✓; porém também é **primary** em `diagnostico_preliminar`(2), onde gabarito espera secundária. |
| legislacao | EXISTE | [app/agents/legislacao.py:84](app/agents/legislacao.py#L84) | Gabarito: principal 5, sec 2,4,7. Código: primary em `caminho_regulatorio`(5); secondary em diagnostico_preliminar(2), diagnostico_tecnico(4), contrato_formalizacao(7). Bate. |
| orcamento | PARCIAL | [app/agents/orcamento.py:20](app/agents/orcamento.py#L20) | Gabarito: principal 6, sec 5. Código: primary em `orcamento_negociacao`(6); **não** aparece como secundário em `caminho_regulatorio`(5). Secundária 5 ausente. |
| financeiro | PARCIAL | [app/agents/financeiro.py:22](app/agents/financeiro.py#L22) | Gabarito: principal 6, secundária 7. Código: **primary** em `orcamento_negociacao`(6) e em `contrato_formalizacao`(7) — na 7 é primary no código, secundária no gabarito. |
| redator | EXISTE | [app/agents/redator.py:42](app/agents/redator.py#L42) | Gabarito: principal 7, sec 6,5,4. Código: primary em `contrato_formalizacao`(7); secondary em diagnostico_tecnico(4), caminho_regulatorio(5), orcamento_negociacao(6). Bate. |
| acompanhamento | EXISTE | [app/agents/acompanhamento.py:20](app/agents/acompanhamento.py#L20) | Gabarito: transversal, sec 3,5,6,7. Código: secondary em coleta_documental(3), caminho_regulatorio(5), orcamento_negociacao(6), contrato_formalizacao(7). Bate. |
| vigia | PARCIAL | [app/agents/vigia.py:19](app/agents/vigia.py#L19) | Gabarito: transversal, Etapas 1 a 7. Código: secondary apenas em entrada_demanda(1), coleta_documental(3), orcamento_negociacao(6), contrato_formalizacao(7) — **ausente** em diagnostico_preliminar(2), diagnostico_tecnico(4), caminho_regulatorio(5). |
| marketing | EXISTE | [app/agents/marketing.py:18](app/agents/marketing.py#L18) | Gabarito: fora do fluxo do caso. Código: registrado no AgentRegistry mas **não** consta em nenhuma etapa de `MACROETAPA_AGENTS`. Bate (fora do fluxo). |

> Os 10 agentes do gabarito estão **todos registrados**. Há ainda `auditor_imovel` ([app/agents/auditor_imovel.py:38](app/agents/auditor_imovel.py#L38)) registrado, que não consta no gabarito.

---

## 3. Telas (aba "Telas Macro")

Rotas em [frontend/src/App.tsx:44-59](frontend/src/App.tsx#L44); menu em [frontend/src/layouts/PrivateLayout.tsx:46](frontend/src/layouts/PrivateLayout.tsx#L46).

| Item | Status | Onde no código | Observação factual |
|---|---|---|---|
| 1. Cadastro | EXISTE | `/intake` → [frontend/src/pages/Intake/](frontend/src/pages/Intake/) (`IntakeWizard`) ([App.tsx:53](frontend/src/App.tsx#L53)) | Wizard de entrada com tipos de entrada, upload (`DraftDocumentUploader.tsx`) e leitura por IA. Não está no menu lateral (acesso por rota). |
| 2. Dashboard | EXISTE | `/dashboard` → [frontend/src/pages/Dashboard/index.tsx](frontend/src/pages/Dashboard/index.tsx) ([App.tsx:45](frontend/src/App.tsx#L45)) | Mostra KPIs, casos por etapa/status, alertas, gargalos. Há também `DashboardRegente.tsx`/`DashboardOperacionalRegente.tsx` no diretório. Bate com o gabarito (KPIs, gargalos, alertas, leitura executiva). |
| 3. Cliente Hub | EXISTE | `/clients/:id` → [frontend/src/pages/Clients/ClientHub.tsx](frontend/src/pages/Clients/ClientHub.tsx) ([App.tsx:50](frontend/src/App.tsx#L50)) | Cabeçalho + status + imóveis vinculados + contratos + timeline. Bate. |
| 4. Imóvel Hub | EXISTE | `/properties/:id` → [frontend/src/pages/Properties/PropertyHub.tsx](frontend/src/pages/Properties/PropertyHub.tsx) ([App.tsx:52](frontend/src/App.tsx#L52)) | Identificação + status regulatório + casos vinculados (`macroetapa_label`). Bate. |
| 5. Fluxo de trabalho | EXISTE | `/processes` → [frontend/src/pages/Processes/index.tsx](frontend/src/pages/Processes/index.tsx) (Quadro de Ações / `QuadroAcoes.tsx`) ([App.tsx:47](frontend/src/App.tsx#L47)) | Kanban pelas 7 macroetapas (`MACROETAPA_COLORS`/`quadro-types.ts`). Bate com as 7 etapas do gabarito. |
| 6. Workspace do caso | EXISTE | `/processes/:id` → [frontend/src/pages/Processes/ProcessDetail.tsx](frontend/src/pages/Processes/ProcessDetail.tsx) ([App.tsx:48](frontend/src/App.tsx#L48)) | Identidade do caso, stepper de etapas (`MacroetapaStepper`), abas Documentos/Diagnóstico/Decisões/Saídas/Tasks, painel da etapa (`WorkspaceRightPanel`). Bate. |
| 7. Agentes IA | EXISTE | `/agents` → [frontend/src/pages/AI/AgentsPage.tsx](frontend/src/pages/AI/AgentsPage.tsx) ([App.tsx:58](frontend/src/App.tsx#L58)) | Lista de agentes, status, execuções. Há também `AIPanel.tsx`. Bate. |
| 8. Configurações | PARCIAL | `/settings` → [frontend/src/pages/Settings/index.tsx:93](frontend/src/pages/Settings/index.tsx#L93) ([App.tsx:59](frontend/src/App.tsx#L59)) | Abas presentes: Perfil, Assinatura/Pagamento (stub, [index.tsx:307](frontend/src/pages/Settings/index.tsx#L307)), Notificações/alertas, preferências de IA. **Ausentes** vs. gabarito: usuários e permissões, responsáveis, tipos de demanda, tags, integrações, templates, automações. |

---

## 4. Macroetapas (abas "MVP1" e "Regras por etapa")

Ordem em `MACROETAPA_ORDER` [app/models/macroetapa.py:32-59](app/models/macroetapa.py#L32); agentes em `MACROETAPA_AGENTS` [app/models/macroetapa.py:209](app/models/macroetapa.py#L209); gate em `can_advance_macroetapa` [app/models/macroetapa.py:415](app/models/macroetapa.py#L415).

| Item | Status | Onde no código | Observação factual |
|---|---|---|---|
| 1. Entrada da demanda | EXISTE | `Macroetapa.entrada_demanda` [macroetapa.py:34](app/models/macroetapa.py#L34) | Agentes código: primary `agent_atendimento`; sec `agent_extrator,agent_vigia`. Gabarito agente sugerido: Intake/Identificação. Alinhado. |
| 2. Diagnóstico preliminar | EXISTE | `Macroetapa.diagnostico_preliminar` [macroetapa.py:35](app/models/macroetapa.py#L35) | Agentes código: primary `agent_atendimento,agent_diagnostico`; sec `agent_legislacao,agent_extrator`. Gabarito: atendimento principal aqui (sec), diagnóstico sec. Divergência de papel (ver §2). |
| 3. Coleta documental | EXISTE | `Macroetapa.coleta_documental` [macroetapa.py:36](app/models/macroetapa.py#L36) | Agentes código: primary `agent_extrator`; sec `agent_vigia,agent_acompanhamento`. Bate com gabarito (extrator principal). |
| 4. Diagnóstico técnico consolidado | EXISTE | `Macroetapa.diagnostico_tecnico` [macroetapa.py:37](app/models/macroetapa.py#L37) | Agentes código: primary `agent_diagnostico`; sec `agent_extrator,agent_legislacao,agent_redator`. Bate (diagnostico principal). |
| 5. Definição do caminho regulatório | EXISTE | `Macroetapa.caminho_regulatorio` [macroetapa.py:38](app/models/macroetapa.py#L38) | Agentes código: primary `agent_legislacao`; sec `agent_diagnostico,agent_redator,agent_acompanhamento`. Gabarito espera `orcamento` como sec 5 — ausente (ver §2). |
| 6. Orçamento e negociação | EXISTE | `Macroetapa.orcamento_negociacao` [macroetapa.py:39](app/models/macroetapa.py#L39) | Agentes código: primary `agent_orcamento,agent_financeiro`; sec `agent_redator,agent_acompanhamento,agent_vigia`. Bate (orcamento/financeiro). |
| 7. Contrato e formalização | EXISTE | `Macroetapa.contrato_formalizacao` [macroetapa.py:40](app/models/macroetapa.py#L40) | Agentes código: primary `agent_redator,agent_financeiro`; sec `agent_legislacao,agent_acompanhamento,agent_vigia`. Bate (redator principal). |
| Gate `can_advance` cobre "Regras por etapa" | PARCIAL | [app/models/macroetapa.py:415-429](app/models/macroetapa.py#L415) + [app/api/v1/processes.py:437](app/api/v1/processes.py#L437) | O gate valida apenas: `completion_pct >= 1.0` (checklist genérico), documentos obrigatórios pendentes (`ProcessChecklist`) e validação humana pendente. **Não** codifica as regras legais/técnicas/normativas específicas que a aba "Regras por etapa" exige (ex.: procuração p/ cancelamento CAR, checagem SIGEF/MapBiomas, pré-requisitos legais entre etapas). As ações por etapa (`DEFAULT_ACTIONS` [macroetapa.py:250](app/models/macroetapa.py#L250)) são checklist genérico, não regras por tipo de demanda. |

> As 7 macroetapas do gabarito (MVP1) existem 1:1 no enum. Há **2 chains paralelas** etapa→agente além de `MACROETAPA_AGENTS`: `MACROETAPA_AGENT_CHAIN` [macroetapa.py:195](app/models/macroetapa.py#L195) e `MACROETAPA_CHAINS` [app/agents/orchestrator.py:70](app/agents/orchestrator.py#L70).

---

## 5. Cadastro — Camada 1 (aba "CAMADA 1 - ENTRADA")

| Item | Status | Onde no código | Observação factual |
|---|---|---|---|
| 1. Tipo de entrada | EXISTE | `EntryType` [app/models/process.py:59-65](app/models/process.py#L59); `IntakeDraft.entry_type` [app/models/intake_draft.py:63](app/models/intake_draft.py#L63) | 5 valores do enum batem com os 5 cenários do gabarito (novo cliente+novo imóvel / cliente existente+novo imóvel / cliente+imóvel existentes / complementar base / importar documentos). |
| 2. Dados mínimos do cliente | EXISTE | `has_minimal_base` [app/models/intake_draft.py:99](app/models/intake_draft.py#L99); `form_data.new_client` | Exige `client_id` OU dados do cliente; gravado em `form_data` JSONB. Mapeia p/ `Client` (nome, telefone, email, tipo). |
| 3. Dados mínimos do imóvel | EXISTE | `has_minimal_base` [intake_draft.py:113](app/models/intake_draft.py#L113); `form_data.new_property` | Exige `property_id` OU `property.name`. Mapeia p/ `Property` (nome, área). |
| 4. Resumo inicial da demanda | EXISTE | `Process.initial_summary` [app/models/process.py:129](app/models/process.py#L129) | Resumo curto (voz do cliente); aparece no card/quadro. |
| 5. Upload opcional de documentos | EXISTE | `Document.intake_draft_id` [app/models/document.py:41](app/models/document.py#L41); UI [frontend/src/pages/Intake/DraftDocumentUploader.tsx](frontend/src/pages/Intake/DraftDocumentUploader.tsx) | Documentos vinculados ao draft antes da criação do caso. |
| 6. Leitura inicial por IA | EXISTE | `agent_extrator` [app/agents/extrator.py:17](app/agents/extrator.py#L17); `intake_enrichment.py` (mapeia extração→colunas) | Lê documentos anexados e sugere preenchimento de Cliente/Imóvel; identifica faltantes. |
| 7. Criação do card no fluxo | EXISTE | [app/api/v1/intake.py:215-226](app/api/v1/intake.py#L215) | Processo nasce em `macroetapa=entrada_demanda`; card aparece no Quadro de Ações. |
| 8. Gate de prontidão p/ próxima etapa | EXISTE | flags em [app/schemas/process.py:63-66](app/schemas/process.py#L63) (`has_minimal_base`/`has_complementary_base`/`missing_docs_count`) + `GET /can-advance` [app/api/v1/processes.py:538](app/api/v1/processes.py#L538) | Sinaliza "base mínima/complementada/faltam documentos". Mapeia aos 3 status de saída do bloco 8 do gabarito. |

---

## 6. Camada 2 — Hubs e Dashboard (aba "CAMADA 2")

| Item | Status | Onde no código | Observação factual |
|---|---|---|---|
| Dashboard | EXISTE | back [app/api/v1/dashboard.py](app/api/v1/dashboard.py) (`/dashboard/kpis`, funil por macroetapa, gargalo); front [frontend/src/pages/Dashboard/index.tsx](frontend/src/pages/Dashboard/index.tsx) | Mostra KPIs, casos ativos, casos por etapa (funil), gargalos, alertas, casos prioritários, leitura executiva. `agent_vigia`/`agent_acompanhamento` alimentam alertas. Bate com o gabarito. |
| Cliente Hub | EXISTE | back [app/api/v1/clients.py:302-390](app/api/v1/clients.py#L302) (status, etapa do caso primário, timeline); front [frontend/src/pages/Clients/ClientHub.tsx](frontend/src/pages/Clients/ClientHub.tsx) | Dados básicos, contatos, status, imóveis vinculados, casos, contratos, timeline. Bate. `documentos cadastrais` do cliente não têm bloco dedicado evidente (documentos ligam por caso/imóvel). |
| Imóvel Hub | EXISTE | back [app/api/v1/properties.py:367-473](app/api/v1/properties.py#L367) (status regulatório, casos, etapa); front [frontend/src/pages/Properties/PropertyHub.tsx](frontend/src/pages/Properties/PropertyHub.tsx) | Dados estruturados, documentos vinculados, status regulatório, casos associados, leitura técnica. Bate. |

---

## Lacunas claras (itens FALTA)

Nenhum item do gabarito auditado foi classificado como **FALTA**. Todos os itens estão **EXISTE** ou **PARCIAL** — os pontos de divergência estão nas linhas marcadas PARCIAL acima (entidades "Caminho regulatório", "Histórico/Timeline", "Campo extraído" e "Diagnóstico"; papéis de agente de `atendimento`, `diagnostico`, `orcamento`, `financeiro`, `vigia`; tela "Configurações"; e cobertura do gate `can_advance` frente às "Regras por etapa").
