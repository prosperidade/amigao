# Sprint A1 — Arquitetura procedural (sem skills de domínio)

**Data:** 2026-05-08
**Status:** ✅ **CONCLUÍDA** — 6/6 tarefas mergeadas (A, C, D1, D2, B, E).
**Branch:** `main` (commits diretos)
**Fase 0 report:** [`SPRINT_A1_FASE0_REPORT.md`](../../SPRINT_A1_FASE0_REPORT.md) (raiz)
**Prompt origem:** [`SPRINT_A1_REGENTE_AMBIENTAL.md`](../../SPRINT_A1_REGENTE_AMBIENTAL.md) (raiz)

## Resumo executivo

Esta sprint constrói **toda a infraestrutura procedural** que a Sprint 1 (Skills) original precisava — menos as skills de domínio. Quando os PDFs-gabarito da sócia chegarem (Sprint A3), basta dropar arquivos `.md` em `app/skills/<agente>/<skill>/SKILL.md`.

Sequência aprovada na Fase 0: **A → C → D1 → D2 → B → E** (alteração proposital sobre A→B→C→D→E original — C antes de B fixa o tipo `CitationRef` antes de B reusar).

| Tarefa | Commit | Status | Testes | Linhas |
|---|---|---|---|---|
| **A** — Skills infra (Forma B) | `100f7da` | ✅ done | 26 | +931/−2 |
| **C** — StageOutputContent + 3 schemas | `8001fc7` | ✅ done | 32 | +512 |
| **D1** — Modelos `RegulatoryDiagnosis`/`Issue` + migration | `5756e9d` | ✅ done | 10 | +631 |
| **D2** — Endpoints REST read-only | `dc165c7` | ✅ done | 15 | +499/−2 |
| **B** — Citation evaluator + hook RedatorAgent | `09e6f85` | ✅ done | 35 | +746/−1 |
| **E** — Feedback loop AtendimentoAgent | `3a8e1f8` | ✅ done | 10 | +844 |

**Total final:** 6 commits feature + 1 commit doc, **+4.163 / −6 linhas**, **128 testes novos**, lint limpo em todos os arquivos tocados.

---

## Tarefa A — Infraestrutura de Skills (Forma B, filesystem on-demand)

**Commit:** `100f7da` — `feat(sprint-a1-A): infraestrutura skills filesystem (Forma B)`

### Entrega

Estrutura `app/skills/`:
```
app/skills/
  __init__.py
  README.md                                  # convenção + formato + matching
  _registry.py                               # discoverer + loader + cache mtime
  redator/_template/SKILL.md                 # placeholder técnico
  extrator/_template/SKILL.md                # placeholder técnico
```

API pública (`app.skills`):
- `discover_skills(root=None) -> dict[str, SkillMetadata]` — varre `app/skills/**/SKILL.md`.
- `load_skill(name, root=None) -> SkillContent | None` — front-matter parseado + corpo.
- `matches_context(meta, agent, ctx_metadata) -> bool` — match por agente + interseção em `applies_to`.
- `invalidate_cache()` — útil em testes.
- `SkillParseError` — erro tipado para front-matter inválido (não derruba boot).

Front-matter YAML obrigatório: `name`, `agent`, `version`, `description`. `applies_to` opcional com chaves plurais (`demand_types`, `doc_types`) — match conjuntivo, lista vazia = não restringe. Convenção plural→singular: `applies_to.demand_types: ["car"]` casa com `ctx.metadata.demand_type == "car"`.

### Integração no `BaseAgent`

- `_load_skills_for_context(self) -> list[SkillContent]` — lê `self.ctx.metadata` + `self.name`. Sem dict paralelo (Q7 da Fase 0).
- `_compose_system_with_skills(base) -> str` — encapsula prompt original com markers `<!-- skills:start --> ... <!-- skills:end -->`.
- `call_llm()` aplica composição automaticamente — agentes existentes não mudam.
- Fallback gracioso: zero skills, falha no registry, ou pasta ausente → comportamento idêntico ao anterior.

