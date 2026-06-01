# API v1

**Documento:** Arquitetura · referência viva
**Estado:** atualizar a cada novo router ou mudança de contrato
**Última revisão:** 2026-05-15
**Verificado em:** `app/main.py:134-161` (29 routers + WebSocket)

---

Superfície REST do Regente Ambiental. Para spec interativa com schemas, abra `http://localhost:8000/docs` (OpenAPI). Este documento explica padrões, autenticação, organização — não substitui o OpenAPI.

## Convenções globais

- **Prefixo:** `/api/v1` (configurável via `API_V1_STR`). Único endpoint sem prefixo é infraestrutura: `/`, `/health`, `/metrics`.
- **Autenticação:** JWT Bearer no header `Authorization`. Login retorna `access_token`.
- **Perfil:** header `X-Auth-Profile: internal` ou `X-Auth-Profile: client_portal` (define qual `get_current_*_user` valida o token).
- **Tenant:** isolamento por `tenant_id` extraído do JWT. Não há header `X-Tenant-Id` (anti-padrão — tenant vem do token, sempre).
- **Formato:** JSON. Pydantic v2 valida request/response.
- **Erros:** `{"detail": "..."}` padrão FastAPI. Códigos: 400, 401, 403, 404, 409, 422, 429, 500.
- **Versionamento:** versão major por prefixo (`/api/v1`, `/api/v2` no futuro). Estratégia em [`../adr/`](../adr/) (a formalizar).

## Mapa de routers (29)

| Tag (OpenAPI) | Prefixo | Arquivo | Resumo |
|---|---|---|---|
| Autenticação | `/api/v1/auth` | `app/api/v1/auth.py` | Login (2 perfis), refresh, signup interno |
| Clientes | `/api/v1/clients` | `app/api/v1/clients.py` | CRUD de cliente + Cliente Hub |
| Processos | `/api/v1/processes` | `app/api/v1/processes.py` | CRUD de processo + transições de estado |
| Documentos | `/api/v1/documents` | `app/api/v1/documents.py` | Upload presigned, confirmação, listagem, OCR async |
| Propriedades | `/api/v1/properties` | `app/api/v1/properties.py` | CRUD de imóvel + Imóvel Hub |
| Tarefas | `/api/v1/tasks` | `app/api/v1/tasks.py` | CRUD + Kanban + transições |
| Comunicação | `/api/v1/threads` | `app/api/v1/threads.py` | Threads, mensagens, anexos |
| Mensageria / Canais | `/api/v1/messaging` | `app/api/v1/messaging.py` | Webhook inbound de WhatsApp (Evolution) — sem JWT, valida HMAC (PR 2.1) |
| Credenciais | `/api/v1/credentials` | `app/api/v1/credentials.py` | Cofre de logins de portais por cliente (senha cifrada, ADR-014) |
| Intake | `/api/v1/intake` | `app/api/v1/intake.py` | Wizard de 5 passos, drafts, commit, import documental |
| Intake Feedback | `/api/v1/processes/{id}/classify` + `/admin/intake-feedback` | `app/api/v1/intake_feedback.py` | Promoção de `demand_type` + métricas de divergência |
| Checklists | `/api/v1/processes` | `app/api/v1/checklists.py` | Checklist documental por processo |
| Trilha Regulatória | `/api/v1/workflows` + `/api/v1/processes` | `app/api/v1/workflows.py` | Workflow templates, gates de macroetapa |
| Dossiê | `/api/v1/processes` | `app/api/v1/dossier.py` | Dossier técnico do caso |
| Decisões | `/api/v1/processes` | `app/api/v1/decisions.py` | Process decisions (mudança de rota regulatória) |
| Diagnóstico Regulatório | `/api/v1/processes` + `/api/v1/properties` | `app/api/v1/regulatory.py` | `RegulatoryDiagnosis` + `RegulatoryIssue` (sprint A1) |
| Propostas | `/api/v1/proposals` | `app/api/v1/proposals.py` | Geração de proposta + revisão + aceite |
| Contratos | `/api/v1/contracts` | `app/api/v1/contracts.py` | Geração de contrato + assinatura + versionamento |
| IA | `/api/v1` | `app/api/v1/ai.py` | classify, extract, jobs list/get/status (síncrono + async) |
| Agentes IA | `/api/v1/agents` | `app/api/v1/agents.py` | Listar agentes, executar agente isolado, ver orçamento |
| Dashboard | `/api/v1/dashboard` | `app/api/v1/dashboard.py` | Métricas operacionais para o painel |
| Base Legislativa | `/api/v1/legislation` | `app/api/v1/legislation.py` | Listar diplomas, buscar |
| Alertas Legislativos | `/api/v1/legislation` | `app/api/v1/legislation_alerts.py` | CRUD de alertas, ack |
| Knowledge Catalog (RAG) | `/api/v1/knowledge` | `app/api/v1/knowledge.py` | `GET /search`, `POST /index`, `POST /reindex-legislation` |
| Waitlist (Regente) | `/api/v1/waitlist` | `app/api/v1/waitlist.py` | `POST /` público (lead anônimo, rate-limited) |
| Tempo Real | (raiz) | `app/api/websockets.py` | WebSocket router para eventos do tenant |
| Admin / Métricas | `/api/v1/admin` | `app/api/v1/intake_feedback.py` | Estatísticas tenant-scoped |

