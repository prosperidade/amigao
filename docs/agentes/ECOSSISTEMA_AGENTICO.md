# Ecossistema agêntico — documento mestre

> Visão transversal do sistema de agentes de IA. Criado no repo em 2026-05-30 a
> partir do código real (versões anteriores viviam só em rascunhos de chat).
> Cada afirmação é verificável no código; os sister files por agente vivem em
> `docs/agentes/<AGENTE>_AGENTE.md`.

## 1. Princípios

Os 10 princípios do produto vivem em `docs/manifesto/03-PRINCIPIOS.md` (fonte de
verdade — não duplicar aqui). Os mais ativados no ecossistema:
- **A IA propõe; o humano decide e assina** — peças formais com `requires_review=True`.
- **Tudo é auditável** — `AuditLog` com hash chain SHA-256.
- **Multi-tenant desde o dia 1** — toda query filtra `tenant_id`.
- **Multi-provider IA** — LiteLLM com fallback; nenhum serviço chama provider direto.

## 2. Catálogo dos agentes

11 agentes registrados via decorator `@AgentRegistry.register`
(`app/agents/base.py`; imports em `app/agents/__init__.py`).

| Agente | job_type | Output | requires_review | Status |
|---|---|---|---|---|
| `atendimento` | classify_demand | dict (demand_type sugerido) | não | Implementado. Recebe `audio_url` (só armazenado). **Transcrição: frente futura, não construída.** |
| `extrator` | extract_document | dict (extracted_fields) | não | Implementado. + `field_sources`, reconciliação, `/extracted-fields` (PR Intake). |
| `diagnostico` | diagnostico_propriedade | DiagnosticoPreliminarContent | **sim** | Implementado. `requires_review=True` forçado (`diagnostico.py:448` — "diagnóstico SEMPRE precisa de validação humana"). Consome `chain_data["auditor_imovel"]`. |
| `auditor_imovel` | diagnostico_propriedade | dict (divergencias/findings) | sim (não-bloqueante) | Implementado. Determinístico (`property_audit`). |
| `legislacao` | consulta_regulatoria | EnquadramentoRegulatorioContent | sim | Implementado. **Filtro RAG por demand_type via JOIN com `LegislationDocument.demand_types` (PR 2.2).** |
| `orcamento` | generate_proposal | dict (proposta) | sim | Implementado. |
| `financeiro` | analise_financeira | dict (insights) | não | Implementado. |
| `redator` | gerar_documento | PecaJuridica/RespostaNotificacao | sim | Implementado. |
| `acompanhamento` | acompanhamento_processo | dict (resposta órgão) | não | Implementado. |
| `vigia` | monitoramento_vigia | dict (alerts) | não | Implementado. Determinístico (sem LLM). |
| `marketing` | gerar_conteudo_marketing | dict (conteúdo) | sim | Implementado. |

## 3. Padrões transversais

- **A norma dita o fluxo** — `legislacao` filtra por `demand_type`; o
  `workflow_engine` levanta `TemplateNotFoundError` quando falta template.
- **IA-driven intake (implementação concreta, PR Intake):** `IntakeWizard` em 2
  colunas — formulário multi-step à esquerda, `PreviewPanel` à direita com
  polling 5s de `GET /intake/drafts/{id}/extracted-fields`. Reconciliação
  manual×IA via modal (Opção A) → `POST /intake/drafts/{id}/reconcile`. Áudio
  anexável via presigned upload. Schemas separados:
  `ManualFields`, `ExtractedFields` (`{value, confidence, source_document_id}`),
  `TriagemFields`.
- **Áudio como input** — `audio_url` armazenado no `IntakeDraft`; transcrição é
  frente futura (não construída).
- **Caso só nasce por mão do consultor** (decisão de produto). O `Process` nasce
  com `demand_type="nao_identificado"`.
- **Provider plugável por consultor** (ver 3.5).
- **Non-blocking review (ADR-011):** `auditor_imovel` emite `requires_review` sem
  travar a chain (`NON_BLOCKING_REVIEW_AGENTS`); `legislacao`/`redator` travam.
- **Decisão contextual ao processo (ADR-012):** decisões do consultor sobre
  achados são por processo, não perenes no imóvel.
