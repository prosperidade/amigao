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
    description = "Extrai dados estruturados de documentos enviados (matrícula, CAR, CCIR, etc.)"
    job_type = AIJobType.extract_document
    prompt_slugs = ["extract_document_system", "extract_matricula", "extract_car", "extract_ccir"]

    def validate_preconditions(self) -> None:
        # Quando rodando dentro de chain sem documento, permite pular
        pass

    def execute(self) -> dict[str, Any]:
        from datetime import UTC, datetime  # noqa: PLC0415

        from app.models.document import Document  # noqa: PLC0415
        from app.services.document_extractor import extract_document_fields  # noqa: PLC0415

        text = self.ctx.metadata.get("text", "")
        doc_type = self.ctx.metadata.get("doc_type", "outro")
        document_id = self.ctx.metadata.get("document_id")

        # Resolução automática de contexto (2026-06-01): quando o extrator é
        # chamado dentro de uma chain (ex.: diagnostico_completo) ou pela aba
        # Agentes apenas com process_id — SEM document_id/text no metadata — ele
        # antes pulava ("chamado sem documento") e o caso ficava sem extração no
        # fluxo agêntico. O consultor nunca digita id: o sistema propaga o
        # contexto. Aqui, havendo process_id, resolvemos os documentos do processo
        # que já têm OCR e extraímos deles (mesma fonte do
        # POST /processes/{id}/extract), agregando os campos.
        if not document_id and not text and getattr(self.ctx, "process_id", None):
            docs = (
                self.ctx.session.query(Document)
                .filter(
                    Document.process_id == self.ctx.process_id,
                    Document.tenant_id == self.ctx.tenant_id,
                    Document.deleted_at.is_(None),
                    Document.extracted_text.isnot(None),
                )
                .order_by(Document.id)
                .all()
            )
            docs = [d for d in docs if (d.extracted_text or "").strip()]
            if docs:
                aggregated: dict[str, Any] = {}
                per_doc: list[dict[str, Any]] = []
                for d in docs:
                    f, _ = extract_document_fields(
                        text=d.extracted_text or "",
                        doc_type=d.document_type or "outro",
                        document_id=d.id,
                        tenant_id=self.ctx.tenant_id,
                        save_job=False,
                        db_session=self.ctx.session,
                    )
                    per_doc.append(
                        {"document_id": d.id, "doc_type": d.document_type, "fields_count": len(f)}
                    )
                    # Ficha 01 / FASE 2 — gravação ADICIONAL no staging (não toca
                    # o extracted_fields acima nem a base real).
                    self._stage_ficha01(
                        text=d.extracted_text or "",
                        doc_type=d.document_type or "outro",
                        document_id=d.id,
                        process_id=self.ctx.process_id,
                    )
                    for k, v in (f or {}).items():
                        if k not in aggregated and v not in (None, "", {}, []):
                            aggregated[k] = v
                return {
                    "extracted_fields": aggregated,
                    "doc_type": "multiplos",
                    "document_id": None,
                    "documents": per_doc,
                    "fields_count": len(aggregated),
                    "resolved_from_process": self.ctx.process_id,
                }
            # Sem documento NOVO com OCR: em vez de devolver "0 campos, tipo outro"
            # (enganoso — a UI ficava como se nada tivesse sido extraído), REUTILIZA
            # a extração já gravada no staging do processo e a repassa à chain.
            reused = self._reuse_staging_fields(self.ctx.process_id)
            if reused is not None:
                return reused
            # Genuinamente sem nada extraído ainda → skip orientativo abaixo.

        # Se nao tem document_id nem text, retorna vazio (permite chain continuar)
        # e dá orientação acionável — antes a mensagem "Nenhum documento fornecido"
        # virava ruído sem caminho de saída na UI de Agentes.
        if not document_id and not text:
            return {
                "extracted_fields": {},
                "doc_type": doc_type,
                "document_id": None,
                "fields_count": 0,
                "skipped": True,
                "reason": (
                    "Extrator chamado sem documento. Para extrair, forneça um dos: "
                    "(a) metadata.document_id (ID de um Document do tenant), "
                    "(b) metadata.text (texto bruto a extrair), ou "
                    "(c) chame POST /api/v1/processes/{id}/extract para processar "
                    "todos os documentos de um processo em um clique."
                ),
            }

        # Busca o Document quando há document_id (para leitura do extracted_text e/ou cache posterior)
        doc: Document | None = None
        if document_id:
            doc = (
                self.ctx.session.query(Document)
                .filter(Document.id == document_id, Document.tenant_id == self.ctx.tenant_id)
                .first()
            )
            if doc is None:
                raise ValueError(f"Documento {document_id} nao encontrado para tenant {self.ctx.tenant_id}")

        # Se temos document_id mas nao text, buscar do banco (Sprint -1 D — coluna existe agora)
        if doc is not None and not text:
            text = doc.extracted_text or ""
            doc_type = doc.document_type or doc_type
            if not text.strip():
                raise ValueError(
                    f"OCR ainda nao rodou para o documento {document_id}. "
                    f"Use POST /api/v1/processes/{{id}}/extract — a chain "
                    f"workers.ocr_then_extract executa o OCR (pypdf/Gemini/OpenAI Vision) "
                    f"e despacha o extrator automaticamente ao fim. "
                    f"Alternativa: aguarde ocr_status='done' no Document e re-execute."
                )

        # Sprint -1 D — se o texto veio por metadata e há Document associado sem
        # extracted_text cacheado, persiste para próximos usos (evita re-OCR).
        if doc is not None and text and not doc.extracted_text:
            doc.extracted_text = text
            doc.extracted_at = datetime.now(UTC)
            self.ctx.session.flush()

        fields, _ = extract_document_fields(
            text=text,
            doc_type=doc_type,
            document_id=document_id,
            tenant_id=self.ctx.tenant_id,
            save_job=False,  # BaseAgent.run() cuida do AIJob
            db_session=self.ctx.session,
        )

        # Ficha 01 / FASE 2 — gravação ADICIONAL no staging.
        self._stage_ficha01(
            text=text,
            doc_type=doc_type,
            document_id=document_id,
            process_id=(doc.process_id if doc is not None else self.ctx.process_id),
        )

        return {
            "extracted_fields": fields,
            "doc_type": doc_type,
            "document_id": document_id,
            "fields_count": len(fields),
        }

    def _stage_ficha01(
        self,
        *,
        text: str,
        doc_type: str,
        document_id: int | None,
        process_id: int | None,
    ) -> None:
        """Ficha 01 / FASE 2 — extração estruturada por tipo → ExtractedFieldStaging.

        Best-effort e ADICIONAL: nunca derruba a extração principal
        (``extracted_fields``) nem grava na base real. Classifica o doc_type por
        conteúdo (quando o tipo do Document é genérico) e delega ao serviço.
        """
        from app.services.ficha01_extraction import (  # noqa: PLC0415
            classify_doc_type,
            extract_and_stage,
        )

        if not (text or "").strip():
            return
        try:
            effective_type = classify_doc_type(text, doc_type)
            ai_job_id = self._current_job.id if self._current_job is not None else None
            extract_and_stage(
                text=text,
                doc_type=effective_type,
                tenant_id=self.ctx.tenant_id,
                db_session=self.ctx.session,
                process_id=process_id,
                document_id=document_id,
                ai_job_id=ai_job_id,
                created_by_agent="extrator",
            )
        except Exception as exc:  # pragma: no cover - blindagem; staging é adicional
            import logging  # noqa: PLC0415

            logging.getLogger(__name__).warning(
                "extrator: staging Ficha 01 falhou (ignorado) doc=%s: %s", document_id, exc
            )

    def _reuse_staging_fields(self, process_id: int | None) -> dict[str, Any] | None:
        """Reúsa a extração já gravada no staging do processo (chain sem doc novo).

        Evita o "0 campos, tipo outro" enganoso: se há staging do processo, devolve
        um resultado EXPLÍCITO ("extração reutilizada, N campos") carregando os
        campos para os próximos agentes da chain. None se não há nada a reutilizar.
        """
        if not process_id:
            return None
        from app.models.extracted_field_staging import ExtractedFieldStaging  # noqa: PLC0415

        rows = (
            self.ctx.session.query(ExtractedFieldStaging)
            .filter(
                ExtractedFieldStaging.tenant_id == self.ctx.tenant_id,
                ExtractedFieldStaging.process_id == process_id,
            )
            .order_by(ExtractedFieldStaging.id)
            .all()
        )
        if not rows:
            return None
        aggregated: dict[str, Any] = {}
        for r in rows:
            val = r.field_value.get("value") if isinstance(r.field_value, dict) else r.field_value
            fname = str(r.field_name)
            if fname not in aggregated and val not in (None, "", {}, []):
                aggregated[fname] = val
        fontes = sorted({str(r.source_doc_type) for r in rows if r.source_doc_type})
        return {
            "extracted_fields": aggregated,
            "doc_type": "reutilizado",
            "document_id": None,
            "fields_count": len(aggregated),
            "reused": True,
            "staging_rows": len(rows),
            "reason": (
                f"Extração reutilizada: {len(rows)} linha(s) de staging já existentes "
                f"no processo {process_id} (fontes: {', '.join(fontes) or '—'}); nenhum "
                f"documento novo com OCR. Campos repassados à chain."
            ),
        }

    def _fallback_prompts(self) -> dict[str, str]:
        return {
            "extract_document_system": (
                "Voce e um especialista em documentos fundiarios e ambientais brasileiros. "
                "Extraia os campos solicitados e retorne APENAS um JSON valido."
            ),
        }
