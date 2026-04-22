"""
RedatorAgent — Geracao de documentos formais.

Gera PRAD, memorial descritivo, oficios, respostas a notificacoes,
propostas e comunicacoes formais.
"""

from __future__ import annotations

import json
from typing import Any

from app.agents.base import AgentRegistry, BaseAgent
from app.models.ai_job import AIJobType


@AgentRegistry.register
class RedatorAgent(BaseAgent):
    name = "redator"
    description = "Gera documentos formais: PRAD, memorial descritivo, ofícios, propostas e contratos"
    job_type = AIJobType.gerar_documento
    palace_room = "agent_redator"
    prompt_slugs = [
        "redator_system", "redator_prad", "redator_memorial",
        "redator_oficio", "redator_proposta", "redator_resposta_notificacao",
    ]

    VALID_TEMPLATES = {"prad", "memorial", "oficio", "proposta", "resposta_notificacao", "contrato", "comunicacao"}

    def validate_preconditions(self) -> None:
        template = self.ctx.metadata.get("document_template", "")
        if template and template not in self.VALID_TEMPLATES:
            raise ValueError(
                f"Template '{template}' invalido. Validos: {self.VALID_TEMPLATES}"
            )

    def execute(self) -> dict[str, Any]:
        doc_template = self.ctx.metadata.get("document_template", "comunicacao")

        # Contexto da chain ou metadata
        process_data = self.ctx.chain_data.get("diagnostico", {})
        legal_data = self.ctx.chain_data.get("legislacao", {})
        client_data = self.ctx.metadata.get("client_data", {})
        property_data = self.ctx.metadata.get("property_data", {})

        # Se temos process_id, enriquecer
        if self.ctx.process_id and not process_data:
            process_data = self._load_process_context()

        system_prompt = self.get_prompt("redator_system")
        slug = f"redator_{doc_template}"
        user_prompt = self.get_prompt(slug, {
            "process_context": json.dumps(process_data, ensure_ascii=False, default=str),
            "legal_context": json.dumps(legal_data, ensure_ascii=False, default=str),
            "client_data": json.dumps(client_data, ensure_ascii=False, default=str),
            "property_data": json.dumps(property_data, ensure_ascii=False, default=str),
            "instructions": self.ctx.metadata.get("instructions", ""),
        })

        response = self.call_llm(user_prompt, system=system_prompt, max_tokens=4096)

        return {
            "document_type": doc_template,
            "content": response.content,
            "requires_review": True,  # Documentos formais SEMPRE precisam de revisao humana
            "confidence": "medium",
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
            "external_protocol": process.external_protocol_number,
            "initial_diagnosis": process.initial_diagnosis,
        }

    def _fallback_prompts(self) -> dict[str, str]:
        return {
            "redator_system": (
                "Voce e um redator tecnico especializado em documentos ambientais e fundiarios brasileiros. "
                "Gere documentos formais, tecnicos e bem fundamentados. "
                "Use linguagem tecnica apropriada e formalidade adequada ao tipo de documento. "
                "Estruture bem o documento com titulos, secoes e paragrafos claros."
            ),
            "redator_prad": (
                "Elabore um PRAD (Plano de Recuperacao de Area Degradada) com base nos dados:\n\n"
                "PROCESSO: {process_context}\n"
                "CONTEXTO LEGAL: {legal_context}\n"
                "PROPRIEDADE: {property_data}\n"
                "INSTRUCOES ADICIONAIS: {instructions}\n\n"
                "Inclua: diagnostico, objetivos, metodologia, cronograma e monitoramento."
            ),
            "redator_memorial": (
                "Elabore um Memorial Descritivo com base nos dados:\n\n"
                "PROCESSO: {process_context}\n"
                "PROPRIEDADE: {property_data}\n"
                "INSTRUCOES: {instructions}"
            ),
            "redator_oficio": (
                "Elabore um oficio formal para o orgao ambiental:\n\n"
                "PROCESSO: {process_context}\n"
                "CONTEXTO LEGAL: {legal_context}\n"
                "CLIENTE: {client_data}\n"
                "INSTRUCOES: {instructions}"
            ),
            "redator_proposta": (
                "Elabore uma proposta comercial de servicos de consultoria ambiental:\n\n"
                "PROCESSO: {process_context}\n"
                "CLIENTE: {client_data}\n"
                "PROPRIEDADE: {property_data}\n"
                "INSTRUCOES: {instructions}"
            ),
            "redator_resposta_notificacao": (
                "Elabore uma resposta a notificacao/auto de infracao ambiental:\n\n"
                "PROCESSO: {process_context}\n"
                "CONTEXTO LEGAL: {legal_context}\n"
                "CLIENTE: {client_data}\n"
                "INSTRUCOES: {instructions}"
            ),
            "redator_contrato": (
                "Elabore um contrato de prestacao de servicos de consultoria ambiental:\n\n"
                "PROCESSO: {process_context}\n"
                "CLIENTE: {client_data}\n"
                "INSTRUCOES: {instructions}"
            ),
            "redator_comunicacao": (
                "Elabore uma comunicacao formal:\n\n"
                "PROCESSO: {process_context}\n"
                "CLIENTE: {client_data}\n"
                "INSTRUCOES: {instructions}"
            ),
        }
