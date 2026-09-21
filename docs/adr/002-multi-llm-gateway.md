# ADR-002 · AI Gateway multi-provider via LiteLLM

**Status:** Aceito
**Data:** 2026-04-03 (Sprint IA-1); formalizada como ADR em 2026-05-15
**Decisores:** tecnologia
**Relacionado:** [`./005-pgvector-rag.md`](./005-pgvector-rag.md), [`./006-skills-procedurais.md`](./006-skills-procedurais.md)
**Adendo:** 21/09/2026 — os nomes de modelo no corpo são os de abril–maio/2026; os vigentes estão no [adendo ao fim](#adendo--21092026-modelos-vigentes).

---

## Contexto

O Regente Ambiental usa LLM em pontos críticos do produto (intake, extração, diagnóstico, redator, legislação, acompanhamento, marketing). A decisão de **como** o produto consome LLM precisava ser tomada antes da Sprint IA-1.

Três caminhos disponíveis no mercado:

1. **Lockin em um provider** — SDK oficial do OpenAI/Anthropic/Google
2. **Camada própria de abstração** — wrapper interno chamando diretamente cada SDK
3. **Camada de abstração open-source** — LiteLLM, LangChain, Haystack, etc.

O domínio LLM se move trimestralmente. Provider líder muda. Preço cai. Modelo melhor surge. Tomar dependência forte de um provider em 2026 é apostar contra o histórico recente do setor.

## Decisão

**LiteLLM como driver único de LLM.** Toda chamada a provider de IA passa por uma camada única em `app/core/ai_gateway.py` que usa LiteLLM internamente. **Nenhum serviço chama provider diretamente.**

Política de fallback: OpenAI → Gemini → Anthropic, ordem ajustável por contexto. Quando o provider primário falha (timeout, rate limit, erro), o LiteLLM tenta o próximo. Tudo configurável via env (`AI_DEFAULT_MODEL`, `AI_FALLBACK_MODEL`).

Cada chamada retorna `AIResponse(content, model_used, tokens_in, tokens_out, cost_usd, duration_ms, provider)` e é persistida em `AIJob` para auditoria.

## Consequências

**Positivas:**
- **Resiliência operacional** — falha de provider não derruba a feature; fallback é automático
- **Diversidade econômica** — modelo barato em provider A para tarefa simples, modelo robusto em provider B para tarefa complexa
- **Lockin reduzido** — trocar provider primário é uma config, não um refactor
- **Custo otimizável** — agente `LegislacaoAgent` usa Gemini 2.0 Flash (janela 1M-2M tokens, custo baixo); demais usam gpt-4o-mini
- **Audit unificado** — uma única forma de logar custo, tokens, modelo, provider
- **Credenciais por tenant** — capacidade habilitada (Tenant pode trazer chave própria, custo vai pro cartão dele)

**Negativas:**
- **LiteLLM é dependência terceira** — manutenção e qualidade dependem do upstream
- **Features novas** dos providers podem demorar a aparecer no LiteLLM (function calling avançado, file uploads etc.)
- **Camada de abstração tem custo** — overhead pequeno em latência, mas existe
- **Debugging** — em provider direto, stack trace bate em SDK conhecido; via LiteLLM, há uma camada intermediária

**Mitigações:**
- Versão do LiteLLM fixada em `requirements.txt`; atualizações são revisadas
- Para features avançadas específicas, podemos chamar SDK do provider diretamente em ponto isolado — mas só excepcionalmente, com aprovação explícita
- Logging interno do AI Gateway preserva contexto para debugging (request_id, agent_name, model_used)

## Alternativas consideradas

**LangChain.** Mais features (chains, agents, RAG embutido), mas opinionated demais e historicamente instável. Mudanças de API frequentes. Quebrou para muita gente em produção. Rejeitado.

**Wrapper próprio chamando SDK de cada provider.** Mais controle, zero dependência terceira. Custo: manter 3 integrações com 3 SDKs diferentes, com semânticas diferentes (streaming, function calling, retry). Tempo gasto em encanamento, não em produto. Rejeitado.

**Lockin em OpenAI.** Mais simples, melhor SDK do mercado. Custo: aposta única no líder atual. Histórico do setor (Gemini superando OpenAI em janela e preço; Anthropic em qualidade em PT-BR técnico) mostra que líder muda. Rejeitado.

## Status de execução

| Item | Estado |
|---|---|
| `app/core/ai_gateway.py` com LiteLLM | ✅ Sprint IA-1 |
| Fallback automático OpenAI → Gemini → Anthropic | ✅ |
| `AIResponse` com cost/tokens/model padronizados | ✅ |
| `AIJob` persistindo toda chamada | ✅ |
| Cost cap por job (`AI_MAX_COST_PER_JOB_USD`) | ✅ |
| Cost cap por tenant/hora | ✅ Sprint R |
| Cost cap por tenant/mês | ✅ Sprint R (`Tenant.ai_monthly_budget_usd`) |
| Credenciais próprias por tenant | ✅ Capacidade arquitetural; UI para configurar pendente |
| Roteamento dinâmico por janela (`LegislacaoAgent`) | ✅ Sprint O |
| Citation evaluator (validação de citações geradas) | ✅ Sprint A1 |

## Relação com outros ADRs

- [`./006-skills-procedurais.md`](./006-skills-procedurais.md) — skills carregadas pelo gateway antes da chamada LLM
- [`./007-stage-output-content.md`](./007-stage-output-content.md) — schema validado para a saída dos agentes
- [`./003-mempalace-REVOKED.md`](./003-mempalace-REVOKED.md) — memória de agente que foi revogada (substituída por RAG)

## Adendo — 21/09/2026: modelos vigentes

A decisão continua valendo: LiteLLM como driver único, o gateway como porta única e fallback
entre providers. Mudou o modelo em cada ponto, e o corpo acima (gpt-4o-mini para quase tudo,
Gemini 2.0 Flash na Legislação) deixou de descrever o sistema:

- **Legislação e OCR** saíram do `gemini-2.0-flash`, que o Google descontinuou e que derrubou o
  worker de produção. A Legislação migrou em 14/05 (Sprint W) para `gemini/gemini-2.5-flash`,
  com `gemini/gemini-2.5-pro` acima de ~800K tokens. O OCR migrou em 02/06 para
  `gemini/gemini-2.5-flash`.
- **Diagnóstico** ganhou modelo próprio em 02/06: `gpt-4.1` (`AI_DIAGNOSTICO_MODEL`).
- **Matriz agente × provider** (`app/core/model_matrix.py`, 07/06). Cada agente declara o
  equivalente em cada provider. O primário vem sempre de setting, e o fallback só entra entre
  providers com chave. Carga fixada (`allow_fallback=False`) falha em vez de trocar de provider.
- **Extrator** (decisão do André, 19/09, #183): `gpt-5.6-luna` (`AI_EXTRATOR_MODEL`), com
  fallback exclusivo `gemini/gemini-3.7-flash` (`AI_EXTRATOR_FALLBACK_MODEL`) e sem Anthropic.
  O fallback cobre falha de provedor; erro de validação semântica da saída não troca de modelo.
- **Demais agentes** seguem em `gpt-4o-mini` (`AI_DEFAULT_MODEL`), com fallback
  `gemini/gemini-2.5-flash` (`AI_FALLBACK_MODEL`).

A tabela viva, com a cadeia de fallback de cada agente, está em
[`GOVERNANCA_IA.md` › Modelos por contexto](../arquitetura/GOVERNANCA_IA.md#modelos-por-contexto).
A próxima troca de modelo atualiza aquela tabela, não este adendo.
