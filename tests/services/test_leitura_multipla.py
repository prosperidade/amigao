"""ADR-079 — a rodada publica a união das leituras, sem o mesmo fato em dobro."""
from app.schemas.entrada_semantica import EntradaExtraida
from app.services.entrada_semantica import conteudo_do_item
from app.services.leitura_multipla import agrupar, mesmo_fato, unir_leituras


def _obs(predicado, valor, inicio, fim, sujeito=None):
    return {"predicado": predicado, "valor": valor, "trecho": "x" * (fim - inicio),
            "posicao_inicio": inicio, "posicao_fim": fim, "sujeito": sujeito}


def _parte(chave, nome, inicio, fim, cpf=None):
    return {"chave": chave, "nome": nome, "natureza": "pf", "identificador": cpf,
            "tipo_identificador": "cpf" if cpf else None, "trecho": "x" * (fim - inicio),
            "posicao_inicio": inicio, "posicao_fim": fim}


def _part(parte_chave, papel, inicio, fim):
    return {"parte_chave": parte_chave, "papel": papel, "trecho": "x" * (fim - inicio),
            "posicao_inicio": inicio, "posicao_fim": fim}


def test_mesma_regra_do_adr_078():
    area = _obs("area_total_ha", "10,5", 0, 20)
    assert mesmo_fato("observacoes", area, _obs("area_imovel", "10, 5", 5, 25))  # rótulo trocado, mesmo valor
    assert not mesmo_fato("observacoes", area, _obs("municipio", "Rio Verde", 5, 25))  # outro fato, mesma frase
    assert not mesmo_fato("observacoes", area, _obs("area_total_ha", "10,5", 20, 40))  # trecho não sobrepõe
    assert not mesmo_fato("partes", _parte("a", "Ana", 0, 9, "111"), _parte("b", "Ana", 0, 9, "222"))


def test_dois_itens_da_mesma_leitura_nunca_se_fundem():
    grupos = agrupar("observacoes", [[_obs("area", "1", 0, 10), _obs("area", "1", 5, 15)], [_obs("area", "1", 0, 15)]])
    assert sorted(len(g) for g in grupos) == [1, 2]


def test_uniao_sem_dobro_com_apoio_por_item():
    l1 = EntradaExtraida(observacoes=[_obs("area_total_ha", "10", 0, 20), _obs("municipio", "Jataí", 30, 40)])
    l2 = EntradaExtraida(observacoes=[_obs("area_imovel", "10", 2, 18)])
    l3 = EntradaExtraida(observacoes=[_obs("area_total_ha", "10", 0, 20), _obs("car", "GO-1", 50, 60)])
    entrada, rodada = unir_leituras([l1, l2, l3])
    assert [o.predicado for o in entrada.observacoes] == ["area_total_ha", "municipio", "car"]
    apoio = {o.predicado: o._leituras_na_rodada for o in entrada.observacoes}
    assert apoio == {"area_total_ha": {"viram": 3, "de": 3}, "municipio": {"viram": 1, "de": 3},
                     "car": {"viram": 1, "de": 3}}
    assert rodada["itens_por_leitura"] == [2, 1, 2]
    assert (rodada["uniao"], rodada["em_todas"], rodada["so_em_uma"]) == (3, 1, 2)
    # O apoio vai para o conteúdo gravado; não é valor lido.
    assert conteudo_do_item(entrada.observacoes[0])["leituras_na_rodada"] == {"viram": 3, "de": 3}


def test_parte_fundida_leva_as_referencias_para_a_chave_do_representante():
    l1 = EntradaExtraida(partes=[_parte("f0:elodi", "ELODI", 0, 10, "123")],
                         participacoes=[_part("f0:elodi", "adquirente", 0, 30)])
    l2 = EntradaExtraida(partes=[_parte("f0:p1", "ELODI", 0, 10, "123"), _parte("f0:p2", "JOÃO", 40, 50, "999")],
                         participacoes=[_part("f0:p2", "transmitente", 40, 60)],
                         observacoes=[_obs("estado_civil", "casada", 0, 25, sujeito="f0:p1")])
    entrada, rodada = unir_leituras([l1, l2])
    assert [p.chave for p in entrada.partes] == ["f0:elodi", "l1:f0:p2"]
    assert {(p.parte_chave, p.papel.value) for p in entrada.participacoes} == {
        ("f0:elodi", "adquirente"), ("l1:f0:p2", "transmitente")}
    assert entrada.observacoes[0].sujeito == "f0:elodi"
    assert rodada["em_todas"] == 1  # a parte ELODI


def test_valor_divergente_publica_a_leitura_mais_antiga_e_registra():
    l1 = EntradaExtraida(observacoes=[_obs("area_total_ha", "10,5", 0, 20)])
    l2 = EntradaExtraida(observacoes=[_obs("area_total_ha", "105", 0, 20)])
    entrada, rodada = unir_leituras([l1, l2])
    assert [o.valor for o in entrada.observacoes] == ["10,5"]
    [divergente] = rodada["valor_divergente"]
    assert divergente["publicado"]["leitura"] == 1
    assert divergente["outros"] == [{"leitura": 2, "valor": {"predicado": "area_total_ha", "valor": "105",
                                                            "unidade": None, "ato_rotulo": None}}]


def test_uma_leitura_e_a_propria_leitura():
    l1 = EntradaExtraida(observacoes=[_obs("area", "1", 0, 10)])
    entrada, rodada = unir_leituras([l1])
    assert entrada is l1 and rodada is None
