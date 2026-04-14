from pathlib import Path
from src.ai.local_extractor import LocalExtractor
from src.ai.validator import InvoiceAIValidator
import json

# minimal settings as in previous quick script
class S:
    local_model_name = 'qwen2.5vl:7b'
    ollama_base_url = 'http://localhost:11434/api'
    ocr_render_dpi = 200

settings = S()

pdf = Path('data/runtime_probe_scan/factura-00130.pdf')
if not pdf.exists():
    pdf = next(Path('data/runtime_probe_scan').glob('*.pdf'))
    print('Fallback chosen PDF:', pdf)

ext = LocalExtractor()
try:
    extraction = ext._extract_with_ollama(str(pdf), settings)
    print('\n=== RAW JSON (as received and parsed) ===')
    print(json.dumps(extraction, ensure_ascii=False, indent=2))

    # Run validator
    is_valid, warnings = InvoiceAIValidator.validate(extraction)
    print('\n=== VALIDATOR RESULT ===')
    print('is_valid:', is_valid)
    print('warnings:', warnings)
except Exception as e:
    print('\n=== ERROR ===')
    print(str(e))

print('\nDone')
