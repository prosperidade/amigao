"""Uma etapa, uma cadeia (dívida #66 — validação Isis 30/07).

Existiam DOIS mapas macroetapa→chain escritos à mão:

* ``app/models/macroetapa.py:MACROETAPA_AGENT_CHAIN`` — lido pelo botão
  "Rodar agentes da etapa";
* ``app/agents/orchestrator.py:MACROETAPA_CHAINS`` — lido pelo orquestrador.

Eles divergiam em ``caminho_regulatorio``: ``analise_regulatoria``
(``["legislacao"]``) contra ``enquadramento_regulatorio``
(``["extrator", "legislacao"]``). Mesma etapa, dois comportamentos, conforme a
porta pela qual o consultor entrasse — o pano de fundo do relato "o botão da
etapa falhou e a seção de agentes funcionou".
"""

from __future__ import annotations

from app.agents.orchestrator import CHAINS, MACROETAPA_CHAINS
from app.models.macroetapa import MACROETAPA_AGENT_CHAIN, Macroetapa


def test_os_dois_mapas_dizem_a_mesma_coisa():
    derivado = {e.value: c for e, c in MACROETAPA_AGENT_CHAIN.items()}
    assert MACROETAPA_CHAINS == derivado


def test_toda_macroetapa_esta_no_mapa():
    """Etapa nova sem entrada aqui viraria botão que não faz nada."""
    assert set(MACROETAPA_AGENT_CHAIN) == set(Macroetapa)


def test_toda_chain_apontada_existe_no_registry():
    """O que destrava a #66: nome de chain inexistente = botão morto."""
    for etapa, chain in MACROETAPA_AGENT_CHAIN.items():
        if chain is None:
            continue  # etapa manual, por projeto (coleta / contrato)
        assert chain in CHAINS, f"{etapa.value} aponta para chain inexistente '{chain}'"


def test_caminho_regulatorio_nao_diverge_mais():
    """A divergência concreta que a #66 nomeou."""
    assert (
        MACROETAPA_CHAINS["caminho_regulatorio"]
        == MACROETAPA_AGENT_CHAIN[Macroetapa.caminho_regulatorio]
    )
