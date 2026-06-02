# Trabalho — Modelo do agente de diagnóstico → GPT-4.1

> Arquivo único de trabalho. Pedido → mudança → validação → status.
> Branch: `fix/diagnostico-modelo-gpt41` (base `main`). Data: 2026-06-02.

## Pedido (André)

O card de execução do agente de diagnóstico mostrava `Modelo: gpt-4o-mini`.
Trocar o modelo do **diagnóstico** para **GPT-4.1** (peça mais complexa do funil:
cruza extrator + auditor + legislação).

## O que mudou (cirúrgico — só o diagnóstico)

Seguindo a convenção que o `legislacao` já usa (passa `model=` próprio por env,
ver `GEMINI_LEGAL_MODEL`), o modelo vai **por setting, nunca hardcoded no agente**
(deprecation futura = troca de variável, não de código — lição do OCR `gemini-2.0`).

| Arquivo | Mudança |
|---|---|
| `app/core/config.py` | Novo setting `AI_DIAGNOSTICO_MODEL` (default `"gpt-4.1"`). Vazio cai no `AI_DEFAULT_MODEL`. |
| `app/agents/diagnostico.py` | `call_llm(...)` agora passa `model=settings.AI_DIAGNOSTICO_MODEL or AI_DEFAULT_MODEL`. White-label do consultor (`user_preferences`) mantém precedência no gateway. |
| `docker-compose.yml` | `AI_DIAGNOSTICO_MODEL: "${AI_DIAGNOSTICO_MODEL:-gpt-4.1}"` em `api` e `worker`. |
| `render.yaml` | `AI_DIAGNOSTICO_MODEL: gpt-4.1` (paridade prod). |

**Os demais agentes não foram tocados** — mudar o `AI_DEFAULT_MODEL` global
encareceria atendimento/orçamento/redator/etc. sem ter sido pedido.

**Nota:** passar `model=` explícito desativa a cadeia de fallback automática
**para o diagnóstico** (mesma característica do `legislacao`). Se o gpt-4.1 falhar,
o `diagnostico` falha e a chain segue (falha de diagnóstico já é tratada).

## Validação (rodando — container real, chave real)

```
1) settings.AI_DIAGNOSTICO_MODEL = 'gpt-4.1'   (compose env aplicada após recreate)
2) complete(model='gpt-4.1') → model_used=gpt-4.1, provider=gpt, content='OK'
```

A chamada real ao `ai_gateway.complete` com `gpt-4.1` retornou conteúdo válido —
o modelo existe e a `OPENAI_API_KEY` do ambiente consegue chamá-lo (evita o erro
"model not available" que já derrubou o OCR 2×). `docker compose config` válido,
`py_compile` OK.

## Status

✅ Concluído. Próximo diagnóstico roda em `gpt-4.1` (AIJob `model_used=gpt-4.1`).
Reversível por env (`AI_DIAGNOSTICO_MODEL=gpt-4o-mini` volta ao anterior).
