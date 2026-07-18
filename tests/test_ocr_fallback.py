from src.pdf.extract_text_with_fallback import extract_text_with_fallback

def test_ocr_fallback_leeroy_merlin():
    path = "data/inbox/SESCANER - 26040817090.pdf"
    text = extract_text_with_fallback(path, min_text_length=30, language="spa")
    assert text and len(text) > 30, "El texto extraído por OCR no debe estar vacío"
    assert "leroy" in text.lower(), "Debe aparecer 'leroy' en el texto extraído"
    assert "total" in text.lower(), "Debe aparecer 'total' en el texto extraído"
