"""Trava de espaço vetorial — consulta e índice no mesmo modelo, ou recusa.

Embeddings de provedores diferentes não são intercambiáveis: são espaços
distintos. Comparar distâncias entre eles **não falha** — devolve trechos com
similaridade de aparência normal e conteúdo aleatório.

É pior que o `probes=1` da #113: lá os vizinhos eram subótimos, mas do MESMO
espaço; aqui seriam distâncias entre coisas incomparáveis, e o consultor
receberia oito fundamentações convincentes e inventadas.

O risco era vivo: `_select_provider()` decidia por **presença de chave** — se há
`OPENAI_API_KEY`, OpenAI; senão, Gemini. Chave ausente, cota estourada ou deploy
sem a variável trocaria o espaço vetorial da consulta contra um índice do outro
provedor. Fallback automático de provider, aqui, é bug — não resiliência.

Medido em 03/08 antes de concluir: o corpus está homogêneo (31.298 chunks, todos
`text-embedding-3-small` 768d). A mistura **ainda não aconteceu** — esta trava é
prevenção, não reparo (dívida #114).
"""

import pytest
from sqlalchemy import text

from app.services.embeddings import (
    DEFAULT_PROVIDER,
    OPENAI_MODEL,
    PROVIDERS,
    EmbeddingError,
    EspacoVetorialIncompativel,
)

# --------------------------------------------------------------------------
# O provider é EXPLÍCITO, nunca inferido por presença de chave
# --------------------------------------------------------------------------

def test_sem_configuracao_usa_o_default_do_produto(monkeypatch):
    """Sem `EMBEDDING_PROVIDER`, assume o default — não olha se há chave."""
    from app.services import embeddings as emb

    monkeypatch.setattr("app.core.config.settings.EMBEDDING_PROVIDER", "")
    assert emb._select_provider() == DEFAULT_PROVIDER
    assert emb.current_model() == PROVIDERS[DEFAULT_PROVIDER]


def test_ausencia_de_chave_NAO_troca_de_provider(monkeypatch):
    """O coração da #114: sem a chave do provider configurado, o sistema NÃO
    passa a usar o outro. Se trocasse, a consulta iria para outro espaço
    vetorial e a busca devolveria ruído com cara de resultado."""
    from app.services import embeddings as emb

    monkeypatch.setattr("app.core.config.settings.EMBEDDING_PROVIDER", "openai")
    monkeypatch.setattr("app.core.config.settings.OPENAI_API_KEY", "")

    assert emb._select_provider() == "openai", (
        "sem chave o provider tem de CONTINUAR openai — a falha vem depois, "
        "ao pedir a chave, e é ruidosa"
    )
    assert emb.current_model() == OPENAI_MODEL

    with pytest.raises(EmbeddingError):
        emb._openai_key()


def test_provider_invalido_falha_alto(monkeypatch):
    """Erro de digitação em produção não pode virar escolha silenciosa."""
    from app.services import embeddings as emb

    monkeypatch.setattr("app.core.config.settings.EMBEDDING_PROVIDER", "anthropic")
    with pytest.raises(EmbeddingError, match="inválido"):
        emb._select_provider()


def test_provider_explicito_vence(monkeypatch):
    from app.services import embeddings as emb

    monkeypatch.setattr("app.core.config.settings.EMBEDDING_PROVIDER", "gemini")
    assert emb._select_provider() == "gemini"
    assert emb.current_model() == PROVIDERS["gemini"]


# --------------------------------------------------------------------------
# A busca MIRA um espaço — e recusa quando o índice está em outro
# --------------------------------------------------------------------------

def _chunk(session, *, ref, modelo, seed=0.1):
    session.execute(
        text(
            """
            INSERT INTO knowledge_catalog (
                tenant_id, source_type, source_ref, chunk_index,
                title, chunk_text, chunk_tokens,
                embedding, embedding_model, embedding_dim, content_hash
            ) VALUES (
                NULL, 'legislation', :ref, 0, :t, :b, 10,
                CAST(:emb AS vector), :modelo, 768, :h
            )
            """
        ),
        {
            "ref": ref, "t": f"Norma {ref}", "b": f"texto {ref}",
            "emb": "[" + ",".join(f"{seed:.6f}" for _ in range(768)) + "]",
            "modelo": modelo, "h": f"hash-{ref}-{modelo}",
        },
    )


def test_busca_so_ve_chunks_do_proprio_espaco(db_session, monkeypatch):
    """Índice misto NÃO é comparado: a busca filtra pelo modelo esperado."""
    import app.services.knowledge_catalog as kc

    monkeypatch.setattr(kc, "embed_text", lambda *a, **k: [0.1] * 768)
    _chunk(db_session, ref="do-openai", modelo=OPENAI_MODEL)
    _chunk(db_session, ref="do-gemini", modelo=PROVIDERS["gemini"], seed=0.11)
    db_session.flush()

    refs = {
        r.source_ref
        for r in kc.search(db_session, "consulta", source_type="legislation",
                           embedding_model=OPENAI_MODEL)
    }
    assert refs == {"do-openai"}, "vetor de outro modelo não pode entrar na comparação"


def test_corpus_em_outro_espaco_RECUSA_em_vez_de_devolver_vazio(db_session, monkeypatch):
    """A falha que a #114 existe para impedir.

    Corpus povoado, consulta em outro espaço: devolver `[]` faria o agente dizer
    "não encontrei fundamentação" quando o problema é estar perguntando no
    idioma errado. Tem de recusar, alto, dizendo o que fazer.
    """
    import app.services.knowledge_catalog as kc

    monkeypatch.setattr(kc, "embed_text", lambda *a, **k: [0.1] * 768)
    _chunk(db_session, ref="tudo-em-openai", modelo=OPENAI_MODEL)
    db_session.flush()

    with pytest.raises(EspacoVetorialIncompativel) as erro:
        kc.search(db_session, "consulta", source_type="legislation",
                  embedding_model=PROVIDERS["gemini"])

    mensagem = str(erro.value)
    assert OPENAI_MODEL in mensagem, "a mensagem precisa dizer em que espaço o corpus ESTÁ"
    assert "EMBEDDING_PROVIDER" in mensagem, "e o que fazer a respeito"


def test_corpus_vazio_nao_e_incompatibilidade(db_session, monkeypatch):
    """Sem nenhum chunk, não há espaço conflitante — devolve vazio, não erro.
    Corpus vazio é um estado legítimo (ambiente novo); espaço trocado não é."""
    import app.services.knowledge_catalog as kc

    monkeypatch.setattr(kc, "embed_text", lambda *a, **k: [0.1] * 768)
    assert kc.search(db_session, "consulta", source_type="legislation") == []


def test_filtro_normal_sem_resultado_tambem_nao_e_incompatibilidade(db_session, monkeypatch):
    """Corpus todo no MESMO modelo da consulta, mas o filtro não casa nada:
    é resposta vazia legítima, não espaço trocado."""
    import app.services.knowledge_catalog as kc

    monkeypatch.setattr(kc, "embed_text", lambda *a, **k: [0.1] * 768)
    _chunk(db_session, ref="unico", modelo=OPENAI_MODEL)
    db_session.flush()

    assert kc.search(db_session, "consulta", source_type="legislation",
                     uf="ZZ", jurisdiction="municipal") == []
