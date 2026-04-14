from pathlib import Path
import base64
import io
import json
import re

from src.ai.local_extractor import LocalExtractor

# minimal settings for test
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

# Render images and inspect sizes
images_b64 = ext._render_pdf_pages_to_base64(str(pdf), dpi=settings.ocr_render_dpi, max_pages=4)
print('Pages rendered:', len(images_b64))
image_infos = []
for i, b64 in enumerate(images_b64, start=1):
    data = base64.b64decode(b64)
    from PIL import Image
    im = Image.open(io.BytesIO(data))
    image_infos.append({'index': i, 'format': im.format, 'size': im.size, 'mode': im.mode, 'bytes': len(data)})
    print(f"Image {i}: format={im.format}, size={im.size}, mode={im.mode}, bytes={len(data)}")

# Build payload shape (without base64 dumps)
payload = {
    'model': settings.local_model_name,
    'messages': [
        {'role': 'system', 'content': 'Eres un extractor que devuelve SOLO JSON estructurado según el esquema solicitado.'},
        {'role': 'user', 'content': 'Procesa las imágenes adjuntas (páginas de una factura) y devuelve EXACTAMENTE un objeto JSON con los campos: tipo_documento, nombre_proveedor, nif_proveedor, nombre_cliente, nif_cliente, cp_cliente, numero_factura, fecha_factura, subtotal, iva, total, confidence, warnings, evidence_snippets. Devuelve null para campos no disponibles. No agregues texto adicional, solo JSON.'}
    ],
    'images': ['<BASE64_IMAGE_%d>' % i for i in range(1, len(images_b64)+1)],
    'format': '<json_schema>',
    'temperature': 0,
    'stream': False,
    'raw': False,
}

print('Ollama endpoint:', settings.ollama_base_url.rstrip('/') + '/chat')
print('Payload keys:', list(payload.keys()))
print('Images sent (count):', len(images_b64))

# Now actually POST to Ollama and capture raw response
import requests
url = settings.ollama_base_url.rstrip('/') + '/chat'
# Rebuild a real payload but avoid printing huge base64 content
real_payload = {
    'model': payload['model'],
    'messages': payload['messages'],
    'images': images_b64,
    'format': {
        'type': 'object',
        'properties': {
            'tipo_documento': {'type': 'string'},
            'nombre_proveedor': {'type': ['string', 'null']},
            'nif_proveedor': {'type': ['string', 'null']},
            'nombre_cliente': {'type': ['string', 'null']},
            'nif_cliente': {'type': ['string', 'null']},
            'cp_cliente': {'type': ['string', 'null']},
            'numero_factura': {'type': ['string', 'null']},
            'fecha_factura': {'type': ['string', 'null']},
            'subtotal': {'type': ['number', 'null']},
            'iva': {'type': ['number', 'null']},
            'total': {'type': ['number', 'null']},
            'confidence': {'type': 'number'},
            'warnings': {'type': 'array', 'items': {'type': 'string'}},
            'evidence_snippets': {'type': 'array', 'items': {'type': 'string'}}
        },
        'required': ['tipo_documento', 'confidence', 'warnings', 'evidence_snippets']
    },
    'temperature': 0,
    'stream': False,
    'raw': False,
}

print('\nPosting to Ollama... (this may take a while)')
resp = requests.post(url, json=real_payload, timeout=600)
resp.raise_for_status()
body = resp.json()

# Extract RAW message.content
generated = None
if isinstance(body.get('message'), dict):
    generated = body['message'].get('content')
elif isinstance(body.get('response'), dict):
    generated = body['response'].get('content') or body['response'].get('response')
elif isinstance(body.get('choices'), list) and body['choices']:
    first = body['choices'][0]
    if isinstance(first, dict) and isinstance(first.get('message'), dict):
        generated = first['message'].get('content')
    else:
        generated = first.get('content') if isinstance(first, dict) else None
else:
    generated = body.get('response')

print('\n=== RAW message.content from Ollama ===')
print(generated if generated is not None else json.dumps(body, ensure_ascii=False))

# Attempt to parse JSON
parsed = None
parse_error = None
try:
    parsed = json.loads(generated) if isinstance(generated, str) else generated
except Exception as e:
    parse_error = str(e)

print('\n=== PARSED JSON ===')
if parsed is not None:
    print(json.dumps(parsed, ensure_ascii=False, indent=2))
else:
    print('JSON parse error:', parse_error)

# Check for placeholders
placeholders = ['Empresa XYZ', 'Cliente ABC', 'A12345678', 'B98765432', '12345', 'Empresa', 'Cliente']
found_placeholders = []
if parsed:
    for k, v in parsed.items():
        if isinstance(v, str):
            for p in placeholders:
                if p in v:
                    found_placeholders.append((k, v))

print('\nContains placeholder/template values?:', bool(found_placeholders))
if found_placeholders:
    print('Found placeholders in fields:')
    for k, v in found_placeholders:
        print('-', k, ':', v)

# Finally, call validator
from src.ai.validator import InvoiceAIValidator
if parsed:
    is_valid, warnings = InvoiceAIValidator.validate(parsed)
    print('\nValidator: is_valid=', is_valid)
    print('Validator warnings=', warnings)
else:
    print('\nValidator skipped due to parse error')

print('\nDone')
