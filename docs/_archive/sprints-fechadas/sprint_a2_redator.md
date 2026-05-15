# Sprint A2-redator — Adoção de PecaJuridicaContent no RedatorAgent

**Data:** 2026-05-09
**Status:** ✅ **CONCLUÍDA** — 4/4 tarefas mergeadas (A, B, C1, C2).
**Predecessora:** Sprint A1 (commit `bd47f0c`).
**Branch:** `main` (commits diretos).
**Fase 0 report:** documentado na conversa; arquivos lidos: `redator.py`, `base.py`, `pdf_generator.py`, `proposal_generator.py`, `contract_generator.py`, `orchestrator.py`, `stage_output.py`, `citation_evaluator.py`, `AgentResultRenderer.tsx`, `test_redator_citation_hook.py`.
**Prompt origem:** [`SPRINT_A2_REDATOR_REGENTE.md`](../../SPRINT_A2_REDATOR_REGENTE.md) (raiz).

## Resumo executivo

Primeira **adoção real** do `StageOutputContent` (introduzido em A1-C). O `RedatorAgent` passa a emitir `PecaJuridicaContent` serializado (ou `RespostaNotificacaoContent` quando aplicável), com flags de execução (`requires_review`, `citation_*`) merged fora do schema no payload final que vai para `AIJob.result`.

Quando Sprint A3 chegar com os PDFs-gabarito da sócia, as skills de domínio (`oficio_semad.md`, `prad.md`, etc.) vão encontrar `PecaJuridicaContent` em uso e encaixar direto sem refator.

## Tabela de tarefas

| Tarefa | Commit | Testes | Linhas | Custo LLM |
|---|---|---|---|---|
| **A** — `RedatorAgent` emite `PecaJuridicaContent` | `1e8566f` | +32 unit | +641/−14 | $0 |
| **B** — Patch frontend `RedatorResult` | `0acbb8f` | typecheck ✓ | +32/−2 | $0 |
| **C1** — Bateria E2E paramétrica (CI) | `d0e0c4f` | +9 E2E | +276 | $0 |
| **C2** — Smoke real com gpt-4o-mini | `12ca673` | manual | +504 | **$0.0030** |

**Total final:** 4 commits, **+1.453 / −16 linhas**, **41 testes Python novos** + 9 E2E paramétricos + smoke real, lint limpo, 0 regressão (134/134 verde inclusive A1 inteira).

## Decisões da Fase 0 (todas aplicadas)

| # | Decisão | Aplicação |
|---|---|---|
| Q1 | Migrar todos os 7 templates | ✅ A — log INFO em `proposta`/`contrato` registra uso quando rota concorre com `proposal_generator`/`contract_generator` |
| Q2 | Defesa em profundidade `document_type` | ✅ A — `@computed_field` em `PecaJuridicaContent` retornando `self.template`; B — frontend lê `r.template \|\| r.document_type` |
| Q3 | Resposta sem prazo/ato → fallback gracioso | ✅ A — `RespostaNotificacaoContent` quando enriched, `PecaJuridicaContent` puro com `template="resposta_notificacao"` quando faltam campos. Cascata `ctx.metadata` → parse best-effort do `content` (regex multi-formato) → fallback. |
| Q4 | C1 stubado + C2 real | ✅ C1 + C2 |
| Q5 | Sem flag `legacy_dict_output` | ✅ rollback é via revert do commit |
| Q6 | C dividida em C1+C2 | ✅ C1 mergeado pra CI, C2 manual com smoke real |

## Adições do feedback (todas aplicadas)

1. **Merge final no `execute()`:** `payload = peca.model_dump(mode="json") | {"requires_review": True, "confidence": "medium", "citation_issues": [...], "citation_total": ..., "citation_coverage_ratio": ..., "citation_valid": ...}`. Flags de execução ficam fora do schema.
2. **`Source` não-vazio em cascata:** `legal_data["legislacao_aplicavel"]` (até 5 itens) → `Source(type="manual", ref="agent_redator", excerpt=instructions[:200])`. `type="manual"` é honesto sobre origem.
3. **Hook citation evaluator estendido** (aditivo): `CitationValidationResult.all_citations: list[CitationRef]` (default `[]`). Os 5 testes do A1-B passam sem alteração — extensão não-quebra.
4. **Cascade `addressee`:** `ctx.metadata["addressee"]` → `process.destination_agency` (via `chain_data["diagnostico"]`) → `None`.

## Arquivos modificados/criados

### Backend
- `app/agents/redator.py` — `execute()` refatorado, helpers `_derive_sources`, `_resolve_addressee`, `_build_peca`, parsers `_parse_prazo_dias`/`_parse_ato_regulatorio`. Log INFO para templates `proposta`/`contrato`.
- `app/schemas/stage_output.py` — `PecaJuridicaContent.document_type` (computed_field), `model_config(extra="ignore")` (override de `_StrictModel.forbid`).
- `app/services/citation_evaluator.py` — `CitationValidationResult.all_citations` (extensão aditiva).

### Frontend
- `frontend/src/components/AgentResultRenderer.tsx::RedatorResult` — lê `r.template || r.document_type`, renderiza badges adicionais para `addressee` e "Citações suspeitas".

