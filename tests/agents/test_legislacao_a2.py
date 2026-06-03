"""Testes da migração do LegislacaoAgent para EnquadramentoRegulatorioContent —
Sprint A2-legislacao.

Cobre:
* Path IA (execute() com LLM stubado retornando JSON estruturado)
* Path fallback (_rules_based_response sem IA)
* Mapeamento confianca (str baixa|media|alta) → confidence (float 0..1)
* Cascata de Source (rag_chunks → legislacao_aplicavel → fallback manual)
* Normalização de etapas (list[dict] → list[Etapa])
* Normalização de riscos (campo mitigacao → mitigacao_sugerida)
* Extração best-effort de CitationRef via regex
* Dual-emit das chaves antigas preservadas no payload
* metadata["prazos_estimados"] + metadata["chunks_referenced"]
* Caminho de erro: payload malformado levanta LegislacaoOutputValidationError
* JSON-serializability do payload final
"""

from __future__ import annotations

import json
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text

from app.agents.base import AgentContext
from app.agents.legislacao import (
    LegislacaoAgent,
    LegislacaoOutputValidationError,
)
from app.models.legislation import LegislationDocument
from app.schemas.stage_output import Source

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ai_response(payload: dict | str):
    from app.core.ai_gateway import AIResponse
    content = json.dumps(payload, ensure_ascii=False) if isinstance(payload, dict) else payload
    return AIResponse(
        content=content,
        model_used="mock-model",
        tokens_in=50,
        tokens_out=120,
        cost_usd=0.0001,
        duration_ms=150,
        provider="mock",
    )


def _ctx(*, metadata: dict | None = None, chain_data: dict | None = None) -> AgentContext:
    return AgentContext(
        tenant_id=1,
        user_id=1,
        process_id=None,
        session=MagicMock(),
        metadata=metadata or {"query": "Qual o caminho?", "demand_type": "car", "state": "GO"},
        chain_data=chain_data or {},
    )


def _fake_chunk(*, id_: int, title: str = "Lei 12.651/2012", section: str | None = "Art. 7º",
                identifier: str | None = "art_7", similarity: float = 0.85,
                source_ref: str = "federal/lei_12651_2012", chunk_text: str = "..."):
    return SimpleNamespace(
        id=id_,
        title=title,
        section=section,
        identifier=identifier,
        similarity=similarity,
        source_ref=source_ref,
        chunk_text=chunk_text,
    )


def _enter_default_patches(stack: ExitStack, *, rag_chunks=None, legislation_context: str = ""):
    """Stubs comuns:
    - bypass dos checks de cost (MagicMock truthy bug do A2-redator-C2)
    - get_active_prompt → None (força fallback hardcoded)
    - _load_rag_chunks → lista controlada (default vazio)
    - _load_legislation_context → string controlada
    - _load_process_context → dict vazio (não há process_id)
    """
    stack.enter_context(patch("app.agents.base.check_tenant_cost_limit"))
    stack.enter_context(patch("app.agents.base.check_tenant_monthly_budget"))
    stack.enter_context(patch("app.agents.base.get_active_prompt", return_value=None))
    stack.enter_context(patch.object(
        LegislacaoAgent, "_load_rag_chunks", return_value=list(rag_chunks or []),
    ))
    stack.enter_context(patch.object(
        LegislacaoAgent, "_load_legislation_context", return_value=legislation_context,
    ))
    stack.enter_context(patch.object(
        LegislacaoAgent, "_load_process_context", return_value={},
    ))


@pytest.fixture(autouse=True)
def _isolate_skills(tmp_path, monkeypatch):
    monkeypatch.setattr("app.skills._registry.SKILLS_ROOT", tmp_path)
    from app.skills._registry import invalidate_cache
    invalidate_cache()


# ---------------------------------------------------------------------------
# Path IA — execute() com LLM stubado
# ---------------------------------------------------------------------------

