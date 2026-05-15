# Sprint A1 — Arquitetura procedural (sem dependência de skills de domínio)

> **Status:** proposta — aguarda validação do solicitante na **Fase 0** antes de qualquer commit.
> **Relação com sprints anteriores:** complementa Sprints -1/0/U/V; substitui parcialmente a Sprint 1 cujo gate (PDFs-gabarito da sócia) segue aberto. Esse sprint constrói **toda a infraestrutura** que a Sprint 1 precisa, **menos** as skills de domínio. Quando os PDFs chegarem, é só dropar arquivos `.md` em `app/skills/redator/`.
> **Branch sugerida:** `feat/sprint-a1-arquitetura-procedural`

## Pré-condições

- [ ] Audit `docs/AUDITORIA_FLUXO_2026-04-29.md` lido.
- [ ] Relatório parcial `descoberta-agentes/RELATORIO_PARCIAL.md` lido.
- [ ] Histórico `docs/progressoIA.md` consultado.
- [ ] `prompt_claude_code_sprints.md` (raiz) consultado para padrões de Sprint.
- [ ] Branch `main` em estado verde (testes passando).

## Princípios inegociáveis (NÃO viole)

1. **Read-then-act.** Fase 0 (PARE E PERGUNTE) é obrigatória. Não rode migration, não modifique `BaseAgent`, não escreva código de produção até receber sinal verde explícito do solicitante.
2. **Evidência ou nada.** Toda decisão arquitetural deve referenciar audit, relatório parcial, ou código com path. Sem evidência → vira pergunta na Fase 0.
3. **Incremental commits.** Cada Tarefa (A-E) tem seu próprio commit `feat(sprint-a1-X): ...`. Sem mega-commit no fim.
4. **Tests obrigatórios.** Toda Tarefa entrega testes. Caminhos felizes + ao menos 1 caminho de erro.
5. **Não tocar fora do escopo.** Se aparecer impulso de "já que estou aqui...", PARE e pergunte.
6. **Lint/format limpos** nos arquivos tocados (padrão do projeto — confirmar na Fase 0).

## Não-objetivos (NÃO faça neste ciclo)

- ❌ Criar skills de domínio (`oficio_semad.md`, `prad.md`, `memorial_car.md`, etc.) — bloqueado por PDFs-gabarito da sócia.
- ❌ Tocar em pgvector, `knowledge_catalog`, embeddings, RAG.
- ❌ Mexer em frontend.
- ❌ Construir o Auditor de inconsistências (Tarefa C6 do relatório) — depende de `Property.geom` populado e parser shapefile.
- ❌ Construir crawlers DOU/DOE (Sprint 0 § 2.4 manteve diferido).
- ❌ Modificar OCR / pipeline de extração (Sprint W4 paralela).
- ❌ Trocar provider LLM, ajustar cost cap, mexer em retry/fallback do `ai_gateway`.
- ❌ Migrar `Process.initial_diagnosis` (Text livre) para o novo modelo `RegulatoryDiagnosis`. Coexistência é OK aqui.

## Fase 0 — PARE E PERGUNTE (obrigatória)

Antes de implementar qualquer Tarefa, faça **nesta ordem**:

### Passo 1 — Leia e confirme

Confirme que leu os arquivos abaixo. Use `view` em cada um. **Não confunda existir com ter lido.**

- `docs/AUDITORIA_FLUXO_2026-04-29.md`
- `descoberta-agentes/RELATORIO_PARCIAL.md`
- `prompt_claude_code_sprints.md` (raiz)
- `app/agents/base.py`
- `app/agents/redator.py`
- `app/agents/legislacao.py`
- `app/agents/diagnostico.py`
- `app/agents/atendimento.py`
- `app/agents/orchestrator.py`
- `app/core/ai_gateway.py`
- `app/services/macroetapa_engine.py`
- `app/services/llm_classifier.py`
- `app/services/intake_classifier.py`
- `app/services/document_extractor.py`
- `app/api/v1/intake.py`
- `app/models/` (em particular: `Process`, `Document`, `AIJob`, `IntakeDraft`, `Property`, `Client`)
- `tests/conftest.py` (padrões de teste)
- `pyproject.toml` (dependências, lint config, versão Pydantic, gerenciador de migration)
- `alembic.ini` ou equivalente (se existir)

### Passo 2 — Reporte ao solicitante (na conversa, sem commitar)

Estruture o report em 4 blocos:

