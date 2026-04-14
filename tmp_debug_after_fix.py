from pathlib import Path
import json

from src.ai.local_extractor import LocalExtractor

class S:
    local_model_name = 'qwen2.5vl:7b'
    ollama_base_url = 'http://localhost:11434/api'
    ocr_render_dpi = 200

settings = S()

inbox = Path('data/inbox')
files = list(inbox.glob('*.pdf'))
if not files:
    raise SystemExit('No PDFs found in data/inbox')
pdf = files[0]
print('PDF path used:', str(pdf))

ext = LocalExtractor()
try:
    extraction, raw = ext._extract_with_ollama(str(pdf), settings, debug=True)
    print('\n=== RAW message.content from Ollama ===')
    print(raw)
    print('\n=== PARSED JSON ===')
    print(json.dumps(extraction, ensure_ascii=False, indent=2))

    from src.ai.validator import InvoiceAIValidator
    is_valid, warnings = InvoiceAIValidator.validate(extraction)
    print('\n=== VALIDATOR RESULT ===')
    print('is_valid:', is_valid)
    print('warnings:', warnings)
except Exception as e:
    print('\n=== ERROR ===')
    print(str(e))

print('\nDone')
