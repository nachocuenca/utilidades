import pytest
from src.parsers.daniel_fernandez import DanielFernandezInvoiceParser
from src.pdf.extract_text_with_fallback import extract_text_with_fallback

PDF_PATH = "data/inbox/FACT 220224 DE SPARK A BENIOFFI.pdf"

@pytest.mark.parametrize("pdf_path,expected_num,expected_fecha,expected_total", [
    (PDF_PATH, "220224", "2026-03-27", 664.29),
])
def test_daniel_fernandez_factura_real(pdf_path, expected_num, expected_fecha, expected_total):
    text = extract_text_with_fallback(pdf_path)
    parser = DanielFernandezInvoiceParser()
    parsed = parser.parse(text, pdf_path)
    assert parsed.numero_factura == expected_num
    assert parsed.fecha_factura == expected_fecha
    assert abs(parsed.total - expected_total) < 0.01
