from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pdfplumber
from pypdf import PdfReader

from src.pdf.text_cleaner import normalize_pdf_text


@dataclass(slots=True, frozen=True)
class PdfReadResult:
    file_path: Path
    text: str
    page_count: int
    extractor: str


def _read_with_pdfplumber(pdf_path: Path) -> tuple[str, int]:
    pages_text: list[str] = []

    with pdfplumber.open(pdf_path) as pdf_document:
        page_count = len(pdf_document.pages)

        for page in pdf_document.pages:
            page_text = page.extract_text() or ""
            pages_text.append(page_text)

    return "\n\n".join(pages_text), page_count


def _read_with_pypdf(pdf_path: Path) -> tuple[str, int]:
    reader = PdfReader(str(pdf_path))
    pages_text: list[str] = []

    for page in reader.pages:
        page_text = page.extract_text() or ""
        pages_text.append(page_text)

    return "\n\n".join(pages_text), len(reader.pages)


def read_pdf_text(pdf_path: str | Path) -> PdfReadResult:
    path = Path(pdf_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"No existe el PDF: {path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError(f"El archivo no es un PDF: {path}")

    pdfplumber_error: Exception | None = None

    try:
        raw_text, page_count = _read_with_pdfplumber(path)
        cleaned_text = normalize_pdf_text(raw_text)
        if cleaned_text:
            return PdfReadResult(
                file_path=path,
                text=cleaned_text,
                page_count=page_count,
                extractor="pdfplumber",
            )
    except Exception as error:
        pdfplumber_error = error

    try:
        raw_text, page_count = _read_with_pypdf(path)
        cleaned_text = normalize_pdf_text(raw_text)
        return PdfReadResult(
            file_path=path,
            text=cleaned_text,
            page_count=page_count,
            extractor="pypdf",
        )
    except Exception as pypdf_error:
        if pdfplumber_error is not None:
            raise RuntimeError(
                f"No se pudo leer el PDF con pdfplumber ni con pypdf: {path}"
            ) from pypdf_error
        raise RuntimeError(f"No se pudo leer el PDF: {path}") from pypdf_error


def read_pdf_text_only(pdf_path: str | Path) -> str:
    return read_pdf_text(pdf_path).text