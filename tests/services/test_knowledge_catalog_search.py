"""RAG — recuperação por similaridade (caso #12 item E).

Dois defeitos medidos em produção (Supabase, 2026-06-07) com o corpus POPULADO
(24.233 chunks, text-embedding-3-small:768):

1. AGENTE — `demand_type` chegava como sentinela "nao_identificado"; o JOIN
   `demand_types @> ["nao_identificado"]` devolvia ZERO linhas (a tag não existe
   no corpus). Sintoma: "NENHUM TRECHO RELEVANTE RECUPERADO", tokens_in≈694.
2. SERVIÇO — o filtro `kc.uf = :uf` excluía a legislação FEDERAL (uf IS NULL):
   filtrando por GO restavam 4.280 chunks e os 761 federais ficavam de fora.

Estes testes travam as duas correções como regressão. O embedding da CONSULTA é
mockado (sem rede); o que importa aqui é a montagem do filtro, não o ranking.
"""

import pytest
from sqlalchemy import text

from app.agents.base import AgentContext
from app.agents.legislacao import LegislacaoAgent


def _vec(seed: float) -> str:
    """Vetor 768-d literal pgvector (constante por seed)."""
    return "[" + ",".join(f"{seed:.6f}" for _ in range(768)) + "]"


def _insert_chunk(session, *, ref, uf, seed):
    session.execute(
        text(
            """
            INSERT INTO knowledge_catalog (
                tenant_id, source_type, source_ref, chunk_index,
                title, chunk_text, chunk_tokens, uf,
                embedding, embedding_model, embedding_dim, content_hash
            ) VALUES (
                NULL, 'legislation', :ref, 0,
                :title, :body, 10, :uf,
                CAST(:emb AS vector), 'text-embedding-3-small', 768, :h
            )
            """
        ),
        {
            "ref": ref, "title": f"Norma {ref}", "body": f"texto {ref}",
            "uf": uf, "emb": _vec(seed), "h": f"hash-{ref}",
        },
    )


@pytest.fixture
def _seed_corpus(db_session):
    _insert_chunk(db_session, ref="go-1", uf="GO", seed=0.10)
    _insert_chunk(db_session, ref="federal-1", uf=None, seed=0.11)
    _insert_chunk(db_session, ref="mt-1", uf="MT", seed=0.12)
    db_session.flush()
    return db_session


def test_search_uf_inclui_federal(_seed_corpus, monkeypatch):
    """Filtrar por GO retorna GO + FEDERAL (uf NULL), nunca exclui o federal;
    MT (outra UF) fica de fora."""
    import app.services.knowledge_catalog as kc

    monkeypatch.setattr(kc, "embed_text", lambda *a, **k: [0.1] * 768)
    results = kc.search(
        _seed_corpus, "qualquer consulta", source_type="legislation", uf="GO",
    )
    refs = {r.source_ref for r in results}
    assert "go-1" in refs
    assert "federal-1" in refs, "legislação federal (uf NULL) não pode ser excluída"
    assert "mt-1" not in refs


def test_search_sem_uf_retorna_tudo(_seed_corpus, monkeypatch):
    import app.services.knowledge_catalog as kc

    monkeypatch.setattr(kc, "embed_text", lambda *a, **k: [0.1] * 768)
    refs = {r.source_ref for r in kc.search(_seed_corpus, "x", source_type="legislation")}
    assert {"go-1", "federal-1", "mt-1"} <= refs


def test_agente_sentinela_demand_type_vira_none(monkeypatch):
    """O agente NÃO repassa a sentinela "nao_identificado" como filtro de demanda
    (seria um JOIN impossível → 0 trechos). Vira None (sem filtro)."""
    import app.services.knowledge_catalog as kc

    calls: list[dict] = []

    def _fake_search(session, composed, **kwargs):
        calls.append(kwargs)
        return []

    monkeypatch.setattr(kc, "search", _fake_search)
    ctx = AgentContext(tenant_id=1, user_id=None, process_id=None, session=None)
    agent = LegislacaoAgent(ctx)
    agent._load_rag_chunks(
        query="Qual o caminho regulatorio?", demand_type="nao_identificado", uf="GO",
    )
    assert calls, "esperava ao menos uma busca"
    assert calls[0]["demand_type"] is None, "sentinela deveria virar None"
    assert calls[0]["uf"] == "GO"


def test_agente_demand_type_real_e_repassado(monkeypatch):
    """Um demand_type REAL (tag do corpus) é repassado normalmente."""
    import app.services.knowledge_catalog as kc

    calls: list[dict] = []
    monkeypatch.setattr(kc, "search", lambda s, c, **kw: calls.append(kw) or [])
    ctx = AgentContext(tenant_id=1, user_id=None, process_id=None, session=None)
    LegislacaoAgent(ctx)._load_rag_chunks(
        query="retificar CAR", demand_type="retificacao_car", uf="GO",
    )
    assert calls[0]["demand_type"] == "retificacao_car"
