"""OCR failed (2026-06-06) — endpoint de reprocesso de OCR.

Resolve o "failed permanente": o consultor reprocessa um doc failed (de PROCESSO
ou de RASCUNHO). Antes, só `POST /processes/{id}/extract` existia — e não cobria
docs de draft (process_id null), exatamente o caso São Jorge.
"""

import app.workers.ocr_tasks as ocr_tasks_mod
from app.core.security import get_password_hash
from app.models.document import Document, OcrStatus
from app.models.tenant import Tenant
from app.models.user import User


class _FakeTask:
    id = "task-reprocess-1"


def _login(tc, email, password):
    resp = tc.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _seed_user(db_session, *, tenant_name, email):
    tenant = Tenant(name=tenant_name)
    db_session.add(tenant)
    db_session.flush()
    user = User(email=email, full_name="C", hashed_password=get_password_hash("Consultor1"),
                tenant_id=tenant.id, is_active=True)
    db_session.add(user)
    db_session.commit()
    return tenant


def _failed_pdf(db_session, tenant_id, *, draft=True):
    doc = Document(
        tenant_id=tenant_id,
        intake_draft_id=None,  # draft id é opcional; o doc pode estar só em draft conceitual
        original_file_name="CCIR.pdf", filename="ccir.pdf",
        content_type="application/pdf", storage_key=f"tenant_{tenant_id}/draft_x/ccir-{tenant_id}.pdf",
        ocr_status=OcrStatus.failed, ocr_error="Falha ao baixar do storage (SignatureDoesNotMatch).",
    )
    db_session.add(doc)
    db_session.commit()
    return doc


def test_reprocess_ocr_reenfileira_e_limpa_erro(client, db_session, monkeypatch):
    tenant = _seed_user(db_session, tenant_name="T Reproc", email="reproc@example.com")
    headers = _login(client, "reproc@example.com", "Consultor1")
    doc = _failed_pdf(db_session, tenant.id)

    captured = {}
    monkeypatch.setattr(ocr_tasks_mod.ocr_then_extract, "delay",
                        lambda **kw: captured.update(kw) or _FakeTask())

    resp = client.post(f"/api/v1/documents/{doc.id}/reprocess-ocr", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ocr_status"] == "processing"
    assert body["task_id"] == "task-reprocess-1"
    # re-enfileirou com force=True (re-baixa do storage, ignora cache)
    assert captured["force"] is True
    assert captured["doc_id"] == doc.id

    db_session.refresh(doc)
    assert doc.ocr_status == OcrStatus.processing
    assert doc.ocr_error is None  # erro limpo ao reprocessar


def test_reprocess_ocr_404_doc_inexistente(client, db_session):
    _seed_user(db_session, tenant_name="T Reproc404", email="reproc404@example.com")
    headers = _login(client, "reproc404@example.com", "Consultor1")
    resp = client.post("/api/v1/documents/999999/reprocess-ocr", headers=headers)
    assert resp.status_code == 404


def test_reprocess_ocr_422_nao_pdf(client, db_session, monkeypatch):
    tenant = _seed_user(db_session, tenant_name="T Reproc422", email="reproc422@example.com")
    headers = _login(client, "reproc422@example.com", "Consultor1")
    doc = Document(
        tenant_id=tenant.id, original_file_name="x.docx", filename="x.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        storage_key=f"tenant_{tenant.id}/x.docx", ocr_status=OcrStatus.failed,
    )
    db_session.add(doc)
    db_session.commit()
    resp = client.post(f"/api/v1/documents/{doc.id}/reprocess-ocr", headers=headers)
    assert resp.status_code == 422