**(a) Divergências encontradas** — entre o que está no relatório parcial / audit e o que você efetivamente vê no código. Ex: "relatório diz X linhas em `redator.py`, vejo Y"; "audit cita modelo Z que não existe"; "Pydantic v1 ou v2?".

**(b) Confirmação ou correção das suposições deste prompt** — em particular:
- Existência dos arquivos listados na Passo 1.
- Padrão de testes (pytest? framework? fixtures?).
- Padrão de migration (alembic? versão? convenção de nome?).
- Convenção de import (`from app.x` ou `from .x`?).
- Versão de Pydantic (v1 vs v2 muda muita coisa em Tarefa C).
- Como o `AIJob.output_data` JSONB é tipado (TypedDict? Pydantic? dict puro?).
- Se há linter (ruff/black/flake8) configurado e qual.

**(c) Riscos arquiteturais** que você enxergou e este prompt não cobre.

**(d) Proposta de execução**:
- Ordem das 5 Tarefas (A→E ou alternativa fundamentada).
- Estimativa de esforço relativo por Tarefa (XS/S/M/L/XL).
- Dependências entre Tarefas.
- Sugestão de partição alternativa, se fizer sentido (ex: "C deveria ser dividida em C1 e C2 porque...").

### Passo 3 — Liste perguntas em aberto

Numeradas. Toda pergunta deve ter o impacto explícito ("se a resposta for X, faço A; se for Y, faço B").

### Passo 4 — PARE

Espere sinal verde **explícito e literal** do solicitante. Frases válidas: "ok pode começar pela Tarefa A", "vai", "aprovado", "go". Sem isso, não escreva uma linha de código de produção.

---

## Tarefas

### Tarefa A — Infraestrutura de Skills (Forma B, filesystem on-demand)

**Por que primeiro:** desbloqueia futuras skills de domínio (Sprint A3) sem retrabalho. Quando os PDFs da sócia chegarem, basta dropar arquivos `.md`.

**Arquitetura proposta:**

Estrutura de pasta:
```
app/skills/
  README.md                           # documenta a convenção
  _registry.py                        # discoverer + loader + cache
  redator/
    _template/
      SKILL.md                        # placeholder técnico (NÃO de domínio)
  extrator/
    _template/
      SKILL.md
```

Convenção de `SKILL.md` (front-matter YAML + corpo markdown):
```yaml
---
name: redator/_template
agent: redator
applies_to:
  demand_types: ["template"]          # opcional
  doc_types: []                       # opcional
version: "0.1.0"
description: "Placeholder técnico — não usar em produção."
---

# Conteúdo procedural aqui (corpo markdown).
```

API do `_registry.py`:
- `discover_skills() -> dict[str, SkillMetadata]` — varre `app/skills/**/SKILL.md`.
- `load_skill(name: str) -> SkillContent` — retorna front-matter parseado + corpo.
- Cache em memória, invalidado por mtime do arquivo.
- Falha graciosamente: front-matter inválido → log estruturado + skill ignorada (não derruba boot).

Mudança no `BaseAgent`:
- Novo método `_load_skills_for_context(context: dict) -> list[SkillContent]`.
- Recebe contexto (`{"agent": "redator", "demand_type": "car", "doc_type": "matricula"}`).
- Match simples por agente + interseção em `applies_to`.
- Quando 0 encontrados, retorna `[]` sem warning.
- Quando 1+ encontrados, concatena no system prompt **abaixo** do prompt-base, **acima** do contexto dinâmico (delimitar com markers `<!-- skills:start -->` ... `<!-- skills:end -->`).

**Não fazer agora:**
- Lógica fina de "qual skill aplica em qual situação" além de match por `agent` + `demand_type`/`doc_type`.
- Skills de domínio reais.
- Versionamento sofisticado (semver enforcement, etc.).
- Hot-reload em dev (mtime já cobre).

**Testes obrigatórios** (`tests/skills/test_registry.py`, `tests/skills/test_base_agent_integration.py`):
- `discover_skills()` retorna `{}` quando pasta vazia.
- `discover_skills()` lista skill placeholder corretamente.
- `load_skill()` parseia front-matter + corpo.
- `load_skill()` levanta erro tipado quando front-matter inválido.
- Cache invalida quando `SKILL.md` modificado (mtime).
- `BaseAgent` injeta skill quando match; não injeta quando ausente.
- Integration: `RedatorAgent` com `demand_type='template'` carrega placeholder no system prompt.

**Critério de sucesso verificável:**
- `pytest tests/skills/` 100% verde.
- `app/skills/` versionada no Git, sem skills de domínio.
- Inspeção manual: rodar `RedatorAgent` em modo dry-run e ver placeholder no prompt final.