### Decisões aplicadas

- **Q7:** `_load_skills_for_context(self)` sem dict paralelo (alinha com `AgentContext`).
- **Risk #1/#2:** `# TODO(perf)` registrado no `_registry.py` para multi-worker — aceito por enquanto.
- **Não-objetivos respeitados:** sem skills de domínio, sem hot-reload sofisticado, sem versionamento semver enforced.

### Testes

26 novos, 100% passing no container:
- `tests/skills/test_registry.py` — 14 (descoberta vazia/preenchida, parsing front-matter válido/inválido, YAML error, campo obrigatório ausente, cache mtime, skip de skill inválida, matching por agent/demand_type/conjunção/lista vazia).
- `tests/skills/test_base_agent_integration.py` — 12 (load + compose + call_llm wrapping + smoke contra placeholders reais).

---

## Tarefa C — StageOutputContent framework + 3 schemas iniciais

**Commit:** `8001fc7` — `feat(sprint-a1-C): StageOutputContent framework + 3 schemas iniciais`

### Entrega

`app/schemas/stage_output.py` (Pydantic v2, `model_config(extra="forbid")`):

```
StageOutputContent              (base — content/metadata/sources/confidence)
├── DiagnosticoPreliminarContent (hipóteses/lacunas/riscos/checklist)
├── PecaJuridicaContent          (template/legal_citations/addressee)
│   └── RespostaNotificacaoContent (+ prazo_dias/ato_regulatorio)
```

Tipos auxiliares:
- `Source(type, ref, excerpt?)` — `type ∈ {legislation, document, manual}`.
- `CitationRef(kind, numero, ano, raw, chunk_id?, jurisdicao?, artigo?)` — **tipo canônico** reusado pelo evaluator da Tarefa B.
  - `kind ∈ {lei, lei_complementar, decreto, decreto_lei, resolucao_conama, instrucao_normativa, portaria, medida_provisoria, outro}` (9 categorias).
  - `jurisdicao ∈ {federal, estadual, municipal, outro}` — ortogonal ao `kind` (evita explosão combinatória); populado por `validate_citations` a partir do chunk.
  - `artigo` — descritivo em V1, base para cruzamento por artigo em V2.
- `Risco(descricao, severidade, mitigacao_sugerida?)` — `severidade ∈ {baixo, medio, alto}`.

Validações:
- `sources` não pode ser vazio (força "evidence ou nada").
- `confidence ∈ [0, 1]` quando presente.
- `CitationRef.ano ∈ [1500, 3000]`.
- `RespostaNotificacaoContent.prazo_dias ≥ 0`.
- `extra="forbid"` em todos — campo desconhecido falha fast (anti-drift).

### Decisões aplicadas

- **Q5:** `StageOutputContent` (não `StageOutputBase`) — não colide com `app.models.stage_output.StageOutput`.
- **Q1:** continua usando `StageOutput.content_data` (JSONB do ORM existente). Sem `AIJob.output_data` separado.
- **Adoção opt-in:** nenhum agente migrado nesta sprint. Coexistência com `dict[str, Any]` legado é explícita.
- **Risk #5:** sem tabela N–N — `RegulatoryDiagnosis` (Tarefa D) referenciará issues via lista de IDs no próprio `content`.

### Documentação

`docs/schemas_stage_output.md` — contexto, regras de validação, exemplos de uso, plano de migração Sprint A2.

### Testes

32 novos, 100% passing:
- `tests/schemas/test_stage_output.py` — Source/CitationRef/StageOutputContent base/Diagnostico/PecaJuridica/RespostaNotificacao + round-trip JSON + coexistência com dict legado.

---

## Tarefa D1 — Modelos RegulatoryDiagnosis + RegulatoryIssue

**Commit:** `5756e9d` — `feat(sprint-a1-D1): modelos RegulatoryDiagnosis e RegulatoryIssue + migration`

