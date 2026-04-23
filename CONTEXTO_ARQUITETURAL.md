# CONTEXTO ARQUITETURAL — Amigão do Meio Ambiente

**Gerado em:** 2026-04-23
**Commits recentes:** `c33c4ad` (refino UI/Kanban) → `3b27516` (Sprint R: budget mensal por tenant)
**Stack:** FastAPI + SQLAlchemy 2 + PostgreSQL 15 + PostGIS 3.3 + Redis + Celery + MinIO + litellm + MemPalace
**Foco deste documento:** (1) expansão do MemPalace com recall ativo, (2) RAG de casos com pgvector, (3) otimização de custo de tokens.

> ✅ **Dados *live* incluídos:** o Postgres `amigao_db` estava acessível durante a extração (PostgreSQL 15.4 via imagem `postgis/postgis:15-3.3`, porta 5433). Todas as queries da seção 4, 6, 7 e 8 foram **executadas em produção** e os resultados aparecem inline abaixo. O MemPalace local (SQLite Chroma + SQLite KG) também pôde ser lido.

---

## 1. AI Gateway

### 1.1 Conteúdo completo de `app/core/ai_gateway.py`

```python
"""
AI Gateway — Sprint 5 (Wave 2)

Gateway multi-provider via litellm com:
- Fallback automático entre providers (OpenAI → Gemini → Claude)
- Registro de custo e tokens por chamada
- Timeout e proteção de custo máximo por job
- Modo degradado quando IA não está configurada (retorna None)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AIResponse:
    content: str
    model_used: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    duration_ms: int
    provider: str


@dataclass
class AIGatewayError(Exception):
    message: str
    last_error: Optional[str] = None


AI_HOURLY_COST_LIMIT_USD = 5.0  # limite padrão por tenant por hora


def check_tenant_cost_limit(
    tenant_id: int,
    db: "Session",
    limit_usd: float = AI_HOURLY_COST_LIMIT_USD,
) -> float:
    """Retorna custo acumulado na última hora. Levanta HTTPException se exceder limite."""
    from datetime import UTC, datetime, timedelta

    from fastapi import HTTPException
    from sqlalchemy import func

    from app.models.ai_job import AIJob

    one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
    total_cost = (
        db.query(func.coalesce(func.sum(AIJob.cost_usd), 0.0))
        .filter(
            AIJob.tenant_id == tenant_id,
            AIJob.created_at >= one_hour_ago,
        )
        .scalar()
    )
    if total_cost >= limit_usd:
        raise HTTPException(
            status_code=429,
            detail=f"Limite de custo de IA excedido: ${total_cost:.2f}/${limit_usd:.2f} na última hora",
        )
    return float(total_cost)


def _month_window_utc() -> "tuple[datetime, datetime]":
    """Retorna (início do mês UTC, início do próximo mês UTC)."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        next_start = start.replace(year=start.year + 1, month=1)
    else:
        next_start = start.replace(month=start.month + 1)
    return start, next_start


def get_tenant_monthly_budget(tenant_id: int, db: "Session") -> float:
    """Retorna o teto mensal vigente para o tenant (override > default global)."""
    from app.core.config import settings
    from app.models.tenant import Tenant

    tenant_budget = (
        db.query(Tenant.ai_monthly_budget_usd).filter(Tenant.id == tenant_id).scalar()
    )
    if tenant_budget is not None:
        return float(tenant_budget)
    return float(settings.AI_BUDGET_USD_MONTHLY_PER_TENANT_DEFAULT)


def get_tenant_monthly_spend(tenant_id: int, db: "Session") -> float:
    """Retorna custo acumulado de IA do tenant no mês corrente (UTC)."""
    from sqlalchemy import func

    from app.models.ai_job import AIJob

    start, next_start = _month_window_utc()
    total = (
        db.query(func.coalesce(func.sum(AIJob.cost_usd), 0.0))
        .filter(
            AIJob.tenant_id == tenant_id,
            AIJob.created_at >= start,
            AIJob.created_at < next_start,
        )
        .scalar()
    )
    return float(total or 0.0)


def check_tenant_monthly_budget(tenant_id: int, db: "Session") -> float:
    """
    Valida o teto mensal de IA do tenant. Retorna o custo acumulado no mês.
    Levanta HTTPException 429 se estourou. limit=0 ⇒ ilimitado.
    """
    from fastapi import HTTPException

    limit = get_tenant_monthly_budget(tenant_id, db)
    if limit <= 0:
        return get_tenant_monthly_spend(tenant_id, db)

    spent = get_tenant_monthly_spend(tenant_id, db)
    if spent >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Orçamento mensal de IA excedido: ${spent:.2f}/${limit:.2f} no mês corrente",
        )
    return spent


def _build_model_list(settings) -> list[tuple[str, str]]:
    """Monta lista de (modelo, api_key) em ordem de preferência baseado nas chaves disponíveis."""
    candidates: list[tuple[str, str, str]] = [
        (settings.OPENAI_API_KEY, settings.AI_DEFAULT_MODEL, settings.OPENAI_API_KEY),
        (settings.GEMINI_API_KEY, settings.AI_FALLBACK_MODEL, settings.GEMINI_API_KEY),
        (settings.ANTHROPIC_API_KEY, "claude-haiku-4-5-20251001", settings.ANTHROPIC_API_KEY),
    ]
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for key, model, api_key in candidates:
        if key and model not in seen:
            seen.add(model)
            result.append((model, api_key))
    return result or [(settings.AI_DEFAULT_MODEL, "")]


def complete(
    prompt: str,
    *,
    system: str = "",
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> AIResponse:
    """
    Envia um prompt para o LLM e retorna AIResponse.

    Tenta os modelos em ordem de fallback. Lança AIGatewayError se todos falharem.
    Deve ser chamado somente quando settings.ai_configured == True.
    """
    # Import tardio para evitar erro de import quando IA desabilitada
    import litellm  # noqa: PLC0415

    from app.core.config import settings

    models: list[tuple[str, str]] = [(model, "")] if model else _build_model_list(settings)
    _max_tokens = max_tokens or settings.AI_MAX_TOKENS
    _temperature = temperature if temperature is not None else settings.AI_TEMPERATURE
    _timeout = settings.AI_TIMEOUT_SECONDS

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_error: Optional[str] = None
    for attempt_model, api_key in models:
        try:
            t0 = time.monotonic()
            response = litellm.completion(
                model=attempt_model,
                messages=messages,
                max_tokens=_max_tokens,
                temperature=_temperature,
                timeout=_timeout,
                api_key=api_key or None,
            )
            elapsed_ms = int((time.monotonic() - t0) * 1000)

            content = response.choices[0].message.content or ""
            usage = response.usage or {}
            tokens_in = getattr(usage, "prompt_tokens", 0) or 0
            tokens_out = getattr(usage, "completion_tokens", 0) or 0

            # litellm calcula custo automaticamente quando disponível
            try:
                cost = litellm.completion_cost(completion_response=response) or 0.0
            except Exception:
                cost = 0.0

            provider = attempt_model.split("/")[0] if "/" in attempt_model else attempt_model.split("-")[0]

            logger.info(
                "ai_gateway.complete model=%s tokens_in=%d tokens_out=%d cost_usd=%.6f ms=%d",
                attempt_model, tokens_in, tokens_out, cost, elapsed_ms,
            )

            return AIResponse(
                content=content,
                model_used=attempt_model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost,
                duration_ms=elapsed_ms,
                provider=provider,
            )

        except Exception as exc:
            last_error = str(exc)
            logger.warning("ai_gateway.complete fallback model=%s error=%s", attempt_model, exc)
            continue

    raise AIGatewayError(
        message=f"Todos os providers falharam. Último erro: {last_error}",
        last_error=last_error,
    )
```

### 1.2 Variáveis de ambiente relacionadas a AI/LLM (grep em `app/core/config.py`)

```python
# IA / LLM (Wave 2 — Sprint 5)
AI_ENABLED: bool = False
OPENAI_API_KEY: str = ""
GEMINI_API_KEY: str = ""
ANTHROPIC_API_KEY: str = ""
AI_DEFAULT_MODEL: str = "gpt-4o-mini"
AI_FALLBACK_MODEL: str = "gemini/gemini-1.5-flash"
AI_MAX_TOKENS: int = 2048
AI_TEMPERATURE: float = 0.2
AI_TIMEOUT_SECONDS: float = 30.0
# Custo máximo por job (USD) — proteção contra prompt injection gigante
AI_MAX_COST_PER_JOB_USD: float = 0.10
# Sprint R — teto mensal padrão por tenant (USD). 0 = ilimitado.
# Override por tenant em Tenant.ai_monthly_budget_usd.
AI_BUDGET_USD_MONTHLY_PER_TENANT_DEFAULT: float = 0.0

# Legislação — Gemini context loading (sem chunking)
LEGISLATION_MAX_CONTEXT_TOKENS: int = 500_000
LEGISLATION_MAX_RESULTS: int = 20

# Claude API (agente regulatório)
CLAUDE_LEGAL_MODEL: str = "claude-sonnet-4-20250514"
CLAUDE_LEGAL_MAX_TOKENS: int = 4096
CLAUDE_LEGAL_TEMPERATURE: float = 0.1

# Gemini (context loading de legislação)
GEMINI_LEGAL_MODEL: str = "gemini/gemini-2.0-flash"

# Sprint O (2026-04-21) — Gemini é o provider default do agente legislação
LEGISLATION_USE_GEMINI_DEFAULT: bool = True
```

### 1.3 Valores default hardcoded

| Constante | Valor | Local |
|---|---|---|
| `AI_HOURLY_COST_LIMIT_USD` | `5.0` | `app/core/ai_gateway.py:38` |
| `AI_MAX_COST_PER_JOB_USD` | `0.10` | `app/core/config.py:105` |
| `AI_BUDGET_USD_MONTHLY_PER_TENANT_DEFAULT` | `0.0` (ilimitado) | `app/core/config.py:108` (Sprint R) |
| `AI_MAX_TOKENS` | `2048` | `app/core/config.py:101` |
| `AI_TEMPERATURE` | `0.2` | `app/core/config.py:102` |
| `AI_TIMEOUT_SECONDS` | `30.0` | `app/core/config.py:103` |
| `LEGISLATION_MAX_CONTEXT_TOKENS` | `500_000` | `app/core/config.py:111` |
| `LEGISLATION_MAX_RESULTS` | `20` | `app/core/config.py:112` |
| `CLAUDE_LEGAL_MAX_TOKENS` | `4096` | `app/core/config.py:116` |
| `CLAUDE_LEGAL_TEMPERATURE` | `0.1` | `app/core/config.py:117` |

### 1.4 Sanidade sobre `AI_FALLBACK_MODEL`

O `docker-compose.yml` atualmente define `AI_FALLBACK_MODEL=gemini/gemini-1.5-flash` como default (linhas 103 e 163), mas as rotas mais críticas (agente legislação) usam `GEMINI_LEGAL_MODEL=gemini/gemini-2.0-flash` via override. As duas convivem.

### 1.5 BaseAgent — template method (cost check integrado)