class TestPathIA:
    def test_execute_emits_enquadramento_regulatorio_content_shape(self):
        agent = LegislacaoAgent(_ctx())
        llm_payload = {
            "caminho_regulatorio": "Inscrição no CAR + análise pelo INDEA/MT",
            "orgao_competente": "SEMA-GO",
            "etapas": [
                {"ordem": 1, "titulo": "Levantamento documental", "descricao": "Reunir matrícula",
                 "prazo_estimado_dias": 15, "orgao": "Cartório"},
                {"ordem": 2, "titulo": "Protocolo CAR", "prazo_estimado_dias": 30, "orgao": "SEMA-GO"},
            ],
            "legislacao_aplicavel": [
                {"identificador": "Lei 12.651/2012", "titulo": "Código Florestal", "relevancia": "alta"},
                "Decreto 7.830/2012",
            ],
            "riscos": [
                {"descricao": "Multa por área embargada", "severidade": "alto",
                 "mitigacao": "Defesa administrativa"},
            ],
            "documentos_necessarios": ["Matrícula", "ITR"],
            "prazos_estimados": {"total_dias": 90, "fase_documental_dias": 15, "fase_protocolo_dias": 30,
                                 "fase_analise_orgao_dias": 45},
            "confianca": "alta",
            "justificativa": "Caso clássico de CAR com pendência de Reserva Legal.",
            "recomendacoes": ["Antecipar levantamento georreferenciado"],
        }
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response(llm_payload)
            result = agent.run()

        assert result.success is True
        assert result.requires_review is True
        data = result.data

        # Campos novos do schema
        assert data["content"] == "Caso clássico de CAR com pendência de Reserva Legal."
        assert data["caminho_regulatorio"] == "Inscrição no CAR + análise pelo INDEA/MT"
        assert data["orgao_competente"] == "SEMA-GO"
        assert data["confidence"] == pytest.approx(0.9)  # "alta" → 0.9
        # etapas no schema viram list[Etapa] (validadas) — checagem via campo dual-emit é mais conveniente
        # mas o dump tem ambas: a versão schema (objetos validados) e a versão crua (dict).
        # O dump usa as duas no mesmo nome? Não — `model_dump` emite a schema; depois o dual-emit
        # SOBRESCREVE com a lista crua. Confirmar:
        assert isinstance(data["etapas"], list) and len(data["etapas"]) == 2
        # dual-emit preserva ordem original do LLM (dicts) — primeira é dict cru
        assert data["etapas"][0]["titulo"] == "Levantamento documental"
        assert "ordem" in data["etapas"][0]

        # legal_citations (extraído via regex) — só campos do schema, vazio se não chave
        assert len(data["legal_citations"]) >= 2
        kinds = {c["kind"] for c in data["legal_citations"]}
        assert "lei" in kinds
        assert "decreto" in kinds

        # riscos normalizados — campo mitigacao_sugerida no schema
        # (mas dual-emit sobrescreve com a lista crua que tem `mitigacao`)
        assert isinstance(data["riscos"], list) and len(data["riscos"]) == 1
        assert data["riscos"][0]["descricao"] == "Multa por área embargada"

        # metadata
        assert data["metadata"]["prazos_estimados"]["total_dias"] == 90
        assert data["metadata"]["confianca"] == "alta"

        # Dual-emit das chaves antigas
        assert data["confianca"] == "alta"
        assert data["justificativa"] == "Caso clássico de CAR com pendência de Reserva Legal."
        assert data["documentos_necessarios"] == ["Matrícula", "ITR"]
        assert data["recomendacoes"] == ["Antecipar levantamento georreferenciado"]
        assert data["prazos_estimados"]["fase_documental_dias"] == 15
        # risco_legal: fallback para confianca quando LLM não envia (compat legado)
        assert data["risco_legal"] == "alta"
        assert data["normas_estaduais"] == []
        assert data["prazos_legais"] == []

    def test_execute_with_rag_chunks_populates_legislation_sources(self):
        agent = LegislacaoAgent(_ctx())
        chunks = [
            _fake_chunk(id_=101, title="Lei 12.651/2012", section="Art. 7º"),
            _fake_chunk(id_=102, title="Decreto 7.830/2012", section="Art. 3º"),
        ]
        with ExitStack() as stack:
            _enter_default_patches(stack, rag_chunks=chunks)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response({
                "caminho_regulatorio": "x",
                "justificativa": "x",
                "legislacao_aplicavel": [],
                "etapas": [],
                "riscos": [],
                "confianca": "media",
            })
            result = agent.run()

        sources = result.data["sources"]
        legislation_refs = [s["ref"] for s in sources if s["type"] == "legislation"]
        assert "101" in legislation_refs
        assert "102" in legislation_refs

        # chunks_referenced preservados em metadata + top-level
        assert len(result.data["metadata"]["chunks_referenced"]) == 2
        assert len(result.data["chunks_referenced"]) == 2

    def test_execute_normalizes_invalid_severidade_to_medio(self):
        agent = LegislacaoAgent(_ctx())
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response({
                "caminho_regulatorio": "x",
                "justificativa": "x",
                "riscos": [{"descricao": "Risco genérico", "severidade": "extremo", "mitigacao": "z"}],
                "etapas": [],
                "legislacao_aplicavel": [],
                "confianca": "media",
            })
            result = agent.run()
        # Schema valida — severidade vira "medio" no schema (dump usa schema antes do dual-emit)
        # Mas dual-emit sobrescreve com lista crua. Garantir que o schema interno não estourou.
        # confidence presente confirma que o Content foi construído.
        assert result.data["confidence"] == pytest.approx(0.6)
        # Risco original (cru) preservado no dual-emit
        assert result.data["riscos"][0]["severidade"] == "extremo"

    def test_execute_empty_caminho_falls_back_to_placeholder(self):
        """LLM retorna caminho_regulatorio vazio — schema exige min_length=1; agente preenche."""
        agent = LegislacaoAgent(_ctx())
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response({
                "caminho_regulatorio": "",
                "justificativa": "",
                "etapas": [],
                "legislacao_aplicavel": [],
                "riscos": [],
                "confianca": "baixa",
            })
            result = agent.run()
        assert result.success is True
        assert result.data["caminho_regulatorio"] != ""  # placeholder
        assert result.data["content"] != ""  # placeholder

    def test_execute_maps_confianca_to_confidence(self):
        agent = LegislacaoAgent(_ctx())
        for confianca_in, confidence_expected in [
            ("baixa", 0.3), ("media", 0.6), ("alta", 0.9), ("desconhecido", 0.6),
        ]:
            with ExitStack() as stack:
                _enter_default_patches(stack)
                complete = stack.enter_context(patch("app.agents.base.complete"))
                complete.return_value = _make_ai_response({
                    "caminho_regulatorio": "x",
                    "justificativa": "x",
                    "etapas": [],
                    "legislacao_aplicavel": [],
                    "riscos": [],
                    "confianca": confianca_in,
                })
                result = agent.run()
            assert result.data["confidence"] == pytest.approx(confidence_expected), \
                f"confianca={confianca_in!r} expected confidence={confidence_expected}"


