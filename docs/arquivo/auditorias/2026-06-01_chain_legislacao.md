# Auditoria — chain `diagnostico_completo` e timeout da legislação

Data: 2026-06-01  
Branch: `fix/chain-legislacao-timeout`

## Contexto

No mergulho do fluxo agêntico, a chain `diagnostico_completo` parava antes do
diagnóstico quando `legislacao` falhava por timeout. A ordem real no código é:

`extrator → auditor_imovel → legislacao → diagnostico`

Fonte: `app/agents/orchestrator.py:CHAINS`.

## Medição rodando

Stack confirmado com `docker compose ps`: `api`, `worker`, `db`, `redis` e
`minio` estavam `Up`; `db` healthy.

Config efetiva no container:
- `AI_ENABLED=True`
- `ai_configured=True`
- `AI_TIMEOUT_SECONDS=30.0`
- `GEMINI_API_KEY` presente
- `OPENAI_API_KEY` presente
- `LEGISLATION_RAG_TOP_K=8`

Medição local do `LegislacaoAgent` para `process_id=30`, `tenant_id=2`:
- Query: `Qual o caminho regulatorio para nao_identificado no estado MS?`
- RAG + embedding de query: `4510 ms`
- Chunks RAG: `0`
- Contexto por metadados: `503 ms`
- Contexto legislativo: `0 chars`

Medição da chamada LLM isolada:
- Modelo: `gemini/gemini-2.5-flash`
- Erro: `litellm.Timeout: Connection timed out after None seconds`
- Limite aplicável: `settings.AI_TIMEOUT_SECONDS`, usado em
  `app/core/ai_gateway.py:247` e passado para `litellm.completion` em
  `app/core/ai_gateway.py:263`.

Conclusão: o gargalo medido é a chamada LLM ao Gemini, não a query SQL/pgvector
nem o dump por metadados. O prompt deste caso era pequeno porque `demand_type`
estava `nao_identificado` e o filtro RAG não retornou chunks.

## Correção

Foram corrigidos dois bloqueios da chain:

1. `legislacao` agora é não-bloqueante por revisão apenas quando é insumo
   intermediário da chain `diagnostico_completo`.
2. Falha de `legislacao` nessa chain também é não-fatal: o erro é preservado em
   `ctx.chain_data["legislacao"]` e a chain continua para `diagnostico`.

A exceção é escopada por chain. `legislacao` continua sendo produto final nas
chains regulatórias (`analise_regulatoria`/`enquadramento_regulatorio`) e não
foi removida de nenhuma chain.

Também foi ajustado `BaseAgent.run()` para retornar o nome da classe da exceção
quando `str(exc)` vem vazio, evitando `AgentResult.error=""`.

## Revalidação rodando

### Cenário com timeout

Execução real:

`docker compose exec -T api python -c "... OrchestratorAgent.execute_chain('diagnostico_completo', ctx) ..."`

Resultado:
- `extrator`: success, `19410 ms`, AIJob `132`
- `auditor_imovel`: success, `145 ms`, AIJob `133`, `requires_review=True`
- `legislacao`: failed, `33611 ms`, AIJob `134`, timeout LLM
- `diagnostico`: success, `3746 ms`, AIJob `135`, `requires_review=True`

Evidência funcional: antes a chain parava em 3/4 e gerava `0` diagnósticos; após
a correção, `diagnostico` executou e entregou `3` itens em
`passivos_identificados`, com `situacao_geral` presente.

### Cenário sem timeout, mas com revisão

Nova execução real:
- `extrator`: success, `33270 ms`, AIJob `136`
- `auditor_imovel`: success, `179 ms`, AIJob `137`, `requires_review=True`
- `legislacao`: success, `33409 ms`, AIJob `138`, `requires_review=True`
- `diagnostico`: success, `8337 ms`, AIJob `139`, `requires_review=True`

Evidência funcional: mesmo com `legislacao.requires_review=True`, a chain chegou
ao `diagnostico`, que entregou `3` itens em `passivos_identificados`.

## Dívidas remanescentes

- #39 permanece aberta: robustez própria da `legislacao` (timeout/retry/parsing).
- #40 permanece aberta: dois `SKILL.md` inválidos ainda são reportados no runtime.
- #41 permanece aberta: `create-case` ainda não auto-dispara a chain; decisão de
  produto/custo.
