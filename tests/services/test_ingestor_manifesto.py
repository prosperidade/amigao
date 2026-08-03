"""Ingestor dirigido por curadoria — as 8 garantias do Bloco 0 (ADR-038).

Cada teste aqui corresponde a um bug que já pagamos, e os casos são os REAIS do
núcleo 06 (01/08/2026), não inventados:

  (a) idempotência   — 8 das 26 linhas deram `skip` por hash idêntico
  (b) canário        — mojibake do Planalto, três meses invisível
  (c) normalização   — U+00A0 quebrando busca literal
  (d) keyword        — a CF da planilha vinha TRUNCADA sem o art. 225 que a
                       própria curadoria invoca; e o LegisWeb já serviu uma
                       resolução da SEFAZ-AM no lugar da IN IBAMA 10/2012
  (e) proveniência   — 97,3% do corpus sem origem declarada
  (f) vigência       — Decreto 9.760/2019 revogado e marcado "validado"
  (g) lote resiliente— 403 do IBAMA não pode derrubar as outras 25 linhas
  (h) dry-run        — padrão
"""

import csv
from datetime import date

import pytest

from app.services.manifesto_corpus import (
    TIPO_NORMA,
    TIPO_REFERENCIA,
    LinhaManifesto,
    ManifestoInvalido,
    carregar_manifesto,
)

COLUNAS = [
    "identifier", "titulo", "url", "bloco", "orgao", "esfera", "uf", "tipo",
    "status_fonte", "fonte_oficial", "vigencia_inicio", "vigencia_fim",
    "sucessora_ref", "validation_keyword", "demand_types", "observacao_curadoria",
]

VALIDADA = "Fonte oficial validada"


def _csv(tmp_path, linhas: list[dict]):
    caminho = tmp_path / "manifesto.csv"
    with caminho.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUNAS)
        w.writeheader()
        for linha in linhas:
            w.writerow({c: linha.get(c, "") for c in COLUNAS})
    return caminho


def _linha(**kw):
    base = {
        "identifier": "Decreto 8.539/2015",
        "titulo": "Processo administrativo eletrônico",
        "url": "https://www.planalto.gov.br/x.htm",
        "bloco": "06",
        "tipo": TIPO_NORMA,
        "status_fonte": VALIDADA,
        "validation_keyword": "8.539",
    }
    base.update(kw)
    return base


# --------------------------------------------------------------------------
# (d) validation_keyword — obrigatória no manifesto
# --------------------------------------------------------------------------

def test_linha_ingerivel_sem_keyword_derruba_o_manifesto(tmp_path):
    """Falha no CARREGAMENTO, antes de baixar qualquer coisa: manifesto
    quebrado não deve começar a puxar rede."""
    caminho = _csv(tmp_path, [_linha(validation_keyword="")])
    with pytest.raises(ManifestoInvalido, match="validation_keyword"):
        carregar_manifesto(caminho)


def test_referencia_operacional_nao_precisa_de_keyword(tmp_path):
    """Não é ingerida, então não há o que conferir."""
    caminho = _csv(tmp_path, [_linha(
        identifier="REF-IBAMA-FAQ", tipo=TIPO_REFERENCIA, validation_keyword=""
    )])
    linhas = carregar_manifesto(caminho)
    assert linhas[0].ingerivel is False


# --------------------------------------------------------------------------
# Contrato do manifesto
# --------------------------------------------------------------------------

def test_tipo_invalido_e_recusado(tmp_path):
    caminho = _csv(tmp_path, [_linha(tipo="jurisprudencia")])
    with pytest.raises(ManifestoInvalido, match="tipo"):
        carregar_manifesto(caminho)


def test_sucessora_sem_fim_de_vigencia_e_incoerente(tmp_path):
    """Se foi sucedida, houve fim de vigência. Deixar passar produziria norma
    com sucessora e sem rótulo histórico — apresentada como vigente."""
    caminho = _csv(tmp_path, [_linha(sucessora_ref="Decreto 11.080/2022")])
    with pytest.raises(ManifestoInvalido, match="vigencia_fim"):
        carregar_manifesto(caminho)


def test_coluna_obrigatoria_ausente(tmp_path):
    caminho = tmp_path / "m.csv"
    caminho.write_text("identifier,titulo\nx,y\n", encoding="utf-8")
    with pytest.raises(ManifestoInvalido, match="colunas obrigatórias"):
        carregar_manifesto(caminho)


# --------------------------------------------------------------------------
# O que entra e o que não entra no corpus vetorial
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "status",
    ["Não localizado nesta rodada", "Fonte não acessível (403)", "Em tramitação", ""],
)
def test_status_nao_validado_fica_fora(tmp_path, status):
    """O corpus não recebe norma que a própria curadoria não confirmou.
    Caso real: IN IBAMA 21/2023 e Portaria 15/2026, 403 no portal."""
    caminho = _csv(tmp_path, [_linha(status_fonte=status)])
    linha = carregar_manifesto(caminho)[0]
    assert linha.ingerivel is False
    assert "status da curadoria" in linha.motivo_nao_ingerivel