```python
# app/agents/base.py:121-137
def run(self) -> AgentResult:
    """
    Ciclo de vida completo do agente:
    1. Verifica limite de custo do tenant
    2. Valida pre-condicoes
    3. Cria AIJob em status running
    4. Executa logica do agente (subclass)
    5. Valida output
    6. Persiste AIJob como completed
    7. Emite evento
    """
    from app.agents.events import emit_agent_event  # noqa: PLC0415
    from app.core.metrics import record_agent_execution  # noqa: PLC0415

    # 1. Cost check (por hora) + Sprint R (teto mensal por tenant)
    check_tenant_cost_limit(self.ctx.tenant_id, self.ctx.session)
    check_tenant_monthly_budget(self.ctx.tenant_id, self.ctx.session)
```

---

## 2. Estrutura dos Agentes

Os 10 agentes herdam de `BaseAgent` em [app/agents/base.py:103](app/agents/base.py#L103). Todos usam `litellm` via `complete()` do gateway (que faz fallback automático OpenAI → Gemini → Claude Haiku conforme as chaves disponíveis no `.env`). **Apenas o agente `legislacao` sobrescreve o provider preferido** (Gemini 2.0 Flash) e cai pra Claude Sonnet via SDK direto quando Gemini não está configurado. **Tools/Functions OpenAI-style NÃO são usadas** — todos os agentes esperam saída JSON parseada por `OutputValidationPipeline.parse_llm_json`. Cada agente tem um atributo `name`, `description`, `job_type`, `prompt_slugs` e `palace_room` declarados como classe.

### 2.1 AtendimentoAgent

- **Arquivo:** `app/agents/atendimento.py`
- **Modelo LLM padrão:** gateway (OpenAI gpt-4o-mini com fallback)
- **max_tokens:** não especifica → usa `AI_MAX_TOKENS=2048`
- **temperature:** não especifica → usa `AI_TEMPERATURE=0.2`
- **Disparo:**
  - Automático: `POST /api/v1/intake/create-case` dispara async se `description ≥10 chars`
  - Chain `intake` (definida em `orchestrator.py:25`)
  - `POST /agents/run` manual

**System prompt (fallback hardcoded):**
```python
"Voce e um especialista em regularizacao ambiental rural brasileira. "
"Classifique a demanda e retorne JSON estruturado."
```

**User prompt template:**
```python
"Classifique esta demanda ambiental:\n"
"DESCRICAO: {description}\nCANAL: {channel}\nURGENCIA: {urgency}\n"
"Retorne apenas o JSON."
```

**Nota:** na prática, `AtendimentoAgent` delega para `app/services/llm_classifier.py` que tem seu próprio system prompt (mais rico). O system prompt do serviço está em `_FALLBACK_SYSTEM_PROMPT` em llm_classifier.py:33-56:

```python
_FALLBACK_SYSTEM_PROMPT = """Voce e um especialista em regularizacao ambiental rural brasileira.
Sua tarefa e classificar a demanda de um cliente rural e retornar um JSON estruturado.

Tipos de demanda validos:
- car: Cadastro Ambiental Rural
- retificacao_car: Retificacao de CAR
- licenciamento: Licenciamento Ambiental
- regularizacao_fundiaria: Regularizacao Fundiaria
- outorga: Outorga de Uso de Agua
- defesa: Defesa Administrativa / Auto de Infracao
- compensacao: Compensacao / PRAD
- exigencia_bancaria: Exigencia Bancaria / Credito Rural
- misto: Demanda Mista
- nao_identificado: Nao Identificado

Retorne APENAS um JSON valido com esta estrutura:
{
  "demand_type": "<tipo>",
  "confidence": "high" | "medium" | "low",
  "diagnosis": "<texto de 2-4 frases explicando a situacao>",
  "urgency": null | "alta" | "critica",
  "relevant_agencies": ["SEMA", "IBAMA", ...],
  "next_steps": ["passo 1", "passo 2", ...]
}"""
```

### 2.2 ExtratorAgent

- **Arquivo:** `app/agents/extrator.py`
- **Modelo LLM padrão:** gateway (OpenAI gpt-4o-mini com fallback)
- **max_tokens:** não especifica
- **temperature:** não especifica
- **Disparo:**
  - Automático em `POST /documents/confirm-upload` (`matricula`, `car`, `ccir`, `auto_infracao`, `licenca`)
  - Automático em `/intake/drafts/{id}/import-documents`
  - Chains: `diagnostico_completo`, `enquadramento_regulatorio`

**System prompt (fallback):**
```python
"Voce e um especialista em documentos fundiarios e ambientais brasileiros. "
"Extraia os campos solicitados e retorne APENAS um JSON valido."
```

**Nota:** delega para `app/services/document_extractor.py` que tem prompts por tipo de documento. System prompt do serviço:

```python
_FALLBACK_SYSTEM_PROMPT = """Voce e um especialista em documentos fundiarios e ambientais brasileiros.
Extraia os campos solicitados do texto do documento e retorne APENAS um JSON valido.
Para campos nao encontrados, use null.
Inclua um campo "confidence" por campo extraido: "high" | "medium" | "low".
"""
```

User prompts por doc_type (matricula, car, ccir, auto_infracao, licenca, outorga) ficam em `_FALLBACK_DOC_PROMPTS` com JSON schema pronto para preencher.

### 2.3 DiagnosticoAgent

- **Arquivo:** `app/agents/diagnostico.py`
- **Modelo LLM padrão:** gateway (OpenAI/fallback) — **não especifica** model no `call_llm`
- **max_tokens:** não especifica
- **temperature:** não especifica
- **Disparo:**
  - Chain `diagnostico_completo` (extrator → legislacao → diagnostico)
  - Chain `gerar_proposta` (diagnostico → orcamento)
  - Transição de macroetapa `diagnostico_tecnico` em `POST /processes/{id}/advance-macroetapa`
  - `POST /agents/run` manual
- **Usa MemPalace recall ativo** (único junto com `legislacao`):
  ```python
  # app/agents/diagnostico.py:47-51
  recall_query = f"diagnostico {prop.get('state', '')} {prop.get('biome', '')} {process_data.get('process', {}).get('demand_type', '')}"
  recall = self.recall_memory(recall_query)
  if recall.get("recent_diary"):
      entries = [e.get("entry", "") if isinstance(e, dict) else str(e) for e in recall["recent_diary"][:3]]
      memory_hint = "\n".join(f"- {e}" for e in entries if e)
  ```

**System prompt (fallback):**
```python
"Voce e um consultor ambiental senior especializado em propriedades rurais brasileiras. "
"Analise a situacao do imovel e forneca um diagnostico completo com sugestoes de remediacao. "
"Retorne APENAS JSON valido com: situacao_geral (str), passivos_identificados (list[str]), "
"acoes_remediacao (list[str]), prioridade_acoes (list[str]), risco_estimado (baixo|medio|alto), "
"observacoes (str)."
```

### 2.4 LegislacaoAgent

- **Arquivo:** `app/agents/legislacao.py`
- **Modelo LLM padrão:** **Gemini 2.0 Flash** (`gemini/gemini-2.0-flash`) — override via `LEGISLATION_USE_GEMINI_DEFAULT=True` (Sprint O). Fallback: Claude Sonnet via SDK direto.
- **max_tokens:** `settings.CLAUDE_LEGAL_MAX_TOKENS = 4096`
- **temperature:** não especifica no call_llm (usa default do gateway 0.2); Claude SDK usa `CLAUDE_LEGAL_TEMPERATURE=0.1`
- **Disparo:**
  - Chains: `diagnostico_completo`, `enquadramento_regulatorio`, `analise_regulatoria`
  - Transição macroetapa `caminho_regulatorio`
  - `POST /agents/run` manual
- **Usa MemPalace recall ativo:**
  ```python
  # app/agents/legislacao.py:73-79
  recall = self.recall_memory(f"legislacao {demand_type} {state}")
  if recall.get("recent_diary"):
      entries = [...]
      memory_context = "\n".join(...)
  if recall.get("search_results"):
      hits = [...]
      memory_context += "\n" + "\n".join(...)
  ```
- **Lógica de provider:**
  ```python
  # app/agents/legislacao.py:102-120
  large_context = bool(legislation_context and len(legislation_context) > 100_000)
  use_gemini = (
      large_context
      or (settings.LEGISLATION_USE_GEMINI_DEFAULT and bool(settings.GEMINI_API_KEY))
  )
  if use_gemini:
      response = self.call_llm(user_prompt, system=system_prompt,
                                model=settings.GEMINI_LEGAL_MODEL,
                                max_tokens=settings.CLAUDE_LEGAL_MAX_TOKENS)
  elif settings.ANTHROPIC_API_KEY:
      response = self._call_claude(user_prompt, system=system_prompt)
  else:
      response = self.call_llm(user_prompt, system=system_prompt)
  ```

**System prompt (fallback):**
```python
"Voce e um advogado ambiental senior brasileiro especialista em enquadramento regulatorio.\n\n"
"Seu trabalho e analisar um caso concreto de consultoria ambiental e determinar:\n"
"1. O caminho regulatorio mais provavel\n"
"2. O orgao competente\n"
"3. A sequencia de etapas regulatorias\n"
"4. A legislacao aplicavel com citacoes especificas\n"
"5. Os riscos juridicos/ambientais\n"
"6. Os documentos necessarios\n"
"7. Estimativa de prazos\n\n"
"Quando BASE LEGISLATIVA for fornecida abaixo, use-a como fonte primaria.\n"
"Cite artigos, paragrafos e incisos especificos.\n\n"
"Retorne APENAS JSON valido com os campos:\n"
"caminho_regulatorio (str), orgao_competente (str), "
"etapas (list[{ordem, titulo, descricao, prazo_estimado_dias, orgao}]), "
"legislacao_aplicavel (list[{identificador, titulo, relevancia}]), "
"riscos (list[{descricao, severidade, mitigacao}]), "
"documentos_necessarios (list[str]), "
"prazos_estimados ({total_dias, fase_documental_dias, fase_protocolo_dias, fase_analise_orgao_dias}), "
"confianca (baixa|media|alta), justificativa (str), recomendacoes (list[str])."
```

### 2.5 OrcamentoAgent

- **Arquivo:** `app/agents/orcamento.py`
- **Modelo LLM padrão:** gateway
- **max_tokens:** não especifica
- **temperature:** não especifica
- **Disparo:**
  - Chain `gerar_proposta` (diagnostico → orcamento)
  - Transição macroetapa `orcamento_negociacao`
  - `POST /agents/run` manual
- **MemPalace:** **só escrita, sem recall** (passivo)

**System prompt (fallback):**
```python
"Voce e um gestor comercial de consultoria ambiental brasileira. "
"Gere orcamentos detalhados com escopo, valores e prazos realistas. "
"Retorne APENAS JSON valido com: complexity (baixa|media|alta), "
"scope_items (list[{description, estimated_hours}]), "
"suggested_value_min (float), suggested_value_max (float), "
"estimated_days (int), payment_terms (str), notes (str), "
"confidence (high|medium|low)."
```

### 2.6 RedatorAgent

- **Arquivo:** `app/agents/redator.py`
- **Modelo LLM padrão:** gateway
- **max_tokens:** **`4096` (especifica)**
- **temperature:** não especifica
- **Disparo:**
  - Chain `gerar_documento`
  - `POST /agents/run` manual (esperando `metadata.document_template` em `{prad, memorial, oficio, proposta, resposta_notificacao, contrato, comunicacao}`)
- **MemPalace:** só escrita, sem recall

**System prompt (fallback):**
```python
"Voce e um redator tecnico especializado em documentos ambientais e fundiarios brasileiros. "
"Gere documentos formais, tecnicos e bem fundamentados. "
"Use linguagem tecnica apropriada e formalidade adequada ao tipo de documento. "
"Estruture bem o documento com titulos, secoes e paragrafos claros."
```

### 2.7 FinanceiroAgent

- **Arquivo:** `app/agents/financeiro.py`
- **Modelo LLM padrão:** gateway (e **só roda LLM se `metadata.generate_insights=True`**; caso contrário retorna só agregação SQL)
- **max_tokens:** não especifica
- **temperature:** não especifica
- **Disparo:**
  - Chain `analise_financeira`
  - `POST /agents/run` manual
- **MemPalace:** só escrita, sem recall

**System prompt (fallback):**
```python
"Voce e um analista financeiro de consultoria ambiental. "
"Analise os dados financeiros e forneca insights e recomendacoes. "
"Retorne APENAS JSON com: insights (list[str]), "
"recommendations (list[str]), confidence (high|medium|low)."
```

### 2.8 AcompanhamentoAgent

- **Arquivo:** `app/agents/acompanhamento.py`
- **Modelo LLM padrão:** gateway
- **max_tokens:** não especifica
- **temperature:** não especifica
- **Disparo:**
  - **Celery Beat `acompanhamento-check-processes` a cada 30 min** (`app/core/celery_app.py:44-47`) → `workers.acompanhamento_check_all` → itera processos com `status=aguardando_orgao`
  - Chain `monitoramento`
  - `POST /agents/run` manual
- **MemPalace:** só escrita, sem recall

**System prompt (fallback):**
```python
"Voce e um especialista em processos ambientais brasileiros. "
"Analise mensagens de orgaos ambientais (IBAMA, SEMA, ICMBio, etc.) "
"e extraia informacoes relevantes para acompanhamento do processo. "
"Retorne APENAS JSON com: is_agency_response (bool), agency (str|null), "
"response_type (aprovacao|exigencia|indeferimento|informacao), "
"summary (str), deadlines (list[str]), action_required (bool), "
"suggested_next_status (str|null), extracted_protocol (str|null), "
"confidence (high|medium|low)."
```

### 2.9 VigiaAgent

- **Arquivo:** `app/agents/vigia.py`
- **Modelo LLM padrão:** **NENHUM — opera só com queries SQL e regras.** Nunca chama `call_llm`.
- **Disparo:**
  - **Celery Beat `vigia-scheduled-check` a cada 6h, minuto 15** (`app/core/celery_app.py:40-43`) → `workers.vigia_all_tenants`
  - Chain `monitoramento`
  - `POST /agents/run` manual
- **MemPalace:** só escrita, sem recall

**System prompt:**
```python
"vigia_system": "Agente de monitoramento — opera por regras, sem LLM."
```

### 2.10 MarketingAgent

- **Arquivo:** `app/agents/marketing.py`
- **Modelo LLM padrão:** gateway
- **max_tokens:** não especifica
- **temperature:** não especifica
- **Disparo:**
  - Chain `marketing_content`
  - `POST /agents/run` manual (esperando `metadata.content_type` em `{post, email, whatsapp, blog, banner}`)
- **MemPalace:** só escrita, sem recall

**System prompt (fallback):**
```python
"Voce e um especialista em marketing para agronegocio e consultoria ambiental no Brasil. "
"Crie conteudo engajante, informativo e acessivel para produtores rurais. "
"Use linguagem clara, evite jargao excessivo, e destaque beneficios praticos. "
"O tom deve ser profissional mas acessivel."
```

### 2.11 Chains (mapa completo em `app/agents/orchestrator.py:24-34`)

```python
CHAINS: dict[str, list[str]] = {
    "intake": ["atendimento"],
    "diagnostico_completo": ["extrator", "legislacao", "diagnostico"],
    "gerar_proposta": ["diagnostico", "orcamento"],
    "gerar_documento": ["redator"],
    "analise_regulatoria": ["legislacao"],
    "enquadramento_regulatorio": ["extrator", "legislacao"],
    "analise_financeira": ["financeiro"],
    "monitoramento": ["acompanhamento", "vigia"],
    "marketing_content": ["marketing"],
}
```

---

## 3. MemPalace

> 🚨 **SEÇÃO REVOGADA em 2026-04-23.** O pacote PyPI `mempalace` foi abandonado
> por sinais fortes de supply-chain attack (ver
> [docs/adr/adr_mempalace_REVOKED.md](docs/adr/adr_mempalace_REVOKED.md)).
> O código em `app/agents/memory.py` foi convertido em **stub no-op interno**:
> as mesmas assinaturas continuam existindo (preservando os 10 agentes e o
> BaseAgent sem quebra), mas nenhuma função importa o pacote ou toca disco.
> Os 3471 embeddings do palace local foram descartados (25 MB em
> `~/.mempalace/palace/`). A estatística de "99.7% vazio de dados de agentes"
> que motivou parte das 3 frentes declaradas deixa de ser relevante — a decisão
> agora é construir memória em pgvector (Sprint U) em cima do stub.
>
> O conteúdo técnico abaixo fica como **registro do estado pré-revogação** e
> como referência de *quais assinaturas o novo backend pgvector deve preservar*.

### 3.1 Schema — MemPalace usa SQLite local, NÃO Postgres

O MemPalace persiste em dois arquivos SQLite em `~/.mempalace/`:

- **`palace/chroma.sqlite3`** — base vetorial Chroma com embeddings semânticos (single collection `mempalace_drawers`)
- **`knowledge_graph.sqlite3`** — knowledge graph (2 tabelas: `entities`, `triples`)

**Não existem tabelas SQLAlchemy ORM para MemPalace no repositório** — a integração é via `mempalace.mcp_server` (pip `mempalace>=3.0.0` em `requirements.txt`). Schema das tabelas Chroma observado em tempo de execução:

```
TABLES no chroma.sqlite3:
['migrations', 'acquire_write', 'collection_metadata', 'segment_metadata',
 'tenants', 'databases', 'collections', 'maintenance_log', 'segments',
 'embeddings', 'embedding_metadata', 'max_seq_id',
 'embedding_fulltext_search', 'embedding_fulltext_search_data',
 'embedding_fulltext_search_idx', 'embedding_fulltext_search_content',
 'embedding_fulltext_search_docsize', 'embedding_fulltext_search_config',
 'embedding_metadata_array', 'embeddings_queue', 'embeddings_queue_config']

TABLES no knowledge_graph.sqlite3:
['entities', 'triples']

Schema da tabela triples:
  id TEXT PRIMARY KEY, subject TEXT, predicate TEXT, object TEXT,
  valid_from TEXT, valid_to TEXT, confidence REAL,
  source_closet TEXT, source_file TEXT, extracted_at TEXT
```

### 3.2 Código da função de escrita (diary + KG)

Todo o módulo de integração está em `app/agents/memory.py`:

```python
"""
MemPalace integration for the Agent framework.

Provides non-blocking memory operations:
- diary_write: logs agent executions (input summary + result)
- diary_read: recalls recent agent activity
- kg_add: stores structured facts in the knowledge graph
- search: semantic search across the palace

All operations are fire-and-forget: MemPalace failures never break agent execution.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Palace path (local, never cloud)
PALACE_PATH = os.path.expanduser("~/.mempalace/palace")
WING = "amigao_do_meio_ambiente"

# Lazy-loaded module reference
_mcp = None


def _get_mcp():
    """Lazy import of mempalace.mcp_server to avoid import-time failures."""
    global _mcp
    if _mcp is None:
        try:
            from mempalace import mcp_server
            _mcp = mcp_server
        except ImportError:
            logger.debug("mempalace not installed — memory features disabled")
    return _mcp


def is_available() -> bool:
    """Check if MemPalace is installed and palace exists."""
    return _get_mcp() is not None and os.path.isdir(PALACE_PATH)


# ---------------------------------------------------------------------------
# Diary operations (per-agent execution log)
# ---------------------------------------------------------------------------

def diary_write(agent_name: str, entry: str, topic: str = "execution") -> None:
    """Write a diary entry for an agent. Non-blocking, never raises."""
    mcp = _get_mcp()
    if mcp is None:
        return
    try:
        mcp.tool_diary_write(agent_name=agent_name, entry=entry, topic=topic)
    except Exception as exc:
        logger.debug("mempalace diary_write failed for %s: %s", agent_name, exc)


def diary_read(agent_name: str, last_n: int = 5) -> list[dict[str, Any]]:
    """Read recent diary entries for an agent. Returns empty list on failure."""
    mcp = _get_mcp()
    if mcp is None:
        return []
    try:
        result = mcp.tool_diary_read(agent_name=agent_name, last_n=last_n)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("entries", [])
        return []
    except Exception as exc:
        logger.debug("mempalace diary_read failed for %s: %s", agent_name, exc)
        return []


# ---------------------------------------------------------------------------
# Knowledge Graph operations
# ---------------------------------------------------------------------------

def kg_add(subject: str, predicate: str, obj: str, source: str | None = None) -> None:
    """Add a fact to the knowledge graph. Non-blocking, never raises."""
    mcp = _get_mcp()
    if mcp is None:
        return
    try:
        mcp.tool_kg_add(
            subject=subject,
            predicate=predicate,
            object=obj,
            source_closet=source,
        )
    except Exception as exc:
        logger.debug("mempalace kg_add failed: %s", exc)


def kg_query(entity: str) -> list[dict[str, Any]]:
    """Query the knowledge graph for an entity. Returns empty list on failure."""
    mcp = _get_mcp()
    if mcp is None:
        return []
    try:
        result = mcp.tool_kg_query(entity=entity)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("triples", [])
        return []
    except Exception as exc:
        logger.debug("mempalace kg_query failed for %s: %s", entity, exc)
        return []


# ---------------------------------------------------------------------------
# Semantic search
# ---------------------------------------------------------------------------

def search(query: str, room: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
    """Semantic search across the palace. Returns empty list on failure."""
    mcp = _get_mcp()
    if mcp is None:
        return []
    try:
        result = mcp.search_memories(
            query=query,
            palace_path=PALACE_PATH,
            wing=WING,
            room=room,
            n_results=limit,
        )
        if isinstance(result, dict):
            return result.get("results", [])
        return []
    except Exception as exc:
        logger.debug("mempalace search failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Drawer operations (store content in a room)
# ---------------------------------------------------------------------------

def save_to_room(room: str, content: str, source_file: str | None = None) -> None:
    """Save content to a specific room. Non-blocking, never raises."""
    mcp = _get_mcp()
    if mcp is None:
        return
    try:
        mcp.tool_add_drawer(
            wing=WING,
            room=room,
            content=content,
            source_file=source_file,
            added_by="agent_framework",
        )
    except Exception as exc:
        logger.debug("mempalace save_to_room failed for %s: %s", room, exc)


# ---------------------------------------------------------------------------
# High-level helpers for BaseAgent integration
# ---------------------------------------------------------------------------

def log_agent_execution(
    agent_name: str,
    palace_room: str,
    ctx_summary: str,
    result_summary: str,
    success: bool,
    confidence: str,
    duration_ms: int,
    process_id: int | None = None,
) -> None:
    """
    Log a complete agent execution to MemPalace.

    Called automatically by BaseAgent.run() after execution.
    Writes diary entry + knowledge graph facts.
    """
    # Diary entry with execution details
    entry = (
        f"[{'OK' if success else 'FAIL'}] conf={confidence} ms={duration_ms}"
        f"{f' process={process_id}' if process_id else ''}\n"
        f"IN: {ctx_summary[:300]}\n"
        f"OUT: {result_summary[:500]}"
    )
    diary_write(agent_name, entry, topic=palace_room)

    # Knowledge graph: agent executed on process
    if process_id and success:
        kg_add(
            subject=f"process_{process_id}",
            predicate=f"analyzed_by_{agent_name}",
            obj=f"confidence={confidence}",
            source=f"agent_{agent_name}",
        )


def recall_agent_context(agent_name: str, query: str | None = None) -> dict[str, Any]:
    """
    Recall context for an agent from MemPalace.

    Returns dict with recent diary entries and optional search results.
    Used by agents that want to enrich their prompts with historical context.
    """
    context: dict[str, Any] = {
        "recent_diary": diary_read(agent_name, last_n=3),
    }

    if query:
        context["search_results"] = search(query, limit=3)

    return context
```

### 3.3 Hooks do BaseAgent para MemPalace

```python
# app/agents/base.py:276-339

def recall_memory(self, query: str | None = None) -> dict[str, Any]:
    """
    Recall context from MemPalace for this agent.

    Returns recent diary entries and optional semantic search results.
    Agents can call this in execute() to enrich prompts with history.
    """
    from app.agents.memory import recall_agent_context  # noqa: PLC0415
    return recall_agent_context(self.name, query=query)

def remember(self, content: str, topic: str = "general") -> None:
    """Manually save something to this agent's diary."""
    from app.agents.memory import diary_write  # noqa: PLC0415
    diary_write(self.name, content, topic=topic)

def remember_fact(self, subject: str, predicate: str, obj: str) -> None:
    """Add a fact to the knowledge graph."""
    from app.agents.memory import kg_add  # noqa: PLC0415
    kg_add(subject, predicate, obj, source=f"agent_{self.name}")

def _mempalace_log(self, result: AgentResult, data: dict[str, Any]) -> None:
    """Log successful execution to MemPalace. Fire-and-forget."""
    from app.agents.memory import log_agent_execution  # noqa: PLC0415

    ctx_summary = self._build_ctx_summary()
    result_keys = list(data.keys())[:10]
    result_summary = f"keys={result_keys} confidence={result.confidence}"

    log_agent_execution(
        agent_name=self.name,
        palace_room=self.palace_room,
        ctx_summary=ctx_summary,
        result_summary=result_summary,
        success=True,
        confidence=result.confidence,
        duration_ms=result.duration_ms,
        process_id=self.ctx.process_id,
    )

def _mempalace_log_failure(self, error: str, elapsed_ms: int) -> None:
    """Log failed execution to MemPalace. Fire-and-forget."""
    from app.agents.memory import log_agent_execution  # noqa: PLC0415

    log_agent_execution(
        agent_name=self.name,
        palace_room=self.palace_room,
        ctx_summary=self._build_ctx_summary(),
        result_summary=f"ERROR: {error[:300]}",
        success=False,
        confidence="low",
        duration_ms=elapsed_ms,
        process_id=self.ctx.process_id,
    )

def _build_ctx_summary(self) -> str:
    """Build a compact summary of the agent context for MemPalace."""
    parts = [f"tenant={self.ctx.tenant_id}"]
    if self.ctx.process_id:
        parts.append(f"process={self.ctx.process_id}")
    if self.ctx.metadata:
        meta_keys = list(self.ctx.metadata.keys())[:5]
        parts.append(f"meta_keys={meta_keys}")
```

### 3.4 Código de recall nos dois agentes que leem hoje

**DiagnosticoAgent** (`app/agents/diagnostico.py:44-67`):

```python
# 4. MemPalace: buscar diagnosticos anteriores similares
memory_hint = ""
prop = process_data.get("property", {})
recall_query = f"diagnostico {prop.get('state', '')} {prop.get('biome', '')} {process_data.get('process', {}).get('demand_type', '')}"
recall = self.recall_memory(recall_query)
if recall.get("recent_diary"):
    entries = [e.get("entry", "") if isinstance(e, dict) else str(e) for e in recall["recent_diary"][:3]]
    memory_hint = "\n".join(f"- {e}" for e in entries if e)

# 5. Chamar LLM para diagnostico completo
system_prompt = self.get_prompt("diagnostico_system")
user_prompt = self.get_prompt("diagnostico_user", {
    "property_data": json.dumps(prop, ensure_ascii=False, default=str),
    "process_data": json.dumps(process_data.get("process", {}), ensure_ascii=False, default=str),
    "documents": json.dumps(process_data.get("documents", []), ensure_ascii=False, default=str),
    "extracted_fields": json.dumps(extracted_data, ensure_ascii=False, default=str),
    "legal_context": json.dumps(legal_data, ensure_ascii=False, default=str),
})

if memory_hint.strip():
    user_prompt += (
        "\n\nDIAGNOSTICOS ANTERIORES SIMILARES (referencia interna):\n"
        + memory_hint
    )
```

**LegislacaoAgent** (`app/agents/legislacao.py:71-96`):

```python
# MemPalace: enriquecer com casos passados similares
memory_context = ""
recall = self.recall_memory(f"legislacao {demand_type} {state}")
if recall.get("recent_diary"):
    entries = [e.get("entry", "") if isinstance(e, dict) else str(e) for e in recall["recent_diary"][:3]]
    memory_context = "\n".join(f"- {e}" for e in entries if e)
if recall.get("search_results"):
    hits = [r.get("text", "")[:200] if isinstance(r, dict) else str(r)[:200] for r in recall["search_results"][:3]]
    memory_context += "\n" + "\n".join(f"- {h}" for h in hits if h)

# Montar prompts
system_prompt = self.get_prompt("legislacao_system")
user_prompt = self.get_prompt("legislacao_user", {
    "query": query,
    "demand_type": demand_type or "nao_identificado",
    "state": state or "nao_informado",
    "context": json.dumps(process_context, ensure_ascii=False, default=str),
    "legislation": legislation_context,
})

# Anexar contexto historico do MemPalace ao prompt
if memory_context.strip():
    user_prompt += (
        "\n\nCASOS ANTERIORES SIMILARES (base de conhecimento interna):\n"
        + memory_context
    )
```

### 3.5 Exemplos REAIS de 3 diary entries no banco

Extração direta do `chroma.sqlite3` local. O MemPalace atual tem **3471 embeddings no total**, mas apenas **10 no room `diary`** — todas são entradas de inicialização do tipo `[INIT] Agent X MemPalace integration test` de 2026-04-09. **Não há ainda diary entries de execuções reais de agentes contra casos de produção**.

| id | agent | room | topic | date | document (entry) |
|---|---|---|---|---|---|
| 2366 | atendimento | diary | setup | 2026-04-09 | `[INIT] Agent atendimento MemPalace integration test` |
| 2369 | extrator | diary | setup | 2026-04-09 | `[INIT] Agent extrator MemPalace integration test` |
| 2371 | diagnostico | diary | setup | 2026-04-09 | `[INIT] Agent diagnostico MemPalace integration test` |

Distribuição real dos 3471 embeddings do palace (room count):

| room | n_embeddings |
|---|---|
| app | 1931 |
| frontend | 641 |
| general | 235 |
| alembic | 202 |
| ops | 178 |
| mobile | 163 |
| client_portal | 86 |
| design | 12 |
| backend | 12 |
| **diary** | **10** |
| scripts | 1 |

> **Observação crítica para análise externa:** o MemPalace está majoritariamente povoado por ingestão de arquivos de código (rooms `app`, `frontend`, `alembic` etc., feita por `save_to_room` fora do fluxo de agentes), não por histórico de execução de agentes. O valor esperado do "recall de casos anteriores" está essencialmente **vazio em produção**.

### 3.6 Exemplo REAL de 1 entrada de knowledge graph

Extração de `~/.mempalace/knowledge_graph.sqlite3` tabela `triples`:

```
triples: 1 row total
entities: 2 rows total

Row observada:
id            = t_amigao_system_has_agent_count_10_36741191
subject       = amigao_system
predicate     = has_agent_count
object        = 10
valid_from    = NULL
valid_to      = NULL
confidence    = 1.0
source_closet = setup
source_file   = NULL
extracted_at  = 2026-04-09 14:27:13
```

> Confirma o ponto acima: a única triple registrada é a de setup inicial. O knowledge graph previsto em `log_agent_execution` (`process_{id} → analyzed_by_{agent_name} → confidence={...}`) nunca foi populado porque os agentes ainda não rodaram em casos reais com `process_id` concreto.

---

## 4. Legislação

### 4.1 Schema da tabela `legislation_documents`

Model em `app/models/legislation.py`:

```python
"""
Legislation models — base de conhecimento legislativo.

LegislationDocument: metadata + texto completo do documento (lei, decreto, resolucao, IN, portaria).

Estrategia: armazenar texto completo e enviar direto no contexto do Gemini (2M tokens)
ao inves de chunking + embeddings. Isso preserva o contexto integral da legislacao.
"""

from __future__ import annotations

import enum

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    ForeignKey,
)
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.types import PortableJSON


class LegislationScope(str, enum.Enum):
    federal = "federal"
    estadual = "estadual"
    municipal = "municipal"


class LegislationSourceType(str, enum.Enum):
    lei = "lei"
    decreto = "decreto"
    resolucao = "resolucao"
    instrucao_normativa = "instrucao_normativa"
    portaria = "portaria"
    nota_tecnica = "nota_tecnica"
    manual = "manual"


class LegislationStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    indexed = "indexed"
    failed = "failed"


class LegislationDocument(Base):
    """Documento legislativo na base de conhecimento."""
    __tablename__ = "legislation_documents"

    id = Column(Integer, primary_key=True, index=True)
    # tenant_id nullable — None = documento global (legislacao federal)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    title = Column(String, nullable=False)
    source_type = Column(String, nullable=False)  # lei, decreto, resolucao, etc.
    identifier = Column(String, nullable=True, index=True)  # "Lei 12.651/2012"

    # Escopo geografico
    uf = Column(String(2), nullable=True, index=True)  # None = federal
    scope = Column(String, nullable=False, default="federal")  # federal/estadual/municipal
    municipality = Column(String, nullable=True)

    # Orgao emissor
    agency = Column(String, nullable=True, index=True)  # IBAMA, SEMA-MT, etc.

    # Datas
    effective_date = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    # Armazenamento
    url = Column(String, nullable=True)
    file_path = Column(String, nullable=True)  # MinIO storage key

    # Texto completo extraido (enviado direto no contexto do Gemini)
    full_text = Column(Text, nullable=True)
    token_count = Column(Integer, nullable=False, default=0)

    # Processamento
    status = Column(String, nullable=False, default="pending")
    content_hash = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)

    # Metadados para filtragem na busca
    demand_types = Column(PortableJSON, nullable=True)  # ["car", "licenciamento", ...]
    keywords = Column(PortableJSON, nullable=True)  # palavras-chave extraidas
    extra_metadata = Column(PortableJSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

### 4.2 `search_legislation` e `build_legislation_context` na íntegra

`app/services/legislation_service.py:122-209`:

```python
def search_legislation(
    db: Session,
    *,
    uf: Optional[str] = None,
    scope: Optional[str] = None,
    agency: Optional[str] = None,
    demand_type: Optional[str] = None,
    keyword: Optional[str] = None,
    max_results: int = 20,
    max_total_tokens: int = 500_000,
) -> list[LegislationDocument]:
    """
    Busca documentos legislativos por metadados.
    Retorna documentos ordenados por relevancia ate o limite de tokens.
    O texto completo sera enviado no contexto do Gemini.
    """
    q = (
        db.query(LegislationDocument)
        .filter(LegislationDocument.status == "indexed")
        .filter(LegislationDocument.full_text.isnot(None))
    )

    # Filtros por metadados
    if uf:
        # Federal se aplica a todos + estadual do UF especifico
        q = q.filter(
            (LegislationDocument.uf == uf) | (LegislationDocument.uf.is_(None))
        )
    if scope:
        q = q.filter(LegislationDocument.scope == scope)
    if agency:
        q = q.filter(LegislationDocument.agency == agency)

    # Busca textual por keyword no titulo ou texto
    if keyword:
        q = q.filter(
            LegislationDocument.title.ilike(f"%{keyword}%")
            | LegislationDocument.full_text.ilike(f"%{keyword}%")
        )

    # Ordenar por federal primeiro, depois por data
    docs = (
        q.order_by(
            LegislationDocument.scope.asc(),  # federal vem antes
            LegislationDocument.effective_date.desc().nulls_last(),
        )
        .limit(max_results)
        .all()
    )

    # Limitar por budget de tokens
    selected: list[LegislationDocument] = []
    total_tokens = 0
    for doc in docs:
        if total_tokens + doc.token_count > max_total_tokens:
            break
        selected.append(doc)
        total_tokens += doc.token_count

    logger.info(
        "legislation search: uf=%s, scope=%s, agency=%s, results=%d, tokens=%d",
        uf, scope, agency, len(selected), total_tokens,
    )
    return selected


def build_legislation_context(docs: list[LegislationDocument]) -> str:
    """
    Monta o contexto legislativo para enviar ao LLM.
    Cada documento e separado com header identificador.
    """
    if not docs:
        return ""

    parts: list[str] = []
    for doc in docs:
        header = f"--- {doc.identifier or doc.title} ({doc.scope}"
        if doc.uf:
            header += f"/{doc.uf}"
        if doc.agency:
            header += f" - {doc.agency}"
        header += ") ---"

        parts.append(header)
        parts.append(doc.full_text or "")
        parts.append("")

    return "\n".join(parts)
```

> Observação importante: `build_legislation_context` filtra o `demand_type` externamente **mas NÃO aplica filtro de `demand_type` na query** (ver `search_legislation`). O argumento `demand_type=...` é aceito mas **não é usado**. Esse é um bug/inefetividade conhecida: todos os docs compatíveis por `uf` + `scope` entram no top-20, independente de mencionarem a demanda concreta.

### 4.3 Quantidade de documentos por UF e scope

**Query pronta para rodar:**

```sql
-- Docs por UF + scope
SELECT
  COALESCE(uf, 'FEDERAL') AS uf,
  scope,
  COUNT(*) AS docs,
  COALESCE(SUM(token_count), 0) AS total_tokens,
  COALESCE(AVG(token_count)::int, 0) AS avg_tokens
FROM legislation_documents
WHERE status = 'indexed'
GROUP BY 1, 2
ORDER BY scope, uf;

-- Total geral
SELECT scope, COUNT(*), SUM(token_count) AS total_tokens
FROM legislation_documents
WHERE status = 'indexed'
GROUP BY scope;

-- Tamanho médio e distribuição
SELECT
  MIN(token_count), MAX(token_count),
  AVG(token_count)::int AS avg,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY token_count) AS median,
  PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY token_count) AS p90
