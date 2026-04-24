"""
LegislacaoAgent — Enquadramento regulatorio com base de conhecimento legislativa.

Arquitetura:
1. Carrega contexto do processo (demand_type, UF, municipio, propriedade)
2. Busca documentos legislativos relevantes por metadados no banco
3. Envia legislacao COMPLETA no contexto do LLM (Gemini 2M tokens ou Claude)
4. LLM analisa o caso contra a legislacao e retorna caminho regulatorio

Usa Claude Sonnet para raciocinio juridico por padrao.
Fallback para Gemini (context loading grande) quando legislacao e extensa.
"""

from __future__ import annotations

import json
from typing import Any

from app.agents.base import AgentRegistry, BaseAgent
from app.agents.validators import OutputValidationPipeline
from app.models.ai_job import AIJobType


@AgentRegistry.register
class LegislacaoAgent(BaseAgent):
    name = "legislacao"
    description = "Enquadramento regulatório com raciocínio jurídico apoiado por base de legislação"
    job_type = AIJobType.consulta_regulatoria
    prompt_slugs = ["legislacao_system", "legislacao_user"]
    palace_room = "agent_legislacao"

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

        # Buscar legislacao relevante no banco
        legislation_context = self._load_legislation_context(
            demand_type=demand_type,
            uf=state,
        )

        # MemPalace: enriquecer com casos passados similares
        memory_context = ""
        recall = self.recall_memory(f"legislacao {demand_type} {state}")
        if recall.get("recent_diary"):
            entries = [e.get("entry", "") if isinstance(e, dict) else str(e) for e in recall["recent_diary"][:3]]
            memory_context = "\n".join(f"- {e}" for e in entries if e)
        if recall.get("search_results"):
            hits = [r.get("text", "")[:200] if isinstance(r, dict) else str(r)[:200] for r in recall["search_results"][:3]]
            memory_context += "\n" + "\n".join(f"- {h}" for h in hits if h)

        # Montar prompts
        system_prompt = self.get_prompt("legislacao_system")
        user_prompt = self.get_prompt("legislacao_user", {
            "query": query,
            "demand_type": demand_type or "nao_identificado",
            "state": state or "nao_informado",
            "context": json.dumps(process_context, ensure_ascii=False, default=str),
            "legislation": legislation_context,
        })

        # Anexar contexto historico do MemPalace ao prompt
        if memory_context.strip():
            user_prompt += (
                "\n\nCASOS ANTERIORES SIMILARES (base de conhecimento interna):\n"
                + memory_context
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

        result = {
            "caminho_regulatorio": parsed.get("caminho_regulatorio", ""),
            "orgao_competente": parsed.get("orgao_competente", ""),
            "etapas": parsed.get("etapas", []),
            "legislacao_aplicavel": parsed.get("legislacao_aplicavel", []),
            "riscos": parsed.get("riscos", []),
            "documentos_necessarios": parsed.get("documentos_necessarios", []),
            "prazos_estimados": parsed.get("prazos_estimados", {}),
            "confianca": parsed.get("confianca", "media"),
            "justificativa": parsed.get("justificativa", ""),
            "recomendacoes": parsed.get("recomendacoes", []),
            "confidence": parsed.get("confianca", "medium"),
            "requires_review": True,
            # Backward compat com formato antigo
            "normas_estaduais": parsed.get("normas_estaduais", []),
            "risco_legal": parsed.get("risco_legal", parsed.get("confianca", "medio")),
            "prazos_legais": parsed.get("prazos_legais", []),
        }

        self.requires_review = True  # sempre requer revisao humana (consequencias juridicas)
        return result

    def _call_claude(self, prompt: str, *, system: str = "") -> Any:
        """Chama Claude diretamente via Anthropic SDK."""
        from app.core.claude_client import ClaudeClient
        client = ClaudeClient()
        response = client.complete(prompt, system=system)
        self._llm_response = response
        return response

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
        """Resposta basica sem LLM com legislacao federal padrao."""
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
        return {
            "caminho_regulatorio": f"Verificar legislacao para {demand_type or 'tipo nao identificado'}",
            "orgao_competente": "A definir conforme UF e tipo",
            "etapas": [],
            "legislacao_aplicavel": legislacao.get(demand_type or "", ["Consulte legislacao especifica"]),
            "riscos": [],
            "documentos_necessarios": [],
            "prazos_estimados": {},
            "confianca": "baixa",
            "justificativa": "Resposta baseada em regras — IA nao configurada",
            "recomendacoes": ["Habilitar IA para analise regulatoria completa"],
            "normas_estaduais": [f"Verificar legislacao estadual para {state or 'UF nao informada'}"],
            "risco_legal": "medio",
            "prazos_legais": [],
            "confidence": "low",
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
                "Retorne APENAS JSON valido com os campos:\n"
                "caminho_regulatorio (str), orgao_competente (str), "
                "etapas (list[{ordem, titulo, descricao, prazo_estimado_dias, orgao}]), "
                "legislacao_aplicavel (list[{identificador, titulo, relevancia}]), "
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
                "BASE LEGISLATIVA DISPONIVEL:\n{legislation}\n\n"
                "Com base na legislacao acima e no seu conhecimento, "
                "retorne o JSON com o enquadramento regulatorio completo."
            ),
        }
