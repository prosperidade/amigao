"""Roteamento de arquivos geoespaciais no /import do intake (fix/intake-geo-routing).

Reproduz e fixa o sintoma de produção: subir um .kml caía no pipeline de OCR de
PDF e estourava cascata de erros. Agora arquivos geoespaciais são roteados para
fora do OCR (ocr_status=not_required, document_type=geoespacial) e NÃO disparam a
task ocr_then_extract — só PDFs/documentos reais é que entram no pipeline.
"""
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.document import Document, DocumentSource, OcrStatus
from app.models.intake_draft import IntakeDraft
from app.models.tenant import Tenant
from app.models.user import User


def _login(tc: TestClient, email: str, password: str) -> dict[str, str]:
    resp = tc.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _make_user_and_draft(db_session, *, email: str) -> tuple[int, int]:
    tenant = Tenant(name=f"T Geo {email}")
    db_session.add(tenant)
    db_session.flush()
    user = User(
        email=email,
        full_name="Consultor Geo",
        hashed_password=get_password_hash("Consultor1"),
        tenant_id=tenant.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    draft = IntakeDraft(tenant_id=tenant.id, created_by_user_id=user.id)
    db_session.add(draft)
    db_session.commit()
    return tenant.id, draft.id


def _add_doc(db_session, *, tenant_id, draft_id, filename, content_type) -> int:
    doc = Document(
        tenant_id=tenant_id,
        intake_draft_id=draft_id,
        original_file_name=filename,
        filename=filename,
        content_type=content_type,
        mime_type=content_type,
        extension=filename.rsplit(".", 1)[-1].lower(),
        storage_key=f"drafts/{draft_id}/{filename}",
        ocr_status=OcrStatus.pending,
        source=DocumentSource.intake,
    )
    db_session.add(doc)
    db_session.commit()
    return doc.id


def test_import_roteia_kml_para_fora_do_ocr(client: TestClient, db_session, monkeypatch):
    tenant_id, draft_id = _make_user_and_draft(db_session, email="geo.kml@example.com")
    headers = _login(client, "geo.kml@example.com", "Consultor1")

    kml_id = _add_doc(
        db_session, tenant_id=tenant_id, draft_id=draft_id,
        filename="imovel.kml", content_type="application/octet-stream",
    )
    pdf_id = _add_doc(
        db_session, tenant_id=tenant_id, draft_id=draft_id,
        filename="matricula.pdf", content_type="application/pdf",
    )

    # Captura quais doc_ids são despachados pro OCR sem rodar Celery de verdade.
    dispatched: list[int] = []
    fake_delay = MagicMock(side_effect=lambda **kw: dispatched.append(kw["doc_id"]) or MagicMock(id="task-x"))
    import app.workers.ocr_tasks as ocr_tasks
    monkeypatch.setattr(ocr_tasks.ocr_then_extract, "delay", fake_delay)

    resp = client.post(f"/api/v1/intake/drafts/{draft_id}/import", json={}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Só o PDF entrou na fila de OCR; o KML foi contabilizado como geoespacial.
    assert body["docs_queued"] == 1
    assert body["docs_skipped_geo"] == 1
    assert dispatched == [pdf_id]

    # KML: armazenado, fora do OCR, classificado como geoespacial.
    kml = db_session.get(Document, kml_id)
    assert kml.ocr_status == OcrStatus.not_required
    assert kml.document_type == "geoespacial"

    # PDF: segue pendente na fila do worker.
    pdf = db_session.get(Document, pdf_id)
    assert pdf.ocr_status == OcrStatus.pending


def test_import_so_geo_nao_enfileira_nada(client: TestClient, db_session, monkeypatch):
    tenant_id, draft_id = _make_user_and_draft(db_session, email="geo.only@example.com")
    headers = _login(client, "geo.only@example.com", "Consultor1")
    _add_doc(
        db_session, tenant_id=tenant_id, draft_id=draft_id,
        filename="area.geojson", content_type="application/geo+json",
    )

    dispatched: list[int] = []
    fake_delay = MagicMock(side_effect=lambda **kw: dispatched.append(kw["doc_id"]) or MagicMock(id="t"))
    import app.workers.ocr_tasks as ocr_tasks
    monkeypatch.setattr(ocr_tasks.ocr_then_extract, "delay", fake_delay)

    resp = client.post(f"/api/v1/intake/drafts/{draft_id}/import", json={}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["docs_queued"] == 0
    assert body["docs_skipped_geo"] == 1
    assert dispatched == []