FROM legislation_documents
WHERE status = 'indexed';
```

**RESULTADO (executado 2026-04-23):**

```
-- SELECT status, COUNT(*) FROM legislation_documents GROUP BY status;
  status | count
---------+-------
 (0 linhas)

-- SELECT COUNT(*) AS total_legislation FROM legislation_documents;
 total_legislation
-------------------
                 0
```

> ⚠️ **A tabela `legislation_documents` está VAZIA.** Apesar da infra estar pronta (model, service, crawlers Celery Beat em `monitor_legislation_dou/doe/agencies`), **nenhum documento foi ingerido ainda**. Isso significa que:
> - Toda chamada ao `LegislacaoAgent` hoje recebe `legislation_context=""` do `search_legislation`
> - O agente cai no caminho do LLM **sem base legislativa**, contando apenas com conhecimento prévio do Gemini/GPT-4o-mini
> - Isso explica o `avg_tokens_in=519` do agente `legislacao` nos logs (pequeno — é só o prompt do caso, sem anexar full_text de leis)
> - **RAG de legislação é prematuro** sem ingestão. Priorizar popular a tabela antes de otimizar retrieval.

### 4.4 Tamanho médio em tokens dos documentos

Fórmula hardcoded: `len(texto) // 4` (ver `_estimate_tokens` em `app/services/legislation_service.py:52-54`).

