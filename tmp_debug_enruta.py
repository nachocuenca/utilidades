from src.ai.local_extractor import LocalExtractor
from config.settings import get_settings
from src.pdf.reader import read_pdf_text_only
import json

pdf = 'data/inbox/Factura_2026001374M000001_001.pdf'
extr = LocalExtractor()
settings = get_settings()

# 1. ANTES: solo extracción bruta
antes = extr._extract_with_ollama(pdf, settings)
print('ANTES:')
print(json.dumps(antes, ensure_ascii=False, indent=2))

# 2. DESPUÉS: postproceso determinista con depuración
ocr_text = read_pdf_text_only(pdf)
# Inyectar pdf_path en extraction para la rama ENRUTA
antes['pdf_path'] = pdf

despues = extr._postprocess_extraction(antes, ocr_text, [])
print('\nDESPUÉS:')
print(json.dumps(despues, ensure_ascii=False, indent=2))
