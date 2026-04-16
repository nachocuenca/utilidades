import pandas as pd
import os
from src.pdf.extract_text_with_fallback import extract_text_with_fallback
from src.parsers.registry import ParserRegistry

# Cargar Excel y filtrar proveedor
excel = 'data/acreedores benioffi.xlsx'
sheet = 'facturas_20260414_124915'
df = pd.read_excel(excel, sheet_name=sheet)
df = df[df['nombre_proveedor'].str.lower().str.contains('leroy merlin')]

registry = ParserRegistry()
results = []

for _, row in df.iterrows():
    pdf = row['ruta_archivo']
    if not isinstance(pdf, str) or not os.path.exists(pdf):
        results.append({'archivo': pdf, 'factura_excel': row['numero_factura'], 'factura_parser': None, 'fecha_excel': row['fecha_factura'], 'fecha_parser': None, 'total_excel': row['total'], 'total_parser': None, 'OK': False, 'error': 'NO PDF'})
        continue
    text = extract_text_with_fallback(pdf)
    parser = registry.evaluate(text, pdf).selected_parser
    parsed = parser.parse(text, pdf)
    ok_fact = str(parsed.numero_factura).strip() == str(row['numero_factura']).strip()
    ok_fecha = str(parsed.fecha_factura).strip() == str(row['fecha_factura']).strip()
    ok_total = abs(float(parsed.total or 0) - float(row['total'] or 0)) < 0.02
    ok = ok_fact and ok_fecha and ok_total
    results.append({'archivo': pdf, 'factura_excel': row['numero_factura'], 'factura_parser': parsed.numero_factura, 'fecha_excel': row['fecha_factura'], 'fecha_parser': parsed.fecha_factura, 'total_excel': row['total'], 'total_parser': parsed.total, 'OK': ok, 'ok_fact': ok_fact, 'ok_fecha': ok_fecha, 'ok_total': ok_total})

print('|archivo|factura_excel|factura_parser|fecha_excel|fecha_parser|total_excel|total_parser|OK|')
for r in results:
    print('|' + '|'.join(str(r.get(k, "")) for k in ['archivo','factura_excel','factura_parser','fecha_excel','fecha_parser','total_excel','total_parser','OK']) + '|')
n = len(results)
n_ok = sum(1 for r in results if r['OK'])
n_fact = sum(1 for r in results if r['ok_fact'])
n_fecha = sum(1 for r in results if r['ok_fecha'])
n_total = sum(1 for r in results if r['ok_total'])
print(f'\nAcierto total: {n_ok/n*100:.1f}%')
print(f'Acierto factura: {n_fact/n*100:.1f}%')
print(f'Acierto fecha: {n_fecha/n*100:.1f}%')
print(f'Acierto total: {n_total/n*100:.1f}%')
print('\nMismatches:')
for r in results:
    if not r['OK']:
        print(r)
print('\nDiagnóstico final:', 'APTO' if n_ok/n>=0.95 else 'NO APTO')
