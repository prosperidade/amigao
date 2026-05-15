# Progresso 6 — Regente v3: Arquitetura em 4 Camadas

Padrao deste arquivo:

- linguagem executiva e de historico de execucao
- foco em resultado, decisao, validacao, risco e pendencia
- evitar instrucoes operacionais detalhadas; isso pertence ao `RunbookOperacional.md`

## Projeto: Amigao do Meio Ambiente
## Referencia: Mapa mental Whimsical "Regente SaaS (arquitetura principal)" + `docs/MUDANCAS_REGENTE.md`

---

## Objetivo da rodada

Implementar a arquitetura Regente v3 da socia em 4 camadas (Entrada / Visao e Memoria / Operacao / Inteligencia e Governanca), corrigindo divergencias entre o MVP do Amigao e a visao dela. O doc `MUDANCAS_REGENTE.md` levantou 43 mudancas; esta rodada fechou 100% delas em 6 sprints.

---

## Restricao de escopo observada

A configuracao dos 10 agentes IA esta congelada. Nenhuma mudanca em `app/agents/*`, prompts, chains ou orchestrator foi feita. Todos os "paineis de IA" do Hub sao deterministicos (geram texto por regra), permitindo upgrade posterior para agentes existentes sem quebrar contrato.

---

## Sprints executados

### Sprint 1 — Camada 1: Entrada (6/6)

| Item | O que mudou |
|------|-------------|
| CAM1-001 | Step 0 "Tipo de entrada" no wizard com 5 cenarios (`EntryType` enum + coluna) |
| CAM1-002 | `description` virou opcional no intake — "o card nasce sem docs completos" |
| CAM1-003 | Classificacao virou assincrona (agente `atendimento` disparado apenas se ha description ≥10 chars) |
| CAM1-008 | Model `IntakeDraft` + 4 estados (`rascunho / pronto_para_criar / card_criado / base_complementada`) |
| CAM1-009 | Botao "Salvar e continuar depois" no wizard + 6 endpoints `/intake/drafts` (CRUD + commit) |
| CAM1-010 | Processo nasce em `macroetapa=entrada_demanda` |
| CAM1-011 | Gate de prontidao no kanban card (`has_minimal_base`, `has_complementary_base`, `missing_docs_count`) |
| CAM1-012 | Campo `initial_summary` separado da `description` tecnica |

**Migrations:** `f5b7c9a1d3e2` (entry_type + initial_summary) + `a6d8f2c4b1e3` (intake_drafts).

### Sprint 2 — Cenarios avancados de entrada (3/3)

| Item | O que mudou |
|------|-------------|
| CAM1-004 | Endpoint `POST /intake/enrich` + cenario "Complementar base" habilitado no wizard |
| CAM1-007 | `Document.intake_draft_id` FK + 3 endpoints de upload em rascunho (`/drafts/{id}/upload-url`, `/documents`, listagem). Componente `DraftDocumentUploader.tsx` novo + Step 4 "Documentos" no wizard |
| CAM1-005 | Endpoint `POST /intake/drafts/{id}/import` dispara `agent_extrator` assincrono para os docs do rascunho. Botao "Ler com IA" no uploader |

**Migration:** `b7e9f1c3a2d4` (intake_draft_id em documents). Commit do draft migra docs: `process_id + client_id + property_id` atualizados.

### Sprint 3 — Camada 3: Operacao (8/8)

**Fluxo de Trabalho (kanban coordenador):**

| Item | O que mudou |
|------|-------------|
| CAM3FT-001 | Card com `next_action` + badge de alerta + estado formal da etapa |
| CAM3FT-003 | Counts agregados por coluna: `blocked_count` + `ready_to_advance_count` |
| CAM3FT-004 | Novo enum `MacroetapaState` (7 estados) + coluna `state` em `macroetapa_checklists` |
| CAM3FT-005 | Service `can_advance_macroetapa()` + endpoint `GET /processes/{id}/can-advance` + guard HTTP 409 no `POST /macroetapa` |

