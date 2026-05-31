# MARKETING — sister file

> Documento vivo do agente `marketing`. Toda afirmação aqui é verificável no
> código (referências `arquivo:linha`). Criado em 2026-05-31 a partir do código
> real (não de rascunho). Estrutura de 12 seções — molde dos sister files.

## 1. Papel no ecossistema

Gera conteúdo de marketing — posts, e-mails, mensagens WhatsApp, artigos de blog
e textos de banner — para campanhas de aquisição e engajamento de produtores
rurais. É um agente **periférico ao núcleo regulatório**: não toca em legislação,
diagnóstico, documentos do imóvel ou peças formais. Não participa de nenhuma
chain de análise (diagnóstico, enquadramento) — vive isolado na chain
single-agent `marketing_content`.

Registrado como `"marketing"` / `MarketingAgent`,
`job_type=AIJobType.gerar_conteudo_marketing`
(`app/agents/marketing.py:16-20`; enum em `app/models/ai_job.py:39`). Importado
para registro em `app/agents/__init__.py:21`.

## 2. Estado de implementação

- **Implementado, mas marginal.** `execute()` monta system + user prompt e chama
  o LLM via `call_llm()`, retornando o conteúdo gerado
  (`app/agents/marketing.py:30-57`).
- **Sem schema dedicado.** O output é um `dict` solto — não há `StageOutputContent`
  nem nenhum DTO Pydantic em `app/schemas/` para marketing (busca por
  `marketing`/`generated_content` em `app/schemas/` retorna vazio).
- **Sem skill procedural.** Não existe `app/skills/marketing/` (glob retorna
  vazio). O comportamento vive inteiro nos prompts.
- **Sem endpoint próprio nem teste dedicado.** `marketing` não aparece por nome
  em `app/api/` nem em `tests/` — a única referência em testes é a checagem de
  que `PromptCategory.marketing` existe no enum
  (`tests/agents/test_prompt_template_model.py:165`).

## 3. Skills

Nenhuma skill procedural dedicada. `app/skills/marketing/` não existe. O agente
ainda passa pelo pipeline genérico de skills (`_compose_system_with_skills`,
`app/agents/base.py:336-349`), mas, sem skill que case com `agent="marketing"`,
o system prompt segue idêntico ao base.

## 4. Tools que usa

- **LiteLLM gateway** — única dependência externa, via `call_llm()`
  (`app/agents/marketing.py:48`), que encapsula `ai_gateway.complete`
  (`app/agents/base.py:263-278`).
- **AIJob** — toda execução persiste tokens/custo/modelo/`raw_output` no ciclo
  `run()` (`app/agents/base.py:376-394`).
- **PromptTemplate / prompt_service** — `get_prompt()` carrega o prompt ativo do
  banco com fallback hardcoded (`app/agents/base.py:245-261`).

Não usa OCR, RAG, PostGIS ou qualquer recurso do núcleo regulatório.

## 5. Inputs aceitos

Por `ctx.metadata`:
- `topic` — **obrigatório**; `validate_preconditions()` levanta `ValueError` se
  vazio (`app/agents/marketing.py:25-28`).
- `content_type` — um de `{"post", "email", "whatsapp", "blog", "banner"}`
  (`VALID_CONTENT_TYPES`, `app/agents/marketing.py:23`); valor inválido cai
  silenciosamente para `"post"` (`marketing.py:31-33`).
- `audience` — default `"produtor_rural"` (`marketing.py:36`).
- `tone` — default `"profissional_acessivel"` (`marketing.py:37`).
- `instructions` — opcional, injetado como `extra_instructions` (`marketing.py:45`).

Disparo: via chain `marketing_content` (`["marketing"]`,
`app/agents/orchestrator.py:40`), mapeada do intent `create_content`
(`orchestrator.py:67`). Não há macroetapa associada (`MACROETAPA_CHAINS` não
inclui marketing).

## 6. Outputs

`dict` (sem schema validado) com as chaves
(`app/agents/marketing.py:50-57`):
`content_type`, `generated_content` (o texto do LLM), `topic`, `audience`,
`requires_review=True` (literal hardcoded), `confidence="medium"`.

`requires_review=True` é fixo — todo conteúdo de marketing passa por revisão
humana, e `_needs_review()` o respeita (`app/agents/base.py:439-443`). O
`confidence="medium"` é lido por `_extract_confidence()` (`base.py:430-437`).

## 7. Knowledge essencial

Vive nos prompts de fallback (`app/agents/marketing.py:59-107`):
- **System** (`marketing_system`): especialista em marketing para agronegócio e
  consultoria ambiental no Brasil; linguagem clara, sem jargão excessivo, tom
  profissional mas acessível (`marketing.py:61-66`).
- **Por formato**: `post` pede hashtags + CTA; `email` pede assunto/corpo/CTA;
  `whatsapp` limita a 500 caracteres; `blog` pede título/subtítulos/conclusão;
  `banner` pede título ≤ 10 palavras + subtítulo (`marketing.py:67-106`).

Os prompts reais usados em produção podem sobrescrever esses fallbacks via
`PromptTemplate` (slugs `marketing_system`, `marketing_post`, `marketing_email`,
`marketing_whatsapp`; `prompt_slugs` em `marketing.py:21`). O slug é resolvido
dinamicamente como `marketing_{content_type}` (`marketing.py:40`).

> **Nota (não verificado a fundo):** `prompt_slugs` lista 4 slugs, mas
> `VALID_CONTENT_TYPES` tem 5 — `blog` e `banner` têm fallback hardcoded porém
> não constam em `prompt_slugs`. Sem template no banco, ambos funcionam pelo
> fallback; com template, dependem do slug estar cadastrado.

## 8. Conversation patterns

Não conversacional. Roda como task de turno único: um `topic` entra, um conteúdo
sai. Sem estado entre execuções, sem `chain_data` (a chain tem um único agente).
Idempotente em espírito — reexecutar com o mesmo `topic` gera novo `AIJob` e novo
conteúdo (LLM não-determinístico).

## 9. Cross-agente

Praticamente nulo. A chain `marketing_content` tem só `marketing`
(`app/agents/orchestrator.py:40`); não consome nem alimenta `chain_data` de
outros agentes. Não está em `NON_BLOCKING_REVIEW_AGENTS`
(`orchestrator.py:54`) — mas, sendo single-agent, seu `requires_review=True` não
interrompe nada downstream (não há downstream).

## 10. Dívidas técnicas próprias

- **Sem schema de output** — diverge do Princípio 6 ("schema antes de escala");
  output é dict livre, não `StageOutputContent`. Aceitável enquanto for agente
  periférico, mas é dívida se o conteúdo passar a ser consumido por outro
  componente.
- **`blog`/`banner` fora de `prompt_slugs`** (ver seção 7) — risco de prompt
  vazio se um dia o fallback for removido e o template não existir.
- **Sem cobertura de teste** própria (ver seção 2).

## 11. Próximas frentes

- O canal **WhatsApp aqui é só um `content_type`** (gera o texto da mensagem);
  **não há integração com provider/SDK de WhatsApp** no projeto. Qualquer envio
  real de campanha é frente futura, fora deste agente.
- Caso o produto priorize a frente comercial, faria sentido dar a este agente um
  schema de output e endpoint/UI próprios — hoje ele só é alcançável pela chain
  genérica via intent `create_content`.

## 12. Validação Isis

- **Não verificado.** Não há registro de validação fim-a-fim deste agente em
  dados/caso real (a frente validada com a Isis é o núcleo regulatório —
  extrator/diagnóstico, caso Romilton). Marketing permanece periférico e sem
  exercício documentado.
