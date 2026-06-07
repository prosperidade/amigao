# Consistência dos agentes LLM — truncamento, fallback e golden tests

> Branch `fix/llm-consistencia` · 2026-06-07
> Frustração de origem: *"uma hora vai, outra não"* — o diagnóstico do caso real
> **#12** (228 campos, Fazenda São Jorge) falhava 3+ vezes seguidas.

## Diagnóstico (medido, não teorizado)

### Causa 1 — Truncamento (a falha de hoje)
O diagnóstico roda `gpt-4.1` (saída longa), mas com o teto **global**
`AI_MAX_TOKENS = 2048`. O formato pós-#70 (`{afirmacao, fonte, confianca}` em
cada passivo/ação) deixou o JSON 2-3× maior. No caso #12 a saída estourava 2048 →
`finish_reason=length` → JSON cortado no meio de `situacao_geral` → o parser caía
no erro **genérico** `json_parse` (`Não foi possível extrair JSON: {...`).
O gateway **nem capturava** `finish_reason`.

### Causa 2 — Legislação refém do provider
A legislação (e o diagnóstico) passavam `model=` explícito ao gateway. Nesse
caminho `models = [(model, "")]` — **um único modelo, sem cadeia de fallback**.
Um Gemini 503 derrubava a consulta inteira.

### max_tokens por agente — ANTES
| Agente | Modelo primário | max_tokens | Fallback |
|---|---|---|---|
| diagnostico | gpt-4.1 | **2048** (global) | não |
| legislacao | gemini-2.5-flash/pro | 8192 | não |
| redator | default | 4096 | sim |
| extrator/atendimento/vigia | gpt-4o-mini | 2048 | sim |

## O que foi feito

### Item 1 — Truncamento
- `AIResponse.finish_reason` capturado **sempre** (`_normalize_finish_reason`:
  OpenAI `length` / Anthropic `max_tokens` → `length`). Vale para litellm e
  para o `ClaudeClient` (SDK direto).
- **Retry inteligente**: `finish_reason=length` → 1 retry automático com
  `max_tokens` **dobrado** (até `AI_MAX_TOKENS_CEILING`). Se ainda truncar →
  `AITruncationError` com mensagem **específica e legível** (*"resposta truncada
  (limite de tokens)…"*), distinta do erro de parse, logada com tokens usados.
  Não cascateia pra outro provider (o teto seria o mesmo).
- **Sem parse parcial silencioso**: o parser segue levantando em truncamento; o
  gateway barra antes via `finish_reason`. `base.run()` agora propaga a
  `.message` legível ao `AgentResult.error` (antes virava só `"AITruncationError"`).

### max_tokens por agente — DEPOIS
| Agente | max_tokens | cost cap | Observação |
|---|---|---|---|
| **diagnostico** | **32.768** (`AI_DIAGNOSTICO_MAX_TOKENS`, máx. do gpt-4.1) | $0.50 (`AI_MAX_COST_PER_JOB_USD_DIAGNOSTICO`) | peça fundamental — máximo de saída |
| legislacao | 8192 (inalterado) | $0.30/$5.00 | — |
| redator | 4096 | global | — |
| extrator/atendimento/vigia | **4096** (global subido de 2048) | global | retry dobra até 32.768 se truncar |

### Item 2 — Matriz de equivalência agente×provider (BYOK-ready)
- Novo `app/core/model_matrix.py`: cada agente declara o modelo equivalente em
  cada provider (OpenAI/Google/Anthropic). Todos os modelos vêm de `settings`
  (env-configurável — nada hardcoded; lição do gemini-2.0-flash descontinuado).
- `resolve_agent_models(agent, settings, primary_model)`:
  - restringe aos providers da casa **com chave disponível**;
  - **preserva o primário** do agente em 1º (esta matriz só ADICIONA fallback,
    nunca troca o primário — `PROIBIDO` respeitado);
  - acrescenta equivalentes em **outros providers disponíveis** como resiliência
    (503/timeout);
  - tenant com **1 provider só** → roda nele, sem erro de config.
- Gateway aceita `agent_name=`; diagnóstico e legislação passam o seu. O
  white-label do consultor (`user_preferences`) continua com precedência.

### Item 3 — Golden tests (cinto de segurança no CI)
- `tests/agents/golden/` — respostas LLM gravadas do caso São Jorge:
  - formato novo (#70) → parser/agente produzem o shape esperado;
  - truncada → erro **específico** (não parse genérico), sem reparo silencioso;
  - fonte inexistente/vazia → marcada `sem_fonte=True` (nunca inventada).
- `tests/core/test_ai_gateway.py` (novos): finish_reason capturado; retry de
  truncamento; `AITruncationError`; fallback por `agent_name` em 503; provider único.
- `tests/core/test_model_matrix.py`: resolução da matriz.

## Embeddings — DECISÃO TOMADA
Anthropic **não tem API de embeddings**. **Decisão de produto:** embeddings
**sempre** com a **chave da casa** (custo ínfimo), independentemente de qual
provider o consultor configurou para geração de texto (BYOK). Continuam
resolvidos por `EMBEDDING_PROVIDER` (OpenAI/Gemini) — **fora desta matriz**, que
cobre só geração de texto. **Não migramos embeddings existentes neste PR**
(trocar provider de embedding exige re-embedar todos os chunks — vetores entre
provedores são incompatíveis).

## Log do provider/modelo efetivo por job
Monitorável por job: `ai_gateway.complete` loga `model=… tokens_in/out cost_usd`
e o `AIJob` persiste `model_used`, `provider`, `tokens_in/out`, `cost_usd` —
inclusive quando o fallback assume um provider diferente do primário.

## Settings novos
`AI_DIAGNOSTICO_MAX_TOKENS=32768` · `AI_MAX_COST_PER_JOB_USD_DIAGNOSTICO=0.50` ·
`AI_MAX_TOKENS_CEILING=32768` · `AI_LEGAL_MODEL_OPENAI=gpt-4.1-mini` ·
`AI_HAIKU_MODEL=claude-haiku-4-5-20251001` · `AI_MAX_TOKENS` 2048→4096.

## Validação
- Caso #12 real: diagnóstico conclui N× seguidas (rodar 3×). *(ver REPORT no PR)*
- 503 do primário → fallback assume (`test_agent_name_falls_back_to_equivalent_provider_on_503`).
- Golden + gateway + matriz verdes; truncamento simulado → erro específico.
