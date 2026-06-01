# Mergulho arquitetural — fluxo agêntico + intake (sistema RODANDO)

**Data:** 2026-06-01
**Branch:** `fix/mergulho-fluxo-agentico`
**Postura:** execução, não leitura. Todo achado abaixo foi reproduzido com o
sistema de pé (request/log/SQL reais). O que não foi reproduzido está marcado
como **pergunta em aberto**, não conclusão.

**Ambiente do mergulho:** `docker compose up -d db redis minio api worker` (sem
Evolution — PR #44 mergeado). `AI_ENABLED=true`, OpenAI + Gemini com chave.
Login `admin@amigao.com` (user 1, tenant 2, superuser). `/health` 200.

---

## TL;DR (resumo executivo)

O fluxo agêntico **funciona em pedaços** — não é "tudo quebrado" nem "tudo
funciona":

- **OCR + extrator + atendimento FUNCIONAM** no fluxo real de intake (provado
  com caso reproduzido ponta a ponta: matrícula → 12 campos extraídos).
- **O que trava a entrega de diagnóstico** é a soma de três coisas:
  1. **`create-case` dispara só o `atendimento`** — a chain de diagnóstico
     (`diagnostico_completo`) nunca é acionada automaticamente. (design)
  2. Quando a chain É acionada, o **`extrator` pulava** ("chamado sem
     documento") porque a chain não passa `document_id`. **(P0 — corrigido)**
  3. A **`legislacao` é um passo bloqueante que falha de forma intermitente**
     (timeout de LLM / json_parse), e ao falhar **aborta a chain antes do
     `diagnostico` rodar** → nenhum diagnóstico é gravado. (P1 — plano)
- O **"CORS" do `/threads`** em produção **é um 500 mascarado**: respostas 500
  saíam sem `Access-Control-Allow-Origin` e o navegador reportava como CORS.
  **(P0 — corrigido: 500 agora carrega CORS + request_id)**.
- O **WebSocket** falha em produção por **mismatch de path**: o front conecta em
  `/api/v1/ws`, a rota nascia só em `/ws` → 403. **(P0 — corrigido: rota montada
  nos dois caminhos)**. A queda do WS **não** derruba a UI (o `onerror` é
  silencioso) — não é causa do Error Boundary.

**Corrigidos neste PR (revalidados rodando):** CORS-mascara-500, path do WS,
gap de orquestração do extrator.
**Viram plano (P1/P2):** chain aborta na legislacao, robustez da legislacao,
auto-trigger da chain pós-case, 2 SKILL.md inválidos, Error Boundary global.

---

## A. Mapa do fluxo agêntico (com evidência)

```
intake wizard
  │
  ├─(1) POST /intake/classify ─────────────► classificador (LLM) ✅
  │        evidência: demand_type=misto, required_documents=[matricula,ccir,car,doc_pessoal]
  │
  ├─(2) POST /intake/drafts ──────────────► draft 11 (rascunho) ✅
  ├─    POST /drafts/11/upload-url ───────► presigned MinIO ✅ (ver nota bucket P1)
  ├─    PUT MinIO (bytes) ─────────────────► HTTP 200 ✅
  ├─    POST /drafts/11/documents ────────► Document 49 (intake_draft_id=11, process_id=NULL) ✅
  │
  ├─(3) POST /drafts/11/import ───────────► ocr_then_extract ✅
  │        OCR: doc=49 method=pypdf chars=345 (AIJob 119) ✅
  │        └─ run_agent(extrator, document_id=49) ──► extrator ✅
  │             AIJob 120: doc_type=matricula, fields_count=12
  │             {numero_matricula:12.345, proprietario:Romilton, area_hectares:250.0, uf:MS, ...}
  │
  ├─(4) POST /intake/create-case (draft_id=11) ──► process 30 + client 21 + property 11 ✅
  │        Document 49 migrado: process_id=30, client_id=21, property_id=11 ✅
  │        checklist auto-link: item matricula → status=received, document_id=49 ✅
  │        agente disparado: SOMENTE atendimento (AIJob 121) ⚠️  ← nada de diagnóstico/legislação
  │
  └─(5) [manual] POST /agents/chain-async diagnostico_completo process=30
           extrator (122) ──► SKIP "chamado sem documento" (chain não passa document_id)  ❌→✅ corrigido
           auditor_imovel (123) ──► completed (review=True, NON_BLOCKING) ✅
           legislacao (124) ──► FAILED litellm.Timeout ❌ (bloqueante)
           diagnostico ──► NÃO RODOU (chain parou em 3/4)  ❌
           regulatory_diagnoses para process 30: 0 linhas
```

Cadeia `diagnostico_completo = [extrator, auditor_imovel, legislacao, diagnostico]`
(`app/agents/orchestrator.py`). `MACROETAPA_CHAINS` mapeia
`diagnostico_preliminar`/`diagnostico_tecnico → diagnostico_completo`, mas
`create-case` cria o processo em `entrada_demanda` e dispara só `atendimento`
(`app/api/v1/intake.py`, gatilho ~linha 371) — nenhuma macroetapa de diagnóstico
é inicializada/rodada automaticamente.

## B. Tabela dos 11 agentes (baseada em execução)

| Agente | Roda? | Recebe contexto certo? | Entrega resultado? | Evidência |
|---|---|---|---|---|
| `atendimento` | ✅ sim | ✅ process_id+metadata | ✅ demand_type/required_docs | AIJob 121 (case 30) |
| `extrator` | ✅ sim | ⚠️→✅ document_id no /import; **na chain pulava** sem document_id | ✅ 12 campos (/import) | AIJob 120 ok; 122 skip→**126 resolvido (9 campos)** pós-fix |
| `auditor_imovel` | ✅ sim | ✅ via chain_data | ✅ review=True (não bloqueia) | AIJob 123 |
| `legislacao` | ⚠️ intermitente | ✅ uf=MS | ❌ Timeout/json_parse → **bloqueia chain** | AIJob 124 (Timeout); 115 (json_parse); 116-118 ok |
| `diagnostico` | ❌ não alcançado | — | ❌ chain parou antes | 0 em `regulatory_diagnoses` p/ proc 30 |
| `acompanhamento` | — não exercitado | — | — | fora do fluxo de intake (beat/scheduled) |
| `financeiro` | — não exercitado | — | — | fora do fluxo de intake |
| `marketing` | — não exercitado | — | — | fora do fluxo de intake |
| `orcamento` | — não exercitado | — | — | macroetapa orcamento_negociacao |
| `redator` | — não exercitado | — | — | pós-diagnóstico |
| `vigia` | — não exercitado | — | — | beat/scheduled |

> "Não exercitado" = fora do caminho intake→diagnóstico testado neste mergulho;
> não significa quebrado. Registro honesto do que foi rodado.

## C. Causa raiz de cada quebra confirmada

### C1. "CORS" do `/threads` = 500 mascarado  — **CONFIRMADO**
- `GET /api/v1/threads/?process_id=8` local → **200 `[]`** (vazio e populado: 200
  com thread+message). O endpoint **não está quebrado em código**.
- Config CORS de produção (`render.yaml:46`) **inclui** `regenteambiental.com.br`
  → a origem É permitida; por isso `/clients` e `/properties` (2xx) não dão CORS.
- **Mecanismo provado:** `app/main.py` registra o `CORSMiddleware` como a
  middleware mais externa do usuário, mas o `ServerErrorMiddleware` do Starlette
  é ainda mais externo. Uma exceção não tratada (500) **sobe por fora** do
  CORSMiddleware → a resposta 500 sai **sem `Access-Control-Allow-Origin`**.
  Reprodução: `POST /threads/` com `process_id` inexistente (FK violation →
  IntegrityError → 500), `Origin: http://localhost:3000`:
  - 200 → tem `access-control-allow-origin`
  - 500 → **NÃO tem** `access-control-allow-origin`
  → o navegador reporta o 500 como "bloqueado por CORS".
- **Conclusão:** o "CORS do threads" em produção é um **500 no endpoint**,
  mascarado. **Qual** 500 (dado específico de prod) **não reproduziu localmente**
  → **pergunta em aberto**: pegar o `x-request-id` da request no log de prod.
  O fix de unmasking (abaixo) faz o navegador passar a mostrar o 500 real + o
  `request_id` em vez de "CORS".

### C2. WebSocket falha em produção — **CONFIRMADO**
- Rota real: `@router.websocket("/ws")` (`app/api/websockets.py:126`), token por
  query param `?token=`. (A memória que dizia `/ws/{tenant_id}/{user_id}` está
  **desatualizada** — verificado contra o código e rodando.)
- `main.py:167` montava o router **sem prefixo** → path real `/ws`.
- O front (`frontend/src/hooks/useAgentEvents.ts:14-26`) deriva
  `WS_BASE = VITE_WS_URL || VITE_API_URL.replace(http→ws)`. Em produção
  `VITE_API_URL` inclui `/api/v1` → conecta em `wss://api.../api/v1/ws`.
- Teste rodando (token válido): `/ws` → **conecta OK** (echo); `/api/v1/ws` →
  **HTTP 403** (rota não existe lá). ← causa raiz do WS de produção.
- A queda do WS **não derruba a UI**: `ws.onerror` é no-op silencioso
  (`useAgentEvents.ts:65`). **WS não é causa do Error Boundary.**

### C3. Gap de orquestração do extrator — **CONFIRMADO**
- `extrator.execute()` (`app/agents/extrator.py`) pulava quando não havia
  `document_id` nem `text` no metadata. A chain (`chain-async`) e a aba Agentes
  (`/agents/run-async` com `metadata:{}`) chamam exatamente assim → **skip**.
- Prova: AIJob 122 (chain) e 125 (run-async) → `skipped=True, fields_count=0`
  mesmo com `process_id=30` (que tinha o Document 49 já OCR'd).
- O consultor nunca digita id — o sistema tinha que propagar o contexto.

### C4. Chain aborta na legislacao → diagnóstico nunca roda — **CONFIRMADO**
- `app/agents/orchestrator.py:137-142`: `if not result.success: break`. Qualquer
  agente que falha **para a chain**.
- A `legislacao` falhou (AIJob 124: "Todos os providers falharam. Último erro:
  litellm.Timeout"); como é passo bloqueante, a chain parou em 3/4 e o
  `diagnostico` (4º) **não rodou**. `regulatory_diagnoses` para process 30: **0**.
- Intermitência confirmada: AIJob 115 falhou por `json_parse`, 116-118 passaram,
  124 deu Timeout. Logo: a entrega do diagnóstico fica refém da legislacao.

### C5. Error Boundary "Algo deu errado" — **PARCIAL (aberto o gatilho exato)**
- `QueryClient` (`frontend/src/App.tsx:22`) **não** usa `throwOnError`/
  `useErrorBoundary` → uma query que falha **não** estoura no boundary; ela seta
  `isError`. Logo o crash é **render-time** (acesso a `undefined` quando a query
  errou e o componente não guarda).
- Há **um único `ErrorBoundary` na raiz** (`App.tsx:33`) envolvendo o app todo →
  qualquer crash de render **apaga a aplicação inteira** ("Algo deu errado").
- **Não reproduzi o componente exato que estoura** (precisa de navegador/devtools,
  indisponível neste mergulho headless) → **pergunta em aberto**. O fix de
  unmasking de 500 (C1) e o de extrator (C3) reduzem causas upstream; a proposta
  estrutural (boundaries por rota/seção) está no plano.

## D. Classificação

### P0 — corrigidos NESTE PR (causa inequívoca, revalidados rodando)
1. **CORS mascara 500** → handler global de exceção reanexa CORS + `request_id`
   na resposta 500. Antes: 500 sem ACAO. Depois: 500 com
   `access-control-allow-origin` + `{"detail":...,"request_id":...}`.
2. **Path do WS** → router montado também sob `/api/v1`. Antes: `/api/v1/ws`=403.
   Depois: `/ws` e `/api/v1/ws` conectam.
3. **Extrator não propaga contexto** → `extrator.execute()` resolve os documentos
   do processo (com OCR) quando recebe só `process_id`. Antes: skip (0 campos).
   Depois: `resolved_from_process=30`, 9 campos extraídos.

### P1/P2 — viram dívida (sem meia-correção aqui)
- **P1 — chain aborta no 1º agente que falha** (C4). A legislacao (bloqueante e
  flaky) mata o diagnóstico. Proposta: tornar a falha da legislacao **não-fatal**
  para a chain (continuar até o diagnostico com contexto parcial — princípio
  "radar não cancela"), via um conjunto `NON_FATAL_CHAIN_AGENTS` espelhando o
  `NON_BLOCKING_REVIEW_AGENTS`. **Toca orquestração (chains "congeladas") → PR
  dedicado + aval do André.**
- **P1 — robustez da legislacao**: Timeout sem limite ("after None seconds") +
  `json_parse` intermitente. Endurecer timeout/parsing/retry.
- **P1 — `create-case` não auto-dispara a chain de diagnóstico** (C/A). Decisão de
  produto/custo: auto-rodar `diagnostico_completo` ao finalizar o caso? PR/decisão
  dedicada.
- **P2 — 2 SKILL.md inválidos** silenciosamente ignorados:
  `auditor_imovel/analise_divergencias_documentais` (`applies_to` deve ser
  mapping) e `diagnostico/situacao_ambiental_imovel_rural` (`agent` obrigatório).
  Agentes rodam sem suas skills procedurais.
- **P1 — bucket MinIO não garantido no upload presigned**: `_ensure_bucket_exists`
  só roda em put/get server-side, não na geração da URL presigned. Em ambiente
  novo o PUT do consultor dá 404 NoSuchBucket. (Prod já tem o bucket; latente.)
- **P1/estrutural — Error Boundary único na raiz** (C5): um crash de render apaga
  o app inteiro. Adicionar boundaries por rota/seção (degrade local). Gatilho
  exato pendente de repro em navegador.

## E. Código vs Infra (separação clara)

**CÓDIGO (corrigido/plano no repo):** C1, C2, C3 (corrigidos); C4, robustez
legislacao, SKILL.md, bucket presigned, Error Boundary (plano).

**INFRA (só o André aplica) — valores exatos:**
- **WebSocket em produção (Cloudflare + Render):**
  - Render Web Service já suporta WS nativamente (upgrade automático) — nada a
    fazer no Render além do deploy com o fix de path.
  - **Cloudflare:** Network → **WebSockets = ON** (padrão; confirmar que não foi
    desabilitado). Para o domínio `api.regenteambiental.com.br` com proxy laranja,
    WS passa quando WebSockets está ligado.
  - **Recomendado:** definir no build do front
    `VITE_WS_URL=wss://api.regenteambiental.com.br` (SEM `/api/v1`). Com o fix de
    path, o caminho `/api/v1/ws` também passa a funcionar mesmo sem essa env —
    mas setar `VITE_WS_URL` é o caminho limpo.
- **CORS de produção:** já correto (`render.yaml:46` inclui os 3 domínios). Não
  mexer. O "CORS do threads" não é config — é o 500 mascarado (C1).
- **Diagnóstico do 500 de prod do `/threads`:** com o fix de unmasking, abrir a
  request no navegador, pegar `request_id` do corpo/headers e cruzar no log do
  `regente-api` (Render) para achar a stacktrace real.