def test_referencia_operacional_fica_fora_com_motivo_proprio(tmp_path):
    """Página de serviço vetorizada competiria com lei na busca — a física do
    ADR-036. Fica no manifesto, fora do corpus."""
    caminho = _csv(tmp_path, [_linha(tipo=TIPO_REFERENCIA, validation_keyword="")])
    linha = carregar_manifesto(caminho)[0]
    assert linha.ingerivel is False
    assert "referência operacional" in linha.motivo_nao_ingerivel


def test_norma_validada_com_url_e_keyword_e_ingerivel(tmp_path):
    linha = carregar_manifesto(_csv(tmp_path, [_linha()]))[0]
    assert linha.ingerivel is True
    assert linha.motivo_nao_ingerivel is None


# --------------------------------------------------------------------------
# (f) vigência
# --------------------------------------------------------------------------

def test_norma_historica_carrega_janela_e_sucessora(tmp_path):
    """O caso real do Decreto 9.760/2019: a planilha o marca "validado" e o
    texto do Planalto diz "(Revogado pelo Decreto nº 11.080, de 2022)"."""
    caminho = _csv(tmp_path, [_linha(
        identifier="Decreto 9.760/2019",
        vigencia_inicio="2019-04-11",
        vigencia_fim="2022-05-24",
        sucessora_ref="Decreto 11.080/2022",
        validation_keyword="9.760",
    )])
    linha = carregar_manifesto(caminho)[0]
    assert linha.historica is True
    assert linha.vigencia_fim == date(2022, 5, 24)
    assert linha.sucessora_ref == "Decreto 11.080/2022"
    assert linha.ingerivel is True, "histórica ENTRA — marcada, não excluída"


# --------------------------------------------------------------------------
# Execução: (a) idempotência, (b) canário, (d) keyword no texto, (g) resiliência
# --------------------------------------------------------------------------

class _FakeSession:
    """Só o suficiente para o caminho de dry-run: consulta o 'corpus'."""

    def __init__(self, existentes=None):
        self._existentes = existentes or {}
        # `executar_manifesto` chama `processar_linha` direto, sem passar pelo
        # `_preparar` — o fake precisa nascer utilizável.
        self._achado = None

    def query(self, _modelo):
        return self

    def filter(self, *_a, **_k):
        return self

    def order_by(self, *_a, **_k):
        return self

    def first(self):
        return self._achado

    def _preparar(self, identifier):
        self._achado = self._existentes.get(identifier)
        return self


class _DocExistente:
    def __init__(self, content_hash, doc_id=7):
        self.content_hash = content_hash
        self.status = "indexed"
        self.id = doc_id


def _stub_download(monkeypatch, texto: str):
    import scripts.ingest_legislation as il

    monkeypatch.setattr(il, "load_from_url", lambda url: ("html", texto))


def test_keyword_ausente_no_texto_reprova_a_linha(monkeypatch):
    """A CF real: a URL da planilha devolve texto que PARA no art. 24 §4º, sem
    o art. 225. Baixa, tem tamanho, parece certa — e não é."""
    import scripts.ingest_manifesto as im

    _stub_download(monkeypatch, "CONSTITUIÇÃO FEDERAL " + ("Art. 1º ... " * 200))
    linha = LinhaManifesto(
        identifier="Constituição Federal de 1988", titulo="CF",
        url="https://planalto.gov.br/cf.htm", bloco="06",
        status_fonte=VALIDADA, validation_keyword="art. 225",
    )
    res = im.processar_linha(_FakeSession()._preparar(linha.identifier), linha, executar=False)
    assert res.acao == "falhou"
    assert "validation_keyword" in res.motivo


def test_canario_de_mojibake_reprova(monkeypatch):
    import scripts.ingest_manifesto as im

    _stub_download(monkeypatch, "Art. 3� O �rg�o aplicar� as san��es " * 40)
    linha = LinhaManifesto(
        identifier="Decreto X", titulo="X", url="https://planalto.gov.br/x.htm",
        bloco="06", status_fonte=VALIDADA, validation_keyword="Art. 3",
    )
    res = im.processar_linha(_FakeSession()._preparar(linha.identifier), linha, executar=False)
    assert res.acao == "falhou"
    assert "U+FFFD" in res.motivo


def test_download_que_explode_nao_derruba_a_linha(monkeypatch):
    """(g) — o 403 do portal do IBAMA não pode abortar o lote."""
    import scripts.ingest_legislation as il
    import scripts.ingest_manifesto as im

    def _explode(url):
        raise RuntimeError("403 Forbidden")

    monkeypatch.setattr(il, "load_from_url", _explode)
    linha = LinhaManifesto(
        identifier="IN IBAMA 21/2023", titulo="X", url="https://ibama.gov.br/x",
        bloco="06", status_fonte=VALIDADA, validation_keyword="21",
    )
    res = im.processar_linha(_FakeSession()._preparar(linha.identifier), linha, executar=False)
    assert res.acao == "falhou"
    assert "403" in res.motivo


