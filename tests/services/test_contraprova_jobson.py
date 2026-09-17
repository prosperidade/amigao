"""Contraprovas do relatório 02, com entradas sintéticas, sem documentos reais."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.agents.auditor_imovel import AuditorImovelAgent
from app.agents.base import AgentContext
from app.agents.diagnostico import DiagnosticoAgent
from app.agents.legislacao import LegislacaoAgent
from app.schemas.intake import IntakeClientCreate
from app.services.inconsistency_matrix import build_matrix


def row(source, field, value, doc_id=1):
    return SimpleNamespace(
        source_doc_type=source, field_name=field, field_value={"value": value},
        document_id=doc_id, matricula_hint=None, status="pendente",
    )


def context():
    return AgentContext(tenant_id=1, user_id=1, process_id=25, session=MagicMock())


def test_sigef_ausente_nao_prova_risco_nem_gera_orcamento():
    result = build_matrix([row("car", "area_declarada_ha", "2,6893")])
    item = next(x for x in result.matriz["linhas"] if x["item"] == "sigef_georreferenciamento")
    assert item["situacao"] == "atencao"
    assert item["destino"] == ["alertas"]
    assert "não comprovada" in item["acao_recomendada"]


def test_fonte_unica_nao_confirma_denominacao_nem_gera_divergencia():
    result = build_matrix([row("car", "denominacao", "Fazenda Teste")])
    item = next(x for x in result.matriz["linhas"] if x["item"] == "denominacao_imovel")
    assert item["situacao"] == "atencao"
    assert "Fonte única" in item["acao_recomendada"]
    assert result.status_updates == []
    assert AuditorImovelAgent(context())._registral_findings_from_matriz(result.matriz) == []


def test_duas_fontes_ainda_confirmam_denominacao():
    result = build_matrix([
        row("car", "denominacao", "Fazenda Teste", 1),
        row("ccir", "denominacao", "Fazenda Teste", 2),
    ])
    item = next(x for x in result.matriz["linhas"] if x["item"] == "denominacao_imovel")
    assert item["situacao"] == "consistente"


def test_resumo_conta_pendencias_da_matriz_mesmo_sem_findings():
    agent = AuditorImovelAgent(context())
    matrix = build_matrix([row("car", "area_declarada_ha", "2,6893")]).matriz
    with (
        patch.object(agent, "_load_process_data", return_value={}),
        patch.object(agent, "_build_matriz_inconsistencias", return_value=matrix),
        patch.object(agent, "_persist_issues", return_value=[]),
        patch("app.agents.auditor_imovel.audit_property", return_value=[]),
    ):
        result = agent.execute()
    count = sum(x["situacao"] != "consistente" for x in matrix["linhas"])
    assert count > 0
    assert f"{count} ponto(s) para revisão" in result["content"]
    assert "0 divergência" not in result["content"]
    assert sum(result["matriz_inconsistencias"]["resumo"].values()) == len(matrix["linhas"])


@pytest.mark.parametrize("email", ["a@", "a@@example.com", "nome sem email", "a b@example.com"])
def test_email_invalido_rejeitado_antes_da_persistencia(email):
    with pytest.raises(ValidationError):
        IntakeClientCreate(full_name="Teste", email=email)


def test_email_valido_preserva_valor_informado():
    value = "Nome.Sobrenome+car@example.com"
    assert IntakeClientCreate(full_name="Teste", email=value).email == value


@pytest.mark.parametrize("official, expected", [("nao_identificado", "car"), ("defesa", "defesa")])
def test_legislacao_usa_objetivo_sem_promover_demanda(official, expected):
    agent = LegislacaoAgent(context())
    process = {"demand_type": official, "process_type": "car", "state": "GO"}
    with (
        patch.object(agent, "_load_process_context", return_value=process),
        patch("app.core.config.settings") as settings,
        patch.object(agent, "_rules_based_response", return_value={}) as fallback,
    ):
        settings.ai_configured = False
        agent.execute()
    fallback.assert_called_once_with(expected, "GO")
    assert process["demand_type"] == official


@pytest.mark.parametrize("metadata, state, expected", [({}, "GO", "GO"), ({"uf": "MT"}, "GO", "MT"), ({}, None, None)])
def test_diagnostico_carrega_skill_no_caminho_sem_metadados(metadata, state, expected):
    ctx = context()
    ctx.metadata = dict(metadata)
    ctx.chain_data = {"extrator": {"extracted_fields": {"area": 2.6893}}, "legislacao": {"content": "contexto"}}
    agent = DiagnosticoAgent(ctx)
    with (
        patch.object(agent, "_load_process_data", return_value={"process": {}, "property": {"state": state}}),
        patch.object(agent, "_load_persisted_atendimento", return_value={}),
        patch.object(agent, "_resolve_auditor_payload", return_value={}),
        patch.object(agent, "_load_auto_infracao_fatos", return_value=[]),
        patch("app.core.config.settings") as settings,
        patch.object(agent, "_rules_based_diagnosis", return_value={}),
    ):
        settings.ai_configured = False
        agent.execute()
    assert ctx.metadata.get("uf") == expected
    skill_names = [s.metadata.name for s in agent._load_skills_for_context()]
    assert ("diagnostico/situacao_ambiental_imovel_rural" in skill_names) == (expected is not None)
    assert metadata == ({"uf": "MT"} if expected == "MT" else {})