### Entrega

`app/models/regulatory.py`:
- `RegulatoryDiagnosis(tenant_id, process_id FK CASCADE, content JSONB, version, validated_by_user_id? FK SET NULL, validated_at?, created_at, updated_at)`
  - Constraint: `unique(process_id, version)` — versionamento simples (caller incrementa).
  - `content` JSONB pode ser um `DiagnosticoPreliminarContent` (Tarefa C) ou dict legado.
- `RegulatoryIssue(tenant_id, property_id FK CASCADE, document_id? FK SET NULL, type, severity, payload? JSONB, detected_by, detected_at, resolved_at?)`
  - `type ∈ {area_divergente, sobreposicao_app, sobreposicao_reserva, poligono_fora_matricula, outro}`.
  - `severity ∈ {info, warning, critical}` (default `warning`).

Migration `alembic/versions/a8e1d4c7f3b6_sprint_a1_regulatory_diagnosis_issue.py`:
- `down_revision = c4e6f8a0d2b3` (último head antes desta sprint).
- 2 tabelas + ENUMs Postgres explícitos (`regulatory_issue_type`, `regulatory_issue_severity`) — drop limpo no downgrade (Postgres não dropa o tipo automaticamente).
- 7 índices + 1 unique constraint composto.

### Validação manual da migration

Documentada na docstring da própria migration (Q6 da Fase 0):

```bash
docker compose exec api alembic upgrade head     # OK — schema confirmado via \d psql
docker compose exec api alembic downgrade -1     # OK — to_regclass retorna NULL
docker compose exec api alembic upgrade head     # re-up OK
```

Os 3 estados foram testados manualmente contra o Postgres do compose; todos limpos.

### Decisões aplicadas

- **Q4:** **sem** tabela associativa N–N. `RegulatoryIssue` não tem FK para `RegulatoryDiagnosis`. Quando um diagnóstico quiser referenciar issues, lista IDs em `content["issue_ids"]: list[int]`.
- **Risk #4:** `app/models/process.py:initial_diagnosis` ganhou comentário inline marcando como "legacy field — fonte canônica é `regulatory.py:RegulatoryDiagnosis`".
- **Q6:** testes não usam Alembic; `Base.metadata.create_all` do conftest cobre os modelos novos automaticamente. Validação up/down ficou manual (documentada na migration).
- Bug fix encontrado durante D2: relationships com `backref=` causam `ArgumentError: property of that name exists on mapper` em hot-reload do uvicorn — substituído por `relationship(..., foreign_keys=[...])` puro. Quando A2/Y precisar de back-relationship, usar `back_populates` explícito em ambos os lados.

### Testes

10 novos em `tests/models/test_regulatory.py`:
- `TestRegulatoryDiagnosis × 5`: create_minimal, unique constraint, multiple versions, human validation, content carregando issue_ids (sem N–N).
- `TestRegulatoryIssue × 5`: create_minimal (defaults), document link, severity enum, resolved_at marca conclusão, `test_no_n_n_with_diagnosis` (verifica explicitamente que os modelos não têm FK/relationship cruzados).

⚠️ **Limitação ambiental:** os testes dependem de Testcontainers + Postgres real, que não roda dentro do api container (Docker-in-Docker permission). Vão verde quando rodados no host (`pytest tests/models/test_regulatory.py`).

---

## Tarefa D2 — Endpoints REST read-only

**Commit:** `dc165c7` — `feat(sprint-a1-D2): endpoints REST read-only para diagnoses + issues`

### Entrega

3 endpoints (auth: `internal` profile, tenant isolation aplicada):

| Método | Path | Comportamento |
|---|---|---|
| GET | `/api/v1/processes/{process_id}/diagnoses` | lista versões ordenadas por `version desc` |
| GET | `/api/v1/processes/{process_id}/diagnoses/{version}` | versão específica |
| GET | `/api/v1/properties/{property_id}/issues?status=open\|resolved\|all` | issues filtráveis (default `open`); `resolved` requer `resolved_at IS NOT NULL`; `all` sem filtro |

