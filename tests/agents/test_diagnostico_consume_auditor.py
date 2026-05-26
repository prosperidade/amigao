"""Testes do consumo de ``chain_data["auditor_imovel"]`` pelo DiagnosticoAgent.

PROMPT_4 Onda A — Diagnóstico passa a consumir os findings do auditor como
"primeiro movimento" (matriz de cruzamento documental), preservando o
``grade`` de 4 níveis (informativo/atencao/alto/critico) sem colapsar
alto vs. crítico no severity de 3 do RegulatoryIssue.

Cobre:
* Sem auditor na chain → diagnostico funciona normal (riscos só do LLM,
  divergencias=[], nivel_risco_geral=None).
* Com auditor com findings em vários graus → cada finding vira
  ``Divergencia`` + ``Risco`` com `grau` preservado.
* Grade ``critico`` → ``grau="critico_impeditivo_potencial"`` (NÃO colapsa).
* nivel_risco_geral derivado do pior grau dos findings (alto vs crítico
  preservado — dívida #4 do REGISTRO_DIVIDAS.md).
* Riscos do auditor vêm ANTES do risco do LLM (primeiro movimento).
* Payload do auditor malformado / vazio é tratado com graciosidade.
* Mapeamento de categoria por finding.type.
* Não duplica cruzamento — auditor é fonte única.
"""

from __future__ import annotations

import json
from contextlib import ExitStack
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from app.agents.base import AgentContext
from app.agents.diagnostico import (
    DiagnosticoAgent,
    _FAMILIA_TO_CATEGORIA,
    _GRADE_TO_GRAU,
)


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


def _default_llm_payload() -> dict:
    return {
        "situacao_geral": "Imóvel com pendência no SICAR.",
        "passivos_identificados": ["CAR pendente"],
        "acoes_remediacao": ["Resolver pendência"],
        "prioridade_acoes": ["resolver_car"],
        "risco_estimado": "medio",
        "observacoes": "Caso em análise.",
    }


# PROMPT_5 atalhos: tipos antigos do PROMPT_4 mapeados para a taxonomia rica
# (codigo_alerta + familia). O parâmetro `type_` virou alias semântico —
# resolvido para (codigo_alerta, familia) via este mapa.
_FINDING_TYPE_TO_RICH = {
    "area_divergente": ("AREA_MATRICULA_X_CAR", "area"),
    "rl_divergente": ("RL_MATRICULA_DIVERGENTE_RL_CAR", "ambiental"),
    "geo_incra_ausente": ("GEO_AUSENTE", "geo_incra"),
    "verificacao_espacial_pendente": ("VERIFICACAO_ESPACIAL_PENDENTE", "geoespacial"),
}


def _finding(
    *,
    type_: str = "area_divergente",
    grade: str = "atencao",
    codigo_alerta: str | None = None,
    familia: str | None = None,
    tema: str = "área (matrícula × CAR)",
    descricao: str = "Áreas divergentes: 100 ha vs 80 ha (Δ 20 ha, 20.00%)",
    impacto: str = "Passivo, compensação e recuperação são calculados em hectares.",
    evidencia: dict | None = None,
) -> dict:
    """Builder do raw finding como o auditor emite no payload (PROMPT_5).

    `type_` é alias retrocompatível dos testes — resolve para
    (codigo_alerta, familia) via `_FINDING_TYPE_TO_RICH`. Passar `codigo_alerta`/
    `familia` diretos sobrescreve essa resolução (para testar códigos
    desconhecidos / família desconhecida)."""
    if codigo_alerta is None or familia is None:
        codigo_resolvido, familia_resolvida = _FINDING_TYPE_TO_RICH.get(
            type_, (type_.upper(), "validade_documental"),
        )
        if codigo_alerta is None:
            codigo_alerta = codigo_resolvido
        if familia is None:
            familia = familia_resolvida
    return {
        "codigo_alerta": codigo_alerta,
        "familia": familia,
        "grade": grade,
        "tema": tema,
        "descricao": descricao,
        "impacto": impacto,
        "evidencia": evidencia or {"area_a_ha": "100", "area_b_ha": "80"},
    }


def _enter_default_patches(stack: ExitStack):
    stack.enter_context(patch("app.agents.base.check_tenant_cost_limit"))
    stack.enter_context(patch("app.agents.base.check_tenant_monthly_budget"))
    stack.enter_context(patch.object(
        DiagnosticoAgent, "_load_process_data",
        return_value={"process": {"id": 42}, "property": {}, "documents": []},
    ))
    stack.enter_context(patch("app.agents.base.get_active_prompt", return_value=None))


