"""Dívida #60 — cadeia de fichas e vigência de matrícula (caso real da Isis).

Critério de domínio: "vigente = matrícula da última averbação; a ficha anterior
vira HISTÓRICO — não soma, não gera lacuna, permanece visível como linhagem".

Casos-referência: 2609→2923→4698 (lote 1B) e 4655→6776 (Shangri-lá → São Jorge).
A resposta certa que a Isis vai ver: 1 clique onde antes eram 12 rejeições.
"""

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.matricula import Matricula
from app.models.process import Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User
from app.services.ficha01_extraction import build_staging_fields
from app.services.matricula_chain import (
    apply_chain,
    detect_chain_proposals,
    set_vigencia,
)


def _login(client: TestClient, email: str, password: str = "x12345") -> dict[str, str]:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _mat(tenant_id, property_id, numero, area, **kw) -> Matricula:
    return Matricula(
        tenant_id=tenant_id, property_id=property_id,
        numero_matricula=numero, area_ha=area, **kw,
    )


def _setup(db_session, email, *, superuser=True):
    tenant = Tenant(name=f"T {email}")
    db_session.add(tenant)
    db_session.flush()
    user = User(email=email, full_name="Consultor",
                hashed_password=get_password_hash("x12345"),
                tenant_id=tenant.id, is_active=True, is_superuser=superuser)
    cli = Client(tenant_id=tenant.id, full_name="Luiz Augusto", email=f"c.{email}",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add_all([user, cli])
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda São Jorge")
    db_session.add(prop)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Caso", process_type="prad", status=ProcessStatus.triagem)
    db_session.add(proc)
    db_session.flush()
    return tenant, cli, prop, proc


# ---------------------------------------------------------------------------
# Extração: registro_anterior + denominacao_anterior viram staging próprio
# ---------------------------------------------------------------------------

def test_extracao_registro_e_denominacao_anterior_tem_coluna_propria():
    parsed = {
        "numero_matricula": "4.698",
        "denominacao": "Fazenda São Jorge Lote 1B",
        "denominacao_anterior": "Fazenda Boa Vista",
        "registro_anterior": "2.923",
        "confidence": {},
    }
    rows = build_staging_fields("matricula", parsed)
    by_field = {r.field_name: r for r in rows}

    # registro_anterior agora É extraído e mapeia para a coluna própria (#60).
    assert "registro_anterior" in by_field
    assert by_field["registro_anterior"].target_field == "registro_anterior"
    assert by_field["registro_anterior"].field_value["value"] == "2.923"

    # denominacao_anterior NÃO cai mais em denominacao_imovel (competia com a atual).
    assert by_field["denominacao_anterior"].target_field == "denominacao_anterior"
    assert by_field["denominacao"].target_field == "denominacao_imovel"


# ---------------------------------------------------------------------------
# Detecção da cadeia — 3 sinais
# ---------------------------------------------------------------------------

def test_detecta_cadeia_por_registro_anterior(db_session):
    _t, _c, prop, _p = _setup(db_session, "reg@ex.com")
    m2923 = _mat(prop.tenant_id, prop.id, "2.923", 660.6561)
    m4698 = _mat(prop.tenant_id, prop.id, "4.698", 660.6561, registro_anterior="R-01 Mat. 2.923")
    db_session.add_all([m2923, m4698])
    db_session.flush()
    db_session.refresh(prop)

    props = detect_chain_proposals(prop)
    assert len(props) == 1
    p = props[0]
    assert (p.anterior_id, p.vigente_id) == (m2923.id, m4698.id)
    assert p.sinal == "registro_anterior"
    assert p.confianca == "alta"


def test_detecta_cadeia_por_denominacao_e_area(db_session):
    _t, _c, prop, _p = _setup(db_session, "den@ex.com")
    m4655 = _mat(prop.tenant_id, prop.id, "4.655", 349.9022,
                 denominacao_imovel="Fazenda Shangri-lá")
    m6776 = _mat(prop.tenant_id, prop.id, "6.776", 349.9022,
                 denominacao_imovel="Fazenda São Jorge",
                 denominacao_anterior="Fazenda Shangri-lá")
    db_session.add_all([m4655, m6776])
    db_session.flush()
    db_session.refresh(prop)

    props = detect_chain_proposals(prop)
    assert len(props) == 1
    p = props[0]
    assert (p.anterior_id, p.vigente_id) == (m4655.id, m6776.id)
    assert p.sinal == "denominacao_area"


def test_detecta_cadeia_por_lote_area_direcao_pelo_numero(db_session):
    _t, _c, prop, _p = _setup(db_session, "lote@ex.com")
    m1 = _mat(prop.tenant_id, prop.id, "2.609", 500.0, denominacao_imovel="Fazenda Velha Lote 1B")
    m2 = _mat(prop.tenant_id, prop.id, "2.923", 500.0, denominacao_imovel="Fazenda Nova Lote 1B")
    db_session.add_all([m1, m2])
    db_session.flush()
    db_session.refresh(prop)

    props = detect_chain_proposals(prop)
    assert len(props) == 1
    p = props[0]
    # maior número = mais recente = vigente
    assert (p.anterior_id, p.vigente_id) == (m1.id, m2.id)
    assert p.sinal == "lote_area"
    assert p.confianca == "baixa"


# ---------------------------------------------------------------------------
# Aplicação: histórica sai da soma; recusa mantém; reversão volta
# ---------------------------------------------------------------------------

def test_aplicar_cadeia_tira_historica_da_soma(db_session):
    _t, _c, prop, _p = _setup(db_session, "soma@ex.com")
    m2923 = _mat(prop.tenant_id, prop.id, "2.923", 660.6561)
    m4698 = _mat(prop.tenant_id, prop.id, "4.698", 660.6561, registro_anterior="2.923")
    db_session.add_all([m2923, m4698])
    db_session.flush()
    db_session.refresh(prop)

    # Antes: soma dobrada (a ficha anterior ainda soma) — o problema da Isis.
    assert prop.area_total_matriculas() == 1321.3122

    apply_chain(db_session, tenant_id=prop.tenant_id, property_id=prop.id,
                pairs=[(m2923.id, m4698.id)])
    db_session.refresh(prop)
    db_session.refresh(m2923)

    assert m2923.vigencia == "historica"
    assert m2923.superseded_by_id == m4698.id
    # Depois: só a vigente soma = 660,6561 (não 1.321).
    assert prop.area_total_matriculas() == 660.6561
    assert [m.id for m in prop.matriculas_historicas()] == [m2923.id]
    assert [m.id for m in prop.matriculas_vigentes()] == [m4698.id]


def test_caso_completo_isis_soma_final(db_session):
    """4 fichas, 2 cadeias → soma final do caso = 1.010,5583."""
    _t, _c, prop, _p = _setup(db_session, "isis@ex.com")
    m2923 = _mat(prop.tenant_id, prop.id, "2.923", 660.6561)
    m4698 = _mat(prop.tenant_id, prop.id, "4.698", 660.6561, registro_anterior="2.923")
    m4655 = _mat(prop.tenant_id, prop.id, "4.655", 349.9022,
                 denominacao_imovel="Fazenda Shangri-lá")
    m6776 = _mat(prop.tenant_id, prop.id, "6.776", 349.9022,
                 denominacao_imovel="Fazenda São Jorge",
                 denominacao_anterior="Fazenda Shangri-lá")
    db_session.add_all([m2923, m4698, m4655, m6776])
    db_session.flush()
    db_session.refresh(prop)

    props = detect_chain_proposals(prop)
    assert len(props) == 2
    apply_chain(db_session, tenant_id=prop.tenant_id, property_id=prop.id,
                pairs=[(p.anterior_id, p.vigente_id) for p in props])
    db_session.refresh(prop)

    vigentes = {m.numero_matricula for m in prop.matriculas_vigentes()}
    assert vigentes == {"4.698", "6.776"}
    assert prop.area_total_matriculas() == 1010.5583


def test_recusa_mantem_ambas_vigentes(db_session):
    _t, _c, prop, _p = _setup(db_session, "recusa@ex.com")
    m2923 = _mat(prop.tenant_id, prop.id, "2.923", 660.6561)
    m4698 = _mat(prop.tenant_id, prop.id, "4.698", 660.6561, registro_anterior="2.923")
    db_session.add_all([m2923, m4698])
    db_session.flush()
    db_session.refresh(prop)

    # Recusa = não aplicar nada (pairs vazio). Ambas seguem vigentes.
    apply_chain(db_session, tenant_id=prop.tenant_id, property_id=prop.id, pairs=[])
    db_session.refresh(prop)
    assert len(prop.matriculas_vigentes()) == 2
    assert prop.area_total_matriculas() == 1321.3122


def test_reversao_volta_a_somar(db_session):
    _t, _c, prop, _p = _setup(db_session, "rev@ex.com")
    m2923 = _mat(prop.tenant_id, prop.id, "2.923", 660.6561)
    m4698 = _mat(prop.tenant_id, prop.id, "4.698", 660.6561, registro_anterior="2.923")
    db_session.add_all([m2923, m4698])
    db_session.flush()
    apply_chain(db_session, tenant_id=prop.tenant_id, property_id=prop.id,
                pairs=[(m2923.id, m4698.id)])
    db_session.refresh(prop)
    assert prop.area_total_matriculas() == 660.6561

    # Reversão em Dados: 2923 volta a vigente → soma restaurada.
    set_vigencia(db_session, tenant_id=prop.tenant_id, property_id=prop.id,
                 matricula_id=m2923.id, vigencia="vigente")
    db_session.refresh(prop)
    db_session.refresh(m2923)
    assert m2923.vigencia == "vigente"
    assert m2923.superseded_by_id is None
    assert prop.area_total_matriculas() == 1321.3122


def test_aplicar_cadeia_idempotente(db_session):
    _t, _c, prop, _p = _setup(db_session, "idem@ex.com")
    m2923 = _mat(prop.tenant_id, prop.id, "2.923", 660.6561)
    m4698 = _mat(prop.tenant_id, prop.id, "4.698", 660.6561, registro_anterior="2.923")
    db_session.add_all([m2923, m4698])
    db_session.flush()
    r1 = apply_chain(db_session, tenant_id=prop.tenant_id, property_id=prop.id,
                     pairs=[(m2923.id, m4698.id)])
    r2 = apply_chain(db_session, tenant_id=prop.tenant_id, property_id=prop.id,
                     pairs=[(m2923.id, m4698.id)])
    assert r1["count"] == 1
    assert r2["count"] == 0  # reaplicar não muda nada


# ---------------------------------------------------------------------------
# Efeitos: histórica não gera MISSING_MATRICULA nem falsa contiguidade
# ---------------------------------------------------------------------------

def test_historica_nao_gera_missing_matricula_nem_contiguidade(db_session):
    from app.services.dossier import validate_technical_consistency

    _t, _c, prop, proc = _setup(db_session, "gap@ex.com")
    m4655 = _mat(prop.tenant_id, prop.id, "4.655", 349.9022,
                 denominacao_imovel="Fazenda Shangri-lá", vigencia="historica")
    m6776 = _mat(prop.tenant_id, prop.id, "6.776", 349.9022,
                 denominacao_imovel="Fazenda São Jorge")
    m4655.superseded_by_id = m6776.id
    db_session.add_all([m4655, m6776])
    db_session.flush()
    db_session.refresh(prop)

    issues = validate_technical_consistency(proc, prop, [], None)
    codes = {i.code for i in issues}
    # Há 1 vigente COM número → nada de "matrícula ausente".
    assert "MISSING_MATRICULA" not in codes
    # 1 vigente (a histórica não conta) → sem lacuna de contiguidade.
    assert "CONTIGUIDADE_NAO_DECLARADA" not in codes


# ---------------------------------------------------------------------------
# Endpoints: proposta + 1 clique + reversão (com auth/tenant)
# ---------------------------------------------------------------------------

def test_endpoint_chain_proposals_e_aplicar(client: TestClient, db_session):
    _t, _c, prop, proc = _setup(db_session, "ep@ex.com")
    m2923 = _mat(prop.tenant_id, prop.id, "2.923", 660.6561)
    m4698 = _mat(prop.tenant_id, prop.id, "4.698", 660.6561, registro_anterior="2.923")
    db_session.add_all([m2923, m4698])
    db_session.commit()
    h = _login(client, "ep@ex.com")
    base = f"/api/v1/processes/{proc.id}"

    r = client.get(f"{base}/chain-proposals", headers=h)
    assert r.status_code == 200, r.text
    props = r.json()
    assert len(props) == 1
    assert props[0]["vigente_numero"] == "4.698"

    r = client.post(f"{base}/chain-proposals/aplicar", headers=h,
                    json={"pairs": [{"anterior_id": m2923.id, "vigente_id": m4698.id}]})
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 1

    db_session.expire_all()
    m = db_session.get(Matricula, m2923.id)
    assert m.vigencia == "historica"
    assert m.superseded_by_id == m4698.id


def test_endpoint_vigencia_reversao_e_validacoes(client: TestClient, db_session):
    _t, _c, prop, _p = _setup(db_session, "vig@ex.com")
    m2923 = _mat(prop.tenant_id, prop.id, "2.923", 660.6561, vigencia="historica")
    m4698 = _mat(prop.tenant_id, prop.id, "4.698", 660.6561)
    m2923.superseded_by_id = None  # set após flush abaixo
    db_session.add_all([m2923, m4698])
    db_session.flush()
    m2923.superseded_by_id = m4698.id
    db_session.commit()
    h = _login(client, "vig@ex.com")
    base = f"/api/v1/properties/{prop.id}/matriculas"

    # historica sem superseded_by → 422
    r = client.patch(f"{base}/{m4698.id}/vigencia", headers=h, json={"vigencia": "historica"})
    assert r.status_code == 422

    # matrícula inexistente → 404
    r = client.patch(f"{base}/999999/vigencia", headers=h, json={"vigencia": "vigente"})
    assert r.status_code == 404

    # reversão da histórica → vigente
    r = client.patch(f"{base}/{m2923.id}/vigencia", headers=h, json={"vigencia": "vigente"})
    assert r.status_code == 200, r.text
    assert r.json()["vigencia"] == "vigente"
    assert r.json()["superseded_by_id"] is None


def test_chain_proposals_sem_auth_401(client: TestClient, db_session):
    _t, _c, _prop, proc = _setup(db_session, "noauth@ex.com")
    db_session.commit()
    r = client.get(f"/api/v1/processes/{proc.id}/chain-proposals")
    assert r.status_code == 401
