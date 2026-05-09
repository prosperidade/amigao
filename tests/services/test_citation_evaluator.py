"""Testes do citation_evaluator — Sprint A1 Tarefa B."""

from __future__ import annotations

import pytest

from app.schemas.stage_output import CitationRef
from app.services.citation_evaluator import (
    CitationValidationResult,
    extract_citations,
    validate_citations,
)

# ---------------------------------------------------------------------------
# extract_citations — variantes de formato
# ---------------------------------------------------------------------------

class TestExtractCitations:
    def test_returns_empty_for_text_without_citations(self) -> None:
        assert extract_citations("Texto livre sem nenhuma norma jurídica.") == []
        assert extract_citations("") == []

    @pytest.mark.parametrize(
        "text,expected_kind,expected_numero,expected_ano",
        [
            ("Lei 12.651/2012",                                         "lei", "12.651", 2012),
            ("Lei nº 12.651/2012",                                      "lei", "12.651", 2012),
            ("Lei nº 12.651, de 25 de maio de 2012",                    "lei", "12.651", 2012),
            ("Lei n° 9.605/1998",                                       "lei", "9.605", 1998),
            ("Lei 12651/2012",                                          "lei", "12651", 2012),
            ("Decreto 7.830/2012",                                      "decreto", "7.830", 2012),
            ("Decreto-Lei 4.657/1942",                                  "decreto_lei", "4.657", 1942),
            ("Lei Complementar 140/2011",                               "lei_complementar", "140", 2011),
            ("Resolução CONAMA nº 237/1997",                            "resolucao_conama", "237", 1997),
            ("Resolução CONAMA 369/2006",                               "resolucao_conama", "369", 2006),
            ("Instrução Normativa MMA 2/2014",                          "instrucao_normativa", "2", 2014),
            ("IN MMA 2/2014",                                           "instrucao_normativa", "2", 2014),
            ("Portaria SEMAD 12/2023",                                  "portaria", "12", 2023),
            ("MP 2.166-67/2001",                                        "medida_provisoria", "2.166-67", 2001),
        ],
    )
    def test_recognizes_format(self, text, expected_kind, expected_numero, expected_ano) -> None:
        cits = extract_citations(text)
        assert len(cits) == 1, f"esperava 1 citação em '{text}', achei {len(cits)}: {cits}"
        c = cits[0]
        assert c.kind == expected_kind
        assert c.numero == expected_numero
        assert c.ano == expected_ano
        assert c.raw  # raw preservado

    def test_lei_complementar_not_swallowed_by_lei_pattern(self) -> None:
        cits = extract_citations("conforme a Lei Complementar 140/2011 e a Lei 12.651/2012")
        kinds = sorted([c.kind for c in cits])
        assert kinds == ["lei", "lei_complementar"]
        assert {c.numero for c in cits} == {"140", "12.651"}

    def test_decreto_lei_not_swallowed_by_decreto_pattern(self) -> None:
        cits = extract_citations("o Decreto-Lei 4.657/1942 e o Decreto 7.830/2012")
        kinds = sorted([c.kind for c in cits])
        assert kinds == ["decreto", "decreto_lei"]

    def test_resolucao_non_conama_falls_back_to_outro(self) -> None:
        cits = extract_citations("Resolução CONABIO 12/2020")
        assert len(cits) == 1
        assert cits[0].kind == "outro"
        assert cits[0].numero == "12"
        assert cits[0].ano == 2020

    def test_extracts_artigo_when_present(self) -> None:
        cits = extract_citations("conforme art. 7º da Lei 12.651/2012")
        assert len(cits) == 1
        assert cits[0].artigo is not None
        assert "7" in cits[0].artigo

    def test_dedupes_repeated_citations(self) -> None:
        text = "Lei 12.651/2012 trata de... A Lei nº 12.651/2012 também aborda..."
        cits = extract_citations(text)
        assert len(cits) == 1

    def test_preserves_raw_form(self) -> None:
        cits = extract_citations("nos termos da Lei nº 12.651, de 25 de maio de 2012")
        assert "Lei nº 12.651" in cits[0].raw

    def test_short_year_inferred(self) -> None:
        cits = extract_citations("Lei 12.651/12")
        assert cits[0].ano == 2012
        cits = extract_citations("Lei 9.605/98")
        assert cits[0].ano == 1998


