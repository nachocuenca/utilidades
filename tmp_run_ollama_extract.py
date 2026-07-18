import json
from pathlib import Path
from src.services.ai_service import AIService

PDFS = [
    "C:/Users/ignac/Desktop/utilidadesgit/data/runtime_probe_scan/factura-00074.pdf",
    "C:/Users/ignac/Desktop/utilidadesgit/data/runtime_probe_scan/factura-00116.pdf",
    "C:/Users/ignac/Desktop/utilidadesgit/data/runtime_probe_scan/factura-00127.pdf",
]

service = AIService(use_local_model=True)
results = []
for pdf in PDFS:
    res = service.process_file(pdf)
    print(f"Archivo: {pdf}")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    results.append({"archivo": pdf, **res["extraction"]})

# Exportar CSV
import csv
csv_path = "C:/Users/ignac/Desktop/utilidadesgit/tmp_ollama_extract_results.csv"
fields = list(results[0].keys())
with open(csv_path, "w", newline='', encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for row in results:
        writer.writerow(row)
print(f"CSV exportado: {csv_path}")
with open(csv_path, encoding="utf-8") as f:
    for i, line in enumerate(f):
        print(line.rstrip())
        if i >= 4:
            break
