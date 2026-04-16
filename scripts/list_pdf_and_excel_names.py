import pandas as pd
from pathlib import Path

EXCEL_PATH = Path('data/acreedores benioffi.xlsx')
PDF_DIR = Path('data/runtime_probe_scan')
SHEET = 'facturas_20260414_124915'

excel = pd.read_excel(EXCEL_PATH, sheet_name=SHEET, dtype=str)
pdf_names = sorted([p.name for p in PDF_DIR.glob('*.pdf')])
ruta_archivo_names = sorted(set(Path(str(r)).name for r in excel['ruta_archivo']))

print('PDFs en runtime_probe_scan:')
for n in pdf_names:
    print(n)
print('\nValores únicos de ruta_archivo en Excel:')
for n in ruta_archivo_names:
    print(n)
