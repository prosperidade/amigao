"""Saneamento do corpus — proveniência (#97) e invisíveis (#96).

A auditoria de 31/07 mediu que 97,3% do texto do corpus não tinha origem
rastreável declarada, e que 708 chunks carregavam caracteres invisíveis que
quebram busca literal. Estes testes travam as duas regras.
"""

from datetime import date

import pytest
from scripts.sanear_corpus import normalizar_invisiveis

from app.services.proveniencia import (
    CONFERIDA_EM,
    DESCONHECIDA,
    classificar_fonte,
)

# Por CODEPOINT, nunca colados como literal: a primeira versão deste arquivo
# tinha `NBSP = " "` e o caractere virou espaço comum no caminho — o teste do
# espaço invisível foi derrubado por um espaço invisível.
NBSP = "\u00a0"
ZWSP = "\u200b"
BOM = "\ufeff"


# --------------------------------------------------------------------------
# #97 — o backfill não marca oficial o que não é
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url",
    [
        "https://www.planalto.gov.br/ccivil_03/leis/l9605.htm",
        "https://www.in.gov.br/web/dou/-/instrucao-normativa-n-19",
        "https://conama.mma.gov.br/?option=com_sisconama",
        "https://sudema.pb.gov.br/legislacao/resolucao.pdf",
    ],
)
def test_dominio_oficial_e_oficial_mas_nao_conferido(url):
    """URL de domínio oficial prova a origem — mas ninguém olhou, então não há
    data de conferência. A distinção importa: é o que separa "o robô deduziu"
    de "uma pessoa afirmou"."""
    p = classificar_fonte(url=url)
    assert p.oficial is True
    assert p.conferida_em is None
    assert "oficial" in p.origem


def test_agregador_nao_vira_oficial_so_por_ter_link():
    """O caso real: a IN IBAMA 10/2012 veio do LegisWeb porque o portal do IBAMA
    responde 403. Ter URL não faz a fonte oficial."""
    p = classificar_fonte(url="https://www.legisweb.com.br/legislacao/?id=277984")
    assert p.oficial is False
    assert "não-oficial" in p.origem
    assert "legisweb" in p.origem.lower()


def test_arquivo_de_disco_e_oficial_por_conferencia_humana_com_data():
    """As pastas GO/MT/MS/AC vieram da Isis, de fontes oficiais estaduais
    (confirmado em 01/08/2026). Oficial — e com data, porque foi uma PESSOA que
    afirmou, não um domínio."""
    p = classificar_fonte(file_path="/app/legislacao_estadual/MT/01_Nucleo.pdf")
    assert p.oficial is True
    assert p.conferida_em == CONFERIDA_EM == date(2026, 8, 1)
    assert "Isis" in p.origem
    assert "01_Nucleo.pdf" in p.origem, "o arquivo real tem de aparecer"


def test_sem_url_e_sem_arquivo_declara_desconhecida_nunca_vazio():
    p = classificar_fonte()
    assert p.oficial is False
    assert p.origem == DESCONHECIDA
    assert p.origem, "origem jamais fica em branco — silêncio vira 'parece ok'"


def test_url_vence_arquivo_quando_os_dois_existem():
    p = classificar_fonte(
        url="https://www.planalto.gov.br/x.htm", file_path="/disco/x.pdf"
    )
    assert p.oficial is True
    assert p.conferida_em is None


# --------------------------------------------------------------------------
# #96 — normalização dos invisíveis
# --------------------------------------------------------------------------

def test_nbsp_vira_espaco_comum_e_o_artigo_fica_pesquisavel():
    """O sintoma medido: `chunk_text LIKE '%Art. 18.%'` devolvia ZERO linhas
    para um artigo que estava no corpus."""
    sujo = f"Art.{NBSP}18.{NBSP}{NBSP}O descumprimento total ou parcial de embargo"
    limpo = normalizar_invisiveis(sujo)
    assert "Art. 18." in limpo
    assert NBSP not in limpo


def test_zwsp_e_bom_somem_sem_deixar_espaco():
    limpo = normalizar_invisiveis(f"Decreto{ZWSP} 6.514{BOM}/2008")
    assert limpo == "Decreto 6.514/2008"


def test_normalizacao_e_idempotente():
    """Rodar o saneamento duas vezes não pode mudar o resultado — senão o
    `content_hash` recalculado no segundo passe difere do primeiro."""
    sujo = f"Art.{NBSP}18{ZWSP} do Decreto{NBSP}6.514{BOM}"
    uma = normalizar_invisiveis(sujo)
    assert normalizar_invisiveis(uma) == uma


def test_texto_limpo_passa_intacto():
    limpo = "Art. 18. O descumprimento total ou parcial de embargo"
    assert normalizar_invisiveis(limpo) == limpo


def test_none_passa_reto():
    assert normalizar_invisiveis(None) is None
