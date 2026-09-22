"""As sondas são versionadas e têm forma fixa (ADR-075 §9) — roda em todo PR, sem banco.

A QUALIDADE (recall@5, controle negativo, groundedness) roda em
`scripts/sondas_recuperacao.py` sobre o corpus de dev/homologação, em PR que toque
recuperação/corpus/chunking/embedding e na rodada noturna (decisão 4).
"""

from app.services.zona_normativa import sondas


def test_sondas_tem_forma_valida():
    assert sondas.validar_formato(sondas.carregar_sondas()) == []


def test_toda_pergunta_positiva_tem_vetor_em_cache():
    lista = sondas.carregar_sondas()
    vetores = sondas.carregar_vetores()
    modelos = {k.split(":", 1)[0] for k in vetores}
    assert len(modelos) == 1, "cache com mais de um espaço vetorial"
    modelo = modelos.pop()
    faltam = [s["id"] for s in lista if s.get("pergunta") and sondas.chave_vetor(modelo, s["pergunta"]) not in vetores]
    assert faltam == []
