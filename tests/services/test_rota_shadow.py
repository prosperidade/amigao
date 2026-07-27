"""ADR-033 — rota sombreada: persiste estruturado, NÃO renderiza.

O contrato que estes testes protegem: no modo sombra a API não serve os campos
prescritivos (etapas/prazos/caminho), mas o `AIJob.result` no banco continua
inteiro. Se um dia alguém "simplificar" isso apagando o resultado, a decisão
deixa de ser reversível e o material de avaliação some — por isso o teste olha as
duas pontas.
"""

from unittest.mock import patch

import pytest

from app.services.rota_shadow import (
    MODO_ATIVA,
    MODO_SHADOW,
    ROTULO_SHADOW,
    apply_shadow,
    build_fundamentacao,
)


class _SessaoFalsa:
    """Sessão mínima: o modo sombra é lógica pura sobre o payload.

    `rota_mode` é patchado nos testes e `_carregar_chunks` só faz UMA query de
    leitura — um stub mantém estes testes rodando sem banco, que é o certo para
    uma regra de apresentação.
    """

    def execute(self, *_args, **_kwargs):
        class _R:
            def mappings(self_inner):
                return self_inner

            def all(self_inner):
                return []

        return _R()


@pytest.fixture
def db_session():
    return _SessaoFalsa()


@pytest.fixture
def result_legislacao():
    """Formato real do agente (dual-emit), reduzido ao que importa aqui."""
    return {
        "content": "Enquadramento preliminar.",
        "caminho_regulatorio": "Defesa administrativa + retificação do CAR",
        "orgao_competente": "SEMAD-GO",
        "etapas": [{"ordem": 1, "titulo": "Analisar auto", "prazo_estimado_dias": 10}],
        "prazos_estimados": {"defesa": 20},
        "prazos_legais": ["20 dias para recurso"],
        "recomendacoes": ["Protocolar defesa"],
        "documentos_necessarios": ["Matrícula"],
        "legislacao_aplicavel": ["Lei 12.651/2012"],
        "chunks_referenced": [],
        "justificativa": "Base legal localizada.",
    }


class TestApplyShadow:
    def test_shadow_remove_prescritivos_e_marca_rotulo(self, db_session, result_legislacao):
        with patch("app.services.rota_shadow.rota_mode", return_value=MODO_SHADOW):
            servido = apply_shadow(
                db_session, result_legislacao, tenant_id=1, agent_name="legislacao"
            )

        for campo in (
            "caminho_regulatorio", "etapas", "prazos_estimados",
            "prazos_legais", "recomendacoes", "documentos_necessarios",
        ):
            assert campo not in servido, f"{campo} vazou para a UI no modo sombra"

        assert servido["rota_shadow"] is True
        assert servido["rota_shadow_rotulo"] == ROTULO_SHADOW
        # O que a consultora PRECISA continua servido.
        assert servido["legislacao_aplicavel"] == ["Lei 12.651/2012"]
        assert servido["justificativa"] == "Base legal localizada."
        assert "fundamentacao" in servido

    def test_shadow_nao_muta_o_result_original(self, db_session, result_legislacao):
        """O dado do banco fica inteiro — sombra é filtro de leitura, não delete."""
        with patch("app.services.rota_shadow.rota_mode", return_value=MODO_SHADOW):
            apply_shadow(db_session, result_legislacao, tenant_id=1, agent_name="legislacao")

        assert result_legislacao["etapas"], "o result persistido foi mutado"
        assert result_legislacao["caminho_regulatorio"]
        assert "rota_shadow" not in result_legislacao

    def test_modo_ativa_passa_intacto(self, db_session, result_legislacao):
        with patch("app.services.rota_shadow.rota_mode", return_value=MODO_ATIVA):
            servido = apply_shadow(
                db_session, result_legislacao, tenant_id=1, agent_name="legislacao"
            )
        assert servido is result_legislacao

    def test_outro_agente_nao_e_tocado(self, db_session, result_legislacao):
        """Sombra é da Análise Legal. Diagnóstico/extrator seguem como estão."""
        with patch("app.services.rota_shadow.rota_mode", return_value=MODO_SHADOW):
            servido = apply_shadow(
                db_session, result_legislacao, tenant_id=1, agent_name="diagnostico"
            )
        assert servido is result_legislacao

    def test_result_nao_dict_nao_quebra(self, db_session):
        with patch("app.services.rota_shadow.rota_mode", return_value=MODO_SHADOW):
            assert apply_shadow(db_session, None, tenant_id=1, agent_name="legislacao") is None


class TestBuildFundamentacao:
    def test_sem_chunks_devolve_lista_vazia(self, db_session):
        """Biblioteca vazia é honesta; citar norma de memória não seria."""
        assert build_fundamentacao(db_session, {"chunks_referenced": []}) == []
        assert build_fundamentacao(db_session, {}) == []

    def test_item_carrega_fonte_e_alcance(self, db_session):
        """Sem chunk no banco, o item ainda sai com o que o job guardou."""
        result = {
            "chunks_referenced": [
                {"id": 999999, "identifier": "Lei 12.651/2012", "title": "Código Florestal",
                 "section": "Art. 17", "source_ref": "legislation_documents:1"},
            ]
        }
        itens = build_fundamentacao(db_session, result)
        assert len(itens) == 1
        item = itens[0]
        assert item["identificador"] == "Lei 12.651/2012"
        assert item["fonte"]["tipo"] == "legislacao"
        assert item["fonte"]["ref"] == "999999"
        # Alcance e vigência desconhecidos permanecem NULOS — nunca preenchidos
        # com um palpite (item 12: "conferi em" só se realmente conferiu).
        assert item["esfera"] is None
        assert item["vigencia_conferida_em"] is None
