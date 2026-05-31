# REDATOR — sister file

> Documento vivo do agente `redator`. Toda afirmação aqui é verificável no
> código (referências `arquivo:linha`). Criado em 2026-05-31 a partir do código
> real (não de rascunho). Estrutura de 12 seções — molde dos sister files.

## 1. Papel no ecossistema

Gera **documentos formais** a partir do contexto da chain/processo: PRAD,
memorial descritivo, ofício, proposta, resposta a notificação, contrato e
comunicação. É um agente **produtor de peça final** entregue ao consultor — não
é insumo de downstream. Por isso é **bloqueante de review** (`requires_review`
trava a chain), materializando o Princípio 1 do manifesto ("a IA propõe; o
humano decide e assina").

Registrado como `"redator"` / `RedatorAgent`, `job_type=AIJobType.gerar_documento`
(`app/agents/redator.py:40-44`).

## 2. Estado de implementação

- **Implementado.** `execute()` carrega contexto, monta os prompts por template,
  chama o LLM e serializa o resultado (`app/agents/redator.py:59-123`).
- **Output schematizado (Sprint A2-redator):** o conteúdo vira
  `PecaJuridicaContent` ou, para `resposta_notificacao` com campos extras
  resolvidos, `RespostaNotificacaoContent` (`app/agents/redator.py:177-237`;
  schemas em `app/schemas/stage_output.py:304-343`).
- **`requires_review=True` sempre:** documentos formais sempre exigem revisão
  humana — flag fixada fora do schema, no merge final do payload
  (`app/agents/redator.py:114-117`).
- **Citation evaluator (Sprint A1 B / A2):** roda contra o contexto legal
  carregado e popula `citation_issues`, `citation_total`,
  `citation_coverage_ratio`, `citation_valid` (`app/agents/redator.py:95-122`,
  `239-268`).

## 3. Skills

Sem skill procedural de domínio ativa hoje. Existe apenas um placeholder técnico
`redator/_template` (`app/skills/redator/_template/SKILL.md`), que só ativa
quando `ctx.metadata.demand_type == "template"` e serve para validar que o
registry descobre/parseia/injeta skills no system prompt. A própria SKILL.md
declara: "Placeholder técnico — não usar em produção" e adia skills reais
(oficio_semad, memorial_car, prad) para a Sprint A3, quando os PDFs-gabarito da
sócia forem fornecidos (`app/skills/redator/_template/SKILL.md:5,13-17`).

## 4. Tools que usa

- **LiteLLM gateway** — via `call_llm(... max_tokens=4096)`
  (`app/agents/redator.py:91`), que injeta skills aplicáveis no system prompt e
  chama `ai_gateway.complete()` (`app/agents/base.py:263-278`).
- **prompt_service** — `get_prompt()` carrega prompts do banco com fallback
  hardcoded (`app/agents/base.py:245-261`); fallbacks em
  `app/agents/redator.py:289-344`.
- **citation_evaluator** — `extract_citations()` + `validate_citations()`
  (`app/services/citation_evaluator.py:187,303`), retornando
  `CitationValidationResult` com `all_citations`/`coverage_ratio`
  (`app/services/citation_evaluator.py:37,58-59`).
- **AIJob** — `BaseAgent` persiste cada execução (tokens, custo, modelo,
  `result`) (`app/agents/base.py:376-394`).

## 5. Inputs aceitos

Por `ctx.metadata`: `document_template` (default `"comunicacao"`), `instructions`,
`client_data`, `property_data`, `addressee`, e — só para `resposta_notificacao` —
`prazo_dias` e `ato_regulatorio` (`app/agents/redator.py:53,60,74-88,169,203-208`).
Da chain: `chain_data["diagnostico"]` e `chain_data["legislacao"]`
(`app/agents/redator.py:72-73`). Com `process_id` e sem diagnóstico, enriquece
via `_load_process_context()` (`app/agents/redator.py:78-79,270-287`).

`validate_preconditions()` rejeita template fora de `VALID_TEMPLATES` (`prad`,
`memorial`, `oficio`, `proposta`, `resposta_notificacao`, `contrato`,
`comunicacao`) (`app/agents/redator.py:50,52-57`).

Caminhos de disparo: (1) `/agents/run` individual (`app/api/v1/agents.py:61-92`);
(2) chain `gerar_documento` (`["redator"]`) via `/agents/chain` ou
`/agents/chain-async` (`app/agents/orchestrator.py:35`); (3) intent
`generate_document` → chain `gerar_documento` (`app/agents/orchestrator.py:62`).

## 6. Outputs

`dict` = `peca.model_dump(mode="json")` mesclado com flags fora-do-schema
(`app/agents/redator.py:114-123`). Campos do schema: `content`, `sources`,
`template`, `legal_citations`, `addressee` (`app/schemas/stage_output.py:304-320`),
mais o `computed_field document_type` (alias deprecated de `template`, mantido
por compat com o frontend) (`app/schemas/stage_output.py:322-331`). Flags
mescladas: `requires_review=True`, `confidence="medium"`, e os `citation_*`
(`app/agents/redator.py:114-122`).

`requires_review=True` é fixo e disparado pelo agente — em `BaseAgent._needs_review`,
`requires_review is True` força revisão independentemente da confiança
(`app/agents/base.py:439-443`).

`sources` nunca é vazio: validator `_sources_non_empty` em `StageOutputContent`
exige ≥1 (`app/schemas/stage_output.py:236-238`); `_derive_sources` garante isso
com cascata `legislacao_aplicavel`/`normas_estaduais` → fallback honesto
`Source(type="manual", ref="agent_redator")` (`app/agents/redator.py:129-160`).

## 7. Knowledge essencial

- 7 templates válidos, cada um com prompt-fallback próprio
  (`app/agents/redator.py:50,289-344`).
- `resposta_notificacao` enriquecida exige `prazo_dias` (0–365) e
  `ato_regulatorio`; quando faltam, parse best-effort do texto via regex
  (`app/agents/redator.py:351-385`) e, se ainda assim não resolver, **fallback
  gracioso** para `PecaJuridicaContent` puro + log warning
  (`app/agents/redator.py:210-237`).
- `proposta`/`contrato` têm fluxos dedicados paralelos
  (proposal_generator/contract_generator); o redator loga quando é chamado
  nesses templates para medir se a rota é caminho morto
  (`app/agents/redator.py:65-69`).
- Não finge proveniência: source de fallback é `type="manual"`, não
  `legislation` (`app/agents/redator.py:153-159`).

## 8. Conversation patterns

Não conversacional. Roda como task — síncrona via `/agents/run` /
`/agents/chain` ou assíncrona via Celery em `/agents/chain-async`
(`app/api/v1/agents.py:61,96,177`). A chain `gerar_documento` tem um único
agente (`["redator"]`), então o `requires_review=True` para a chain
imediatamente após a geração (`app/agents/orchestrator.py:35,144`).

## 9. Cross-agente

- **Consome** `chain_data["diagnostico"]` e `chain_data["legislacao"]` como
  contexto (`app/agents/redator.py:72-73`). O contexto legal alimenta tanto os
  `sources` quanto o citation evaluator.
- **Bloqueante de review:** o redator NÃO está em
  `NON_BLOCKING_REVIEW_AGENTS` (que hoje contém apenas `auditor_imovel`)
  (`app/agents/orchestrator.py:54`). Junto com `legislacao` (peça/produto final),
  é diferente do `auditor_imovel`, cujo `requires_review` é não-bloqueante por
  produzir insumo de downstream (`app/agents/orchestrator.py:43-54,144-148`).
- **Frontend:** `AgentResultRenderer.tsx::RedatorResult` lê `r.template` com
  fallback para `r.document_type` (AIJobs legados)
  (`frontend/src/components/AgentResultRenderer.tsx:374-380,620`).

## 10. Dívidas técnicas próprias

- **Skills de domínio ausentes.** Só existe o placeholder `_template`; os
  gabaritos reais da sócia (oficio_semad, memorial_car, prad) estão adiados
  (`app/skills/redator/_template/SKILL.md:13-17`).
- **Parsers best-effort V1.** Extração de `prazo_dias`/`ato_regulatorio` por
  regex é frágil; falha cai no fallback de `PecaJuridicaContent` puro
  (`app/agents/redator.py:351-385,227-237`).
- **`document_type` alias deprecated.** `computed_field` mantido só por compat
  com frontend/AIJobs antigos; previsto remover após medir 0 uso
  (`app/schemas/stage_output.py:322-331`).
- **Rota redundante para proposta/contrato.** Convivência com os geradores
  dedicados ainda em observação por log (`app/agents/redator.py:62-69`).

## 11. Próximas frentes

- Sprint A3: skills procedurais reais por tipo de peça, condicionadas aos
  PDFs-gabarito da sócia (`app/skills/redator/_template/SKILL.md:16-17`).
- `rag_chunks_meta` no `legal_data` já é aceito pelo evaluator como espaço para
  expor `SearchResult` em sprint futura (`app/agents/redator.py:257-260`).
- Endurecer/eliminar parsers regex assim que `prazo_dias`/`ato_regulatorio`
  vierem estruturados no metadata.

## 12. Validação Isis

- **Não verificado.** Não encontrei no código/docs registro de validação
  fim-a-fim do redator pela Isis em peça real (gabarito comparado). A geração de
  documento depende dos gabaritos da sócia (Sprint A3) para sair de
  pilot-grade — até lá, os fallbacks hardcoded em `_fallback_prompts` governam o
  tom (`app/agents/redator.py:289-344`).
