"""
LegislacaoAgent — Enquadramento regulatorio com base de conhecimento legislativa.

Arquitetura:
1. Carrega contexto do processo (demand_type, UF, municipio, propriedade)
2. Busca **trechos hiper-relevantes** via RAG semantico (knowledge_catalog/pgvector)
3. Busca documentos legislativos relevantes por metadados no banco
4. Envia legislacao no contexto do LLM (Gemini 2M tokens ou Claude)
5. LLM analisa o caso contra a legislacao e retorna caminho regulatorio

Sprint V (2026-04-29) — agente passou a consumir o knowledge_catalog
(RAG entregue na Sprint U). Os top-k chunks mais similares ao caso entram no
prompt antes do dump completo, ancorando o raciocinio juridico em texto
recuperado por similaridade vetorial. O dump completo permanece como
fallback quando o RAG nao retorna chunks relevantes.

Usa Gemini Flash/Pro por padrao (Sprint O) com fallback Claude Sonnet.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from app.agents.base import AgentRegistry, BaseAgent
from app.agents.validators import OutputValidationPipeline
from app.models.ai_job import AIJobType
from app.schemas.stage_output import (
    CitationRef,
    EnquadramentoRegulatorioContent,
    Etapa,
    Risco,
    Source,
)

logger = logging.getLogger(__name__)

_CONFIANCA_TO_CONFIDENCE = {"baixa": 0.3, "media": 0.6, "alta": 0.9}
_VALID_SEVERIDADES = {"baixo", "medio", "alto"}

# Captura "Lei 12.651/2012", "LC 140/2011", "Decreto 7.830/2012", "Resolução CONAMA 237/1997",
# "IN IBAMA 02/2014", "Portaria 123/2020", "MP 2.166/2001"
_CITATION_REGEX = re.compile(
    r"(?P<raw>"
    r"(?P<kind>Lei Complementar|LC|Lei|Decreto-Lei|Decreto|Resolução CONAMA|"
    r"Resolu[cç][aã]o\s+CONAMA|Resolu[cç][aã]o|IN(?:strução Normativa)?(?:\s+\w+)?|"
    r"Instru[cç][aã]o\s+Normativa|Portaria|MP|Medida\s+Provis[oó]ria)"
    r"\s*n?[º°.]?\s*"
    r"(?P<numero>[\d.]+)\s*/\s*(?P<ano>\d{4})"
    r")",
    re.IGNORECASE,
)

_CITATION_KIND_MAP = {
    "lei": "lei",
    "lei complementar": "lei_complementar",
    "lc": "lei_complementar",
    "decreto": "decreto",
    "decreto-lei": "decreto_lei",
    "resolução conama": "resolucao_conama",
    "resolucao conama": "resolucao_conama",
    "resolução": "outro",
    "resolucao": "outro",
    "instrução normativa": "instrucao_normativa",
    "instrucao normativa": "instrucao_normativa",
    "in": "instrucao_normativa",
    "portaria": "portaria",
    "mp": "medida_provisoria",
    "medida provisória": "medida_provisoria",
    "medida provisoria": "medida_provisoria",
}


class LegislacaoOutputValidationError(ValueError):
    """Erro tipado quando o output do enquadramento regulatório falha a validação Pydantic."""


@AgentRegistry.register
class LegislacaoAgent(BaseAgent):
    name = "legislacao"
    description = "Enquadramento regulatório com raciocínio jurídico apoiado por base de legislação"
    job_type = AIJobType.consulta_regulatoria
    prompt_slugs = ["legislacao_system", "legislacao_user"]

    def validate_preconditions(self) -> None:
        query = self.ctx.metadata.get("query", "")
        demand_type = (
            self.ctx.metadata.get("demand_type")
            or self.ctx.chain_data.get("atendimento", {}).get("demand_type")
        )
        if not query.strip() and not demand_type and not self.ctx.process_id:
            raise ValueError("'query', 'demand_type' ou process_id necessario para consulta regulatoria")

    def execute(self) -> dict[str, Any]:
        from app.core.config import settings

        query = self.ctx.metadata.get("query", "")
        demand_type = (
            self.ctx.metadata.get("demand_type")
            or self.ctx.chain_data.get("atendimento", {}).get("demand_type")
        )
        state = self.ctx.metadata.get("state", "")

        # Enriquecer com dados do processo
        process_context: dict[str, Any] = {}
        if self.ctx.process_id:
            process_context = self._load_process_context()
            if not demand_type:
                demand_type = process_context.get("demand_type", "")
            if not state:
                state = process_context.get("state", "")
            if not query:
                query = f"Qual o caminho regulatorio para {demand_type} no estado {state}?"

        if not settings.ai_configured:
            return self._rules_based_response(demand_type, state)

        # Sprint V — RAG semantico: trechos hiper-relevantes do knowledge_catalog.
        rag_chunks = self._load_rag_chunks(
            query=query, demand_type=demand_type, uf=state,
        )
        rag_context = self._format_rag_context(rag_chunks)

        # Buscar legislacao relevante por metadados (dump completo como fallback amplo)
        legislation_context = self._load_legislation_context(
            demand_type=demand_type,
            uf=state,
        )

        # Montar prompts
        system_prompt = self.get_prompt("legislacao_system")
        user_prompt = self.get_prompt("legislacao_user", {
            "query": query,
            "demand_type": demand_type or "nao_identificado",
            "state": state or "nao_informado",
            "context": json.dumps(process_context, ensure_ascii=False, default=str),
            "rag_chunks": rag_context or "(nenhum trecho relevante recuperado)",
            "legislation": legislation_context,
        })

        # Defensivo: se o template salvo no banco for da versao antiga e nao incluir
        # {rag_chunks}, anexamos os trechos manualmente ao final do prompt.
        if rag_context and "TRECHOS LEGISLATIVOS HIPER-RELEVANTES" not in user_prompt:
            user_prompt += (
                "\n\nTRECHOS LEGISLATIVOS HIPER-RELEVANTES (recuperados por similaridade "
                "vetorial — use como fonte primaria e cite em legislacao_aplicavel):\n"
                + rag_context
            )

        # Sprint O — Gemini é o provider default do agente legislação.
        # Sprint 0 (2026-04-23) — roteamento dinâmico Flash → Pro:
        #   - Flash 2.0 (janela 1M, $0.10/1M): caso comum, ~95% das chamadas.
        #   - Pro 1.5 (janela 2M, $2.50/1M acima de 200K): só quando contexto
        #     legislativo extrapola o limiar (coletâneas grandes, múltiplos
        #     diplomas grandes na resposta do search_legislation).
        context_chars = len(legislation_context) if legislation_context else 0
        needs_long_window = context_chars > settings.GEMINI_LEGAL_LONG_CONTEXT_THRESHOLD_CHARS
        gemini_available = (
            settings.LEGISLATION_USE_GEMINI_DEFAULT and bool(settings.GEMINI_API_KEY)
        )
        # "use_gemini" mantém compat com a decisão do Sprint O: qualquer contexto
        # legislativo material (>100K chars) vai pro Gemini, mesmo que a flag esteja
        # off (não queremos truncar legislação em modelos de janela pequena).
        use_gemini = needs_long_window or context_chars > 100_000 or gemini_available

        if use_gemini:
            # Roteamento Flash → Pro baseado no tamanho do contexto.
            chosen_model = (
                settings.GEMINI_LEGAL_LONG_MODEL
                if needs_long_window
                else settings.GEMINI_LEGAL_MODEL
            )
            cost_limit = (
                settings.AI_MAX_COST_PER_JOB_USD_LEGISLACAO_LONG
                if needs_long_window
                else settings.AI_MAX_COST_PER_JOB_USD_LEGISLACAO
            )
            import logging as _log  # noqa: PLC0415

            _log.getLogger(__name__).info(
                "legislacao.route context_chars=%d needs_long=%s model=%s cost_limit=%.2f",
                context_chars, needs_long_window, chosen_model, cost_limit,
            )
            response = self.call_llm(
                user_prompt,
                system=system_prompt,
                model=chosen_model,
                max_tokens=settings.CLAUDE_LEGAL_MAX_TOKENS,
                max_cost_override_usd=cost_limit,
            )
        elif settings.ANTHROPIC_API_KEY:
            # Fallback: Claude via SDK quando Gemini não tiver API key.
            response = self._call_claude(user_prompt, system=system_prompt)
        else:
            # Último fallback: LiteLLM padrao (outro provider configurado).
            response = self.call_llm(
                user_prompt,
                system=system_prompt,
                max_cost_override_usd=settings.AI_MAX_COST_PER_JOB_USD_LEGISLACAO,
            )

        parsed = OutputValidationPipeline.parse_llm_json(response.content)

        sources = self._derive_sources(
            rag_chunks=rag_chunks,
            legislacao_aplicavel=parsed.get("legislacao_aplicavel", []),
            origin="ai",
        )
        chunks_referenced = [
            {
                "id": c.id,
                "source_ref": c.source_ref,
                "title": c.title,
                "section": c.section,
                "identifier": c.identifier,
                "similarity": round(c.similarity, 3),
            }
            for c in rag_chunks
        ]
        self.requires_review = True  # sempre requer revisao humana (consequencias juridicas)
        return self._build_payload(
            caminho_regulatorio=str(parsed.get("caminho_regulatorio", "") or ""),
            orgao_competente=str(parsed.get("orgao_competente", "") or ""),
            etapas_raw=parsed.get("etapas", []) or [],
            legislacao_aplicavel_raw=parsed.get("legislacao_aplicavel", []) or [],
            riscos_raw=parsed.get("riscos", []) or [],
            documentos_necessarios=list(parsed.get("documentos_necessarios", []) or []),
            prazos_estimados=parsed.get("prazos_estimados", {}) or {},
            recomendacoes=list(parsed.get("recomendacoes", []) or []),
            confianca=str(parsed.get("confianca", "media") or "media"),
            justificativa=str(parsed.get("justificativa", "") or ""),
            sources=sources,
            chunks_referenced=chunks_referenced,
            normas_estaduais=list(parsed.get("normas_estaduais", []) or []),
            risco_legal=str(parsed.get("risco_legal", parsed.get("confianca", "medio")) or "medio"),
            prazos_legais=list(parsed.get("prazos_legais", []) or []),
        )

    def _call_claude(self, prompt: str, *, system: str = "") -> Any:
        """Chama Claude diretamente via Anthropic SDK."""
        from app.core.claude_client import ClaudeClient
        client = ClaudeClient()
        response = client.complete(prompt, system=system)
        self._llm_response = response
        return response

    def _load_rag_chunks(
        self,
        *,
        query: str,
        demand_type: str | None,
        uf: str | None,
    ) -> list:
        """Sprint V — busca top-k trechos legislativos via RAG semantico.

        Retorna lista de SearchResult (vazia em caso de falha ou catalogo sem dados).
        Combina o query do usuario com demand_type e uf para enriquecer a consulta:
        consultas curtas como "Qual o caminho regulatorio?" ficam mais especificas.
        """
        from app.core.config import settings  # noqa: PLC0415
        from app.services.knowledge_catalog import search

        # Compor query enriquecida quando o input vier curto
        parts = [p for p in [query, demand_type, uf] if p]
        composed = " ".join(parts).strip()
        if not composed:
            return []

        try:
            results = search(
                self.ctx.session,
                composed,
                limit=getattr(settings, "LEGISLATION_RAG_TOP_K", 8),
                source_type="legislation",
                uf=uf if uf else None,
                tenant_id=self.ctx.tenant_id,
                demand_type=demand_type if demand_type else None,
                min_similarity=0.0,
            )
            # Sem resultados com filtro de UF? tenta uma busca global (legislacao federal).
            if not results and uf:
                results = search(
                    self.ctx.session,
                    composed,
                    limit=getattr(settings, "LEGISLATION_RAG_TOP_K", 8),
                    source_type="legislation",
                    tenant_id=self.ctx.tenant_id,
                    demand_type=demand_type if demand_type else None,
                    min_similarity=0.0,
                )
            return results
        except Exception as exc:
            import logging  # noqa: PLC0415
            logging.getLogger(__name__).warning(
                "legislacao.rag falha na busca semantica: %s", exc,
            )
            return []

    def _format_rag_context(self, chunks: list) -> str:
        """Formata trechos RAG como blocos numerados pra inserir no prompt."""
        if not chunks:
            return ""
        lines: list[str] = []
        for i, c in enumerate(chunks, 1):
            header_bits = [c.title or c.source_ref]
            if c.section:
                header_bits.append(c.section)
            if c.identifier:
                header_bits.append(c.identifier)
            header = " — ".join(b for b in header_bits if b)
            lines.append(f"[{i}] {header}  (similarity={c.similarity:.3f})")
            lines.append(c.chunk_text.strip())
            lines.append("")
        return "\n".join(lines).strip()

    def _load_legislation_context(
        self,
        demand_type: str | None,
        uf: str | None,
    ) -> str:
        """Busca legislacao no banco e monta contexto textual.

        Sprint 0 — usa o budget LONG (1.9M tokens) quando o agente roda Gemini Pro.
        Como não sabemos a priori se vamos rodar Pro (depende do tamanho do contexto
        montado), usamos sempre o budget LONG aqui e deixamos o roteamento decidir
        o modelo. Se o contexto ficar abaixo do threshold, usa Flash; se ficar
        acima, usa Pro. Ambos cabem na janela do modelo escolhido.
        """
        from app.core.config import settings  # noqa: PLC0415
        from app.services.legislation_service import build_legislation_context, search_legislation

        try:
            docs = search_legislation(
                self.ctx.session,
                uf=uf if uf else None,
                demand_type=demand_type,
                max_total_tokens=settings.LEGISLATION_MAX_CONTEXT_TOKENS_LONG,
                max_results=settings.LEGISLATION_MAX_RESULTS,
            )
            if docs:
                return build_legislation_context(docs)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Falha ao carregar legislacao: %s", exc)

        return ""

    def _load_process_context(self) -> dict[str, Any]:
        """Carrega contexto do processo para enriquecer a consulta."""
        from app.models.process import Process
        from app.models.property import Property

        process = (
            self.ctx.session.query(Process)
            .filter(Process.id == self.ctx.process_id, Process.tenant_id == self.ctx.tenant_id)
            .first()
        )
        if not process:
            return {}

        ctx: dict[str, Any] = {
            "demand_type": process.demand_type.value if process.demand_type else "",
            "process_type": process.process_type,
            "title": process.title,
            "description": process.description or "",
            "initial_diagnosis": process.initial_diagnosis or "",
        }

        if process.property_id:
            prop = self.ctx.session.query(Property).filter(Property.id == process.property_id).first()
            if prop:
                ctx["state"] = prop.state or ""
                ctx["municipality"] = prop.municipality or ""
                ctx["biome"] = prop.biome or ""
                ctx["area_ha"] = prop.total_area_ha
                ctx["has_embargo"] = prop.has_embargo
                ctx["car_status"] = prop.car_status or ""

        return ctx

    def _rules_based_response(self, demand_type: str | None, state: str) -> dict[str, Any]:
        """Resposta basica sem LLM com legislacao federal padrao.

        Sprint A2-legislacao: passa a emitir ``EnquadramentoRegulatorioContent``
        com ``Source(type="manual", ref="rules_engine")``.
        """
        legislacao = {
            "car": ["Lei 12.651/2012 (Codigo Florestal)", "Decreto 7.830/2012 (SICAR)"],
            "retificacao_car": ["Lei 12.651/2012", "Decreto 7.830/2012", "IN IBAMA 02/2014"],
            "licenciamento": ["LC 140/2011", "Resolucao CONAMA 237/1997"],
            "outorga": ["Lei 9.433/1997 (Politica Nacional de Recursos Hidricos)"],
            "defesa": ["Lei 9.605/1998 (Lei de Crimes Ambientais)", "Decreto 6.514/2008"],
            "prad": ["Lei 12.651/2012 Art. 59-66", "IN IBAMA 11/2014"],
            "compensacao": ["Lei 12.651/2012 Art. 66", "Decreto 8.235/2014"],
            "regularizacao_fundiaria": ["Lei 13.465/2017", "Lei 12.651/2012"],
            "exigencia_bancaria": ["Resolucao CMN 4.327/2014", "Resolucao BCB 140/2021"],
        }
        legislacao_aplicavel = legislacao.get(demand_type or "", ["Consulte legislacao especifica"])
        self.requires_review = True
        return self._build_payload(
            caminho_regulatorio=f"Verificar legislacao para {demand_type or 'tipo nao identificado'}",
            orgao_competente="A definir conforme UF e tipo",
            etapas_raw=[],
            legislacao_aplicavel_raw=legislacao_aplicavel,
            riscos_raw=[],
            documentos_necessarios=[],
            prazos_estimados={},
            recomendacoes=["Habilitar IA para analise regulatoria completa"],
            confianca="baixa",
            justificativa="Resposta baseada em regras — IA nao configurada",
            sources=[
                Source(
                    type="manual",
                    ref="rules_engine",
                    excerpt="enquadramento produzido por regras determinísticas (LLM indisponível)",
                )
            ],
            chunks_referenced=[],
            normas_estaduais=[f"Verificar legislacao estadual para {state or 'UF nao informada'}"],
            risco_legal="medio",
            prazos_legais=[],
        )

    # ------------------------------------------------------------------
    # Helpers Sprint A2-legislacao
    # ------------------------------------------------------------------

    def _derive_sources(
        self,
        *,
        rag_chunks: list,
        legislacao_aplicavel: list,
        origin: str,
    ) -> list[Source]:
        """Constrói lista de ``Source`` priorizando chunks RAG.

        1. Cada ``rag_chunks[i]`` vira ``Source(type="legislation", ref=str(chunk.id))``
           (até 10 — sources já condensam o que importa).
        2. Se não houver chunks, cai pra ``legislacao_aplicavel`` (até 5 itens).
        3. Se ainda vazio, fallback ``Source(type="manual", ref="agent_legislacao",
           excerpt="no_legal_context_available")`` + log warning.
        """
        sources: list[Source] = []
        for chunk in (rag_chunks or [])[:10]:
            chunk_id = getattr(chunk, "id", None)
            if chunk_id is None:
                continue
            excerpt_bits = [
                getattr(chunk, "title", None),
                getattr(chunk, "section", None),
                getattr(chunk, "identifier", None),
            ]
            excerpt = " — ".join(b for b in excerpt_bits if b) or None
            sources.append(Source(
                type="legislation",
                ref=str(chunk_id),
                excerpt=excerpt,
            ))

        if not sources:
            for item in (legislacao_aplicavel or [])[:5]:
                ref = self._citation_ref_from_raw(item)
                if not ref:
                    continue
                sources.append(Source(type="legislation", ref=ref))

        if not sources:
            logger.warning(
                "legislacao.sources_fallback origin=%s — enquadramento produzido "
                "sem chunks RAG nem citações estruturadas", origin,
            )
            sources.append(Source(
                type="manual",
                ref="agent_legislacao",
                excerpt="no_legal_context_available",
            ))
        return sources

    @staticmethod
    def _citation_ref_from_raw(item: Any) -> str | None:
        """Normaliza um item de legislacao_aplicavel (str ou dict) para uma ref textual."""
        if not item:
            return None
        if isinstance(item, str):
            return item.strip() or None
        if isinstance(item, dict):
            for key in ("identificador", "raw", "titulo", "norma"):
                value = item.get(key)
                if value:
                    return str(value).strip() or None
        return None

    def _normalize_etapas(self, etapas_raw: list) -> list[Etapa]:
        """Aceita list[dict] do LLM e mapeia para list[Etapa]; ignora itens malformados."""
        out: list[Etapa] = []
        for i, raw in enumerate(etapas_raw or [], start=1):
            if not isinstance(raw, dict):
                continue
            titulo = (raw.get("titulo") or raw.get("title") or "").strip()
            if not titulo:
                continue
            try:
                prazo = raw.get("prazo_estimado_dias")
                prazo_int = int(prazo) if prazo is not None and str(prazo).strip() != "" else None
                # Rastreabilidade (06/06): a fonte do prazo. Se o LLM apontou um
                # trecho do RAG (fonte_trecho), é "norma" + SourceRef; senão, e
                # havendo prazo, marca "estimativa_profissional" (sem fonte
                # normativa nos autos) — honestidade explícita, nunca prazo "da cabeça".
                fonte_ref = raw.get("fonte_trecho") or raw.get("fonte") or raw.get("fonte_prazo")
                sources_et, prazo_fonte = self._etapa_fonte(fonte_ref, prazo_int)
                out.append(Etapa(
                    ordem=int(raw.get("ordem", i)),
                    titulo=titulo,
                    descricao=(raw.get("descricao") or None),
                    prazo_estimado_dias=prazo_int,
                    orgao=(raw.get("orgao") or None),
                    sources=sources_et,
                    prazo_fonte=prazo_fonte,
                ))
            except (ValueError, TypeError, ValidationError) as exc:
                logger.warning("legislacao.etapa_skipped raw=%r err=%s", raw, exc)
        return out

    @staticmethod
    def _etapa_fonte(fonte_ref: Any, prazo_int: int | None) -> tuple[list, str | None]:
        """Fonte do prazo de uma etapa. fonte_ref preenchida e plausível → 'norma'
        + SourceRef(legislacao); sem fonte e com prazo → 'estimativa_profissional'."""
        from app.schemas.stage_output import SourceRef  # noqa: PLC0415

        ref_str = str(fonte_ref).strip() if fonte_ref not in (None, "") else ""
        if ref_str and "sem fonte" not in ref_str.lower() and "estimativa" not in ref_str.lower():
            return [SourceRef(tipo="legislacao", descricao=ref_str)], "norma"
        if prazo_int is not None:
            return (
                [SourceRef(tipo="sem_fonte", sem_fonte=True,
                           descricao="estimativa profissional — sem fonte normativa nos autos")],
                "estimativa_profissional",
            )
        return [], None

    def _normalize_riscos(self, riscos_raw: list) -> list[Risco]:
        """Mapeia list[dict] do LLM (campos `descricao`, `severidade`, `mitigacao`)
        para list[Risco] do schema (`mitigacao_sugerida`)."""
        out: list[Risco] = []
        for raw in riscos_raw or []:
            if not isinstance(raw, dict):
                continue
            descricao = (raw.get("descricao") or raw.get("description") or "").strip()
            if not descricao:
                continue
            severidade = (raw.get("severidade") or raw.get("severity") or "medio").strip().lower()
            if severidade not in _VALID_SEVERIDADES:
                logger.warning("legislacao.invalid_severidade '%s' → fallback 'medio'", severidade)
                severidade = "medio"
            mitigacao = raw.get("mitigacao_sugerida") or raw.get("mitigacao") or None
            try:
                out.append(Risco(
                    descricao=descricao,
                    severidade=severidade,  # type: ignore[arg-type]
                    mitigacao_sugerida=mitigacao,
                ))
            except ValidationError as exc:
                logger.warning("legislacao.risco_skipped raw=%r err=%s", raw, exc)
        return out

    def _extract_citations(self, legislacao_aplicavel: list) -> list[CitationRef]:
        """Tenta extrair CitationRef estruturadas via regex em itens de
        legislacao_aplicavel. Itens não parseáveis são ignorados — `legal_citations`
        é best-effort; o dual-emit preserva a forma original."""
        citations: list[CitationRef] = []
        seen: set[tuple[str, str, int]] = set()
        for item in legislacao_aplicavel or []:
            raw_text = self._citation_ref_from_raw(item)
            if not raw_text:
                continue
            match = _CITATION_REGEX.search(raw_text)
            if not match:
                continue
            kind_raw = (match.group("kind") or "").strip().lower()
            # IN tem variações ("IN IBAMA 02/2014"): caputra só os primeiros 2 chars do prefixo
            if kind_raw.startswith("in "):
                kind_raw = "in"
            kind = _CITATION_KIND_MAP.get(kind_raw, "outro")
            numero = match.group("numero")
            try:
                ano = int(match.group("ano"))
            except (TypeError, ValueError):
                continue
            key = (kind, numero, ano)
            if key in seen:
                continue
            seen.add(key)
            try:
                citations.append(CitationRef(
                    kind=kind,  # type: ignore[arg-type]
                    numero=numero,
                    ano=ano,
                    raw=match.group("raw").strip(),
                ))
            except ValidationError as exc:
                logger.warning("legislacao.citation_skipped raw=%r err=%s", raw_text, exc)
        return citations

    def _build_payload(
        self,
        *,
        caminho_regulatorio: str,
        orgao_competente: str,
        etapas_raw: list,
        legislacao_aplicavel_raw: list,
        riscos_raw: list,
        documentos_necessarios: list[str],
        prazos_estimados: dict[str, Any],
        recomendacoes: list[str],
        confianca: str,
        justificativa: str,
        sources: list[Source],
        chunks_referenced: list[dict[str, Any]],
        normas_estaduais: list[str],
        risco_legal: str,
        prazos_legais: list,
    ) -> dict[str, Any]:
        """Monta EnquadramentoRegulatorioContent + dual-emit das chaves antigas.

        Mapeamento:
        * ``justificativa`` (ou ``caminho_regulatorio`` como fallback) → ``content``.
        * ``confianca`` (string baixa|media|alta) → ``confidence`` (float 0..1).
        * ``prazos_estimados`` (dict) → ``metadata["prazos_estimados"]``.
        * ``chunks_referenced`` → ``metadata["chunks_referenced"]`` (preserva
          payload da UI; ``sources`` carrega versão normalizada).
        * Demais campos viram fields próprios do schema.

        Dual-emit no payload final: chaves antigas (``caminho_regulatorio``,
        ``orgao_competente``, ``etapas`` como list[dict], ``legislacao_aplicavel``
        bruto, ``riscos`` bruto, ``confianca`` string, ``prazos_estimados``, etc.)
        ficam acessíveis para o frontend e o DiagnosticoAgent downstream.
        """
        # content não pode ser vazio — usa justificativa, ou caminho como fallback
        content_text = (justificativa or caminho_regulatorio or "Enquadramento regulatório preliminar.").strip()
        if not content_text:
            content_text = "Enquadramento regulatório preliminar."

        # caminho_regulatorio é obrigatório no schema; fallback se LLM devolveu vazio
        caminho_final = caminho_regulatorio.strip() or "Caminho regulatório a definir após análise complementar."

        # confianca (string) → confidence (float)
        confianca_norm = (confianca or "media").strip().lower()
        confidence_float = _CONFIANCA_TO_CONFIDENCE.get(confianca_norm, 0.6)

        etapas = self._normalize_etapas(etapas_raw)
        riscos = self._normalize_riscos(riscos_raw)
        legal_citations = self._extract_citations(legislacao_aplicavel_raw)

        metadata: dict[str, Any] = {
            "prazos_estimados": prazos_estimados or {},
            "confianca": confianca_norm,
        }
        if chunks_referenced:
            metadata["chunks_referenced"] = chunks_referenced

        try:
            enq = EnquadramentoRegulatorioContent(
                content=content_text,
                metadata=metadata,
                sources=sources,
                confidence=confidence_float,
                caminho_regulatorio=caminho_final,
                orgao_competente=(orgao_competente.strip() or None),
                etapas=etapas,
                legal_citations=legal_citations,
                riscos=riscos,
                documentos_necessarios=list(documentos_necessarios),
                recomendacoes=list(recomendacoes),
            )
        except ValidationError as exc:
            raise LegislacaoOutputValidationError(
                f"EnquadramentoRegulatorioContent inválido: {exc}"
            ) from exc

        # Dual-emit (γ): chaves antigas preservadas pra backward-compat com frontend,
        # DiagnosticoAgent downstream (lê chain_data["legislacao"]["legislacao_aplicavel"]),
        # e logs/auditoria existentes. Plano de deprecação: ver sprint_a2_legislacao.md.
        return enq.model_dump(mode="json") | {
            "requires_review": True,  # decisão jurídica SEMPRE precisa de revisão humana
            "caminho_regulatorio": caminho_final,
            "orgao_competente": orgao_competente,
            "etapas": list(etapas_raw),  # preserva forma original (dict cru)
            "legislacao_aplicavel": list(legislacao_aplicavel_raw),
            "riscos": list(riscos_raw),
            "documentos_necessarios": list(documentos_necessarios),
            "prazos_estimados": prazos_estimados or {},
            "confianca": confianca_norm,
            "justificativa": justificativa,
            "recomendacoes": list(recomendacoes),
            # Sprint V — chunks_referenced no top-level também (compat com UI/legislation_alerts)
            "chunks_referenced": list(chunks_referenced),
            # Backward compat com formato anterior à Sprint V
            "normas_estaduais": list(normas_estaduais),
            "risco_legal": risco_legal,
            "prazos_legais": list(prazos_legais),
        }

    def _fallback_prompts(self) -> dict[str, str]:
        return {
            "legislacao_system": (
                "Voce e um advogado ambiental senior brasileiro especialista em enquadramento regulatorio.\n\n"
                "Seu trabalho e analisar um caso concreto de consultoria ambiental e determinar:\n"
                "1. O caminho regulatorio mais provavel\n"
                "2. O orgao competente\n"
                "3. A sequencia de etapas regulatorias\n"
                "4. A legislacao aplicavel com citacoes especificas\n"
                "5. Os riscos juridicos/ambientais\n"
                "6. Os documentos necessarios\n"
                "7. Estimativa de prazos\n\n"
                "Quando BASE LEGISLATIVA for fornecida abaixo, use-a como fonte primaria.\n"
                "Cite artigos, paragrafos e incisos especificos.\n\n"
                "REGRA INVIOLAVEL — NENHUMA AFIRMACAO SEM FONTE: cada norma citada e cada PRAZO deve "
                "apontar o TRECHO de origem entre os TRECHOS HIPER-RELEVANTES (referencie pelo numero [N] "
                "do trecho). Se um prazo NAO tem base nos trechos fornecidos, marque-o como "
                "\"estimativa profissional — sem fonte normativa nos autos\" no campo fonte_trecho da etapa. "
                "NUNCA invente numero de norma, artigo ou prazo \"de cabeca\".\n\n"
                "Retorne APENAS JSON valido com os campos:\n"
                "caminho_regulatorio (str), orgao_competente (str), "
                "etapas (list[{ordem, titulo, descricao, prazo_estimado_dias, orgao, fonte_trecho}]), "
                "legislacao_aplicavel (list[{identificador, titulo, relevancia, fonte_trecho}]), "
                "riscos (list[{descricao, severidade, mitigacao}]), "
                "documentos_necessarios (list[str]), "
                "prazos_estimados ({total_dias, fase_documental_dias, fase_protocolo_dias, fase_analise_orgao_dias}), "
                "confianca (baixa|media|alta), justificativa (str), recomendacoes (list[str])."
            ),
            "legislacao_user": (
                "CASO CONCRETO:\n\n"
                "PERGUNTA: {query}\n"
                "TIPO DE DEMANDA: {demand_type}\n"
                "ESTADO (UF): {state}\n"
                "DADOS DO CASO: {context}\n\n"
                "TRECHOS LEGISLATIVOS HIPER-RELEVANTES (recuperados por similaridade vetorial — "
                "use estes como fonte primaria e cite explicitamente em legislacao_aplicavel):\n"
                "{rag_chunks}\n\n"
                "BASE LEGISLATIVA AMPLA (referencia complementar):\n{legislation}\n\n"
                "Com base nos TRECHOS HIPER-RELEVANTES (prioritarios) e na BASE AMPLA, "
                "retorne o JSON com o enquadramento regulatorio completo. "
                "Cite artigos, paragrafos e incisos especificos sempre que possivel."
            ),
        }