### Testes
- `tests/agents/test_redator_a2.py` (32 testes unit) — bateria paramétrica × 7 templates, fallback de `resposta_notificacao`, derivação de `Source`, cascata `addressee`, integração do citation evaluator, alias `document_type`, parsers, log INFO.
- `tests/agents/test_redator_a2_e2e.py` (9 testes E2E) — pipeline `run()` → `AgentResult` → JSON dump round-trip por template, sincronização com `VALID_TEMPLATES`.

### Smoke
- `scripts/smoke_a2_redator.py` — 7 templates contra LLM real, gera relatório.
- `docs/sprints/sprint_a2_redator_smoke.md` — relatório do smoke (timestamp, commit, modelo, métricas, calibração).

## Smoke C2 — resumo

Modelo: `gpt-4o-mini` via litellm/OpenAI. Custo total: **$0.0030**. 7/7 ✅.

| Template | tokens (in/out) | cost | citations | sources | addressee | latência |
|---|---|---|---|---|---|---|
| prad | 203/1017 | $0.0006 | 3/valid | 3 | — | 25s |
| memorial | 134/677 | $0.0004 | — (skip) | 1 | — | 16s |
| oficio | 159/623 | $0.0004 | 1/valid | 2 | SEMAD-GO | 6s |
| proposta | 152/689 | $0.0004 | — (skip) | 1 | — | 8s |
| resposta_notificacao | 154/701 | $0.0004 | 3/valid | 3 | SEMAD-GO | 16s |
| contrato | 141/1063 | $0.0006 | — (skip) | 1 | — | 26s |
| comunicacao | 104/213 | $0.0001 | — (skip) | 1 | Cliente Final | 3s |

`requires_review=True` em **7/7** — por design (hardcoded para peças formais), não por algoritmo.

## Bugs encontrados e fixados durante a sprint

1. **D1/D2 herdou da A1:** `relationship(..., backref=...)` causa `ArgumentError: property of that name exists on mapper` em hot-reload do uvicorn. Não tocou nesta sprint (já resolvido em A1).
2. **C2 — `emit_agent_event`/`record_agent_execution`** são imports tardios em `BaseAgent.run()`. Patch precisa ser no módulo de origem (`app.agents.events`/`app.core.metrics`), não em `app.agents.base`.
3. **C2 — `MagicMock(session)`** faz `get_active_prompt()` retornar um `MagicMock` truthy em vez de `None`. Fallback hardcoded em `_fallback_prompts` nunca era usado, prompt virava `<MagicMock ...>`. Solução: `patch("app.agents.base.get_active_prompt", return_value=None)`. Mesma armadilha vai aparecer em smokes futuros de outros agentes — pattern documentado no docstring de `_enter_smoke_patches`.
4. **C2 — `git rev-parse` falha no container** porque `.git` não está em volume mount. Solução: aceitar `SMOKE_COMMIT_SHA` via env var injetada pelo caller no host.

## Dívidas remanescentes

Nenhuma bloqueante. Itens para sprints futuras:

- **`legal_citations` enriquecimento via `SearchResult`:** hoje o citation evaluator aceita `SearchResult` no contexto (popula `chunk_id`/`jurisdicao`), mas o `RedatorAgent._evaluate_citations` ainda passa só strings (`legislacao_aplicavel`/`normas_estaduais`). Sprint A2-legislacao (próxima) deve expor `chain_data["legislacao"]["rag_chunks_meta"]: list[SearchResult]` para enriquecer.
- **`document_type` alias:** `@computed_field` mantém compat. Em 1-2 sprints, depois de medir 0 uso do alias em logs, pode sumir.
- **AIJobs históricos** com formato dict legado coexistem com novo. Frontend já renderiza ambos (fallback). Sem migração de dados (decisão do prompt).

## Próximo agente recomendado a migrar

**`DiagnosticoAgent` → `DiagnosticoPreliminarContent`** (Sprint A2-diagnostico).

Razões:
1. `DiagnosticoPreliminarContent` já existe (A1-C) com `hipoteses`, `lacunas`, `riscos`, `checklist_documental` — mais valor que extrator (que é wrapper sobre `document_extractor`).
2. Output do diagnóstico é input para a peça do redator — formalizar a saída melhora a entrada do agente que acabamos de migrar.
3. Risco médio: chain `diagnostico_completo` (`extrator → legislacao → diagnostico`) é a mais usada — vale validar que migrar diagnóstico não quebra a chain.
4. Padrão da A2-redator é replicável: `model_dump(mode="json") | flags`. Deve render esforço S/M.

Templates seguintes recomendados, em ordem decrescente de valor:
1. `DiagnosticoAgent` (alto valor, risco médio).
2. `LegislacaoAgent` (alto valor — alimenta redator e diagnóstico).
3. `AtendimentoAgent` (já tem feedback loop em A1-E; migrar formaliza o que está dict).
4. `ExtratorAgent` (baixo valor isoladamente; útil quando `StageOutputContent` virar contrato em endpoints).

---

**Doc gerado em encerramento da Sprint A2-redator (2026-05-09).**
