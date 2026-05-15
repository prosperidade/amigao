# Sprint A1 — Fase 0 (PARE E PERGUNTE) — Report estruturado

**Data:** 2026-05-08
**Branch:** `main` @ `ad1ce5d`
**Prompt:** `SPRINT_A1_REGENTE_AMBIENTAL.md` (raiz)
**Audit prévio referenciado:** `docs/AUDITORIA_FLUXO_2026-04-29.md`, `descoberta-agentes/RELATORIO_PARCIAL.md`, `docs/progressoIA.md`
**Status:** aguardando sinal verde explícito do solicitante antes de qualquer commit em código de produção.

---

## Step 1 — Arquivos lidos

Os 18 arquivos da Fase 0 Step 1 foram lidos (incluindo `app/agents/base.py`, `legislacao.py`, `diagnostico.py`, `atendimento.py`, `orchestrator.py`, `redator.py`, `extrator.py`, `app/api/v1/intake.py`, `app/models/stage_output.py`, `document.py`, `ai_job.py`, `intake_draft.py`, `tests/conftest.py`, `pyproject.toml`). Não foi escrita nenhuma linha de código de produção. Versões reais em runtime confirmadas via `docker compose exec`:

| Dependência | Versão real |
|---|---|
| Pydantic | 2.12.5 |
| SQLAlchemy | 2.0.49 |
| FastAPI | 0.136.1 |
| Alembic | 1.18.4 |

---

## (a) Divergências encontradas entre prompt × código real

