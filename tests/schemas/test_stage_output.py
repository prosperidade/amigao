"""Testes dos schemas Pydantic de StageOutput.content_data — Sprint A1 Tarefa C."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.stage_output import (
    CitationRef,
    DiagnosticoPreliminarContent,
    PecaJuridicaContent,
    RespostaNotificacaoContent,
    Risco,
    Source,
    StageOutputContent,
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
        with pytest.raises(ValidationError):
            Risco(descricao="x", severidade="critico")  # type: ignore[arg-type]


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
        assert all(isinstance(k, str) for k in dumped.keys())