```python
def _estimate_tokens(text: str) -> int:
    """Estimativa simples: ~4 chars por token em portugues."""
    return len(text) // 4
```

**RESULTADO:** N/A. Base vazia (0 documentos), impossível calcular tamanho médio real.

---

## 5. Propriedades e Geo

### 5.1 Schema completo do modelo Property

`app/models/property.py`:

```python
from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.types import PortableJSON


class Property(Base):
    """Imóvel rural — entidade central fundiária."""
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False, index=True)

    name = Column(String, nullable=False)
    registry_number = Column(String, nullable=True)   # matrícula
    ccir = Column(String, nullable=True)
    nirf = Column(String, nullable=True)
    car_code = Column(String, nullable=True)
    car_status = Column(String, nullable=True)         # ativo, pendente, cancelado, etc.

    total_area_ha = Column(Float, nullable=True)
    municipality = Column(String, nullable=True)
    state = Column(String(2), nullable=True)           # UF
    biome = Column(String, nullable=True)

    geom = Column(Geometry(geometry_type="GEOMETRY", srid=4674), nullable=True)

    has_embargo = Column(Boolean, default=False)
    status = Column(String, default="active")         # active, inactive, archived
    notes = Column(Text, nullable=True)

    # Regente Cam2 CAM2IH-007 — origem por campo: raw | ai_extracted | human_validated
    field_sources = Column(PortableJSON, nullable=True, default=dict)

    # Regente Cam2 CAM2IH-003/004 (Sprint H) — campos técnicos do Dashboard + Aba Informações
    rl_status = Column(String, nullable=True)           # averbada | proposta | pendente | cancelada
    app_area_ha = Column(Float, nullable=True)
    regulatory_issues = Column(PortableJSON, nullable=True, default=list)  # [{tipo, descricao, severidade}]
    area_documental_ha = Column(Float, nullable=True)
    area_grafica_ha = Column(Float, nullable=True)
    tipologia = Column(String, nullable=True)           # agricultura | pecuaria | misto | outro
    strategic_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tenant = relationship("Tenant")
    client = relationship("Client")
```

