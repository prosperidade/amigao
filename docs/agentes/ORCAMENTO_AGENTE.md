# ORCAMENTO — sister file

> Documento vivo do agente `orcamento`. Toda afirmação aqui é verificável no
> código (referências `arquivo:linha`). Criado em 2026-05-31 a partir do código
> real (não de rascunho). Estrutura de 12 seções — molde dos sister files.

## 1. Papel no ecossistema

Gera proposta comercial (escopo, valores min/max, prazo, condições de pagamento)
a partir do diagnóstico do processo e do `demand_type`. É a etapa
`orcamento_negociacao` da operação — propõe a peça que o consultor revisa,
ajusta e envia. **IA propõe; o humano decide e assina** (`requires_review=True`,
sempre — `orcamento.py:75`).

Registrado como `"orcamento"` / `OrcamentoAgent`,
`job_type=AIJobType.generate_proposal` (`app/agents/orcamento.py:18-22`). Para o
transversal (lifecycle `run()`, AIJob, cost cap, chain), ver
`docs/agentes/ECOSSISTEMA_AGENTICO.md`.

## 2. Estado de implementação

- **Implementado.** `execute()` (`orcamento.py:29-76`) tem duas camadas:
  1. **Estimativa por regras** (`_estimate_by_rules`, `orcamento.py:95-138`),
     **sempre** calculada — funciona mesmo sem IA.
  2. **Enriquecimento LLM** — só ocorre se `settings.ai_configured`
     (`orcamento.py:50-51`); senão retorna a estimativa base crua.
- **Degrada com elegância:** sem IA configurada, devolve `base_estimate` sem
  abortar (`orcamento.py:50-52`).
- **Merge LLM × base:** cada campo do output usa o valor do LLM com fallback ao
  da estimativa base (`orcamento.py:65-76`).

## 3. Skills

Sem skill procedural dedicada em `app/skills/orcamento/` (diretório não existe —
verificado por glob). Comportamento vive em `_estimate_by_rules` + prompts
`orcamento_system` / `orcamento_user`. Skills do projeto hoje:
`diagnostico/situacao_ambiental_imovel_rural` e
`auditor_imovel/analise_divergencias_documentais`. O hook genérico
`_compose_system_with_skills` (`base.py:336-349`) injetaria uma skill que casasse
com `agent="orcamento"`, mas nenhuma existe no momento.

## 4. Tools que usa

- **LiteLLM gateway** via `self.call_llm()` (`orcamento.py:62`) →
  `base.py:263-278` → `ai_gateway.complete`. Nunca chama provider direto.
- **`OutputValidationPipeline.parse_llm_json`** (`orcamento.py:63`) — parse
  tolerante do JSON do LLM (`app/agents/validators.py:52`).
- **`Process` (ORM)** — `_load_process_context` lê título, `process_type`,
  `demand_type`, `destination_agency`, filtrando por `tenant_id`
  (`orcamento.py:78-93`).
- **AIJob** — `run()` persiste tokens/custo/modelo/`result` (`base.py:376-396`).

## 5. Inputs aceitos

`validate_preconditions` exige `ctx.process_id` **ou** `demand_type` em
`metadata` (`orcamento.py:25-27`). Fontes de `demand_type`, nesta ordem
(`orcamento.py:34-45`): `ctx.metadata["demand_type"]` →
`chain_data["diagnostico"]["demand_type"]` →
`chain_data["atendimento"]["demand_type"]` → `process.demand_type`. Sem nenhum,
cai em `"misto"` (`orcamento.py:48`). Disparo:
1. Via `/agents` (execução manual por agente).
2. Via chain `gerar_proposta` (`["diagnostico", "orcamento"]`,
   `orchestrator.py:34`), mapeada de `intent="generate_proposal"`
   (`orchestrator.py:61`) e da macroetapa `orcamento_negociacao`
   (`orchestrator.py:77`).

## 6. Outputs

