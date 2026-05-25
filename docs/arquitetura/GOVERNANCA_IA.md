# Governança de IA

**Documento:** Arquitetura · referência viva
**Estado:** atualizar a cada nova política, agente, ou provider
**Última revisão:** 2026-05-15

---

Política completa de IA aplicada no Regente Ambiental: como provedores são selecionados, como prompts são versionados, como custo é controlado, quando IA pode agir, quando exige revisão humana.

## Princípios materializados

Este documento operacionaliza os Princípios 1, 5, 6, 7 e 8 do manifesto.

| Princípio | Como vive aqui |
|---|---|
| 1 — IA propõe, humano decide | `AgentResult.requires_review=True` por default em peças formais |
| 5 — Multi-provider | LiteLLM com fallback ordenado |
| 6 — Schema antes de escala | `StageOutputContent` + derivados |
| 7 — Cost cap hard | `AI_MAX_COST_PER_JOB_USD` enforced |
| 8 — Skills procedurais | `app/skills/` carregadas pelo BaseAgent |

## AI Gateway

**Local:** `app/core/ai_gateway.py`

Camada única de contato com provedores. **Nenhum serviço chama provider diretamente** — princípio inegociável. Toda chamada passa pelo `complete()` do gateway.

### Provedores configurados

| Provider | Configuração | Default para |
|---|---|---|
| OpenAI | `OPENAI_API_KEY` em `.env` | Maioria dos agentes (`gpt-4o-mini`) |
| Gemini (Google) | `GEMINI_API_KEY` em `.env` | `LegislacaoAgent` (janela 1M-2M tokens) |
| Anthropic Claude | `ANTHROPIC_API_KEY` em `.env` | Fallback secundário |

### Fallback automático

Quando o provider primário falha (timeout, rate limit, erro do provider), o LiteLLM tenta o próximo. Ordem padrão: OpenAI → Gemini → Anthropic.

### Modelos por contexto

| Modelo | Uso | Por quê |
|---|---|---|
| `gpt-4o-mini` | Default geral (atendimento, redator, diagnostico, extrator) | Custo baixo, qualidade adequada para a maioria, PT-BR sólido |
| `gpt-4o` | Casos complexos com necessidade de raciocínio | Quando o `mini` falha em testes de qualidade |
| `gemini/gemini-2.0-flash` | `LegislacaoAgent` (corpus regulatório grande) | Janela 1M tokens, custo competitivo |
| `gemini/gemini-1.5-pro` | Fallback para contexto > 800K tokens | Janela 2M |
| Anthropic Claude (qualquer SKU) | Fallback secundário | Diversidade de risco |

Configuração default está em `.env` (`AI_DEFAULT_MODEL`, `AI_FALLBACK_MODEL`).

### Roteamento dinâmico por janela (`LegislacaoAgent`)

`app/agents/legislacao.py` detecta tamanho do contexto e roteia:

- Contexto ≤ 800K tokens → `gemini/gemini-2.0-flash` (mais rápido, mais barato)
- Contexto > 800K tokens → `gemini/gemini-1.5-pro` (janela maior)

Threshold é ajustável. Health check no boot loga WARNING se `LEGISLATION_USE_GEMINI_DEFAULT=true` sem `GEMINI_API_KEY` configurada.

### Resposta padrão (`AIResponse`)

Toda chamada retorna:

```python
@dataclass
class AIResponse:
    content: str            # texto gerado
    model_used: str         # ex: "gpt-4o-mini"
    tokens_in: int
    tokens_out: int
    cost_usd: float
    duration_ms: int
    provider: str           # "openai" | "gemini" | "anthropic"
```

Tudo persistido em `AIJob`. Falhas levantam `AIGatewayError` que **preserva** cost/tokens/model quando aplicável (auditoria de jobs bloqueados por cost cap).

## Cost cap — três camadas

### Camada 1 — Limite por job

`AI_MAX_COST_PER_JOB_USD` (default `$0.10`) é enforced em `ai_gateway.complete()`. Estoura → `AIGatewayError(cost_exceeded)` antes mesmo do request sair.

Override por chamada: `complete(..., max_cost_override_usd=0.50)` quando você sabe que a tarefa específica precisa de mais.

### Camada 2 — Limite por hora (por tenant)

`AI_HOURLY_COST_LIMIT_USD = 5.0` (hardcoded em `ai_gateway.py:48`) — soma de `AIJob.cost_usd` da última hora para o tenant. Estoura → `HTTPException 429`.

### Camada 3 — Orçamento mensal (por tenant)

`Tenant.ai_monthly_budget_usd` (override por tenant) ou `AI_BUDGET_USD_MONTHLY_PER_TENANT_DEFAULT` (default global). Janela: início do mês UTC até início do mês seguinte. Estoura → bloqueio com `HTTPException 429`.

