import pytesseract
import os

# Configuración de tesseract_cmd para Windows
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

# Fallback de idioma
TESSDATA_PATH = r"C:\Program Files\Tesseract-OCR\tessdata"
def _detect_language(requested: str) -> str:
    if requested == "spa" and not os.path.exists(os.path.join(TESSDATA_PATH, "spa.traineddata")):
        return "eng"
    return requested

from pathlib import Path
from src.pdf.reader import _read_with_pdfplumber, _read_with_pypdf
from src.pdf.ocr import ocr_pdf_text, has_meaningful_text
from src.pdf.text_cleaner import normalize_pdf_text

def extract_text_with_fallback(pdf_path: str | Path, min_text_length: int = 30, language: str = "spa", dpi: int = 200, tesseract_cmd: str | None = None) -> str:
    path = Path(pdf_path).resolve()
    # 1. Intentar pdfplumber
    try:
        raw_text, _ = _read_with_pdfplumber(path)
        cleaned = normalize_pdf_text(raw_text)
        if has_meaningful_text(cleaned, min_text_length):
            return cleaned
    except Exception:
        pass
    # 2. Intentar pypdf
    try:
        raw_text, _ = _read_with_pypdf(path)
        cleaned = normalize_pdf_text(raw_text)
        if has_meaningful_text(cleaned, min_text_length):
            return cleaned
    except Exception:
        pass
    # 3. Fallback OCR
    lang = _detect_language(language)
    ocr_result = ocr_pdf_text(path, language=lang, dpi=dpi, tesseract_cmd=tesseract_cmd or TESSERACT_PATH)
    return ocr_result.text
