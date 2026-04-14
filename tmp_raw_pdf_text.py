from src.pdf.reader import read_pdf_text_only
from pathlib import Path

pdf_path = Path(r"c:/Users/ignac/Desktop/utilidadesgit/data/inbox/Factura_26D013477-00110790- (1 de 2).PDF")
text = read_pdf_text_only(pdf_path)
print(text)
