"""Testes dos schemas Pydantic de StageOutput.content_data — Sprint A1 Tarefa C."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.stage_output import (
    CitationRef,
    DiagnosticoPreliminarContent,
    Divergencia,
    NotificacaoItem,
    PecaJuridicaContent,
    RespostaNotificacaoContent,
    Risco,
    Source,
    StageOutputContent,
    validate_diagnostic_content,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _src(ref: str = "chunk_1") -> Source:
    return Source(type="legislation", ref=ref)


def _citation(*, numero: str = "12.651", ano: int = 2012, kind: str = "lei", chunk_id: int | None = None) -> CitationRef:
    return CitationRef(
        kind=kind, numero=numero, ano=ano,
        raw=f"Lei nº {numero}/{ano}", chunk_id=chunk_id,
    )


# ---------------------------------------------------------------------------
# Source
# ---------------------------------------------------------------------------

class TestSource:
    def test_minimal_valid(self):
        s = Source(type="legislation", ref="chunk_1")
        assert s.type == "legislation"
        assert s.excerpt is None

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            Source(type="random", ref="x")  # type: ignore[arg-type]

    def test_blank_ref_rejected(self):
        with pytest.raises(ValidationError):
            Source(type="legislation", ref="")


# ---------------------------------------------------------------------------
# CitationRef
# ---------------------------------------------------------------------------

class TestCitationRef:
    def test_minimal_valid(self):
        c = _citation()
        assert c.numero == "12.651"
        assert c.ano == 2012
        assert c.chunk_id is None

    def test_carries_chunk_id_when_validated(self):
        c = _citation(chunk_id=42)
        assert c.chunk_id == 42

    def test_invalid_kind_rejected(self):
        with pytest.raises(ValidationError):
            CitationRef(kind="acordao_stf", numero="1", ano=2020, raw="x")  # type: ignore[arg-type]

    @pytest.mark.parametrize("ano", [-1, 0, 999, 3001])
    def test_year_range_enforced(self, ano):
        with pytest.raises(ValidationError):
            CitationRef(kind="lei", numero="1", ano=ano, raw="x")


# ---------------------------------------------------------------------------
# StageOutputContent (base)
# ---------------------------------------------------------------------------

class TestStageOutputContent:
    def test_valid_minimal(self):
        c = StageOutputContent(content="OK", sources=[_src()])
        assert c.confidence is None
        assert c.metadata == {}

    def test_empty_sources_rejected(self):
        with pytest.raises(ValidationError, match="sources"):
            StageOutputContent(content="OK", sources=[])

    def test_blank_content_rejected(self):
        with pytest.raises(ValidationError):
            StageOutputContent(content="", sources=[_src()])

    @pytest.mark.parametrize("conf,ok", [(0.0, True), (0.5, True), (1.0, True), (-0.1, False), (1.1, False)])
    def test_confidence_range(self, conf, ok):
        if ok:
            c = StageOutputContent(content="x", sources=[_src()], confidence=conf)
            assert c.confidence == conf
        else:
            with pytest.raises(ValidationError):
                StageOutputContent(content="x", sources=[_src()], confidence=conf)

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            StageOutputContent(content="x", sources=[_src()], unknown_field=1)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# DiagnosticoPreliminarContent
# ---------------------------------------------------------------------------

class TestDiagnosticoPreliminarContent:
    def test_valid(self):
        c = DiagnosticoPreliminarContent(
            content="Diagnóstico preliminar do processo",
            sources=[_src()],
            hipoteses=["Possível pendência CAR"],
            lacunas=["Falta CCIR"],
            riscos=[Risco(descricao="Multa por desmatamento", severidade="alto")],
            checklist_documental=["Matrícula", "CAR", "CCIR"],
        )
        assert c.riscos[0].severidade == "alto"
        assert "CCIR" in c.checklist_documental

    def test_inherits_sources_validation(self):
        with pytest.raises(ValidationError):
            DiagnosticoPreliminarContent(content="x", sources=[])

    def test_invalid_severidade_rejected(self):
        # Sprint A4: "critico" foi adicionado ao enum legado para mapeamento
        # limpo com `grau="critico_impeditivo_potencial"`. Mantemos a verificação
        # de rejeição com um valor genuinamente inválido.
        with pytest.raises(ValidationError):
            Risco(descricao="x", severidade="extremo")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# PecaJuridicaContent + RespostaNotificacaoContent
# ---------------------------------------------------------------------------

class TestPecaJuridicaContent:
    def test_valid_with_citations(self):
        c = PecaJuridicaContent(
            content="Em atenção à notificação...",
            sources=[_src("chunk_42")],
            template="oficio",
            legal_citations=[_citation(chunk_id=42)],
            addressee="SEMAD-GO",
            confidence=0.85,
        )
        assert c.template == "oficio"
        assert c.legal_citations[0].chunk_id == 42

    def test_invalid_template_rejected(self):
        with pytest.raises(ValidationError):
            PecaJuridicaContent(
                content="x", sources=[_src()],
                template="acordao",  # type: ignore[arg-type]
            )


class TestRespostaNotificacaoContent:
    def test_valid(self):
        c = RespostaNotificacaoContent(
            content="Resposta",
            sources=[_src()],
            prazo_dias=30,
            ato_regulatorio="Notificação SEMAD nº 123/2026",
            legal_citations=[_citation()],
        )
        assert c.template == "resposta_notificacao"
        assert c.prazo_dias == 30

    def test_template_locked(self):
        with pytest.raises(ValidationError):
            RespostaNotificacaoContent(
                content="x", sources=[_src()],
                template="oficio",  # type: ignore[arg-type]
                prazo_dias=10, ato_regulatorio="x",
            )

    def test_negative_prazo_rejected(self):
        with pytest.raises(ValidationError):
            RespostaNotificacaoContent(
                content="x", sources=[_src()],
                prazo_dias=-1, ato_regulatorio="x",
            )


# ---------------------------------------------------------------------------
# Round-trip JSON
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_peca_juridica_roundtrip(self):
        original = PecaJuridicaContent(
            content="Texto",
            sources=[_src("c1"), _src("c2")],
            template="proposta",
            legal_citations=[_citation(numero="9.605", ano=1998), _citation(numero="6.938", ano=1981)],
            addressee="IBAMA",
            confidence=0.9,
            metadata={"versao": 1},
        )
        dumped = original.model_dump()
        rebuilt = PecaJuridicaContent.model_validate(dumped)
        assert rebuilt == original

    def test_diagnostico_roundtrip(self):
        original = DiagnosticoPreliminarContent(
            content="Diag",
            sources=[_src()],
            hipoteses=["A", "B"],
            lacunas=["L1"],
            riscos=[Risco(descricao="r", severidade="medio", mitigacao_sugerida="m")],
            checklist_documental=["X"],
        )
        rebuilt = DiagnosticoPreliminarContent.model_validate(original.model_dump())
        assert rebuilt.riscos == original.riscos

    def test_resposta_notificacao_roundtrip_via_json(self):
        original = RespostaNotificacaoContent(
            content="x", sources=[_src()],
            prazo_dias=15, ato_regulatorio="Of. 1/2026",
            legal_citations=[_citation()],
        )
        # round-trip via JSON string (simula trânsito por API/JSONB)
        as_json = original.model_dump_json()
        rebuilt = RespostaNotificacaoContent.model_validate_json(as_json)
        assert rebuilt == original


# ---------------------------------------------------------------------------
# Compatibilidade legado (BaseAgent.run aceita dict + StageOutputContent)
# ---------------------------------------------------------------------------

class TestCoexistenceWithLegacyDict:
    """O BaseAgent atual ainda lida com ``dict[str, Any]``. Os schemas novos
    coexistem — não ha contrato de exclusividade nesta sprint.
    """

    def test_legacy_dict_remains_valid_input_for_persistence(self):
        legacy = {"raw_field": 123, "anything": True}
        # legacy não é validado pelos schemas novos — é só um dict
        assert isinstance(legacy, dict)

    def test_new_schema_dump_is_a_plain_dict_compatible_with_jsonb(self):
        c = StageOutputContent(content="x", sources=[_src()])
        dumped = c.model_dump()
        assert isinstance(dumped, dict)
        # garante que o resultado é serializável (sem objetos exóticos)
        assert all(isinstance(k, str) for k in dumped)


# ---------------------------------------------------------------------------
# Sprint A4 — taxonomia oficial: Risco estendido + dual-emit
# ---------------------------------------------------------------------------

class TestRiscoNovaTaxonomia:
    """8 campos novos + prioridade_triagem (9o, ortogonal a grau)."""

    def test_minimal_novo_payload(self):
        r = Risco(risco_identificado="Déficit de RL", grau="alto")
        assert r.risco_identificado == "Déficit de RL"
        assert r.grau == "alto"
        assert r.status_saneamento == "pendente"  # default

    def test_payload_completo_8mais1(self):
        r = Risco(
            categoria="ambiental",
            risco_identificado="Supressão sem ASV",
            grau="critico_impeditivo_potencial",
            impacto_possivel="Auto de infração + embargo",
            evidencia="Imagem MapBiomas 2023",
            proximo_passo="Suspender atividade até regularizar ASV",
            status_saneamento="em_validacao",
            observacao_consultor="Verificar com órgão",
            prioridade_triagem="urgentissima",
        )
        assert r.categoria == "ambiental"
        assert r.prioridade_triagem == "urgentissima"

    @pytest.mark.parametrize("valor", ["invalido", "outro", ""])
    def test_categoria_invalida_rejeitada(self, valor):
        with pytest.raises(ValidationError):
            Risco(risco_identificado="x", grau="alto", categoria=valor)  # type: ignore[arg-type]

    @pytest.mark.parametrize("valor", ["critico", "baixo", "informativo_alto"])
    def test_grau_invalido_rejeitado(self, valor):
        # "critico" sozinho NÃO é grau válido (é severidade legado);
        # o grau correspondente é "critico_impeditivo_potencial".
        with pytest.raises(ValidationError):
            Risco(risco_identificado="x", grau=valor)  # type: ignore[arg-type]

    def test_status_saneamento_invalido_rejeitado(self):
        with pytest.raises(ValidationError):
            Risco(risco_identificado="x", grau="alto", status_saneamento="fechado")  # type: ignore[arg-type]

    def test_prioridade_triagem_invalida_rejeitada(self):
        with pytest.raises(ValidationError):
            Risco(risco_identificado="x", grau="alto", prioridade_triagem="urgentissimo")  # type: ignore[arg-type]

    def test_sem_risco_identificado_nem_descricao_rejeitado(self):
        with pytest.raises(ValidationError, match="risco_identificado"):
            Risco(grau="alto")  # type: ignore[call-arg]

    def test_sem_grau_nem_severidade_rejeitado(self):
        with pytest.raises(ValidationError, match="grau"):
            Risco(risco_identificado="x")  # type: ignore[call-arg]


class TestRiscoDualEmit:
    """Aceita payload antigo (3 campos) e reconcilia para o novo shape."""

    def test_payload_antigo_continua_valido(self):
        r = Risco(descricao="Multa por desmatamento", severidade="alto")
        assert r.descricao == "Multa por desmatamento"
        assert r.severidade == "alto"

    def test_payload_antigo_preenche_aliases_novos(self):
        r = Risco(descricao="Erosão em APP", severidade="medio", mitigacao_sugerida="Cercar e replantar")
        # ida: antigo → novo
        assert r.risco_identificado == "Erosão em APP"
        assert r.grau == "atencao"  # medio → atencao
        assert r.proximo_passo == "Cercar e replantar"

    def test_payload_novo_preenche_aliases_antigos(self):
        r = Risco(
            risco_identificado="GEO INCRA ausente",
            grau="critico_impeditivo_potencial",
            proximo_passo="Obter GEO antes do CAR",
        )
        # volta: novo → antigo
        assert r.descricao == "GEO INCRA ausente"
        assert r.severidade == "critico"  # critico_impeditivo_potencial → critico
        assert r.mitigacao_sugerida == "Obter GEO antes do CAR"

    @pytest.mark.parametrize("sev,grau_esperado", [
        ("baixo", "informativo"),
        ("medio", "atencao"),
        ("alto", "alto"),
        ("critico", "critico_impeditivo_potencial"),
    ])
    def test_mapeamento_severidade_para_grau(self, sev, grau_esperado):
        r = Risco(descricao="x", severidade=sev)
        assert r.grau == grau_esperado

    @pytest.mark.parametrize("grau,sev_esperada", [
        ("informativo", "baixo"),
        ("atencao", "medio"),
        ("alto", "alto"),
        ("critico_impeditivo_potencial", "critico"),
    ])
    def test_mapeamento_grau_para_severidade(self, grau, sev_esperada):
        r = Risco(risco_identificado="x", grau=grau)
        assert r.severidade == sev_esperada

    def test_payload_misto_antigo_e_novo(self):
        # Quando os dois pares estão presentes, o validator não sobrescreve
        # — payload explícito vence.
        r = Risco(
            descricao="legado",
            severidade="alto",
            risco_identificado="novo explícito",
            grau="critico_impeditivo_potencial",
            proximo_passo="ação nova",
        )
        assert r.risco_identificado == "novo explícito"
        assert r.descricao == "legado"
        assert r.grau == "critico_impeditivo_potencial"
        assert r.severidade == "alto"

    def test_roundtrip_antigo_via_model_dump(self):
        original = Risco(descricao="r", severidade="medio", mitigacao_sugerida="m")
        rebuilt = Risco.model_validate(original.model_dump())
        assert rebuilt == original

    def test_roundtrip_novo_via_model_dump(self):
        original = Risco(
            categoria="fundiario",
            risco_identificado="Matrícula em nome de falecido",
            grau="alto",
            impacto_possivel="Trava protocolo no cartório",
            prioridade_triagem="alta",
        )
        rebuilt = Risco.model_validate(original.model_dump())
        assert rebuilt == original


# ---------------------------------------------------------------------------
# Sprint A4 — Divergencia (matriz de cruzamento documental)
# ---------------------------------------------------------------------------

class TestDivergencia:
    def test_valido(self):
        d = Divergencia(
            tema="área",
            divergencia="Matrícula declara 120ha, CAR declara 95ha",
            impacto="Passivo de compensação calculado em ha — precisa padronizar antes do protocolo",
        )
        assert d.tema == "área"

    @pytest.mark.parametrize("campo_em_branco", ["tema", "divergencia", "impacto"])
    def test_campo_em_branco_rejeitado(self, campo_em_branco):
        payload = {"tema": "x", "divergencia": "x", "impacto": "x"}
        payload[campo_em_branco] = ""
        with pytest.raises(ValidationError):
            Divergencia(**payload)


# ---------------------------------------------------------------------------
# Sprint A4 — NotificacaoItem (estágio saneamento)
# ---------------------------------------------------------------------------

class TestNotificacaoItem:
    def test_minimal_valido(self):
        n = NotificacaoItem(
            exigencia="Apresentar PRAD em 30 dias",
            fundamento="Art. 26 da Lei 18.104/2024",
            acao="Contratar engenheiro florestal",
            status="pendente",
        )
        assert n.responsavel is None

    def test_status_em_branco_rejeitado(self):
        with pytest.raises(ValidationError):
            NotificacaoItem(exigencia="x", fundamento="x", acao="x", status="")


# ---------------------------------------------------------------------------
# Sprint A4 — DiagnosticoPreliminarContent estendido
# ---------------------------------------------------------------------------

class TestDiagnosticoPreliminarContentEstendido:
    def test_campos_opcionais_default(self):
        # Construção com os 4 campos antigos só — defaults vazios para os novos.
        c = DiagnosticoPreliminarContent(
            content="Diag preliminar",
            sources=[_src()],
            hipoteses=["H1"],
        )
        assert c.divergencias == []
        assert c.nivel_risco_geral is None
        assert c.nivel_confianca_diagnostico is None
        assert c.recomendacoes_externas == []
        assert c.etapa_funil_sugerida is None
        assert c.matriz_notificacao is None

    def test_com_divergencias(self):
        c = DiagnosticoPreliminarContent(
            content="Diag",
            sources=[_src()],
            divergencias=[
                Divergencia(tema="área", divergencia="X", impacto="Y"),
                Divergencia(tema="titularidade", divergencia="A", impacto="B"),
            ],
            nivel_risco_geral="alto",
            nivel_confianca_diagnostico="media",
            recomendacoes_externas=["Advogado fundiário", "Engenheiro agrimensor"],
            etapa_funil_sugerida="diagnostico_consolidado",
        )
        assert len(c.divergencias) == 2
        assert c.nivel_risco_geral == "alto"

    def test_com_matriz_notificacao_saneamento(self):
        c = DiagnosticoPreliminarContent(
            content="Diag de saneamento",
            sources=[_src()],
            matriz_notificacao=[
                NotificacaoItem(
                    exigencia="Item 1",
                    fundamento="Art. X",
                    acao="Y",
                    status="pendente",
                ),
            ],
        )
        assert c.matriz_notificacao is not None
        assert len(c.matriz_notificacao) == 1

    def test_nivel_risco_geral_invalido_rejeitado(self):
        with pytest.raises(ValidationError):
            DiagnosticoPreliminarContent(
                content="x", sources=[_src()],
                nivel_risco_geral="impeditivo",  # type: ignore[arg-type]
            )

    def test_nivel_confianca_invalido_rejeitado(self):
        with pytest.raises(ValidationError):
            DiagnosticoPreliminarContent(
                content="x", sources=[_src()],
                nivel_confianca_diagnostico="certeza",  # type: ignore[arg-type]
            )

    def test_riscos_novos_aceitos(self):
        # Garante que a lista riscos: list[Risco] aceita o novo shape.
        c = DiagnosticoPreliminarContent(
            content="Diag",
            sources=[_src()],
            riscos=[
                Risco(
                    categoria="geoespacial",
                    risco_identificado="CAR sem GEO INCRA",
                    grau="critico_impeditivo_potencial",
                    prioridade_triagem="alta",
                ),
                Risco(descricao="legado", severidade="medio"),  # mistura é OK
            ],
        )
        assert c.riscos[0].grau == "critico_impeditivo_potencial"
        assert c.riscos[1].risco_identificado == "legado"  # dual-emit funcionou

    def test_roundtrip_completo_via_json(self):
        # Simula trânsito por JSONB / API.
        original = DiagnosticoPreliminarContent(
            content="Diag",
            sources=[_src()],
            riscos=[
                Risco(
                    risco_identificado="Sobreposição com APP",
                    grau="alto",
                    prioridade_triagem="media",
                ),
            ],
            divergencias=[Divergencia(tema="x", divergencia="y", impacto="z")],
            nivel_risco_geral="medio",
            matriz_notificacao=[
                NotificacaoItem(exigencia="x", fundamento="x", acao="x", status="pendente"),
            ],
        )
        rebuilt = DiagnosticoPreliminarContent.model_validate_json(original.model_dump_json())
        assert rebuilt == original


# ---------------------------------------------------------------------------
# Sprint A4 — validate_diagnostic_content (Pydantic ↔ JSONB)
# ---------------------------------------------------------------------------

class TestValidateDiagnosticContent:
    def test_dict_valido_retorna_instancia(self):
        payload = {
            "content": "Diag",
            "sources": [{"type": "legislation", "ref": "chunk_1"}],
            "hipoteses": ["H"],
        }
        result = validate_diagnostic_content(payload)
        assert isinstance(result, DiagnosticoPreliminarContent)
        assert result.hipoteses == ["H"]

    def test_dict_invalido_levanta_validation_error(self):
        with pytest.raises(ValidationError):
            validate_diagnostic_content({"content": "", "sources": []})  # blank content + empty sources

    def test_aceita_payload_antigo_com_risco_legado(self):
        # JSONB pode estar com forma antiga; o validator reconcilia.
        payload = {
            "content": "Diag legado",
            "sources": [{"type": "legislation", "ref": "c1"}],
            "riscos": [{"descricao": "Multa", "severidade": "alto"}],
        }
        result = validate_diagnostic_content(payload)
        assert result.riscos[0].risco_identificado == "Multa"
        assert result.riscos[0].grau == "alto"

    def test_rejeita_payload_com_campo_desconhecido_no_topo(self):
        payload = {
            "content": "x",
            "sources": [{"type": "legislation", "ref": "c1"}],
            "campo_inventado": 42,
        }
        with pytest.raises(ValidationError):
            validate_diagnostic_content(payload)


# ---------------------------------------------------------------------------
# Sprint A4 — confirma que EnquadramentoRegulatorioContent.riscos segue OK
# ---------------------------------------------------------------------------

class TestRetrocompatEnquadramentoRiscos:
    """O LegislacaoAgent emite EnquadramentoRegulatorioContent com `riscos: list[Risco]`
    no formato antigo (descricao/severidade/mitigacao_sugerida). Confirma que o
    novo Risco aceita esse payload sem quebrar.
    """

    def test_enquadramento_com_riscos_legados(self):
        from app.schemas.stage_output import EnquadramentoRegulatorioContent

        c = EnquadramentoRegulatorioContent(
            content="Caminho regulatório",
            sources=[_src()],
            caminho_regulatorio="Licenciamento ordinário",
            riscos=[
                Risco(descricao="r1", severidade="medio"),
                Risco(descricao="r2", severidade="alto", mitigacao_sugerida="m"),
            ],
        )
        assert len(c.riscos) == 2
        assert c.riscos[0].grau == "atencao"  # medio → atencao via dual-emit
        assert c.riscos[1].grau == "alto"
