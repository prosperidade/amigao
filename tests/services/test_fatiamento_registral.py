"""Fatiamento da matrícula por ato registral (ADR-077, dívida #271).

Cada teste trava uma regra do ADR. O texto imita a certidão real: cabeçalho,
abertura com memorial, e atos separados por linha de traços.
"""

import pytest

from app.services.fatiamento_registral import fatiar_por_ato, localizar_atos

SEP = "-" * 40 + "\n"


def _certidao(abertura: str, atos: list[tuple[str, str]], encerramento: str = "") -> str:
    texto = abertura
    for cabecalho, corpo in atos:
        texto += SEP + cabecalho + corpo
    return texto + encerramento


ABERTURA = "CERTIFICA, que a presente é reprodução autêntica da Matrícula n° 3181.\nIMÓVEL: gleba.\n"


def _ladrilha(texto, fatias):
    assert fatias[0].inicio == 0
    assert fatias[-1].fim == len(texto)
    assert all(a.fim == b.inicio for a, b in zip(fatias, fatias[1:], strict=False))


def test_ato_comeca_no_cabecalho_depois_dos_tracos():
    texto = _certidao(ABERTURA, [
        ("AV-01 - MAT. 3.181 - DO GEORREFERENCIAMENTO", " averba-se.\n"),
        ("R.06- MAT. 3.181 - REGISTRO DE HIPOTECA", " registra-se.\n"),
        ("AV.05 Mat. 3.181- DO ARRENDAMENTO", " averba-se.\n"),
    ])
    rotulos = [r for r, _, _ in localizar_atos(texto)]
    assert rotulos == ["abertura", "AV-01", "R-06", "AV-05"]


def test_mencao_interna_a_ato_nao_abre_ato():
    texto = _certidao(ABERTURA, [
        ("R-10 MAT. 3.181 - REGISTRO DE CÉDULA", " dívida registrada no R-10,\nobjeto do R-12 acima.\n"),
        ("AV.11 MAT. 3.181 - ADITIVO", " aditivo ao R-10.\n"),
    ])
    assert [r for r, _, _ in localizar_atos(texto)] == ["abertura", "R-10", "AV-11"]


def test_atos_pequenos_dividem_chamada_ate_o_maximo_e_nunca_partem():
    corpo = "x" * 300 + "\n"
    texto = _certidao(ABERTURA, [(f"R-{i:02d} MAT. 3.181 - ATO", corpo) for i in range(1, 7)])
    fatias = fatiar_por_ato(texto, max_chars=1_000)
    _ladrilha(texto, fatias)
    assert all(f.tamanho <= 1_000 for f in fatias)
    atos = [a for f in fatias for a in f.atos]
    assert atos == ["abertura"] + [f"R-{i:02d}" for i in range(1, 7)]  # cada ato em uma fatia só
    assert any(len(f.atos) > 1 for f in fatias)  # houve agrupamento


def test_ato_maior_que_o_maximo_corta_em_fronteira_estrutural_sem_sobreposicao():
    memorial = "".join(f"vértice V{i}, de coordenadas N={i}m e E={i}m;\n" for i in range(200))
    texto = _certidao(ABERTURA + memorial, [("R-01 MAT. 3.181 - COMPRA E VENDA", " vende.\n")])
    fatias = fatiar_por_ato(texto, max_chars=1_000)
    _ladrilha(texto, fatias)
    aberturas = [f for f in fatias if f.atos == ("abertura",)]
    assert len(aberturas) > 1
    assert {f.partes for f in aberturas} == {len(aberturas)}
    for f in aberturas[:-1]:
        assert f.tamanho <= 1_000
        assert texto[f.fim - 2:f.fim] == ";\n"  # cortou depois de uma frase de vértice


def test_ato_grande_sem_fronteira_forte_corta_em_fim_de_linha():
    linhas = "".join(f"linha {i} sem pontuação final\n" for i in range(200))
    texto = _certidao(ABERTURA + linhas, [("R-01 MAT. 3.181 - ATO", " fim.\n")])
    fatias = fatiar_por_ato(texto, max_chars=500)
    _ladrilha(texto, fatias)
    for f in fatias:
        if f.partes > 1 and f.parte < f.partes:
            assert texto[f.fim - 1] == "\n"


def test_texto_sem_ato_reconhecivel_devolve_none_para_o_fatiamento_por_tamanho():
    assert fatiar_por_ato("Escritura pública de compra e venda, sem registro.", max_chars=1_000) is None


def test_maximo_invalido_recusa():
    with pytest.raises(ValueError):
        fatiar_por_ato("x", max_chars=0)


def test_rotulo_diz_ato_e_parte():
    memorial = "".join(f"vértice V{i};\n" for i in range(300))
    texto = _certidao(ABERTURA + memorial, [("AV-01 MAT. 3.181 - ATO", " a.\n")])
    fatias = fatiar_por_ato(texto, max_chars=800)
    assert fatias[0].rotulo.startswith("abertura#1/")
    assert fatias[-1].rotulo.startswith("AV-01[")


def test_abertura_tem_maximo_proprio():
    """O memorial gera ~0,2 token por caractere; o ato, 0,9 a 1,6 — máximos diferentes."""
    memorial = "".join(f"vértice V{i}, de coordenadas N={i}m e E={i}m;\n" for i in range(200))
    corpo = "y" * 900 + "\n"
    texto = _certidao(ABERTURA + memorial, [(f"R-{i:02d} MAT. 3.181 - ATO", corpo) for i in range(1, 5)])
    fatias = fatiar_por_ato(texto, max_chars=1_000, max_chars_abertura=4_000)
    aberturas = [f for f in fatias if f.atos == ("abertura",)]
    atos = [f for f in fatias if f.atos != ("abertura",)]
    assert all(f.tamanho <= 4_000 for f in aberturas) and any(f.tamanho > 1_000 for f in aberturas)
    assert all(f.tamanho <= 1_000 for f in atos)
    _ladrilha(texto, fatias)
