"""
ExtratorAgent — Extracao de campos estruturados de documentos via OCR+LLM.

Adaptador da entrada semantica: observacao duravel e preview projetado.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentRegistry, BaseAgent
from app.models.ai_job import AIJobType


@AgentRegistry.register
class ExtratorAgent(BaseAgent):
    name = "extrator"
    description = "Extrai dados estruturados de documentos enviados (matrícula, CAR, CCIR, etc.)"
    job_type = AIJobType.extract_document
    prompt_slugs = ["extract_document_system", "extract_matricula", "extract_car", "extract_ccir"]

    def _fallback_prompts(self) -> dict[str, str]:
        # BaseAgent requires the hook; the extractor requires its manifest skills.
        return {}

    def validate_preconditions(self) -> None:
        # Quando rodando dentro de chain sem documento, permite pular
        pass

    def execute(self) -> dict[str, Any]:
        from app.services.entrada_semantica import executar_extracao
        return executar_extracao(self.ctx, ai_job_id=self._current_job.id if self._current_job else None,
            on_response=lambda response, rotulo:
            self.registrar_chamada_llm(response, rotulo=rotulo))
