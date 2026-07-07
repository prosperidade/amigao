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
    Divergencia,
    Risco,
    Source,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Consumo de chain_data["auditor_imovel"] — PROMPT_4 Onda A
# ---------------------------------------------------------------------------
#
# O AuditorImovelAgent (chain `diagnostico_completo`: extrator → auditor_imovel
# → legislacao → diagnostico) é a fonte do cruzamento documental: matrícula ×
# CAR × CCIR/ITR, GEO INCRA, RL averbada × declarada. O DiagnosticoAgent CONSOME
# esses findings como "primeiro movimento" (matriz de cruzamento) e NÃO refaz
# a conta — o auditor é o radar, o diagnóstico é a interpretação.
#
# Mapeamento `grade` (4 níveis da régua de divergência, Onda C) → `grau` (4
# níveis da taxonomia oficial). Preservar `critico` como
# `critico_impeditivo_potencial` é essencial: a sócia distinguiu alto-vs-crítico
# de propósito — apenas `critico` dispara o mecanismo de decisão obrigatória do
# consultor (camada 2 do Princípio 1, sprint posterior). NÃO colapsar com o
# `severity` de 3 níveis do RegulatoryIssue.
_GRADE_TO_GRAU: dict[str, str] = {
    "informativo": "informativo",
    "atencao": "atencao",
    "alto": "alto",
    "critico": "critico_impeditivo_potencial",
}

# Mapeamento `familia` (taxonomia rica do PROMPT_5 — 11 valores estáveis) →
# `RiscoCategoria` (7 categorias do Mapa de Riscos da skill diagnostico). É
# 11→7 (algumas famílias caem na mesma categoria, ex.: identificacao/car/
# validade_documental → cadastral_sistemico). Substituiu o mapeamento por
# `finding.type` do PROMPT_4 (que tinha 4 valores e caía maioritariamente em
# "outro").
_FAMILIA_TO_CATEGORIA: dict[str, str] = {
    "identificacao": "cadastral_sistemico",
    "titularidade": "fundiario",
    "area": "cadastral_sistemico",
    "geoespacial": "geoespacial",
    "geo_incra": "fundiario",
    "car": "cadastral_sistemico",
    "ambiental": "ambiental",
    "fiscal": "credito_mercado",
    "restricao_risco": "territorial",
    "licenciamento": "atividade_produtiva",
    "validade_documental": "cadastral_sistemico",
}

