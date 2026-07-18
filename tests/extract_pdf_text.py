from pdfminer.high_level import extract_text
import sys

if __name__ == "__main__":
    pdf_path = sys.argv[1]
    txt_path = sys.argv[2]
    text = extract_text(pdf_path)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)
