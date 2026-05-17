"""
RedatorAgent — Geracao de documentos formais.

Gera PRAD, memorial descritivo, oficios, respostas a notificacoes,
propostas e comunicacoes formais.

Sprint A2-redator: o output passa a ser um ``PecaJuridicaContent``
serializado (ou ``RespostaNotificacaoContent`` quando ``template`` for
``resposta_notificacao`` E os campos extras estiverem presentes).
Campos de execução (``requires_review``, ``citation_issues``,
``citation_total``, ``citation_coverage_ratio``, ``citation_valid``,
``confidence``) ficam **fora** do schema, no merge final do dict que vai
para ``AIJob.result`` — preserva os 5 testes do hook de citação (A1 B).

``BaseAgent.run()`` continua aceitando ``dict`` (não foi migrado em A1),
então o redator emite o resultado já serializado via ``model_dump(mode="json")``.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from app.agents.base import AgentRegistry, BaseAgent
from app.models.ai_job import AIJobType
from app.schemas.stage_output import (
    CitationRef,
    PecaJuridicaContent,
    RespostaNotificacaoContent,
    Source,
)

logger = logging.getLogger(__name__)


@AgentRegistry.register
class RedatorAgent(BaseAgent):
    name = "redator"
    description = "Gera documentos formais: PRAD, memorial descritivo, ofícios, propostas e contratos"
    job_type = AIJobType.gerar_documento
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

        # Sprint A2-redator (Q1): registra quando o redator é chamado em
        # template que tem fluxo dedicado paralelo. Em 1-2 sprints de uso,
        # esse log mostra se a rota pelo redator é caminho morto.
        if doc_template in ("proposta", "contrato"):
            logger.info(
                "redator chamado com template '%s' que tem fluxo dedicado "
                "(proposal_generator/contract_generator)", doc_template,
            )

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

        # Sprint A1 B — evaluator de citação legal (extensão A2: também emite
        # all_citations populado em CitationValidationResult).
        citation_eval = self._evaluate_citations(response.content, legal_data)

        # Sprint A2-redator-A: monta PecaJuridicaContent (ou subclass).
        legal_citations: list[CitationRef] = (
            citation_eval.all_citations if citation_eval is not None else []
        )
        sources = self._derive_sources(legal_data)
        addressee = self._resolve_addressee(process_data)
        peca = self._build_peca(
            template=doc_template,
            content=response.content,
            sources=sources,
            legal_citations=legal_citations,
            addressee=addressee,
        )

        # Merge schema serializado + flags de execução fora-do-schema.
        # requires_review e citation_* não cabem em PecaJuridicaContent —
        # ficam no payload final que vai pra AIJob.result.
        payload: dict[str, Any] = peca.model_dump(mode="json") | {
            "requires_review": True,  # documentos formais SEMPRE precisam de revisão humana
            "confidence": "medium",
        }
        if citation_eval is not None:
            payload["citation_issues"] = [c.model_dump() for c in citation_eval.invalid]
            payload["citation_total"] = citation_eval.total
            payload["citation_coverage_ratio"] = citation_eval.coverage_ratio
            payload["citation_valid"] = citation_eval.valid
        return payload

    # ------------------------------------------------------------------
    # Helpers Sprint A2-redator-A
    # ------------------------------------------------------------------

    def _derive_sources(self, legal_data: dict[str, Any]) -> list[Source]:
        """Constrói lista de ``Source`` a partir do contexto legal carregado.

        Cascata:
        1. ``legal_data["legislacao_aplicavel"]`` (lista de strings) →
           uma ``Source(type="legislation")`` por item, até 5 itens.
        2. ``legal_data["normas_estaduais"]`` (lista de strings) → idem.
        3. Se ainda vazio, fallback ``Source(type="manual", ref="agent_redator", excerpt=instructions[:200])``.
           ``type="manual"`` é honesto sobre a origem — não finge ser legislação.
           A obrigação de pelo menos 1 ``Source`` vem do validator
           ``StageOutputContent._sources_non_empty``.
        """
        sources: list[Source] = []
        if isinstance(legal_data, dict):
            for key in ("legislacao_aplicavel", "normas_estaduais"):
                items = legal_data.get(key)
                if isinstance(items, list):
                    for item in items[:5]:
                        if not item:
                            continue
                        sources.append(Source(type="legislation", ref=str(item)))
                if len(sources) >= 5:
                    break

        if not sources:
            instructions = (self.ctx.metadata.get("instructions") or "").strip()
            sources.append(Source(
                type="manual",
                ref="agent_redator",
                excerpt=instructions[:200] or "Sem contexto legal fornecido na chamada do redator.",
            ))
        return sources

    def _resolve_addressee(self, process_data: dict[str, Any]) -> str | None:
        """Cascata: ``ctx.metadata['addressee']`` → ``process.destination_agency`` → None.

        Para ``oficio``/``comunicacao``/``resposta_notificacao`` espera-se
        que ao menos um dos dois primeiros popule. Quando vier ``None``,
        a peça é gerada normalmente — o frontend pode mostrar lacuna no badge.
        """
        explicit = self.ctx.metadata.get("addressee")
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip()
        agency = process_data.get("destination_agency") if isinstance(process_data, dict) else None
        if isinstance(agency, str) and agency.strip():
            return agency.strip()
        return None

    def _build_peca(
        self,
        *,
        template: str,
        content: str,
        sources: list[Source],
        legal_citations: list[CitationRef],
        addressee: str | None,
    ) -> PecaJuridicaContent:
        """Monta ``PecaJuridicaContent`` ou ``RespostaNotificacaoContent``.

        Para ``template == "resposta_notificacao"``, tenta enriquecer com
        ``prazo_dias`` e ``ato_regulatorio`` numa cascata ``ctx.metadata`` →
        parse best-effort do ``content``. Se algum dos dois não puder ser
        resolvido, **fallback gracioso para PecaJuridicaContent puro** com
        ``template="resposta_notificacao"`` + log warning (Q3 da Fase 0).
        """
        if template != "resposta_notificacao":
            return PecaJuridicaContent(
                content=content,
                sources=sources,
                template=template,  # type: ignore[arg-type]
                legal_citations=legal_citations,
                addressee=addressee,
            )

        prazo_dias = self.ctx.metadata.get("prazo_dias")
        if prazo_dias is None:
            prazo_dias = _parse_prazo_dias(content)
        ato = self.ctx.metadata.get("ato_regulatorio")
        if ato is None:
            ato = _parse_ato_regulatorio(content)

        if isinstance(prazo_dias, int) and prazo_dias >= 0 and isinstance(ato, str) and ato.strip():
            try:
                return RespostaNotificacaoContent(
                    content=content,
                    sources=sources,
                    legal_citations=legal_citations,
                    addressee=addressee,
                    prazo_dias=prazo_dias,
                    ato_regulatorio=ato.strip(),
                )
            except ValidationError as exc:
                logger.warning(
                    "redator: ValidationError em RespostaNotificacaoContent (%s); "
                    "fallback para PecaJuridicaContent com template=resposta_notificacao",
                    exc,
                )

        logger.warning(
            "redator: prazo_dias/ato_regulatorio ausentes em template=resposta_notificacao; "
            "emitindo PecaJuridicaContent puro (sem subclass enriched)",
        )
        return PecaJuridicaContent(
            content=content,
            sources=sources,
            template="resposta_notificacao",
            legal_citations=legal_citations,
            addressee=addressee,
        )

    def _evaluate_citations(self, text: str, legal_data: dict[str, Any]) -> Any | None:
        """Roda o evaluator de citação contra o legislation_context já carregado.

        Retorna ``None`` quando não há contexto legislativo nessa execução
        (ex.: redator chamado fora da chain). Nesse caso, o caller decidiu
        prescindir do RAG, então não temos verdade a confrontar.
        """
        from app.services.citation_evaluator import (  # noqa: PLC0415
            extract_citations,
            validate_citations,
        )

        context: list[Any] = []
        # legislacao_aplicavel + normas_estaduais são listas de strings tipo "Lei 12.651/2012"
        for key in ("legislacao_aplicavel", "normas_estaduais"):
            value = legal_data.get(key) if isinstance(legal_data, dict) else None
            if isinstance(value, list):
                context.extend(str(item) for item in value if item)
        # rag_chunks_meta — espaço para Sprint A2 expor SearchResult; aceito hoje se já vier
        chunks = legal_data.get("rag_chunks_meta") if isinstance(legal_data, dict) else None
        if isinstance(chunks, list):
            context.extend(chunks)

        if not context:
            return None

        citations = extract_citations(text)
        if not citations:
            return None
        return validate_citations(citations, context)

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


# ----------------------------------------------------------------------
# Parsers best-effort para resposta_notificacao (Sprint A2-redator-A, Q3)
# ----------------------------------------------------------------------

_PRAZO_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"prazo\s+(?:de\s+)?(\d{1,3})\s+dias?", re.IGNORECASE),
    re.compile(r"em\s+at[éé]\s+(\d{1,3})\s+dias?", re.IGNORECASE),
    re.compile(r"(\d{1,3})\s+dias?\s+(?:corridos|úteis|para)", re.IGNORECASE),
)

_ATO_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?:Notificação|Auto\s+de\s+Infração|Ofício)\s*(?:n[º°ºo]\.?\s*)?([A-Z0-9./\-]+(?:/\d{2,4})?)",
        re.IGNORECASE,
    ),
)


def _parse_prazo_dias(text: str) -> int | None:
    """Extrai ``prazo_dias`` do texto (best-effort, V1)."""
    for pattern in _PRAZO_PATTERNS:
        match = pattern.search(text or "")
        if match:
            try:
                value = int(match.group(1))
            except (ValueError, IndexError):
                continue
            if 0 <= value <= 365:
                return value
    return None


def _parse_ato_regulatorio(text: str) -> str | None:
    """Extrai identificação do ato regulatório do texto (best-effort, V1)."""
    for pattern in _ATO_PATTERNS:
        match = pattern.search(text or "")
        if match:
            return match.group(0).strip()
    return None
