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
from typing import Any
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

    def __init__(self, ctx: AgentContext) -> None:
        self.ctx = ctx
        self._started_at: float = 0.0
        self._llm_response: AIResponse | None = None
        # Dívida #33: auditamos o uso da api_key do consultor no máximo uma vez
        # por execução de agente (call_llm pode ser chamado mais de uma vez).
        self._ai_key_audited: bool = False

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

            # 9. Sprint O — telemetria Prometheus por execução de agente
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
            error_message = str(exc) or exc.__class__.__name__
            self._fail_job(job, exc)
            emit_agent_event(self.name, "failed", self.ctx, error=error_message)

            # Sprint O — telemetria Prometheus (falha)
            record_agent_execution(
                agent_name=self.name,
                result="failure",
                duration_seconds=elapsed_ms / 1000.0,
                tenant_id=self.ctx.tenant_id,
                cost_usd=float(job.cost_usd) if job and job.cost_usd else None,
            )

            logger.error("agent.%s failed error=%s ms=%d", self.name, error_message, elapsed_ms)
            return AgentResult(
                success=False,
                data={},
                confidence="low",
                ai_job_id=job.id if job else None,
                suggestions=[],
                requires_review=False,
                agent_name=self.name,
                duration_ms=elapsed_ms,
                error=error_message,
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
        """Wrapper sobre ai_gateway.complete(). Armazena resposta em _llm_response.

        Sprint A1 A — antes de chamar o gateway, injeta no ``system`` as skills
        procedurais que casarem com o contexto atual (``ctx.metadata`` + ``self.name``).
        Quando nenhuma skill casa, comportamento idêntico ao anterior.
        """
        composed_system = self._compose_system_with_skills(system)
        # White label (André 2026-05-28): se o consultor configurou provider+chave
        # própria, o gateway usa a combinação dele. Senão (None), default global.
        user_prefs = kwargs.pop("user_preferences", None)
        if user_prefs is None:
            user_prefs = self._resolve_user_ai_preferences()
        # Dívida #33: a chave do consultor está prestes a ser usada — audita o
        # ato (mascarada), uma vez por execução. Default global (None) não audita.
        if user_prefs and not self._ai_key_audited:
            self._audit_ai_key_use(user_prefs)
            self._ai_key_audited = True
        response = complete(prompt, system=composed_system, user_preferences=user_prefs, **kwargs)
        self._llm_response = response
        return response

    def _audit_ai_key_use(self, prefs: dict) -> None:
        """Registra no AuditLog o uso da api_key do consultor (dívida #33).

        Mascara a chave antes de passar adiante — plaintext nunca sai daqui.
        Best-effort: nada nesta auditoria pode derrubar a execução do agente.
        """
        try:
            from app.agents.events import emit_ai_key_use_event  # noqa: PLC0415

            key = (prefs or {}).get("api_key") or ""
            masked = f"…{key[-4:]}" if len(key) >= 4 else ("****" if key else None)
            emit_ai_key_use_event(
                self.name,
                self.ctx,
                provider=(prefs or {}).get("provider"),
                model=(prefs or {}).get("model"),
                api_key_masked=masked,
            )
        except Exception as exc:  # pragma: no cover - defensivo
            logger.warning("agent.%s: falha ao auditar uso de api_key: %s", self.name, exc)

    def _resolve_user_ai_preferences(self) -> dict | None:
        """Resolve {provider, model, api_key} do usuário da chain (ctx.user_id).

        Sem user_id/session no contexto, ou config incompleta → None (default global).
        Best-effort: qualquer falha cai no comportamento global.
        """
        uid = getattr(self.ctx, "user_id", None)
        session = getattr(self.ctx, "session", None)
        if not uid or session is None:
            return None
        try:
            from app.models.user import User  # noqa: PLC0415
            from app.services.user_preferences import get_ai_runtime  # noqa: PLC0415
            user = session.get(User, uid)
            return get_ai_runtime(user) if user else None
        except Exception:
            return None

    # --- Skills (Sprint A1 A) ----------------------------------------------

    def _load_skills_for_context(self) -> list:
        """Retorna a lista de skills aplicáveis ao agente + ``ctx.metadata`` atual.

        Lê de ``self.name`` e ``self.ctx.metadata`` (sem dict paralelo). Falhas no
        registry são silenciadas para não derrubar o agente.
        """
        from app.skills import (  # noqa: PLC0415
            SkillContent,
            discover_skills,
            load_skill,
        )
        from app.skills._registry import matches_context  # noqa: PLC0415

        try:
            catalog = discover_skills()
        except Exception as exc:
            logger.warning("agent.%s: skill discovery falhou: %s", self.name, exc)
            return []

        ctx_meta = self.ctx.metadata or {}
        applicable: list[SkillContent] = []
        for meta in catalog.values():
            if not matches_context(meta, agent=self.name, ctx_metadata=ctx_meta):
                continue
            try:
                content = load_skill(meta.name)
            except Exception as exc:
                logger.warning(
                    "agent.%s: skill '%s' inválida em %s: %s",
                    self.name, meta.name, meta.path, exc,
                )
                continue
            if content is not None:
                applicable.append(content)
        return applicable

    def _compose_system_with_skills(self, base_system: str) -> str:
        """Anexa skills aplicáveis ao system prompt, preservando o original."""
        skills = self._load_skills_for_context()
        if not skills:
            return base_system

        parts: list[str] = [base_system.rstrip()] if base_system else []
        parts.append("<!-- skills:start -->")
        for skill in skills:
            header = f"=== Skill: {skill.metadata.name} v{skill.metadata.version} ==="
            parts.append(header)
            parts.append(skill.body)
        parts.append("<!-- skills:end -->")
        return "\n\n".join(p for p in parts if p)

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
        """Marca AIJob como failed.

        Sprint -1 B — quando a falha é AIGatewayError (cost_exceeded), preserva
        cost_usd/tokens/model para auditoria do limite financeiro.
        """
        if job is None:
            return
        from datetime import UTC, datetime  # noqa: PLC0415

        from app.core.ai_gateway import AIGatewayError  # noqa: PLC0415

        try:
            job.status = AIJobStatus.failed
            job.error = str(getattr(exc, "message", exc))[:2000]
            job.finished_at = datetime.now(UTC)
            job.duration_ms = int((time.monotonic() - self._started_at) * 1000)

            if isinstance(exc, AIGatewayError):
                if exc.cost_usd:
                    job.cost_usd = exc.cost_usd
                if exc.tokens_in:
                    job.tokens_in = exc.tokens_in
                if exc.tokens_out:
                    job.tokens_out = exc.tokens_out
                if exc.model_used:
                    job.model_used = exc.model_used

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
