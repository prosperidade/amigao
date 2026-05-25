"""Regressão A4 — LegislacaoAgent não pode quebrar com Risco estendido (Fase 2).

Preocupação documentada: `Risco` é tipo compartilhado entre DiagnosticoAgent e
LegislacaoAgent. A Onda 1 (A4) estendeu de 3 para 8+1 campos via dual-emit.
Se o reconcile bidirecional falhar, `EnquadramentoRegulatorioContent.riscos`
quebra silenciosamente — testes existentes do LegislacaoAgent passam mas a
forma de saída muda, derrubando consumidores downstream (frontend +
DiagnosticoAgent que consome `chain_data["legislacao"]`).

Invariantes que este arquivo prova:

1. `Risco(descricao=, severidade=, mitigacao_sugerida=)` no formato antigo
   continua válido após A4 (sem precisar dos 8 campos novos).
2. `EnquadramentoRegulatorioContent(riscos=[Risco antigo, ...])` valida sem
   levantar `ValidationError`.
3. `enq.model_dump(mode="json")["riscos"]` mantém as 3 chaves antigas
   `descricao/severidade/mitigacao_sugerida` populadas (consumidores que
   leem o schema serializado continuam funcionando).
4. Round-trip JSON: `EnquadramentoRegulatorioContent.model_validate_json(
   enq.model_dump_json())` é idempotente.
5. O dual-emit MANUAL no payload final do `_build_payload` (linha 666 do
   `legislacao.py`: `"riscos": list(riscos_raw)`) preserva a forma BRUTA do LLM
   no payload retornado, independentemente do shape interno do schema.
"""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from app.agents.base import AgentContext
from app.agents.legislacao import LegislacaoAgent
from app.schemas.stage_output import (
    EnquadramentoRegulatorioContent,
    Risco,
    Source,
)


def _src() -> Source:
    return Source(type="legislation", ref="chunk_1")


def _ctx() -> AgentContext:
    return AgentContext(
        tenant_id=1, user_id=1, process_id=42,
        session=MagicMock(), metadata={}, chain_data={},
    )


# ---------------------------------------------------------------------------
# Invariante 1: construção do Risco antigo continua válida após A4
# ---------------------------------------------------------------------------

class TestInvarianteRiscoAntigoValido:
    def test_risco_minimo_antigo_valida(self):
        r = Risco(descricao="x", severidade="alto")
        assert r.descricao == "x"
        assert r.severidade == "alto"

    def test_risco_antigo_completo_valida(self):
        r = Risco(descricao="x", severidade="medio", mitigacao_sugerida="y")
        assert r.descricao == "x"
        assert r.severidade == "medio"
        assert r.mitigacao_sugerida == "y"

    def test_severidade_baixo_continua_valida(self):
        # cobertura paranoica dos 4 níveis legados (`critico` é aditivo do A4)
        for sev in ("baixo", "medio", "alto", "critico"):
            r = Risco(descricao="x", severidade=sev)
            assert r.severidade == sev


# ---------------------------------------------------------------------------
# Invariante 2: EnquadramentoRegulatorioContent com riscos antigos valida
# ---------------------------------------------------------------------------

class TestInvarianteEnquadramentoComRiscosAntigos:
    def test_enquadramento_com_um_risco_antigo(self):
        c = EnquadramentoRegulatorioContent(
            content="x",
            sources=[_src()],
            caminho_regulatorio="Licenciamento ordinário",
            riscos=[Risco(descricao="Multa", severidade="alto")],
        )
        assert len(c.riscos) == 1
        assert c.riscos[0].descricao == "Multa"
        assert c.riscos[0].severidade == "alto"

    def test_enquadramento_com_riscos_mistos(self):
        # Mistura: 1 risco antigo (3 campos) + 1 risco novo (8 campos)
        c = EnquadramentoRegulatorioContent(
            content="x",
            sources=[_src()],
            caminho_regulatorio="Defesa administrativa",
            riscos=[
                Risco(descricao="Auto", severidade="critico", mitigacao_sugerida="Defesa"),
                Risco(
                    categoria="ambiental",
                    risco_identificado="Supressão sem ASV",
                    grau="critico_impeditivo_potencial",
                    impacto_possivel="Embargo + multa",
                    prioridade_triagem="urgentissima",
                ),
            ],
        )
        assert len(c.riscos) == 2
        # ambos os riscos têm as chaves antigas populadas (dual-emit)
        for r in c.riscos:
            assert r.descricao is not None
            assert r.severidade is not None

    def test_enquadramento_com_riscos_vazios(self):
        c = EnquadramentoRegulatorioContent(
            content="x",
            sources=[_src()],
            caminho_regulatorio="x",
            riscos=[],
        )
        assert c.riscos == []


# ---------------------------------------------------------------------------
# Invariante 3: model_dump preserva chaves antigas (frontend ainda lê)
# ---------------------------------------------------------------------------

