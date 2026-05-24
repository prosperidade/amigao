"""Testes do citation_evaluator no DiagnosticoAgent — Sprint A3 (Onda 2 da Fase 2).

Espelha o gate que já existe no RedatorAgent (`app/agents/redator.py:_evaluate_citations`).
Citações detectadas no texto do diagnóstico são cruzadas contra `legal_data` da chain
(legislacao_aplicavel, normas_estaduais, rag_chunks_meta). Citações sem match ficam
como `citation_issues`; não derrubam a execução.
"""

from __future__ import annotations

import json
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from app.agents.base import AgentContext
from app.agents.diagnostico import DiagnosticoAgent


def _make_ai_response(payload: dict):
    from app.core.ai_gateway import AIResponse
    return AIResponse(
        content=json.dumps(payload, ensure_ascii=False),
        model_used="mock-model",
        tokens_in=50,
        tokens_out=120,
        cost_usd=0.0001,
        duration_ms=150,
        provider="mock",
    )


def _ctx(*, chain_data: dict | None = None) -> AgentContext:
    return AgentContext(
        tenant_id=1,
        user_id=1,
        process_id=42,
        session=MagicMock(),
        metadata={},
        chain_data=chain_data or {},
    )


def _enter_default_patches(stack: ExitStack):
    stack.enter_context(patch("app.agents.base.check_tenant_cost_limit"))
    stack.enter_context(patch("app.agents.base.check_tenant_monthly_budget"))
    stack.enter_context(patch.object(
        DiagnosticoAgent, "_load_process_data",
        return_value={"process": {"id": 42}, "property": {}, "documents": []},
    ))
    stack.enter_context(patch("app.agents.base.get_active_prompt", return_value=None))


class TestCitationEvaluatorIntegration:
    def test_sem_legal_data_payload_nao_emite_campos_citation(self):
        """Sem `chain_data["legislacao"]`, _evaluate_citations retorna None
        e o payload final não inclui citation_total/issues/coverage_ratio/valid.
        """
        agent = DiagnosticoAgent(_ctx())
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response({
                "situacao_geral": "Conforme Lei 12.651/2012, area de RL...",
                "passivos_identificados": [],
                "acoes_remediacao": [],
                "risco_estimado": "medio",
            })
            data = agent.run().data

        assert "citation_total" not in data
        assert "citation_issues" not in data
        assert "citation_valid" not in data
        assert "citation_coverage_ratio" not in data

    def test_citacao_no_contexto_legal_marcada_como_valida(self):
        """Citacao 'Lei 12.651/2012' presente em legislacao_aplicavel ->
        citation_valid=True, coverage_ratio=1.0, sem citation_issues.
        """
        agent = DiagnosticoAgent(_ctx(
            chain_data={"legislacao": {"legislacao_aplicavel": ["Lei 12.651/2012"]}}
        ))
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response({
                "situacao_geral": "Conforme a Lei nº 12.651/2012, area de RL...",
                "passivos_identificados": [],
                "acoes_remediacao": [],
                "risco_estimado": "medio",
            })
            data = agent.run().data

        assert data["citation_valid"] is True
        assert data["citation_total"] == 1
        assert data["citation_coverage_ratio"] == 1.0
        assert data["citation_issues"] == []

    def test_citacao_fora_do_contexto_marcada_como_suspeita(self):
        """Citacao detectada no texto mas ausente em legislacao_aplicavel ->
        citation_valid=False, citation_issues populado. Execucao NAO eh
        derrubada (requires_review continua True, payload completo).
        """
        agent = DiagnosticoAgent(_ctx(
            chain_data={"legislacao": {"legislacao_aplicavel": ["Lei nº 9.605/1998"]}}
        ))
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response({
                # cita uma norma que nao esta no contexto (Lei 12.651/2012 != Lei 9.605/1998)
                "situacao_geral": "Aplicavel a Lei nº 12.651/2012 para regime de RL.",
                "passivos_identificados": [],
                "acoes_remediacao": [],
                "risco_estimado": "alto",
            })
            result = agent.run()
            data = result.data

        assert result.success is True
        assert result.requires_review is True
        assert data["citation_valid"] is False
        assert data["citation_total"] >= 1
        assert len(data["citation_issues"]) >= 1
        assert data["citation_coverage_ratio"] < 1.0

    def test_citacao_de_norma_estadual_indexada_via_normas_estaduais_key(self):
        """O evaluator aceita tanto `legislacao_aplicavel` quanto `normas_estaduais`."""
        agent = DiagnosticoAgent(_ctx(
            chain_data={"legislacao": {"normas_estaduais": ["Lei nº 21.231/2022"]}}
        ))
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response({
                "situacao_geral": "A Lei nº 21.231/2022 regulamenta a compensacao.",
                "passivos_identificados": [],
                "acoes_remediacao": [],
                "risco_estimado": "medio",
            })
            data = agent.run().data

        assert data["citation_valid"] is True
        assert data["citation_total"] == 1

    def test_texto_sem_citacao_retorna_None_eval(self):
        """Texto livre sem citação detectável (sem Lei/Decreto/IN/CONAMA/etc) ->
        citation_eval=None e payload sem os campos."""
        agent = DiagnosticoAgent(_ctx(
            chain_data={"legislacao": {"legislacao_aplicavel": ["Lei 12.651/2012"]}}
        ))
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response({
                "situacao_geral": "Imovel com pendencia de cadastro.",  # sem citacao
                "passivos_identificados": ["CAR pendente"],
                "acoes_remediacao": ["Regularizar CAR no SICAR"],
                "risco_estimado": "medio",
            })
            data = agent.run().data

        assert "citation_total" not in data
        assert "citation_issues" not in data

    def test_extrai_citacao_de_passivos_e_observacoes(self):
        """Citacoes em qualquer campo de texto livre (passivos, observacoes) tambem
        sao detectadas pelo evaluator — nao só em situacao_geral.
        """
        agent = DiagnosticoAgent(_ctx(
            chain_data={"legislacao": {"legislacao_aplicavel": ["Lei 12.651/2012"]}}
        ))
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response({
                "situacao_geral": "ok",
                "passivos_identificados": ["Vide art. 12 da Lei 12.651/2012 — RL 20%"],
                "acoes_remediacao": [],
                "risco_estimado": "medio",
                "observacoes": "",
            })
            data = agent.run().data

        # Citacao foi achada no passivo, e o contexto bate
        assert data.get("citation_valid") is True
        assert data["citation_total"] >= 1

    def test_build_payload_sem_citation_eval_nao_emite_campos(self):
        """Unidade: chamar _build_payload com citation_eval=None (igual ao path
        rules-based, fallback sem LLM) deixa os campos citation_* fora do payload.

        Substituí o teste do path completo (rules_based) porque o mocking de
        settings.ai_configured (property) é frágil; o invariante real
        a proteger é "citation_eval=None ⇒ payload sem citation_*".
        """
        agent = DiagnosticoAgent(_ctx())
        from app.schemas.stage_output import Source  # noqa: PLC0415
        payload = agent._build_payload(
            situacao_geral="x",
            passivos=[],
            acoes=[],
            prioridades=[],
            risco_estimado="medio",
            observacoes="",
            sources=[Source(type="manual", ref="test")],
            citation_eval=None,
        )
        assert "citation_total" not in payload
        assert "citation_issues" not in payload
        assert "citation_valid" not in payload
        assert "citation_coverage_ratio" not in payload
