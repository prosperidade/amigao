"""
ENT-001 / ENT-002 — as OUTRAS portas da mesma classe de defeito.

A matriz de perfis (`test_matriz_perfis_identidade.py`) é o gate: prova os sete
perfis pelo caminho principal. Este arquivo cobre o resto da classe, que é onde a
regra costuma vazar:

  · `PATCH /clients/{id}` — mover o documento de um cadastro para o de outro é
    criar o duplicado pela porta dos fundos (cobrir PATCH além de POST);
  · `POST /intake/create-case` — a SEGUNDA porta de criação de cliente;
  · CRUD do representante — inclusive a recusa em cliente PF;
  · validação de formato do documento, que é o que protege a coluna indexada.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.client_representative import ClientRepresentative
from app.models.tenant import Tenant
from app.models.user import User

CNPJ = "29.091.958/0001-17"
CPF = "529.982.247-25"


def _cenario(db, email: str):
    t = Tenant(name=f"T-{email}")
    db.add(t)
    db.flush()
    db.add(User(email=email, full_name="Consultora",
                hashed_password=get_password_hash("x12345"),
                tenant_id=t.id, is_active=True, is_superuser=True))
    db.flush()
    return t


def _login(client: TestClient, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login",
                    data={"username": email, "password": "x12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------------------------------------------------------------------------
# ENT-002 — PATCH
# ---------------------------------------------------------------------------

def test_patch_nao_move_documento_para_o_de_outro_cadastro(client: TestClient, db_session):
    _cenario(db_session, "patch@ex.com")
    db_session.commit()
    h = _login(client, "patch@ex.com")

    a = client.post("/api/v1/clients/", headers=h, json={
        "full_name": "ELODI", "cpf_cnpj": CNPJ, "client_type": "pj"}).json()
    b = client.post("/api/v1/clients/", headers=h, json={
        "full_name": "Valeria", "cpf_cnpj": CPF, "client_type": "pf"}).json()

    r = client.patch(f"/api/v1/clients/{b['id']}", headers=h,
                     json={"cpf_cnpj": "29091958000117"})
    assert r.status_code == 409, f"PATCH criou duplicata: {r.status_code} {r.text}"
    assert r.json()["detail"]["client_id"] == a["id"]


def test_patch_do_proprio_documento_continua_permitido(client: TestClient, db_session):
    """O guard não pode fazer o cadastro colidir consigo mesmo — reformatar o
    próprio documento é edição legítima."""
    _cenario(db_session, "patch2@ex.com")
    db_session.commit()
    h = _login(client, "patch2@ex.com")

    a = client.post("/api/v1/clients/", headers=h, json={
        "full_name": "ELODI", "cpf_cnpj": CNPJ, "client_type": "pj"}).json()
    r = client.patch(f"/api/v1/clients/{a['id']}", headers=h,
                     json={"cpf_cnpj": "29091958000117"})
    assert r.status_code == 200, r.text
    assert r.json()["cpf_cnpj"] == "29091958000117"


# ---------------------------------------------------------------------------
# ENT-002 — a segunda porta de criação
# ---------------------------------------------------------------------------

def test_intake_nao_cria_segundo_cadastro_com_o_mesmo_documento(client: TestClient, db_session):
    t = _cenario(db_session, "intake@ex.com")
    db_session.add(Client(tenant_id=t.id, full_name="ELODI", legal_name="ELODI Ltda.",
                          cpf_cnpj=CNPJ, client_type=ClientType.pj,
                          status=ClientStatus.active, email="elodi@ex.com"))
    db_session.commit()
    h = _login(client, "intake@ex.com")

    r = client.post("/api/v1/intake/create-case", headers=h, json={
        "new_client": {"full_name": "Joel ELODI", "email": "joel@ex.com",
                       "cpf_cnpj": "29091958000117", "client_type": "pj"},
        "new_property": {"name": "Fazenda Retiro"},
        "description": "Regularização ambiental do imóvel rural.",
    })
    assert r.status_code == 409, f"intake criou duplicata: {r.status_code} {r.text}"
    assert r.json()["detail"]["code"] == "documento_ja_cadastrado"


# ---------------------------------------------------------------------------
# Formato do documento — protege a coluna que o índice único indexa
# ---------------------------------------------------------------------------

def test_documento_com_digitos_de_menos_e_recusado(client: TestClient, db_session):
    _cenario(db_session, "fmt@ex.com")
    db_session.commit()
    h = _login(client, "fmt@ex.com")

    r = client.post("/api/v1/clients/", headers=h, json={
        "full_name": "Meio documento", "cpf_cnpj": "529.982", "client_type": "pf"})
    assert r.status_code == 422, r.text

    # Cadastro SEM documento continua válido (lead real).
    r2 = client.post("/api/v1/clients/", headers=h, json={
        "full_name": "Lead sem documento", "client_type": "pf"})
    assert r2.status_code == 201, r2.text
    assert r2.json()["cpf_cnpj"] is None


# ---------------------------------------------------------------------------
# ENT-001 — CRUD do representante
# ---------------------------------------------------------------------------

def test_representante_so_existe_em_cliente_pj(client: TestClient, db_session):
    _cenario(db_session, "rep@ex.com")
    db_session.commit()
    h = _login(client, "rep@ex.com")

    pf = client.post("/api/v1/clients/", headers=h, json={
        "full_name": "Valeria Ruiz", "cpf_cnpj": CPF, "client_type": "pf"}).json()

    r = client.post(f"/api/v1/clients/{pf['id']}/representatives", headers=h,
                    json={"full_name": "Alguem", "cpf": "123.456.789-09"})
    assert r.status_code == 400, "PF não tem representante — o titular é a própria pessoa"


def test_ciclo_do_representante_em_cliente_pj(client: TestClient, db_session):
    _cenario(db_session, "rep2@ex.com")
    db_session.commit()
    h = _login(client, "rep2@ex.com")

    pj = client.post("/api/v1/clients/", headers=h, json={
        "full_name": "ELODI", "legal_name": "ELODI Agropecuaria Ltda.",
        "cpf_cnpj": CNPJ, "client_type": "pj"}).json()
    base = f"/api/v1/clients/{pj['id']}/representatives"

    criado = client.post(base, headers=h, json={
        "full_name": "Joel Cenci", "cpf": "123.456.789-09",
        "papel": "socio_administrador"})
    assert criado.status_code == 201, criado.text
    rep = criado.json()
    assert rep["papel"] == "socio_administrador"
    # Digitado pela consultora nasce com proveniência humana.
    assert rep["field_sources"]["full_name"] == "human_validated"

    # O titular continua sendo a empresa — o representante não desloca ninguém.
    titular = client.get(f"/api/v1/clients/{pj['id']}", headers=h).json()
    assert titular["cpf_cnpj"] == CNPJ
    assert titular["legal_name"] == "ELODI Agropecuaria Ltda."
    assert len(titular["representatives"]) == 1

    alterado = client.patch(f"{base}/{rep['id']}", headers=h,
                            json={"papel": "procurador"})
    assert alterado.status_code == 200 and alterado.json()["papel"] == "procurador"

    assert client.delete(f"{base}/{rep['id']}", headers=h).status_code == 204
    assert client.get(base, headers=h).json() == []
    # Soft delete: a linha continua no banco, fora das leituras.
    assert db_session.query(ClientRepresentative).filter(
        ClientRepresentative.id == rep["id"]).first().deleted_at is not None


def test_representante_de_outro_tenant_nao_e_alcancavel(client: TestClient, db_session):
    """404, nunca 403 — não confirmar existência de recurso de outro tenant."""
    t1 = _cenario(db_session, "tA@ex.com")
    t2 = _cenario(db_session, "tB@ex.com")
    alheio = Client(tenant_id=t2.id, full_name="ELODI", cpf_cnpj=CNPJ,
                    client_type=ClientType.pj, email="outro@ex.com")
    db_session.add(alheio)
    db_session.flush()
    rep = ClientRepresentative(tenant_id=t2.id, client_id=alheio.id,
                               full_name="Joel", cpf="123.456.789-09")
    db_session.add(rep)
    db_session.commit()

    h = _login(client, "tA@ex.com")
    assert client.get(f"/api/v1/clients/{alheio.id}/representatives",
                      headers=h).status_code == 404
    assert client.patch(f"/api/v1/clients/{alheio.id}/representatives/{rep.id}",
                        headers=h, json={"papel": "procurador"}).status_code == 404
    assert t1.id != t2.id