@pytest.fixture(autouse=True)
def _isolate_skills(tmp_path, monkeypatch):
    monkeypatch.setattr("app.skills._registry.SKILLS_ROOT", tmp_path)
    from app.skills._registry import invalidate_cache
    invalidate_cache()


# ---------------------------------------------------------------------------
# Caso 1 — sem auditor na chain: comportamento atual preservado
# ---------------------------------------------------------------------------

class TestSemAuditor:
    def test_sem_auditor_diagnostico_funciona_e_divergencias_vazias(self):
        agent = DiagnosticoAgent(_ctx(chain_data={}))
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response(_default_llm_payload())
            data = agent.run().data

        assert data["divergencias"] == []
        # Só há o risco do LLM, no severity legado
        assert len(data["riscos"]) == 1
        risco = data["riscos"][0]
        # nivel_risco_geral=None quando sem auditor (LLM não popula)
        assert data.get("nivel_risco_geral") is None
        # severidade do LLM continua mapeando (dual-emit)
        assert risco["severidade"] == "medio"

    def test_auditor_payload_malformado_nao_quebra(self):
        """auditor_imovel presente mas sem findings_raw / shape inesperado."""
        agent = DiagnosticoAgent(_ctx(chain_data={"auditor_imovel": "lixo"}))
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response(_default_llm_payload())
            data = agent.run().data
        assert data["divergencias"] == []
        # findings_raw=None → idem
        agent2 = DiagnosticoAgent(_ctx(chain_data={"auditor_imovel": {"findings_raw": None}}))
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response(_default_llm_payload())
            data2 = agent2.run().data
        assert data2["divergencias"] == []


# ---------------------------------------------------------------------------
# Caso 2 — com auditor: findings viram divergencias + riscos com grau preservado
# ---------------------------------------------------------------------------

