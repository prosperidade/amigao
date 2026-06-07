# Golden fixtures — respostas LLM gravadas dos agentes

> fix/llm-consistencia (2026-06-07). Cinto de segurança da esteira: toda mudança
> futura de prompt/parser/formato de saída LLM passa por aqui ANTES do merge.

Cada arquivo é uma **resposta LLM real (ou fiel ao real)** gravada do caso
**Fazenda São Jorge** — o caso grande que exercita o formato pós-#70
(`{afirmacao, fonte, confianca}`). Os testes em `tests/agents/test_golden_agents.py`
alimentam o **parser/agente** com estas fixtures e exigem que:

1. o parser processe **sem erro** e produza o **shape esperado**;
2. resposta **truncada** vire o **erro específico** de truncamento (não o erro
   genérico de parse);
3. afirmação com **fonte inexistente / vazia** seja marcada como
   `sem_fonte=True` ("fonte não verificada") — nunca inventada.

| Fixture | O que representa |
|---|---|
| `diagnostico_sao_jorge_p70.json` | Diagnóstico grande no formato #70 (passivos/ações + `afirmacoes` com fonte/confiança) |
| `diagnostico_fonte_inexistente.json` | Diagnóstico cujo `afirmacoes` traz fonte vazia/"sem fonte" → tem que marcar não-verificada |
| `diagnostico_truncado.txt` | Saída crua TRUNCADA (JSON cortado no meio) → parser não pode reparar em silêncio |
| `legislacao_sao_jorge.json` | Resposta do agente legislação (caminho regulatório + legislação aplicável) |

**Como regravar:** rode o agente real contra o caso e salve `response.content`
(o texto cru do LLM) aqui. Não edite à mão para "consertar" — se o real mudou, o
golden test deve pegar a mudança.
