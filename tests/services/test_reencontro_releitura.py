"""Dívida #281 — quando uma observação anterior foi reencontrada na releitura.

A regra decide o que é superado automaticamente e o que fica para o consultor.
Errar para um lado perde evidência (superar o que não foi reencontrado); errar
para o outro inunda o consultor (marcar como não reencontrado o mesmo fato com
outro rótulo). Estes testes travam os dois lados com casos tirados da medição.
"""

from types import SimpleNamespace

from app.services.entrada_semantica import separar_por_reencontro


def _obs(tipo, predicado, inicio, fim, valor=None, versao=1, literal="x", **normalizado):
    return SimpleNamespace(
        source_record={"tipo_entrada": tipo},
        content={"attributes": {"predicate": predicado, "position": f"[{inicio},{fim})",
                                "documento_versao_id": versao, "literal": literal,
                                "normalized": {"valor": valor, **normalizado}}})


def test_mesmo_predicado_e_trecho_sobreposto_e_reencontrada():
    velha = _obs("observacao", "area_imovel", 100, 140, "926,3654")
    nova = _obs("observacao", "area_imovel", 95, 150, "926,3654")
    reencontradas, nao = separar_por_reencontro([velha], [nova])
    assert reencontradas == [(velha, nova, False)] and nao == []


def test_rotulo_trocado_com_o_mesmo_valor_e_reencontrada():
    """Metade da variância medida é só rótulo: não pode ir para o consultor."""
    velha = _obs("observacao", "area_imovel", 100, 140, "926,3654")
    nova = _obs("observacao", "area_total_ha", 100, 140, "926, 3654")
    assert separar_por_reencontro([velha], [nova])[1] == []


def test_fato_diferente_no_mesmo_trecho_nao_e_reencontrado():
    """Área e município na mesma frase: casar só pelo trecho perderia um dos dois."""
    velha = _obs("observacao", "municipio", 100, 140, "Alto Paraíso de Goiás")
    nova = _obs("observacao", "area_imovel", 100, 140, "926,3654")
    reencontradas, nao = separar_por_reencontro([velha], [nova])
    assert reencontradas == [] and nao == [velha]


def test_mesmo_fato_com_valor_corrigido_e_reencontrado_e_diz_que_mudou():
    velha = _obs("observacao", "area_imovel", 100, 140, "926,36")
    nova = _obs("observacao", "area_imovel", 100, 140, "926,3654")
    [(v, n, diferente)] = separar_por_reencontro([velha], [nova])[0]
    assert diferente is True


def test_parte_com_identificador_diferente_nao_e_a_mesma():
    velha = _obs("parte", "parte", 10, 60, identificador="29.091.958/0001-17")
    nova = _obs("parte", "parte", 10, 60, identificador="01.023.570/0001-60")
    assert separar_por_reencontro([velha], [nova])[1] == [velha]


def test_sem_sobreposicao_nao_e_reencontrada():
    velha = _obs("observacao", "area_imovel", 100, 140, "926,3654")
    nova = _obs("observacao", "area_imovel", 500, 540, "926,3654")
    assert separar_por_reencontro([velha], [nova])[1] == [velha]


def test_versao_nova_do_texto_compara_pelo_literal():
    velha = _obs("observacao", "area_imovel", 100, 140, "926,3654", versao=1, literal="área de 926,3654 ha")
    nova = _obs("observacao", "area_imovel", 300, 340, "926,3654", versao=2, literal="área de  926,3654 ha")
    assert separar_por_reencontro([velha], [nova])[1] == []