**Commit:** `feat(sprint-a1-A): infraestrutura skills filesystem (Forma B)`

---

### Tarefa B — Evaluator de citação legal pós-redator

**Por que junto com A:** mitiga risco de C2 (redator) **agora**, mesmo sem skills de domínio. Toda peça gerada que cita lei inexistente é marcada `requires_review=True` e não vai cega para o consultor.

**Arquitetura proposta:**

`app/services/citation_evaluator.py`:
- `extract_citations(text: str) -> list[Citation]` — regex multi-formato:
  - "Lei 12.651/2012", "Lei nº 12.651/2012", "Lei nº 12.651, de 25 de maio de 2012"
  - "Decreto X/AAAA", "Decreto-Lei X/AAAA"
  - "Resolução CONAMA nº X/AAAA"
  - "IN MMA X/AAAA"
  - Normaliza para `Citation(tipo, numero, ano, raw)`.
- `validate_citations(citations: list[Citation], legislation_context: list[KnowledgeChunk]) -> CitationValidationResult` — para cada citação, busca **no contexto já carregado** (NÃO faz nova consulta RAG).
- `CitationValidationResult(valid: bool, total: int, invalid: list[Citation], coverage_ratio: float)`.

Hook de integração:
- No `RedatorAgent` (ou no `BaseAgent` quando aplicável):
  - Após LLM responder, chamar `validate_citations`.
  - Se `valid=False`:
    - `AIJob.output_data["citation_issues"]` populado com lista de inválidas.
    - `requires_review=True` forçado.
    - Log estruturado com `process_id`, `agent`, `invalid_count`.
  - Se `valid=True`, segue normal.

**Não fazer agora:**
- Não tornar bloqueante (não rejeita output, só marca + força review).
- Não chamar pgvector — só valida contra contexto já presente.
- Normalizador robusto de identificador (Q3 do relatório). Versão simples agora cobre 80%+; refinar quando aparecer falso-positivo real em produção.
- Não cobrir citações jurisprudenciais (acórdão STF/STJ) — só normas.

**Testes obrigatórios** (`tests/services/test_citation_evaluator.py`):
- 3 citações válidas + contexto cobre as 3 → `valid=True`, `coverage_ratio=1.0`.
- 1 inválida + 2 válidas → `valid=False`, lista contém a inválida.
- Texto sem citação → `valid=True` (vacuosamente).
- Variações de formato → mesma `Citation` normalizada (tabela paramétrica com pelo menos 5 variações).
- Integration: `RedatorAgent` em dry-run com citação fabricada inválida → `requires_review=True` + `citation_issues` no output.

**Critério de sucesso verificável:**
- Testes verdes.
- Smoke test: rodar redator em 2 casos reais (controlados) e ver `citation_issues` na saída quando aplicável.

**Commit:** `feat(sprint-a1-B): evaluator de citação legal pós-redator`

---

### Tarefa C — `StageOutput` schemas (framework + 3 schemas iniciais)

**Por que:** fecha gap B2 do audit ("StageOutput sem schema obrigatório") sem forçar adoção em todos os agentes ainda. Constrói o framework e 3 schemas concretos prioritários. Adoção real em Sprint A2.

**Arquitetura proposta:**

`app/schemas/stage_output.py`:
```python
class Source(BaseModel):
    type: Literal["legislation", "document", "manual"]
    ref: str                            # ID do KnowledgeChunk, doc, ou ref livre
    excerpt: str | None = None

class StageOutputBase(BaseModel):
    content: str
    metadata: dict = Field(default_factory=dict)
    sources: list[Source]
    confidence: float | None = None     # 0..1
```

3 schemas derivados:
- `DiagnosticoPreliminarOutput(StageOutputBase)` com campos extras: `hipoteses: list[str]`, `lacunas: list[str]`, `riscos: list[Risco]`, `checklist_documental: list[str]`.
- `PecaJuridicaOutput(StageOutputBase)` com `template: Literal[...os 7 templates...]`, `legal_citations: list[CitationRef]`, `addressee: str | None`.
- `RespostaNotificacaoOutput(StageOutputBase)` (subtipo de `PecaJuridicaOutput` ou irmão, decidir na Fase 0) com `prazo_dias: int`, `ato_regulatorio: str`.

Validators:
- `sources` não vazio em `StageOutputBase`.
- `confidence` ∈ [0, 1] quando presente.
- `PecaJuridicaOutput.legal_citations`: cada `CitationRef` referencia `KnowledgeChunk.id` (FK lógica — validação no nível de schema).

