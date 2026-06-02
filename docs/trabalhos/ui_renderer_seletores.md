# Trabalho — UI: renderer humanizado + seletores cliente/imóvel

> Arquivo único de trabalho. Problema → causa medida → fix → validação → status.
> Branch: `fix/ui-renderer-seletores` (base `main`). Data: 2026-06-02.
> Fecha dívidas **#UX-1** (seletor de cliente) e **#UX-2** (seletor de imóvel).

## Problema 1 — Resultado dos agentes saía como JSON cru

Na aba Agentes, o resultado de cada job vinha como JSON cru / `[object Object]`
em vez dos cards humanizados, e o cabeçalho de execução mostrava
`Agente —`, `Modelo —`, `Provedor —`, `Tokens —`, `Duração 0.0s`.

O frontend (`AgentResultRenderer.tsx`) escolhe o renderer humanizado por
`agentName` (`renderers[agentName]`). Sem `agent_name`, cai no `GenericResult`,
que fazia `JSON.stringify(value)`.

## Causa (medida — não assumida)

A hipótese inicial do prompt era "o `AIJob` da chain não popula `agent_name`".
**Falso, verificado no banco.** `BaseAgent.run()` (`app/agents/base.py`) grava
`agent_name` em `_create_running_job` **tanto no disparo avulso quanto na chain**:

```
id  | agent_name     | chain_trace_id   | model_used   | provider
139 | diagnostico    | c888107f9ec04cbd | gpt-4o-mini  | gpt
138 | legislacao     | c888107f9ec04cbd | gemini/...   | gemini
137 | auditor_imovel | c888107f9ec04cbd | (null)       | (null)
136 | extrator       | c888107f9ec04cbd | (null)       | (null)
```

`agent_name` **está preenchido**. `model_used`/`tokens` ficam nulos só para
agentes que **não chamam LLM** (`extrator` faz OCR/extração; `auditor_imovel` é
determinístico) — isso é correto, não é bug.

**Causa raiz real:** o serializer `_serialize_job` em `app/api/v1/ai.py` (rota
`GET /ai/jobs`, consumida pela aba Agentes) **omitia `agent_name`** da resposta.
O banco persistia, a API descartava → o front recebia `agent_name = undefined`
→ `GenericResult` → JSON cru. O `model_used`/`provider`/`tokens` já eram
serializados (por isso o card mostrava `—` só para os agentes sem LLM).

## Problema 2 — Seletores pediam ID digitado

`IntakeWizard.tsx` pedia "ID do cliente" e "ID do imóvel" como texto. O consultor
não decora IDs. O backend já expõe `GET /clients/` e `GET /properties/?client_id=`.

## O que mudou

| Arquivo | Mudança |
|---|---|
| `app/api/v1/ai.py` | `_serialize_job` agora inclui `agent_name` e `chain_trace_id`. **É o fix da causa raiz** do JSON cru. |
| `frontend/src/components/AgentResultRenderer.tsx` | Novo `AuditorResult` (lista `divergencias`: tema/divergência/impacto; esconde `findings_raw`/`issue_ids`/`method`/`geom_present`). Registrado no dispatch + ícone + título. `DiagnósticoResult` ganhou seção de `divergencias`. `GenericResult` endurecido: **nunca** faz `JSON.stringify`/`[object Object]` — escalares viram linha, arrays de string viram bullets, arrays/objetos com campos escalares viram cards rotulados, aninhamento profundo é omitido; esconde meta (`confidence`, `requires_review`, `geom_present`, `method`, `issue_ids`, `metadata`, `*_raw`). |
| `frontend/src/types/agent.ts` | `AIJob.chain_trace_id`; `auditor_imovel` em `AGENT_LABELS`. |
| `frontend/src/pages/Intake/IntakeWizard.tsx` | Novo `SearchSelect` (dropdown com busca). "Cliente existente" lista `GET /clients/` (nome + CPF/CNPJ). "Imóvel existente" lista `GET /properties/?client_id=` do cliente escolhido; desabilitado sem cliente. Trocar de cliente limpa o imóvel. Resumo do Confirmar mostra **nome** em vez de `ID #x`. |

## Validação (rodando — API real, core de pé)

**Frente A — `agent_name` na resposta da API** (`GET /api/v1/ai/jobs`, token admin):

```
id  agent_name     chain_trace_id    model_used    provider  duration_ms
139 diagnostico    c888107f9ec04cbd  gpt-4o-mini   gpt       8337
138 legislacao     c888107f9ec04cbd  gemini/...    gemini    33409
137 auditor_imovel c888107f9ec04cbd  (null)        (null)    179
136 extrator       c888107f9ec04cbd  (null)        (null)    33270
```

`agent_name` + `chain_trace_id` presentes. → o front dispara o renderer certo
(#139 → `DiagnósticoResult`, #137 → novo `AuditorResult`) e o card de execução
mostra Agente/Modelo/Provedor/Tokens/Duração preenchidos para quem chama LLM.

Shapes batidos contra o banco: `result` de #139 tem `situacao_geral`, `riscos[]`,
`acoes_remediacao[]`, `checklist_documental[]`, `hipoteses[]`, `divergencias[]`,
`sources[]` — todos lidos pelo `DiagnósticoResult` sem objeto cru. `result` de
#137 tem `content` + `divergencias[]` — lidos pelo `AuditorResult`.

**Frente C — seletores** (`GET /clients/`, `GET /properties/?client_id=`):

```
CLIENTES: 16   (ex: "Fazenda Boa Vista Agropecuaria" — 00.000.002/0001-00)
IMÓVEIS do cliente #3: 1   (id 7 — "Teste Sprint I" — Goiânia/GO)
```

Endpoints retornam dados → dropdowns populam por nome.

**Typecheck:** `npx tsc --noEmit` no `frontend/` passou sem erros.

## Status

✅ Concluído. Causa raiz (serialização omitia `agent_name`) confirmada e corrigida.
Renderers humanizados (incl. `auditor_imovel`) e `GenericResult` à prova de JSON
cru. Seletores de cliente/imóvel no intake. #UX-1 e #UX-2 fechadas.
