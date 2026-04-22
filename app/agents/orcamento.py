"""
OrcamentoAgent — Geracao de orcamento/proposta com escopo detalhado.

Gera propostas comerciais com escopo, valores e prazos baseados
no diagnostico do processo e dados do cliente.
"""

from __future__ import annotations

import json
from typing import Any

from app.agents.base import AgentRegistry, BaseAgent
from app.agents.validators import OutputValidationPipeline
from app.models.ai_job import AIJobType


@AgentRegistry.register
class OrcamentoAgent(BaseAgent):
    name = "orcamento"
    description = "Gera orçamento e proposta comercial com escopo detalhado"
    job_type = AIJobType.generate_proposal
    prompt_slugs = ["orcamento_system", "orcamento_user"]
    palace_room = "agent_orcamento"

    def validate_preconditions(self) -> None:
        if not self.ctx.process_id and not self.ctx.metadata.get("demand_type"):
            raise ValueError("process_id ou 'demand_type' em metadata necessario para orcamento")

    def execute(self) -> dict[str, Any]:
        from app.core.config import settings  # noqa: PLC0415

        # Dados do diagnostico (chain ou metadata)
        diagnostico_data = self.ctx.chain_data.get("diagnostico", {})
        demand_type = (
            self.ctx.metadata.get("demand_type")
            or diagnostico_data.get("demand_type")
            or self.ctx.chain_data.get("atendimento", {}).get("demand_type")
        )

        # Carregar dados do processo se disponivel
        process_context = {}
        if self.ctx.process_id:
            process_context = self._load_process_context()
            if not demand_type:
                demand_type = process_context.get("demand_type", "")

        # Orcamento baseado em regras (sempre disponivel)
        base_estimate = self._estimate_by_rules(demand_type or "misto")

        if not settings.ai_configured:
            return base_estimate

        # Enriquecer com LLM
        system_prompt = self.get_prompt("orcamento_system")
        user_prompt = self.get_prompt("orcamento_user", {
            "base_estimate": json.dumps(base_estimate, ensure_ascii=False, default=str),
            "diagnostico": json.dumps(diagnostico_data, ensure_ascii=False, default=str),
            "process_context": json.dumps(process_context, ensure_ascii=False, default=str),
            "demand_type": demand_type or "nao_identificado",
        })

        response = self.call_llm(user_prompt, system=system_prompt)
        parsed = OutputValidationPipeline.parse_llm_json(response.content)

        return {
            "demand_type": demand_type,
            "complexity": parsed.get("complexity", base_estimate.get("complexity", "media")),
            "scope_items": parsed.get("scope_items", base_estimate.get("scope_items", [])),
            "suggested_value_min": parsed.get("suggested_value_min", base_estimate.get("suggested_value_min")),
            "suggested_value_max": parsed.get("suggested_value_max", base_estimate.get("suggested_value_max")),
            "estimated_days": parsed.get("estimated_days", base_estimate.get("estimated_days")),
            "payment_terms": parsed.get("payment_terms", ""),
            "notes": parsed.get("notes", ""),
            "confidence": parsed.get("confidence", "medium"),
            "requires_review": True,
        }

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
            "title": process.title,
            "process_type": process.process_type,
            "demand_type": process.demand_type.value if process.demand_type else None,
            "destination_agency": process.destination_agency,
        }

    def _estimate_by_rules(self, demand_type: str) -> dict[str, Any]:
        """Estimativa basica por regras de negocio."""
        estimates: dict[str, dict[str, Any]] = {
            "car": {
                "complexity": "baixa",
                "scope_items": [
                    {"description": "Inscricao no CAR/SICAR", "estimated_hours": 8},
                    {"description": "Levantamento de campo", "estimated_hours": 16},
                ],
                "suggested_value_min": 2500,
                "suggested_value_max": 5000,
                "estimated_days": 30,
            },
            "licenciamento": {
                "complexity": "alta",
                "scope_items": [
                    {"description": "Estudo ambiental", "estimated_hours": 40},
                    {"description": "Elaboracao de relatorios", "estimated_hours": 24},
                    {"description": "Protocolo e acompanhamento", "estimated_hours": 16},
                ],
                "suggested_value_min": 8000,
                "suggested_value_max": 25000,
                "estimated_days": 90,
            },
            "defesa": {
                "complexity": "alta",
                "scope_items": [
                    {"description": "Analise do auto de infracao", "estimated_hours": 8},
                    {"description": "Elaboracao de defesa", "estimated_hours": 24},
                    {"description": "Acompanhamento processual", "estimated_hours": 16},
                ],
                "suggested_value_min": 5000,
                "suggested_value_max": 15000,
                "estimated_days": 60,
            },
        }
        default = {
            "complexity": "media",
            "scope_items": [{"description": "Servico de consultoria ambiental", "estimated_hours": 24}],
            "suggested_value_min": 3000,
            "suggested_value_max": 10000,
            "estimated_days": 45,
        }
        return estimates.get(demand_type, default)

    def _fallback_prompts(self) -> dict[str, str]:
        return {
            "orcamento_system": (
                "Voce e um gestor comercial de consultoria ambiental brasileira. "
                "Gere orcamentos detalhados com escopo, valores e prazos realistas. "
                "Retorne APENAS JSON valido com: complexity (baixa|media|alta), "
                "scope_items (list[{description, estimated_hours}]), "
                "suggested_value_min (float), suggested_value_max (float), "
                "estimated_days (int), payment_terms (str), notes (str), "
                "confidence (high|medium|low)."
            ),
            "orcamento_user": (
                "Gere um orcamento para este servico:\n\n"
                "TIPO DE DEMANDA: {demand_type}\n"
                "ESTIMATIVA BASE: {base_estimate}\n"
                "DIAGNOSTICO: {diagnostico}\n"
                "PROCESSO: {process_context}\n\n"
                "Retorne o JSON do orcamento."
            ),
        }