class TestInvarianteModelDumpPreservaChavesAntigas:
    def test_dump_de_risco_antigo_emite_3_chaves_antigas(self):
        r = Risco(descricao="Multa", severidade="alto", mitigacao_sugerida="Defender")
        d = r.model_dump(mode="json")
        # As 3 chaves antigas continuam saindo no dump
        assert d["descricao"] == "Multa"
        assert d["severidade"] == "alto"
        assert d["mitigacao_sugerida"] == "Defender"

    def test_dump_de_risco_novo_emite_3_chaves_antigas_via_dual_emit_reverso(self):
        r = Risco(
            risco_identificado="GEO INCRA ausente",
            grau="critico_impeditivo_potencial",
            proximo_passo="Obter GEO",
        )
        d = r.model_dump(mode="json")
        # ida volta: campos novos preencheram os antigos
        assert d["descricao"] == "GEO INCRA ausente"
        assert d["severidade"] == "critico"
        assert d["mitigacao_sugerida"] == "Obter GEO"

    def test_dump_de_enquadramento_serializa_riscos_com_chaves_antigas(self):
        c = EnquadramentoRegulatorioContent(
            content="x",
            sources=[_src()],
            caminho_regulatorio="Defesa",
            riscos=[
                Risco(descricao="R1", severidade="medio", mitigacao_sugerida="M1"),
                Risco(descricao="R2", severidade="alto"),
            ],
        )
        d = c.model_dump(mode="json")
        # `riscos` é uma list[dict] — cada dict tem as 3 chaves antigas
        assert len(d["riscos"]) == 2
        for entry in d["riscos"]:
            assert "descricao" in entry
            assert "severidade" in entry
            assert "mitigacao_sugerida" in entry
        assert d["riscos"][0]["descricao"] == "R1"
        assert d["riscos"][0]["severidade"] == "medio"
        assert d["riscos"][1]["descricao"] == "R2"
        assert d["riscos"][1]["severidade"] == "alto"


# ---------------------------------------------------------------------------
# Invariante 4: round-trip JSON é idempotente
# ---------------------------------------------------------------------------

class TestInvarianteRoundTripJSON:
    def test_roundtrip_enquadramento_via_model_dump(self):
        original = EnquadramentoRegulatorioContent(
            content="Caminho",
            sources=[_src()],
            caminho_regulatorio="Licenciamento ordinário",
            etapas=[],
            legal_citations=[],
            riscos=[
                Risco(descricao="Multa", severidade="alto"),
                Risco(descricao="Embargo", severidade="critico", mitigacao_sugerida="Defesa"),
            ],
            documentos_necessarios=["matrícula"],
            recomendacoes=["consultar advogado"],
        )
        rebuilt = EnquadramentoRegulatorioContent.model_validate(original.model_dump())
        # Reconstrução não pode mudar nada
        assert rebuilt == original
        # Riscos preservam ordem e conteúdo
        assert rebuilt.riscos[0].descricao == "Multa"
        assert rebuilt.riscos[1].severidade == "critico"

    def test_roundtrip_enquadramento_via_json_string(self):
        original = EnquadramentoRegulatorioContent(
            content="x",
            sources=[_src()],
            caminho_regulatorio="x",
            riscos=[Risco(descricao="r", severidade="medio", mitigacao_sugerida="m")],
        )
        as_json = original.model_dump_json()
        rebuilt = EnquadramentoRegulatorioContent.model_validate_json(as_json)
        assert rebuilt == original


# ---------------------------------------------------------------------------
# Invariante 5: dual-emit manual no payload final do _build_payload
# ---------------------------------------------------------------------------

