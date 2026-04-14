import pandas as pd
from pathlib import Path
import json

# Leer Excel
excel_path = Path(r"c:/Users/ignac/Desktop/utilidadesgit/data/acreedores benioffi.xlsx")
df = pd.read_excel(excel_path, sheet_name="facturas_20260414_124915")

# PDFs en inbox
inbox_dir = Path(r"c:/Users/ignac/Desktop/utilidadesgit/data/inbox")
pdf_files = sorted([f for f in inbox_dir.iterdir() if f.suffix.lower() == ".pdf"])

# Mostrar nombres de los PDFs y filas del Excel
print("PDFs en inbox:")
for f in pdf_files:
    print(f.name)

print("\nPrimeras filas del Excel:")
print(df[["ruta_archivo", "numero_factura", "nombre_proveedor", "total"]].head(10))

# Emparejamiento exacto por ruta_archivo
matches = []

# Emparejamiento exacto por ruta_archivo
for _, row in df.iterrows():
    excel_pdf = Path(row["ruta_archivo"]).name
    for pdf in pdf_files:
        if pdf.name == excel_pdf:
            # Convertir todos los campos a tipos serializables
            row_dict = row.to_dict()
            for k, v in row_dict.items():
                if hasattr(v, 'isoformat'):
                    row_dict[k] = v.isoformat()
            matches.append({
                "pdf": pdf.name,
                "excel_row": row_dict
            })
            break

print(f"Coincidencias exactas por ruta_archivo: {len(matches)}")
for m in matches[:5]:
    print(json.dumps(m, indent=2, ensure_ascii=False))