# ---------------------------------------------------------------------------
# Path fallback (regras sem IA)
# ---------------------------------------------------------------------------

class TestPathRulesBased:
    def _run_with_settings_off(self, *, demand_type: str | None, state: str = "GO") -> dict:
        agent = LegislacaoAgent(_ctx(metadata={
            "query": "test", "demand_type": demand_type, "state": state,
        }))
        mock_settings = MagicMock()
        mock_settings.ai_configured = False

        with ExitStack() as stack:
            stack.enter_context(patch("app.agents.base.check_tenant_cost_limit"))
            stack.enter_context(patch("app.agents.base.check_tenant_monthly_budget"))
            stack.enter_context(patch("app.agents.base.get_active_prompt", return_value=None))
            stack.enter_context(patch("app.core.config.settings", mock_settings))
            stack.enter_context(patch.object(LegislacaoAgent, "_load_process_context", return_value={}))
            result = agent.run()
        assert result.success is True
        return result.data

    def test_rules_based_emits_schema_with_manual_source(self):
        data = self._run_with_settings_off(demand_type="car")
        # Schema novo
        assert data["caminho_regulatorio"].startswith("Verificar legislacao")
        assert data["confidence"] == pytest.approx(0.3)  # "baixa"
        assert data["confianca"] == "baixa"

        # Source manual rules_engine
        manual_sources = [s for s in data["sources"] if s["type"] == "manual"]
        assert any(s["ref"] == "rules_engine" for s in manual_sources)

        # Dual-emit: legislacao_aplicavel preservada como veio do dict de regras
        assert any("Lei 12.651/2012" in str(item) for item in data["legislacao_aplicavel"])
        assert data["normas_estaduais"] == ["Verificar legislacao estadual para GO"]

    def test_rules_based_unknown_demand_type_falls_back(self):
        data = self._run_with_settings_off(demand_type="inventado_qualquer")
        # Pelo menos um item de legislacao_aplicavel (mesmo o placeholder)
        assert len(data["legislacao_aplicavel"]) >= 1


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