### 5.2 Checagem "geometria existe sim/não"

Duas ocorrências — a única leitura de `geom` no sistema inteiro:

```python
# app/services/dossier.py:100-108 (resumo do dossier do processo)
"car_code": prop.car_code,
"car_status": prop.car_status,
"total_area_ha": prop.total_area_ha,
"municipality": prop.municipality,
"state": prop.state,
"biome": prop.biome,
"has_embargo": prop.has_embargo,
"has_geom": prop.geom is not None,
```

```python
# app/services/dossier.py:281-288 (validação de inconsistências)
if not prop.geom and demand in ("car", "retificacao_car", "regularizacao_fundiaria"):
    issues.append(Inconsistency(
        code="MISSING_GEOM",
        severity="warning",
        title="Georreferenciamento ausente",
        description="Imóvel sem geometria georreferenciada. Necessário para esta demanda.",
        field="property.geom",
    ))
```

### 5.3 SRIDs em uso

**SRID 4674** (SIRGAS 2000) — único SRID **declarado** no sistema, em `Property.geom`. Grep confirma:

```
app/models/property.py:30:    geom = Column(Geometry(geometry_type="GEOMETRY", srid=4674), nullable=True)
```

Nenhuma outra tabela tem coluna geográfica. Nenhum outro SRID aparece em migrations ou services.

**RESULTADO (executado 2026-04-23 contra DB live):**

```
-- SELECT DISTINCT ST_SRID(geom) FROM properties WHERE geom IS NOT NULL;
(0 linhas)

-- SELECT COUNT(*), COUNT(geom) FROM properties;
 total_properties | with_geom | with_car | with_area
------------------+-----------+----------+-----------
                7 |         0 |        3 |         3
```

> **7 propriedades cadastradas, 0 com geometria preenchida.** PostGIS está 100% dormindo em runtime — nenhum ST_* pode ser executado porque não há dado espacial. Apenas 3 de 7 têm `car_code` e `total_area_ha`.

---

## 6. Orçamento, Redator e Extrator (prioritários para recall)

### 6.1 ExtratorAgent — entrada e saída

**Entrada esperada em `ctx.metadata`:**

```python
{
    "text": str,              # texto OCR/PDF extraído (opcional se document_id presente)
    "doc_type": str,          # "matricula" | "car" | "ccir" | "auto_infracao" | "licenca" | "outorga"
    "document_id": int | None,  # se ausente, precisa de text; se presente, busca text no banco
}
```

Se `document_id` é passado e `text` vazio, o agente busca de `Document.extracted_text` no banco (ver `app/agents/extrator.py:46-58`). **Nota:** o modelo `Document` **NÃO** tem uma coluna `extracted_text` no schema atual — ela está presumida pela função de extração mas não existe no ORM. Isso é uma dívida.

**Saída:**

```python
{
    "extracted_fields": dict[str, Any],  # Campos estruturados do documento, varia por doc_type
    "doc_type": str,
    "document_id": int | None,
    "fields_count": int,
    # Extras quando skip:
    "skipped": bool,
    "reason": str,
}
```

**Exemplo de `extracted_fields` por doc_type (schemas definidos em `app/services/document_extractor.py`):**