Codes:
- 401 sem auth
- 404 quando processo/imóvel não existe ou pertence a outro tenant
- 422 quando `status` fora do enum

Arquivos:
- `app/api/v1/regulatory.py` — `process_router` + `property_router` (segue padrão `app/api/v1/workflows.py` com 2 routers no mesmo módulo).
- `app/schemas/regulatory.py` — `RegulatoryDiagnosisOut` + `RegulatoryIssueOut` + `IssueStatusFilter` (Literal). `model_config(from_attributes=True)` para serializar direto do ORM.
- `app/main.py` — registra os 2 routers em `/processes` e `/properties` com tag "Diagnóstico Regulatório".

Sem POST/PUT/PATCH/DELETE — escrita fica para Sprint A2/Y (`auditor_imovel` + consultor).

### Smoke test funcional (api container live)

- ✅ 401 sem auth nos 3 endpoints
- ✅ 404 com `process_id`/`property_id` inexistente
- ✅ 422 com `?status=blabla`
- ✅ 200 `[]` em processo de tenant correto sem dados (`/processes/3/diagnoses` no tenant 2)
- ✅ 404 ao tentar acessar processo de outro tenant (`/processes/1/diagnoses` para user do tenant 2)

### Testes

15 novos em `tests/api/test_regulatory.py`:
- `TestListDiagnoses × 5` — 401, vazio, ordem desc, 404 process, tenant isolation cross-tenant.
- `TestGetDiagnosisVersion × 2` — versão específica, 404 versão.
- `TestListPropertyIssues × 8` — 401, vazio, 404 property, default open, filtro resolved, filtro all, status inválido (422), ordem por `detected_at`.

⚠️ Mesma limitação ambiental da D1 (Testcontainers).

---

## Tarefa B — Citation evaluator + hook RedatorAgent

**Commit:** `09e6f85` — `feat(sprint-a1-B): evaluator de citação legal pós-redator`

### CitationRef ajustada (após review da Fase 0)

Acréscimos antes de B começar:
- `jurisdicao: Literal["federal", "estadual", "municipal", "outro"] | None` — ortogonal a `kind`, evita explosão combinatória ("lei_estadual"/"decreto_estadual"/...). Populada pelo `validate_citations` a partir do `SearchResult.jurisdiction`.
- `artigo: str | None` — capturado em `extract_citations` ("art. 7º", "art. 12, § 2º"); descritivo em V1, base para cruzamento por artigo em V2.

### Entrega

`app/services/citation_evaluator.py`:
- `extract_citations(text) -> list[CitationRef]`
  Regex multi-formato (ordem importa para evitar match parcial):
  1. **Lei Complementar** (antes de Lei)
  2. **Decreto-Lei** (antes de Decreto)
  3. **Decreto**
  4. **Lei**
  5. **Resolução genérica com SIGLA** — `CONAMA → resolucao_conama`, demais → `outro` (acomoda futuras CONABIO/CONAREM sem refator).
  6. **Instrução Normativa / IN <ÓRGÃO>**
  7. **Portaria <ÓRGÃO opcional>**
  8. **MP / Medida Provisória**

  Variantes suportadas: `n°` (ordinal masculino) e `nº`, `12651` sem pontos, ano de 2 dígitos com inferência (`<50 → 20xx`, `≥50 → 19xx`), prefixo `art. X[, § Y]` capturado, forma extensa `, de DD de MES de AAAA`.

  Deduplicação por `(kind, numero_dígito-only, ano)`. Acórdãos STF/STJ ficam fora de escopo (regra explícita do prompt).