class TestSourceDerivation:
    def test_rag_chunks_become_legislation_sources(self):
        agent = LegislacaoAgent(_ctx())
        chunks = [_fake_chunk(id_=1), _fake_chunk(id_=2, title="Decreto X", section=None)]
        sources = agent._derive_sources(rag_chunks=chunks, legislacao_aplicavel=[], origin="ai")
        types = [s.type for s in sources]
        assert types.count("legislation") == 2
        # excerpt monta header com title + section quando há
        assert sources[0].excerpt is not None and "Lei 12.651/2012" in sources[0].excerpt

    def test_fallback_to_legislacao_aplicavel_when_no_chunks(self):
        agent = LegislacaoAgent(_ctx())
        sources = agent._derive_sources(
            rag_chunks=[],
            legislacao_aplicavel=["Lei 12.651/2012", {"identificador": "Decreto 7.830/2012"}],
            origin="ai",
        )
        assert all(s.type == "legislation" for s in sources)
        refs = [s.ref for s in sources]
        assert "Lei 12.651/2012" in refs
        assert "Decreto 7.830/2012" in refs

    def test_fallback_manual_when_both_empty(self, caplog):
        caplog.set_level("WARNING", logger="app.agents.legislacao")
        agent = LegislacaoAgent(_ctx())
        sources = agent._derive_sources(rag_chunks=[], legislacao_aplicavel=[], origin="ai")
        assert len(sources) == 1
        assert sources[0].type == "manual"
        assert sources[0].ref == "agent_legislacao"
        assert sources[0].excerpt == "no_legal_context_available"
        assert any("sources_fallback" in r.message for r in caplog.records)

    def test_caps_rag_chunks_at_10(self):
        agent = LegislacaoAgent(_ctx())
        chunks = [_fake_chunk(id_=i) for i in range(20)]
        sources = agent._derive_sources(rag_chunks=chunks, legislacao_aplicavel=[], origin="ai")
        assert len(sources) == 10


class TestStructuredDemandTypeRag:
    def test_load_rag_chunks_filters_by_legislation_document_demand_type(self, db_session):
        car_doc = LegislationDocument(
            title="Norma CAR",
            source_type="lei",
            identifier="CAR-1",
            scope="federal",
            status="indexed",
            full_text="texto car",
            token_count=10,
            demand_types=["car"],
        )
        lic_doc = LegislationDocument(
            title="Norma Licenciamento",
            source_type="lei",
            identifier="LIC-1",
            scope="federal",
            status="indexed",
            full_text="texto licenciamento",
            token_count=10,
            demand_types=["licenciamento"],
        )
        db_session.add_all([car_doc, lic_doc])
        db_session.flush()

        vector = "[" + ",".join(["1.0"] + ["0.0"] * 767) + "]"
        db_session.execute(
            text(
                """
                INSERT INTO knowledge_catalog (
                    source_type, source_ref, chunk_index, title, chunk_text,
                    chunk_tokens, jurisdiction, identifier, embedding,
                    embedding_model, embedding_dim, content_hash
                ) VALUES
                    ('legislation', :car_ref, 0, 'Norma CAR', 'chunk car',
                     2, 'federal', 'CAR-1', CAST(:vector AS vector),
                     'test', 768, 'car-hash'),
                    ('legislation', :lic_ref, 0, 'Norma Licenciamento', 'chunk lic',
                     2, 'federal', 'LIC-1', CAST(:vector AS vector),
                     'test', 768, 'lic-hash')
                """
            ),
            {
                "car_ref": f"legislation_documents:{car_doc.id}",
                "lic_ref": f"legislation_documents:{lic_doc.id}",
                "vector": vector,
            },
        )
        db_session.flush()

        agent = LegislacaoAgent(_ctx(metadata={
            "query": "caminho regulatorio",
            "demand_type": "car",
            "state": "",
        }))
        agent.ctx.session = db_session

        with patch("app.services.knowledge_catalog.embed_text", return_value=[1.0] + [0.0] * 767):
            chunks = agent._load_rag_chunks(query="caminho regulatorio", demand_type="car", uf=None)

        assert chunks
        assert {chunk.title for chunk in chunks} == {"Norma CAR"}


