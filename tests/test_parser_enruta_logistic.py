import pytest
from src.parsers.enruta_logistic import EnrutaLogisticInvoiceParser
from src.pdf.extract_text_with_fallback import extract_text_with_fallback

PDF_PATH = "data/inbox/Factura_2026001374M000001_001.pdf"

@pytest.mark.parametrize("pdf_path,expected_num,expected_fecha,expected_total", [
    (PDF_PATH, "2026001374M", "2026-03-31", 184.75),
])
def test_enruta_logistic_factura_real(pdf_path, expected_num, expected_fecha, expected_total):
    text = extract_text_with_fallback(pdf_path)
    parser = EnrutaLogisticInvoiceParser()
    parsed = parser.parse(text, pdf_path)
    assert parsed.numero_factura == expected_num
    assert parsed.fecha_factura == expected_fecha
    assert abs(parsed.total - expected_total) < 0.01