# Ordenação ascendente do grau para escolher o "pior" entre os findings do
# auditor e alimentar `nivel_risco_geral` (4 níveis: baixo/medio/alto/critico).
_GRAU_RANK: dict[str, int] = {
    "informativo": 0,
    "atencao": 1,
    "alto": 2,
    "critico_impeditivo_potencial": 3,
}
_GRAU_TO_NIVEL_RISCO: dict[str, str] = {
    "informativo": "baixo",
    "atencao": "medio",
    "alto": "alto",
    "critico_impeditivo_potencial": "critico",
}


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

        # 2.b Fallback persistido (PR fix/diagnostico-insumo) — diagnóstico avulso
        # (aba Agentes) ou rodada com extrator/legislacao falhos chega aqui com
        # chain_data vazio e sai CEGO (tokens_in≈358). Os campos extraídos e o
        # enquadramento PERSISTEM nos AIJobs do extrator/legislacao do processo;
        # quando a chain não os trouxe, buscamos o mais recente do banco. Na
        # chain, chain_data continua prioritário (mais fresco).
        if not self._has_extracted_fields(extracted_data):
            persisted = self._load_persisted_extraction(process_data)
            if persisted:
                extracted_data = persisted
        if not legal_data:
            persisted_legal = self._load_persisted_legislacao()
            if persisted_legal:
                legal_data = persisted_legal

        # Property: se não há Property persistida mas a extração trouxe
        # municipio/uf/area, enriquece o CONTEXTO do prompt (sem gravar na
        # Property — efeito colateral proibido).
        if not process_data.get("property"):
            enriched = self._property_from_extracted(extracted_data)
            if enriched:
                process_data["property"] = enriched

        # Item E (fix/teste-isis-rodada2) — relato/demanda do consultor.
        # SEMPRE carregado do AIJob do atendimento (nunca veio na chain): leva ao
        # diagnostico o que so existe na abertura do caso e nao em documento
        # (ex.: embargo relatado sem doc). Fonte ADICIONAL — entra no contexto do
        # processo sem competir com extrator/legislacao (que seguem prioritarios).
        atendimento_data = self._load_persisted_atendimento()
        if atendimento_data:
            process_data["process"]["relato_demanda_consultor"] = atendimento_data

        # Ficha 02 / FASE 3 — matriz de inconsistências do auditor no contexto.
        # Sem tocar prompt-template: injeta no bloco `process` (placeholder
        # {process_data}). Da chain quando disponível; senão do AIJob persistido
        # (mesmo padrão do atendimento). Fonte adicional para o diagnóstico citar.
        auditor_payload = self._resolve_auditor_payload()
        matriz = auditor_payload.get("matriz_inconsistencias") if isinstance(auditor_payload, dict) else None
        if isinstance(matriz, dict) and matriz.get("linhas"):
            process_data["process"]["matriz_inconsistencias"] = matriz

        # Fase 1 (N2, item 10) — fatos de auto de infração no contexto do
        # diagnóstico (spec da Isis: fato de passivo, não campo cadastral).
        autos_infracao = self._load_auto_infracao_fatos(process_data)
        if autos_infracao:
            process_data["process"]["autos_infracao"] = autos_infracao

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

        # Modelo dedicado por env (AI_DIAGNOSTICO_MODEL); vazio cai no default
        # global. White-label do consultor (user_preferences) ainda tem precedência
        # no gateway. Mesma convenção do agente legislacao.
        diag_model = settings.AI_DIAGNOSTICO_MODEL or settings.AI_DEFAULT_MODEL
        # fix/llm-consistencia (2026-06-07): o diagnóstico é a peça fundamental e
        # a maior saída do funil (pós-#70 cada passivo/ação carrega afirmacao+fonte
        # +confianca). Teto de saída dedicado (AI_DIAGNOSTICO_MAX_TOKENS = máx. do
        # gpt-4.1) + cost cap próprio, e agent_name liga a matriz de equivalência:
        # se o provider primário cair (503/timeout), assume o equivalente disponível.
        response = self.call_llm(
            user_prompt,
            system=system_prompt,
            model=diag_model,
            agent_name="diagnostico",
            max_tokens=settings.AI_DIAGNOSTICO_MAX_TOKENS,
            max_cost_override_usd=settings.AI_MAX_COST_PER_JOB_USD_DIAGNOSTICO,
        )
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

        # PROMPT_4 Onda A — consumir findings do auditor (primeiro movimento)
        auditor_payload = self._resolve_auditor_payload()
        divergencias_auditor, riscos_auditor = self._consume_auditor_findings(auditor_payload)

        # Rastreabilidade (06/06): cada passivo/ação com fonte; sem fonte → marcado.
        afirmacoes = self._build_afirmacoes(parsed, passivos, acoes)
        # Fase 1 (N2, item 7) — fatos de auto de infração viram Afirmacao
        # DETERMINÍSTICA (não fuzzy-match com a prosa do LLM): são fato
        # estruturado, não interpretação.
        afirmacoes.extend(self._build_afirmacoes_auto_infracao(autos_infracao))

        return self._build_payload(
            situacao_geral=situacao_geral,
            passivos=passivos,
            acoes=acoes,
            prioridades=prioridades,
            risco_estimado=risco_estimado,
            observacoes=observacoes,
            sources=sources,
            citation_eval=citation_eval,
            divergencias_auditor=divergencias_auditor,
            riscos_auditor=riscos_auditor,
            afirmacoes=afirmacoes,
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
                # Item E (fix/teste-isis-rodada2): a narrativa da abertura do caso
                # — relato do consultor (description), resumo e notas de intake —
                # carrega informacoes que so existem na entrada e nao em documento
                # (ex.: embargo relatado sem doc). Antes ficavam de fora do contexto
                # e o diagnostico ficava cego pra elas.
                "description": process.description,
                "initial_summary": process.initial_summary,
                "intake_notes": process.intake_notes,
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
                    # Sprint 4 (Ficha 07 §9): o LLM não raciocina porte/passivo
                    # sobre soma possivelmente fictícia — a ressalva viaja junto.
                    "matriculas_count": len(prop.matriculas or []),
                    "matriculas_contiguas": prop.matriculas_contiguas,
                    "area_total_matriculas_ha": (
                        prop.area_total_matriculas() if prop.matriculas else None
                    ),
                    "area_total_nota": prop.nota_soma_matriculas(),
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

    # ------------------------------------------------------------------
    # Fallback persistido (PR fix/diagnostico-insumo)
    # ------------------------------------------------------------------
    #
    # Chaves do payload do extrator (wrapper do ExtratorAgent OU campos
    # diretos do document_extractor) que NÃO são "campo do imóvel" e portanto
    # não entram no contexto como dado extraído.
    _EXTRACTION_META_KEYS: frozenset[str] = frozenset({
        "doc_type", "document_id", "documents", "fields_count", "skipped",
        "reason", "resolved_from_process", "confidence", "_raw", "_parse_error",
        "_source", "documents_count",
    })

    @staticmethod
    def _has_extracted_fields(extracted_data: Any) -> bool:
        """True quando ``chain_data['extrator']`` traz campos extraídos reais.

        ``{}`` (avulso) ou ``{'extracted_fields': {}, 'skipped': True}`` (extrator
        sem documento) contam como vazio → dispara o fallback persistido.
        """
        if not isinstance(extracted_data, dict):
            return False
        fields = extracted_data.get("extracted_fields")
        return isinstance(fields, dict) and bool(fields)

    def _fields_from_job_result(self, result: Any) -> dict[str, Any]:
        """Extrai os campos estruturados de um ``AIJob.result`` de extração.

        Dois shapes coexistem (ver ``document_extractor`` vs ``ExtratorAgent``):
        * ExtratorAgent: ``{"extracted_fields": {...}, "doc_type": ...}``.
        * document_extractor (save_job): campos no topo do ``result``.
        Em ambos retornamos só os campos pequenos — NUNCA ``extracted_text`` bruto
        (que não vive no result do extrator de qualquer forma).
        """
        if not isinstance(result, dict):
            return {}
        inner = result.get("extracted_fields")
        if isinstance(inner, dict):
            return inner
        return {k: v for k, v in result.items() if k not in self._EXTRACTION_META_KEYS}

    def _load_auto_infracao_fatos(self, process_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Fase 1 (N2, item 10) — carrega os fatos de auto de infração
        (extraídos pelo ExtratorAgent em `AIJob.result`) dos documentos do
        processo, enriquece com lookup de enquadramento legal (item 8) e
        cruzamento autuado×titular (item 9, nunca bloqueia), e devolve pra
        injetar no contexto + virar Afirmacao (item 7 — NÃO passa pelo
        staging cadastral, sem hint de matrícula)."""
        from app.models.ai_job import AIJob, AIJobStatus, AIJobType  # noqa: PLC0415
        from app.models.client import Client  # noqa: PLC0415
        from app.models.process import Process  # noqa: PLC0415
        from app.models.property import Property  # noqa: PLC0415
        from app.services.auto_infracao_extraction import (  # noqa: PLC0415
            check_autuado_diverge_titular,
            lookup_enquadramento,
        )

        doc_ids = [
            d.get("id")
            for d in process_data.get("documents", [])
            if isinstance(d, dict) and d.get("id") is not None
        ]
        if not doc_ids:
            return []

        jobs = (
            self.ctx.session.query(AIJob)
            .filter(
                AIJob.tenant_id == self.ctx.tenant_id,
                AIJob.job_type == AIJobType.extract_document,
                AIJob.status == AIJobStatus.completed,
                AIJob.agent_name == "extrator",
            )
            .order_by(AIJob.id.desc())
            .all()
        )
        fatos_by_doc: dict[int, dict[str, Any]] = {}
        for job in jobs:
            result = job.result if isinstance(job.result, dict) else {}
            single = result.get("auto_infracao_fato")
            if single is not None:
                doc_id = result.get("document_id")
                if doc_id in doc_ids and doc_id not in fatos_by_doc:
                    fatos_by_doc[doc_id] = {"document_id": doc_id, **single}
            for item in (result.get("auto_infracao_fatos") or []):
                doc_id = item.get("document_id") if isinstance(item, dict) else None
                if doc_id in doc_ids and doc_id not in fatos_by_doc:
                    fatos_by_doc[doc_id] = item

        if not fatos_by_doc:
            return []

        # Titular atual (item 9): Client do processo + proprietários da Matrícula.
        titular_nome = titular_cpf = None
        matricula_proprietarios: list[dict[str, Any]] = []
        process = (
            self.ctx.session.query(Process)
            .filter(Process.id == self.ctx.process_id, Process.tenant_id == self.ctx.tenant_id)
            .first()
        )
        if process and process.client_id:
            client = self.ctx.session.query(Client).filter(Client.id == process.client_id).first()
            if client:
                titular_nome, titular_cpf = client.full_name, client.cpf_cnpj
        if process and process.property_id:
            prop = self.ctx.session.query(Property).filter(Property.id == process.property_id).first()
            if prop:
                for m in prop.matriculas or []:
                    matricula_proprietarios.extend(m.proprietarios or [])

        fatos: list[dict[str, Any]] = []
        for doc_id, fato in fatos_by_doc.items():
            enriched = dict(fato)
            enriched["enquadramento_fontes"] = lookup_enquadramento(
                fato.get("enquadramento_legal"),
                db_session=self.ctx.session,
                tenant_id=self.ctx.tenant_id,
            )
            enriched["nota_titular_divergente"] = check_autuado_diverge_titular(
                fato.get("autuado_nome"),
                fato.get("autuado_cpf"),
                titular_nome=titular_nome,
                titular_cpf=titular_cpf,
                matricula_proprietarios=matricula_proprietarios,
            )
            fatos.append(enriched)
        return fatos

    def _load_persisted_extraction(self, process_data: dict[str, Any]) -> dict[str, Any] | None:
        """Busca os campos extraídos persistidos nos ``AIJob`` do extrator quando
        a chain não os trouxe. Mescla o job mais recente de CADA documento
        (most-recent-wins) e devolve no mesmo shape de ``chain_data['extrator']``.

        Cobre ambos os shapes de job: ``entity_type='process'`` (ExtratorAgent,
        agent_name='extrator') e ``entity_type='document'`` (document_extractor,
        agent_name=None). Por isso filtra por ``job_type`` + entidade, não por
        agent_name. Ordena por ``id`` desc (monotônico → mais recente primeiro).
        """
        from sqlalchemy import and_, or_  # noqa: PLC0415

        from app.models.ai_job import AIJob, AIJobStatus, AIJobType  # noqa: PLC0415

        pid = self.ctx.process_id
        doc_ids = [
            d.get("id")
            for d in process_data.get("documents", [])
            if isinstance(d, dict) and d.get("id") is not None
        ]

        entity_conds = [and_(AIJob.entity_type == "process", AIJob.entity_id == pid)]
        if doc_ids:
            entity_conds.append(
                and_(AIJob.entity_type == "document", AIJob.entity_id.in_(doc_ids))
            )

        jobs = (
            self.ctx.session.query(AIJob)
            .filter(
                AIJob.tenant_id == self.ctx.tenant_id,
                AIJob.job_type == AIJobType.extract_document,
                AIJob.status == AIJobStatus.completed,
            )
            .filter(or_(*entity_conds))
            .order_by(AIJob.id.desc())
            .all()
        )
        if not jobs:
            return None

        aggregated: dict[str, Any] = {}
        seen_docs: set[Any] = set()
        for job in jobs:
            result = job.result if isinstance(job.result, dict) else {}
            # Identifica o documento dessa extração para dedupe "mais recente vence".
            doc_key = result.get("document_id")
            if doc_key is None and job.entity_type == "document":
                doc_key = job.entity_id
            if doc_key is not None:
                if doc_key in seen_docs:
                    continue
                seen_docs.add(doc_key)
            for key, value in self._fields_from_job_result(result).items():
                if key not in aggregated and value not in (None, "", {}, []):
                    aggregated[key] = value

        if not aggregated:
            return None

        logger.info(
            "diagnostico.extracted_fields_fallback process=%s docs=%d fields=%d "
            "— chain_data vazio, campos recuperados de AIJob persistido",
            pid, len(seen_docs), len(aggregated),
        )
        return {
            "extracted_fields": aggregated,
            "doc_type": "multiplos",
            "_source": "persisted_aijob",
            "documents_count": len(seen_docs),
        }

    def _load_persisted_legislacao(self) -> dict[str, Any] | None:
        """Busca o ``result`` do AIJob mais recente da legislacao do MESMO
        processo (status completed) quando a chain não trouxe ``legislacao``.
        Filtra por ``agent_name='legislacao'`` (job_type é consulta_regulatoria)."""
        from app.models.ai_job import AIJob, AIJobStatus  # noqa: PLC0415

        job = (
            self.ctx.session.query(AIJob)
            .filter(
                AIJob.tenant_id == self.ctx.tenant_id,
                AIJob.entity_type == "process",
                AIJob.entity_id == self.ctx.process_id,
                AIJob.agent_name == "legislacao",
                AIJob.status == AIJobStatus.completed,
            )
            .order_by(AIJob.id.desc())
            .first()
        )
        if job is not None and isinstance(job.result, dict) and job.result:
            logger.info(
                "diagnostico.legal_context_fallback process=%s job=%s "
                "— chain_data vazio, enquadramento recuperado de AIJob persistido",
                self.ctx.process_id, job.id,
            )
            return job.result
        return None

    def _load_persisted_atendimento(self) -> dict[str, Any] | None:
        """Busca o ``result`` do AIJob mais recente do atendimento (classificacao
        da demanda) do MESMO processo (status completed).

        Item E (fix/teste-isis-rodada2): o atendimento NAO participa da chain
        ``diagnostico_completo`` (roda no create-case), entao o relato/demanda do
        consultor — inclusive o que so existe na abertura do caso e nao em
        documento (ex.: embargo relatado sem doc) — nunca chegava ao diagnostico.
        Diferente de extrator/legislacao (que preferem ``chain_data``), o
        atendimento e SEMPRE recuperado do AIJob persistido e entra como fonte
        ADICIONAL — nao concorre com extrator/legislacao.
        """
        from app.models.ai_job import AIJob, AIJobStatus  # noqa: PLC0415

        job = (
            self.ctx.session.query(AIJob)
            .filter(
                AIJob.tenant_id == self.ctx.tenant_id,
                AIJob.entity_type == "process",
                AIJob.entity_id == self.ctx.process_id,
                AIJob.agent_name == "atendimento",
                AIJob.status == AIJobStatus.completed,
            )
            .order_by(AIJob.id.desc())
            .first()
        )
        if job is not None and isinstance(job.result, dict) and job.result:
            logger.info(
                "diagnostico.atendimento_context process=%s job=%s "
                "— relato/demanda do consultor injetado como fonte adicional",
                self.ctx.process_id, job.id,
            )
            return job.result
        return None

    def _resolve_auditor_payload(self) -> dict[str, Any]:
        """Payload do auditor: ``chain_data`` quando disponível; senão o AIJob
        persistido (Ficha 02 / FASE 3, mesmo padrão do atendimento)."""
        payload = self.ctx.chain_data.get("auditor_imovel", {}) if isinstance(self.ctx.chain_data, dict) else {}
        if not payload:
            payload = self._load_persisted_auditor() or {}
        return payload if isinstance(payload, dict) else {}

    def _load_persisted_auditor(self) -> dict[str, Any] | None:
        """Busca o ``result`` do AIJob mais recente do auditor_imovel do MESMO
        processo (status completed) — traz a matriz de inconsistências e os
        findings quando a chain não os trouxe. Fonte ADICIONAL."""
        from app.models.ai_job import AIJob, AIJobStatus  # noqa: PLC0415

        job = (
            self.ctx.session.query(AIJob)
            .filter(
                AIJob.tenant_id == self.ctx.tenant_id,
                AIJob.entity_type == "process",
                AIJob.entity_id == self.ctx.process_id,
                AIJob.agent_name == "auditor_imovel",
                AIJob.status == AIJobStatus.completed,
            )
            .order_by(AIJob.id.desc())
            .first()
        )
        if job is not None and isinstance(job.result, dict) and job.result:
            logger.info(
                "diagnostico.auditor_context process=%s job=%s "
                "— matriz/findings do auditor recuperados de AIJob persistido",
                self.ctx.process_id, job.id,
            )
            return job.result
        return None

    def _property_from_extracted(self, extracted_data: Any) -> dict[str, Any] | None:
        """Monta um dict de propriedade mínimo a partir dos campos extraídos
        (municipio/uf/area/CAR/denominação) quando NÃO há Property persistida.

        Só enriquece o prompt — NÃO grava na Property (efeito colateral proibido).
        Marca ``_source='extracted_fields'`` para deixar a origem rastreável.
        """
        fields = extracted_data.get("extracted_fields") if isinstance(extracted_data, dict) else None
        if not isinstance(fields, dict) or not fields:
            return None

        def pick(*keys: str) -> Any:
            for key in keys:
                value = fields.get(key)
                if value not in (None, "", {}, []):
                    return value
            return None

        prop: dict[str, Any] = {}
        name = pick("denominacao_imovel", "property_name", "proprietario_nome", "nome_proprietario")
        municipality = pick("municipio", "municipality")
        state = pick("uf", "state")
        area = pick("area_total_ha", "area_hectares", "area_ha", "area")
        car_code = pick("numero_car", "car_code", "car_numero")

        if name:
            prop["name"] = name
        if municipality:
            prop["municipality"] = municipality
        if state:
            prop["state"] = state
        if area is not None:
            prop["total_area_ha"] = area
        if car_code:
            prop["car_code"] = car_code

        if not prop:
            return None
        prop["_source"] = "extracted_fields"
        return prop

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

        # PROMPT_4 Onda A — mesmo no path sem LLM, se o auditor já rodou na chain
        # consumimos os findings. O Diagnóstico é a interpretação; a matriz de
        # cruzamento vem do auditor independentemente do path.
        auditor_payload = self._resolve_auditor_payload()
        divergencias_auditor, riscos_auditor = self._consume_auditor_findings(auditor_payload)

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
            divergencias_auditor=divergencias_auditor,
            riscos_auditor=riscos_auditor,
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

    # --- Rastreabilidade (validação 06/06) ---------------------------------

    @staticmethod
    def _infer_fonte_tipo(s: str) -> str:
        low = s.lower()
        if "rat" in low or "go-rat" in low or "parecer" in low:
            return "rat"
        if "matriz" in low or "linha" in low:
            return "matriz"
        if any(t in low for t in ("lei", "art", "norma", "decreto", "resolu", "instru")):
            return "legislacao"
        if any(t in low for t in ("atendimento", "relato", "demanda")):
            return "atendimento"
        if any(t in low for t in ("matric", "certid", "ccir", "itr", "car", "sigef", "documento", "escritura")):
            return "documento"
        return "documento"

    def _parse_item_fontes(self, raw: Any) -> list[Any]:
        """Converte a 'fonte' que o LLM atribuiu a um item → list[SourceRef].
        String vazia / 'sem fonte' → marca sem_fonte (NUNCA inventa)."""
        from app.schemas.stage_output import SourceRef  # noqa: PLC0415

        def _sem_fonte() -> Any:
            return SourceRef(tipo="sem_fonte", sem_fonte=True, descricao="sem fonte identificada")

        out: list[Any] = []
        items = raw if isinstance(raw, list) else [raw]
        for it in items:
            if isinstance(it, str):
                s = it.strip()
                if not s or "sem fonte" in s.lower():
                    out.append(_sem_fonte())
                else:
                    out.append(SourceRef(tipo=self._infer_fonte_tipo(s), descricao=s))
            elif isinstance(it, dict):
                desc = (it.get("descricao") or it.get("ref") or it.get("fonte") or "").strip()
                if not desc or "sem fonte" in desc.lower():
                    out.append(_sem_fonte())
                else:
                    out.append(SourceRef(
                        tipo=(it.get("tipo") if it.get("tipo") in {
                            "documento", "matriz", "rat", "legislacao", "atendimento", "auditor"
                        } else self._infer_fonte_tipo(desc)),
                        ref=it.get("ref"), descricao=desc, valor=it.get("valor"),
                    ))
        return out or [_sem_fonte()]

    # Stopwords PT-BR para casar texto de passivo/ação com a afirmação do LLM
    # (a redação do LLM raramente é idêntica à do passivo — casa pelo conteúdo).
    _AFIRMACAO_STOPWORDS = frozenset({
        "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "no", "na",
        "nos", "nas", "ao", "aos", "um", "uma", "para", "por", "com", "sem", "que",
        "ha", "ou", "the", "ja", "se", "entre",
    })

    @classmethod
    def _afirmacao_tokens(cls, texto: str) -> set:
        import re as _re  # noqa: PLC0415
        toks = _re.findall(r"[0-9a-zà-ÿ]+", str(texto).lower())
        return {t for t in toks if t not in cls._AFIRMACAO_STOPWORDS and len(t) > 1}

    def _build_afirmacoes_auto_infracao(self, autos_infracao: list[dict[str, Any]]) -> list[Any]:
        """Fase 1 (N2, item 7) — cada auto de infração vira UMA Afirmacao
        determinística (fato de passivo, não interpretação do LLM). Fontes:
        o próprio documento + as normas de enquadramento ACHADAS no corpus
        (item 8; não achada é marcada honesta, nunca inventada). Divergência
        autuado×titular (item 9) vira uma 2ª Afirmacao informativa — nunca
        bloqueia."""
        from app.schemas.stage_output import Afirmacao, SourceRef  # noqa: PLC0415

        out: list[Any] = []
        for fato in autos_infracao or []:
            numero = fato.get("numero_auto") or "s/número"
            orgao = fato.get("orgao_autuante") or "órgão não identificado"
            descricao = fato.get("descricao_infracao") or "infração sem descrição extraída"
            texto = f"Auto de infração {numero} ({orgao}): {descricao}"

            fontes: list[Any] = [SourceRef(
                tipo="documento", ref=str(fato.get("document_id")) if fato.get("document_id") else None,
                descricao=f"Auto de infração {numero}",
            )]
            for enq in fato.get("enquadramento_fontes") or []:
                if enq.get("localizada"):
                    fontes.append(SourceRef(
                        tipo="legislacao", ref=str(enq.get("chunk_id")) if enq.get("chunk_id") else None,
                        descricao=enq.get("citacao"),
                    ))
                else:
                    fontes.append(SourceRef(
                        tipo="sem_fonte", sem_fonte=True,
                        descricao=f"{enq.get('citacao')} — não localizada no corpus",
                    ))
            out.append(Afirmacao(texto=texto, categoria="passivo", fontes=fontes))

            nota = fato.get("nota_titular_divergente")
            if nota:
                out.append(Afirmacao(
                    texto=nota, categoria="passivo",
                    fontes=[SourceRef(
                        tipo="documento", ref=str(fato.get("document_id")) if fato.get("document_id") else None,
                        descricao=f"Auto de infração {numero} × titular atual",
                    )],
                ))
        return out

    def _build_afirmacoes(self, parsed: dict[str, Any], passivos: list, acoes: list) -> list[Any]:
        """Cada passivo e cada ação vira UMA Afirmacao(texto, fontes), com
        COBERTURA 100% (Ficha 04, regra de ouro — validação Isis 16/06).

        A lista canônica exibida é passivos/ações. Para cada item, casa (por
        sobreposição de conteúdo, dentro da categoria) a fonte que o LLM atribuiu
        no campo `afirmacoes`; sem casamento → piso honesto "sem fonte
        identificada" (jamais inventa). Antes, se o LLM citasse só alguns, os
        demais passivos ficavam SEM fonte — agora nenhum fica órfão."""
        from app.schemas.stage_output import Afirmacao, SourceRef  # noqa: PLC0415

        sem = SourceRef(tipo="sem_fonte", sem_fonte=True, descricao="sem fonte identificada")

        # Índice do que o LLM atribuiu: (tokens, fontes, categoria).
        llm_items: list[tuple[set, list[Any], str]] = []
        raw = parsed.get("afirmacoes")
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                texto = (item.get("texto") or item.get("afirmacao") or "").strip()
                if not texto:
                    continue
                fontes = self._parse_item_fontes(item.get("fonte") or item.get("fontes"))
                cat = str(item.get("categoria") or "").strip().lower()
                llm_items.append((self._afirmacao_tokens(texto), fontes, cat))

        def _fonte_for(text: str, categoria: str) -> list[Any]:
            toks = self._afirmacao_tokens(text)
            if not toks:
                return [sem]
            best_fontes, best_score = None, 0.0
            for ltoks, fontes, lcat in llm_items:
                if lcat in ("passivo", "acao") and lcat != categoria:
                    continue  # não cruza passivo↔ação
                if not ltoks:
                    continue
                # coeficiente de sobreposição (robusto a redação diferente)
                score = len(toks & ltoks) / min(len(toks), len(ltoks))
                if score > best_score:
                    best_fontes, best_score = fontes, score
            return best_fontes if best_fontes is not None and best_score >= 0.6 else [sem]

        afirmacoes: list[Any] = []
        for p in passivos:
            if isinstance(p, str) and p.strip():
                afirmacoes.append(Afirmacao(texto=p.strip(), categoria="passivo",
                                            fontes=_fonte_for(p, "passivo")))
        for a in acoes:
            if isinstance(a, str) and a.strip():
                afirmacoes.append(Afirmacao(texto=a.strip(), categoria="acao",
                                            fontes=_fonte_for(a, "acao")))

        # Edge: payload só com `afirmacoes` (sem passivos/ações) — preserva-as.
        if not afirmacoes and isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                texto = (item.get("texto") or item.get("afirmacao") or "").strip()
                if texto:
                    afirmacoes.append(Afirmacao(
                        texto=texto, categoria=item.get("categoria"),
                        fontes=self._parse_item_fontes(item.get("fonte") or item.get("fontes")),
                    ))
        return afirmacoes

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
        divergencias_auditor: list[Divergencia] | None = None,
        riscos_auditor: list[Risco] | None = None,
        afirmacoes: list[Any] | None = None,
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

        PROMPT_4 Onda A:
        * ``divergencias_auditor`` → ``divergencias`` (matriz de cruzamento do auditor).
        * ``riscos_auditor`` → entram ANTES do risco do LLM (primeiro movimento).
        * ``nivel_risco_geral`` derivado do "pior" grau entre os riscos do auditor
          quando houver — preserva alto vs. crítico (não usa o severity de 3).
        """
        divergencias_auditor = divergencias_auditor or []
        riscos_auditor = riscos_auditor or []

        # Garantia mínima de não-vazio em ``content`` (validator do schema)
        content_text = situacao_geral or "Diagnóstico sem síntese textual."

        # severidade do Risco do LLM continua no enum legado {baixo, medio, alto}.
        # O Risco do auditor carrega `grau` próprio (4 níveis), sem colapsar aqui.
        normalized_severidade = (risco_estimado or "medio").strip().lower()
        if normalized_severidade not in {"baixo", "medio", "alto"}:
            logger.warning(
                "diagnostico.invalid_severidade '%s' → fallback 'medio'", risco_estimado,
            )
            normalized_severidade = "medio"

        # Risco do LLM (síntese textual). Os do auditor vêm antes — são o
        # "primeiro movimento" (matriz de cruzamento) que pauta a interpretação.
        risco_llm = Risco(
            descricao=(situacao_geral or "Risco preliminar identificado")[:200],
            severidade=normalized_severidade,  # type: ignore[arg-type]
        )
        riscos: list[Risco] = list(riscos_auditor) + [risco_llm]

        # nivel_risco_geral derivado do pior grau encontrado entre os findings
        # do auditor (preserva os 4 níveis). Sem auditor na chain, fica None —
        # o LLM atualmente não popula esse campo direto.
        nivel_risco_geral = self._derive_nivel_risco_geral(riscos_auditor)

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
                divergencias=divergencias_auditor,
                nivel_risco_geral=nivel_risco_geral,  # type: ignore[arg-type]
                afirmacoes=afirmacoes or [],
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

    # ------------------------------------------------------------------
    # PROMPT_4 Onda A — consumo de chain_data["auditor_imovel"]
    # ------------------------------------------------------------------

    def _consume_auditor_findings(
        self,
        auditor_payload: dict[str, Any],
    ) -> tuple[list[Divergencia], list[Risco]]:
        """Lê os findings do AuditorImovelAgent e os transforma em
        ``Divergencia`` (matriz de cruzamento) + ``Risco`` (com ``grau`` em
        4 níveis preservado).

        O auditor é a fonte do cruzamento documental — o Diagnóstico não refaz
        a conta. Esta função é o "primeiro movimento" da skill diagnostico:
        recebe os findings prontos e os incorpora no payload do diagnóstico
        para alimentar hipóteses, riscos e enquadramento downstream.

        Retorna ``([], [])`` quando:
        - não há ``chain_data["auditor_imovel"]`` (chain sem auditor),
        - ``findings_raw`` está vazio,
        - o payload do auditor não tem o shape esperado.
        """
        if not isinstance(auditor_payload, dict):
            return [], []

        findings_raw = auditor_payload.get("findings_raw")
        if not isinstance(findings_raw, list):
            return [], []

        divergencias: list[Divergencia] = []
        riscos: list[Risco] = []

        for raw in findings_raw:
            if not isinstance(raw, dict):
                continue

            tema = str(raw.get("tema") or "").strip()
            descricao = str(raw.get("descricao") or "").strip()
            impacto = str(raw.get("impacto") or "").strip()
            # PROMPT_5: payload do auditor passou de `type` (4 valores
            # genéricos) para `codigo_alerta` + `familia` (taxonomia rica).
            # Compat retroativa: se `codigo_alerta`/`familia` ausentes (payload
            # antigo), tentamos o `type` legado como fallback para descrição.
            codigo_alerta = str(raw.get("codigo_alerta") or "").strip()
            familia = str(raw.get("familia") or "").strip()
            grade = str(raw.get("grade") or "").strip()
            evidencia_raw = raw.get("evidencia")

            # Divergencia exige os 3 campos não-vazios. Se faltar algum,
            # pulamos esse finding como divergência (ainda assim pode virar
            # risco se grade/descricao existirem).
            if tema and descricao and impacto:
                try:
                    divergencias.append(Divergencia(
                        tema=tema,
                        divergencia=descricao,
                        impacto=impacto,
                    ))
                except ValidationError:
                    logger.warning(
                        "diagnostico.auditor_finding.divergencia_invalida codigo=%s",
                        codigo_alerta,
                    )

            # Risco com `grau` preservado (4 níveis). Falta de grade conhecido
            # → não viraliza em risco (finding novo sem mapeamento ainda; o
            # consultor ainda enxerga via `divergencias`).
            grau = _GRADE_TO_GRAU.get(grade)
            if not grau or not descricao:
                continue

            # Categoria a partir de `familia` (PROMPT_5). Default
            # `cadastral_sistemico` cobre familias desconhecidas (catálogo
            # evolutivo permite famílias futuras).
            categoria = _FAMILIA_TO_CATEGORIA.get(familia, "cadastral_sistemico")
            evidencia_str = self._evidencia_to_str(evidencia_raw)

            try:
                riscos.append(Risco(
                    categoria=categoria,  # type: ignore[arg-type]
                    risco_identificado=descricao[:500],
                    grau=grau,  # type: ignore[arg-type]
                    impacto_possivel=impacto[:500] if impacto else None,
                    evidencia=evidencia_str,
                ))
            except ValidationError:
                logger.warning(
                    "diagnostico.auditor_finding.risco_invalido codigo=%s grade=%s",
                    codigo_alerta, grade,
                )

        return divergencias, riscos

    @staticmethod
    def _evidencia_to_str(value: Any) -> str | None:
        """Serializa a evidência do finding (dict cru do auditor) em string
        legível para o campo ``Risco.evidencia``. Mantém auditabilidade
        (Princípio 2) sem perder o detalhe do cruzamento."""
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip() or None
        if isinstance(value, dict):
            try:
                return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
            except (TypeError, ValueError):
                return str(value)
        return str(value)

    @staticmethod
    def _derive_nivel_risco_geral(riscos_auditor: list[Risco]) -> str | None:
        """Calcula ``nivel_risco_geral`` (4 níveis) pelo "pior" grau encontrado
        nos riscos vindos do auditor. Retorna ``None`` quando não há riscos do
        auditor — o LLM atualmente não popula esse campo direto."""
        if not riscos_auditor:
            return None
        worst_rank = -1
        worst_grau: str | None = None
        for risco in riscos_auditor:
            grau = risco.grau
            if grau is None:
                continue
            rank = _GRAU_RANK.get(grau, -1)
            if rank > worst_rank:
                worst_rank = rank
                worst_grau = grau
        if worst_grau is None:
            return None
        return _GRAU_TO_NIVEL_RISCO.get(worst_grau)

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
                "REGRA INVIOLAVEL — NENHUMA AFIRMACAO SEM FONTE: toda afirmacao (passivo, acao) deve citar "
                "DE ONDE veio, referenciando um insumo concreto fornecido (matriz de inconsistencias, RAT por "
                "protocolo, certidao/CCIR/ITR/CAR, relato do atendimento). Se NAO houver fonte identificavel "
                "nos insumos, escreva a fonte como \"sem fonte identificada\" — NUNCA invente fonte nem use "
                "generico (\"conforme documentos\"). Preferir OMITIR a inventar. "
                "Retorne APENAS JSON valido com: situacao_geral (str), passivos_identificados (list[str]), "
                "acoes_remediacao (list[str]), prioridade_acoes (list[str]), risco_estimado (baixo|medio|alto), "
                "observacoes (str), e afirmacoes (list de objetos {texto, categoria (passivo|acao), "
                "fonte}) — uma entrada por passivo e por acao, cada uma com sua fonte especifica ou "
                "\"sem fonte identificada\"."
            ),
            "diagnostico_user": (
                "Analise este imovel rural. Os INSUMOS abaixo sao as UNICAS fontes validas para citar.\n\n"
                "PROPRIEDADE: {property_data}\n\n"
                "PROCESSO (inclui matriz_inconsistencias e relato_demanda_consultor quando houver): {process_data}\n\n"
                "DOCUMENTOS: {documents}\n\n"
                "DADOS EXTRAIDOS (campos por documento): {extracted_fields}\n\n"
                "CONTEXTO LEGAL: {legal_context}\n\n"
                "Retorne o JSON de diagnostico. Em 'afirmacoes', CADA passivo e CADA acao deve apontar a fonte "
                "especifica (ex.: \"RAT GO-RAT-2024-002207 — pendencia de cobertura\", \"matriz: linha area\", "
                "\"certidao matricula 6.776\", \"relato do atendimento\") ou \"sem fonte identificada\"."
            ),
        }
