# Sprint A2-diagnostico — Adoção de DiagnosticoPreliminarContent no DiagnosticoAgent

**Data:** 2026-05-09
**Status:** ✅ **CONCLUÍDA** — 4/4 tarefas mergeadas (A, B, C1, C2).
**Predecessoras:** Sprint A1 (`bd47f0c`) + Sprint A2-redator (`9c28003`).
**Branch:** `main` (commits diretos).
**Prompt origem:** `SPRINT_A2_DIAGNOSTICO_REGENTE.md`.

## Resumo executivo

Segunda adoção do `StageOutputContent` (depois do redator). O `DiagnosticoAgent` passa a emitir `DiagnosticoPreliminarContent` serializado, com **dual-emit (γ)** das 6 chaves antigas preservadas no payload — frontend e consumidores existentes não quebram, schema novo é validado em runtime.

Diferenciais desta sprint vs A2-redator:
- **2 paths** num só commit (A.1 IA + A.2 rules-based) — sem split de formato AI-on/AI-off.
- **Mock pesado** no smoke (Q5) em vez de `MagicMock(session)` puro — `_load_process_data` faz queries reais no agente.
- **`lacunas` introduzido como campo schema-only** (V1 lista vazia + log INFO) — evolução prevista pra A3+ quando skills do redator consumirem.

## Tabela de tarefas

| Tarefa | Commit | Testes | Linhas | Custo LLM |
|---|---|---|---|---|
| **A** — `DiagnosticoAgent` emite `DiagnosticoPreliminarContent` (A.1 + A.2) | `8bd6885` | +15 unit | +597/−18 | $0 |
| **B** — Patch frontend `DiagnósticoResult` (aditivo) | `f4854a7` | typecheck ✓ | +57/−14 | $0 |
| **C1** — Bateria E2E paramétrica (4 cenários × AI on/off) | `ba5e4a4` | +7 E2E | +310 | $0 |
| **C2** — Smoke real com gpt-4o-mini (2 cenários) | `ab0ef0c` | manual | +442 | **$0.0002** |

**Total:** 4 commits, **+1.406 / −32 linhas**, **22 testes Python novos** + 7 E2E paramétricos + smoke real, lint limpo, 0 regressão (156/156 verde inclusive A1+A2-redator).

## Decisões da Fase 0 (todas aplicadas)

| # | Decisão | Aplicação |
|---|---|---|
| Q1 | **γ dual-emit** confirmado | ✅ A — payload final tem schema novo + 6 chaves antigas. Frontend não quebra sem patch obrigatório. |
| Q2 | **`lacunas = []` em V1** + log INFO | ✅ A — `_build_payload` emite lista vazia e loga "lacunas_empty schema-only field". Evolução prevista pra A3+. |
| Q3 | `prioridade_acoes`/`observacoes` em `metadata` + dual-emit | ✅ A — ambos. Sem perda de informação. |
| Q4 | `_rules_based_diagnosis` migra junto | ✅ A.2 — `Source(type="manual", ref="rules_engine")`. Sem split de formato AI-on/AI-off. |
| Q5 | Smoke com **mock pesado** | ✅ C2 — `patch.object(DiagnosticoAgent, "_load_process_data", return_value=fake_dict)`. Preserva isolamento de DB. |
| Q6 | `gpt-4o-mini` | ✅ C2 — comparabilidade cross-sprint com A2-redator-C2. |

## Adições importantes do feedback (todas aplicadas)

1. **Sub-paths A.1 + A.2** num só commit:
   - A.1 (`execute()` path IA) lê JSON estruturado do LLM e constrói `DiagnosticoPreliminarContent`.
   - A.2 (`_rules_based_diagnosis` fallback) emite mesmo schema com `Source(type="manual", ref="rules_engine")`.
2. **Tradução `risco_estimado` (str) → `riscos: list[Risco]`** com 1 elemento `Risco(descricao=situacao_geral[:200], severidade=risco_estimado)`. Preserva info sem inventar dado. Em sprints futuras, prompt pode produzir múltiplos riscos estruturados.
3. **`sources` cascata com fallback explícito:** quando `process_data["documents"]` E `legal_data["legislacao_aplicavel"]` ambos vazios, `Source(type="manual", ref="agent_diagnostico", excerpt="no_evidence_available")` + log warning sinalizando "diagnóstico sem evidência documental".

## Mapeamento de campos

| Antigo (dict) | Schema novo | Estratégia |
|---|---|---|
| `situacao_geral: str` | `content: str` | direto + dual-emit |
| `passivos_identificados: list[str]` | `hipoteses: list[str]` | direto + dual-emit |
| `acoes_remediacao: list[str]` | `checklist_documental: list[str]` | direto + dual-emit |
| `prioridade_acoes: list[str]` | `metadata["prioridade_acoes"]` | metadata + dual-emit |
| `observacoes: str` | `metadata["observacoes"]` | metadata + dual-emit |
| `risco_estimado: "baixo"\|"medio"\|"alto"` | `riscos: [Risco(severidade=...)]` | tradução 1:1 + dual-emit string |
| — | `lacunas: list[str]` | `[]` em V1 + log INFO |
| — | `sources: list[Source]` | derivado de docs + legislation com fallback manual |