```json
// doc_type = "matricula"
{
  "numero_matricula": "15.234",
  "cartorio": "2º RGI de Sorriso",
  "comarca": "Sorriso",
  "uf": "MT",
  "proprietario_nome": "...",
  "proprietario_cpf_cnpj": "...",
  "area_hectares": 432.5,
  "denominacao_imovel": "Fazenda Santa Rita",
  "municipio": "Sorriso",
  "descricao_limites": "...",
  "data_registro": "2019-03-15",
  "confidence": {"numero_matricula": "high", "area_hectares": "medium"}
}

// doc_type = "car"
{
  "numero_car": "MT-5107883-...",
  "situacao": "Ativo",
  "cpf_cnpj_proprietario": "...",
  "area_total_ha": 432.5,
  "area_app_ha": 45.2,
  "area_reserva_legal_ha": 86.5,
  "data_inscricao": "2020-08-22",
  "pendencias": null,
  "confidence": {...}
}
```

**Volume histórico:**

```sql
-- Extrações de documento armazenadas em AIJob (job_type = 'extract_document')
SELECT
  COUNT(*) AS total_extractions,
  COUNT(*) FILTER (WHERE status = 'completed') AS completed,
  COUNT(DISTINCT entity_id) AS unique_documents,
  AVG(cost_usd)::numeric(10,6) AS avg_cost,
  AVG(tokens_in)::int AS avg_tokens_in,
  AVG(tokens_out)::int AS avg_tokens_out
FROM ai_jobs
WHERE job_type = 'extract_document';

-- Por doc_type
SELECT
  result->>'doc_type' AS doc_type,
  COUNT(*),
  AVG(cost_usd)::numeric(10,6) AS avg_cost
FROM ai_jobs
WHERE job_type = 'extract_document' AND status = 'completed'
GROUP BY 1;
```

**RESULTADO (executado 2026-04-23):**

```
-- Extrações por doc_type
 doc_type | jobs | completed
----------+------+-----------
 [none]   |    1 |         0
 outro    |    4 |         4
```

**Observação:** apenas **5 extrações no total**, sendo 4 bem-sucedidas com `doc_type="outro"` e 1 falha sem doc_type. **Nenhuma extração real de matrícula/car/ccir/auto_infracao/licenca no banco.** O agente extrator registrou execuções mas sem texto real (provável smoke-test, já que `avg_tokens_in=0`).

### 6.2 OrcamentoAgent — entrada e saída

**Entrada esperada em `ctx.metadata` e/ou `ctx.chain_data`:**

```python
ctx.process_id: int | None
ctx.metadata: {
    "demand_type": str,  # usado se não veio de chain
}
ctx.chain_data: {
    "diagnostico": dict,   # saída do DiagnosticoAgent (opcional)
    "atendimento": dict,   # saída do AtendimentoAgent (opcional)
}
```

O agente tem um caminho **sem-LLM** baseado em regras (`_estimate_by_rules`) com valores hardcoded por `demand_type` — retorna orçamento-base que é usado como input para o LLM refinar.

**Regras-base (`app/agents/orcamento.py:96-139`):**

```python
estimates: dict[str, dict[str, Any]] = {
    "car": {"complexity": "baixa", "suggested_value_min": 2500, "suggested_value_max": 5000, "estimated_days": 30, ...},
    "licenciamento": {"complexity": "alta", "suggested_value_min": 8000, "suggested_value_max": 25000, "estimated_days": 90, ...},
    "defesa": {"complexity": "alta", "suggested_value_min": 5000, "suggested_value_max": 15000, "estimated_days": 60, ...},
}
# default: {complexity: media, min: 3000, max: 10000, days: 45}
```

**Saída:**

```python
{
    "demand_type": str,
    "complexity": str,             # baixa | media | alta
    "scope_items": list[{"description": str, "estimated_hours": int}],
    "suggested_value_min": float,
    "suggested_value_max": float,
    "estimated_days": int,
    "payment_terms": str,
    "notes": str,
    "confidence": str,             # high | medium | low
    "requires_review": bool,       # sempre True
}
```

**Volume histórico — contraparte real no modelo `Proposal`:**

```python
# app/models/proposal.py (integral):
class ProposalStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    accepted = "accepted"
    rejected = "rejected"
    expired = "expired"


class Proposal(Base):
    __tablename__ = "proposals"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    process_id = Column(Integer, ForeignKey("processes.id", ondelete="SET NULL"), nullable=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False, index=True)

    status = Column(Enum(ProposalStatus), default=ProposalStatus.draft, nullable=False)
    version_number = Column(Integer, default=1, nullable=False)

    title = Column(String, nullable=False)
    scope_items = Column(JSON, nullable=False, default=list)  # [{description, unit, qty, unit_price, total}]
    total_value = Column(Float, nullable=True)
    validity_days = Column(Integer, default=30)
    payment_terms = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    complexity = Column(String, nullable=True)

    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
```

**Queries de volume:**

```sql
-- Propostas histórias (candidatos a "casos passados" para recall semântico)
SELECT status, COUNT(*), SUM(total_value) AS total_proposed
FROM proposals
GROUP BY status;

SELECT complexity, status, COUNT(*), AVG(total_value)::numeric(12,2) AS avg_value
FROM proposals
WHERE total_value IS NOT NULL
GROUP BY 1, 2
ORDER BY 1, 2;

-- Propostas aceitas (ground truth para modelagem)
SELECT COUNT(*) FROM proposals WHERE status = 'accepted';
```

**RESULTADO (executado 2026-04-23):**

```
-- SELECT status, COUNT(*), SUM(total_value) FROM proposals GROUP BY status;
  status  | n | avg_value
----------+---+-----------
 accepted | 4 |  11625.00

-- Amostra de títulos (4 propostas reais no banco):
 id |  status  | total_value |                                      title
----+----------+-------------+----------------------------------------------------------------------------------
  1 | accepted |        1500 | CAR Fazenda Mozondó
  5 | accepted |       10000 | Proposta — Demanda Mista / Múltiplos Passivos — Wesley Gontijo (Fazenda Paraiso)
  2 | accepted |        3500 | Proposta — Demanda Mista / Múltiplos Passivos — andre mello
  3 | accepted |       31500 | Proposta — Licenciamento Ambiental — Cliente Demo

-- Por complexity (nenhuma proposta preenche complexity):
 complexity |  status  | count | avg_value
------------+----------+-------+-----------
   NULL     | accepted |     4 |  11625.00
```

**Volume histórico real:** **4 propostas aceitas** (todas status=`accepted`), valores entre R$ 1500 e R$ 31.500, **todas com `complexity=NULL`** (campo não preenchido nos seeds). Não há propostas `draft`/`sent`/`rejected` — ou seja, o banco é essencialmente **dados de seed**, não produção real com funil de negociação.

### 6.3 RedatorAgent — entrada e saída

**Entrada esperada em `ctx.metadata` e/ou `ctx.chain_data`:**

```python
ctx.process_id: int | None
ctx.metadata: {
    "document_template": str,   # "prad" | "memorial" | "oficio" | "proposta" | "resposta_notificacao" | "contrato" | "comunicacao"
    "client_data": dict,
    "property_data": dict,
    "instructions": str,
}
ctx.chain_data: {
    "diagnostico": dict,        # se vier de chain
    "legislacao": dict,
}
```

**Saída:**

```python
{
    "document_type": str,
    "content": str,             # texto formatado do documento gerado (não estruturado — Markdown/plain)
    "requires_review": bool,    # sempre True
    "confidence": str,          # sempre "medium"
}
```

**Volume histórico:** os documentos gerados pelo Redator ficam em `AIJob.result->>'content'`. Não há tabela dedicada. Contraparte parcial: o modelo `Contract` (ver abaixo) armazena conteúdos finais gerados ou selecionados de templates:

```python
# app/models/contract.py (recorte):
class ContractStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    signed = "signed"
    cancelled = "cancelled"


class Contract(Base):
    __tablename__ = "contracts"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ...), nullable=False, index=True)
    proposal_id = Column(Integer, ForeignKey("proposals.id", ...), nullable=True, index=True)
    process_id = Column(Integer, ForeignKey("processes.id", ...), nullable=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ...), nullable=False, index=True)
    template_id = Column(Integer, ForeignKey("contract_templates.id", ...), nullable=True)

    status = Column(Enum(ContractStatus), default=ContractStatus.draft, nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=True)
    pdf_storage_key = Column(String, nullable=True)
    signed_at = Column(DateTime(timezone=True), nullable=True)
    signed_by_client = Column(Boolean, default=False)
```

**Queries de volume:**

```sql
-- Documentos gerados por Redator (em AIJob.job_type='gerar_documento')
SELECT
  COUNT(*) AS total_generated,
  COUNT(*) FILTER (WHERE status = 'completed') AS completed,
  AVG(cost_usd)::numeric(10,6) AS avg_cost,
  AVG(tokens_out)::int AS avg_tokens_out,
  AVG(LENGTH(result->>'content'))::int AS avg_content_chars
FROM ai_jobs
WHERE job_type = 'gerar_documento';

-- Por template
SELECT
  result->>'document_type' AS template,
  COUNT(*),
  AVG(cost_usd)::numeric(10,6) AS avg_cost
FROM ai_jobs
WHERE job_type = 'gerar_documento' AND status = 'completed'
GROUP BY 1;

-- Contratos gerados (histórico "limpo" de documentos aceitos)
SELECT status, COUNT(*) FROM contracts GROUP BY status;
```

**RESULTADO (executado 2026-04-23):**

```
-- Documentos gerados (AIJob job_type='gerar_documento')
 -- 0 linhas retornadas: nenhum documento foi gerado pelo Redator ainda.

-- Contratos:
 status | n
--------+---
 draft  | 4

-- Contratos com conteúdo real:
 total_contracts | with_content | avg_content_chars
-----------------+--------------+-------------------
               4 |            4 |               872
```

**Amostra de contratos (4 no total, todos draft):**

```
 id | status | title                                                                                       | len
----+--------+---------------------------------------------------------------------------------------------+------
  1 | draft  | Contrato — CAR Fazenda Mozondó                                                              |  661
  2 | draft  | Contrato — Proposta — Demanda Mista / Múltiplos Passivos — andre mello                      |  795
  3 | draft  | Contrato — Proposta — Licenciamento Ambiental — Cliente Demo                                | 1147
  4 | draft  | Contrato — Proposta — Demanda Mista / Múltiplos Passivos — Wesley Gontijo (Fazenda Paraiso) |  885
```

**Conclusão:** 4 contratos draft com conteúdo curto (média 872 chars = ~217 tokens), **nenhum signed**. Nenhum documento foi gerado pelo agente Redator (`job_type='gerar_documento'` = 0 linhas). Isso significa que **não há corpus histórico real** de ofícios/PRADs/memoriais para alimentar recall semântico do Redator — qualquer RAG sobre artefatos gerados teria que começar populando com documentos reais ou usar modelos-padrão.

---

## 7. Infra e Docker

### 7.1 docker-compose.yml — serviço do banco (integral)

```yaml
services:
  db:
    image: postgis/postgis:15-3.3
    environment:
      POSTGRES_USER: "${POSTGRES_USER:-postgres}"
      POSTGRES_PASSWORD: "${POSTGRES_PASSWORD:-pgpass2026}"
      POSTGRES_DB: "${POSTGRES_DB:-amigao_db}"
    ports:
      - "5433:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d amigao_db"]
      interval: 10s
      timeout: 5s
      retries: 10

volumes:
  postgres_data:
  redis_data:
  minio_data:
  mempalace_data:
```

