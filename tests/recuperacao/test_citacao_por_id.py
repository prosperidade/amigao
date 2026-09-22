"""Citação por ID verificada antes de emitir (ADR-075 §8) — pertencimento, não semelhança."""

from __future__ import annotations

from datetime import date

from tests.recuperacao import catalogo_sintetico as cs

from app.services.zona_normativa.citacao import Afirmacao, Citacao, carregar_envelope, mencoes, verificar

HOJE = date(2026, 9, 22)


def _cenario(db, status="validado", **kw):
    f = cs.fonte(db, "decreto|br||6514|2008", rotulo="Decreto 6.514/2008")
    v = cs.versao(db, f, status=status, **kw)
    d = cs.dispositivo(db, v, "18", rotulo_fonte="Decreto 6.514/2008")
    cs.dispositivo(db, v, "18", rotulo_fonte="Decreto 6.514/2008", paragrafo="1", parent_id=d.id)
    return v, carregar_envelope(db, {v.id})


def _tipos(ver):
    return [f.tipo for f in ver.falhas]


def test_citacao_valida_emite(db_session):
    v, env = _cenario(db_session)
    a = Afirmacao("O descumprimento de embargo atrai o art. 18 do Decreto 6.514/2008.",
                  [Citacao(v.id, "art. 18")])
    ver = verificar(db_session, [a], env, destino="peca", data_referencia=HOJE)
    assert ver.emitir, ver.falhas


def test_paragrafo_existente_e_inexistente(db_session):
    v, env = _cenario(db_session)
    ok = verificar(db_session, [Afirmacao("x", [Citacao(v.id, "art. 18, § 1º")])], env,
                   destino="peca", data_referencia=HOJE)
    assert ok.emitir
    ruim = verificar(db_session, [Afirmacao("x", [Citacao(v.id, "art. 18, § 7º")])], env,
                     destino="peca", data_referencia=HOJE)
    assert _tipos(ruim) == ["dispositivo_inexistente"]


def test_id_fora_do_envelope_bloqueia(db_session):
    v, env = _cenario(db_session)
    ver = verificar(db_session, [Afirmacao("x", [Citacao(v.id + 999_999, "art. 18")])], env,
                    destino="peca", data_referencia=HOJE)
    assert not ver.emitir and _tipos(ver) == ["id_fora_do_envelope"]


def test_dispositivo_inexistente_bloqueia(db_session):
    v, env = _cenario(db_session)
    ver = verificar(db_session, [Afirmacao("x", [Citacao(v.id, "art. 999")])], env,
                    destino="peca", data_referencia=HOJE)
    assert _tipos(ver) == ["dispositivo_inexistente"]


def test_status_nao_serve_a_peca(db_session):
    v, env = _cenario(db_session, status="proposto")
    ver = verificar(db_session, [Afirmacao("x", [Citacao(v.id, "18")])], env,
                    destino="peca", data_referencia=HOJE)
    assert _tipos(ver) == ["status_nao_serve_ao_destino"]
    assert verificar(db_session, [Afirmacao("x", [Citacao(v.id, "18")])], env,
                     destino="interno", data_referencia=HOJE).emitir


def test_fora_da_vigencia(db_session):
    v, env = _cenario(db_session, fim=date(2008, 7, 22))
    ver = verificar(db_session, [Afirmacao("x", [Citacao(v.id, "18")])], env,
                    destino="peca", data_referencia=HOJE)
    assert _tipos(ver) == ["fora_da_vigencia"]
    assert verificar(db_session, [Afirmacao("x", [Citacao(v.id, "18")])], env,
                     destino="peca", data_referencia=date(2007, 1, 1)).emitir


def test_versao_bloqueada_por_original(db_session):
    v, env = _cenario(db_session, bloqueio="original_divergente")
    ver = verificar(db_session, [Afirmacao("x", [Citacao(v.id, "18")])], env,
                    destino="peca", data_referencia=HOJE)
    assert "versao_bloqueada" in _tipos(ver)


def test_mencao_sem_id_e_citacao_orfa(db_session):
    v, env = _cenario(db_session)
    a = Afirmacao("Aplica-se o art. 18 do Decreto 6.514/2008 e a Lei 12.651/2012.",
                  [Citacao(v.id, "art. 18")])
    ver = verificar(db_session, [a], env, destino="peca", data_referencia=HOJE)
    assert not ver.emitir
    assert _tipos(ver) == ["citacao_orfa"]
    assert "12.651" in ver.falhas[0].detalhe


def test_artigo_mencionado_sem_vinculo(db_session):
    v, env = _cenario(db_session)
    a = Afirmacao("Conforme o art. 3º do Decreto 6.514/2008, a multa é devida.", [Citacao(v.id, "art. 18")])
    ver = verificar(db_session, [a], env, destino="peca", data_referencia=HOJE)
    assert _tipos(ver) == ["artigo_mencionado_sem_vinculo"]


def test_detector_reconhece_formas_que_o_regex_antigo_perdia():
    # #243: LC 140/2011, "Res. CONAMA 237/1997", Lei GO 18.104/2013 e norma sem ano passavam sem checar.
    achadas = {m["literal"] for m in mencoes(
        "Nos termos da LC 140/2011, da Res. CONAMA 237/1997, da Lei GO 18.104/2013 e da Lei 9.605."
    )}
    assert any("140/2011" in x for x in achadas)
    assert any("237/1997" in x for x in achadas)
    assert any("18.104/2013" in x for x in achadas)
    assert any(x.endswith("9.605") for x in achadas)
