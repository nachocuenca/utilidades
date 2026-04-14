from pathlib import Path
from src.ai.local_extractor import LocalExtractor

# Lightweight settings object to avoid importing dotenv in this quick test
class S:
    local_model_name = 'qwen2.5vl:7b'
    ollama_base_url = 'http://localhost:11434/api'
    ocr_render_dpi = 200

settings = S()
print("Using Ollama base URL:", settings.ollama_base_url)
print("Using model:", settings.local_model_name)

pdf = Path('data/runtime_probe_scan/factura-00130.pdf')
if not pdf.exists():
    # fallback to another available pdf
    pdf = next(Path('data/runtime_probe_scan').glob('*.pdf'))
    print('Fallback chosen PDF:', pdf)

ext = LocalExtractor()
try:
    res = ext._extract_with_ollama(str(pdf), settings)
    print('\n=== PARSED JSON ===')
    import json
    print(json.dumps(res, ensure_ascii=False, indent=2))
except Exception as e:
    print('\n=== ERROR ===')
    print(str(e))

print('\nDone')