## Autenticação em detalhe

### Login (`POST /api/v1/auth/login`)

Recebe:
```
POST /api/v1/auth/login
X-Auth-Profile: internal
Content-Type: application/x-www-form-urlencoded

username=consultor@regenteambiental.com.br&password=...
```

(Form-data porque é compatível com OAuth2PasswordBearer do FastAPI.)

Responde:
```json
{
  "access_token": "<JWT>",
  "token_type": "bearer",
  "expires_in": 86400
}
```

JWT contém:
- `sub` (user_id, str)
- `tenant_id` (int)
- `profile` ("internal" | "client_portal")
- `client_id` (apenas quando profile = client_portal)
- `exp` (timestamp)

### Guardas

| Guarda | Aceita | Rejeita |
|---|---|---|
| `get_current_user` | qualquer token válido | token inválido/expirado (401) |
| `get_current_internal_user` | profile = internal | profile = client_portal (403) |
| `get_current_portal_user` | profile = client_portal | profile = internal (403) |
| `get_current_active_user` | usuário com `is_active = true` | desativado (403) |
| `require_superuser` | `is_superuser = true` | comum (403) |

Tenant guard implícito: toda dependency que devolve usuário também exige que `tenant_id` do JWT exista. Tentativa de manipular entidade de outro tenant retorna 403 em deep check no service layer.

### Preferências de IA — provider por consultor (white label, PR LLM)

Decisão André 2026-05-28. O consultor pode trazer a própria chave de LLM. Vive no grupo `ai`
de `User.preferences` (JSONB).

**`PATCH /api/v1/auth/me/preferences`** — estendido: o grupo `ai` aceita `provider`
(`anthropic|google|openai|deepseek`), `model` e `api_key`. A `api_key` é **write-only**: entra
em plaintext, o service cifra (ADR-014) em `api_key_encrypted` e **nunca persiste plaintext**.
Um PATCH sem `api_key` **preserva** a chave existente (não apaga). A resposta vem mascarada
(`api_key: null`, `api_key_masked: "…AB12"`, `api_key_set: true`).

**`GET /api/v1/auth/me/full`** — o grupo `ai` volta sempre mascarado (nunca plaintext).

**`GET /api/v1/auth/me/preferences/ai/available-models`** — lookup table hardcoded de modelos
por provider (popula o dropdown do Settings > IA):

```json
{ "anthropic": ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001", "claude-opus-4-20250514"],
  "google": ["gemini-2.5-flash", "gemini-2.5-pro"],
  "openai": ["gpt-4o-mini", "gpt-4o"],
  "deepseek": ["deepseek-chat", "deepseek-reasoner"] }
```

> **Gateway:** `ai_gateway.complete(user_preferences=...)` resolve provider/model/chave do
> consultor (formato LiteLLM `provider/model`). Falha de **auth** com a chave do consultor
> **não** cai no fallback global (não gastar crédito do sistema) — erro claro pedindo revisão
> em Configurações > IA. `BaseAgent.call_llm` resolve as prefs via `ctx.user_id`.

### Cofre de credenciais de portal (`/api/v1/credentials`, PR 2.3)

CRUD tenant-scoped do modelo `Credential` (logins de portais por cliente — SEMA/IBAMA/SICAR/
INCRA/banco). Internal user; tenant vem do JWT.

- `POST /api/v1/credentials` — `{client_id, portal, label?, login?, password?, url?, notes?}`.
  O cliente precisa ser do mesmo tenant (senão 404). A **senha é cifrada** (`EncryptedString`,
  ADR-014) — ciphertext no banco, **nunca plaintext** na resposta.
