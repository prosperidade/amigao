"""Fundamentação: identidade da norma, dispositivo e cobertura honesta (#9, #10).

O achado mais grave da validação de 30/07, medido no corpus de produção:

* a citação **"Art. 70 da Lei 9.605/98"** (lei FEDERAL) foi marcada
  ``localizada: True`` apontando o chunk 4838 — *"MT — Compêndio Regente NUC04:
  Núcleo de Licenciamento Ambiental"*, seção "Art. 70.", jurisdição **estadual**,
  UF **MT**. Casou pela string "Art. 70." e virou fonte clicável de um passivo
  federal em Goiás;
* "IN IBAMA nº 14/2009" → chunk 19532, resolução de **MS** sobre comércio de
  iscas vivas.

O corpus explica: 26.505 chunks estaduais contra 785 federais (IBAMA: 106). Sem
escopo por esfera e sem conferência de identidade, toda citação federal afunda em
compêndio estadual de outra UF — e o resultado sai plausível e errado, a classe
de falha mais cara aqui.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.diagnostico import _rotulo_norma
from app.services.auto_infracao_extraction import chunk_confere_com_a_norma


@dataclass
class _Chunk:
    id: int
    identifier: str | None = None
    title: str | None = None
    chunk_text: str = ""
    section: str | None = None
    jurisdiction: str | None = None


# ── Identidade da norma (o falso positivo medido) ──────────────────────────


def test_compendio_estadual_nao_passa_por_lei_federal():
    """O chunk 4838 real: casava só pela string 'Art. 70.'."""
    falso = _Chunk(
        id=4838,
        identifier="MT-NUC04-licenciamento",
        title="MT — Compêndio Regente NUC04: Núcleo de Licenciamento Ambiental",
        chunk_text="Art. 70.",
        section="Art. 70.",
        jurisdiction="estadual",
    )
    assert chunk_confere_com_a_norma(falso, numero="9.605", ano=1998) is False


def test_chunk_da_norma_certa_confere():
    certo = _Chunk(
        id=1,
        identifier="lei-9605-1998",
        title="Lei nº 9.605, de 12 de fevereiro de 1998",
        chunk_text="Art. 70. Considera-se infração administrativa ambiental…",
        section="Art. 70.",
        jurisdiction="federal",
    )
    assert chunk_confere_com_a_norma(certo, numero="9.605", ano=1998) is True


def test_numero_no_texto_do_trecho_tambem_confere():
    """Corpus nem sempre preenche identifier/title — o texto vale."""
    c = _Chunk(id=2, chunk_text="…nos termos da Lei 12.651/2012, art. 61-A…")
    assert chunk_confere_com_a_norma(c, numero="12.651", ano=2012) is True


def test_norma_sem_numero_nunca_confere():
    assert chunk_confere_com_a_norma(_Chunk(id=3, chunk_text="qualquer"), "", 1998) is False


def test_formatacao_do_numero_nao_atrapalha():
    """'9.605' e '9605' são a mesma lei."""
    c = _Chunk(id=4, title="Lei 9605/98", chunk_text="Art. 70.")
    assert chunk_confere_com_a_norma(c, numero="9.605", ano=1998) is True


# ── Item 9 — citar o dispositivo ───────────────────────────────────────────


def test_rotulo_acrescenta_o_dispositivo_quando_o_chunk_tem():
    rotulo = _rotulo_norma({"citacao": "Lei 9.605/98", "dispositivo": "Art. 70."})
    assert rotulo == "Lei 9.605/98, Art. 70"


def test_rotulo_nao_repete_dispositivo_ja_presente_na_citacao():
    rotulo = _rotulo_norma({"citacao": "Art. 70 da Lei 9.605/98", "dispositivo": "Art. 70."})
    assert rotulo == "Art. 70 da Lei 9.605/98"


def test_rotulo_sem_dispositivo_devolve_a_citacao():
    assert _rotulo_norma({"citacao": "Lei 9.605/98"}) == "Lei 9.605/98"
    assert _rotulo_norma({"citacao": "Lei 9.605/98", "dispositivo": None}) == "Lei 9.605/98"


# ── Item 10 — honestidade de cobertura ─────────────────────────────────────


def test_biblioteca_vazia_declara_a_lacuna(db_session):
    """Biblioteca vazia era honesta e MUDA — a tela não distinguia os dois casos."""
    from app.services.rota_shadow import apply_shadow

    servivel = apply_shadow(
        db_session, {"caminho_regulatorio": "x", "chunks_referenced": []},
        tenant_id=None, agent_name="legislacao",
    )
    assert servivel["fundamentacao"] == []
    assert "não cobrir o órgão/esfera" in servivel["cobertura_nota"]
    # E o campo prescritivo continua sombreado (ADR-033 intacta).
    assert "caminho_regulatorio" not in servivel


def test_cobertura_insuficiente_marca_a_citacao_e_nao_mente(db_session, monkeypatch):
    """A resposta deixa de ser 'não localizada' (que sugere que a norma não existe)."""
    import app.services.auto_infracao_extraction as mod

    # Esfera federal com base rasa — o retrato do corpus de produção.
    monkeypatch.setattr(mod, "_cobertura_da_esfera", lambda _db, _e: 106)
    monkeypatch.setattr(
        "app.services.knowledge_catalog.search", lambda *a, **k: []
    )

    out = mod.lookup_enquadramento(
        "Art. 70 da Lei 9.605/98", db_session=db_session,
        esferas=["federal"], orgao="IBAMA",
    )
    assert out[0]["localizada"] is False
    assert out[0]["cobertura_insuficiente"] is True
    assert out[0]["motivo"] == (
        "cobertura normativa insuficiente para IBAMA — base em atualização"
    )


def test_corpus_farto_mantem_o_nao_localizada(db_session, monkeypatch):
    """Base boa + norma não achada = a norma não está lá. Não confundir as duas."""
    import app.services.auto_infracao_extraction as mod

    monkeypatch.setattr(mod, "_cobertura_da_esfera", lambda _db, _e: 20_000)
    monkeypatch.setattr("app.services.knowledge_catalog.search", lambda *a, **k: [])

    out = mod.lookup_enquadramento(
        "Lei 12.651/2012", db_session=db_session, esferas=["estadual"], orgao="SEMAD",
    )
    assert out[0]["cobertura_insuficiente"] is not True
    assert out[0]["motivo"] == "não localizada no corpus"
