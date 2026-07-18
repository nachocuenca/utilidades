import csv
import json
from pathlib import Path

# Directory with JSON extraction outputs
INPUT_DIR = Path(__file__).resolve().parents[1] / 'output'
OUTPUT_CSV = INPUT_DIR / 'acreedores_benioffi_from_json.csv'

fields = [
    'nombre_proveedor', 'nif_proveedor', 'nombre_cliente', 'nif_cliente',
    'cp_cliente', 'numero_factura', 'subtotal', 'iva', 'total', 'tipo_documento', 'pdf_path', 'raw_model_output'
]

json_files = list(INPUT_DIR.glob('*.json'))
if not json_files:
    print('No JSON files found in', INPUT_DIR)
    exit(0)

with OUTPUT_CSV.open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding='utf-8'))
        except Exception as e:
            print('Skipping', jf.name, 'read error:', e)
            continue
        row = {k: data.get(k) for k in fields}
        writer.writerow(row)

print('Wrote', OUTPUT_CSV)