`dict` (`orcamento.py:65-76`): `demand_type`, `complexity` (baixa|media|alta),
`scope_items` (`list[{description, estimated_hours}]`), `suggested_value_min`,
`suggested_value_max`, `estimated_days`, `payment_terms`, `notes`, `confidence`
(high|medium|low) e `requires_review: True`. Não usa `StageOutputContent` — é
dict livre, ao contrário de `diagnostico`/`legislacao`.

`requires_review=True` é literal no dict, então `_needs_review` retorna `True`
independente do `confidence` (`base.py:439-443`). Na chain `gerar_proposta`, como
`orcamento` é o **último** agente e **não** está em `NON_BLOCKING_REVIEW_AGENTS`
(só `auditor_imovel` está — `orchestrator.py:54`), a chain pausa para revisão
humana após ele (`orchestrator.py:144-159`).

## 7. Knowledge essencial

Tabela de regras embutida em `_estimate_by_rules` (`orcamento.py:97-138`) cobre
3 tipos: `car` (baixa, R$2.500–5.000, 30d), `licenciamento` (alta,
R$8.000–25.000, 90d), `defesa` (alta, R$5.000–15.000, 60d). Qualquer outro
`demand_type` cai no `default` (media, R$3.000–10.000, 45d, escopo genérico —
`orcamento.py:131-137`). Os valores são âncora; o LLM os ajusta dado o
diagnóstico e o contexto do processo.

## 8. Conversation patterns

Não conversacional. Roda como task (síncrona via `/agents` ou na chain). Uma
chamada LLM por execução. Reentrante: reexecutar gera novo `AIJob`. Prompts vêm
do banco (`get_active_prompt`) com fallback hardcoded em `_fallback_prompts`
(`orcamento.py:140-159`), que já especifica o JSON de saída esperado.

## 9. Cross-agente

- **Consome `diagnostico`:** na chain `gerar_proposta`, recebe
  `chain_data["diagnostico"]` e o injeta no prompt do usuário
  (`orcamento.py:33,57`). Também lê `chain_data["atendimento"]` como fonte
  alternativa de `demand_type` (`orcamento.py:37`).
- É o passo final da chain — seu output não alimenta outro agente; é entregue ao
  consultor para revisão.

## 10. Dívidas técnicas próprias

- **Duas trilhas de orçamento paralelas, desalinhadas:** o agente
  (`_estimate_by_rules`, 3 tipos) e o serviço determinístico
  `app/services/proposal_generator.py` (`PRICE_TABLE` com ~8 tipos e prazos
  distintos) têm tabelas de preço **diferentes**. O endpoint
  `GET /api/v1/proposals/generate-draft` usa o **serviço**
  (`app/api/v1/proposals.py:114`), **não** o agente. Risco de divergência de
  valores conforme o caminho. **Dívida #34** (`REGISTRO_DIVIDAS.md`, P3).
- **Sister file desta família era a dívida #32** (`docs/REGISTRO_DIVIDAS.md:123`)
  — este documento a quita parcialmente.

## 11. Próximas frentes

- Reconciliar as duas tabelas de preço (agente × `proposal_generator`) numa
  fonte única, ou definir claramente qual caminho é canônico.
- Skill procedural de orçamento (modelo de proposta da consultoria) caso o
  comportamento por regras precise virar conteúdo editável — hoje vive em código.
- Persistência da proposta gerada pelo agente como entidade revisável (hoje o
  output fica no `AIJob.result`; a entidade `Proposal` é alimentada pelo fluxo do
  `proposal_generator`/`/proposals`).

## 12. Validação Isis

- **Não verificado:** não há registro no código/docs de validação fim-a-fim do
  `OrcamentoAgent` (caminho LLM) pela Isis em caso real. O agente está marcado
  "Implementado" no catálogo (`docs/agentes/ECOSSISTEMA_AGENTICO.md:29`), mas a
  prova de campo da proposta gerada por IA fica pendente.
