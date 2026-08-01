"""Dimensão temporal do corpus — a norma revogada é citável, nunca como vigente.

O caso 15 é um auto do IBAMA de 2007. O enquadramento invoca o Decreto 3.179/1999
e a Lei 4.771/1965, ambos revogados hoje. A defesa PRECISA citá-los (a norma da
data do fato — *tempus regit actum*) e o sistema não pode apresentá-los como
direito vigente. Ver ADR-037.

Os três casos que o André pediu, mais a prova de que o Decreto 6.514/2008 passou
a ter texto próprio recuperável (era o buraco medido em 31/07: 102 chunks o
citavam, nenhum continha seu texto).

O embedding da consulta é mockado — o que se testa aqui é o filtro temporal e o
rótulo, não o ranking semântico.
"""

from datetime import date

import pytest
from sqlalchemy import text

from app.services.vigencia import (
    MARCADOR_HISTORICA,
    Vigencia,
    rotulo_historico,
    titulo_com_vigencia,
    vigencia_do_documento,
)

# --------------------------------------------------------------------------
# Unidade — a regra de vigência, sem banco
# --------------------------------------------------------------------------


def test_norma_vigente_nao_ganha_rotulo():
    """Caso 3: norma vigente não carrega rótulo nenhum."""
    vig = Vigencia(inicio=date(2008, 7, 22), fim=None)
    assert vig.historica is False
    assert rotulo_historico(vig) == ""
    assert titulo_com_vigencia("Decreto 6.514/2008", vig) == "Decreto 6.514/2008"


def test_norma_revogada_declara_revogacao_sucessora_e_janela():
    vig = Vigencia(
        inicio=date(1999, 9, 21),
        fim=date(2008, 7, 22),
        sucessora_ref="Decreto 6.514/2008",
    )
    rotulo = rotulo_historico(vig)
    assert MARCADOR_HISTORICA in rotulo
    assert "22/07/2008" in rotulo
    assert "Decreto 6.514/2008" in rotulo
    assert "NÃO citar como norma vigente" in rotulo


def test_vigente_em_respeita_a_janela():
    vig = Vigencia(inicio=date(1999, 9, 21), fim=date(2008, 7, 22))
    assert vig.vigente_em(date(2007, 6, 1)) is True     # o fato do caso 15
    assert vig.vigente_em(date(2026, 7, 31)) is False   # hoje
    assert vig.vigente_em(date(1999, 1, 1)) is False    # antes de existir


def test_documento_sem_vigencia_declarada_conta_como_vigente():
    """Todo o corpus anterior a esta coluna. Ausência de curadoria não pode
    apagar trecho da busca."""

    class _Doc:
        vigencia_inicio = None
        vigencia_fim = None
        sucessora_ref = None
        effective_date = None

    vig = vigencia_do_documento(_Doc())
    assert vig.historica is False
    assert vig.vigente_em(date(2026, 7, 31)) is True


def test_rotulo_nao_duplica_ao_reindexar():
    """Indexação é idempotente; o rótulo não pode se empilhar."""
    vig = Vigencia(fim=date(2012, 5, 25), sucessora_ref="Lei 12.651/2012")
    uma = titulo_com_vigencia("Lei 4.771/1965", vig)
    duas = titulo_com_vigencia(uma, vig)
    assert uma == duas
    assert duas.count(MARCADOR_HISTORICA) == 1


# --------------------------------------------------------------------------
# Integração — o filtro temporal na busca
# --------------------------------------------------------------------------


def _vec(seed: float) -> str:
    return "[" + ",".join(f"{seed:.6f}" for _ in range(768)) + "]"


def _doc_e_chunk(session, *, identifier, titulo, corpo, vig_inicio, vig_fim,
                 sucessora_ref=None, seed=0.1):
    """Grava o documento e um chunk seu, como a ingestão faz."""
    doc_id = session.execute(
        text(
            """
            INSERT INTO legislation_documents
                (title, source_type, identifier, scope, status, full_text,
                 token_count, vigencia_inicio, vigencia_fim, sucessora_ref)
            VALUES (:t, 'lei', :i, 'federal', 'indexed', :body, 10,
                    :vi, :vf, :sr)
            RETURNING id
            """
        ),
        {"t": titulo, "i": identifier, "body": corpo,
         "vi": vig_inicio, "vf": vig_fim, "sr": sucessora_ref},
    ).scalar()

    vig = Vigencia(inicio=vig_inicio, fim=vig_fim, sucessora_ref=sucessora_ref)
    session.execute(
        text(
            """
            INSERT INTO knowledge_catalog (
                tenant_id, source_type, source_ref, chunk_index,
                title, chunk_text, chunk_tokens, identifier,
                embedding, embedding_model, embedding_dim, content_hash
            ) VALUES (
                NULL, 'legislation', :ref, 0, :title, :body, 10, :ident,
                CAST(:emb AS vector), 'text-embedding-3-small', 768, :h
            )
            """
        ),
        {
            "ref": f"legislation_documents:{doc_id}",
            "title": titulo_com_vigencia(titulo, vig),
            "body": corpo,
            "ident": identifier,
            "emb": _vec(seed),
            "h": f"hash-{identifier}",
        },
    )
    return doc_id