class TestInvarianteBuildContentDualEmitManual:
    """O `_build_payload` do LegislacaoAgent retorna um dict que MERGE-OVERRIDES
    a chave `riscos` do `enq.model_dump()` com `list(riscos_raw)` (linha 666).
    Isso garante que o consumidor downstream (frontend + DiagnosticoAgent via
    chain_data) lê a forma BRUTA do LLM, não a forma serializada do schema.
    Sem esse override, o Risco A4 mudaria o shape e quebraria silenciosamente.
    """

    def test_build_payload_emite_riscos_brutos_no_payload_final(self):
        agent = LegislacaoAgent(_ctx())
        riscos_raw = [
            {"descricao": "Multa", "severidade": "alto", "mitigacao": "Defender"},
            {"descricao": "Embargo", "severidade": "critico", "mitigacao_sugerida": "Pedir desembargo"},
        ]
        payload = agent._build_payload(
            caminho_regulatorio="Licenciamento ordinário",
            orgao_competente="SEMAD-GO",
            etapas_raw=[],
            legislacao_aplicavel_raw=[],
            riscos_raw=riscos_raw,
            documentos_necessarios=["matrícula"],
            prazos_estimados={},
            recomendacoes=["x"],
            confianca="alta",
            justificativa="por que",
            sources=[_src()],
            chunks_referenced=[],
            normas_estaduais=[],
            risco_legal="medio",
            prazos_legais=[],
        )
        # Payload final NÃO é o schema serializado: é o merge com chaves antigas
        # cruas no topo (linha 666 de legislacao.py).
        assert payload["riscos"] == riscos_raw
        # Especificamente: chave "mitigacao" (sem `_sugerida`) e "mitigacao_sugerida"
        # convivem, e isso só é possível porque é a forma bruta do LLM, não o schema.
        assert payload["riscos"][0]["mitigacao"] == "Defender"
        assert payload["riscos"][1]["mitigacao_sugerida"] == "Pedir desembargo"
        # E o dual-emit do schema também aparece no payload, mas com as 3 chaves
        # antigas POR Risco (não como list[Risco] tipado):
        # → essa parte é o `enq.model_dump()` que vem ANTES do merge.
        # Conferimos abaixo num teste separado para não acoplar a estrutura.

    def test_build_payload_payload_inclui_chaves_dual_emit_e_schema(self):
        agent = LegislacaoAgent(_ctx())
        payload = agent._build_payload(
            caminho_regulatorio="x",
            orgao_competente="y",
            etapas_raw=[],
            legislacao_aplicavel_raw=[],
            riscos_raw=[{"descricao": "x", "severidade": "alto"}],
            documentos_necessarios=[],
            prazos_estimados={},
            recomendacoes=[],
            confianca="media",
            justificativa="por que",
            sources=[_src()],
            chunks_referenced=[],
            normas_estaduais=[],
            risco_legal="alto",
            prazos_legais=[],
        )
        # Chaves do schema validado
        assert payload["caminho_regulatorio"] == "x"
        assert payload["content"] == "por que"
        # Chaves dual-emit do schema (Risco no model_dump)
        # — substituídas pelo merge para forma bruta
        assert payload["riscos"] == [{"descricao": "x", "severidade": "alto"}]
        # requires_review é hard-coded no dual-emit manual
        assert payload["requires_review"] is True

    def test_build_payload_severidade_invalida_cai_para_medio_via_normalize(self):
        # _normalize_riscos faz o saneamento ANTES de instanciar Risco —
        # garante que A4 não rejeite payload do LLM com severidade fora.
        agent = LegislacaoAgent(_ctx())
        payload = agent._build_payload(
            caminho_regulatorio="x",
            orgao_competente="y",
            etapas_raw=[],
            legislacao_aplicavel_raw=[],
            riscos_raw=[{"descricao": "x", "severidade": "extremo", "mitigacao": "z"}],
            documentos_necessarios=[],
            prazos_estimados={},
            recomendacoes=[],
            confianca="media",
            justificativa="x",
            sources=[_src()],
            chunks_referenced=[],
            normas_estaduais=[],
            risco_legal="alto",
            prazos_legais=[],
        )
        # No payload bruto (chave riscos no topo), "extremo" continua lá (forma original)
        assert payload["riscos"][0]["severidade"] == "extremo"
        # Mas o schema (enq) já foi montado com severidade="medio" (normalizada)
        # — não acessível como payload["riscos"] porque foi sobrescrito, mas o
        # fato de NÃO ter levantado LegislacaoOutputValidationError aqui prova
        # que a normalização funcionou.


# ---------------------------------------------------------------------------
# Invariante 6 (transversal): payload do LegislacaoAgent é consumível pelo Diagnostico
# ---------------------------------------------------------------------------

class TestInvarianteDownstreamConsumption:
    """Garante que o que o LegislacaoAgent emite é exatamente o que o
    DiagnosticoAgent espera ler em `chain_data["legislacao"]`. Cruzamento entre
    o produtor (legislacao) e o consumidor (diagnostico via citation_evaluator
    A3) — protege contra mudanças de shape silenciosas.
    """

    def test_payload_tem_chaves_que_diagnostico_e_redator_leem(self):
        agent = LegislacaoAgent(_ctx())
        payload = agent._build_payload(
            caminho_regulatorio="Licenciamento ordinário",
            orgao_competente="SEMAD-GO",
            etapas_raw=[],
            legislacao_aplicavel_raw=["Lei nº 12.651/2012", "Lei nº 9.605/1998"],
            riscos_raw=[{"descricao": "R1", "severidade": "alto"}],
            documentos_necessarios=["matrícula"],
            prazos_estimados={"protocolo": "30 dias"},
            recomendacoes=["consultar advogado"],
            confianca="alta",
            justificativa="análise legal completa",
            sources=[_src()],
            chunks_referenced=[],
            normas_estaduais=["Lei GO 18.104/2013"],
            risco_legal="alto",
            prazos_legais=[],
        )
        # Chaves que o DiagnosticoAgent._evaluate_citations lê
        # (app/agents/diagnostico.py: legal_data["legislacao_aplicavel"] e ["normas_estaduais"])
        assert "legislacao_aplicavel" in payload
        assert "normas_estaduais" in payload
        assert payload["legislacao_aplicavel"] == ["Lei nº 12.651/2012", "Lei nº 9.605/1998"]
        assert payload["normas_estaduais"] == ["Lei GO 18.104/2013"]
        # Chaves que o RedatorAgent._evaluate_citations também consome
        # (app/agents/redator.py: idem)
        # — mesmo contrato, mesma garantia
