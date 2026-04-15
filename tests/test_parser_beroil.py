from src.parsers.beroil import BeroilInvoiceParser
from src.pdf.extract_text_with_fallback import extract_text_with_fallback

def test_beroil_factura_real():
    path = r"data/inbox/Factura_26D013477-00110790- (1 de 2).PDF"
    text = extract_text_with_fallback(path)
    parser = BeroilInvoiceParser()
    parsed = parser.parse(text, path)
    assert parsed.numero_factura == "26D013477"
    assert parsed.fecha_factura == "2026-03-31"
    assert abs(parsed.total - 70.0) < 0.01