@pytest.fixture
def _corpus_temporal(db_session):
    """Duas normas sobre o mesmo tema, uma revogada pela outra."""
    _doc_e_chunk(
        db_session,
        identifier="Decreto 3.179/1999",
        titulo="Sanções administrativas ao meio ambiente (Decreto 3.179/1999)",
        corpo="Art. 25. A supressão de vegetação em área de preservação permanente...",
        vig_inicio=date(1999, 9, 21),
        vig_fim=date(2008, 7, 22),
        sucessora_ref="Decreto 6.514/2008",
        seed=0.10,
    )
    _doc_e_chunk(
        db_session,
        identifier="Decreto 6.514/2008",
        titulo="Infrações e sanções administrativas ao meio ambiente (Decreto 6.514/2008)",
        corpo="Art. 18. § 1º O embargo da área é medida cautelar...",
        vig_inicio=date(2008, 7, 22),
        vig_fim=None,
        seed=0.11,
    )
    db_session.flush()
    return db_session


def test_fato_de_2007_traz_a_norma_da_epoca_rotulada(_corpus_temporal, monkeypatch):
    """CASO 1 — o auto é de 2007: a norma da época vem, e vem AVISADA."""
    import app.services.knowledge_catalog as kc

    monkeypatch.setattr(kc, "embed_text", lambda *a, **k: [0.1] * 768)
    achados = kc.search(
        _corpus_temporal,
        "supressão de vegetação em APP",
        source_type="legislation",
        vigente_em=date(2007, 6, 1),
    )
    por_id = {r.identifier: r for r in achados}

    assert "Decreto 3.179/1999" in por_id, "a norma da data do fato tem de vir"
    antiga = por_id["Decreto 3.179/1999"]
    assert antiga.historica is True
    assert MARCADOR_HISTORICA in (antiga.title or ""), (
        "o trecho precisa CHEGAR rotulado — é o título que o agente põe no prompt"
    )
    assert antiga.sucessora_ref == "Decreto 6.514/2008"

    # A norma de 2008 não valia em 2007.
    assert "Decreto 6.514/2008" not in por_id


def test_fato_de_hoje_nao_traz_a_revogada_como_vigente(_corpus_temporal, monkeypatch):
    """CASO 2 — fato atual: a revogada não aparece; a vigente aparece limpa."""
    import app.services.knowledge_catalog as kc

    monkeypatch.setattr(kc, "embed_text", lambda *a, **k: [0.1] * 768)
    achados = kc.search(
        _corpus_temporal,
        "embargo de área",
        source_type="legislation",
        vigente_em=date(2026, 7, 31),
    )
    por_id = {r.identifier: r for r in achados}

    assert "Decreto 3.179/1999" not in por_id, (
        "norma revogada não pode ser recuperada para fato de hoje"
    )
    assert "Decreto 6.514/2008" in por_id


def test_norma_vigente_chega_sem_rotulo(_corpus_temporal, monkeypatch):
    """CASO 3 — a vigente não carrega aviso nenhum (o rótulo não vaza)."""
    import app.services.knowledge_catalog as kc

    monkeypatch.setattr(kc, "embed_text", lambda *a, **k: [0.1] * 768)
    achados = kc.search(
        _corpus_temporal, "embargo", source_type="legislation",
        vigente_em=date(2026, 7, 31),
    )
    vigente = next(r for r in achados if r.identifier == "Decreto 6.514/2008")
    assert vigente.historica is False
    assert MARCADOR_HISTORICA not in (vigente.title or "")
    assert vigente.sucessora_ref is None


def test_sem_filtro_temporal_a_historica_vem_avisada(_corpus_temporal, monkeypatch):
    """Sem `vigente_em`, tudo vem — e o histórico vem rotulado.

    Esconder a norma revogada seria pior que trazê-la avisada: forçaria o
    consultor a buscar fora do sistema na hora mais delicada.
    """
    import app.services.knowledge_catalog as kc

    monkeypatch.setattr(kc, "embed_text", lambda *a, **k: [0.1] * 768)
    achados = kc.search(_corpus_temporal, "APP", source_type="legislation")
    por_id = {r.identifier: r for r in achados}

    assert {"Decreto 3.179/1999", "Decreto 6.514/2008"} <= set(por_id)
    assert MARCADOR_HISTORICA in (por_id["Decreto 3.179/1999"].title or "")
    assert MARCADOR_HISTORICA not in (por_id["Decreto 6.514/2008"].title or "")


def test_6514_tem_texto_proprio_e_nao_so_mencao(_corpus_temporal, monkeypatch):
    """O buraco medido em 31/07: 102 chunks CITAVAM o 6.514 e nenhum o continha.

    Identidade, não parecença (mesma régua do ADR-036): o trecho vale como
    fundamentação quando o `identifier` É a norma — não quando o texto de outra
    norma a menciona.
    """
    import app.services.knowledge_catalog as kc

    # Um chunk de OUTRA norma que apenas cita o 6.514 — não pode contar.
    _doc_e_chunk(
        _corpus_temporal,
        identifier="Lei estadual qualquer",
        titulo="Compêndio estadual",
        corpo="aplica-se subsidiariamente o Decreto 6.514, de 22 de julho de 2008",
        vig_inicio=date(2010, 1, 1),
        vig_fim=None,
        seed=0.12,
    )
    _corpus_temporal.flush()

    monkeypatch.setattr(kc, "embed_text", lambda *a, **k: [0.1] * 768)
    achados = kc.search(_corpus_temporal, "embargo", source_type="legislation")

    proprios = [r for r in achados if r.identifier == "Decreto 6.514/2008"]
    assert proprios, "o 6.514 precisa ter chunk com identidade própria"
    assert "Art. 18" in proprios[0].chunk_text
    assert "§ 1º" in proprios[0].chunk_text

    mencoes = [
        r for r in achados
        if r.identifier != "Decreto 6.514/2008" and "6.514" in r.chunk_text
    ]
    assert mencoes, "o cenário do teste precisa ter a menção de terceiro"
    assert all(r.identifier != "Decreto 6.514/2008" for r in mencoes)