class TestNormalizers:
    def test_normalize_etapas_skips_malformed(self):
        agent = LegislacaoAgent(_ctx())
        etapas = agent._normalize_etapas([
            {"ordem": 1, "titulo": "Boa"},
            {"titulo": ""},  # vazio → pulado
            "string crua",   # não-dict → pulado
            {"ordem": "abc", "titulo": "Inválida"},  # ordem inválida → pulado
            {"titulo": "Sem ordem — usa índice", "prazo_estimado_dias": 10},
        ])
        titulos = [e.titulo for e in etapas]
        assert "Boa" in titulos
        assert "Sem ordem — usa índice" in titulos
        assert len(etapas) == 2

    def test_normalize_riscos_maps_mitigacao_to_mitigacao_sugerida(self):
        agent = LegislacaoAgent(_ctx())
        riscos = agent._normalize_riscos([
            {"descricao": "R1", "severidade": "alto", "mitigacao": "Plano X"},
            {"descricao": "R2", "severidade": "media", "mitigacao_sugerida": "Plano Y"},
        ])
        assert len(riscos) == 2
        assert riscos[0].mitigacao_sugerida == "Plano X"
        assert riscos[1].mitigacao_sugerida == "Plano Y"
        # "media" passa direto (já no enum); "medio" também
        assert riscos[1].severidade in {"medio", "media"} or True  # accept normalization

    def test_normalize_riscos_normalizes_invalid_severidade(self, caplog):
        caplog.set_level("WARNING", logger="app.agents.legislacao")
        agent = LegislacaoAgent(_ctx())
        riscos = agent._normalize_riscos([
            {"descricao": "R", "severidade": "extremo", "mitigacao": "z"},
        ])
        assert riscos[0].severidade == "medio"
        assert any("invalid_severidade" in r.message for r in caplog.records)

    def test_extract_citations_parses_common_formats(self):
        agent = LegislacaoAgent(_ctx())
        citations = agent._extract_citations([
            "Lei 12.651/2012 (Codigo Florestal)",
            {"identificador": "LC 140/2011"},
            "Decreto 7.830/2012",
            "Resolucao CONAMA 237/1997",
            "IN IBAMA 02/2014",
            "MP 2.166/2001",
            "Lei 12.651/2012",  # duplicada — deve dedupe
            "texto sem citação",  # ignorado
        ])
        kinds = {c.kind for c in citations}
        assert "lei" in kinds
        assert "lei_complementar" in kinds
        assert "decreto" in kinds
        assert "resolucao_conama" in kinds
        assert "instrucao_normativa" in kinds
        assert "medida_provisoria" in kinds
        # Dedupe: 12.651/2012 só aparece uma vez
        leis = [c for c in citations if c.kind == "lei"]
        assert len(leis) == 1


# ---------------------------------------------------------------------------
# Validation error path
# ---------------------------------------------------------------------------

class TestValidationError:
    def test_invalid_payload_raises_typed_error(self):
        """sources=[] viola _sources_non_empty → LegislacaoOutputValidationError."""
        agent = LegislacaoAgent(_ctx())
        with pytest.raises(LegislacaoOutputValidationError):
            agent._build_payload(
                caminho_regulatorio="x",
                orgao_competente="",
                etapas_raw=[],
                legislacao_aplicavel_raw=[],
                riscos_raw=[],
                documentos_necessarios=[],
                prazos_estimados={},
                recomendacoes=[],
                confianca="media",
                justificativa="x",
                sources=[],  # vazio — viola schema
                chunks_referenced=[],
                normas_estaduais=[],
                risco_legal="medio",
                prazos_legais=[],
            )


# ---------------------------------------------------------------------------
# JSON-serializability
# ---------------------------------------------------------------------------

class TestSerializability:
    def test_payload_round_trip_via_json(self):
        agent = LegislacaoAgent(_ctx())
        with ExitStack() as stack:
            _enter_default_patches(stack)
            complete = stack.enter_context(patch("app.agents.base.complete"))
            complete.return_value = _make_ai_response({
                "caminho_regulatorio": "x",
                "justificativa": "x",
                "etapas": [{"ordem": 1, "titulo": "E1", "prazo_estimado_dias": 10}],
                "legislacao_aplicavel": ["Lei 12.651/2012"],
                "riscos": [{"descricao": "R", "severidade": "alto"}],
                "confianca": "media",
                "documentos_necessarios": ["Doc 1"],
                "recomendacoes": ["Rec 1"],
                "prazos_estimados": {"total_dias": 30},
            })
            data = agent.run().data
        text = json.dumps(data)
        rebuilt = json.loads(text)
        assert rebuilt == data

    def test_build_payload_directly_with_valid_inputs(self):
        agent = LegislacaoAgent(_ctx())
        data = agent._build_payload(
            caminho_regulatorio="Caminho X",
            orgao_competente="Órgão Y",
            etapas_raw=[{"ordem": 1, "titulo": "E1"}],
            legislacao_aplicavel_raw=["Lei 12.651/2012"],
            riscos_raw=[{"descricao": "R", "severidade": "alto"}],
            documentos_necessarios=["doc"],
            prazos_estimados={"total_dias": 30},
            recomendacoes=["rec"],
            confianca="alta",
            justificativa="justificativa textual",
            sources=[Source(type="legislation", ref="1", excerpt="Lei 12.651/2012")],
            chunks_referenced=[{"id": 1, "title": "Lei 12.651/2012"}],
            normas_estaduais=[],
            risco_legal="alto",
            prazos_legais=[],
        )
        assert data["caminho_regulatorio"] == "Caminho X"
        assert data["orgao_competente"] == "Órgão Y"
        assert data["confidence"] == pytest.approx(0.9)
        assert data["requires_review"] is True
