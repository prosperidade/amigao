"""
Agent Framework — Base classes.

BaseAgent (ABC), AgentContext, AgentResult, AgentRegistry.
Cada agente herda BaseAgent e implementa execute().
O metodo run() e um template method que cuida de:
  cost check → preconditions → create job → execute → validate → persist → emit event.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.ai_gateway import (
    AIResponse,
    check_tenant_cost_limit,
    check_tenant_monthly_budget,
    complete,
)
from app.models.ai_job import AIJob, AIJobStatus, AIJobType
from app.services.prompt_service import get_active_prompt, render_prompt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AgentContext:
    """Contexto compartilhado entre agentes. Session e caller-owned."""

    tenant_id: int
    user_id: int | None
    process_id: int | None
    session: Session
    metadata: dict[str, Any] = field(default_factory=dict)
    chain_data: dict[str, Any] = field(default_factory=dict)
    trace_id: str = field(default_factory=lambda: uuid4().hex[:16])


@dataclass
class AgentResult:
    """Resultado padronizado retornado por todo agente."""

    success: bool
    data: dict[str, Any]
    confidence: str  # "high" | "medium" | "low"
    ai_job_id: int | None
    suggestions: list[str]
    requires_review: bool
    agent_name: str
    duration_ms: int
    error: str | None = None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class AgentRegistry:
    """Singleton registry para descobrir e instanciar agentes."""

    _agents: dict[str, type[BaseAgent]] = {}

    @classmethod
    def register(cls, agent_cls: type[BaseAgent]) -> type[BaseAgent]:
        """Decorator: @AgentRegistry.register"""
        cls._agents[agent_cls.name] = agent_cls
        return agent_cls

    @classmethod
    def get(cls, name: str) -> type[BaseAgent] | None:
        return cls._agents.get(name)

    @classmethod
    def list_agents(cls) -> list[dict[str, str]]:
        return [
            {"name": a.name, "description": a.description}
            for a in cls._agents.values()
        ]

    @classmethod
    def create(cls, name: str, ctx: AgentContext) -> BaseAgent:
        agent_cls = cls._agents.get(name)
        if not agent_cls:
            raise ValueError(f"Agente '{name}' nao registrado. Disponiveis: {list(cls._agents.keys())}")
        return agent_cls(ctx)


# ---------------------------------------------------------------------------
# Base Agent
# ---------------------------------------------------------------------------

class BaseAgent(ABC):
    """Classe base abstrata para todos os agentes."""

    # Subclasses DEVEM definir estes atributos de classe
    name: str
    description: str
    job_type: AIJobType
    prompt_slugs: list[str] = []
    confidence_threshold: float = 0.7
    palace_room: str = "agents_core"  # MemPalace room — override per agent

    def __init__(self, ctx: AgentContext) -> None:
        self.ctx = ctx
        self._started_at: float = 0.0
        self._llm_response: AIResponse | None = None

    # --- Template method ---------------------------------------------------

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

        # 2. Preconditions
        self.validate_preconditions()

        # 3. Create running job
        job = self._create_running_job()

        self._started_at = time.monotonic()
        try:
            # 4. Execute
            raw_result = self.execute()

            # 5. Validate output
            validated = self.validate_output(raw_result)

            elapsed_ms = int((time.monotonic() - self._started_at) * 1000)

            # 6. Determine confidence and review need
            confidence = self._extract_confidence(validated)
            requires_review = self._needs_review(confidence, validated)

            result = AgentResult(
                success=True,
                data=validated,
                confidence=confidence,
                ai_job_id=job.id if job else None,
                suggestions=validated.get("suggestions", []) if isinstance(validated.get("suggestions"), list) else [],
                requires_review=requires_review,
                agent_name=self.name,
                duration_ms=elapsed_ms,
            )

            # 7. Complete job
            self._complete_job(job, result)

            # 8. Emit event
            emit_agent_event(self.name, "completed", self.ctx, result=result)

            # 9. MemPalace: log execution to diary + knowledge graph
            self._mempalace_log(result, validated)

            # 10. Sprint O — telemetria Prometheus por execução de agente
            record_agent_execution(
                agent_name=self.name,
                result="success",
                duration_seconds=elapsed_ms / 1000.0,
                tenant_id=self.ctx.tenant_id,
                cost_usd=float(job.cost_usd) if job and job.cost_usd else None,
            )

            logger.info(
                "agent.%s completed confidence=%s review=%s ms=%d job_id=%s",
                self.name, confidence, requires_review, elapsed_ms, job.id if job else None,
            )
            return result

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - self._started_at) * 1000)
            self._fail_job(job, exc)
            emit_agent_event(self.name, "failed", self.ctx, error=str(exc))

            # MemPalace: log failure
            self._mempalace_log_failure(str(exc), elapsed_ms)

            # Sprint O — telemetria Prometheus (falha)
            record_agent_execution(
                agent_name=self.name,
                result="failure",
                duration_seconds=elapsed_ms / 1000.0,
                tenant_id=self.ctx.tenant_id,
                cost_usd=float(job.cost_usd) if job and job.cost_usd else None,
            )

            logger.error("agent.%s failed error=%s ms=%d", self.name, exc, elapsed_ms)
            return AgentResult(
                success=False,
                data={},
                confidence="low",
                ai_job_id=job.id if job else None,
                suggestions=[],
                requires_review=False,
                agent_name=self.name,
                duration_ms=elapsed_ms,
                error=str(exc),
            )

    # --- Abstract methods (subclasses implementam) -------------------------

    @abstractmethod
    def execute(self) -> dict[str, Any]:
        """Logica principal do agente. Retorna dict com resultado."""
        ...

    @abstractmethod
    def _fallback_prompts(self) -> dict[str, str]:
        """Retorna dict slug -> prompt hardcoded para fallback."""
        ...

    # --- Hooks opcionais ---------------------------------------------------

    def validate_preconditions(self) -> None:
        """Override para checar dados obrigatorios antes da execucao."""
        pass

    def validate_output(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Override para validacao de dominio. Default: passa direto."""
        return raw

    def get_output_schema(self) -> dict | None:
        """JSON Schema para validacao de output. Carregado do PromptTemplate se disponivel."""
        return None

    # --- Helpers para subclasses -------------------------------------------

    def get_prompt(self, slug: str, variables: dict[str, str] | None = None) -> str:
        """Carrega prompt do banco via prompt_service, com fallback hardcoded."""
        tpl = get_active_prompt(slug, self.ctx.session, tenant_id=self.ctx.tenant_id)
        if tpl is not None:
            if variables:
                return render_prompt(tpl, variables)
            return tpl.content
        # Fallback
        fallbacks = self._fallback_prompts()
        content = fallbacks.get(slug, "")
        if not content:
            logger.warning("agent.%s: sem prompt para slug='%s'", self.name, slug)
            return ""
        if variables:
            for key, value in variables.items():
                content = content.replace(f"{{{key}}}", str(value))
        return content

    def call_llm(self, prompt: str, *, system: str = "", **kwargs: Any) -> AIResponse:
        """Wrapper sobre ai_gateway.complete(). Armazena resposta em _llm_response."""
        response = complete(prompt, system=system, **kwargs)
        self._llm_response = response
        return response

    # --- MemPalace integration -----------------------------------------------

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
        if self.ctx.chain_data:
            chain_agents = list(self.ctx.chain_data.keys())
            parts.append(f"chain_from={chain_agents}")
        return " ".join(parts)

    # --- Internals ---------------------------------------------------------

    def _create_running_job(self) -> AIJob | None:
        """Cria AIJob em status running."""
        from datetime import UTC, datetime  # noqa: PLC0415

        try:
            job = AIJob(
                tenant_id=self.ctx.tenant_id,
                created_by_user_id=self.ctx.user_id,
                entity_type="process" if self.ctx.process_id else "agent",
                entity_id=self.ctx.process_id,
                job_type=self.job_type,
                status=AIJobStatus.running,
                agent_name=self.name,
                chain_trace_id=self.ctx.trace_id,
                started_at=datetime.now(UTC),
            )
            self.ctx.session.add(job)
            self.ctx.session.flush()
            return job
        except Exception as exc:
            logger.warning("agent.%s: falha ao criar AIJob: %s", self.name, exc)
            return None

    def _complete_job(self, job: AIJob | None, result: AgentResult) -> None:
        """Atualiza AIJob com resultado e metricas LLM."""
        if job is None:
            return
        from datetime import UTC, datetime  # noqa: PLC0415

        try:
            job.status = AIJobStatus.completed
            job.result = result.data
            job.finished_at = datetime.now(UTC)
            job.duration_ms = result.duration_ms
            if self._llm_response:
                job.model_used = self._llm_response.model_used
                job.provider = self._llm_response.provider
                job.tokens_in = self._llm_response.tokens_in
                job.tokens_out = self._llm_response.tokens_out
                job.cost_usd = self._llm_response.cost_usd
                job.raw_output = self._llm_response.content
            self.ctx.session.flush()
        except Exception as exc:
            logger.warning("agent.%s: falha ao completar AIJob %s: %s", self.name, job.id, exc)

    def _fail_job(self, job: AIJob | None, exc: Exception) -> None:
        """Marca AIJob como failed."""
        if job is None:
            return
        from datetime import UTC, datetime  # noqa: PLC0415

        try:
            job.status = AIJobStatus.failed
            job.error = str(exc)[:2000]
            job.finished_at = datetime.now(UTC)
            job.duration_ms = int((time.monotonic() - self._started_at) * 1000)
            self.ctx.session.flush()
        except Exception as flush_exc:
            logger.warning("agent.%s: falha ao marcar AIJob %s como failed: %s", self.name, job.id, flush_exc)

    def _extract_confidence(self, data: dict[str, Any]) -> str:
        """Extrai confianca do resultado ou calcula com base nos dados."""
        if "confidence" in data:
            return str(data["confidence"])
        if "risco_estimado" in data:
            risk_map = {"baixo": "high", "medio": "medium", "alto": "low"}
            return risk_map.get(str(data["risco_estimado"]), "medium")
        return "medium"

    def _needs_review(self, confidence: str, data: dict[str, Any]) -> bool:
        """Determina se resultado precisa de revisao humana."""
        if data.get("requires_review") is True:
            return True
        return confidence == "low"