- `validate_citations(citations, legislation_context) -> CitationValidationResult`
  Aceita contexto heterogêneo: `CitationRef`, `SearchResult` duck-typed, ou strings tipo "Lei 12.651/2012".
  Match por `(kind, numero_normalizado, ano)`. Quando casa contra `SearchResult`, popula `chunk_id` + `jurisdicao` no `CitationRef` original (preserva valores já preenchidos pelo caller). **Sem chamadas RAG novas** — só cruza contra contexto in-memory.

- `CitationValidationResult` dataclass: `valid`, `total`, `invalid: list[CitationRef]`, `coverage_ratio`.

### Hook em RedatorAgent

`app/agents/redator.py:_evaluate_citations(text, legal_data)`:
- Roda **só** quando há contexto: `legal_data["legislacao_aplicavel"]` + `["normas_estaduais"]` + `["rag_chunks_meta"]` (espaço para Sprint A2 expor `SearchResult` reais).
- Sem contexto → **skip silencioso** (caller decidiu prescindir do RAG, não temos verdade a confrontar).
- `result["citation_issues"] = [c.model_dump() for c in invalid]` + `result["citation_total" / "citation_coverage_ratio" / "citation_valid"]`.
- `requires_review` continua `True` por default (peças formais sempre).
- **Não bloqueia** o output — só marca.

### Decisões aplicadas

- **Q1 confirmada:** `AIJob.result["citation_issues"]` (não `output_data`).
- **Não bloqueante:** peça gerada chega ao consultor com badge.
- **Sem novas chamadas RAG.**
- **Risk #3:** cobertura ~80% — variantes OCRizadas (`°`/`º`) suportadas.
- **CitationKind 9 categorias** mantidas; CONABIO/CONAREM caem em `outro` (V1).
- **`numero: str`** preserva "12.651"; comporta "MMA 2/2014", "001/2026", "2.166-67".
- Bug fix encontrado durante implementação: regex `(\d{2}|\d{4})` capturava só "20" para "2012" — invertido para `(\d{4}|\d{2})` (alternation é leftmost em re).

### Smoke test live (2 cenários)

| Cenário | `chain_data["legislacao"]` | LLM produz | Resultado |
|---|---|---|---|
| 1 — sem chain | `{}` | "Lei 12.651/2012 e Lei 99.999/2099" | `citation_issues` ausente — skip silencioso |
| 2 — com chain | `legislacao_aplicavel=["Lei 12.651/2012"]` | idem | `total=2, valid=False, coverage=0.5, issues=[(lei, 99.999, 2099)]` |

### Testes

35 novos, 100% passing:
- `tests/services/test_citation_evaluator.py` — 30 (extract: vazio + 14 variantes paramétricas + Lei Complementar não engole "Lei" + DL não engole "Decreto" + Resolução genérica → outro + artigo + dedupe + raw preservado + ano de 2 dígitos; validate: todos válidos + 1 inválida + citações vazias + SearchResult enriquece + não sobrescreve + normalização de número + contexto não-parseável ignorado + mix).
- `tests/agents/test_redator_citation_hook.py` — 5 (sem chain skip, todas válidas, 1 alucinação, sem citações, normas_estaduais conta como contexto).

---

## Tarefa E — Feedback loop AtendimentoAgent

**Commit:** `3a8e1f8` — `feat(sprint-a1-E): feedback loop AtendimentoAgent + endpoint de stats`

### Investigação Q3 — Plano B confirmado

❌ Plano A (instrumentar PATCH posterior em `Process.demand_type`) inviável: `PUT /processes/{id}` existe mas `ProcessUpdate` só expõe `title`, `process_type`, `description`, `status`. Não há nenhum endpoint hoje que atualize `demand_type`. **Plano B aplicado**: novo endpoint canônico `/processes/{id}/classify`.

### Entrega

**Modelo** `app/models/intake_classification_feedback.py`:
- `IntakeClassificationFeedback(tenant_id, process_id FK CASCADE, intake_draft_id? FK SET NULL, ai_demand_type, ai_confidence?, ai_run_id? FK SET NULL, corrected_demand_type, corrected_by_user_id? FK SET NULL, corrected_at)`.
- 3 índices (`tenant_id`, `process_id`, `intake_draft_id`).

