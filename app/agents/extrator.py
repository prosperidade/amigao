"""
ExtratorAgent — Extracao de campos estruturados de documentos via OCR+LLM.

Wrapper sobre o servico document_extractor existente.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentRegistry, BaseAgent
from app.models.ai_job import AIJobType


@AgentRegistry.register
class ExtratorAgent(BaseAgent):
    name = "extrator"
    description = "Extracao de campos estruturados de documentos via OCR + LLM"
    job_type = AIJobType.extract_document
    prompt_slugs = ["extract_document_system", "extract_matricula", "extract_car", "extract_ccir"]
    palace_room = "agent_extrator"

    def validate_preconditions(self) -> None:
        # Quando rodando dentro de chain sem documento, permite pular
        pass

    def execute(self) -> dict[str, Any]:
        from app.services.document_extractor import extract_document_fields  # noqa: PLC0415

        text = self.ctx.metadata.get("text", "")
        doc_type = self.ctx.metadata.get("doc_type", "outro")
        document_id = self.ctx.metadata.get("document_id")

        # Se nao tem document_id nem text, retorna vazio (permite chain continuar)
        if not document_id and not text:
            return {
                "extracted_fields": {},
                "doc_type": doc_type,
                "document_id": None,
                "fields_count": 0,
                "skipped": True,
                "reason": "Nenhum documento fornecido para extracao",
            }

        # Se temos document_id mas nao text, buscar do banco
        if document_id and not text:
            from app.models.document import Document  # noqa: PLC0415
            doc = (
                self.ctx.session.query(Document)
                .filter(Document.id == document_id, Document.tenant_id == self.ctx.tenant_id)
                .first()
            )
            if doc is None:
                raise ValueError(f"Documento {document_id} nao encontrado para tenant {self.ctx.tenant_id}")
            text = getattr(doc, "extracted_text", "") or ""
            doc_type = doc.document_type or doc_type
            if not text.strip():
                raise ValueError(f"Documento {document_id} nao possui texto extraido (OCR deve rodar primeiro)")

        fields, _ = extract_document_fields(
            text=text,
            doc_type=doc_type,
            document_id=document_id,
            tenant_id=self.ctx.tenant_id,
            save_job=False,  # BaseAgent.run() cuida do AIJob
            db_session=self.ctx.session,
        )

        return {
            "extracted_fields": fields,
            "doc_type": doc_type,
            "document_id": document_id,
            "fields_count": len(fields),
        }

    def _fallback_prompts(self) -> dict[str, str]:
        return {
            "extract_document_system": (
                "Voce e um especialista em documentos fundiarios e ambientais brasileiros. "
                "Extraia os campos solicitados e retorne APENAS um JSON valido."
            ),
        }
