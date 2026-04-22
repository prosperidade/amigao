"""
AcompanhamentoAgent — Monitoramento de email para respostas de orgaos.

Analisa mensagens recebidas (email, portal) para detectar respostas de
orgaos ambientais, extrair prazos e sugerir proximas acoes.
"""

from __future__ import annotations

import json
from typing import Any

from app.agents.base import AgentRegistry, BaseAgent
from app.agents.validators import OutputValidationPipeline
from app.models.ai_job import AIJobType


@AgentRegistry.register
class AcompanhamentoAgent(BaseAgent):
    name = "acompanhamento"
    description = "Monitora e-mails em busca de respostas de órgãos e rastreia o status dos processos"
    job_type = AIJobType.acompanhamento_processo
    prompt_slugs = ["acompanhamento_system", "acompanhamento_parse_email"]
    palace_room = "agent_acompanhamento"

    def validate_preconditions(self) -> None:
        message = self.ctx.metadata.get("message_content", "")
        if not message.strip() and not self.ctx.process_id:
            raise ValueError("'message_content' ou process_id necessario para acompanhamento")

    def execute(self) -> dict[str, Any]:
        from app.core.config import settings  # noqa: PLC0415

        message_content = self.ctx.metadata.get("message_content", "")
        message_source = self.ctx.metadata.get("message_source", "email")

        # Se temos process_id sem mensagem, verificar comunicacoes recentes
        if not message_content and self.ctx.process_id:
            message_content = self._load_recent_messages()
            if not message_content:
                return {
                    "is_agency_response": False,
                    "summary": "Sem mensagens recentes para analisar",
                    "action_required": False,
                }

        if not settings.ai_configured:
            return self._rules_based_parse(message_content)

        # Contexto do processo
        process_context = {}
        if self.ctx.process_id:
            process_context = self._load_process_context()

        system_prompt = self.get_prompt("acompanhamento_system")
        user_prompt = self.get_prompt("acompanhamento_parse_email", {
            "message": message_content[:3000],
            "source": message_source,
            "process_protocol": process_context.get("external_protocol", ""),
            "process_agency": process_context.get("destination_agency", ""),
        })

        response = self.call_llm(user_prompt, system=system_prompt)
        parsed = OutputValidationPipeline.parse_llm_json(response.content)

        return {
            "is_agency_response": parsed.get("is_agency_response", False),
            "agency": parsed.get("agency"),
            "response_type": parsed.get("response_type"),  # aprovacao, exigencia, indeferimento, informacao
            "summary": parsed.get("summary", ""),
            "deadlines_detected": parsed.get("deadlines", []),
            "action_required": parsed.get("action_required", False),
            "suggested_next_status": parsed.get("suggested_next_status"),
            "extracted_protocol": parsed.get("extracted_protocol"),
            "confidence": parsed.get("confidence", "medium"),
        }

    def _load_recent_messages(self) -> str:
        """Carrega mensagens recentes da thread do processo."""
        from app.models.communication import CommunicationThread, Message  # noqa: PLC0415

        thread = (
            self.ctx.session.query(CommunicationThread)
            .filter(
                CommunicationThread.process_id == self.ctx.process_id,
                CommunicationThread.tenant_id == self.ctx.tenant_id,
            )
            .first()
        )
        if not thread:
            return ""

        messages = (
            self.ctx.session.query(Message)
            .filter(Message.thread_id == thread.id)
            .order_by(Message.created_at.desc())
            .limit(10)
            .all()
        )
        return "\n---\n".join(m.content or "" for m in messages if m.content)

    def _load_process_context(self) -> dict[str, Any]:
        from app.models.process import Process  # noqa: PLC0415

        process = (
            self.ctx.session.query(Process)
            .filter(Process.id == self.ctx.process_id, Process.tenant_id == self.ctx.tenant_id)
            .first()
        )
        if not process:
            return {}
        return {
            "external_protocol": process.external_protocol_number or "",
            "destination_agency": process.destination_agency or "",
            "status": process.status.value if process.status else "",
        }

    def _rules_based_parse(self, message: str) -> dict[str, Any]:
        """Parse basico sem LLM."""
        message_lower = message.lower()
        is_agency = any(kw in message_lower for kw in [
            "ibama", "sema", "icmbio", "protocolo", "despacho", "notificacao",
            "auto de infracao", "licenca", "condicionante",
        ])
        action_required = any(kw in message_lower for kw in [
            "prazo", "exigencia", "pendencia", "comparecer", "apresentar",
        ])
        return {
            "is_agency_response": is_agency,
            "agency": None,
            "response_type": "informacao",
            "summary": "Analise detalhada requer IA habilitada",
            "deadlines_detected": [],
            "action_required": action_required,
            "suggested_next_status": None,
            "extracted_protocol": None,
            "confidence": "low",
        }

    def _fallback_prompts(self) -> dict[str, str]:
        return {
            "acompanhamento_system": (
                "Voce e um especialista em processos ambientais brasileiros. "
                "Analise mensagens de orgaos ambientais (IBAMA, SEMA, ICMBio, etc.) "
                "e extraia informacoes relevantes para acompanhamento do processo. "
                "Retorne APENAS JSON com: is_agency_response (bool), agency (str|null), "
                "response_type (aprovacao|exigencia|indeferimento|informacao), "
                "summary (str), deadlines (list[str]), action_required (bool), "
                "suggested_next_status (str|null), extracted_protocol (str|null), "
                "confidence (high|medium|low)."
            ),
            "acompanhamento_parse_email": (
                "Analise esta mensagem relacionada a processo ambiental:\n\n"
                "FONTE: {source}\n"
                "PROTOCOLO DO PROCESSO: {process_protocol}\n"
                "ORGAO DESTINO: {process_agency}\n\n"
                "MENSAGEM:\n{message}\n\n"
                "Retorne o JSON da analise."
            ),
        }
