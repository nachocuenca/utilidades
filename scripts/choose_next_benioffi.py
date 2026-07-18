import os, sys, re
import pandas as pd
from src.pdf.extract_text_with_fallback import extract_text_with_fallback

xls = r'c:/Users/ignac/Desktop/utilidadesgit/data/acreedores benioffi.xlsx'
sheet = 'facturas_20260414_124915'

df = pd.read_excel(xls, sheet_name=sheet)
# exclude closed providers
exclude = [p.lower() for p in ['Leroy Merlin','BEROIL','RPG CARVIN','ENRUTA LOGISTIC','B2Mobility']]
# list real pdfs
pdfs = os.listdir('data/inbox')
# normalize ruta_archivo basenames
if 'ruta_archivo' not in df.columns:
    print('A. ERROR')
    print('B. ERROR')
    print('C. BLOQUEADO')
    print('D. motivo exacto: columna ruta_archivo no encontrada en Excel')
    sys.exit(0)

df['basename'] = df['ruta_archivo'].astype(str).str.strip().apply(lambda x: os.path.basename(x))
mask = df['basename'].isin(pdfs)
candidates = df[mask & ~df['nombre_proveedor'].astype(str).str.lower().isin(exclude)][['nombre_proveedor','ruta_archivo','basename']]
uniq = candidates.drop_duplicates(subset=['nombre_proveedor','basename']).head(20)

if uniq.empty:
    print('A. Ninguno')
    print('B. Ninguno')
    print('C. BLOQUEADO')
    print('D. motivo exacto: No hay candidatos tras cruzar basenames del Excel con data/inbox y excluir proveedores cerrados')
    sys.exit(0)

first = uniq.iloc[0]
prov = first['nombre_proveedor']
basename = first['basename']
pdf_path = os.path.join('data','inbox', basename)

# extract text
try:
    text = extract_text_with_fallback(pdf_path)
except Exception as e:
    print(f"A. {prov}")
    print(f"B. {pdf_path}")
    print('C. BLOQUEADO')
    print(f"D. motivo exacto: extract_text_with_fallback error: {e}")
    sys.exit(0)

up = text.upper()
parseable = False
reason = ''
if len(text.strip()) < 30:
    parseable = False
    reason = 'OCR too short'
elif 'FACTURA' in up or 'INVOICE' in up or re.search(r"\d{2}/\d{2}/\d{2,4}", text) or 'TOTAL' in up:
    parseable = True
    reason = 'Contains invoice markers or date/total'
else:
    parseable = False
    reason = 'No invoice markers (FACTURA/INVOICE/TOTAL/date) in OCR text'

print(f"A. {prov}")
print(f"B. {pdf_path}")
print(f"C. {'PARSEABLE' if parseable else 'BLOQUEADO'}")
print(f"D. {reason}")