- `GET /api/v1/credentials?client_id=` · `GET /{id}` — devolvem `has_password` (bool), **nunca**
  a senha. Recuperação para uso é server-side (ORM decifra ao carregar).
- `PATCH /{id}` — parcial; `password` ausente/vazia **preserva** a atual.
- `DELETE /{id}` — soft delete (`deleted_at`). 204.
- Todas as operações geram `AuditLog` (`entity_type=credential`, hash chain SHA-256).
- Primeiro consumidor de UI: aba **Credenciais** no Cliente Hub. A UI usa `has_password`
  para indicar senha protegida e não oferece "ver senha". O contrato atual não expõe
  `valid_until`; alerta de vencimento fica em dívida de produto (#36).

## Rate limiting

- Implementação: `slowapi` (`app/core/rate_limit.py`)
- Estratégia: per-IP por padrão
- Endpoints com limites específicos:
  - `POST /api/v1/auth/login` — limite documentado em `.env.example` (recomendado em produção)
  - `POST /api/v1/waitlist` — `10/min` por IP
- Resposta quando excede: `429 Too Many Requests`

## Padrões REST aplicados

### Idempotência

`POST` de criação **não é** garantidamente idempotente. Quando idempotência importa (signup, waitlist), o endpoint usa estratégia explícita:

- `POST /api/v1/waitlist` — segundo POST com mesmo email retorna 200 com o lead existente (não 409, decisão de produto registrada no `RELATORIO_WAITLIST.md`).

### Soft delete

`DELETE /documents/{id}` continua soft delete (`deleted_at`). `DELETE /processes/{id}`
também é soft delete.

**Exceção — `DELETE /clients/{id}` e `DELETE /properties/{id}` viraram cascata
hard-delete** (`fix/upload-checklist-binding`, 2026-05-28). Motivação: ciclo de
teste — a consultora precisa apagar pra resubir os mesmos casos. Cada endpoint
exige preview antes:

| Endpoint | Função |
|---|---|
| `GET    /api/v1/clients/{id}/delete-preview` | Devolve `{properties, processes, documents, checklists, contracts, proposals}` (contagens exatas) sem alterar o banco. Usado pelo modal de confirmação. |
| `DELETE /api/v1/clients/{id}` | Cascata em ordem segura (documentos do escopo do cliente → checklists → processos → imóveis → contratos → propostas → cliente). Satisfaz FKs RESTRICT (Process/Property/Contract/Proposal em `client_id`). Documentos só caem se pertencem ao escopo do cliente (Document.client_id OU process_id IN procs_owned_by_client OU property_id IN props_owned_by_client) — **nunca toca doc de outro cliente**. AuditLog `cascade_deleted` com hash chain SHA-256, `details` JSON com nome + contagens (LGPD). |
| `GET    /api/v1/properties/{id}/delete-preview` | Devolve `{properties: 1, processes, documents, checklists, contracts: 0, proposals: 0}`. |
| `DELETE /api/v1/properties/{id}` | Cascata documentos → checklists → processos do imóvel → imóvel. AuditLog `cascade_deleted` com hash chain SHA-256. |

Lógica isolada em `app/services/cascade_delete.py` (`preview_*` + `cascade_delete_*` +
`CascadePreview` dataclass). Sem migration — usa FKs existentes. Tudo dentro do
endpoint roda em uma única transação (commit no router).

### Paginação

Listagens usam query params `?skip=0&limit=100` (FastAPI default). Soma máxima `limit=200`. Endpoints com volume relevante (logs, ai_jobs, knowledge_catalog) limitam `limit` ainda mais.

### Listagem com filtro

Convenção: query string aceita filtros simples (`?status=execucao&demand_type=car`). Filtros complexos (full-text, semântico) usam endpoint dedicado (`GET /knowledge/search`).

### Confirmação de upload (`POST /documents/confirm-upload`)

`DocumentConfirmRequest` aceita `checklist_item_id?: str` (opcional —
`fix/upload-checklist-binding`, 2026-05-28). Comportamento de auto-vínculo:

1. Se o body trouxer `checklist_item_id`, o endpoint marca aquele item específico
   do `ProcessChecklist` como `received` com `document_id = doc.id`.
2. Senão, se `document_type` estiver setado, `auto_link_document` procura o
   primeiro item pendente do checklist com `doc_type == document_type` e marca.
   O `Document.checklist_item_id` é preenchido com o item_id linkado.
3. Se não houver checklist ou nenhum item casar, o documento é persistido sem
   vínculo — o consultor ainda pode marcar manualmente via PATCH `/checklist/items`.

Resposta continua `202 Accepted` (extração OCR é enfileirada como antes).

### Endpoints regulatórios (`/processes/{id}/diagnoses`, `/properties/{id}/issues`)

`app/api/v1/regulatory.py` — versionamento de `RegulatoryDiagnosis` por processo +
assinatura humana.

| Endpoint | Função |
|---|---|
| `GET   /api/v1/processes/{id}/diagnoses` | Lista versões do `RegulatoryDiagnosis`, mais nova primeiro |
| `GET   /api/v1/processes/{id}/diagnoses/{version}` | Versão específica |
| `POST  /api/v1/processes/{id}/diagnoses` | Cria versão nova (gate Pydantic↔JSONB via `validate_diagnostic_content`) — 422 se `content` não respeita `DiagnosticoPreliminarContent`. Versão é `MAX(version)+1` server-side. |
| `PATCH /api/v1/processes/{id}/diagnoses/{version}/validate` | **Camada 1 + 2 do Princípio 1.** Grava `validated_by_user_id` + `validated_at` + AuditLog hash chain. **409** se já validada. **422** (PROMPT_6 + ADR-012) com lista de `alertas_pendentes` se houver `RegulatoryIssue` com `severity=critico` + `resolved_at IS NULL` + `status_achado in {suspeita, confirmada, ignorada}` no imóvel **sem `ProcessIssueDecision` deste processo**. **PROMPT_10/11:** só `descartada` e `resolvida` ficam de fora (terminais sem o que decidir). `ignorada` **continua exigindo decisão** (PROMPT_11 corrigiu o #10): é achado real posto de lado e setá-la via `PATCH /issues` não exige justificativa — excluí-la abriria atalho pra silenciar crítico real sem registro (bypassa o #19); ignorar um real passa por `decisao=ignorar_justificado` (com justificativa). `suspeita` força adjudicação antes de assinar (não é deadlock — `PATCH /issues` move o estado). Decisão tomada em OUTRO processo da mesma property não libera (ADR-012). Quando 422 rejeita, NADA é gravado (`validated_*` continua None). **Efeito colateral (`fix/diagnostico-propaga-estado`, 28/05/2026):** após gravar `validated_at`, se `Process.macroetapa` é `diagnostico_preliminar` ou `diagnostico_tecnico` e `can_advance_macroetapa` passa (checklist 100% + docs obrigatórios OK + agora a assinatura), o backend chama `advance_macroetapa` automaticamente — `Process.macroetapa` avança para a próxima etapa no mesmo request. Gate travado (docs pendentes, checklist incompleto) mantém o `validated_at` gravado mas não muda macroetapa. Etapa não-diagnóstica nunca dispara o auto-advance. |
| `GET   /api/v1/properties/{id}/issues?status=open\|resolved\|all` | Lista `RegulatoryIssue` do imóvel |
| `PATCH /api/v1/properties/{prop_id}/issues/{issue_id}` | **Consultor edita os 2 status perenes** (PROMPT_7 — ADR-012 enxugou). Body parcial via `RegulatoryIssueUpdate` (`extra="forbid"`): `status_achado`, `status_saneamento`. **AuditLog granular por campo** (`<campo>_changed`) com hash chain SHA-256. Mesmo valor (no-op por campo) NÃO gera AuditLog. 404 se issue não pertence à property/tenant. Os 3 campos de decisão saíram daqui — moveram para `PUT /processes/.../decision`. **PROMPT_8 (#17):** rejeita 422 quando o **estado resultante** (corpo aplicado sobre a issue carregada) tem `status_saneamento in {em_validacao, saneado}` sem `status_achado in {confirmada, resolvida}`. Body completo com a combinação proibida estoura fast-fail no `@model_validator` do schema; PATCH parcial é validado no endpoint. |
| `GET   /api/v1/processes/{process_id}/issues/{issue_id}/decision` | **PROMPT_7 (ADR-012)** — lê a decisão do consultor para `(process_id, issue_id)`. **404** se ainda não há decisão (cada processo recomeça do zero — comportamento contextual). |
| `PUT   /api/v1/processes/{process_id}/issues/{issue_id}/decision` | **PROMPT_7 (ADR-012)** — **upsert** da decisão. Body via `ProcessIssueDecisionCreate`: `decisao` (obrigatório), `justificativa` (obrigatória quando `decisao in {ignorar_justificado, fora_escopo}` — Princípio 2). Server-side: `decided_by_user_id = current_user.id`, `decided_at = now()`. Primeira chamada cria com `AuditLog(action="created")`; chamadas seguintes atualizam com AuditLog **granular por campo** (`decisao_changed`, `justificativa_changed`). Mesmo valor = no-op. **404** se issue não pertence à property do processo. **PROMPT_8 (#17):** rejeita 422 (com mensagem "Confirme ou descarte o achado antes de decidir") quando `issue.status_achado == suspeita` — decide-se o que fazer com a divergência só depois de confirmar que ela é real. |

**Princípio 1 fechado em 2 camadas:**
- **Camada 1** (PROMPT_4 Onda B): consultor assina o `RegulatoryDiagnosis` como um todo via `PATCH /validate`.
- **Camada 2** (PROMPT_6 + ADR-012 / PROMPT_7 + PROMPT_10/11): o gate de `PATCH /validate` exige `ProcessIssueDecision` registrada **neste processo** para issues críticas com `status_achado in {suspeita, confirmada, ignorada}`. Só `descartada` ("não é divergência real") e `resolvida` ("corrigida no mundo") são excluídas — nelas não há o que decidir. `ignorada` **continua exigindo decisão** (PROMPT_11): é achado real posto de lado, e setá-la não exige justificativa — ignorar um real passa por `decisao=ignorar_justificado` (com justificativa, #19), não por um status livre. Os 5 valores do enum de decisão (`corrigir_antes` / `seguir_com_ressalva` / `solicitar_doc` / `fora_escopo` / `ignorar_justificado`) são **todos** decisões válidas que liberam o gate — o princípio é "obrigar a decidir", não "obrigar a corrigir" (radar-não-cancela preservado). Cada processo recomeça do zero — decisão em outro processo da mesma property não libera (ADR-012).

#### Shape do 422 do gate (camada 2)

```json
{
  "detail": {
    "message": "3 alerta(s) crítico(s) sem decisão do consultor — camada 2 do Princípio 1 exige decisão alerta por alerta antes da assinatura do diagnóstico",
    "alertas_pendentes": [
      {"id": 42, "codigo_alerta": "GEO_AUSENTE", "familia": "geo_incra", "severity": "critico"},
      {"id": 43, "codigo_alerta": "EMBARGO_NAO_INFORMADO", "familia": "restricao_risco", "severity": "critico"},
      {"id": 44, "codigo_alerta": "RL_CAR_X_REALIDADE", "familia": "ambiental", "severity": "critico"}
    ]
  }
}
```

A UI consome esse shape para mostrar cada alerta pendente e levar o consultor à tela de decisão.

#### Coerência entre status do alerta (PROMPT_8 — #17)

Duas regras semânticas barram combinações que o negócio considera incoerentes, sem
construir máquina de estados completa. Fonte da verdade:
`app/services/regulatory_coherence.py`.

- **Regra A (perenes) — `PATCH /properties/{prop}/issues/{id}`**
  Saneamento em estado **ativo** (`em_validacao`) ou **concluído** (`saneado`) exige
  `status_achado in {confirmada, resolvida}`. Validada sobre o estado **resultante**
  (corpo aplicado sobre a issue carregada — cobre PATCH parcial). Quando os 2 status
  vêm juntos no body, dispara fast-fail no `@model_validator` do
  `RegulatoryIssueUpdate`. Mensagem: *"Combinação inválida: saneamento '<x>' exige que
  o achado esteja 'confirmada' ou 'resolvida' (atual: '<y>')."*

- **Regra B (cross-entidade) — `PUT /processes/.../issues/.../decision`**
  Bloqueia o registro de decisão quando `issue.status_achado == suspeita` —
  decide-se o que fazer com a divergência só depois de confirmar que ela é real.
  Mensagem: *"Não é possível registrar decisão: o achado ainda está como 'suspeita'.
  Confirme ou descarte o achado antes de decidir."*

Shape do 422 (string simples em `detail`, distinto do shape do gate camada 2):

```json
{ "detail": "Não é possível registrar decisão: o achado ainda está como 'suspeita'. Confirme ou descarte o achado antes de decidir." }
```

**Heads-up de UX:** pela Regra B, um alerta crítico em `suspeita` não aceita decisão —
e o gate de `/validate` exige decisão. A UI dos 5 botões precisa expor a transição do
`status_achado` (PATCH `/issues`) no mesmo fluxo da decisão, senão trava no gate sem
caminho.

### Extração por processo (`POST /api/v1/processes/{id}/extract`) — fix/extrator-por-processo

Dispara extração de campos em **todos** os documentos do processo em um clique.
Para cada `Document` (`tenant_id` + `process_id` + `deleted_at IS NULL`):

- **Com `extracted_text` cacheado e `force=false`:** enfileira
  `workers.run_agent.delay(agent_name="extrator", process_id=…, metadata={document_id, document_type})`.
  Entra em `jobs` da resposta com `method="extract"`.
- **Sem `extracted_text` ou `force=true`:** enfileira
  `workers.ocr_then_extract.delay(doc_id=…, force=…)`. A chain roda OCR
  (pypdf → Gemini Vision → OpenAI Vision) e ao final despacha o
  `extrator`. Entra em `pending_ocr` com `method="ocr_then_extract"`.

**Auditoria:** grava `AuditLog(action="extractor_dispatched", details="…")`.
**404:** processo sem documentos. **200:** mesmo se *zero* tasks
enfileiram com sucesso (skipped/failures vão no shape).

**Body (opcional):**
```json
{ "force": false }
```

**Resposta 200:**
```json
{
  "process_id": 42,
  "total_docs": 3,
  "jobs":         [{"document_id": 11, "filename": "matricula.pdf", "document_type": "matricula", "method": "extract", "task_id": "…"}],
  "pending_ocr":  [{"document_id": 12, "filename": "ccir.pdf",      "document_type": "ccir",      "method": "ocr_then_extract", "task_id": "…"}],
  "skipped":      []
}
```

> **Por que existe.** Antes, "Executar" do `extrator` na página `/agents`
> sem metadata era no-op silencioso ("Nenhum documento fornecido"). O
> caminho explícito por processo cobre o fluxo natural da consultora:
> abrir caso → subir docs → clicar uma vez.

### Preview lateral + reconciliação do intake (feat/intake-campos-backend)

Decisões Isis 2026-05-28. Dois endpoints novos sobre o draft, para a UX de
cadastro com preview da extração da IA e reconciliação cliente × IA (Opção A —
decisão na divergência). A UI que os consome vem na PR de frontend.

**`GET /api/v1/intake/drafts/{draft_id}/extracted-fields`** — preview lateral.
Agrega o AIJob mais recente do `extrator` por documento do draft e devolve, por
campo: `value`, `confidence`, `source_document_id`, `source_document_name` e
`diverges_from_manual` (valor digitado ≠ extraído e ainda não reconciliado).

```json
{ "draft_id": 12, "has_divergence": true,
  "fields": [ {"field": "car_numero", "value": "GO-IA-999", "confidence": 0.93,
               "source_document_id": 5, "source_document_name": "car.pdf",
               "diverges_from_manual": true} ] }
```

**`POST /api/v1/intake/drafts/{draft_id}/reconcile`** — resolve UM campo
divergente. Body `{field, source, value}` com `source ∈ {manual, extracted}`
(fora disso → 422). Grava `form_data["field_sources"][field]` e fixa o valor em
`form_data["reconciled"][field]`; as colunas reais (`Client`/`Property.field_sources`)
são preenchidas no commit do draft. Registra `AuditLog` (`entity_type=intake_draft`,
`action=reconciled`, hash chain). Retorna o `field_sources` atualizado.

> **E-mail obrigatório** (decisão Isis): `IntakeClientCreate.email` virou
> campo requerido com validação — `create-case`/draft commit com e-mail vazio
> ou ausente → 422. `audio_url` (entrevista) é aceito no payload e carregado
> para transcrição futura pelo agente de atendimento (transcrição = PR própria).

> **`draft_id` no `/create-case` (fix Isis 2026-05-31):** campo opcional. Quando presente, após criar
> cliente/imóvel/processo/checklist o endpoint migra os `Document`s do `IntakeDraft` (`process_id IS
> NULL`, `deleted_at IS NULL`) para o processo + `auto_link` no checklist, na mesma transação. `draft`
> inexistente ou de outro tenant → 404; já finalizado → 409. Sem `draft_id` → comportamento inalterado.
> `/drafts/{id}/commit` segue existindo (deprecated).

### Canal WhatsApp inbound (`POST /api/v1/messaging/whatsapp/webhook`, PR 2.1)

`app/api/v1/messaging.py` — webhook chamado pelo **provider externo** (Evolution API)
quando o cliente manda mensagem de WhatsApp. Integra a mensagem a um **caso já aberto** —
inbound **nunca cria caso** (decisão fechada 2026-05-28).

**Autenticação — não usa JWT.** O provider externo é quem chama, então não há `Authorization`
nem `X-Auth-Profile`. A autenticidade vem de **HMAC-SHA256 do corpo cru** no header
`X-Hub-Signature-256` (aceita `sha256=<hex>` ou `<hex>` puro), validado contra
`EVOLUTION_WEBHOOK_SECRET`. **Sem secret configurado** o webhook **não exige assinatura**
(modo dormente — útil enquanto não há credenciais). HMAC inválido → **401**.

**Fluxo de identificação (resumo — detalhe em [`FLUXOS_E2E.md`](./FLUXOS_E2E.md) fluxo 7):**

1. Acha o `Client` pelo telefone (normalizado, casando pelos **últimos 8 dígitos** em
   `phone`/`secondary_phone`). O `tenant_id` é derivado do `Client`.
2. Pega o `Process` **mais recente não terminal** (status ∉ `{concluido, arquivado, cancelado}`,
   `deleted_at IS NULL`). Grava `Message` (`status="received"`, `external_msg_id` = id do provider)
   na `CommunicationThread` de canal `whatsapp` do caso.
3. **Sem caso aberto** → grava `Message` em `CommunicationThread` **órfão** (`process_id NULL`)
   + alerta interno (`publish_realtime_event` evento `messaging.inbound_orphan` + `AuditLog action="inbound_orphan"`).
4. **Sem `Client`** → ignora com log (resposta `status:"ignored"`), não cria caso.
5. **Mídia:** se `media_url` presente **E** há caso aberto, baixa via `httpx` e grava como
   `Document` (`source="whatsapp"`, `document_category="whatsapp_inbound"`). Best-effort —
   falha no download não derruba o webhook.

**Respostas:**

```json
// 200 — ingerido com sucesso (caso aberto ou órfão)
{ "status": "ok", "thread_id": 12, "message_id": 84, "orphan": false, "document_id": 31 }

// 200 — descartado (remetente sem Client, corpo não-JSON, payload não parseável, sem remetente)
{ "status": "ignored", "reason": "unknown_sender" }   // ou: invalid_json | unparseable | no_sender
```

`401` apenas quando o HMAC é inválido. Demais condições devolvem `200` (com `status:"ignored"`)
de propósito — o provider só faz retry em `5xx`, e não queremos reentrega de payload inválido.

> **Provider plugável.** O parsing do payload vem de `app/services/messaging/`
> (`get_whatsapp_provider()` lê `settings.WHATSAPP_PROVIDER`, default `evolution`).
> `EvolutionProvider` é real; `ZAPIProvider` é stub. Ver [`INTEGRACOES_GOVTECH.md`](./INTEGRACOES_GOVTECH.md).

> **Limitação conhecida — sem idempotência.** Reentrega do mesmo evento pelo provider
> grava `Message` duplicada (não há dedupe por `external_msg_id` ainda). Aceitável no
> estado dormente; endurecer junto com a ativação das credenciais.

> **E-mail inbound (Resend) NÃO existe.** Não há webhook de e-mail nesta superfície — só
> placeholders de config (`EMAIL_INBOUND_PROVIDER`, `RESEND_INBOUND_WEBHOOK_SECRET`).
> Resend Inbound não está habilitado no plano/domínio.

### Webhooks / async

Endpoints assíncronos que dependem de Celery retornam 202 com `job_id`:

```json
POST /api/v1/ai/classify-async
→ 202 Accepted
{
  "job_id": 187,
  "status": "queued",
  "poll_url": "/api/v1/ai/jobs/187"
}
```

Cliente faz polling em `GET /api/v1/ai/jobs/{job_id}` ou recebe via WebSocket (`event_type = "ai_job_completed"`).

## Endpoints de IA detalhados

### Síncronos (`/api/v1/ai/...`)

| Endpoint | Função |
|---|---|
| `POST /api/v1/ai/classify` | Classifica demanda a partir de texto |
| `POST /api/v1/ai/extract` | Extrai campos de documento (passa `document_id`) |

### Assíncronos (mesma família + `-async`)

| Endpoint | Função |
|---|---|
| `POST /api/v1/ai/classify-async` | Mesma classificação, retorna `job_id` |
| `POST /api/v1/ai/extract-async` | Idem extração |

### Jobs

| Endpoint | Função |
|---|---|
| `GET /api/v1/ai/jobs` | Lista AI Jobs do tenant (paginação, filtro por agente/status) |
| `GET /api/v1/ai/jobs/{id}` | Detalhe de um job |
| `GET /api/v1/ai/jobs/{id}/status` | Polling leve (só status + progress) |

### Agentes individuais

| Endpoint | Função |
|---|---|
| `GET /api/v1/agents` | Lista os 10 agentes registrados |
| `POST /api/v1/agents/{name}/run` | Executa agente específico com metadata |
| `GET /api/v1/agents/budget` | Orçamento mensal de IA do tenant (Sprint R) |

### Trilha regulatória

| Endpoint | Função |
|---|---|
| `POST /api/v1/processes/{id}/apply-workflow` | Aplica o `WorkflowTemplate` do `Process.demand_type` e cria tarefas. **422** quando o processo não tem `demand_type` ou quando o `demand_type` não tem `WorkflowTemplate` ativo. A mensagem indica o tipo sem template para ação operacional. |

## WebSocket

- Endpoint: `ws://localhost:8000/ws?token=<JWT>`
- Autenticação: token JWT na query string (não cabe header em WebSocket nativo do browser)
- Canais: por `tenant_id` (via Redis pubsub no canal `amigao_events`)
- Eventos emitidos:
  - `ai_job_completed` — quando um job assíncrono termina
  - `process_status_changed` — quando processo muda de estado
  - `task_assigned` — quando tarefa é atribuída
  - `document_processed` — quando OCR + extração terminam
  - `notification` — notificação genérica do tenant

## Headers de resposta importantes

| Header | Significado |
|---|---|
| `X-Trace-Id` | ID propagado por toda a requisição. Usar em troubleshooting. |
| `X-Request-Duration-Ms` | Latência da requisição (debug). |
| `X-RateLimit-Remaining` | Quantas requisições restam na janela atual (quando rate limit ativo). |
| Headers de segurança | `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`, etc. (via `SecurityHeadersMiddleware`). |

## Endpoints públicos (sem auth)

| Endpoint | Função |
|---|---|
| `GET /` | Identidade da API |
| `GET /health` | Health check (200 OK quando saudável) |
| `GET /metrics` | Métricas Prometheus (proteger por rede no prod, não por auth) |
| `POST /api/v1/waitlist` | Lead anônimo (rate-limited 10/min) |
| `POST /api/v1/messaging/whatsapp/webhook` | Webhook do provider de WhatsApp — **sem JWT**, mas autenticado por HMAC-SHA256 (`X-Hub-Signature-256`) quando `EVOLUTION_WEBHOOK_SECRET` está setado (ver seção do canal acima) |

Nenhum outro endpoint é público. Todos os demais exigem JWT válido (o webhook de
WhatsApp é "sem JWT" por ser chamado por provider externo, mas é gated por HMAC).

## Pendências e dívidas

1. **Documentar estratégia de versionamento como ADR formal.** Hoje apenas mencionado em docs antigos.
2. **Padronizar paginação** — alguns endpoints usam `skip/limit`, outros não paginam. Auditar.
3. **OpenAPI tags inconsistentes** — alguns prefixos repetem (`/api/v1/processes` aparece em 7 routers diferentes). Funciona, mas dificulta navegação no `/docs`. Avaliar consolidação em sprint dedicada.
4. **CORS** — em `BACKEND_CORS_ORIGINS` no `.env.example`. Em prod, incluir `https://regenteambiental.com.br` e `https://www.regenteambiental.com.br`.
5. **Swagger desabilitado em prod** — checklist em `ops/production-secrets-checklist.md` exige `ENVIRONMENT=production` resultar em `/docs` desabilitado.

## Próximas leituras

- [`GOVERNANCA_IA.md`](./GOVERNANCA_IA.md) — política aplicada nos endpoints de IA
- [`OBSERVABILIDADE.md`](./OBSERVABILIDADE.md) — trace_id e métricas
- [`MULTITENANT_LGPD.md`](./MULTITENANT_LGPD.md) — isolamento aplicado na camada API