## Arquivos modificados/criados

### Backend
- `app/agents/diagnostico.py` — `execute()` refatorado (A.1), `_rules_based_diagnosis` refatorado (A.2), helpers `_derive_sources`, `_build_payload`, exceção tipada `DiagnosticoOutputValidationError`. Normalização defensiva de severidade fora-do-enum + content vazio.

### Frontend
- `frontend/src/components/AgentResultRenderer.tsx::DiagnósticoResult` — leitura aditiva de `r.content || r.situacao_geral`, `r.hipoteses || r.passivos_identificados`, `r.checklist_documental || r.acoes_remediacao`, `r.lacunas`, `r.riscos`, `r.metadata.{prioridade_acoes,observacoes}`. Novas seções "Lacunas Documentais" + "Prioridades".

### Testes
- `tests/agents/test_diagnostico_a2.py` (15 unit) — TestPathIA × 5, TestPathRulesBased × 2, TestSourceDerivation × 5, TestValidationError × 1, TestSerializability × 1, TestLacunasLogInfo × 1.
- `tests/agents/test_diagnostico_a2_e2e.py` (7 E2E) — 4 paramétricos (`ai_on_simples`, `ai_on_medio`, `ai_on_completo`, `ai_off_rules_based`) + 3 específicos (rules_engine source, fallback warning, metadata).

### Smoke
- `scripts/smoke_a2_diagnostico.py` — 2 cenários (AI on rich context + AI off rules-based) com mock pesado.
- `docs/sprints/sprint_a2_diagnostico_smoke.md` — relatório do smoke.

## Smoke C2 — resumo

Modelo: `gpt-4o-mini`. Custo total: **$0.0002**. 2/2 ✅.

| Cenário | AI on | tokens | cost | sources | hipóteses | risco | dual-emit |
|---|---|---|---|---|---|---|---|
| ai_on_rich_context | True | 490/205 | $0.0002 | 7 | 3 | alto | ✅ |
| ai_off_rules_based | False | 0/0 | $0.0000 | 1 | 1 | medio | ✅ |

`requires_review=True` em 2/2 (por design, igual ao redator).
`dual-emit` em 2/2 (estratégia γ confirmada em runtime real).

## Bugs/armadilhas encontrados durante a sprint

1. **`recall_memory` (MemPalace) sofre o mesmo bug de `MagicMock(session)` que o `get_active_prompt`** sofreu na A2-redator-C2. Solução: `patch.object(DiagnosticoAgent, "recall_memory", return_value={})`. Adicionado a `_enter_smoke_patches`.
2. **`_load_process_data` faz query SQL real** — diferente do redator. Mock pesado obrigatório no smoke.
3. **Severidade fora do enum** (LLM pode retornar "extremo", "crítico", etc.). Defesa: normalização para `"medio"` + log warning.
4. **`content` vazio viola validator `min_length=1`**. Defesa: placeholder "Diagnóstico sem síntese textual." + dual-emit preserva o vazio original.

## Plano de deprecação das chaves antigas (futuro)

A estratégia γ é tech debt aceitável para preservar consumidores existentes. Plano:

1. **Sprint frontend follow-up:** confirmar 0 uso das chaves antigas em logs/observabilidade. Frontend já lê schema novo com fallback (Tarefa B).
2. **Sprint cleanup (A2-cleanup ou A3+):** remover dual-emit do `_build_payload`. AIJobs históricos continuam funcionando porque o frontend mantém fallback.

Registrado como dívida de simplificação — não bloqueia próximas sprints.

## Dívidas remanescentes

- **`lacunas` populadas:** lista vazia em V1. Quando o redator começar a usar lacunas no prompt da peça (provavelmente Sprint A3 com skills), evolui para (ii) prompt do LLM ou (iii) heurísticas de regra.
- **Múltiplos riscos estruturados:** hoje 1 `Risco` derivado de `risco_estimado` (string). Sprint futura pode pedir ao LLM produzir lista detalhada.
- **`RegulatoryDiagnosis` SQL persistence:** modelo da A1 D1 continua read-only. Persistência via agente vira Sprint Y (junto com auditor C6).

## Próximo agente recomendado a migrar

**`LegislacaoAgent` → criar `LegislationContextContent`** (Sprint A2-legislacao).

Razões:
1. **Custo extra:** precisa criar schema novo (`LegislationContextContent`) — diferente de A2-diagnostico que aproveitou schema existente.
2. **Valor alto:** legislação alimenta tanto redator quanto diagnóstico. Migrar formaliza a saída do nó mais a montante da chain `diagnostico_completo`.
3. **Risco médio:** o redator hoje já consome `chain_data["legislacao"]["legislacao_aplicavel"]` como list[str]. Schema novo precisa preservar essa interface ou patchar redator.

Templates seguintes em ordem decrescente de valor:
1. `LegislacaoAgent` (alto valor — alimenta redator+diagnóstico).
2. `AtendimentoAgent` (já tem feedback loop em A1-E; migrar formaliza).
3. `ExtratorAgent` (baixo valor isoladamente).

---

**Doc gerado em encerramento da Sprint A2-diagnostico (2026-05-09).**
