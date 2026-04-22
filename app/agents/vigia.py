"""
VigiaAgent — Monitoramento agendado.

Verifica prazos de tarefas, validade de documentos, processos parados
e custos de IA. Roda via Celery Beat periodicamente.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.agents.base import AgentRegistry, BaseAgent
from app.models.ai_job import AIJobType


@AgentRegistry.register
class VigiaAgent(BaseAgent):
    name = "vigia"
    description = "Monitora prazos, validade de documentos e processos parados — gera alertas automáticos"
    job_type = AIJobType.monitoramento_vigia
    prompt_slugs = ["vigia_system"]
    palace_room = "agent_vigia"

    def execute(self) -> dict[str, Any]:
        """Executa verificacoes sem LLM — apenas queries e regras."""
        check_type = self.ctx.metadata.get("check_type", "all")

        alerts: list[dict[str, Any]] = []

        if check_type in ("deadlines", "all"):
            alerts.extend(self._check_task_deadlines())

        if check_type in ("documents", "all"):
            alerts.extend(self._check_document_expiry())

        if check_type in ("process_status", "all"):
            alerts.extend(self._check_stale_processes())

        if check_type in ("billing", "all"):
            alerts.extend(self._check_ai_cost_alerts())

        return {
            "alerts": alerts,
            "check_type": check_type,
            "alerts_count": len(alerts),
            "confidence": "high",  # Sem LLM, dados factuais
        }

    def _check_task_deadlines(self) -> list[dict[str, Any]]:
        """Tarefas vencidas ou prestes a vencer."""
        from app.models.task import Task, TaskStatus  # noqa: PLC0415

        now = datetime.now(UTC)
        soon = now + timedelta(days=3)
        terminal = [TaskStatus.concluida, TaskStatus.cancelada]

        base_filter = [
            Task.tenant_id == self.ctx.tenant_id,
            Task.status.notin_(terminal),
            Task.due_date.isnot(None),
        ]

        overdue = (
            self.ctx.session.query(Task)
            .filter(*base_filter, Task.due_date < now)
            .limit(50)
            .all()
        )
        upcoming = (
            self.ctx.session.query(Task)
            .filter(*base_filter, Task.due_date.between(now, soon))
            .limit(50)
            .all()
        )

        alerts: list[dict[str, Any]] = []
        for t in overdue:
            alerts.append({
                "type": "task_overdue",
                "severity": "error",
                "task_id": t.id,
                "process_id": t.process_id,
                "title": t.title,
                "due_date": str(t.due_date),
                "message": f"Tarefa '{t.title}' vencida desde {t.due_date}",
            })
        for t in upcoming:
            alerts.append({
                "type": "task_approaching",
                "severity": "warning",
                "task_id": t.id,
                "process_id": t.process_id,
                "title": t.title,
                "due_date": str(t.due_date),
                "message": f"Tarefa '{t.title}' vence em breve: {t.due_date}",
            })
        return alerts

    def _check_document_expiry(self) -> list[dict[str, Any]]:
        """Documentos prestes a expirar."""
        from app.models.document import Document  # noqa: PLC0415

        now = datetime.now(UTC)
        soon = now + timedelta(days=30)

        expiring = (
            self.ctx.session.query(Document)
            .filter(
                Document.tenant_id == self.ctx.tenant_id,
                Document.expires_at.isnot(None),
                Document.expires_at.between(now, soon),
                Document.deleted_at.is_(None),
            )
            .limit(50)
            .all()
        )

        return [
            {
                "type": "document_expiring",
                "severity": "warning",
                "document_id": d.id,
                "process_id": d.process_id,
                "document_type": d.document_type,
                "expires_at": str(d.expires_at),
                "message": f"Documento '{d.document_type}' expira em {d.expires_at}",
            }
            for d in expiring
        ]

    def _check_stale_processes(self) -> list[dict[str, Any]]:
        """Processos parados ha mais de 30 dias em aguardando_orgao."""
        from app.models.process import Process, ProcessStatus  # noqa: PLC0415

        stale_threshold = datetime.now(UTC) - timedelta(days=30)

        stale = (
            self.ctx.session.query(Process)
            .filter(
                Process.tenant_id == self.ctx.tenant_id,
                Process.status == ProcessStatus.aguardando_orgao,
                Process.updated_at < stale_threshold,
                Process.deleted_at.is_(None),
            )
            .limit(50)
            .all()
        )

        return [
            {
                "type": "process_stale",
                "severity": "warning",
                "process_id": p.id,
                "title": p.title,
                "status": p.status.value,
                "last_updated": str(p.updated_at),
                "message": f"Processo '{p.title}' parado em aguardando_orgao ha mais de 30 dias",
            }
            for p in stale
        ]

    def _check_ai_cost_alerts(self) -> list[dict[str, Any]]:
        """Tenant se aproximando do limite de custo de IA."""
        from sqlalchemy import func as sqlfunc  # noqa: PLC0415

        from app.core.ai_gateway import AI_HOURLY_COST_LIMIT_USD  # noqa: PLC0415
        from app.models.ai_job import AIJob  # noqa: PLC0415

        one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
        cost = (
            self.ctx.session.query(sqlfunc.coalesce(sqlfunc.sum(AIJob.cost_usd), 0.0))
            .filter(
                AIJob.tenant_id == self.ctx.tenant_id,
                AIJob.created_at >= one_hour_ago,
            )
            .scalar()
        ) or 0.0

        alerts: list[dict[str, Any]] = []
        threshold = AI_HOURLY_COST_LIMIT_USD * 0.8  # 80% do limite
        if cost >= threshold:
            alerts.append({
                "type": "ai_cost_warning",
                "severity": "error" if cost >= AI_HOURLY_COST_LIMIT_USD else "warning",
                "cost_usd": float(cost),
                "limit_usd": AI_HOURLY_COST_LIMIT_USD,
                "percentage": round(cost / AI_HOURLY_COST_LIMIT_USD * 100, 1),
                "message": f"Custo de IA na ultima hora: ${cost:.2f} / ${AI_HOURLY_COST_LIMIT_USD:.2f}",
            })
        return alerts

    def _fallback_prompts(self) -> dict[str, str]:
        return {
            "vigia_system": "Agente de monitoramento — opera por regras, sem LLM.",
        }
