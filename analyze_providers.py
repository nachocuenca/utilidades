import pandas as pd
import os
import re

df = pd.read_excel('data/acreedores benioffi.xlsx', sheet_name='facturas_20260414_124915')
pdfs = set(os.listdir('data/inbox'))
df = df[df['ruta_archivo'].apply(lambda x: isinstance(x, str) and x.strip() != '')]
df['pdf_exists'] = df['ruta_archivo'].apply(lambda x: os.path.basename(x) in pdfs)
df_real = df[df['pdf_exists']]
grouped = df_real.groupby('nombre_proveedor')
stats = []
for name, group in grouped:
    files = group['ruta_archivo'].tolist()
    count = len(files)
    examples = files[:3]
    # Heurística: si quitando dígitos y minúsculas, todos los nombres son iguales
    norm_names = set([re.sub(r'\d+', '', os.path.basename(f)).lower() for f in files])
    homog = len(norm_names) == 1
    stats.append((name, count, examples, homog))
stats.sort(key=lambda x: x[1], reverse=True)
print('PROVEEDORES TOP 5:')
for i, (name, count, examples, homog) in enumerate(stats[:5]):
    print(f'{i+1}. {name} | {count} facturas | Ejemplos: {examples} | Homogéneos: {homog}')