Endpoint `GET /api/v1/agents/budget` retorna estado atual: gasto, teto, restante, % usado.

### Endurecimento adicional

Workers Celery também checam o budget antes de iniciar. Tarefa que estouraria orçamento marca-se como `skipped_budget` e emite alerta.

## Prompts versionados

**Modelo:** `PromptTemplate` (`app/models/prompt_template.py`)

Cada prompt tem:

- `name` (chave, ex: `redator_oficio_default`)
- `version` (int, auto-incremento)
- `tenant_id` (NULL = global, valor = override do tenant)
- `category` (`classify` | `extract` | `summarize` | `proposal` | etc.)
- `input_schema` (JSONB)
- `output_schema` (JSONB)
- `system_prompt`, `user_prompt_template`
- `is_active` (bool)

### Hierarquia de resolução

Quando agente pede o prompt `X`:

1. Procura `tenant_id = <tenant>` e `name = X` e `is_active = true` (ordem: versão mais alta)
2. Se não encontra, procura `tenant_id IS NULL` e `name = X` (prompt global)
3. Se não encontra, cai no fallback hardcoded no `.py` do agente (sempre existe um)

### Cache

`app/services/prompt_service.py` cacheia in-process com TTL 60s. Prioriza tenant-specific sobre global. Atualização de prompt invalida cache automaticamente em até 60s.

### Editor de prompts via UI

**Status: cortado.** Decisão da sócia em 21/04. Prompts são editados via banco direto (admin) ou via migration. UI dedicada não entra no escopo agora.

## Skills procedurais

**Local:** `app/skills/<agente>/<dominio>.md`

Skills são arquivos Markdown com frontmatter YAML. Carregadas automaticamente pelo `BaseAgent.call_llm` quando o contexto bate.

### Estrutura de uma skill

```markdown
---
name: oficio_semad_go
applies_to:
  - agent: redator
    demand_type: [car, retificacao_car]
    doc_type: oficio
    uf: GO
---

# Ofício SEMAD-GO

[corpo da skill com instruções procedurais]
```

### Como o agente carrega skills

`BaseAgent.call_llm` chama `_load_skills_for_context(self)` que:

1. Lê `self.ctx.metadata` para descobrir `demand_type`, `doc_type`, `uf`, etc.
2. Casa contra cada `applies_to` no registry de skills
3. Concatena skills matched dentro do system prompt entre marcadores `<!-- skills:start -->` e `<!-- skills:end -->`

### Status hoje

Apenas placeholders `_template/SKILL.md`. Skills reais entram quando a sócia fornecer PDFs-gabarito (reunião 16/05). Lista priorizada:

1. `redator/oficio_semad_go.md`
2. `redator/memorial_car_sicar.md`
3. `redator/resposta_notificacao_semad.md`
4. `redator/prad.md`
5. `extrator/matricula_generica.md`
6. `extrator/car_sicar.md`

## Citation Evaluator

**Local:** `app/services/citation_evaluator.py`

Hook chamado **após** o LLM retornar resposta em agentes que citam normas (Redator, Legislacao, **Diagnóstico desde 2026-05-23**). Funciona em duas fases:

### Fase 1 — Extração

Regex multi-formato captura todas as citações no texto:
- `Lei nº 12.651/2012`, `Lei 12651/12`, `Lei Federal 12.651/2012`
- `Decreto N/AAAA`, `Resolução CONAMA N/AAAA`, `Instrução Normativa N/AAAA`
- Variações com/sem ano abreviado

Retorna lista de `CitationRef(kind, numero, ano, raw, ...)`.

### Fase 2 — Validação

Cada citação extraída é confrontada contra o `knowledge_catalog`:

- Se a norma **existe** na base → válida, `chunk_id` é vinculado
- Se a norma **não existe** → suspeita (citação possivelmente inventada)

### Comportamento ao detectar suspeita

- `AIJob.result["citation_issues"]` ganha lista das citações suspeitas
- A peça é marcada `requires_review = True` (independente de já estar marcada)
- Frontend mostra badge "Citações suspeitas" sobre a peça
- **Não bloqueia** o output — apenas sinaliza

Esse é o ponto onde o Regente cumpre o princípio "citação rastreável" do manifesto: cada lei citada precisa estar no banco; o que não estiver vira pendência humana.

## Quando IA pode agir automaticamente (sem revisão)

| Operação | Pode agir automaticamente |
|---|---|
| Cache de OCR (mesmo arquivo, mesmo hash) | ✅ |
| Re-indexação de `knowledge_catalog` ao ingerir novo diploma | ✅ |
| Cálculo de prazos pelo `vigia` (rules-based, sem LLM) | ✅ |
| Crawl de DOU/DOE (quando crawlers existirem) | ✅ (só ingere, não decide) |
| Filtro `demand_type` em busca legislativa | ✅ |
| Classificação inicial de demanda (Atendimento) | ⚠️ Propõe, consultor confirma |
| Extração de campos de documento | ⚠️ Propõe, consultor confirma (`requires_review=True`) |
| Diagnóstico técnico-regulatório | ❌ Sempre revisado |
| Geração de peça (PRAD, ofício, memorial, resposta a notificação) | ❌ Sempre revisada (`requires_review=True` hardcoded) |
| Avanço entre macroetapas | ❌ Consultor decide |
| Promoção de `demand_type` no Process | ❌ Consultor decide |

