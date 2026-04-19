"""
DiagnosticoAgent — Analise da situacao do imovel com sugestoes de remediacao.

Combina dados da propriedade, documentos extraidos e inconsistencias
do dossie para produzir diagnostico completo e sugestoes de acao.
"""

from __future__ import annotations

import json
from typing import Any

from app.agents.base import AgentRegistry, BaseAgent
from app.agents.validators import OutputValidationPipeline
from app.models.ai_job import AIJobType


@AgentRegistry.register
class DiagnosticoAgent(BaseAgent):
    name = "diagnostico"
    description = "Analise da situacao do imovel com sugestoes de remediacao"
    job_type = AIJobType.diagnostico_propriedade
    prompt_slugs = ["diagnostico_system", "diagnostico_user"]
    palace_room = "agent_diagnostico"

    def validate_preconditions(self) -> None:
        if not self.ctx.process_id:
            raise ValueError("process_id obrigatorio para diagnostico")

    def execute(self) -> dict[str, Any]:
        from app.core.config import settings  # noqa: PLC0415

        # 1. Montar contexto do processo
        process_data = self._load_process_data()

        # 2. Dados da chain (se veio de extrator ou legislacao)
        extracted_data = self.ctx.chain_data.get("extrator", {})
        legal_data = self.ctx.chain_data.get("legislacao", {})

        # 3. Se IA nao configurada, retorna diagnostico baseado em regras
        if not settings.ai_configured:
            return self._rules_based_diagnosis(process_data)

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

        response = self.call_llm(user_prompt, system=system_prompt)
        parsed = OutputValidationPipeline.parse_llm_json(response.content)

        return {
            "situacao_geral": parsed.get("situacao_geral", ""),
            "passivos_identificados": parsed.get("passivos_identificados", []),
            "acoes_remediacao": parsed.get("acoes_remediacao", []),
            "prioridade_acoes": parsed.get("prioridade_acoes", []),
            "risco_estimado": parsed.get("risco_estimado", "medio"),
            "observacoes": parsed.get("observacoes", ""),
            "requires_review": True,  # Diagnostico sempre precisa de validacao humana
        }

    def _load_process_data(self) -> dict[str, Any]:
        """Carrega dados do processo, propriedade e documentos."""
        from app.models.document import Document  # noqa: PLC0415
        from app.models.process import Process  # noqa: PLC0415
        from app.models.property import Property  # noqa: PLC0415

        process = (
            self.ctx.session.query(Process)
            .filter(Process.id == self.ctx.process_id, Process.tenant_id == self.ctx.tenant_id)
            .first()
        )
        if not process:
            raise ValueError(f"Processo {self.ctx.process_id} nao encontrado")

        data: dict[str, Any] = {
            "process": {
                "id": process.id,
                "title": process.title,
                "process_type": process.process_type,
                "status": process.status.value if process.status else None,
                "demand_type": process.demand_type.value if process.demand_type else None,
                "initial_diagnosis": process.initial_diagnosis,
                "destination_agency": process.destination_agency,
                "risk_score": process.risk_score,
            },
        }

        if process.property_id:
            prop = self.ctx.session.query(Property).filter(Property.id == process.property_id).first()
            if prop:
                data["property"] = {
                    "name": prop.name,
                    "municipality": prop.municipality,
                    "state": prop.state,
                    "total_area_ha": prop.total_area_ha,
                    "biome": prop.biome,
                    "car_code": prop.car_code,
                    "car_status": prop.car_status,
                    "has_embargo": prop.has_embargo,
                }

        docs = (
            self.ctx.session.query(Document)
            .filter(Document.process_id == self.ctx.process_id, Document.tenant_id == self.ctx.tenant_id)
            .filter(Document.deleted_at.is_(None))
            .all()
        )
        data["documents"] = [
            {
                "id": d.id,
                "document_type": d.document_type,
                "ocr_status": d.ocr_status.value if d.ocr_status else None,
                "review_required": d.review_required,
            }
            for d in docs
        ]

        return data

    def _rules_based_diagnosis(self, process_data: dict[str, Any]) -> dict[str, Any]:
        """Diagnostico basico sem LLM."""
        passivos = []
        acoes = []
        prop = process_data.get("property", {})

        if prop.get("has_embargo"):
            passivos.append("Imovel com embargo ativo")
            acoes.append("Verificar auto de infracao e prazo de defesa")

        if not prop.get("car_code"):
            passivos.append("CAR nao cadastrado")
            acoes.append("Realizar inscricao no CAR")
        elif prop.get("car_status") == "pendente":
            passivos.append("CAR com pendencias")
            acoes.append("Resolver pendencias no SICAR")

        return {
            "situacao_geral": "Diagnostico baseado em regras (IA indisponivel)",
            "passivos_identificados": passivos,
            "acoes_remediacao": acoes,
            "prioridade_acoes": [],
            "risco_estimado": "alto" if prop.get("has_embargo") else "medio",
            "observacoes": "Diagnostico simplificado. Ative a IA para analise completa.",
        }

    def _fallback_prompts(self) -> dict[str, str]:
        return {
            "diagnostico_system": (
                "Voce e um consultor ambiental senior especializado em propriedades rurais brasileiras. "
                "Analise a situacao do imovel e forneca um diagnostico completo com sugestoes de remediacao. "
                "Retorne APENAS JSON valido com: situacao_geral (str), passivos_identificados (list[str]), "
                "acoes_remediacao (list[str]), prioridade_acoes (list[str]), risco_estimado (baixo|medio|alto), "
                "observacoes (str)."
            ),
            "diagnostico_user": (
                "Analise este imovel rural:\n\n"
                "PROPRIEDADE: {property_data}\n\n"
                "PROCESSO: {process_data}\n\n"
                "DOCUMENTOS: {documents}\n\n"
                "DADOS EXTRAIDOS: {extracted_fields}\n\n"
                "CONTEXTO LEGAL: {legal_context}\n\n"
                "Retorne o JSON de diagnostico."
            ),
        }