def test_texto_curto_demais_e_pagina_de_erro(monkeypatch):
    import scripts.ingest_manifesto as im

    _stub_download(monkeypatch, "Página não encontrada")
    linha = LinhaManifesto(
        identifier="X", titulo="X", url="https://planalto.gov.br/x.htm",
        bloco="06", status_fonte=VALIDADA, validation_keyword="X",
    )
    res = im.processar_linha(_FakeSession()._preparar(linha.identifier), linha, executar=False)
    assert res.acao == "falhou"
    assert "curto" in res.motivo


def test_idempotencia_hash_identico_vira_skip(monkeypatch):
    """(a) — 8 das 26 linhas do núcleo 06 caíram aqui, sobre dado real."""
    import hashlib

    import scripts.ingest_manifesto as im
    from scripts.ingest_legislation import sanitize_text

    texto_bruto = "Art. 1º Esta lei estabelece o que 9.605 determina. " * 40
    _stub_download(monkeypatch, texto_bruto)
    # O hash é do texto JÁ SANEADO — é assim que o ingestor o calcula.
    hash_esperado = hashlib.sha256(
        sanitize_text(texto_bruto).encode("utf-8")
    ).hexdigest()

    linha = LinhaManifesto(
        identifier="Lei 9.605/1998", titulo="X", url="https://planalto.gov.br/x.htm",
        bloco="06", status_fonte=VALIDADA, validation_keyword="9.605",
    )
    sessao = _FakeSession({"Lei 9.605/1998": _DocExistente(hash_esperado)})
    res = im.processar_linha(sessao._preparar(linha.identifier), linha, executar=False)
    assert res.acao == "skip"
    assert "idêntico" in res.motivo
    assert res.doc_id == 7
    assert res.chunks == 0, "skip não gasta embedding"


def test_conteudo_mudou_nao_e_skip(monkeypatch):
    """Norma alterada na origem tem de ser reingerida, não pulada."""
    import scripts.ingest_manifesto as im

    _stub_download(monkeypatch, "Art. 1º texto NOVO da 9.605 aqui. " * 40)
    linha = LinhaManifesto(
        identifier="Lei 9.605/1998", titulo="X", url="https://planalto.gov.br/x.htm",
        bloco="06", status_fonte=VALIDADA, validation_keyword="9.605",
    )
    sessao = _FakeSession({"Lei 9.605/1998": _DocExistente("hash-antigo-diferente")})
    res = im.processar_linha(sessao._preparar(linha.identifier), linha, executar=False)
    assert res.acao == "ok"
    assert res.chunks > 0


def test_linha_nao_ingerivel_nem_baixa(monkeypatch):
    """Referência operacional não gasta rede."""
    import scripts.ingest_legislation as il
    import scripts.ingest_manifesto as im

    def _nao_deveria(url):
        raise AssertionError("não deveria baixar linha não-ingerível")

    monkeypatch.setattr(il, "load_from_url", _nao_deveria)
    linha = LinhaManifesto(
        identifier="REF-X", titulo="X", url="https://gov.br/servicos/x",
        bloco="06", tipo=TIPO_REFERENCIA, status_fonte=VALIDADA,
    )
    res = im.processar_linha(_FakeSession()._preparar(linha.identifier), linha, executar=False)
    assert res.acao == "ignorado"


# --------------------------------------------------------------------------
# (g) o lote inteiro
# --------------------------------------------------------------------------

def test_lote_segue_apos_falha_e_soma_o_custo(monkeypatch):
    import scripts.ingest_legislation as il
    import scripts.ingest_manifesto as im

    def _download(url):
        if "quebrada" in url:
            raise RuntimeError("403 Forbidden")
        return ("html", "Art. 1º Norma 8.539 de teste com texto suficiente. " * 40)

    monkeypatch.setattr(il, "load_from_url", _download)
    linhas = [
        LinhaManifesto(identifier="A", titulo="A", url="https://planalto.gov.br/quebrada.htm",
                       bloco="06", status_fonte=VALIDADA, validation_keyword="8.539"),
        LinhaManifesto(identifier="B", titulo="B", url="https://planalto.gov.br/ok.htm",
                       bloco="06", status_fonte=VALIDADA, validation_keyword="8.539"),
        LinhaManifesto(identifier="REF", titulo="R", url="https://gov.br/servicos/x",
                       bloco="06", tipo=TIPO_REFERENCIA, status_fonte=VALIDADA),
    ]

    class _S(_FakeSession):
        def _preparar(self, _i):
            self._achado = None
            return self

    sumario = im.executar_manifesto(_S(), linhas, executar=False)
    assert [r.acao for r in sumario.resultados] == ["falhou", "ok", "ignorado"]
    assert sumario.chunk_tokens > 0
    assert sumario.custo_usd > 0
