"""
DiagnosticoAgent — Analise da situacao do imovel com sugestoes de remediacao.

Combina dados da propriedade, documentos extraidos e inconsistencias
do dossie para produzir diagnostico completo e sugestoes de acao.

Sprint A2-diagnostico: o output passa a ser um ``DiagnosticoPreliminarContent``
serializado, com **dual-emit** das chaves antigas (``situacao_geral``,
``passivos_identificados``, ``acoes_remediacao``, ``prioridade_acoes``,
``risco_estimado``, ``observacoes``) preservadas no payload final que vai
para ``AIJob.result``. Garante que:

* ``RedatorAgent`` continua recebendo o dict via ``chain_data["diagnostico"]``;
* Frontend ``DiagnósticoResult`` continua renderizando sem patch;
* Schema novo é validado em runtime + carrega ``hipoteses``, ``lacunas``,
  ``riscos`` (objetos), ``checklist_documental`` e ``sources``.

A migração cobre 2 paths:

* ``execute()`` (path IA) — ler JSON do LLM e construir o `Content`.
* ``_rules_based_diagnosis()`` (path fallback sem IA) — idem, com
  ``Source(type="manual", ref="rules_engine")``.

Plano de deprecação das chaves antigas: ver ``docs/sprints/sprint_a2_diagnostico.md``.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from app.agents.base import AgentRegistry, BaseAgent
from app.agents.validators import OutputValidationPipeline
from app.models.ai_job import AIJobType
from app.schemas.stage_output import (
    DiagnosticoPreliminarContent,
    Risco,
    Source,
)

logger = logging.getLogger(__name__)


class DiagnosticoOutputValidationError(ValueError):
    """Erro tipado quando o output do diagnóstico falha a validação Pydantic."""


@AgentRegistry.register
class DiagnosticoAgent(BaseAgent):
    name = "diagnostico"
    description = "Analisa a situação do imóvel e sugere ações de remediação"
    job_type = AIJobType.diagnostico_propriedade
    prompt_slugs = ["diagnostico_system", "diagnostico_user"]

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

        prop = process_data.get("property", {})

        # 4. Chamar LLM para diagnostico completo
        system_prompt = self.get_prompt("diagnostico_system")
        user_prompt = self.get_prompt("diagnostico_user", {
            "property_data": json.dumps(prop, ensure_ascii=False, default=str),
            "process_data": json.dumps(process_data.get("process", {}), ensure_ascii=False, default=str),
            "documents": json.dumps(process_data.get("documents", []), ensure_ascii=False, default=str),
            "extracted_fields": json.dumps(extracted_data, ensure_ascii=False, default=str),
            "legal_context": json.dumps(legal_data, ensure_ascii=False, default=str),
        })

        response = self.call_llm(user_prompt, system=system_prompt)
        parsed = OutputValidationPipeline.parse_llm_json(response.content)

        # Sprint A2-diagnostico-A.1 (path IA) — extrai chaves brutas do JSON do LLM
        # e constrói DiagnosticoPreliminarContent com dual-emit das chaves antigas.
        situacao_geral = parsed.get("situacao_geral", "") or ""
        passivos = list(parsed.get("passivos_identificados", []) or [])
        acoes = list(parsed.get("acoes_remediacao", []) or [])
        prioridades = list(parsed.get("prioridade_acoes", []) or [])
        risco_estimado = parsed.get("risco_estimado", "medio") or "medio"
        observacoes = parsed.get("observacoes", "") or ""

        sources = self._derive_sources(
            documents=process_data.get("documents", []),
            legal_data=legal_data,
            origin="ai",
        )

        # Sprint A3 (Onda 2) — citation_evaluator no Diagnostico
        # Espelha o padrão do RedatorAgent (`app/agents/redator.py:_evaluate_citations`).
        # Concatena todos os campos de texto livre que o LLM pode ter citado normas.
        # Citações fora do contexto legislativo viram "suspeitas" (não derrubam execução).
        citation_text = "\n".join([
            situacao_geral,
            *passivos,
            *acoes,
            observacoes,
        ])
        citation_eval = self._evaluate_citations(citation_text, legal_data)

        return self._build_payload(
            situacao_geral=situacao_geral,
            passivos=passivos,
            acoes=acoes,
            prioridades=prioridades,
            risco_estimado=risco_estimado,
            observacoes=observacoes,
            sources=sources,
            citation_eval=citation_eval,
        )

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
        """Diagnostico basico sem LLM.

        Sprint A2-diagnostico-A.2 — emite ``DiagnosticoPreliminarContent`` com
        ``Source(type="manual", ref="rules_engine")`` para satisfazer o validator
        ``_sources_non_empty``. Mantém dual-emit das chaves antigas no payload.
        """
        passivos: list[str] = []
        acoes: list[str] = []
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

        return self._build_payload(
            situacao_geral="Diagnostico baseado em regras (IA indisponivel)",
            passivos=passivos,
            acoes=acoes,
            prioridades=[],
            risco_estimado="alto" if prop.get("has_embargo") else "medio",
            observacoes="Diagnostico simplificado. Ative a IA para analise completa.",
            sources=[
                Source(
                    type="manual",
                    ref="rules_engine",
                    excerpt="diagnóstico produzido por regras determinísticas (LLM indisponível)",
                )
            ],
            # Sem LLM, não há texto livre que justifique extrair citações.
            citation_eval=None,
        )

    # ------------------------------------------------------------------
    # Helpers Sprint A2-diagnostico-A
    # ------------------------------------------------------------------

    def _derive_sources(
        self,
        *,
        documents: list[dict[str, Any]],
        legal_data: dict[str, Any],
        origin: str,
    ) -> list[Source]:
        """Constrói lista de ``Source`` em cascata.

        1. Cada documento analisado vira ``Source(type="document", ref=str(id))``
           (até 10 itens — diagnósticos podem ter base documental rica).
        2. Itens de ``legal_data["legislacao_aplicavel"]`` viram
           ``Source(type="legislation", ref=str(...))`` (até 5 itens).
        3. Se ambos vierem vazios, fallback ``Source(type="manual",
           ref="agent_diagnostico", excerpt="no_evidence_available")`` + log
           warning sinalizando "diagnóstico sem evidência documental".
        """
        sources: list[Source] = []

        if isinstance(documents, list):
            for doc in documents[:10]:
                if not isinstance(doc, dict):
                    continue
                doc_id = doc.get("id")
                if doc_id is None:
                    continue
                excerpt = (doc.get("document_type") or "").strip() or None
                sources.append(Source(
                    type="document",
                    ref=str(doc_id),
                    excerpt=excerpt,
                ))

        if isinstance(legal_data, dict):
            for item in (legal_data.get("legislacao_aplicavel") or [])[:5]:
                if not item:
                    continue
                sources.append(Source(type="legislation", ref=str(item)))

        if not sources:
            logger.warning(
                "diagnostico.sources_fallback origin=%s — diagnóstico produzido "
                "sem evidência documental nem contexto legal", origin,
            )
            sources.append(Source(
                type="manual",
                ref="agent_diagnostico",
                excerpt="no_evidence_available",
            ))
        return sources

    def _build_payload(
        self,
        *,
        situacao_geral: str,
        passivos: list[str],
        acoes: list[str],
        prioridades: list[str],
        risco_estimado: str,
        observacoes: str,
        sources: list[Source],
        citation_eval: Any | None = None,
    ) -> dict[str, Any]:
        """Monta DiagnosticoPreliminarContent + dual-emit das chaves antigas.

        Mapeamento:
        * ``situacao_geral`` → ``content`` (e dual-emit)
        * ``passivos_identificados`` → ``hipoteses`` (e dual-emit)
        * ``acoes_remediacao`` → ``checklist_documental`` (e dual-emit)
        * ``risco_estimado`` (string) → ``riscos: [Risco(descricao=situacao[:200],
          severidade=risco_estimado)]`` (e dual-emit como string)
        * ``prioridade_acoes`` → ``metadata["prioridade_acoes"]`` (e dual-emit)
        * ``observacoes`` → ``metadata["observacoes"]`` (e dual-emit)
        * ``lacunas`` → ``[]`` (V1 — log INFO; ver Q2 da Fase 0)
        """
        # Garantia mínima de não-vazio em ``content`` (validator do schema)
        content_text = situacao_geral or "Diagnóstico sem síntese textual."

        # severidade do Risco precisa estar no enum {baixo, medio, alto}
        normalized_severidade = (risco_estimado or "medio").strip().lower()
        if normalized_severidade not in {"baixo", "medio", "alto"}:
            logger.warning(
                "diagnostico.invalid_severidade '%s' → fallback 'medio'", risco_estimado,
            )
            normalized_severidade = "medio"

        # Mapping risco_estimado (string única) → riscos (list[Risco])
        riscos = [
            Risco(
                descricao=(situacao_geral or "Risco preliminar identificado")[:200],
                severidade=normalized_severidade,  # type: ignore[arg-type]
            )
        ]

        # Sprint A2-diagnostico Q2 (i): lacunas é schema-only em V1.
        lacunas: list[str] = []
        logger.info(
            "diagnostico.lacunas_empty schema-only field — populated in Sprint A3+ "
            "when redator skills consume lacunas from the prompt"
        )

        try:
            diag = DiagnosticoPreliminarContent(
                content=content_text,
                metadata={
                    "prioridade_acoes": prioridades,
                    "observacoes": observacoes,
                },
                sources=sources,
                hipoteses=passivos,
                lacunas=lacunas,
                riscos=riscos,
                checklist_documental=acoes,
            )
        except ValidationError as exc:
            raise DiagnosticoOutputValidationError(
                f"DiagnosticoPreliminarContent inválido: {exc}"
            ) from exc

        # Dual-emit (γ): chaves antigas preservadas no payload final pra
        # backward-compat com frontend DiagnósticoResult e logs existentes.
        # Plano de deprecação: ver docs/sprints/sprint_a2_diagnostico.md.
        payload: dict[str, Any] = diag.model_dump(mode="json") | {
            "requires_review": True,  # Diagnóstico SEMPRE precisa de validação humana
            "situacao_geral": situacao_geral,
            "passivos_identificados": passivos,
            "acoes_remediacao": acoes,
            "prioridade_acoes": prioridades,
            "risco_estimado": normalized_severidade,
            "observacoes": observacoes,
        }

        # Sprint A3 — campos do citation_evaluator (mesma estrutura do RedatorAgent).
        # Quando não há contexto legal disponível (ex.: chain sem LegislacaoAgent ou
        # path de regras), citation_eval=None e nenhum campo é emitido.
        if citation_eval is not None:
            payload["citation_issues"] = [c.model_dump() for c in citation_eval.invalid]
            payload["citation_total"] = citation_eval.total
            payload["citation_coverage_ratio"] = citation_eval.coverage_ratio
            payload["citation_valid"] = citation_eval.valid

        return payload

    def _evaluate_citations(self, text: str, legal_data: dict[str, Any]) -> Any | None:
        """Roda o evaluator de citação contra o legislation_context já carregado.

        Sprint A3 (Onda 2 da Fase 2) — espelha `app/agents/redator.py:_evaluate_citations`.
        Aplica ao Diagnóstico (preliminar/consolidado/saneamento) o mesmo gate que
        o Redator usa em peças formais: citações sem match no contexto legislativo
        ficam marcadas como suspeitas (`payload["citation_issues"]`), sem derrubar
        a execução. Diagnóstico já vai com `requires_review=True` por princípio,
        então o consultor decide o que fazer com cada citação suspeita.

        Retorna ``None`` quando não há contexto legislativo nessa execução
        (ex.: diagnóstico chamado fora da chain `extrator → legislacao → diagnostico`,
        ou texto sem citação detectável).
        """
        from app.services.citation_evaluator import (  # noqa: PLC0415
            extract_citations,
            validate_citations,
        )

        context: list[Any] = []
        for key in ("legislacao_aplicavel", "normas_estaduais"):
            value = legal_data.get(key) if isinstance(legal_data, dict) else None
            if isinstance(value, list):
                context.extend(str(item) for item in value if item)
        chunks = legal_data.get("rag_chunks_meta") if isinstance(legal_data, dict) else None
        if isinstance(chunks, list):
            context.extend(chunks)

        if not context:
            return None

        citations = extract_citations(text)
        if not citations:
            return None
        return validate_citations(citations, context)

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
