"""Recall da busca vetorial — o índice IVFFlat precisa OLHAR o suficiente.

`ix_knowledge_catalog_embedding_cosine` é um índice IVFFlat com `lists=100`:
busca **aproximada**. O pgvector traz `ivfflat.probes = 1` de fábrica, e com isso
a busca percorre ~1% dos vetores e devolve vizinhos que não são os mais próximos
— **em silêncio**, porque ela sempre devolve alguma coisa.

Medido em 03/08/2026, na pergunta de retificação de CAR, com 3.192 chunks
federais no corpus:

    probes=1   → topo 0,6936; 8º devolvido 0,3996; o trecho de 0,7286 NÃO vinha
    probes=10  → topo 0,7286, e o top-5 real, exato
    probes=50  → idêntico a 10
    probes=100 → idêntico a 10

O sintoma foi confundido com regressão de corpus: depois de ingerir o bloco 2, a
recuperação "piorou". Não tinha piorado — o índice é que não estava olhando, e
crescer o corpus mudou quais listas a sonda única alcançava.

Estes testes travam as duas metades: o valor sai de settings e chega ao banco,
e a busca não quebra onde `SET LOCAL ivfflat.probes` não existe.
"""

import pytest

from app.core.config import settings


def test_default_de_probes_e_maior_que_um():
    """`probes=1` é o default do pgvector e o defeito. O nosso default não pode
    ser 1 nunca — é o valor que produz o modo de falha silenciosa."""
    assert settings.RAG_IVFFLAT_PROBES > 1
    assert settings.RAG_IVFFLAT_PROBES >= 10, (
        "10 ≈ sqrt(lists) para lists=100; abaixo disso o recall medido cai"
    )


def test_probes_de_settings_chega_ao_sql(db_session, monkeypatch):
    """O valor de settings tem de CHEGAR ao banco — não basta existir.

    Confere o SQL emitido, não o parâmetro lido de volta. A primeira versão
    deste teste fazia `SHOW ivfflat.probes` depois da busca e passava sozinha,
    mas quebrava na suíte completa: `SET LOCAL` é escopo de TRANSAÇÃO, e uma
    busca de outro teste já havia deixado o valor default na mesma conexão.
    O teste media o estado do banco, que é compartilhado; o contrato é o SQL
    emitido, que é só desta chamada.
    """
    import app.services.knowledge_catalog as kc

    monkeypatch.setattr(kc, "embed_text", lambda *a, **k: [0.1] * 768)
    monkeypatch.setattr(settings, "RAG_IVFFLAT_PROBES", 7, raising=False)

    emitidos: list[str] = []
    original = db_session.execute

    def _espiao(sentenca, *a, **k):
        emitidos.append(str(sentenca))
        return original(sentenca, *a, **k)

    monkeypatch.setattr(db_session, "execute", _espiao)
    kc.search(db_session, "qualquer consulta", source_type="legislation")

    sets = [s for s in emitidos if "ivfflat.probes" in s]
    assert sets, "a busca não emitiu `SET LOCAL ivfflat.probes` — seguiria no default 1"
    assert "= 7" in sets[0], f"o valor de settings não chegou ao SQL: {sets[0]!r}"


def test_probes_zero_desliga_sem_quebrar(db_session, monkeypatch):
    """Escape hatch: 0 desliga o ajuste (volta ao default do banco) e a busca
    continua funcionando. Serve para diagnosticar sem editar código."""
    import app.services.knowledge_catalog as kc

    monkeypatch.setattr(kc, "embed_text", lambda *a, **k: [0.1] * 768)
    monkeypatch.setattr(settings, "RAG_IVFFLAT_PROBES", 0, raising=False)

    resultados = kc.search(db_session, "qualquer consulta", source_type="legislation")
    assert isinstance(resultados, list)


def test_busca_sobrevive_a_banco_sem_ivfflat(db_session, monkeypatch):
    """Onde `SET LOCAL ivfflat.probes` não existe, a busca NÃO pode morrer.

    O ajuste é otimização de recall, não requisito de funcionamento — degradar
    com elegância vale aqui como em qualquer outro lugar.
    """
    import app.services.knowledge_catalog as kc

    monkeypatch.setattr(kc, "embed_text", lambda *a, **k: [0.1] * 768)

    original = db_session.execute

    def _execute(sentenca, *a, **k):
        texto = str(sentenca)
        if "ivfflat.probes" in texto:
            raise RuntimeError('unrecognized configuration parameter "ivfflat.probes"')
        return original(sentenca, *a, **k)

    monkeypatch.setattr(db_session, "execute", _execute)
    resultados = kc.search(db_session, "qualquer consulta", source_type="legislation")
    assert isinstance(resultados, list), "a busca tem de seguir sem o ajuste"


@pytest.mark.parametrize("valor", [1, 0, -5])
def test_valores_que_nao_deveriam_virar_default(valor):
    """Documenta o que cada valor significa, para quem for mexer no settings.

    1 é o default do pgvector — e o defeito. 0 e negativos desligam o ajuste.
    Nenhum dos três serve como configuração de produção.
    """
    assert valor != settings.RAG_IVFFLAT_PROBES
