import pandas as pd
from pathlib import Path
from src.ai.local_extractor import LocalExtractor
import json

# Leer Excel
excel_path = Path(r"c:/Users/ignac/Desktop/utilidadesgit/data/acreedores benioffi.xlsx")
df = pd.read_excel(excel_path, sheet_name="facturas_20260414_124915")

# PDFs en inbox
inbox_dir = Path(r"c:/Users/ignac/Desktop/utilidadesgit/data/inbox")
pdf_files = sorted([f for f in inbox_dir.iterdir() if f.suffix.lower() == ".pdf"])

# Emparejamiento exacto por ruta_archivo
matches = []
for _, row in df.iterrows():
    excel_pdf = Path(row["ruta_archivo"]).name
    for pdf in pdf_files:
        if pdf.name == excel_pdf:
            row_dict = row.to_dict()
            for k, v in row_dict.items():
                if hasattr(v, 'isoformat'):
                    row_dict[k] = v.isoformat()
            matches.append({
                "pdf": pdf,
                "excel_row": row_dict
            })
            break

# Ejecutar 1 prueba real tras el cambio
extractor = LocalExtractor()
pdf_path = matches[0]["pdf"]
excel_row = matches[0]["excel_row"]
salida_ia = extractor.extract_from_pdf(pdf_path)
print(json.dumps({
    "pdf": pdf_path.name,
    "salida_ia": salida_ia,
    "excel": excel_row
}, indent=2, ensure_ascii=False))
