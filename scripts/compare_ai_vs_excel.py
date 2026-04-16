import pandas as pd
import json
from pathlib import Path
from src.ai.local_extractor import LocalExtractor

# Config
EXCEL_PATH = Path('data/acreedores benioffi.xlsx')
PDF_DIR = Path('data/runtime_probe_scan')
SHEET = 'facturas_20260414_124915'
COLUMNS = [
    'ruta_archivo', 'nombre_proveedor', 'nif_proveedor', 'nombre_cliente', 'nif_cliente',
    'cp_cliente', 'numero_factura', 'fecha_factura', 'subtotal', 'iva', 'total'
]

# Load Excel
excel = pd.read_excel(EXCEL_PATH, sheet_name=SHEET, dtype=str)
excel = excel[COLUMNS]

 # Map by base name (ignore path/extension)
pdf_map = {}
pdf_basenames = {p.stem: p for p in PDF_DIR.glob('*.pdf')}
for ix, row in excel.iterrows():
    ruta = Path(str(row['ruta_archivo'])).stem
    if ruta in pdf_basenames:
        pdf_map[pdf_basenames[ruta]] = row

# Run extractor and compare
ext = LocalExtractor()
results = []
for i, (pdf, truth) in enumerate(pdf_map.items()):
    if i >= 5:
        break
    ai = ext.extract_from_pdf(str(pdf))
    mismatches = {}
    for col in COLUMNS[1:]:
        ai_val = ai.get(col)
        truth_val = truth[col]
        if isinstance(ai_val, float):
            try:
                truth_val = float(truth_val)
            except Exception:
                pass
        if str(ai_val).strip() != str(truth_val).strip():
            mismatches[col] = {'ai': ai_val, 'truth': truth_val}
    results.append({
        'pdf': pdf.name,
        'ai': {k: ai.get(k) for k in COLUMNS[1:]},
        'truth': {k: truth[k] for k in COLUMNS[1:]},
        'mismatch': mismatches
    })

# Output
for r in results:
    print('\n---')
    print('PDF:', r['pdf'])
    print('AI:', json.dumps(r['ai'], ensure_ascii=False))
    print('Excel:', json.dumps(r['truth'], ensure_ascii=False))
    print('Mismatch:', json.dumps(r['mismatch'], ensure_ascii=False))
