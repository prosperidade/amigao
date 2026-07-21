"""Cascata de vinculação ITR → matrícula (spec da Isis, 20/07).

Do mais forte ao mais fraco: NIRF → INCRA → (corroboração: dívida) → manual.

Só os degraus 1, 2 e 4 estão implementados (recorte do André, 20/07). O degrau
3 (corroboração) virou dívida com a cascata da Isis como spec.
"""

from __future__ import annotations

from tests.services.test_consolidacao_lineage import _mat, _seed

from app.services.consolidacao_lineage import vincular_itr

# ---------------------------------------------------------------------------
# Degrau 1 — NIRF (o mais forte)
# ---------------------------------------------------------------------------

def test_nivel_1_nirf_vincula(db_session):
    tenant, proc, prop = _seed(db_session)
    alvo = _mat(db_session, tenant, prop, "6776")
    alvo.nirf_cib = "9.153.765-7"
    _mat(db_session, tenant, prop, "2923")
    db_session.flush()

    r = vincular_itr(db_session, tenant_id=tenant.id, property_id=prop.id,
                     nirf="9153765-7")

    assert r.nivel == 1
    assert r.autolink is True
    assert r.matricula.id == alvo.id


def test_nirf_vence_o_incra(db_session):
    """O degrau 1 resolve antes de o INCRA ser consultado."""
    tenant, proc, prop = _seed(db_session)
    por_nirf = _mat(db_session, tenant, prop, "6776", incra="111.111.111.111-1")
    por_nirf.nirf_cib = "9.153.765-7"
    _mat(db_session, tenant, prop, "2923", incra="951.048.549.371-0")
    db_session.flush()

    r = vincular_itr(db_session, tenant_id=tenant.id, property_id=prop.id,
                     nirf="9153765-7", codigos_incra=["951048.549371-0"])

    assert r.nivel == 1
    assert r.matricula.id == por_nirf.id


def test_nirf_ambiguo_cai_para_o_proximo_degrau(db_session):
    tenant, proc, prop = _seed(db_session)
    a = _mat(db_session, tenant, prop, "6776", incra="951.048.549.371-0")
    b = _mat(db_session, tenant, prop, "2923")
    a.nirf_cib = "9.153.765-7"
    b.nirf_cib = "9153765-7"
    db_session.flush()

    r = vincular_itr(db_session, tenant_id=tenant.id, property_id=prop.id,
                     nirf="9.153.765-7", codigos_incra=["951048.549371-0"])

    assert r.nivel == 2          # NIRF não resolveu; INCRA resolveu
    assert r.matricula.id == a.id


# ---------------------------------------------------------------------------
# Degrau 2 — INCRA
# ---------------------------------------------------------------------------

def test_nivel_2_incra_vincula_quando_unico(db_session):
    tenant, proc, prop = _seed(db_session)
    alvo = _mat(db_session, tenant, prop, "6776", incra="951.048.549.371-0")
    _mat(db_session, tenant, prop, "2923", incra="000.051.123.390-9")

    r = vincular_itr(db_session, tenant_id=tenant.id, property_id=prop.id,
                     codigos_incra=["951048.549371-0"])

    assert r.nivel == 2
    assert r.autolink is True
    assert r.matricula.id == alvo.id


# ---------------------------------------------------------------------------
# Degrau 3 — corroboração: DÍVIDA (recorte do André, 20/07)
# ---------------------------------------------------------------------------
# Área + denominação como sugestão ranqueada ficou para follow-up. Enquanto
# não existe, o caso ambíguo cai no degrau 4 manual — coberto abaixo.
# Quando entrar, o teste que NÃO pode faltar é "nunca autolinka": a Isis foi
# explícita de que corroboração é sugestão, jamais vínculo automático.

# ---------------------------------------------------------------------------
# Degrau 4 — o consultor decide
# ---------------------------------------------------------------------------

def test_nivel_4_apresenta_candidatos(db_session):
    """Caso do Lote 01-C: nenhum sinal resolve — mostra os candidatos."""
    tenant, proc, prop = _seed(db_session)
    _mat(db_session, tenant, prop, "6776", incra="951.048.549.371-0")
    _mat(db_session, tenant, prop, "2923", incra="000.051.123.390-9")

    r = vincular_itr(db_session, tenant_id=tenant.id, property_id=prop.id,
                     nirf="1.111.111-1", codigos_incra=["9500683909098"])

    assert r.nivel == 0
    assert r.autolink is False
    assert len(r.candidatas) == 2
    assert "escolha a matrícula" in r.motivo


def test_incra_divergente_no_documento_nao_vincula(db_session):
    """Duas famílias documentais concorrentes (909-8 x 371-0)."""
    tenant, proc, prop = _seed(db_session)
    _mat(db_session, tenant, prop, "6776", incra="951.048.549.371-0")

    r = vincular_itr(db_session, tenant_id=tenant.id, property_id=prop.id,
                     codigos_incra=["951048.549371-0", "9500683909098"])

    assert r.autolink is False


def test_sem_matricula_na_base(db_session):
    tenant, proc, prop = _seed(db_session)

    r = vincular_itr(db_session, tenant_id=tenant.id, property_id=prop.id,
                     nirf="9.153.765-7")

    assert r.matricula is None
    assert "ainda não tem matrícula" in r.motivo
