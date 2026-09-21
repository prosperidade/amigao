import os

# Dívida #255: o LiteLLM baixa o mapa de modelos no import e, se o download falha,
# os modelos novos ficam sem provider e sem preço. Mapa embutido sempre; os modelos
# da casa entram por app/core/litellm_tabela.py. Precisa vir antes de qualquer
# import do litellm, por isso mora no pacote raiz.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