# ---------------------------------------------------------------------------
# validate_citations
# ---------------------------------------------------------------------------

def _ref(kind: str, numero: str, ano: int, raw: str | None = None) -> CitationRef:
    return CitationRef(kind=kind, numero=numero, ano=ano, raw=raw or f"{kind} {numero}/{ano}")


class _FakeSearchResult:
    """Duck-type mínimo de SearchResult do knowledge_catalog."""

    def __init__(
        self,
        identifier: str,
        result_id: int,
        jurisdiction: str | None = None,
    ) -> None:
        self.identifier = identifier
        self.id = result_id
        self.jurisdiction = jurisdiction


class TestValidateCitations:
    def test_all_valid_returns_full_coverage(self) -> None:
        cits = [
            _ref("lei", "12.651", 2012),
            _ref("decreto", "7.830", 2012),
            _ref("lei_complementar", "140", 2011),
        ]
        context = ["Lei 12.651/2012", "Decreto 7.830/2012", "Lei Complementar 140/2011"]
        result = validate_citations(cits, context)
        assert isinstance(result, CitationValidationResult)
        assert result.valid is True
        assert result.total == 3
        assert result.invalid == []
        assert result.coverage_ratio == 1.0

    def test_missing_citation_marks_invalid(self) -> None:
        cits = [
            _ref("lei", "12.651", 2012),
            _ref("lei", "9.605", 1998),       # NÃO está no contexto
            _ref("decreto", "7.830", 2012),
        ]
        context = ["Lei 12.651/2012", "Decreto 7.830/2012"]
        result = validate_citations(cits, context)
        assert result.valid is False
        assert result.total == 3
        assert len(result.invalid) == 1
        assert result.invalid[0].numero == "9.605"
        assert result.coverage_ratio == pytest.approx(2 / 3)

    def test_empty_citations_returns_vacuously_valid(self) -> None:
        result = validate_citations([], ["Lei 12.651/2012"])
        assert result.valid is True
        assert result.total == 0
        assert result.invalid == []
        assert result.coverage_ratio == 1.0

    def test_search_result_match_populates_chunk_id_and_jurisdicao(self) -> None:
        cits = [_ref("lei", "12.651", 2012)]
        context = [_FakeSearchResult("Lei 12.651/2012", result_id=42, jurisdiction="federal")]
        result = validate_citations(cits, context)
        assert result.valid is True
        # mutação no lugar da CitationRef original
        assert cits[0].chunk_id == 42
        assert cits[0].jurisdicao == "federal"

    def test_does_not_overwrite_existing_chunk_id(self) -> None:
        cits = [_ref("lei", "12.651", 2012)]
        cits[0] = cits[0].model_copy(update={"chunk_id": 99, "jurisdicao": "estadual"})
        context = [_FakeSearchResult("Lei 12.651/2012", result_id=42, jurisdiction="federal")]
        validate_citations(cits, context)
        assert cits[0].chunk_id == 99           # preservado
        assert cits[0].jurisdicao == "estadual"  # preservado

    def test_normalizes_number_format_for_match(self) -> None:
        # Citação tem "12.651"; contexto tem "12651" (sem ponto). Devem casar.
        cits = [_ref("lei", "12.651", 2012)]
        context = ["Lei 12651/2012"]
        result = validate_citations(cits, context)
        assert result.valid is True

    def test_unparseable_context_strings_silently_ignored(self) -> None:
        cits = [_ref("lei", "12.651", 2012)]
        # texto solto sem padrão reconhecível — não casa, não levanta
        context = ["alguma coisa", "Lei 12.651/2012"]
        result = validate_citations(cits, context)
        assert result.valid is True

    def test_mixed_context_search_result_and_strings(self) -> None:
        cits = [
            _ref("lei", "12.651", 2012),
            _ref("lei", "9.605", 1998),
        ]
        context = [
            _FakeSearchResult("Lei 12.651/2012", result_id=42, jurisdiction="federal"),
            "Lei 9.605/1998",
        ]
        result = validate_citations(cits, context)
        assert result.valid is True
        # SearchResult enriquece chunk_id; string apenas confirma match
        assert cits[0].chunk_id == 42
        assert cits[1].chunk_id is None
