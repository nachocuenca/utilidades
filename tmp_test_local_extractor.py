from src.ai.local_extractor import LocalExtractor
import json
extr = LocalExtractor()
pdfs = [
    'data/inbox/FACT 220224 DE SPARK A BENIOFFI.pdf',
    'data/inbox/Factura_2026001374M000001_001.pdf'
]
results = {}
for pdf in pdfs:
    before = extr.extract_from_pdf(pdf)
    results[pdf] = {'antes': before}
    # Leer texto OCR real
    from src.pdf.reader import read_pdf_text_only
    ocr_text = read_pdf_text_only(pdf)
    after = extr._postprocess_extraction(before, ocr_text, [])
    results[pdf]['despues'] = after
print(json.dumps(results, ensure_ascii=False, indent=2))