**Adoção opt-in:**
- `BaseAgent.run()` aceita output em formato `dict` legado **e** em `StageOutputBase` ou subclasse.
- Quando `StageOutputBase`, persiste como JSONB no `AIJob.output_data`.
- Quando `dict`, comportamento atual mantido.
- **Nenhum agente é migrado neste sprint.**

**Não fazer agora:**
- Não migrar agentes existentes para usar `StageOutput`. Sprint A2.
- Não criar mais que 3 schemas. Os outros virão sob demanda do consultor sênior (Q6 do relatório).
- Não validar `legal_citations` contra `knowledge_catalog` real (validação só de tipo). Cruzamento real é com Tarefa B em runtime.

**Testes obrigatórios** (`tests/schemas/test_stage_output.py`):
- Construção válida de cada um dos 3 schemas.
- Validators funcionam (sources vazio → ValidationError; confidence > 1 → ValidationError).
- Serialização/deserialização JSON estável (round-trip).
- `BaseAgent.run()` aceita `dict` legado e `StageOutput` novo (parametrizado).

**Critério de sucesso verificável:**
- Testes verdes.
- Documentação: `docs/schemas_stage_output.md` com exemplo de uso e nota de migração futura (Sprint A2).

**Commit:** `feat(sprint-a1-C): StageOutput framework + 3 schemas iniciais`

---

### Tarefa D — Modelos `RegulatoryDiagnosis` + `RegulatoryIssue`

**Por que:** fecha gap B3 do audit. Habilita Sprint Y (Auditor C6) e Sprint A2. Estrutura sem popular ainda.

**Arquitetura proposta:**

`app/models/regulatory.py`:
- `RegulatoryDiagnosis`:
  - `id`, `process_id` (FK), `content` (JSONB — pode armazenar `DiagnosticoPreliminarOutput` da Tarefa C), `validated_by` (FK User, nullable), `version` (int, default 1), `created_at`, `updated_at`.
  - Constraint: unique(`process_id`, `version`).
- `RegulatoryIssue`:
  - `id`, `property_id` (FK), `document_id` (FK, nullable), `type` (enum: `area_divergente`, `sobreposicao_app`, `sobreposicao_reserva`, `poligono_fora_matricula`, `outro`), `severity` (enum: `info`, `warning`, `critical`), `payload` (JSONB), `detected_by` (string — nome do agente ou "manual"), `detected_at`, `resolved_at` (nullable).
- Relação `RegulatoryDiagnosis.issues` → lista de `RegulatoryIssue` referenciadas via tabela associativa `regulatory_diagnosis_issues(diagnosis_id, issue_id)`.

Migration alembic com `upgrade` e `downgrade`.

Endpoints REST mínimos (read-only):
- `GET /processes/{id}/diagnoses` — lista versões de diagnóstico do processo.
- `GET /processes/{id}/diagnoses/{version}` — versão específica.
- `GET /properties/{id}/issues?status=open|resolved|all` — lista issues do imóvel.

**Sem POST/PUT.** Escrita só em Sprint A2/Y por agente.

**Não fazer agora:**
- Popular dados retroativos.
- Escrever o auditor C6 (depende de `Property.geom` + shapefile parser).
- Migrar `Process.initial_diagnosis` (Text livre) para o novo modelo. Coexistência é OK.
- UI/frontend para visualizar issues.

**Testes obrigatórios** (`tests/models/test_regulatory.py`, `tests/api/test_regulatory_endpoints.py`):
- Migration `up` aplica sem erro.
- Migration `down` reverte sem erro.
- Modelos: criar/consultar via factories (siga o padrão de `tests/conftest.py`).
- Constraint `unique(process_id, version)` viola corretamente.
- `GET /processes/{id}/diagnoses` retorna `[]` quando vazio, lista ordenada por `version desc` quando preenchido.
- `GET /properties/{id}/issues` aceita query param `status`.
- 404 quando `process_id`/`property_id` não existem.

**Critério de sucesso verificável:**
- `alembic upgrade head` aplica migration limpa.
- `alembic downgrade -1` reverte limpa.
- Endpoints retornam JSON válido nos 3 caminhos (vazio, preenchido, 404).
- Testes verdes.

**Commit:** `feat(sprint-a1-D): modelos RegulatoryDiagnosis e RegulatoryIssue (read-only)`

---

### Tarefa E — Instrumentação do `AtendimentoAgent` (feedback loop C4)

