# Sprint -1 — Faxina (2026-04-23)

**Status:** ✅ Concluída
**Commit-base:** `3b27516` (Sprint R)
**Escopo:** 4 bugs/dívidas que invalidavam decisões arquiteturais já tomadas.

---

## Resumo

| Tarefa | Ação | Estado |
|---|---|---|
| A | Ativar Gemini de verdade (health-check + testes de model list) | ✅ |
| B | Enforce `AI_MAX_COST_PER_JOB_USD` com fail-fast e preservação de auditoria | ✅ |
| C | Corrigir bug do filtro `demand_type` em `search_legislation` | ✅ |
| D | `Document.extracted_text` + `extracted_at` (migration + cache no Extrator) | ✅ |

**Validação do marco:**
- Baseline antes da Sprint: 28 failed / 137 passed.
- Depois da Sprint: 27 failed / 155 passed — **18 testes novos, zero regressão**.
- As 27 falhas remanescentes são todas pré-existentes (auth, dashboard, pdf_generator, e2e). Fora do escopo deste ciclo.
- Lint dos arquivos tocados: limpo (único erro restante `B027` em `BaseAgent.validate_preconditions` é pré-existente e fora do escopo).

---

## A — Health-check Gemini

**Diagnóstico:** 100% dos $0.0035 gastos nos últimos 18 dias foram em `gpt-4o-mini` apesar da Sprint O ter definido Gemini como default do agente `legislacao`. Causa: `GEMINI_API_KEY` vazia no `.env` e fallback chain caindo para OpenAI silenciosamente.

**Implementação:**
- [`app/main.py`](../../app/main.py) — função `_check_ai_provider_contracts()` chamada no warm-up. Loga `WARNING` no boot quando `LEGISLATION_USE_GEMINI_DEFAULT=True` mas `GEMINI_API_KEY` está vazio. Mensagem: `[startup] Sprint O contract violated: ...`.
- [`.env.example`](../../.env.example) — documentado formato das 3 API keys com links para consoles (OpenAI, Google AI Studio, Anthropic) e a flag `LEGISLATION_USE_GEMINI_DEFAULT=true` explícita.
- [`tests/core/test_ai_gateway.py`](../../tests/core/test_ai_gateway.py) — 4 testes do `_build_model_list`:
  - Ordem default OpenAI → Gemini → Claude com as 3 keys presentes.
  - Gemini lidera quando `AI_DEFAULT_MODEL=gemini/...`.
  - Keys ausentes são removidas.
  - Sem nenhuma key: retorna o modelo default como placeholder.

---

## B — Enforce `AI_MAX_COST_PER_JOB_USD`

**Diagnóstico:** `settings.AI_MAX_COST_PER_JOB_USD=0.10` estava declarado mas não enforçado no gateway. Um job mal formatado contra Gemini (2M tokens de janela) podia custar $1–2.

**Implementação:**
- [`app/core/ai_gateway.py`](../../app/core/ai_gateway.py):
  - Após `litellm.completion_cost(...)`, compara `cost > settings.AI_MAX_COST_PER_JOB_USD` e levanta `AIGatewayError` com log `ERROR`.
  - Guarda só dispara quando `cost > 0` e `max_per_job > 0` (provider sem tabela de preço retorna `0.0` e o horário/mensal cobrem o risco).
  - `AIGatewayError` ganhou campos `cost_usd`, `tokens_in`, `tokens_out`, `model_used` para auditoria.
  - **Fail-fast:** novo `except AIGatewayError: raise` antes do `except Exception` evita que o fallback chain tente o próximo provider após cost_exceeded.
- [`app/agents/base.py`](../../app/agents/base.py) — `_fail_job` detecta `AIGatewayError` e preserva cost/tokens/model no registro `AIJob` antes de persistir `status=failed`. Exceções comuns não sobrescrevem campos prévios.
- Testes:
  - [`tests/core/test_ai_gateway.py`](../../tests/core/test_ai_gateway.py): 3 cenários — bloqueia job caro, libera job barato, ignora quando cost=0.
  - [`tests/agents/test_base_agent_cost_limit.py`](../../tests/agents/test_base_agent_cost_limit.py): 2 cenários — cost_exceeded preserva métricas, exceção comum não sobrescreve cost.

---

## C — Filtro `demand_type` no `search_legislation`

**Diagnóstico:** O parâmetro `demand_type` aparecia na assinatura de `search_legislation()` mas nunca era aplicado na query. Invalidava a Sprint 0 inteira (retrieval de legislação por demanda).

**Implementação:**
- [`app/services/legislation_service.py`](../../app/services/legislation_service.py):
  ```python
  if demand_type:
      q = q.filter(
          cast(LegislationDocument.demand_types, JSONB).contains([demand_type])
      )
  ```
- Regra: docs com `demand_types=NULL` ficam **fora** do filtro quando `demand_type` é especificado (prioriza diploma especializado sobre genérico).
- [`tests/services/test_legislation_service.py`](../../tests/services/test_legislation_service.py): 4 cenários — filtro exato, sem filtro retorna tudo (incluindo NULL), NULL é excluído com filtro ativo, combina com filtro UF.

---

## D — `Document.extracted_text` + cache no Extrator

**Diagnóstico:** `ExtratorAgent.execute()` fazia `getattr(doc, "extracted_text", "")` — a coluna **não existia** no model. Bug silencioso só porque o fluxo sempre passava `text` em metadata.

**Implementação:**
- Migration [`a9c3e5f7b1d2_sprint_minus1_document_extracted_text`](../../alembic/versions/a9c3e5f7b1d2_sprint_minus1_document_extracted_text.py):
  - `documents.extracted_text` (Text, nullable)
  - `documents.extracted_at` (DateTime, nullable)
  - Aditiva, sem backfill.
- [`app/models/document.py`](../../app/models/document.py) — colunas adicionadas com comentário de origem.
- [`app/agents/extrator.py`](../../app/agents/extrator.py):
  - Busca `Document` por `document_id` primeiro (quando fornecido).
  - Lê `doc.extracted_text` quando `text` não veio em metadata.
  - **Cache:** quando `text` vem em metadata e `doc.extracted_text` é NULL, persiste o texto + `extracted_at=now()` para próximas execuções (evita re-OCR).
- [`tests/agents/test_extrator_cache.py`](../../tests/agents/test_extrator_cache.py): 3 cenários — cacheia texto da metadata, lê do cache na segunda execução, erro claro quando não há cache nem texto.

---

## Validação do marco (comandos rodados)

```bash
# Migration no banco local (docker db ativo)
alembic upgrade head
# → aplicou Sprint R (f8b2c4d6e0a1) e Sprint -1 D (a9c3e5f7b1d2)

psql ... -c "\d documents" | grep extracted
# → extracted_text: text, extracted_at: timestamp with tz

# Testes do escopo
pytest tests/core/test_ai_gateway.py \
       tests/agents/test_base_agent_cost_limit.py \
       tests/agents/test_extrator_cache.py \
       tests/services/test_legislation_service.py \
       tests/agents/test_prompt_template_model.py --no-cov
# → 23 passed

# Suite completa (regressão)
pytest tests/ --no-cov
# → 155 passed, 27 failed (todas pré-existentes)
```

---

## Próximo passo

**Sprint 0 — Ingestão de Legislação.** Exige parada obrigatória para confirmar com a sócia a lista curada de diplomas (seção 2.1 do prompt). Os arquivos da pasta `legislacao/` já foram classificados em 3 grupos (pequenos DOCX → skills; médios PDF → ingestão 1:1; grandes → quebrar + MinIO).
