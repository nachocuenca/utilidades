import pytest
from src.parsers.rpg_carvin import RpgCarvinInvoiceParser
from src.pdf.extract_text_with_fallback import extract_text_with_fallback

PDF_PATH = "data/inbox/Factura_20261867.pdf"

@pytest.mark.parametrize("pdf_path,expected_num,expected_fecha,expected_total", [
    (PDF_PATH, "20261867", "2026-03-31", 168.52),
])
def test_rpg_carvin_factura_real(pdf_path, expected_num, expected_fecha, expected_total):
    text = extract_text_with_fallback(pdf_path)
    parser = RpgCarvinInvoiceParser()
    parsed = parser.parse(text, pdf_path)
    assert parsed.numero_factura == expected_num
    assert parsed.fecha_factura == expected_fecha
    assert abs(parsed.total - expected_total) < 0.01
