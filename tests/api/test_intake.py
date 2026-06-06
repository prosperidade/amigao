"""
Testes da API de Intake — campos derivados + UX (decisões Isis 2026-05-28).

Cobre:
  - E-mail OBRIGATÓRIO no contato (422 quando vazio/ausente).
  - Áudio da entrevista carregado no draft (audio_url persistido).
  - Reconciliação cliente × IA: POST /reconcile atualiza field_sources.
  - Preview lateral: GET /extracted-fields responde (vazio sem docs).
"""
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.tenant import Tenant
from app.models.user import User


def _login(tc: TestClient, email: str, password: str) -> dict[str, str]:
    resp = tc.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _make_user(db_session, *, tenant_name: str, email: str) -> None:
    tenant = Tenant(name=tenant_name)
    db_session.add(tenant)
    db_session.flush()
    user = User(
        email=email,
        full_name="Consultor Intake",
        hashed_password=get_password_hash("Consultor1"),
        tenant_id=tenant.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()


def test_create_case_empty_email_returns_422(client: TestClient, db_session):
    """E-mail é obrigatório (decisão Isis): create-case com e-mail vazio → 422."""
    _make_user(db_session, tenant_name="T Intake Email", email="intake.email@example.com")
    headers = _login(client, "intake.email@example.com", "Consultor1")

    resp = client.post(
        "/api/v1/intake/create-case",
        json={
            "new_client": {
                "full_name": "Cliente Sem Email",
                "phone": "11999990000",
                "email": "",  # vazio → deve falhar a validação
                "client_type": "pf",
            },
            "new_property": {"name": "Fazenda X"},
            "description": "Demanda qualquer de licenciamento ambiental rural",
        },
        headers=headers,
    )
    assert resp.status_code == 422


def test_create_case_missing_email_returns_422(client: TestClient, db_session):
    """create-case sem o campo e-mail no new_client → 422 (campo obrigatório)."""
    _make_user(db_session, tenant_name="T Intake NoEmail", email="intake.noemail@example.com")
    headers = _login(client, "intake.noemail@example.com", "Consultor1")

    resp = client.post(
        "/api/v1/intake/create-case",
        json={
            "new_client": {
                "full_name": "Cliente Sem Campo Email",
                "phone": "11999990000",
                "client_type": "pf",
            },
            "new_property": {"name": "Fazenda Y"},
            "description": "Demanda qualquer de licenciamento ambiental rural",
        },
        headers=headers,
    )
    assert resp.status_code == 422


def test_draft_carries_audio_url(client: TestClient, db_session):
    """Áudio da entrevista (audio_url) é aceito e persistido no draft."""
    _make_user(db_session, tenant_name="T Intake Audio", email="intake.audio@example.com")
    headers = _login(client, "intake.audio@example.com", "Consultor1")

    resp = client.post(
        "/api/v1/intake/drafts",
        json={
            "entry_type": "novo_cliente_novo_imovel",
            "form_data": {
                "new_client": {
                    "full_name": "Cliente Com Audio",
                    "phone": "11999990000",
                    "email": "audio@example.com",
                    "client_type": "pf",
                },
                "new_property": {"name": "Fazenda Audio"},
                "audio_url": "intake-audio/entrevista-123.mp3",
            },
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["form_data"]["audio_url"] == "intake-audio/entrevista-123.mp3"


def test_reconcile_updates_field_sources(client: TestClient, db_session):
    """POST /drafts/{id}/reconcile grava a origem escolhida em field_sources."""
    _make_user(db_session, tenant_name="T Intake Reconcile", email="intake.recon@example.com")
    headers = _login(client, "intake.recon@example.com", "Consultor1")

    # cria draft com um valor manual de CAR
    create = client.post(
        "/api/v1/intake/drafts",
        json={
            "entry_type": "novo_cliente_novo_imovel",
            "form_data": {
                "new_client": {
                    "full_name": "Cliente Recon",
                    "phone": "11999990000",
                    "email": "recon@example.com",
                    "client_type": "pf",
                },
                "new_property": {"name": "Fazenda Recon", "car_number": "GO-MANUAL-001"},
            },
        },
        headers=headers,
    )
    assert create.status_code == 201
    draft_id = create.json()["id"]

    # consultor escolhe o valor EXTRAÍDO pela IA para o campo car_numero
    resp = client.post(
        f"/api/v1/intake/drafts/{draft_id}/reconcile",
        json={"field": "car_numero", "source": "extracted", "value": "GO-IA-999"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["field"] == "car_numero"
    assert body["source"] == "extracted"
    assert body["field_sources"]["car_numero"] == "extracted"

    # o draft persistiu field_sources + valor reconciliado
    got = client.get(f"/api/v1/intake/drafts/{draft_id}", headers=headers)
    assert got.status_code == 200
    fd = got.json()["form_data"]
    assert fd["field_sources"]["car_numero"] == "extracted"
    assert fd["reconciled"]["car_numero"] == "GO-IA-999"


def test_reconcile_invalid_source_returns_422(client: TestClient, db_session):
    """source fora de {manual, extracted} → 422."""
    _make_user(db_session, tenant_name="T Intake ReconBad", email="intake.reconbad@example.com")
    headers = _login(client, "intake.reconbad@example.com", "Consultor1")

    create = client.post(
        "/api/v1/intake/drafts",
        json={"entry_type": "novo_cliente_novo_imovel", "form_data": {}},
        headers=headers,
    )
    draft_id = create.json()["id"]

    resp = client.post(
        f"/api/v1/intake/drafts/{draft_id}/reconcile",
        json={"field": "car_numero", "source": "chute", "value": "x"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_extracted_fields_empty_without_docs(client: TestClient, db_session):
    """GET /drafts/{id}/extracted-fields responde vazio quando não há docs/extração."""
    _make_user(db_session, tenant_name="T Intake Preview", email="intake.preview@example.com")
    headers = _login(client, "intake.preview@example.com", "Consultor1")

    create = client.post(
        "/api/v1/intake/drafts",
        json={"entry_type": "novo_cliente_novo_imovel", "form_data": {}},
        headers=headers,
    )
    draft_id = create.json()["id"]

    resp = client.get(f"/api/v1/intake/drafts/{draft_id}/extracted-fields", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["draft_id"] == draft_id
    assert data["fields"] == []
    assert data["has_divergence"] is False


def test_extracted_fields_excludes_confidence_map_and_maps_score(client: TestClient, db_session):
    """Regressão: o mapa `confidence` do extrator virava um campo
    'Confidence: [object Object]' e os campos ficavam 's/ score'. Agora o mapa é
    metadado — pontua cada campo e NÃO aparece como linha."""
    from app.models.ai_job import AIJob, AIJobStatus, AIJobType
    from app.models.document import Document

    _make_user(db_session, tenant_name="T Conf Preview", email="conf.preview@example.com")
    headers = _login(client, "conf.preview@example.com", "Consultor1")
    user = db_session.query(User).filter(User.email == "conf.preview@example.com").first()

    create = client.post(
        "/api/v1/intake/drafts",
        json={"entry_type": "novo_cliente_novo_imovel", "form_data": {}},
        headers=headers,
    )
    draft_id = create.json()["id"]

    doc = Document(
        tenant_id=user.tenant_id,
        intake_draft_id=draft_id,
        filename="cert.pdf",
        content_type="application/pdf",
        original_file_name="Certidao 4698.pdf",
        document_type="matricula",
        storage_key="drafts/cert.pdf",
    )
    db_session.add(doc)
    db_session.flush()

    db_session.add(AIJob(
        tenant_id=user.tenant_id,
        job_type=AIJobType.extract_document,
        agent_name="extrator",
        status=AIJobStatus.completed,
        result={
            "document_id": doc.id,
            "extracted_fields": {
                "denominacao_imovel": "FAZENDA SÃO JORGE – GLEBA 01 B",
                "area_ha": 660.6561,
                "confidence": {"denominacao_imovel": "high", "area_ha": "medium"},
            },
        },
    ))
    db_session.commit()

    resp = client.get(f"/api/v1/intake/drafts/{draft_id}/extracted-fields", headers=headers)
    assert resp.status_code == 200
    by_field = {f["field"]: f for f in resp.json()["fields"]}

    assert "confidence" not in by_field  # mapa de scores não é campo
    assert by_field["denominacao_imovel"]["value"] == "FAZENDA SÃO JORGE – GLEBA 01 B"
    assert by_field["denominacao_imovel"]["confidence"] == 0.95  # high
    assert by_field["area_ha"]["confidence"] == 0.8  # medium
