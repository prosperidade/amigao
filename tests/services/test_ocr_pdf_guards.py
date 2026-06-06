"""OCR failed (2026-06-06) — guards de formato honestos no ocr_pdf."""

from app.services.ocr_pdf import extract_text_from_pdf


def test_docx_devolve_mensagem_honesta():
    """Word não é lido por OCR → mensagem clara (não código técnico)."""
    docx_bytes = b"PK\x03\x04 fake docx zip header"
    r = extract_text_from_pdf(
        docx_bytes,
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert r.text == ""
    assert "word" in (r.error or "").lower()
    assert "pdf" in (r.error or "").lower()


def test_nao_pdf_generico_orienta_converter():
    r = extract_text_from_pdf(b"not a pdf at all", mime_type="application/octet-stream")
    assert r.text == ""
    assert "converta para pdf" in (r.error or "").lower()


def test_vazio():
    r = extract_text_from_pdf(b"", mime_type="application/pdf")
    assert r.text == ""
    assert r.error
