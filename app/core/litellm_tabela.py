"""Tabela local de modelos do LiteLLM (dívidas #255 e #256).

O LiteLLM baixa o mapa de modelos do GitHub no import, com timeout de 5 s, e se o
download falha usa o mapa embutido na versão instalada. O embutido não conhece
os modelos novos: em 21/09/2026 os jobs dev 161 e 162 falharam com "LLM Provider
NOT provided" para o gpt-5.6-luna, sem chamar o modelo. Sem preço, o gateway
gravava custo zero e o teto por job não atuava.

O sistema não depende mais de rede no boot: ``app/__init__.py`` força o mapa
embutido e ``carregar()`` registra por cima os modelos da casa, com as entradas
fixadas em ``litellm_modelos.json``. Modelo sem preço falha antes da chamada.
"""

import json
from pathlib import Path

TABELA = Path(__file__).with_name("litellm_modelos.json")


def modelos() -> dict:
    return json.loads(TABELA.read_text(encoding="utf-8"))["modelos"]


def carregar():
    """O módulo litellm com a tabela local registrada (uma vez por módulo carregado)."""
    import litellm  # noqa: PLC0415

    if getattr(litellm, "_tabela_regente", None) is not True:
        litellm.register_model(modelos())
        litellm._tabela_regente = True
    return litellm


def exigir_preco(litellm, model: str) -> None:
    """Preço desconhecido não é zero: falha antes de gastar (dívida #256)."""
    try:
        info = litellm.get_model_info(model)
    except Exception:
        info = {}
    if info.get("input_cost_per_token") is None or info.get("output_cost_per_token") is None:
        raise ModeloSemPreco(model)


class ModeloSemPreco(Exception):
    def __init__(self, model: str):
        super().__init__(f"Modelo sem preço na tabela local: {model}. "
                         "Acrescente a entrada em app/core/litellm_modelos.json antes de usá-lo.")
        self.model = model