### 7.2 docker-compose.yml — persistência de MemPalace

```yaml
# MemPalace é montado como volume nomeado em 2 serviços (api e worker):
volumes:
  - mempalace_data:/root/.mempalace

# Inicialização no entrypoint do serviço api:
command: sh -c "python -m mempalace init --yes . 2>/dev/null || true && python -m app.db.init_db && python seed.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"
```

### 7.3 Versão atual do PostgreSQL

**PostgreSQL 15** (via imagem `postgis/postgis:15-3.3`). PostGIS 3.3 instalado.

Referências:
- `docker-compose.yml:3` → `image: postgis/postgis:15-3.3`
- `.github/workflows/ci.yml:70` → mesma imagem
- `tests/conftest.py:25` → `PostgresContainer("postgis/postgis:15-3.3", ...)`

### 7.4 pgvector — NÃO INSTALADO (confirmado live)

A imagem `postgis/postgis:15-3.3` **não inclui pgvector**. Confirmação via query live executada agora:

```sql
-- SELECT extname, extversion FROM pg_extension ORDER BY extname;
        extname         | extversion
------------------------+------------
 fuzzystrmatch          | 1.1
 plpgsql                | 1.0
 postgis                | 3.3.4
 postgis_tiger_geocoder | 3.3.4
 postgis_topology       | 3.3.4

-- Teste que falha:
CREATE EXTENSION IF NOT EXISTS vector;
-- ERROR: could not open extension control file ".../vector.control"
```

Apenas PostGIS 3.3.4 + extensões geográficas. **pgvector ausente.**

Para habilitar pgvector há 2 caminhos:

1. **Trocar a imagem** em 3 pontos (`docker-compose.yml`, `.github/workflows/ci.yml`, `tests/conftest.py`) para uma community image como `imresamu/postgis-pgvector:15-3.3.5-0.6.0` que traz postgis + pgvector empacotados.
2. **Dockerfile custom** em cima da imagem `postgis/postgis:15-3.3` que rode `apt-get install -y postgresql-15-pgvector`.

Nada disso está feito hoje.

### 7.5 Dependências Python relacionadas (requirements.txt na íntegra)

```
fastapi
uvicorn[standard]
pydantic
pydantic-settings
email-validator
sqlalchemy
sqlalchemy-utils
alembic
psycopg2-binary
redis
celery
python-multipart
python-jose[cryptography]
passlib[bcrypt]
boto3
GeoAlchemy2
fpdf2
litellm
mempalace>=3.0.0
httpx
slowapi>=0.1.9
pytest
pytest-cov
testcontainers[postgres]
ruff
mypy
```

**Não há** `pgvector`, `sentence-transformers`, `openai` (direto), `chromadb` explícito, `langchain`, `llama-index`. MemPalace traz o Chroma embarcado como dependência indireta.

### 7.6 Storage do MemPalace em disco

**Local observado:** `C:\Users\Administrador\.mempalace\` (equivalente a `~/.mempalace/` em Unix).

```
~/.mempalace/
├── config.json
├── knowledge_graph.sqlite3          (KG — 2 entities, 1 triple)
├── knowledge_graph.sqlite3-shm
├── knowledge_graph.sqlite3-wal
├── palace/
│   ├── chroma.sqlite3               (20 MB — 3471 embeddings)
│   └── 0a68bdbf-b38c-4dce-856e-1dd0c7dbe745/
│       ├── data_level0.bin          (4.8 MB)
│       ├── header.bin               (1 KB)
│       ├── index_metadata.pickle    (368 KB)
│       ├── length.bin               (12 KB)
│       └── link_lists.bin           (28 KB)
└── wal/
```

**Tamanho total:** `~25 MB` (`du -sh ~/.mempalace/palace/` retornou `25M`).

**Contagem de arquivos dentro de `palace/`:** `6` arquivos (1 sqlite + 5 arquivos do índice HNSW do Chroma).

**Documentos indexados:** `3471` embeddings em uma única collection `mempalace_drawers`, distribuídos principalmente em rooms de ingestão de código-fonte (ver 3.5).

---

## 8. Métricas de Custo Atual

### 8.1 Schema da tabela `ai_jobs`

`app/models/ai_job.py`:

```python
class AIJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class AIJobType(str, enum.Enum):
    classify_demand = "classify_demand"
    extract_document = "extract_document"
    generate_proposal = "generate_proposal"
    generate_dossier_summary = "generate_dossier_summary"
    diagnostico_propriedade = "diagnostico_propriedade"
    consulta_regulatoria = "consulta_regulatoria"
    gerar_documento = "gerar_documento"
    analise_financeira = "analise_financeira"
    acompanhamento_processo = "acompanhamento_processo"
    monitoramento_vigia = "monitoramento_vigia"
    gerar_conteudo_marketing = "gerar_conteudo_marketing"
    embedding_generation = "embedding_generation"
    enquadramento_regulatorio = "enquadramento_regulatorio"
    monitoramento_legislacao = "monitoramento_legislacao"


