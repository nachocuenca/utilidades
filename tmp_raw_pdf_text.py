from src.pdf.reader import read_pdf_text_only
from pathlib import Path
import sys

if len(sys.argv) < 2:
	print("Uso: python tmp_raw_pdf_text.py <ruta_pdf>")
	sys.exit(1)

pdf_path = Path(sys.argv[1])
if not pdf_path.exists():
	print(f"ERROR: No existe el archivo: {pdf_path}")
	sys.exit(2)

text = read_pdf_text_only(pdf_path)
print(text)