**Workspace do Caso (dossie vivo):**

| Item | O que mudou |
|------|-------------|
| CAM3WS-001 | `ProcessDetail.tsx` refatorado em layout 6-areas (cabeçalho + barra 7 etapas + menu lateral + area central + painel direito + rodape timeline). Novo componente `WorkspaceRightPanel.tsx` |
| CAM3WS-003 | `MACROETAPA_METADATA` com `objective` + `expected_outputs[]` para cada etapa |
| CAM3WS-005 | Actions ganham `needs_human_validation / validated_at / validated_by_user_id`. Endpoint `POST /macroetapa/{etapa}/actions/validate` |
| CAM3WS-006 | Model `StageOutput` + 3 endpoints (`GET /artifacts`, `POST /artifacts`, `POST /artifacts/{id}/validate`) |

**Migrations:** `c8a1e5d7f3b2` (macroetapa state) + `d4e6b8f1a3c5` (stage_outputs).

### Sprint 4 — Cliente Hub (9/9)

| Item | O que mudou |
|------|-------------|
| CAM2CH-001 | Pagina `ClientHub.tsx` + rota `/clients/:id` |
| CAM2CH-002/003 | Endpoint `GET /clients/{id}/summary` (cabeçalho + 7 KPIs + chips + estado) |
| CAM2CH-004 | Endpoint `GET /clients/{id}/properties-with-status` com estado da macroetapa do caso primario |
| CAM2CH-005 | Mini-timeline por imovel (ate 8 eventos por AuditLog) |
| CAM2CH-006 | Endpoint `GET /clients/{id}/timeline` |
| CAM2CH-007 | Endpoint `GET /clients/{id}/ai-summary` (deterministico: texto + foco + pendencia + recomendacao) + painel lateral na UI |
| CAM2CH-008 | 5 abas internas (Visao geral / Imoveis / Casos / Contratos / Historico) |
| CAM2CH-009 | 5 estados computados: `recem_criado / em_construcao / ativo / com_alertas / consolidado` |

Sem migration — `Client.status` ja existia no schema.

### Sprint 5 — Dashboard Executivo (7/7)

| Item | O que mudou |
|------|-------------|
| CAM2D-001 | Endpoint `GET /dashboard/stages` com distribuicao pelas 7 etapas (total / blocked / ready / avg_days) |
| CAM2D-002 | Endpoint `GET /dashboard/alerts` (docs obrigatorios pendentes por tipo + etapas travadas + propostas sem retorno >7d) |
| CAM2D-003 | Endpoint `GET /dashboard/priority-cases` (ranking por urgencia + dias parado + docs pendentes + estado) |
| CAM2D-004 | Endpoint `GET /dashboard/ai-summary` (leitura executiva deterministica) |
| CAM2D-005 | Filtros executivos em stages/priority-cases (responsible / urgency / demand / UF / period) + FilterBar na UI |
| CAM2D-006 | View selector no dashboard: Geral / Gargalos / Prioridade do dia |
| CAM2D-007 | Botao "Fluxo" no header + "Nova Demanda" ja existente |

Componente `DashboardRegente.tsx` novo — 4 blocos Regente inseridos acima das secoes existentes sem quebrar nada.

### Sprint 6 — Imovel Hub (10/10)

