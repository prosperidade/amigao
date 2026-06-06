"""Guard "não é PDF" do orquestrador de OCR (fix/intake-geo-routing).

Garante que bytes não-PDF (ex.: KML mandado como octet-stream) falham LIMPO,
sem disparar a cascata pypdf→Gemini→OpenAI que estourava erros técnicos na UI.
Os ramos testados retornam ANTES de qualquer chamada a provider (sem rede).
"""

from app.services.ocr_pdf import extract_text_from_pdf


def test_bytes_nao_pdf_falha_limpo_sem_cascata():
    kml = (
        b'<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2">'
        b"<Placemark><Polygon/></Placemark></kml>"
    )
    res = extract_text_from_pdf(kml, mime_type="application/octet-stream")
    assert res.text == ""
    assert res.method == "none"
    assert res.provider == ""
    assert res.error is not None
    # Mensagem honesta (sem código técnico): orienta converter para PDF.
    assert "converta para pdf" in res.error.lower()
    # Custo zero e nenhum provider acionado.
    assert res.cost_usd == 0.0


def test_bytes_vazios():
    res = extract_text_from_pdf(b"", mime_type="application/pdf")
    assert res.error == "empty_bytes"
    assert res.method == "none"


def test_zip_shapefile_tambem_falha_limpo_no_guard():
    # Mesmo um .zip (PK\x03\x04) não-PDF é barrado limpo — sem assinatura %PDF.
    zip_magic = b"PK\x03\x04" + b"\x00" * 64
    res = extract_text_from_pdf(zip_magic, mime_type="application/zip")
    assert res.method == "none"
    assert res.error is not None
    assert "converta para pdf" in res.error.lower()
