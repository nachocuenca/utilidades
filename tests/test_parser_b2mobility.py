import pytest
from src.parsers.b2mobility import B2MobilityInvoiceParser
from src.pdf.extract_text_with_fallback import extract_text_with_fallback

PDF_PATH = "data/inbox/260331-2-ES-NI-0264041084-237952-990403EM10453-INV.pdf"

@pytest.mark.parametrize("pdf_path,expected_num,expected_fecha,expected_total", [
    (PDF_PATH, "0264041084", "2026-03-31", 653.21),
])
def test_b2mobility_factura_real(pdf_path, expected_num, expected_fecha, expected_total):
    text = extract_text_with_fallback(pdf_path)
    parser = B2MobilityInvoiceParser()
    parsed = parser.parse(text, pdf_path)
    assert parsed.numero_factura == expected_num
    assert parsed.fecha_factura == expected_fecha
    assert abs(parsed.total - expected_total) < 0.01
