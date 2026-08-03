"""Classificador norma × referência operacional — a URL manda.

O extrator do manifesto (ADR-038) decide, por linha da planilha, se aquilo é
**norma** (entra no corpus vetorial) ou **referência operacional** (fica
versionada e exibível, fora da busca). Página de serviço vetorizada competiria
com lei por similaridade — a física do ADR-036 — e viraria fonte de peça
assinada.

A ordem de precedência foi errada DUAS vezes antes de acertar, no bloco 2, e
cada erro tinha um custo diferente:

1. Só padrões de URL (calibrado no núcleo 06): não reconhecia SIGEF, malhas do
   IBGE, CNUC, WebAmbiente — portais entravam como norma.
2. Tipo da curadoria vencendo a URL: "Portaria / serviço" virava referência e
   a **Portaria IBAMA 15/2026 sairia do corpus caladamente**.
3. Certo: a **URL manda** (é ela que será baixada), a espécie normativa no tipo
   desempata, o tipo de referência decide o resto, e a dúvida vira norma — o
   dry-run e a `validation_keyword` pegam o engano depois.
"""

import pytest

from scripts.extrair_manifesto import _classificar

NORMA = "norma"
REF = "referencia_operacional"


# --------------------------------------------------------------------------
# 1. A URL manda — é ela que vai ser baixada
# --------------------------------------------------------------------------

def test_url_de_portal_vence_tipo_que_nomeia_norma():
    """O caso real do núcleo 06: a linha é "Decreto federal / sistema" e a URL é
    a consulta de áreas embargadas. Baixaria a PÁGINA DE CONSULTA, não o
    decreto — então é referência, por mais que o tipo diga "decreto"."""
    assert _classificar(
        "https://www.gov.br/ibama/pt-br/servicos/consultas/autuacoes-e-embargos/areas-embargadas",
        "Decreto federal / sistema",
    ) == REF


@pytest.mark.parametrize(
    "url",
    [
        "https://www.gov.br/ibama/pt-br/acesso-a-informacao/perguntas-frequentes/auto-de-infracao-ambiental",
        "https://www.gov.br/pt-br/servicos/obter-certidao-de-embargo-ambiental",
        "https://dadosabertos.ibama.gov.br/dados/SIFISC/termo_embargo/termo_embargo.html",
        "https://servicos.ibama.gov.br/ctf/publico/areasembargadas/",
    ],
)
def test_padroes_de_url_de_servico(url):
    assert _classificar(url, "qualquer coisa") == REF


# --------------------------------------------------------------------------
# 2. Espécie normativa no tipo desempata quando a URL não denuncia portal
# --------------------------------------------------------------------------

def test_portaria_com_pagina_de_servico_continua_portaria():
    """A regressão que a segunda versão causou: a Portaria IBAMA 15/2026 tem
    tipo "Portaria / serviço" e URL de legislação. É NORMA."""
    assert _classificar(
        "https://www.ibama.gov.br/component/legislacao/?legislacao=139558&view=legislacao",
        "Portaria / serviço",
    ) == NORMA


@pytest.mark.parametrize(
    "tipo",
    [
        "Lei federal",
        "Decreto federal",
        "Instrução normativa federal / sistema",
        "Resolução CONAMA",
        "Constituição Federal",
        "Orientação jurídica normativa",
        "Lei complementar",
    ],
)
def test_especie_normativa_nomeada_e_norma(tipo):
    assert _classificar("https://www.planalto.gov.br/ccivil_03/leis/l9605.htm", tipo) == NORMA


# --------------------------------------------------------------------------
# 3. Tipo de referência decide o que sobra
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "tipo",
    [
        "Sistema / serviço oficial",
        "Base geoespacial oficial",
        "Base cartográfica oficial",
        "Portal oficial / base temática",
        "Sistema federal / dados abertos",
        "Plano federal / documento técnico oficial",
    ],
)
def test_tipos_de_sistema_e_base_sao_referencia(tipo):
    """Os do bloco 2 que os padrões de URL do núcleo 06 não pegavam: SIGEF,
    acervo do INCRA, malhas do IBGE, CNUC, WebAmbiente."""
    assert _classificar("https://sigef.incra.gov.br/", tipo) == REF


# --------------------------------------------------------------------------
# 4. Na dúvida, norma
# --------------------------------------------------------------------------

def test_sem_sinal_nenhum_assume_norma():
    """Errar para o lado de CONFERIR é mais barato que errar para o lado de
    excluir em silêncio: o dry-run e a validation_keyword pegam o engano."""
    assert _classificar("https://exemplo.gov.br/algum-documento.pdf", "") == NORMA
    assert _classificar("", "") == NORMA


def test_nao_confunde_maiuscula_e_minuscula():
    assert _classificar("https://x.gov.br/a.htm", "LEI FEDERAL") == NORMA
    assert _classificar("https://x.gov.br/a.htm", "sistema oficial") == REF
