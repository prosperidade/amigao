# LEGISLACAO — sister file

> Documento vivo do agente `legislacao`. Afirmações verificáveis no código.
> Criado em 2026-05-30 a partir do código real.

## 1. Papel no ecossistema

Monta o **caminho regulatório** (macroetapa 5 — `caminho_regulatorio`): órgão
competente, etapas, legislação aplicável, riscos, prazos. Consulta a base
regulatória via RAG semântico filtrado. Secundariamente apoia diagnóstico (4) e
acompanhamento (7). Registrado como `"legislacao"` / `LegislacaoAgent`,
`job_type="consulta_regulatoria"` (`app/agents/legislacao.py`).

## 2. Estado de implementação

- **Implementado.** RAG semântico + busca por metadados + LLM (Gemini Flash/Pro
  por tamanho de contexto) → `EnquadramentoRegulatorioContent` com dual-emit do
  formato legado.
- **PR 2.2 (#26, mergeado 2026-05-29):** consulta RAG **filtrada por
  `demand_type`** via JOIN com `LegislationDocument.demand_types`. Em
  `app/services/knowledge_catalog.py:search()`, o filtro usa o operador JSON
  containment `@>` do PostgreSQL: `CAST(ld.demand_types AS jsonb) @> [demand_type]`
  juntando `knowledge_catalog.source_ref` com `legislation_documents.id`. UF
  permanece como filtro; `demand_type` reforça a string semântica da query.
- **Fail-fast de template:** `app/services/workflow_engine.py:apply_workflow_template`
  levanta `TemplateNotFoundError` quando o `demand_type` não tem
  `WorkflowTemplate` ativo (silent failure resolvido na PR 2.2).
- Fallback sem UF quando a busca com UF não retorna chunks.

## 3. Skills

Sem skill procedural formal em `app/skills/legislacao/` hoje — o método vive no
código do agente + prompt. (Anotado como dívida documental menor.)

## 4. Tools que usa

- **RAG `knowledge_catalog`** (`app/services/knowledge_catalog.py:search`) —
  busca vetorial pgvector (768d), filtros `uf`, `jurisdiction`, `agency`,
  `demand_type`, `source_type`.
- **Busca por metadados** (dump de legislação por identificador).
- **LiteLLM gateway** — roteamento dual (Gemini 2.5 Flash padrão / Pro p/
  contextos grandes; ver `config.py:GEMINI_LEGAL_MODEL`/`GEMINI_LEGAL_LONG_MODEL`).

## 5. Inputs aceitos

Por `ctx.metadata`/`chain_data`: `query`, `demand_type` (com fallback para
`chain_data["atendimento"].demand_type`), `state` (UF), `process_id`.

## 6. Outputs

`EnquadramentoRegulatorioContent` (StageOutputContent): `caminho_regulatorio`,
`orgao_competente`, `etapas`, `legislacao_aplicavel`, `riscos`,
`normas_estaduais`, `prazos_legais`, `sources`, `chunks_referenced`.
**`requires_review=True` sempre** — é insumo regulatório que o consultor revisa
e assina (Princípio 1). Em `diagnostico_completo`, revisão e falha/timeout são
não-bloqueantes porque a etapa é insumo do `diagnostico`; nas chains em que a
legislação é produto final, continua bloqueante.

## 7. Knowledge essencial

- Vocabulário regulatório: CAR, RL, APP, GEO, SIGEF, embargo, PRAD, outorga,
  supressão, regularização fundiária.
- Estados e órgãos: SEMA por UF, IBAMA, INCRA, ANA, MAPA.
- Taxonomia `DemandType`: **16 valores** (`app/models/process.py`): car,
  retificacao_car, licenciamento, regularizacao_fundiaria, outorga, defesa,
  compensacao, exigencia_bancaria, prad, sobreposicao, supressao, due_diligence,
  arrendamento, condicionantes_antigas, misto, nao_identificado.
- Corpus indexado: federal + GO/MS/MT + corpus operacional SEMAD
  (ver `docs/arquitetura/BASE_REGULATORIA.md`).

## 8. Conversation patterns

- Na chain `analise_regulatoria` (`["legislacao"]`) e `enquadramento_regulatorio`
  (`["extrator", "legislacao"]`), disparada ao avançar para a macroetapa
  `caminho_regulatorio` (`MACROETAPA_AGENT_CHAIN`).
- Na chain `diagnostico_completo`, roda entre `auditor_imovel` e `diagnostico`.
  Desde 2026-06-01, timeout ou `requires_review=True` não abortam a entrega do
  diagnóstico; o erro/output fica em `chain_data["legislacao"]`.
- Por pedido direto via UI ("rodar legislação no processo").

## 9. Cross-agente

- Recebe contexto do `diagnostico` (etapa 4) e do `extrator`.
- Alimenta `orcamento` (etapa 6) com etapas + prazos.
- Pode sugerir `demand_type` quando o `Process.demand_type` ainda é
  `nao_identificado`.

## 10. Dívidas técnicas próprias

- **#21** — criar `WorkflowTemplate` para demand_types sem cobertura
  (`prad`, `sobreposicao`, `supressao`, `due_diligence`, `arrendamento`,
  `condicionantes_antigas`, `misto`, `nao_identificado`). Cobertura efetiva é
  dado de runtime: `tools/check_template_coverage.py` existe; rodada real
  registrada em `docs/arquivo/auditorias/2026-05-28_cobertura_templates.md`.
- Os 5 demand_types novos (sobreposicao, supressao, due_diligence, arrendamento,
  condicionantes_antigas) têm regras placeholder no `intake_classifier`;
  refinamento futuro.
- Sem skill procedural formal (dívida documental menor).
- **#39** — robustez de timeout/parsing permanece aberta. Medição em 2026-06-01
  apontou timeout na chamada Gemini (`gemini/gemini-2.5-flash`) com RAG local em
  ~4,5s e contexto por metadados em ~0,5s.

## 11. Próximas frentes

- PR 2.1 (WhatsApp/email) sem impacto direto.
- **EIXO 3** (unificação `Process.status` × `Process.macroetapa`, dívida #26)
  afeta os gates de avanço de etapa.

## 12. Validação Isis

- RAG estadual validado E2E (Sprint W, 2026-05-14).
- **Pendente:** skill/agente de legislação validado explicitamente pela Isis
  (saída regulatória conferida contra a prática dela).