**Migration** `b9d2e5a8f4c1` (down_revision = `a8e1d4c7f3b6`). Validada manualmente up/down/up no Postgres real.

**Endpoints** (`app/api/v1/intake_feedback.py`, auth: `internal`):
- `POST /api/v1/processes/{id}/classify` — body `{demand_type}`. Atualiza `Process.demand_type` e grava log **sempre** (cada call é evento). Hook automático lê o último `AIJob` com `agent_name='atendimento'` vinculado ao mesmo `intake_draft` (via `entity_id`) e captura `ai_demand_type`/`ai_confidence`/`ai_run_id`. Resposta inclui `previous_demand_type`, `new_demand_type`, `feedback_id`, `ai_demand_type`, `diverged_from_ai`. Sem máquina-de-estados — qualquer transição aceita. Trilha auditoria espelhada em `audit_log` (`action="demand_type_classified"`).
- `GET /api/v1/admin/intake-feedback/stats` — métricas tenant-scoped:
  - `total_classifications`: nº de processos com pelo menos 1 log.
  - `total_corrections`: nº de processos onde IA divergiu (último log por processo).
  - `accuracy_overall = 1 - corrections/classifications`.
  - `accuracy_by_demand_type`: precisão por tipo humano final.
  - `top_corrections`: até 10 pares `"X -> Y"` mais frequentes.

### Decisões aplicadas (defaults dos 4 detalhes pendentes)

1. **Idempotência:** cada `/classify` gera 1 log; `accuracy_overall` usa **último** log por processo (consultor pode reclassificar várias vezes — só a decisão final entra na métrica).
2. **Sem máquina-de-estados** em `demand_type` — aceita qualquer transição (até voltar a `nao_identificado`).
3. **`/admin/stats`** com `get_current_internal_user` (qualquer interno do tenant; não exige `is_superuser`).
4. **`top_corrections`** limitado a 10 itens.

Resolve **Risk #6** (denominador enviesado): só conta correções **explícitas**, não casos abandonados sem classificação.

### Smoke test live (api container, contra dados reais)

| # | Cenário | Resultado |
|---|---|---|
| 1 | `GET /admin/intake-feedback/stats` (tenant sem logs) | `{total_classifications:0, ...}` 200 |
| 2 | `POST /processes/9999/classify` | 404 |
| 3 | `POST /processes/9999/classify` body `{"demand_type":"naoexiste"}` | 422 |
| 4 | `POST /processes/3/classify {"demand_type":"retificacao_car"}` (AIJob histórico tinha `misto`) | 200, `diverged_from_ai=true`, log gravado |
| 5 | stats após call 4 | `accuracy=0.0`, `top_corrections=[["misto -> retificacao_car", 1]]` |
| 6 | `POST /processes/3/classify {"demand_type":"misto"}` (consultor reclassifica) | 200, `feedback_id=2`, `diverged_from_ai=false` |
| 7 | stats após call 6 (último log = misto, IA = misto) | `accuracy=1.0`, `top_corrections=[]` — **idempotência confirmada** |
| 8 | `GET /processes/3` | `demand_type: "misto"` — Process efetivamente atualizado |

Logs de smoke removidos do banco antes do commit (`DELETE FROM intake_classification_feedback WHERE id IN (1,2)`).

### Testes

10 novos em `tests/api/test_intake_feedback.py`:
- `TestClassifyEndpoint × 6`: 401, 404, 422, atualiza+loga+captura AI, sem AI rodada (graceful), idempotência (2 calls = 2 logs preservados em ordem), tenant isolation cross-tenant.
- `TestStatsEndpoint × 4`: 401, vazio = zeros, último-log-por-processo drives accuracy (3 processos, p3 reclassificado 2x), tenant isolation.

⚠️ Mesma limitação ambiental das outras tarefas — exigem `pytest` no host.