class AIJob(Base):
    __tablename__ = "ai_jobs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    entity_type = Column(String(50), nullable=True)
    entity_id = Column(Integer, nullable=True)

    job_type = Column(Enum(AIJobType), nullable=False, index=True)
    status = Column(Enum(AIJobStatus), nullable=False, default=AIJobStatus.pending, index=True)

    model_used = Column(String(100), nullable=True)
    provider = Column(String(50), nullable=True)
    tokens_in = Column(Integer, nullable=True)
    tokens_out = Column(Integer, nullable=True)
    cost_usd = Column(Float, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    input_payload = Column(PortableJSON, nullable=True)
    result = Column(PortableJSON, nullable=True)
    raw_output = Column(Text, nullable=True)
    error = Column(Text, nullable=True)

    agent_name = Column(String(50), nullable=True, index=True)
    chain_trace_id = Column(String(32), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
```

Campos relevantes para análise de custo: `agent_name`, `model_used`, `provider`, `tokens_in`, `tokens_out`, `cost_usd`, `duration_ms`, `created_at`, `status`.

### 8.2 Queries de custo (últimos 30 dias)

**Custo médio por agente (30d):**

```sql
SELECT
  agent_name,
  COUNT(*) AS jobs,
  COUNT(*) FILTER (WHERE status = 'completed') AS completed,
  AVG(cost_usd)::numeric(10,6) AS avg_cost,
  AVG(cost_usd) FILTER (WHERE status = 'completed')::numeric(10,6) AS avg_cost_completed,
  SUM(cost_usd)::numeric(10,4) AS total_cost,
  AVG(duration_ms)::int AS avg_duration_ms,
  AVG(tokens_in)::int AS avg_tokens_in,
  AVG(tokens_out)::int AS avg_tokens_out
FROM ai_jobs
WHERE created_at >= NOW() - INTERVAL '30 days'
  AND agent_name IS NOT NULL
GROUP BY agent_name
ORDER BY total_cost DESC NULLS LAST;
```

**Top 5 agentes mais caros:**

```sql
SELECT
  agent_name,
  SUM(cost_usd)::numeric(10,4) AS total_cost,
  COUNT(*) AS jobs,
  (SUM(cost_usd) / NULLIF(COUNT(*), 0))::numeric(10,6) AS cost_per_job,
  AVG(tokens_in)::int AS avg_tokens_in
FROM ai_jobs
WHERE created_at >= NOW() - INTERVAL '30 days'
  AND agent_name IS NOT NULL
  AND cost_usd IS NOT NULL
GROUP BY agent_name
ORDER BY total_cost DESC NULLS LAST
LIMIT 5;
```

**Modelo mais caro em uso e share do total:**

```sql
WITH total AS (
  SELECT SUM(cost_usd) AS grand_total
  FROM ai_jobs
  WHERE created_at >= NOW() - INTERVAL '30 days' AND cost_usd IS NOT NULL
)
SELECT
  model_used,
  provider,
  COUNT(*) AS jobs,
  SUM(cost_usd)::numeric(10,4) AS total_cost,
  (SUM(cost_usd) * 100.0 / (SELECT grand_total FROM total))::numeric(5,2) AS pct_of_total
FROM ai_jobs
WHERE created_at >= NOW() - INTERVAL '30 days'
  AND cost_usd IS NOT NULL
  AND model_used IS NOT NULL
GROUP BY model_used, provider
ORDER BY total_cost DESC NULLS LAST;
```

**Evolução diária (para detectar tendências):**

```sql
SELECT
  DATE_TRUNC('day', created_at)::date AS day,
  COUNT(*) AS jobs,
  SUM(cost_usd)::numeric(10,4) AS daily_cost,
  COUNT(DISTINCT tenant_id) AS active_tenants
FROM ai_jobs
WHERE created_at >= NOW() - INTERVAL '30 days' AND cost_usd IS NOT NULL
GROUP BY 1
ORDER BY 1 DESC;
```

**RESULTADO (executado 2026-04-23 — janela de dados: 2026-04-03 → 2026-04-21, span total de 18 dias 19h):**

**Custo médio + total por agente (30d):**

```
 agent_name  | total_cost_30d | jobs_30d | cost_per_job | avg_tokens_in
-------------+----------------+----------+--------------+---------------
 legislacao  |         0.0025 |        4 |     0.000632 |           519
 diagnostico |         0.0008 |        4 |     0.000201 |           315
```

> Apenas 2 agentes produziram jobs com custo monetário: `legislacao` e `diagnostico`. Os demais (atendimento, extrator, vigia, acompanhamento) registram execuções com `cost_usd=0` ou `NULL` (provavelmente caminhos sem-LLM / falhas antes de chamar o gateway).

**Top 5 agentes mais caros:**

Só há 2 agentes com custo real. Ranking completo:

```
 1. legislacao  — $0.0025 total (4 jobs, $0.000632/job, 519 tokens in avg)
 2. diagnostico — $0.0008 total (4 jobs, $0.000201/job, 315 tokens in avg)
```

**Modelo mais caro em uso:**

```
 model_used  | provider | jobs | total_cost | pct_of_total
-------------+----------+------+------------+--------------
 gpt-4o-mini | gpt      |    9 |     0.0035 |       100.00
```

> **100% do custo registrado foi em `gpt-4o-mini`.** Gemini 2.0 Flash não aparece nas métricas (apesar de ser configurado como default do agente legislação pela Sprint O) — significa que **`GEMINI_API_KEY` não está populada no `.env` local**, e o fallback chain caiu para OpenAI em todas as 9 execuções. Portanto a decisão arquitetural "Gemini default pra legislação" (Sprint O) **não está sendo aplicada em runtime** com a configuração atual.

**Detalhamento completo de jobs (24 no total):**

```
      agent       |        job_type         |  status   | jobs | avg_cost | total_cost | avg_ms | avg_in | avg_out
------------------+-------------------------+-----------+------+----------+------------+--------+--------+---------
 legislacao       | consulta_regulatoria    | completed |    4 | 0.000632 |     0.0025 |  22343 |    519 |     923
 diagnostico      | diagnostico_propriedade | completed |    4 | 0.000201 |     0.0008 |  16970 |    315 |     256
 [sem agent_name] | classify_demand         | completed |    1 | 0.000123 |     0.0001 |   6110 |    307 |     129
 vigia            | monitoramento_vigia     | completed |    1 | 0.000000 |     0.0000 |    262 |      0 |       0
 extrator         | extract_document        | failed    |    1 | 0.000000 |     0.0000 |    104 |      0 |       0
 acompanhamento   | acompanhamento_processo | completed |    1 | 0.000000 |     0.0000 |     14 |      0 |       0
 atendimento      | classify_demand         | completed |    4 | 0.000000 |     0.0000 |   3747 |      0 |       0
 extrator         | extract_document        | completed |    4 | 0.000000 |     0.0000 |      1 |      0 |       0
 diagnostico      | diagnostico_propriedade | failed    |    4 | 0.000000 |     0.0000 |   3015 |      0 |       0
```

**Observações:**
- `legislacao` é caro em latência (22.3s de média — despeja contexto grande mesmo sem docs na base, provavelmente chain completa com memória).
- `atendimento` registra `tokens_in=0` e `tokens_out=0` mas `duration_ms=3747` — o classifier usa path de regras estáticas (sem LLM) quando `confidence != low`.
- 4 falhas de `diagnostico_propriedade` e 1 de `extract_document` — precisa investigar.

**Amostra de raw_output real de uma chamada completada:**

```
id=23 agent=legislacao model=gpt-4o-mini cost=0.00058 tokens_in=441 tokens_out=855
raw_output (primeiros 200 chars):
```json
{
  "caminho_regulatorio": "Análise preliminar e identificação do tipo de demanda para definição do enquadramento regulatório adequado.",
  "orgao_competente": "Órgão Ambiental Estadual ou Mun
```
```

### 8.3 Observação crítica sobre dados de custo disponíveis

**Confirmado pelo banco live:** 24 jobs totais, 18 dias de span, custo acumulado = **$0.0035 USD**. Isso é **volume de smoke-test**, não produção. Propriedades: 7 totais, 0 com geom, 3 com CAR. Propostas: 4 (todas accepted, todos seed). Contratos: 4 (todos draft). Tenants: 3. Legislação: 0 docs indexados.

**Implicações para análises externas:**
- Não há corpus histórico real para modelar padrões de custo por demand_type em escala.
- Análise deve ser baseada em custos **esperados** (preços por modelo da OpenAI/Gemini/Anthropic) × volumes **projetados**, não em observação histórica.
- O RAG de casos requer ingestão prévia de dados reais ou simulação.

### 8.4 Controles de custo ativos hoje (pós Sprint R)

Três camadas de guardrails:

1. **Por job:** `AI_MAX_COST_PER_JOB_USD = 0.10` em `settings`. *(Observação: apesar de declarado no settings, não encontrei ainda o ponto de aplicação desse limite por-job no `ai_gateway.complete()` — a variável existe mas pode não estar enforced; revisar.)*
2. **Por hora por tenant:** `check_tenant_cost_limit` em `ai_gateway.py:41` → HTTP 429 se soma do últim hora ≥ `AI_HOURLY_COST_LIMIT_USD=5.0`.
3. **Por mês por tenant:** `check_tenant_monthly_budget` em `ai_gateway.py:116` → HTTP 429 se soma do mês ≥ `Tenant.ai_monthly_budget_usd` (com fallback para `AI_BUDGET_USD_MONTHLY_PER_TENANT_DEFAULT=0` que significa ilimitado).

Ambos `check_tenant_cost_limit` e `check_tenant_monthly_budget` são chamados em `BaseAgent.run()` (linhas 136-137), cobrindo 100% dos agentes, e em `/ai/classify`, `/ai/extract`, `/ai/jobs/*-async`.

**Sprint R endpoint `GET /api/v1/agents/budget`:**

```json
{
  "used_usd": 0.0123,
  "limit_usd": 10.0,
  "pct": 12.3,
  "unlimited": false,
  "alert": false,
  "period_end": "2026-05-01T00:00:00+00:00"
}
```

`alert=true` quando `used >= 0.8 * limit`.

---

## Anexo A — Triggers automáticos dos agentes (mapa completo)

| Agente | Quando roda | Onde no código |
|---|---|---|
| atendimento | Automático em `POST /intake/create-case` se `description ≥10` chars | `app/api/v1/intake.py:~311` |
| extrator | Automático em `POST /documents/confirm-upload` (doc_types: matricula/car/ccir/auto_infracao/licenca) | `app/api/v1/documents.py:~209` |
| extrator | Automático em `POST /intake/drafts/{id}/import-documents` (por doc) | `app/api/v1/intake.py:~810` |
| diagnostico | Transição macroetapa `diagnostico_tecnico` → chain `diagnostico_completo` | `app/api/v1/processes.py:~615` |
| legislacao | Só via chains: `diagnostico_completo`, `enquadramento_regulatorio`, `analise_regulatoria`. Crawlers (DOU/DOE/IBAMA) **não chamam o agente**, só ingerem docs | `app/workers/legislation_tasks.py` |
| orcamento | Transição macroetapa `orcamento_negociacao` → chain `gerar_proposta` | `app/api/v1/processes.py:~615` |
| redator | Só via chain `gerar_documento` ou `/agents/run` manual | — |
| financeiro | Só via chain `analise_financeira` ou `/agents/run` manual | — |
| acompanhamento | Celery Beat **a cada 30min**, loop em processos `aguardando_orgao` | `app/core/celery_app.py:44-47` + `app/workers/agent_tasks.py:~244` |
| vigia | Celery Beat **a cada 6h:15** loop em tenants | `app/core/celery_app.py:40-43` + `app/workers/agent_tasks.py:~206` |
| marketing | Só via chain `marketing_content` ou `/agents/run` manual | — |

**Endpoints manuais (aplicam a todos):**

| Endpoint | Uso |
|---|---|
| `POST /api/v1/agents/run` | Executa agente sync |
| `POST /api/v1/agents/run-async` | Enfileira via Celery (HTTP 202) |
| `POST /api/v1/agents/chain` | Executa chain sync |
| `POST /api/v1/agents/chain-async` | Enfileira chain via Celery (HTTP 202) |
| `GET /api/v1/agents/registry` | Lista 10 agentes |
| `GET /api/v1/agents/chains` | Lista 9 chains |
| `GET /api/v1/agents/budget` | Sprint R: uso/limite/pct mensal |

---

## Anexo B — Celery Beat Schedule (completo)

`app/core/celery_app.py:27-53`:

```python
beat_schedule={
    "monitor-legislation-dou-daily": {
        "task": "workers.monitor_legislation_dou",
        "schedule": crontab(hour=6, minute=0),  # 06:00 BRT diario
    },
    "monitor-legislation-doe-daily": {
        "task": "workers.monitor_legislation_doe",
        "schedule": crontab(hour=6, minute=30),  # 06:30 BRT diario
    },
    "monitor-legislation-agencies-weekly": {
        "task": "workers.monitor_legislation_agencies",
        "schedule": crontab(hour=3, minute=0, day_of_week=1),  # segunda 03:00
    },
    "vigia-scheduled-check": {
        "task": "workers.vigia_all_tenants",
        "schedule": crontab(hour="*/6", minute=15),  # a cada 6h, minuto 15
    },
    "acompanhamento-check-processes": {
        "task": "workers.acompanhamento_check_all",
        "schedule": crontab(minute="*/30"),  # a cada 30 minutos
    },
    "cleanup-expired-intake-drafts": {
        "task": "workers.cleanup_expired_intake_drafts",
        "schedule": crontab(hour=2, minute=30),  # 02:30 BRT diário (off-peak)
    },
},
```

---

## Anexo C — Resumo executivo para análise externa

### C.1 Três frentes declaradas pelo user

1. ~~**Expansão do MemPalace com recall ativo em 8 agentes hoje passivos**~~
   **REVOGADA em 2026-04-23.** O pacote `mempalace` foi abandonado por supply-chain
   red flags. Nova formulação da frente 1: **construir memória de agentes em pgvector**
   e pluggar nas assinaturas preservadas em `app/agents/memory.py` (agora no-op stub).
2. **RAG de casos com pgvector** (agora funde com a frente 1 — pgvector é o backend
   único de memória do produto).
3. **Otimização de custo de tokens.**

### C.2 Sinais relevantes detectados (confirmados por queries live)

- **MemPalace está 99.7% vazio de dados de agentes.** Dos 3471 embeddings, só **10** são de diário de agentes — todas `[INIT]` de 2026-04-09. Os demais 3461 são ingestão de código-fonte (room `app` 1931, `frontend` 641 etc.). **Recall de `diagnostico` e `legislacao` atualmente retorna entradas INIT** (basicamente inócuo).
- **Knowledge Graph tem 1 única triple** (`amigao_system has_agent_count 10` de setup).
- **pgvector não está instalado** (confirmado via `pg_extension`): só PostGIS 3.3.4 + fuzzystrmatch. Migração requer mudança de imagem OU Dockerfile custom.
- **Legislação: 0 documentos indexados no banco.** Isso é o **achado mais crítico** — toda a infra de crawlers/search/context existe, mas a tabela `legislation_documents` está vazia. **RAG de legislação não faz sentido antes de popular a base.** O agente `legislacao` roda hoje só com conhecimento do LLM.
- **`search_legislation` ignora o argumento `demand_type`** — filtro declarado mas não aplicado (bug latente, mas moot enquanto não há docs).
- **Gemini não está sendo usado em produção** apesar da decisão Sprint O. **100% dos $0.0035 gastos foi em gpt-4o-mini.** A `GEMINI_API_KEY` provavelmente não está no `.env` local, e o fallback chain vai pra OpenAI.
- **PostGIS está 100% dormindo.** 7 propriedades, **0 com geom preenchida**. Zero operações `ST_*` no código.
- **Redator nunca rodou em produção.** 0 jobs com `job_type='gerar_documento'`. 4 contratos existem mas são seeds draft, não artefatos gerados pelo LLM.
- **Custo acumulado em 18 dias: $0.0035** (smoke). Modelagem de escala deve ser prospectiva, não retrospectiva.
- **Nenhum agente tem temperature/max_tokens override específico**, exceto `redator` (max_tokens=4096) e `legislacao` (usa `CLAUDE_LEGAL_MAX_TOKENS=4096` e `GEMINI_LEGAL_MODEL`).
- **Cost control tem 3 camadas** (por job, por hora, por mês) mas o "por job" (`AI_MAX_COST_PER_JOB_USD=0.10`) pode não estar enforced no gateway.

### C.3 Estado do código nos últimos 2 dias (commits)

```
3b27516 feat: Sprint R — orçamento mensal de IA por tenant
c33c4ad refactor(ui): Kanban legado removido + barra de tabs horizontal + refino PT-BR
0d34b0f docs: fechar sessão 2026-04-21 — refino UI documentado + plano Camada 4 revisado
5001a89 fix: refinamento UI — JSX text bugs (\u00XX literais) + termos técnicos em PT-BR natural
b71307d feat: Sprint O — Camada 4 quick wins (Gemini default + métricas por agente)
```

---

**Fim do documento. Qualquer item marcado "RESULTADO PENDENTE" requer `docker compose up -d db` + psql para preencher.**