1. **`AIJob.output_data` não existe.** Tarefa B (linha 190) e Tarefa C (linha 247) referem-se a `AIJob.output_data["citation_issues"]` / "persiste como JSONB no `AIJob.output_data`". O modelo real ([app/models/ai_job.py:70](app/models/ai_job.py#L70)) tem o campo `result` (`PortableJSON`). Para `citation_issues`, o caminho natural é `AIJob.result["citation_issues"]` (já é o que `_complete_job` faz hoje em [app/agents/base.py:378](app/agents/base.py#L378)).

2. **`StageOutput` já é um modelo SQLAlchemy.** Tarefa C propõe `app/schemas/stage_output.py` com `StageOutputBase(BaseModel)` Pydantic, mas já existe [app/models/stage_output.py:29](app/models/stage_output.py#L29) (SQLAlchemy ORM com `content_data` JSONB e `output_type` String). A Tarefa C continua válida — separação `models/` (ORM) vs `schemas/` (Pydantic) é convenção do projeto — só precisa ficar explícito que o **Pydantic schema valida o conteúdo do `content_data` JSONB** do ORM existente, e que o naming não pode colidir nos imports.

3. **Endpoint de confirmação se chama `/drafts/{id}/commit`, não `/confirm`.** Tarefa E (linhas 339, 365) refere-se a `POST /intake/drafts/{id}/confirm`. O endpoint real ([app/api/v1/intake.py:926](app/api/v1/intake.py#L926)) é `commit_draft`. Um caller externo que use `/confirm` tomará 404. Trocar para `commit` na Tarefa E é trivial.

4. **`IntakeDraft.demand_type` não é uma coluna.** Tarefa E pressupõe comparar "`demand_type` final vs IA" no momento do `commit`. Mas: (a) o draft guarda o demand_type dentro de `form_data` (JSONB), não em coluna ([app/models/intake_draft.py:66](app/models/intake_draft.py#L66)); (b) o `Process` resultante **sempre** nasce com `DemandType.nao_identificado` ([app/api/v1/intake.py:191-199](app/api/v1/intake.py#L191-L199), comentário CAM1-003 Opção B). O `demand_type` "real" é classificação rodada **antes** do commit (`DemandClassification` em `intake_classifier.py`) e a "promoção" é feita pelo consultor depois, em outra ação. Isso muda fundamentalmente o ponto de captura: a correção do consultor não acontece no `commit_draft`, acontece no momento em que ele atualiza o `Process.demand_type` posterior. O prompt está enxergando um fluxo que esse projeto não tem.

5. **Tabela `intake_drafts` não tem coluna `demand_type` para `update`.** Tarefa E último teste (linha 365) diz "Endpoint `correct` ... atualiza `intake_drafts.demand_type` (se assim for o fluxo atual — confirmar na Fase 0)". Confirmando: **não é o fluxo**. O update teria que ser em `Process.demand_type` (após commit) ou em `IntakeDraft.form_data["demand_type"]` (antes).

6. **Testes não usam Alembic.** [tests/conftest.py:38](tests/conftest.py#L38) faz `Base.metadata.create_all(bind=engine)` direto com Testcontainers PostgreSQL+PostGIS, função-scoped com transação rollback. Isso afeta Tarefa D ("Migration `up` aplica sem erro") — o teste de migration teria que rodar Alembic explicitamente em um engine paralelo. Não é o padrão do conftest atual; vale teste manual de migration (`alembic upgrade head`) + um teste isolado que importa o módulo da migration sem o resto do conftest.

7. **Padrão `_load_skills_for_context(context: dict)` colide com o estilo atual.** Os agentes não passam `dict` de contexto — `BaseAgent` lê tudo de `self.ctx` (`AgentContext` dataclass com `tenant_id`, `process_id`, `metadata`, `chain_data`). A assinatura proposta na Tarefa A reintroduz um dict paralelo. Sugiro `_load_skills_for_context(self) -> list[SkillContent]` lendo de `self.ctx.metadata` e `self.name` — alinha com o resto do código.

8. **Re-uso de `AIJob.entity_id`/`entity_type` para vincular feedback.** Tarefa E propõe nova tabela `intake_classification_feedback`. Antes de criar, vale notar que `AIJob` já tem `agent_name`, `chain_trace_id`, `entity_type`, `entity_id`, `result` — uma alternativa mais leve seria armazenar a correção como uma row de `audit_log` ou como atualização do próprio `AIJob.result["corrected_to"]`. Tabela dedicada continua sendo o caminho mais explícito; só explicito para o solicitante decidir.

---

## (b) Confirmação / correção de suposições do prompt

| Item | Estado real |
|---|---|
| Pydantic | **v2.12.5** — usar `model_config = ConfigDict(...)`, `Field`, `field_validator`. CLAUDE.md já exige. |
| SQLAlchemy | **2.0.49** com `from sqlalchemy.orm import declarative_base`. |
| Alembic | **1.18.4** instalado, `alembic/versions/` com convenção `<hash>_<descricao>.py`. **Não usado em testes** — `Base.metadata.create_all` direto (conftest). |
| FastAPI | **0.136.1**. |
| Testes | **pytest + pytest-cov + Testcontainers PostgreSQL+PostGIS 15-3.3** ([tests/conftest.py:25](tests/conftest.py#L25)). Function-scoped session em transação rollback, TestClient FastAPI compartilhando a mesma sessão via `dependency_overrides[get_db]`. `fail_under=70` em coverage. |
| Imports | **`from app.x import Y`** (absolute imports), com `noqa: PLC0415` para imports tardios dentro de funções (padrão recorrente). |
| Lint | **Ruff** (line-length 120, target py311), ignores documentados em [pyproject.toml:31-46](pyproject.toml#L31). MyPy configurado mas com `ignore_errors=True` em workers. |
| `AIJob.output_data` | **Não existe.** Usar `result` (PortableJSON). |
| Pasta `app/skills/` | **Não existe.** Caminho livre (confirmado por `ls`). |
| Pasta `tests/skills/`, `tests/schemas/`, `tests/models/test_regulatory.py` | **Nenhum existe.** Pode criar. |
| `KnowledgeChunk` | Tipo real é `SearchResult` ([app/services/knowledge_catalog.py:36](app/services/knowledge_catalog.py#L36)) — `id, source_type, source_ref, title, section, identifier, chunk_text, jurisdiction, uf, agency, similarity`. Tarefa B precisa importar daqui. |
| Tabela `regulatory_issues` | **Não existe.** Tarefa D vai criá-la. |
| Endpoint `/processes/{id}/diagnoses` | **Não existe.** Tarefa D vai criá-lo. |

---

## (c) Riscos arquiteturais não cobertos pelo prompt

1. **Race condition na invalidação por mtime (Tarefa A).** Em produção rodando múltiplos workers Gunicorn, cada processo tem seu cache; mtime check funciona, mas a 1ª invalidação por worker custa I/O. Não é bloqueador — só vale registrar.
2. **`_load_skills_for_context` chamado do `BaseAgent.run()` adiciona um filesystem read no caminho crítico de cada execução de agente.** Hoje a chain `diagnostico_completo` faz 3 execuções; passa a fazer 3 file reads + parses YAML por chain. Cache resolve, mas o "primeiro hit" do dia paga. Aceitável; só registrar.
3. **Citation evaluator (Tarefa B) com regex pode dar falso-negativo em variações OCRizadas** ("Lei n° 12.651/2012" com `°` em vez de `nº`, "Lei 12651/12" sem barra, etc.). O próprio prompt já admite cobertura "80%+"; risco é não bloqueante e mitigado pelo `requires_review=True`.
4. **Coexistência de `Process.initial_diagnosis` (Text) com `RegulatoryDiagnosis` (JSONB versionado)** vai gerar dúvida em quem ler a UI: qual fonte é canônica? O prompt explicitamente permite a coexistência, mas seria bom já reservar comentário no model dizendo "campo legacy, ver `RegulatoryDiagnosis`" para evitar bug futuro.
5. **A tabela `regulatory_diagnosis_issues(diagnosis_id, issue_id)` (associativa N-N)** não é justificada pelo audit. O audit (gap I3) modela `RegulatoryIssue` como **diretamente vinculada ao Property/Document**, não como N-N com `RegulatoryDiagnosis`. Vale perguntar antes de criar a tabela associativa: queremos N-N (uma issue cabendo em vários diagnósticos) ou apenas FK direta + filtro por `process_id` no select?
6. **Sprint A1 Tarefa E só fecha o loop se o consultor *corrigir explicitamente* via endpoint.** Se ele simplesmente avança o caso e nunca toca em demand_type, o sistema não tem como saber se "não corrigiu porque estava certo" ou "não corrigiu porque o caso ainda nem chegou na hora de classificar". O denominador da `accuracy_overall` fica enviesado para casos onde o consultor *intervém*. Não é bloqueador, mas afeta interpretação.

---

## (d) Proposta de execução

**Ordem recomendada:** **A → C → D → B → E** (alteração proposital sobre a ordem alfabética e sobre o paralelismo sugerido na linha 380 do prompt).

**Justificativa:**
- **A primeiro.** Toca `BaseAgent`, é a base. Mergeia primeiro para evitar conflito.
- **C antes de B.** Tarefa C cria `PecaJuridicaOutput.legal_citations: list[CitationRef]`. Tarefa B produz `Citation` que **pode** ser o mesmo tipo (`CitationRef`). Fazer C primeiro me dá o tipo canônico a usar em B; fazer na ordem inversa eu invento um `Citation` em B e tenho que renomear/realinhar em C.
- **D antes de B.** Tarefa D não conflita com B, mas é totalmente isolada (modelos novos + endpoints read-only). Posso entregar fechada e sem risco.
- **B depois.** Mexe no `RedatorAgent` (igual A). Fica no fim para não conflitar com A no merge.
- **E por último.** Depende de uma decisão arquitetural (divergência #4) que precisa de input humano antes de implementar.

| Tarefa | Esforço | Dependência |
|---|---|---|
| A — Skills infra | M | só depende de `BaseAgent` |
| C — StageOutput Pydantic + 3 schemas | S/M | independente |
| D — Modelos `RegulatoryDiagnosis`/`RegulatoryIssue` + 3 endpoints read-only | M/L | só Alembic + FastAPI |
| B — Citation evaluator + integração `RedatorAgent` | S/M | depende de A (merge) e idealmente de C (tipo `CitationRef`) |
| E — Feedback loop classificação | M | **bloqueada** até decisão sobre captura (commit vs update posterior do `Process.demand_type`) |

**Sugestão de partição alternativa:** dividir **Tarefa D** em D1 (modelos + migration + testes de modelo) e D2 (3 endpoints REST + testes de API). Isso permite mergear D1 imediatamente depois de A, e D2 só quando o consumo for óbvio. Vale considerar.

**Sequenciamento prático sugerido:**
```
A → C (paralelo) → D1 → D2 → B → E (após decisão sobre #4)
```

---

## Step 3 — Perguntas em aberto (impacto explícito)

1. **`AIJob.result` em vez de `output_data`?** Se sim, sigo com `result["citation_issues"]` em B e `result` recebendo o `StageOutputBase.model_dump()` em C. Se você quer adicionar coluna `output_data` separada, isso vira mini-Tarefa C0 (migration + ajustes em `_complete_job`).
2. **Endpoint da Tarefa E é `/commit` (real) ou criar um novo `/confirm`?** Se `/commit`: instrumento o hook lá. Se `/confirm`: crio endpoint novo (mais código, dois pontos de captura).
3. **Captura da correção (divergência #4):** opção A — instrumentar atualização posterior do `Process.demand_type` (mais fiel ao fluxo CAM1-003 Opção B); opção B — instrumentar a edição em `IntakeDraft.form_data["demand_type"]` antes do commit; opção C — endpoint dedicado `/correct` independente de fluxo. Cada opção muda a tabela e os endpoints. Sem isso, **não posso começar Tarefa E**.
4. **Tabela associativa `regulatory_diagnosis_issues` (N-N) é necessária?** Se sim, sigo com a estrutura sugerida pelo prompt. Se não (uma issue só pertence a um diagnóstico/property), faço FK direta `RegulatoryIssue.diagnosis_id` nullable + `property_id` obrigatório. Resposta muda 1 migration + a query do endpoint.
5. **Naming do Pydantic schema (Tarefa C)** — manter `StageOutputBase` (colide visualmente com `app/models/stage_output.StageOutput` no autocompletar) ou renomear para `StageOutputDTO` / `StageOutputContent`? Eu prefiro `StageOutputContent` por ser semanticamente mais preciso (é o conteúdo do `content_data` JSONB), mas é decisão de estilo. Resposta muda só o nome.
6. **Migrar para Alembic em testes ou manter `create_all` (divergência #6)?** Conforme está, o teste de Tarefa D fica "manual" para migration up/down (rodar `alembic upgrade head` no host antes de pytest). Aceitável? Se quiser teste programático de migration, requer pequeno utilitário em conftest ou um conftest auxiliar.
7. **Sprint A2 e A3 (referidas no encerramento) já estão delineadas?** Se sim, vale ler antes de definir contratos em A1 que vão refletir lá. Se não, sigo com os contratos enxutos descritos no prompt.

---

## Step 4 — PARO aqui

Não vou tocar em código de produção até receber sinal verde explícito (ex.: "ok, começa pela Tarefa A com a ordem A→C→D→B→E proposta", ou correções específicas).

As perguntas 1, 2, 3, 4, 5 acima precisam de resposta antes da execução. As perguntas 6 e 7 são preferíveis mas posso seguir com defaults razoáveis se você priorizar velocidade.
