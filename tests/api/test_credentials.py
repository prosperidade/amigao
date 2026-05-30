"""
Testes da API de Credenciais de portal (PR 2.3).

Foco: senha cifrada em repouso (verificação SQL direta), nunca em plaintext na
resposta, isolamento por tenant, e preservação da senha em update parcial.
"""
import json

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import get_password_hash
from app.models.client import Client, ClientType
from app.models.tenant import Tenant
from app.models.user import User


def _login(tc: TestClient, email: str, password: str) -> dict[str, str]:
    r = tc.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup(db_session, *, tenant_name: str, email: str) -> tuple[int, int]:
    """Cria tenant + user + client. Retorna (tenant_id, client_id)."""
    tenant = Tenant(name=tenant_name)
    db_session.add(tenant)
    db_session.flush()
    user = User(
        email=email,
        full_name="Consultor Cred",
        hashed_password=get_password_hash("Consultor1"),
        tenant_id=tenant.id,
        is_active=True,
    )
    client = Client(tenant_id=tenant.id, client_type=ClientType.pf, full_name="Cliente Cred")
    db_session.add_all([user, client])
    db_session.commit()
    return tenant.id, client.id


def test_create_credential_encrypts_password_not_plaintext(client: TestClient, db_session):
    _, client_id = _setup(db_session, tenant_name="T Cred Enc", email="cred.enc@example.com")
    headers = _login(client, "cred.enc@example.com", "Consultor1")

    r = client.post(
        "/api/v1/credentials",
        json={
            "client_id": client_id,
            "portal": "sema",
            "label": "SEMA-GO produtor X",
            "login": "usuario_portal",
            "password": "SENHA-PLAINTEXT-9999",
            "url": "https://sema.go.gov.br",
        },
        headers=headers,
    )
    assert r.status_code == 201
    body = r.json()
    cred_id = body["id"]
    # resposta NUNCA traz a senha
    assert "password" not in body
    assert body["has_password"] is True
    assert body["login"] == "usuario_portal"

    # SQL direto: o ciphertext não pode conter o plaintext.
    db_session.expire_all()
    stored = db_session.execute(
        text("SELECT password_encrypted FROM credentials WHERE id = :id"), {"id": cred_id}
    ).scalar()
    assert stored is not None
    assert "SENHA-PLAINTEXT-9999" not in str(stored)


def test_get_and_list_never_return_password(client: TestClient, db_session):
    _, client_id = _setup(db_session, tenant_name="T Cred Get", email="cred.get@example.com")
    headers = _login(client, "cred.get@example.com", "Consultor1")
    created = client.post(
        "/api/v1/credentials",
        json={"client_id": client_id, "portal": "banco", "password": "sk-x"},
        headers=headers,
    ).json()

    got = client.get(f"/api/v1/credentials/{created['id']}", headers=headers)
    assert got.status_code == 200
    assert "password" not in got.json()
    assert got.json()["has_password"] is True

    listed = client.get(f"/api/v1/credentials?client_id={client_id}", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert all("password" not in c for c in listed.json())
    # garante que o plaintext não vaza no corpo da resposta inteiro
    assert "sk-x" not in json.dumps(listed.json())


def test_tenant_isolation_blocks_other_tenant(client: TestClient, db_session):
    _, client_a = _setup(db_session, tenant_name="T Cred A", email="cred.a@example.com")
    headers_a = _login(client, "cred.a@example.com", "Consultor1")
    cred = client.post(
        "/api/v1/credentials",
        json={"client_id": client_a, "portal": "incra", "password": "p"},
        headers=headers_a,
    ).json()

    _setup(db_session, tenant_name="T Cred B", email="cred.b@example.com")
    headers_b = _login(client, "cred.b@example.com", "Consultor1")

    # B não enxerga a credencial de A
    assert client.get(f"/api/v1/credentials/{cred['id']}", headers=headers_b).status_code == 404


def test_update_password_and_preserve_when_absent(client: TestClient, db_session):
    _, client_id = _setup(db_session, tenant_name="T Cred Upd", email="cred.upd@example.com")
    headers = _login(client, "cred.upd@example.com", "Consultor1")
    cred = client.post(
        "/api/v1/credentials",
        json={"client_id": client_id, "portal": "sicar", "password": "primeira"},
        headers=headers,
    ).json()
    cred_id = cred["id"]

    # update só do label — não pode apagar a senha
    client.patch(f"/api/v1/credentials/{cred_id}", json={"label": "novo rótulo"}, headers=headers)
    got = client.get(f"/api/v1/credentials/{cred_id}", headers=headers).json()
    assert got["has_password"] is True
    assert got["label"] == "novo rótulo"

    # troca a senha
    db_session.expire_all()
    client.patch(f"/api/v1/credentials/{cred_id}", json={"password": "segunda-NOVA"}, headers=headers)
    db_session.expire_all()
    stored = db_session.execute(
        text("SELECT password_encrypted FROM credentials WHERE id = :id"), {"id": cred_id}
    ).scalar()
    assert "segunda-NOVA" not in str(stored)  # cifrada
    assert "primeira" not in str(stored)


def test_soft_delete(client: TestClient, db_session):
    _, client_id = _setup(db_session, tenant_name="T Cred Del", email="cred.del@example.com")
    headers = _login(client, "cred.del@example.com", "Consultor1")
    cred = client.post(
        "/api/v1/credentials",
        json={"client_id": client_id, "portal": "outro", "password": "p"},
        headers=headers,
    ).json()

    assert client.delete(f"/api/v1/credentials/{cred['id']}", headers=headers).status_code == 204
    # some das leituras
    assert client.get(f"/api/v1/credentials/{cred['id']}", headers=headers).status_code == 404
    assert client.get(f"/api/v1/credentials?client_id={client_id}", headers=headers).json() == []


def test_create_rejects_client_from_other_tenant(client: TestClient, db_session):
    _setup(db_session, tenant_name="T Cred X", email="cred.x@example.com")
    _, client_y = _setup(db_session, tenant_name="T Cred Y", email="cred.y@example.com")
    headers_x = _login(client, "cred.x@example.com", "Consultor1")

    # X tenta criar credencial para o cliente de Y → 404
    r = client.post(
        "/api/v1/credentials",
        json={"client_id": client_y, "portal": "sema", "password": "p"},
        headers=headers_x,
    )
    assert r.status_code == 404
