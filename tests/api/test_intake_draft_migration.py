"""PR fix Isis #2 — /intake/create-case com draft_id migra docs do rascunho.

Cobre: regressão sem draft_id, migração com draft_id, 404 (inexistente / outro
tenant), 409 (já consumido), no-op sem docs.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.document import Document
from app.models.intake_draft import IntakeDraft, IntakeDraftState
from app.models.tenant import Tenant
from app.models.user import User


def _setup_tenant_user(db_session, *, email: str) -> int:
    tenant = Tenant(name=f"T {email}")
    db_session.add(tenant)
    db_session.flush()
    user = User(
        email=email,
        full_name="Consultor Intake",
        hashed_password=get_password_hash("Intake1"),
        tenant_id=tenant.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return tenant.id


def _login(tc: TestClient, email: str) -> dict[str, str]:
    r = tc.post("/api/v1/auth/login", data={"username": email, "password": "Intake1"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_draft(db_session, tenant_id: int, *, state: IntakeDraftState = IntakeDraftState.rascunho) -> IntakeDraft:
    draft = IntakeDraft(tenant_id=tenant_id, state=state, form_data={})
    db_session.add(draft)
    db_session.flush()
    return draft


def _make_draft_doc(db_session, tenant_id: int, draft_id: int, *, key: str, doc_type: str = "matricula") -> Document:
    doc = Document(
        tenant_id=tenant_id,
        intake_draft_id=draft_id,
        process_id=None,
        original_file_name=f"{key}.pdf",
        filename=f"{key}.pdf",
        content_type="application/pdf",
        storage_key=key,
        document_type=doc_type,
    )
    db_session.add(doc)
    db_session.flush()
    return doc


_PAYLOAD = {
    "entry_type": "novo_cliente_novo_imovel",
    "new_client": {
        "full_name": "Fazenda Boa Vista",
        "email": "fazenda.boavista@example.com",  # e-mail é obrigatório (decisão Isis)
        "phone": "62999990000",
        "client_type": "pf",
    },
    "new_property": {"name": "Sítio X", "municipality": "Goiânia", "state": "GO"},
}


def test_create_case_without_draft_id_regression(client: TestClient, db_session):
    _setup_tenant_user(db_session, email="reg.nodraft@example.com")
    headers = _login(client, "reg.nodraft@example.com")

    r = client.post("/api/v1/intake/create-case", json=dict(_PAYLOAD), headers=headers)

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["process_id"] > 0
    assert body["client_id"] > 0


def test_create_case_with_draft_id_migrates_docs(client: TestClient, db_session):
    tenant_id = _setup_tenant_user(db_session, email="reg.migra@example.com")
    draft = _make_draft(db_session, tenant_id)
    d1 = _make_draft_doc(db_session, tenant_id, draft.id, key="mig-a")
    d2 = _make_draft_doc(db_session, tenant_id, draft.id, key="mig-b")
    db_session.commit()
    headers = _login(client, "reg.migra@example.com")

    payload = {**_PAYLOAD, "draft_id": draft.id}
    r = client.post("/api/v1/intake/create-case", json=payload, headers=headers)

    assert r.status_code == 201, r.text
    process_id = r.json()["process_id"]
    client_id = r.json()["client_id"]

    db_session.expire_all()
    for doc_id in (d1.id, d2.id):
        doc = db_session.query(Document).filter_by(id=doc_id).one()
        assert doc.process_id == process_id
        assert doc.client_id == client_id
        assert doc.intake_draft_id == draft.id  # preservado

    migrated_draft = db_session.query(IntakeDraft).filter_by(id=draft.id).one()
    assert migrated_draft.state == IntakeDraftState.card_criado
    assert migrated_draft.linked_process_id == process_id


def test_create_case_draft_id_not_found(client: TestClient, db_session):
    _setup_tenant_user(db_session, email="reg.404@example.com")
    headers = _login(client, "reg.404@example.com")

    payload = {**_PAYLOAD, "draft_id": 999999}
    r = client.post("/api/v1/intake/create-case", json=payload, headers=headers)

    assert r.status_code == 404, r.text


def test_create_case_draft_id_other_tenant_is_404(client: TestClient, db_session):
    # draft pertence ao tenant B; usuário é do tenant A
    tenant_b = _setup_tenant_user(db_session, email="reg.tenantB@example.com")
    draft_b = _make_draft(db_session, tenant_b)
    db_session.commit()

    _setup_tenant_user(db_session, email="reg.tenantA@example.com")
    headers = _login(client, "reg.tenantA@example.com")

    payload = {**_PAYLOAD, "draft_id": draft_b.id}
    r = client.post("/api/v1/intake/create-case", json=payload, headers=headers)

    assert r.status_code == 404, r.text  # não 403 — não vaza existência


def test_create_case_draft_id_already_consumed_is_409(client: TestClient, db_session):
    tenant_id = _setup_tenant_user(db_session, email="reg.409@example.com")
    draft = _make_draft(db_session, tenant_id, state=IntakeDraftState.card_criado)
    db_session.commit()
    headers = _login(client, "reg.409@example.com")

    payload = {**_PAYLOAD, "draft_id": draft.id}
    r = client.post("/api/v1/intake/create-case", json=payload, headers=headers)

    assert r.status_code == 409, r.text


def test_create_case_draft_id_without_docs_marks_consumed(client: TestClient, db_session):
    tenant_id = _setup_tenant_user(db_session, email="reg.nodocs@example.com")
    draft = _make_draft(db_session, tenant_id)
    db_session.commit()
    headers = _login(client, "reg.nodocs@example.com")

    payload = {**_PAYLOAD, "draft_id": draft.id}
    r = client.post("/api/v1/intake/create-case", json=payload, headers=headers)

    assert r.status_code == 201, r.text
    db_session.expire_all()
    migrated_draft = db_session.query(IntakeDraft).filter_by(id=draft.id).one()
    assert migrated_draft.state == IntakeDraftState.card_criado