class TestComAuditor:
    def test_finding_atencao_vira_divergencia_e_risco_com_grau_correto(self):
        auditor_payload = {
            "findings_raw": [_finding(grade="atencao", type_="area_divergente")],
        }
        agent = DiagnosticoAgent(_ctx(chain_data={"auditor_imovel": auditor_payload}))
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response(_default_llm_payload())
            data = agent.run().data

        # 1 divergência
        assert len(data["divergencias"]) == 1
        div = data["divergencias"][0]
        assert div["tema"] == "área (matrícula × CAR)"
        assert div["divergencia"].startswith("Áreas divergentes")
        assert "hectares" in div["impacto"]

        # Riscos = auditor (1) + LLM (1)
        assert len(data["riscos"]) == 2
        risco_auditor = data["riscos"][0]  # auditor vem ANTES
        assert risco_auditor["grau"] == "atencao"
        assert risco_auditor["categoria"] == "cadastral_sistemico"
        # nivel_risco_geral derivado do pior do auditor
        assert data["nivel_risco_geral"] == "medio"

    def test_grade_critico_vira_grau_critico_impeditivo_potencial(self):
        """A distinção alto-vs-crítico não pode se perder no caminho — dívida #4
        do REGISTRO_DIVIDAS.md. Crítico do auditor vira `critico_impeditivo_potencial`,
        que é o gatilho da camada 2 do Princípio 1 (5 botões, sprint posterior)."""
        auditor_payload = {
            "findings_raw": [_finding(
                grade="critico",
                type_="area_divergente",
                descricao="Áreas divergentes: 100 ha vs 30 ha (70%)",
            )],
        }
        agent = DiagnosticoAgent(_ctx(chain_data={"auditor_imovel": auditor_payload}))
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response(_default_llm_payload())
            data = agent.run().data

        risco_auditor = data["riscos"][0]
        # NÃO colapsa em "alto" — grau crítico preservado integralmente
        assert risco_auditor["grau"] == "critico_impeditivo_potencial"
        assert data["nivel_risco_geral"] == "critico"

    def test_grade_informativo_preservado(self):
        auditor_payload = {
            "findings_raw": [_finding(
                grade="informativo",
                type_="verificacao_espacial_pendente",
                descricao="geom ausente — verificação espacial pendente",
            )],
        }
        agent = DiagnosticoAgent(_ctx(chain_data={"auditor_imovel": auditor_payload}))
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response(_default_llm_payload())
            data = agent.run().data

        risco_auditor = data["riscos"][0]
        assert risco_auditor["grau"] == "informativo"
        assert risco_auditor["categoria"] == "geoespacial"
        assert data["nivel_risco_geral"] == "baixo"

    def test_pior_grau_decide_nivel_risco_geral(self):
        """Quando convivem findings com graus diferentes, o pior decide
        ``nivel_risco_geral`` (alto vs crítico preservados nessa hierarquia)."""
        auditor_payload = {
            "findings_raw": [
                _finding(grade="informativo", type_="verificacao_espacial_pendente"),
                _finding(grade="alto", type_="area_divergente"),
                _finding(grade="atencao", type_="rl_divergente"),
            ],
        }
        agent = DiagnosticoAgent(_ctx(chain_data={"auditor_imovel": auditor_payload}))
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response(_default_llm_payload())
            data = agent.run().data
        # Pior é "alto" entre os 3
        assert data["nivel_risco_geral"] == "alto"

    def test_critico_vence_alto_no_pior_grau(self):
        auditor_payload = {
            "findings_raw": [
                _finding(grade="alto", type_="area_divergente"),
                _finding(grade="critico", type_="geo_incra_ausente"),
            ],
        }
        agent = DiagnosticoAgent(_ctx(chain_data={"auditor_imovel": auditor_payload}))
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response(_default_llm_payload())
            data = agent.run().data
        assert data["nivel_risco_geral"] == "critico"

    def test_riscos_do_auditor_vem_antes_do_risco_do_llm(self):
        """Auditor é o "primeiro movimento" — a matriz de cruzamento vem antes
        da síntese textual do LLM no array `riscos`."""
        auditor_payload = {
            "findings_raw": [
                _finding(grade="atencao", type_="area_divergente",
                         descricao="primeiro auditor"),
                _finding(grade="alto", type_="rl_divergente",
                         descricao="segundo auditor"),
            ],
        }
        agent = DiagnosticoAgent(_ctx(chain_data={"auditor_imovel": auditor_payload}))
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response(_default_llm_payload())
            data = agent.run().data

        riscos = data["riscos"]
        assert len(riscos) == 3
        # Auditor preserva ordem
        assert riscos[0]["risco_identificado"] == "primeiro auditor"
        assert riscos[1]["risco_identificado"] == "segundo auditor"
        # LLM por último — vem do `situacao_geral`
        assert "SICAR" in riscos[2]["risco_identificado"]

    def test_categoria_inferida_por_familia(self):
        """PROMPT_5: agora a categoria é mapeada por `familia` (11 valores
        estáveis) ao invés de `type` (4 valores genéricos)."""
        auditor_payload = {
            "findings_raw": [
                _finding(grade="alto", type_="area_divergente"),
                _finding(grade="alto", type_="rl_divergente"),
                _finding(grade="critico", type_="geo_incra_ausente"),
                _finding(grade="informativo", type_="verificacao_espacial_pendente"),
            ],
        }
        agent = DiagnosticoAgent(_ctx(chain_data={"auditor_imovel": auditor_payload}))
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response(_default_llm_payload())
            data = agent.run().data

        categorias = [r["categoria"] for r in data["riscos"][:4]]
        assert categorias == [
            "cadastral_sistemico",  # familia=area
            "ambiental",            # familia=ambiental
            "fundiario",            # familia=geo_incra
            "geoespacial",          # familia=geoespacial
        ]

    def test_grade_desconhecido_nao_vira_risco_mas_pode_virar_divergencia(self):
        """Finding novo do auditor com grade não mapeado: não inferimos grau, então
        não vira Risco. Mas se tema/descricao/impacto estão presentes, ainda
        vira Divergencia (auditor é radar — não suprimimos o cruzamento)."""
        auditor_payload = {
            "findings_raw": [_finding(
                grade="nao_mapeado_ainda",
                codigo_alerta="CODIGO_FUTURO",
                familia="validade_documental",
                tema="campo desconhecido",
                descricao="finding novo do futuro",
                impacto="ainda em validação",
            )],
        }
        agent = DiagnosticoAgent(_ctx(chain_data={"auditor_imovel": auditor_payload}))
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response(_default_llm_payload())
            data = agent.run().data

        # Divergência ainda emitida (radar não cancela)
        assert len(data["divergencias"]) == 1
        assert data["divergencias"][0]["tema"] == "campo desconhecido"
        # Mas só 1 risco (do LLM) — finding sem grade conhecido não vira Risco
        assert len(data["riscos"]) == 1
        assert data.get("nivel_risco_geral") is None

    def test_evidencia_vira_string_serializada_para_auditabilidade(self):
        """Evidência (dict do auditor) é serializada em string JSON no
        Risco.evidencia, preservando o detalhe do cruzamento (Princípio 2)."""
        auditor_payload = {
            "findings_raw": [_finding(
                grade="alto",
                evidencia={"area_a_ha": "100", "area_b_ha": "50", "diff_pct": "0.50"},
            )],
        }
        agent = DiagnosticoAgent(_ctx(chain_data={"auditor_imovel": auditor_payload}))
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response(_default_llm_payload())
            data = agent.run().data

        risco_auditor = data["riscos"][0]
        # JSON serializado, com keys sort_keys=True (determinístico)
        parsed = json.loads(risco_auditor["evidencia"])
        assert parsed["area_a_ha"] == "100"
        assert parsed["diff_pct"] == "0.50"