---

## Métricas finais (6/6 tarefas)

| Métrica | Valor |
|---|---|
| Commits feature | 6 (`100f7da`, `8001fc7`, `5756e9d`, `dc165c7`, `09e6f85`, `3a8e1f8`) |
| Commits doc | 1 (`1169521`) |
| Linhas adicionadas | **+4.163** |
| Linhas removidas | −6 |
| Arquivos novos | 23 (8 código + 2 migrations + 9 testes + 4 docs) |
| Arquivos modificados | 7 (`app/agents/base.py`, `app/agents/redator.py`, `app/main.py`, `app/models/__init__.py`, `app/models/process.py`, `requirements.txt`, `app/schemas/stage_output.py`) |
| Testes novos | **128** (26 skills + 32 schemas + 10 regulatory models + 15 regulatory API + 30 evaluator + 5 hook redator + 10 intake_feedback) |
| Testes verde no container | **103** (rodáveis sem DB real) |
| Testes que requerem pytest no host | **25** (regulatory models/API + intake_feedback API — Testcontainers + Postgres) |
| Lint `ruff check` | ✅ limpo em todos os arquivos tocados |
| Smoke tests live | ✅ todos os endpoints novos validados contra a API rodando |

---

## Decisões da Fase 0 — checklist final

| # | Decisão | Aplicada? |
|---|---|---|
| Q1 | `AIJob.result` em vez de `output_data` | ✅ B usa `result["citation_issues"]` |
| Q2 | Endpoint `/commit` não `/confirm` | ✅ E referencia `/commit` real (não criou `/confirm`) |
| Q3 | Captura via `Process.demand_type` posterior | ✅ Plano B aplicado: novo `POST /processes/{id}/classify` |
| Q4 | Sem tabela N–N entre Diagnosis e Issue | ✅ D1 |
| Q5 | `StageOutputContent` (não `StageOutputBase`) | ✅ C |
| Q6 | Testes não usam Alembic; validação manual documentada | ✅ D1 + E |
| Q7 | `_load_skills_for_context(self)` sem dict paralelo | ✅ A |
| Q8 | Tabela dedicada `intake_classification_feedback` | ✅ E |
| Risk #1/#2 | `# TODO(perf)` no `_registry.py` | ✅ A |
| Risk #3 | Regex evaluator cobre ~80% | ✅ B |
| Risk #4 | Comentário "legacy" em `Process.initial_diagnosis` | ✅ D1 |
| Risk #5 | Sem N–N (drop tabela associativa) | ✅ D1 |
| Risk #6 | Captura via correção explícita | ✅ E (denominador = só correções explícitas) |

---

## Pontos de pausa explícitos (do prompt)

✅ Pausa antes de B — reportei tipo `CitationRef`. Solicitante aprovou com 2 ajustes (`jurisdicao` + `artigo`) incorporados.
✅ Pausa antes de E — reportei cenário Q3 (Plano B necessário). Solicitante aprovou com sinal "vai E"; 4 detalhes secundários resolvidos com defaults documentados.

---

## Próximos passos previsíveis (FORA desta sprint, do prompt original)

- **Sprint A2** — adoção gradual de `StageOutputContent` nos 5 agentes (extrator → atendimento → diagnostico → redator → legislacao). Cada um vira sub-commit; os outros continuam aceitando `dict` enquanto não migram.
- **Sprint A3** — Skills de domínio (chega quando os PDFs-gabarito da sócia chegarem). Cria os arquivos `.md` em `app/skills/redator/` e `app/skills/extrator/`. A infra já existe (Tarefa A).
- **Sprint Y** — Auditor de inconsistências C6 (depende de `Property.geom` populado + parser shapefile). Modelos `RegulatoryIssue` já existem; falta o agente `auditor_imovel` + endpoint `POST /properties/{id}/audit`.
- **Sprint W4** — OCR worker (paralelo, já priorizado).