- **Skills procedurais (ADR-006):** compiladas no system prompt via
  `_compose_system_with_skills`.
- **RAG seletivo:** `knowledge_catalog.search` filtra por uf/agency/demand_type.

### 3.2 IA-driven intake
Ver bloco acima (implementado na PR Intake backend #26 + frontend #27).

### 3.5 Provider plugável (white label) — implementado 2026-05-30 (PR LLM #28)
4 providers configuráveis em `User.preferences.ai`: **Anthropic, Google, OpenAI,
DeepSeek**. `api_key` cifrada via `encrypt_str` em
`User.preferences['ai']['api_key_encrypted']` (ADR-014). `BaseAgent.call_llm`
passa `user_preferences` ao `ai_gateway.complete`; resolução `provider:model` no
formato LiteLLM (`anthropic/claude-...`, `gemini/gemini-2.5-pro`, `openai/...`,
`deepseek/...`). **Sem fallback global automático em falha de auth** da chave do
usuário (não gastar crédito do sistema). Provider chinês default = `deepseek`
(`settings.LLM_CHINESE_PROVIDER`).

*WhatsApp/email externos:* PR 2.1 ainda **não** mergeado — sem implementação.

## 4. Orquestração

`app/agents/orchestrator.py` define `CHAINS`:
- `intake`: `[atendimento]`
- `diagnostico_completo`: `[extrator, auditor_imovel, legislacao, diagnostico]`
- `gerar_proposta`: `[diagnostico, orcamento]`
- `gerar_documento`: `[redator]`
- `analise_regulatoria`: `[legislacao]`
- `enquadramento_regulatorio`: `[extrator, legislacao]`
- `analise_financeira`: `[financeiro]`
- `monitoramento`: `[acompanhamento, vigia]`
- `marketing_content`: `[marketing]`

`MACROETAPA_AGENT_CHAIN` (`app/models/macroetapa.py`) liga as 7 macroetapas
pré-contrato a chains. `NON_BLOCKING_REVIEW_AGENTS = {auditor_imovel}`.

## 5. Tools shared

- **5.1 LiteLLM gateway** (`app/core/ai_gateway.py`) — camada única; **agora
  resolve por usuário** quando `User.preferences.ai` tem provider/model/api_key
  (`complete(user_preferences=...)`). Cost cap por job + por tenant (hora/mês).
- **5.2 RAG `knowledge_catalog`** — pgvector 768d; filtros uf/agency/demand_type.
- **5.3 OCR pipeline** (`ocr_then_extract`) — ver `docs/arquitetura/PIPELINE_OCR.md`.
- **5.4 PostGIS** — `Property.geom` (helpers geoespaciais do auditor aguardam
  dados; dívida #14).
- **5.5 AuditLog hash chain SHA-256** (`stamp_audit_hash`).
- **5.6 Encryption (Fernet + EncryptedString) — ADR-014.** 1º uso real em coluna:
  `Credential.password_encrypted` (PR 2.3). Em JSONB: `api_key` em
  `User.preferences.ai` (cifrada via `encrypt_str` no `save_ai_preferences`,
  não via `EncryptedString` — JSONB não é coluna String).
- **5.7 Auditoria de uso da `api_key` do consultor (dívida #33, parcial).** O uso
  server-side da chave própria do consultor é auditado: `BaseAgent.call_llm` emite
  `AuditLog` `action="ai_key_used"` (hash chain) uma vez por execução, com a chave
  mascarada (`emit_ai_key_use_event`, `app/agents/events.py`). A senha de portal
  (`Credential`) ainda não é auditada no uso — sem consumidor hoje (resto da #33).
- **5.8 Verificação da hash chain (dívida #18, fechada 31/05).** `verify_audit_chain(db, tenant_id)`
  (`app/services/audit_hash.py`) recomputa cada hash em ordem e compara com o persistido (conteúdo +
  elo), devolvendo os elos quebrados. Exposto em `GET /api/v1/admin/audit/verify-chain` (superusuário,
  read-only). A hash chain deixou de ser só escrita — agora tem verificador.

## 6. Skills vs Tools

- **Tool:** função/integração determinística (RAG, OCR, gateway, PostGIS).
- **Skill (ADR-006):** template procedural em Markdown compilado no system prompt.
  Skills formais hoje: `diagnostico/situacao_ambiental_imovel_rural`,
  `auditor_imovel/analise_divergencias_documentais`. Demais agentes ainda sem
  skill formal dedicada.

## 7. Knowledge essencial transversal

- Vocabulário ambiental: CAR, RL, APP, GEO, SIGEF, NIRF, CCIR, embargo, PRAD,
  outorga, supressão.
- Estados/órgãos: SEMA por UF, IBAMA, INCRA, ANA, MAPA.
- **Taxonomia `DemandType`: 16 valores** (`app/models/process.py`).
- **Triagem 2 eixos (UI implementada, `PriorityStep`):** Urgência (4 níveis:
  urgentissima/alta/media/baixa) e Valor Estratégico (3 níveis: alto/medio/baixo),
  dropdowns independentes. Critério do nível "Baixo" pendente (**dívida #29**).

## 8. Roadmap

- ✅ Mergeado: Eixo 1 · PR 2.2 (#26 motor workflow) · Frente D (ADR-014) · Intake
  backend (#26) · Intake frontend (#27) · PR LLM (#28) · PR 2.3 credenciais (#29)
  · fix compose CREDENTIAL_ENCRYPTION_KEY (#30) · remoção corpus do git (#31) ·
  governança Render (#32).
- ⏭ Pendente: **PR 2.1** (WhatsApp/email externos — depende de Resend Inbound +
  URL/key da Evolution). **EIXO 3** (unificação `Process.status` ×
  `macroetapa`, dívida #26).

## 9. Decisões pendentes

- **Resend Inbound:** dispensado por ora (ADR-008 escolheu Resend p/ outbound;
  inbound não construído — ver `docs/arquitetura/INTEGRACOES_GOVTECH.md`).
- **Hosting da Evolution (WhatsApp):** a decidir (URL/key externas) — pré-req do PR 2.1.
- **Critério Valor Estratégico "Baixo"** (dívida #29) — Isis decide na tela.
- **Transcrição de áudio** — frente futura sem PR.

## 10. Governança documental do ecossistema

Regra (`docs/arquitetura/GOVERNANCA_DOCUMENTAL.md`): todo PR que evolui um agente
atualiza o sister file correspondente; decisões cross-cutting atualizam este
mestre. Sister files são VIVOS — afirmação que não bate com o código sai.

## 11. Catálogo de sister files

| Agente | Sister file | Status |
|---|---|---|
| extrator | `docs/agentes/EXTRATOR_AGENTE.md` | ✅ criado (2026-05-30) |
| legislacao | `docs/agentes/LEGISLACAO_AGENTE.md` | ✅ criado (2026-05-30) |
| atendimento | `docs/agentes/ATENDIMENTO_AGENTE.md` | ✅ criado (2026-05-30) |
| diagnostico | `docs/agentes/DIAGNOSTICO_AGENTE.md` | ✅ criado (2026-05-31) |
| auditor_imovel | `docs/agentes/AUDITOR_IMOVEL_AGENTE.md` | ✅ criado (2026-05-31, skill validada pela Isis 26/05) |
| orcamento | `docs/agentes/ORCAMENTO_AGENTE.md` | ✅ criado (2026-05-31) |
| financeiro | `docs/agentes/FINANCEIRO_AGENTE.md` | ✅ criado (2026-05-31) |
| redator | `docs/agentes/REDATOR_AGENTE.md` | ✅ criado (2026-05-31) |
| acompanhamento | `docs/agentes/ACOMPANHAMENTO_AGENTE.md` | ✅ criado (2026-05-31) |
| vigia | `docs/agentes/VIGIA_AGENTE.md` | ✅ criado (2026-05-31) |
| marketing | `docs/agentes/MARKETING_AGENTE.md` | ✅ criado (2026-05-31) |

**Os 11 sister files estão criados** (os 3 primeiros — extrator, legislacao,
atendimento — em 2026-05-30; os 8 restantes em 2026-05-31, quitando a dívida
documental **#32**). São VIVOS: cada PR que evolui um agente atualiza o seu.