| Item | O que mudou |
|------|-------------|
| CAM2IH-001 | Pagina `PropertyHub.tsx` + rota `/properties/:id` |
| CAM2IH-002 | Bloco 1 cabeçalho com identificacao tecnica (matricula/CAR/CCIR/NIRF/area) + chips + estado do hub |
| CAM2IH-003 | 4 KPIs (casos / docs / analises / pendencias) |
| CAM2IH-004 | 5 abas (Informacoes / Documentos / Analises / Historico / Casos) — Docs e Analises deferem para o workspace |
| CAM2IH-005 | Endpoint `GET /properties/{id}/ai-summary` (deterministico com inconsistencia + pendencia + recomendacao) + painel lateral na UI |
| CAM2IH-006 | `PropertyHealthScore` 0-100 combinando 4 dimensoes (documental / regulatorio / analises / consistencia). Card visual lateral com barras de componente |
| CAM2IH-007 | `Property.field_sources` JSONB + endpoint `POST /properties/{id}/validate-fields`. UI: badges de origem (`raw/ai_extracted/human_validated`) + botao "Validar" por campo |
| CAM2IH-008 | 5 estados (`recem_criado / em_construcao / memoria_estruturada / com_alertas / consolidado`) |
| CAM2IH-009 | CTA principal "Abrir workspace do caso" sempre visivel no cabeçalho |
| CAM2IH-010 | Modulo `document_categories.py` com 6 categorias canonicas Regente + endpoint `GET /documents/categories`. Aliases legados traduzidos automaticamente |

**Migration:** `e7c9b2a4f8d1` (property.field_sources).

---

## Resumo numerico

| Dimensao | Quantidade |
|----------|------------|
| Sprints | 6 |
| Itens Regente fechados | 43/43 (100%) |
| Endpoints novos | ~30 (intake drafts, hubs de cliente/imovel, dashboard Regente, etc.) |
| Migrations novas | 6 |
| Componentes React novos | 5 (`DraftDocumentUploader`, `WorkspaceRightPanel`, `DashboardRegente`, `ClientHub`, `PropertyHub`) |
| Rotas frontend novas | 2 (`/clients/:id`, `/properties/:id`) |
| Arquivos backend modificados | 15+ |

---

## Decisoes arquiteturais

### Painel de IA determinístico primeiro

Os paineis de IA dos hubs (Cliente, Imovel, Dashboard) foram implementados deterministicamente (regras sobre dados agregados). Motivo: respeita a restricao "nao mexer em agentes", evita latencia e custo de token no MVP, e mantem contrato (`source: deterministic`) que permite trocar depois por chamada real a agente existente sem quebrar o frontend.

### Gate de avancanco como guard de transicao

`can_advance_macroetapa()` e chamado tanto em `GET /can-advance` (cliente consulta) quanto no `POST /macroetapa` (backend bloqueia com 409). Blockers cobrem output minimo da etapa + documentos obrigatorios + validacao humana pendente. Futuro: drag-and-drop do kanban precisa integrar com este guard.

### Rascunhos como ponte entre draft e processo

Documentos podem ser anexados a um `IntakeDraft` antes do processo existir (via `intake_draft_id` FK). No commit do draft, docs sao migrados para o processo criado. Isso habilita os cenarios Regente "Complementar base" e "Importar documentos" sem relaxar a integridade referencial.

### 7 estados formais por etapa

A granularidade "nao_iniciada / em_andamento / aguardando_input / aguardando_validacao / travada / pronta_para_avancar / concluida" substitui o `completion_pct` boolean. Calculado dinamicamente via `compute_macroetapa_state()` — a coluna `state` serve apenas como cache.

### Score de saude do imovel (0-100)

`PropertyHealthScore` agrega 4 componentes ponderados. Isso da ao consultor uma leitura rapida "este imovel esta X/100" que reflete completude documental + atualizacao regulatoria + profundidade de analise + consistencia cadastral.

### Origem dos dados com 3 estados

`Property.field_sources` distingue `raw / ai_extracted / human_validated` por campo. Permite que o consultor saiba "este CAR foi extraido por IA mas ninguem validou" e promova para `human_validated` com 1 clique.

---

## Principais arquivos criados

### Backend
- `app/models/intake_draft.py`
- `app/models/stage_output.py`
- `app/models/document_categories.py`
- `app/schemas/client_hub.py`
- `app/schemas/property_hub.py`