# ---------------------------------------------------------------------------
# Caso 3 — path fallback (rules-based) também consome auditor
# ---------------------------------------------------------------------------

class TestPathRulesBased:
    def test_rules_based_consome_auditor_quando_chain_data_presente(self):
        """Mesmo sem LLM (settings.ai_configured=False), se o auditor já rodou
        antes na chain, o diagnostico consome os findings — o cruzamento
        documental não depende do LLM."""
        auditor_payload = {
            "findings_raw": [_finding(grade="critico", type_="geo_incra_ausente")],
        }
        agent = DiagnosticoAgent(_ctx(chain_data={"auditor_imovel": auditor_payload}))
        with ExitStack() as stack:
            stack.enter_context(patch("app.agents.base.check_tenant_cost_limit"))
            stack.enter_context(patch("app.agents.base.check_tenant_monthly_budget"))
            stack.enter_context(patch.object(
                DiagnosticoAgent, "_load_process_data",
                return_value={"process": {"id": 42}, "property": {}, "documents": []},
            ))
            stack.enter_context(patch("app.agents.base.get_active_prompt", return_value=None))
            # AI desabilitada → path _rules_based_diagnosis. `ai_configured`
            # é uma @property em Settings; patchamos no nível da classe via
            # PropertyMock.
            stack.enter_context(patch(
                "app.core.config.Settings.ai_configured",
                new_callable=PropertyMock,
                return_value=False,
            ))
            data = agent.run().data

        # Mesmo sem LLM, divergencia e risco do auditor aparecem
        assert len(data["divergencias"]) == 1
        # 1 auditor + 1 fallback do rules-based
        assert len(data["riscos"]) == 2
        assert data["riscos"][0]["grau"] == "critico_impeditivo_potencial"
        assert data["nivel_risco_geral"] == "critico"


# ---------------------------------------------------------------------------
# Caso 4 — não há duplicação entre auditor e diagnostico
# ---------------------------------------------------------------------------

class TestSemDuplicacao:
    def test_diagnostico_nao_refaz_cruzamento_de_areas(self):
        """O DiagnosticoAgent NÃO calcula divergencia de área por conta própria:
        Divergencias vêm exclusivamente do auditor. Mesmo o LLM tentando
        descrever um cruzamento, ele não vira `Divergencia` automaticamente —
        só passa por `situacao_geral` / `hipoteses`."""
        # Auditor produz 1 área divergente
        auditor_payload = {"findings_raw": [_finding(grade="alto")]}
        # LLM "alucina" texto sobre divergência (não vira divergencia)
        llm = dict(_default_llm_payload())
        llm["situacao_geral"] = (
            "Áreas divergentes detectadas em CAR vs matrícula (LLM diz)"
        )
        agent = DiagnosticoAgent(_ctx(chain_data={"auditor_imovel": auditor_payload}))
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response(llm)
            data = agent.run().data

        # Exatamente 1 divergencia — a do auditor; LLM não duplica
        assert len(data["divergencias"]) == 1
        # auditor é fonte única do cruzamento
        assert data["divergencias"][0]["divergencia"].startswith("Áreas divergentes")


# ---------------------------------------------------------------------------
# Mapeamentos expostos
# ---------------------------------------------------------------------------

class TestMapeamentos:
    def test_grade_to_grau_4x4(self):
        assert _GRADE_TO_GRAU == {
            "informativo": "informativo",
            "atencao": "atencao",
            "alto": "alto",
            "critico": "critico_impeditivo_potencial",
        }

    def test_familia_to_categoria_cobre_11_familias(self):
        """PROMPT_5: agora `familia` (11) → `categoria` (7) — antes era
        `type` (4 do PROMPT_4) → `categoria` (4)."""
        assert _FAMILIA_TO_CATEGORIA == {
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
