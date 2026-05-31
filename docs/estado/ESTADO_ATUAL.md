# Estado Atual — Regente Ambiental

**Data do instantâneo:** 2026-05-30 (pós-PR #23 fechamento do PR 2.2 — testes integrados 42/42 + cobertura real; pós-PR #24 corpus SEMAD operacional em main; + faxina de repositório: de ~23 branches remotas / 6 worktrees para só `main`)
**Próxima atualização:** eixo 3 — unificação `Process.status` × `Process.macroetapa` (PR3-agressivo; dívida nova #26) ou follow-on do badge crítico-pendente
**Responsável de atualização:** quem fechar a próxima sprint
**Frente em revisão:** `fix/diagnostico-propaga-estado` (PR a abrir — assinatura propaga macroetapa, gate cobra `validated_at`, badge espelha). `fix/extrator-por-processo` (PR #15) já em main.

> Este documento é regenerado a cada sprint. Reflete o estado real da plataforma agora, não o estado planejado. Quando algo muda no código, muda aqui.

---

## Visão de uma página

**O que está funcionando hoje em produção/dev:**

- Backend FastAPI com 27 routers REST + WebSocket
- 11 agentes de IA via LiteLLM (multi-provider, fallback, cost cap enforced) — `auditor_imovel` ativo na chain `diagnostico_completo` desde 2026-05-24
- Painel do consultor (React + Vite) com 36 telas em 10 áreas
- Multi-tenant com isolamento por `tenant_id` validado no JWT
- AuditLog com hash chain SHA-256 encadeado
- RAG semântico via pgvector (~23.000 chunks em 4 UFs; +466 chunks de 9 normas-chave GO/federal)
- Sprint Waitlist B1 mergeada (commit `148c25b`)
- Sprint A2 fechada (redator + diagnóstico + legislacao migrados para schema validado)
- **Fase 2 (skill diagnóstico) fechada em 2026-05-23:** Risco 8+1 (taxonomia oficial),
  citation_evaluator no Diagnóstico, `auditor_imovel` + `property_audit` determinístico,
  9 normas-chave indexadas. Ver `docs/auditoria/MAPA_GAPS_CONFIRMADO_2026-05-23.md`.
- **Pós-Fase 2 (Ondas A/B/C) fechada em 2026-05-24:** `auditor_imovel` ativo na chain
  `diagnostico_completo` via `NON_BLOCKING_REVIEW_AGENTS`; `POST /processes/{id}/diagnoses`
  versionado com gate A4 Pydantic↔JSONB; régua de 4 faixas para divergência (≤1%
  informativo / 1-5% atenção / 5-10% alto / >10% crítico) — **sempre emite** o finding.
- **PROMPT_4 (fechar-pipeline) mergeado em 2026-05-25** (commits `f93b4b4` + `c74ff2e`):
  - **Onda A** — `DiagnosticoAgent` consome `chain_data["auditor_imovel"]`. Cada finding
    vira `Divergencia` + `Risco` com `grau` 4 níveis preservado.
  - **Onda B** — `PATCH /api/v1/processes/{id}/diagnoses/{version}/validate` fecha a
    **camada 1 do Princípio 1** (consultor assina). AuditLog hash chain SHA-256.
- **PROMPT_5 (remodelar `RegulatoryIssue`) mergeado em 2026-05-25** (3c8ac8f):
  - **Onda A** — `RegulatoryIssue` ganha taxonomia rica: `familia` (enum estável 11) +
    `codigo_alerta` (FK em `regulatory_issue_catalog`, catálogo evolutivo via INSERT) +
    campos `muda_rota_regulatoria`/`muda_escopo_preco_prazo`/`documentos_cruzados`.
    `severity` passa de 3 para 4 níveis (`informativo`/`atencao`/`alto`/`critico`) — sai
    o `_GRADE_TO_SEVERITY` que colapsava (dívida #4 fechada). `type` legado fica nullable.
    Migration `c1b2d3e4f5a7` cria, popula 45 entradas seed e migra dados antigos.
  - **Onda B** — auditor emite codigos reais (📄: AREA_MATRICULA_X_CAR, GEO_AUSENTE,
    RL_MATRICULA_DIVERGENTE_RL_CAR, etc.); 🛰️ e 🔌 ficam no catálogo mas não emitidos.
  - **Onda C** — proposta de reconciliação dos 3 status em
    `docs/arquitetura/RECONCILIACAO_STATUS_ALERTAS.md` (Opção A recomendada).
- **PROMPT_6 (camada 2 do Princípio 1) mergeado em 2026-05-26** (62740ae):
  - **Onda A1** — `RegulatoryIssue` ganhou 3 status reconciliados (Opção A):
    `status_achado` (default `suspeita`), `decisao_consultor` (nullable),
    `decisao_consultor_justificativa`, `decisao_consultor_at`, `status_saneamento`
    (default `pendente`). Migration `d2c3e4f5a6b8` (aditiva).
  - **Onda B** — `PATCH /api/v1/properties/{prop}/issues/{id}` edita os 3 status +
    decisão. AuditLog **granular por campo** com hash chain SHA-256.
  - **Onda D (camada 2)** — `PATCH /validate` com gate: **422** se houver
    `RegulatoryIssue` com `severity=critico` sem `decisao_consultor`.
    5 botões P4 (`corrigir_antes` / `seguir_com_ressalva` / `solicitar_doc` /
    `fora_escopo` / `ignorar_justificado`) obrigatórios para críticas.
  - **Revisão pós-rodada (PR #7)** — validator de justificativa obrigatória para
    `ignorar_justificado` e `fora_escopo` (#19 fechada); MODELO_DE_DADOS e API_v1
    atualizados (gatilhos de estrutura).
- **ADR-012 aceito em 2026-05-26** — Isis validou: a decisão do consultor é
  **contextual ao processo**, não perene no imóvel.
- **PROMPT_7 mergeado em 2026-05-26** — implementa o ADR-012:
  - Nova entidade `ProcessIssueDecision` (FK composta `(process_id, issue_id)`
    única) com `decisao`/`justificativa`/`decided_by_user_id`/`decided_at`.
    Migration `e3d4f5g6a7b8`.
  - 3 campos de decisão **saem** do `RegulatoryIssue` (drop sem backfill —
    sem dados em prod ainda). Restam só os 2 status perenes (`status_achado`
    e `status_saneamento`).
  - Endpoints novos: `GET` e `PUT /api/v1/processes/{pid}/issues/{iid}/decision`
    (upsert; AuditLog granular por campo com hash chain SHA-256).
  - Gate `PATCH /validate` ajustado: cruza issues críticas × `ProcessIssueDecision`
    deste processo (não mais campo no `RegulatoryIssue`). Decisão tomada
    no processo A não libera o processo B (titularidade torta pesa diferente
    para venda e para crédito).
  - Validator de justificativa obrigatória (#19) migrou para o schema novo.
  - `decided_by_user_id` é melhoria proporcional ao Princípio 2 — autor
    explícito além do timestamp.
- **Skill `auditor_imovel/analise_divergencias_documentais` validada
  integralmente pela sócia** em 2026-05-26 — separação 📄/🛰️/🔌 confirmada.
- **PROMPT_8 mergeado em 2026-05-26** — fecha a dívida #17 (coerência entre status):
  - Helper puro `app/services/regulatory_coherence.py` com 2 regras semânticas
    (escopo fechado — sem máquina de estados completa).
  - **Regra A (perenes):** saneamento em `em_validacao`/`saneado` exige
    `status_achado in {confirmada, resolvida}`. Aplicada no `@model_validator`
    do `RegulatoryIssueUpdate` (fast-fail) E no endpoint `PATCH
    /properties/.../issues/{id}` sobre o **estado resultante** (fonte da
    verdade, cobre PATCH parcial).
  - **Regra B (cross-entidade):** `PUT /processes/.../decision` rejeita
    `status_achado == suspeita` com mensagem acionável ("Confirme ou
    descarte o achado antes de decidir").
  - Sem migration (validação, não modelagem). Suite 635/635 verde.
- **PROMPT_9 mergeado em 2026-05-26** — UI da camada 2 do Princípio 1
  (consome o backend regulatório sem inventar contrato):
  - Aba **"Alertas"** nova no `ProcessDetail` (block_type "active", entre
    "Visão geral" e "Ações"). Lista `RegulatoryIssue` do imóvel, críticos
    no topo. Cada `AlertaCard` tem: dois `<select>` pros status perenes
    + 5 radios da decisão + textarea de justificativa.
  - **Regra B preventiva na UI:** enquanto `status_achado === 'suspeita'`,
    o fieldset da decisão fica `disabled` com hint "Confirme ou descarte
    o achado para poder decidir". O consultor adjudica primeiro, aí a
    decisão libera. O 422 do backend é rede de segurança, não a primeira
    linha. **#19 (justificativa) validada client-side** + 422 inline.
  - **Bloco "Assinar diagnóstico vN"** no topo do `DiagnosisTab` com
    badge "N pendentes" (`useQueries` cruza issues críticas × decisões).
    Click → `PATCH /validate`. 422 do gate abre modal listando
    `alertas_pendentes`; click no item troca pra aba "Alertas" e faz
    `scrollIntoView` do card `#alerta-{id}`. **Autoridade do backend:**
    se cálculo client-side divergir do 422 (cache stale), confiamos no
    422 e mostramos o que veio.
  - **PropertyHub.AnalysesTab aumentado** (era stub com 5 casos sem
    contexto): vira lente do ADR-012 — lista issues do imóvel + chips
    de TODOS os processos da property, mais recente primeiro. Cada chip
    "Processo #N (demand) · {decisão|pendente} · Decidir/Ver" com
    verbo-por-estado via `useDecision`. Cor emerald = decidida, amber =
    pendente. Teto visual "+N mais" se overflow. Read-only — click leva
    à aba Alertas do processo.
  - **Camada de dados:** `frontend/src/lib/regulatory/{types,labels,hooks}.ts`
    espelha o contrato sem inventar campo nem renomear valor. Cache do
    `useDecision` é compartilhado entre AlertaCard, DiagnosisAssinatura
    e IssueProcessChip — três telas vêem a mesma decisão sem refetch.
  - **Testes:** 10 novos (Vitest+RTL), 31/31 verde. Runner
    `frontend/scripts/run-vitest.mjs` injeta `--experimental-require-module`
    via `NODE_OPTIONS` (workaround pro jsdom 27 + Node 22.11 — registrado
    no commit, removível quando upstream corrigir).
- **PROMPT_10 + PROMPT_11 mergeados em 2026-05-26** — fecha #23 (gate cobrando
  decisão em achado terminal — trap revelado pós-PROMPT_9):
  - Filtro do `PATCH /diagnoses/{version}/validate` cobra decisão em críticos
    com `status_achado in {suspeita, confirmada, ignorada}`. Excluídos só
    `descartada` ("não é divergência real") e `resolvida` ("corrigida no
    mundo") — neles não há o que decidir.
  - **PROMPT_11 corrigiu a versão original do #10**, que excluía `ignorada`
    por erro de simetria. `ignorada` = "achado REAL posto de lado"; setá-la
    via PATCH /issues não exige justificativa, então excluí-la abriria atalho
    pra silenciar crítico real sem registro (bypassa o #19). Quem quer ignorar
    registra `decisao=ignorar_justificado` (com justificativa); a Regra B
    permite porque `ignorada` ≠ `suspeita`.
  - `suspeita` permanece dentro do filtro pra **forçar adjudicação** antes
    de assinar — não é deadlock, o consultor pode mover o estado via
    PATCH /issues.
  - `resolved_at IS NULL` continua como critério ortogonal.
  - Sem migration, sem ADR. Testes no `TestValidateDiagnosisGateCamada2`:
    `descartada`/`resolvida` liberam; `suspeita`/`confirmada`/`ignorada`
    continuam exigindo (422).
  - **Follow-on aberto:** badge "N pendentes" do `DiagnosisAssinatura`
    (PROMPT_9) precisa espelhar a mesma exclusão (`descartada`/`resolvida`)
    pra não super-contar.
- **`fix/upload-checklist-binding` mergeado em 2026-05-28 (PR #14)** — destrava o ciclo de teste da Isis:
  - **Vínculo doc ↔ item de checklist no upload.** `DocumentConfirmRequest` ganha
    `checklist_item_id?: str` (opcional). O endpoint `POST /documents/confirm-upload`
    persiste a coluna `Document.checklist_item_id` (já existia no model) e — se o
    frontend não enviou um `checklist_item_id` explícito mas o `document_type`
    casa com um item pendente — chama `auto_link_document` para marcar o item
    como `received`. Sintoma original: documento subido não virava "recebido"
    no checklist mesmo com tipo correto.
  - **Campos extraídos visíveis na DocumentsTab.** Lista `Object.entries(AIJob.result)`
    do extrator (excluindo `document_id`/`doc_type`/`tenant_id`/`process_id`)
    em `<dl>` abaixo de cada documento processado — antes só aparecia o badge
    "Campos extraídos" sem mostrar o que foi extraído.
  - **`document_id` no PATCH "Recebido" do ProcessChecklist.** `handleReceived`
    passa `item.document_id` (quando existe) no payload — antes só mandava
    `action`, perdendo o vínculo se o consultor desfizesse + refizesse manualmente.
  - **Exclusão em cascata controlada de cliente e imóvel** (`app/services/cascade_delete.py`):
    `cascade_delete_client` apaga, em ordem: documentos do escopo do cliente
    (Document.client_id OU process_id no escopo OU property_id no escopo —
    nunca toca doc de outro cliente), checklists, processos, imóveis, contratos,
    propostas, cliente. Satisfaz FKs RESTRICT (Process/Property/Contract/Proposal
    em client_id). `cascade_delete_property` apaga documentos, checklists e
    processos do imóvel + o próprio imóvel. Cada cascata grava `AuditLog`
    `cascade_deleted` com `details` JSON `{"client_name"/"property_name", "cascade": {counts}}`
    e hash chain SHA-256 (LGPD).
  - **Preview da cascata antes de confirmar.** Endpoints novos
    `GET /clients/{id}/delete-preview` e `GET /properties/{id}/delete-preview`
    devolvem `{properties, processes, documents, checklists, contracts, proposals}`.
    Os modais (`Clients/index.tsx`, `Properties/index.tsx`) carregam o preview
    e listam contagens exatas antes do botão "Confirmar exclusão".
  - **Comportamento de DELETE de documento NÃO mudou:** `DELETE /documents/{id}`
    continua soft delete (`deleted_at`). A cascata acima é hard delete porque
    o caso de uso é resubir os mesmos dados de teste.
  - Suite ampliada das frentes afetadas: **186 testes passando**, tsc `--noEmit`
    zero erros. Sem migration (todas as colunas já existem no schema).
- **`fix/extrator-por-processo` em revisão (2026-05-28, logo após PR #14)** — fecha #25
  (extrator no-op silencioso + falta de extração por processo):
  - **Backend:** `POST /api/v1/processes/{id}/extract` enfileira por
    documento: `workers.run_agent("extrator")` quando há
    `extracted_text` cacheado (com `force=true` opcional pra re-OCR);
    `workers.ocr_then_extract` (chain OCR→extrator) quando o texto
    falta. Resposta separa `jobs` × `pending_ocr`; AuditLog
    `extractor_dispatched` rastreia o disparo. **404** sem docs.
  - **`ExtratorAgent` agora orienta:** sem `document_id`/`text`, o
    `reason` aponta pros 3 caminhos (incluindo o endpoint novo); com
    `document_id` mas `extracted_text` NULL, o `ValueError` diz "OCR
    ainda não rodou — use POST /processes/{id}/extract" em vez do
    críptico "texto extraido".
  - **UI consultor:** card do `extrator` em `/agents` mostra **"Rodar
    no processo #N"** (disabled sem ID — sem mais no-op silencioso).
    Step 4 do `IntakeWizard` **trava avanço** se há docs anexados sem
    "Ler documentos com IA" disparado. `DraftDocumentUploader` ganha
    botão 🗑 por linha (habilitado pra `ocr_status` em `{null,
    pending}`) — exclui antes da IA processar. Doc já processado
    continua removível pela aba Documentos do processo.
  - **Sem migration. Sem ADR.** Reuso de `ocr_then_extract`,
    `run_agent`, `ProcessRepository.add_audit`, `DELETE
    /documents/{id}`. 9 testes em `tests/api/test_processes.py` (3
    novos) + 4 em `tests/agents/test_extrator_cache.py` (1 novo) verde.
    Frontend tsc/build verde.
- **Pipeline ponta a ponta no nível de código + UI:** `extrator → auditor_imovel
  → legislacao → diagnostico → POST /diagnoses (versionado + gate Pydantic) →
  consultor adjudica status_achado e decide alerta por alerta (aba Alertas) →
  consultor assina (DiagnosisAssinatura — gate camada 2 cross-entidades + AuditLog,
  excluindo só achados descartados/resolvidos — PROMPT_10/11)`.
  Princípio 1 fechado em UI também — **a IA propõe, o consultor decide e assina,
  alerta por alerta.**
- **`fix/diagnostico-propaga-estado` em revisão (2026-05-28, logo após PR #15)**
  — fecha o sintoma "card discorda do diagnóstico assinado" e abre a dívida
  **#26** (unificação `Process.status` × `Process.macroetapa` para o eixo 3):
  - **`compute_macroetapa_state`** e **`can_advance_macroetapa`** ganham os
    kwargs `current_macroetapa` + `diagnosis_validated`. Etapa de diagnóstico
    com checklist 100% mas sem `RegulatoryDiagnosis.validated_at` agora
    devolve `aguardando_validacao` (badge passa a concordar com o bloco
    "diagnóstico assinado"); o gate de saída de `diagnostico_preliminar` /
    `diagnostico_tecnico` cobra `validated_at` preenchido.
  - **`PATCH /processes/{id}/diagnoses/{version}/validate`** chama
    `advance_macroetapa` automaticamente quando o gate passa — mesmo
    critério do botão "Avançar" manual: docs obrigatórios + checklist 100%
    + agora a assinatura. Quando o gate trava, o `validated_at` ainda é
    gravado; só a transição de etapa fica suspensa.
  - **Conservador por desenho:** NÃO toca `Process.status`, nem consolida
    as duas chains, nem mexe nas 4 tabelas denormalizadas. A unificação
    propriamente dita virou a dívida **#26** (eixo 3 — PR3-agressivo,
    isolado, com migration própria).
  - **Kanban (`processes.py`)** executa uma única query agregada por
    `tenant_id` para carregar o set de `process_id` com diagnóstico
    assinado — evita N+1 na listagem.
  - 4 testes unitários (`tests/models/test_macroetapa_gate.py`) + 3 de
    API (`TestValidateAdvancesMacroetapa`). Sem migration.
- **Eixo 2 workflow por tipo — ajuste pontual em 2026-05-29:** RAG vetorial do
  `LegislacaoAgent` agora filtra `demand_type` de forma estruturada via
  `LegislationDocument.demand_types`; `WorkflowEngine` levanta
  `TemplateNotFoundError` e API devolve 422 quando não existe template ativo;
  `DemandType` ganhou `sobreposicao`, `supressao`, `due_diligence`,
  `arrendamento`, `condicionantes_antigas`. Relatório:
  `docs/arquivo/auditorias/2026-05-28_cobertura_templates.md`.
- **Frente D (cripto de segredos) fechada em 2026-05-28** — [ADR-014](../adr/014-cripto-segredos-usuario.md):
  padrão Fernet (AES-128-CBC + HMAC-SHA256) para segredos de terceiros no banco
  (white label LLM + credenciais de portal). Entregue: `app/core/encryption.py`
  (`get_fernet`/`encrypt_str`/`decrypt_str` com MultiFernet pra rotação), type decorator
  `EncryptedString` (`app/models/types.py`), `CREDENTIAL_ENCRYPTION_KEY` obrigatória (falha no
  startup, sem fallback inseguro, separada do `SECRET_KEY`), `tools/gen_encryption_key.py`.
  8 testes verdes. **Nenhuma coluna real alterada** — aplicação fica para a PR `Credential`
  (PR 2.3) e a PR LLM (dívida #27). Infraestrutura, não feature de usuário.

**O que está congelado:**

- Portal do cliente (`client-portal/`, Next.js 16) — ver [`../adr/009-mobile-clientportal-congelados.md`](../adr/009-mobile-clientportal-congelados.md)
- App de campo (`mobile/`, Expo) — idem

**O que está em transição:**

- Renomeação Amigão → Regente: rebrand interno feito (`PROJECT_NAME`, docstrings); 8 contratos
  externos (`X-Amigao-*` headers em `alerts.py` + crawlers User-Agent) pendentes — coordenação
  com consumidores antes (dívida #13).
- **Remodelagem do `RegulatoryIssue`** (família + codigo_alerta + 4 níveis) — próxima rodada
  (PROMPT_5), aguardando validação da skill `auditor_imovel/analise_divergencias_documentais`
  pela sócia.

## Backend

### Agentes ativos (11)

| Agente | Arquivo | Status A2 | Custo médio observado |
|---|---|---|---|
| atendimento | `app/agents/atendimento.py` | dict legado | baixo (4 execuções) |
| extrator | `app/agents/extrator.py` | dict legado | 51 execuções históricas — mais usado |
| diagnostico | `app/agents/diagnostico.py` | ✅ A2+A3 (DiagnosticoPreliminarContent + citation_evaluator) | $0.0002 smoke |
| legislacao | `app/agents/legislacao.py` | ✅ A2 (EnquadramentoRegulatorioContent) | $0.0047 acumulado (Gemini 2.0 Flash) |
| redator | `app/agents/redator.py` | ✅ A2 (PecaJuridicaContent) | $0.0030 smoke 7 templates |
| auditor_imovel | `app/agents/auditor_imovel.py` | ✅ A2-Fase2 (deterministic tools, sem LLM) | $0 — cruzamento via `app/services/property_audit.py` |
| orcamento | `app/agents/orcamento.py` | dict legado | baixo |
| financeiro | `app/agents/financeiro.py` | dict legado | baixo |
| acompanhamento | `app/agents/acompanhamento.py` | dict legado | 1 execução |
| vigia | `app/agents/vigia.py` | rules-based (sem LLM) | $0 |
| marketing | `app/agents/marketing.py` | dict legado | baixo |

### Chains de orquestração (9)

Definidas em `app/agents/orchestrator.py:CHAINS`: `intake`, `diagnostico_completo`, `gerar_proposta`, `gerar_documento`, `analise_regulatoria`, `enquadramento_regulatorio`, `analise_financeira`, `monitoramento`, `marketing_content`. Chain principal: `diagnostico_completo` (extrator → legislacao → diagnostico → redator).

### Models SQLAlchemy (28 entidades)

Tabelas principais: `tenants`, `users`, `clients`, `properties`, `processes`, `tasks`, `documents`, `communications`, `proposals`, `contracts`, `ai_jobs`, `audit_logs`, `prompt_templates`, `intake_drafts`, `regulatory_diagnosis`, `regulatory_issues`, `knowledge_catalog`, `legislation_documents`, `pre_cadastros`, `intake_classification_feedback`, etc.

### Routers REST (27 + 1 WebSocket)

Ver `app/main.py:135-161`. Áreas: auth, clientes, processos, documentos, propriedades, tarefas, threads, intake, intake-feedback, checklists, workflows, dossier, decisions, regulatory, proposals, contracts, ai, agents, dashboard, legislation, legislation_alerts, knowledge, waitlist.

**Endpoints regulatórios (2026-05-25):**
- `GET   /api/v1/processes/{id}/diagnoses` — lista versões (mais nova primeiro)
- `GET   /api/v1/processes/{id}/diagnoses/{version}` — versão específica
- `POST  /api/v1/processes/{id}/diagnoses` — cria versão nova (gate A4 Pydantic↔JSONB)
- `PATCH /api/v1/processes/{id}/diagnoses/{version}/validate` — **(PROMPT_4 Onda B)** consultor assina; AuditLog hash chain; 409 se já validado
- `GET   /api/v1/properties/{id}/issues?status=open|resolved|all` — issues do imóvel

### Migrations Alembic

39 migrations aplicadas em produção. Convenção: `<8-hex>_sprint_<X>_<descricao>.py`.

## Corpus regulatório (RAG)

| UF | Chunks indexados | Provider de embedding |
|---|---|---|
| Federal | 720 | OpenAI `text-embedding-3-small` (migração de Gemini concluída) |
| GO | 3.855 | idem |
| MS | 4.587 | idem |
| MT | 13.411 | idem |
| GO — SEMAD operacional | 1.194 | Gemini Flash classify + OpenAI 768d (PR #24, 30/05) |
| **Total** | **23.767** | — |

Corpus SEMAD operacional (PR #24): 282/283 PDFs, 4 source types novos (`norma_procedural`/`matriz_ipe`/`manual_ipe`/`gabarito_laudo`). 1 PDF pendente de OCR (dívida #28). Detalhe em `docs/arquitetura/BASE_REGULATORIA.md`.

Próximos estados na fila: SP, MG, TO (próxima semana).

## Frontend (painel consultor)

- React 19 + Vite + TypeScript + TailwindCSS + React Query + Zustand
- 37+ telas/abas em 10 áreas (Auth, Clients, Processes, Properties, Intake, Contracts, Proposals, Dashboard, AI, Settings)
  - **PROMPT_9:** aba **Alertas** nova no ProcessDetail (Regra B preventiva + 5 botões da P4 + textarea de justificativa); **AnalysesTab** do PropertyHub agora é lente do ADR-012 com chips verbo-por-estado.
- TypeScript strict, zero `any` explícito, mutations uniformizadas via async/await
- Token em Zustand persist + interceptor de 401/403 em `frontend/src/lib/api.ts`
- **Vitest+RTL:** 31/31 verde (4 testes pré-existentes + 10 do PROMPT_9 em `AlertaCard.test.tsx` e `DiagnosisAssinatura.test.tsx`). Runner `frontend/scripts/run-vitest.mjs` injeta `NODE_OPTIONS=--experimental-require-module` (workaround pro jsdom 27 + Node 22.11).

## Testes

- 42+ arquivos de teste em `tests/`
- Testcontainers PostgreSQL+PostGIS (function-scoped session em transação rollback)
- pytest + pytest-cov, `fail_under=70` em coverage
- **Estado verde após PROMPT_4:** **585 passed, 0 failed** (vs 562 antes da rodada — +23 testes:
  15 do `test_diagnostico_consume_auditor.py` + 8 do `TestValidateDiagnosis` em `test_regulatory.py`).
- 4 falhas pré-existentes em main resolvidas na Onda A do PROMPT_3 (24/05) — não há mais falhas
  pré-existentes mascarando o estado.
- **Pulso 2026-05-30 (`fix/pr2.2-fechar-testes` — fecha pendência (a) do PR 2.2):** rodada dos
  testes integrados do motor de workflow contra o banco dev ativo (Docker up, `db` healthy
  na 55432). `test_workflow_engine.py` + `test_regulatory.py` + `test_workflows.py`: **23 passed,
  0 failed**; `test_legislacao_a2.py`: **19 passed**. Total **42 passed, 0 failed, 0 skipped**
  (2 warnings de teardown de transação, infra de teste). Divergências do prompt registradas:
  (1) `tests/api/test_legislacao.py` não existe no repo — não rodado; (2) não há marker
  `pytest.mark.integration` na suíte, então `-m integration` deselecionava tudo — os arquivos
  foram rodados diretamente (eles *são* os testes integrados via Testcontainers).
- **Pulso 2026-05-30 (`feat/intake-campos-backend` — campos derivados do intake, decisões Isis,
  PR 1 de 2):** e-mail obrigatório no contato (422 se vazio); 3 famílias de schema (`ManualFields`/
  `ExtractedFields`/`TriagemFields`); 2 endpoints novos no draft (`GET .../extracted-fields` preview,
  `POST .../reconcile` Opção A → `field_sources`); `audio_url` aceito; regra `prad` no classifier
  (16/16 demand_types classificáveis). **25 testes novos verdes** (`test_intake.py` + 18 do
  `test_intake_classifier.py`), 14 pré-existentes sem regressão. Frontend (PreviewPanel/Reconcile/
  PriorityStep) + docs de agente/UX = **PR 2 (follow-up)**. Validação com a Isis pendente.
- **Pulso 2026-05-30 (`feat/intake-ux-frontend` — PR 2 de 2):** `IntakeWizard` em 2 colunas com
  `PreviewPanel` (polling do `extracted-fields`, badges de confiança, divergência → `ReconcileModal`
  Opção A) + `PriorityStep` (2 eixos: urgência 4 / valor estratégico 3) + áudio da entrevista
  anexável. `npx tsc --noEmit` limpo. `npm run build`/Vitest não rodam neste ambiente (node_modules
  sem dev-deps — `vite`/`@types/node`/`vitest`; pré-existente). Validação fim-a-fim com a Isis pendente.
- **Pulso 2026-05-30 (`feat/llm-provider-por-consultor` — white label):** consultor traz a própria
  chave de LLM (anthropic/google/openai/deepseek). Schema `AiPreferences` + service que cifra a chave
  (`api_key_encrypted` no JSONB, ADR-014, nunca plaintext) + `GET .../ai/available-models` +
  `ai_gateway.complete(user_preferences=...)` (sem fallback global em erro de auth) +
  `BaseAgent.call_llm` via `ctx.user_id` + UI na aba Settings > IA. **28 testes verdes** (incl.
  verificação SQL de cripto); `tsc --noEmit` limpo. Fecha parcialmente a dívida #27; abre #30
  (auditoria de uso por chave). Validação com o André pendente.
- **Pulso 2026-05-30 (`feat/credenciais-portal` — PR 2.3, cofre de credenciais):** modelo `Credential`
  (tabela `credentials`) com `password_encrypted` usando `EncryptedString` — **1º uso real em coluna**
  (fecha #27). CRUD tenant-scoped em `/api/v1/credentials` (senha cifrada, nunca plaintext na API,
  AuditLog hash chain). Migration `c0d1e2f3a4b5` também **reunificou 2 heads divergentes do Alembic**
  (bug pré-existente que quebrava `alembic upgrade head`). **6 testes verdes** (incl. SQL de cripto +
  isolamento de tenant). UI no Client Hub = follow-up; auditoria de leitura de campo sensível segue aberta.
- **Pulso 2026-05-30 (`docs/sistema-agentico-no-repo` — quitação documental, doc-only):** criados
  `docs/agentes/` com `ECOSSISTEMA_AGENTICO.md` (mestre) + sister files `EXTRATOR`/`LEGISLACAO`/
  `ATENDIMENTO`, `docs/MEMORIA_CHAT.md` e a auditoria de leitura sensível — **tudo verificado contra
  o código** (a doc anterior tinha alegações fabricadas). Achado: `AuditLog` cobre escrita, não uso
  de segredo decifrado → dívida **#33**. Dívida **#32** (8 sister files restantes). Whisper/transcrição
  documentada como frente futura (não construída).

## Infraestrutura

- Docker Compose com serviços: db (Postgres+PostGIS+pgvector), redis, minio, api, worker, client-portal (congelado)
- Variáveis de ambiente em `.env.example` (40+ variáveis)
- Métricas Prometheus em `/metrics`
- Health check em `/health`
- OpenAPI em `/docs`

## Sprints concluídas (últimas 6)

| Sprint | Conteúdo | Status |
|---|---|---|
| Sprint -1 (faxina) | Cost cap, filtro demand_type, cache OCR, MemPalace stub | ✅ |
| Sprint 0 (ingestão) | Corpus federal+GO+MS+MT no `knowledge_catalog` | ✅ |
| Sprint U (RAG) | pgvector instalado, busca semântica, embeddings | ✅ |
| Sprint A1 (infra) | `app/skills/`, `StageOutputContent`, RegulatoryDiagnosis, CitationEvaluator | ✅ |
| Sprint A2-redator | RedatorAgent emite `PecaJuridicaContent` (7 templates) | ✅ |
| Sprint A2-diagnostico | DiagnosticoAgent emite `DiagnosticoPreliminarContent` | ✅ |
| Sprint A2-legislacao | LegislacaoAgent emite `EnquadramentoRegulatorioContent` (18 testes A2) | ✅ |
| Fase 0 (auditoria skill) | Skill `situacao_ambiental_imovel_rural` posicionada + ADR-010 + mapa de gaps | ✅ commit `7877652` |
| Fase 2 Onda 1 — A4 (schema) | Risco estendido (8+1), Divergencia, NotificacaoItem, dual-emit, validate_diagnostic_content | ✅ commit `43ac9d5` |
| Fase 2 Onda 1 — K3 (RAG) | 9 normas-chave ingeridas + reindex (466 chunks novos) | ✅ commit `92f6376` |
| Fase 2 Onda 2 — A3 (citation) | citation_evaluator no DiagnosticoAgent (espelha RedatorAgent) | ✅ commit `5c4dd33` |
| Fase 2 Onda 2 — A2 (auditor) | AuditorImovelAgent + property_audit determinístico | ✅ commit `1830e70` |
| Pós-Fase 2 (Ondas A/B/C — PROMPT_3) | 4 fixes pré-existentes + `auditor_imovel` na chain + `POST /diagnoses` + régua 4 faixas | ✅ commits `357993c` + `5e64db4` (mergeado em main) |
| PROMPT_4 — fechar pipeline | Diagnóstico consome auditor + `PATCH /validate` (camada 1 do Princípio 1) | ✅ commits `f93b4b4` + `c74ff2e` (PR aberto, pendente de merge) |
| Upstash polling redução | `polling_interval=5.0`, `vigia 6h→12h`, `acompanhamento 30min→2h` (-85% de comandos Redis) | ✅ commit `a746eb0` (PR #2 mergeado, `bc98c93`) |

## Sprints em curso

| Sprint | Conteúdo | Estado |
|---|---|---|
| Waitlist | Endpoint público + Resend + drip educativo | PR 2 mergeado, PR 3 pendente |
| Governança documental | Mover/arquivar docs conforme `GOVERNANCA_DOCUMENTAL.md`; capturar duráveis | Em curso (esta rodada) |

## Pendências críticas

| Item | Bloqueio | Janela |
|---|---|---|
| Remodelagem `RegulatoryIssue` (dívida #3) | PROMPT_5 — aguarda sócia validar skill `auditor_imovel/analise_divergencias_documentais` | Próxima rodada |
| Camada 2 do Princípio 1 (5 botões P4) | Depende da remodelagem do `RegulatoryIssue` + reconciliação de status (dívida #5) | Pós-PROMPT_5 |
| UI consultor-assina (frontend do `PATCH /validate`) | Endpoint pronto desde PROMPT_4; frontend precisa consumir e renderizar | Curto |
| Property.geom populado | Falta parser shapefile + ingestão de KML/SHP — destrava alertas geoespaciais (dívidas #14/#15) | Médio |
| Crawlers DOU/DOE ativados em prod | Apenas esqueleto pronto | Médio |
| Connector e-mail inbound (acompanhamento) | Sem integração de inbound hoje | Médio |
| R1 polish dos 8 contratos externos (dívida #13) | Headers `X-Amigao-*` em `alerts.py` + crawlers User-Agent — quebra webhook + allowlists SEMAs; coordenar antes | Médio |
| Hardening de produção (secrets, CORS, Swagger desabilitado) | Checklist em `ops/production-secrets-checklist.md` | Curto |
| State-leakage entre testes em suite (29 fails que passam isolados) | Pytest e2e desbloqueado em 17/05 (`0e17ebd`). Sprint dedicada: fixture `autouse=True` resetando `slowapi.Limiter._storage` + auditar testes que committam manualmente. Não bloqueia deploy. | Curto |

## Próximos marcos

- **PROMPT_5 — remodelar `RegulatoryIssue`**: `familia` (enum estável) + `codigo_alerta`
  (catálogo evolutivo) + 4 níveis em severity. Pré-requisito: skill da sócia validada.
- **Camada 2 do Princípio 1** (5 botões P4) — após reconciliação de status (PROMPT_5 Onda C
  só **propõe**).
- **UI do consultor-assina** — frontend consome `PATCH /validate`.
- **Property.geom + parser shapefile** (D1) — destrava overlay PostGIS para
  `auditor_imovel` (sobreposição com APP/UC/terceiros).

## Métricas operacionais

(Esta seção precisa ser preenchida com query SQL real do banco de produção. Marcador para próxima atualização.)

- Clientes cadastrados: a apurar
- Processos abertos: a apurar
- Documentos extraídos: a apurar
- AI Jobs (últimos 30 dias): a apurar
- Custo total IA (últimos 30 dias): a apurar
- Tenant ativo: 1 (sócia)