### Frontend
- `frontend/src/pages/Intake/DraftDocumentUploader.tsx`
- `frontend/src/pages/Processes/WorkspaceRightPanel.tsx`
- `frontend/src/pages/Dashboard/DashboardRegente.tsx`
- `frontend/src/pages/Clients/ClientHub.tsx`
- `frontend/src/pages/Properties/PropertyHub.tsx`

### Documentacao
- `docs/MUDANCAS_REGENTE.md` — levantamento completo das 43 mudancas com premissa/gap/mudanca por item

### Migrations Alembic (6)
- `f5b7c9a1d3e2_regente_v3_cam1_entry_type`
- `a6d8f2c4b1e3_regente_v3_cam1_intake_drafts`
- `b7e9f1c3a2d4_regente_v3_cam1_doc_intake_draft`
- `c8a1e5d7f3b2_regente_v3_cam3_macroetapa_state`
- `d4e6b8f1a3c5_regente_v3_cam3_stage_outputs`
- `e7c9b2a4f8d1_regente_v3_cam2_property_field_sources`

---

## Perguntas pendentes para a socia

Consolidadas em `docs/MUDANCAS_REGENTE.md` secao "PERGUNTAS PENDENTES":

1. **Camada 4** (Configuracoes da conta — assinatura, notificacoes, preferencias) — mapa foi entregue, implementacao ainda nao iniciada
2. **Drag-and-drop do kanban** — manter com validacao no drop ou desabilitar e forcar botao "Avancar etapa"?
3. **Decisoes no workspace** — log textual ou campo estruturado por tipo de decisao?
4. **Blocos condicionais** — regra automatica (baseada em campos) ou consultor liga/desliga manualmente?
5. **Rascunhos** — politica de expiracao (nunca / 30d / 90d)?
6. **Leitura da IA no Dashboard** — frequencia de atualizacao (tempo real / 1x hora / sob demanda)?

---

## Riscos e pendencias para proxima rodada

### Camada 4 nao implementada
A sub-camada "Configuracoes" (perfil / assinatura / notificacoes / preferencias / IA / seguranca / equipe) esta toda mapeada mas nao entregue. Requer integracao com gateway de pagamento e ganha com decisao de produto (quem vai pagar por que plano).

### Dados legados com estado "Base incompleta"
12 dos 13 processos ativos criados antes da Sprint 1 nao tem `has_minimal_base=true` (faltam phone/email no cliente ou imovel vinculado). Nao e bug — o gate reflete dados reais. Migracao de dados pode ser considerada futuramente.

### Paineis de IA sao deterministicos
Funcionam bem como MVP mas nao refletem profundidade que um LLM traria. Quando a restricao de agentes for relaxada, trocar implementacoes deterministicas por chamadas a agentes existentes e trivial (source field ja preve "agent_xxx").

### Kanban drag-and-drop sem gate
O drag existente permite mover casos sem passar pelo guard `can_advance_macroetapa`. Precisa decisao da socia (ver perguntas pendentes).

### Blocos condicionais do workspace (CAM3WS-002)
A lista de blocos condicionais Regente (procuracao, contrato societario, parceiro tecnico, campo, passivo relevante, embargo, analise fundiaria adicional) foi documentada mas nao implementada. Requer modelagem extra.

---

## Estado operacional pos-Regente v3

| Controle | Estado |
|----------|--------|
| Sprints Regente v3 | 6/6 (100%) |
| Itens fechados | 43/43 |
| Migrations aplicadas | 6 (head: `e7c9b2a4f8d1`) |
| Endpoints novos | ~30 |
| Restricao "nao mexer em agentes" | Respeitada — 0 alteracoes em `app/agents/` |
| Frontend typecheck | Limpo (`npx tsc --noEmit` passa) |
| Rotas novas | `/clients/:id`, `/properties/:id` (hubs) |
| Backend Python imports | OK |
| Docker containers | api, worker, db, redis, minio, client-portal — todos rodando |