**Por que:** responde à pergunta #5 do relatório parcial — gera dado pra decidir se C4 merece evolução. Sem instrumentação, evolução é palpite.

**Arquitetura proposta:**

Tabela `intake_classification_feedback`:
```
id (pk)
intake_draft_id (fk -> intake_drafts.id)
ia_demand_type (string)
ia_confidence (float, nullable)
ia_run_id (fk -> ai_jobs.id, nullable)
corrected_demand_type (string)
corrected_by_user_id (fk -> users.id)
corrected_at (timestamp)
```

Endpoint:
- `POST /intake/drafts/{id}/classification/correct` body `{"new_demand_type": "..."}` — registra correção manual antes do confirm. Auth: `internal` profile.

Hook automático no `POST /intake/drafts/{id}/confirm`:
- Compara `demand_type` final vs `demand_type` que o IA classificou (via última `AIJob` com `agent_name='atendimento'` + `intake_draft_id`).
- Se diferentes, log automático na tabela.
- Se iguais ou IA não rodou, nada.

Endpoint admin:
- `GET /admin/intake-feedback/stats` — auth `internal` ou `admin`.
- Retorna:
  ```json
  {
    "total_classifications": int,
    "total_corrections": int,
    "accuracy_overall": float,
    "accuracy_by_demand_type": {"car": 0.92, "licenciamento": 0.74, ...},
    "top_corrections": [["car -> retificacao_car", 12], ...]
  }
  ```

**Não fazer agora:**
- Não mudar comportamento do `AtendimentoAgent`. Só observar.
- Não construir UI de admin. Endpoint REST resolve.
- Não treinar/finetunar nada.

**Testes obrigatórios** (`tests/api/test_intake_feedback.py`):
- Confirmação de draft sem alteração de `demand_type`: nenhum log.
- Confirmação com alteração: 1 log com IDs corretos.
- Endpoint `correct` registra log + atualiza `intake_drafts.demand_type` (se assim for o fluxo atual — confirmar na Fase 0).
- `GET /admin/intake-feedback/stats` calcula precisão correta com dados sintéticos (cobrir caso de zero classificações).

**Critério de sucesso verificável:**
- Migration aplica.
- Testes verdes.
- Smoke test: criar 3 drafts (1 sem correção, 2 com), rodar stats, ver precisão = 1/3.

**Commit:** `feat(sprint-a1-E): feedback loop AtendimentoAgent + endpoint de stats`

---

## Sequenciamento sugerido (a confirmar na Fase 0)

```
Tarefa A (skills infra)        ─┐
                                ├──► smoke test integrado ──► fechar sprint
Tarefa B (citation evaluator) ──┤
Tarefa C (StageOutput schemas)  ─┤
Tarefa D (modelos regulatórios) ─┤
Tarefa E (feedback intake)      ─┘
```

- **A e B** ambos tocam em `BaseAgent` / `RedatorAgent`. Recomendo **A primeiro**, mergear, depois B em cima. Evita conflito de merge e rebase chato.
- **C, D, E** são independentes entre si e do par A/B.
- Paralelismo seguro: A → B em série; C, D, E em paralelo com A/B.

## Encerramento da sprint

Quando todas as Tarefas estiverem completas:

1. Atualize `docs/progressoIA.md` com seção "Sprint A1".
2. Crie `docs/sprints/sprint_a1.md` documentando: o que foi entregue, decisões tomadas, dívidas remanescentes, próximos passos sugeridos.
3. Imprima sumário na conversa: testes adicionados, commits, arquivos novos, dívidas, baseline de testes (passados/falhados antes vs depois).

## Próximos passos previsíveis (FORA deste sprint)

- **Sprint A2** — adoção gradual de `StageOutput` nos agentes existentes. Migra um por vez (sugestão: extrator → atendimento → diagnostico → redator → legislacao).
- **Sprint A3** — Skills de domínio (chega quando os PDFs da sócia chegarem). Cria os arquivos `.md` em `app/skills/redator/` e `app/skills/extrator/`. A infra já vai existir (Tarefa A).
- **Sprint Y** — Auditor de inconsistências C6 (depende de `Property.geom` populado + shapefile parser).
- **Sprint W4** — OCR worker (paralelo, já priorizado).

---

**Fim do prompt.** Cole tudo a partir do título "# Sprint A1 — ..." até esta linha em uma sessão do Claude Code aberta na raiz do projeto Regente Ambiental. **Lembre que a Fase 0 é obrigatória — não autorize execução até receber o report estruturado em 4 blocos.**