## Métricas e auditabilidade

Toda chamada IA gera:

1. **`AIJob`** — entidade persistida (cost, tokens, model, status, result)
2. **Métrica Prometheus** — `agent_executions_total{agent, status}`, `agent_execution_duration_seconds`, `agent_execution_cost_usd`
3. **Evento WebSocket** — `ai_job_completed` no canal do tenant (quando assíncrono)
4. **Log estruturado** — JSON com `trace_id`, `tenant_id`, `agent_name`, `cost_usd`

## Pendências e dívidas

1. ~~Skills reais não existem ainda~~ — **Primeira skill real escrita em 2026-05-23**: `app/skills/diagnostico/situacao_ambiental_imovel_rural/SKILL.md` (3 estágios: preliminar/consolidado/saneamento; 18 heurísticas; mapa de riscos com 7 categorias × 4 graus × 4 prioridades). 5 skills do Redator continuam aguardando reunião com a sócia.
2. ~~Citation evaluator só roda no Redator hoje~~ — **Expandido para o DiagnosticoAgent em 2026-05-23** (Fase 2 Onda 2, commit `5c4dd33`). Espelha o padrão do RedatorAgent: extrai citações de `situacao_geral + passivos + acoes + observacoes`, valida contra `legislation_context` da chain (`legislacao_aplicavel`, `normas_estaduais`, `rag_chunks_meta`), e popula `citation_total/issues/coverage_ratio/valid` no payload. Citações sem match ficam como suspeitas, não derrubam a execução.
3. **Override de prompts via UI cortado** — formalizar como ADR ([`../adr/`](../adr/)).
4. ~~MemPalace stub vivo em `app/agents/memory.py`~~ — **Já removido em commit `757b7de`** (Sprint Z). Gap A5 da auditoria fechado.
5. **`AI_HOURLY_COST_LIMIT_USD` ainda hardcoded** — migrar para config quando justificar.
6. ~~`AuditorImovelAgent` registrado mas sem chain~~ — **Resolvido em 2026-05-24** (PROMPT_3 Onda B). Agente entrou na chain `diagnostico_completo` (`extrator → auditor_imovel → legislacao → diagnostico`) via `NON_BLOCKING_REVIEW_AGENTS` — `requires_review=True` do auditor não interrompe a chain (critério: o output é INSUMO `chain_data`, não produto final).
7. ~~Diagnóstico não consome findings do auditor~~ — **Resolvido em 2026-05-25** (PROMPT_4 Onda A, commit `f93b4b4`). `DiagnosticoAgent._consume_auditor_findings()` lê `chain_data["auditor_imovel"]["findings_raw"]` e os incorpora como "primeiro movimento": cada finding vira `Divergencia` (matriz de cruzamento) + `Risco` com `grau` 4-níveis preservado (`critico` → `critico_impeditivo_potencial`, **NÃO** colapsa em "alto" no payload). `nivel_risco_geral` derivado do pior grau dos findings. Path rules-based também consome (auditor é fonte independente do LLM).
8. ~~Princípio 1 sem ato de assinatura~~ — **Camada 1 resolvida em 2026-05-25** (PROMPT_4 Onda B, commit `c74ff2e`). `PATCH /api/v1/processes/{id}/diagnoses/{version}/validate` grava `validated_by_user_id` + `validated_at` + AuditLog hash chain SHA-256. 409 ao revalidar (idempotência explícita). **Camada 2** (5 botões P4 — decisão por alerta crítico) ainda **aberta**, depende da remodelagem do `RegulatoryIssue` (PROMPT_5).
9. **`RegulatoryIssue` ainda colapsa 4→3 níveis** na persistência via `_GRADE_TO_SEVERITY`. O payload do Diagnóstico já preserva os 4, mas a persistência só vai para 4 níveis no PROMPT_5 (remodelagem: `familia` + `codigo_alerta` + `severity` 4 níveis). Dívida #4 do `REGISTRO_DIVIDAS.md`.

## Próximas leituras

- [`MODELO_DE_DADOS.md`](./MODELO_DE_DADOS.md) — schema do `AIJob`, `PromptTemplate`, `knowledge_catalog`
- [`BASE_REGULATORIA.md`](./BASE_REGULATORIA.md) — detalhe da base que o citation evaluator confronta
- [`OBSERVABILIDADE.md`](./OBSERVABILIDADE.md) — métricas e logs gerados pelos agentes
